import os
import pandas as pd
import anthropic

# ── Config ─────────────────────────────────────────────────────────────────
DEFAULT_CSV = "data/sample_data.csv"
FAVORABLE_THRESHOLD = 5.0   # % variance flagged as favorable
UNFAVORABLE_THRESHOLD = 5.0 # % variance flagged as unfavorable


# ── Data Loading ────────────────────────────────────────────────────────────
def load_data(filepath: str) -> pd.DataFrame:
    """Load CSV and validate required columns."""
    df = pd.read_csv(filepath)
    required = {"Category", "Line_Item", "Budget", "Actual"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing columns: {missing}")
    return df


# ── Variance Calculations ────────────────────────────────────────────────────
def calculate_variances(df: pd.DataFrame) -> pd.DataFrame:
    """Add variance columns to the dataframe."""
    df = df.copy()
    df["Variance_$"] = df["Actual"] - df["Budget"]
    df["Variance_%"] = ((df["Actual"] - df["Budget"]) / df["Budget"] * 100).round(2)

    # For expense categories, over-budget is unfavorable; for revenue it's favorable
    revenue_mask = df["Category"] == "Revenue"

    def label(row):
        pct = row["Variance_%"]
        is_revenue = row["Category"] == "Revenue"
        if is_revenue:
            if pct >= FAVORABLE_THRESHOLD:
                return "Favorable"
            elif pct <= -UNFAVORABLE_THRESHOLD:
                return "Unfavorable"
        else:
            if pct <= -FAVORABLE_THRESHOLD:
                return "Favorable"
            elif pct >= UNFAVORABLE_THRESHOLD:
                return "Unfavorable"
        return "On Track"

    df["Status"] = df.apply(label, axis=1)
    return df


def build_summary(df: pd.DataFrame) -> dict:
    """Compute category-level and overall P&L summary."""
    summary = {}

    for category in df["Category"].unique():
        cat_df = df[df["Category"] == category]
        summary[category] = {
            "budget_total": cat_df["Budget"].sum(),
            "actual_total": cat_df["Actual"].sum(),
            "variance_$": cat_df["Variance_$"].sum(),
            "variance_%": round(
                (cat_df["Variance_$"].sum() / cat_df["Budget"].sum()) * 100, 2
            ),
        }

    # Gross Profit
    rev_actual = df[df["Category"] == "Revenue"]["Actual"].sum()
    cogs_actual = df[df["Category"] == "COGS"]["Actual"].sum()
    rev_budget = df[df["Category"] == "Revenue"]["Budget"].sum()
    cogs_budget = df[df["Category"] == "COGS"]["Budget"].sum()

    summary["Gross_Profit"] = {
        "budget_total": rev_budget - cogs_budget,
        "actual_total": rev_actual - cogs_actual,
        "variance_$": (rev_actual - cogs_actual) - (rev_budget - cogs_budget),
        "variance_%": round(
            ((rev_actual - cogs_actual) - (rev_budget - cogs_budget))
            / (rev_budget - cogs_budget)
            * 100,
            2,
        ),
    }

    # Net Income (Revenue - COGS - OpEx)
    opex_actual = df[df["Category"] == "OpEx"]["Actual"].sum()
    opex_budget = df[df["Category"] == "OpEx"]["Budget"].sum()
    summary["Net_Income"] = {
        "budget_total": rev_budget - cogs_budget - opex_budget,
        "actual_total": rev_actual - cogs_actual - opex_actual,
        "variance_$": (rev_actual - cogs_actual - opex_actual)
        - (rev_budget - cogs_budget - opex_budget),
        "variance_%": round(
            ((rev_actual - cogs_actual - opex_actual) - (rev_budget - cogs_budget - opex_budget))
            / (rev_budget - cogs_budget - opex_budget)
            * 100,
            2,
        ),
    }

    return summary


# ── Prompt Engineering ───────────────────────────────────────────────────────
def build_prompt(df: pd.DataFrame, summary: dict) -> str:
    """Build the structured prompt for Claude."""

    # Line-item detail table
    detail_lines = []
    for _, row in df.iterrows():
        sign = "+" if row["Variance_$"] >= 0 else ""
        detail_lines.append(
            f"  {row['Category']} | {row['Line_Item']} | "
            f"Budget: ${row['Budget']:,.0f} | Actual: ${row['Actual']:,.0f} | "
            f"Variance: {sign}${row['Variance_$']:,.0f} ({sign}{row['Variance_%']}%) | {row['Status']}"
        )
    detail_table = "\n".join(detail_lines)

    # Summary table
    summary_lines = []
    for key, vals in summary.items():
        sign = "+" if vals["variance_$"] >= 0 else ""
        summary_lines.append(
            f"  {key}: Budget ${vals['budget_total']:,.0f} | "
            f"Actual ${vals['actual_total']:,.0f} | "
            f"Variance {sign}${vals['variance_$']:,.0f} ({sign}{vals['variance_%']}%)"
        )
    summary_table = "\n".join(summary_lines)

    flagged = df[df["Status"] != "On Track"]
    flagged_lines = []
    for _, row in flagged.iterrows():
        sign = "+" if row["Variance_$"] >= 0 else ""
        flagged_lines.append(
            f"  [{row['Status']}] {row['Line_Item']} ({row['Category']}): "
            f"{sign}${row['Variance_$']:,.0f} ({sign}{row['Variance_%']}%)"
        )
    flagged_table = "\n".join(flagged_lines) if flagged_lines else "  None — all line items within threshold."

    prompt = f"""You are a junior FP&A analyst preparing a weekly variance report for senior finance leadership.

Below is the budget vs. actual financial data for this reporting period.

=== P&L SUMMARY ===
{summary_table}

=== LINE-ITEM DETAIL ===
{detail_table}

=== FLAGGED ITEMS (>{FAVORABLE_THRESHOLD}% variance) ===
{flagged_table}

Write a concise variance analysis in plain English. Structure your response exactly as follows:

1. EXECUTIVE SUMMARY (2-3 sentences): Overall performance this period — are we ahead or behind, and by how much at the net income level?

2. REVENUE ANALYSIS: Comment on total revenue performance and call out any notable line items.

3. COST ANALYSIS (COGS & OpEx): Highlight where we are over or under budget and what that means for margins.

4. KEY CONCERNS: List the top 2-3 items finance leadership should focus on.

5. POSITIVES: List 1-2 things performing well.

6. RECOMMENDED ACTIONS: Brief, actionable recommendations (bullet points).

Keep the tone professional but direct. No filler language. Format numbers with $ and commas."""

    return prompt


# ── Claude API Call ──────────────────────────────────────────────────────────
def get_analysis(prompt: str) -> str:
    """Send prompt to Claude and return the analysis."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ── Output ───────────────────────────────────────────────────────────────────
def print_variance_table(df: pd.DataFrame):
    """Print a clean variance table to the console."""
    print("\n" + "=" * 70)
    print("  FP&A VARIANCE REPORT — LINE ITEM DETAIL")
    print("=" * 70)
    print(f"{'Category':<12} {'Line Item':<28} {'Budget':>10} {'Actual':>10} {'Var $':>10} {'Var %':>7} {'Status'}")
    print("-" * 90)

    current_category = None
    for _, row in df.iterrows():
        if row["Category"] != current_category:
            if current_category is not None:
                print()
            current_category = row["Category"]

        sign = "+" if row["Variance_$"] >= 0 else ""
        status_icon = {"Favorable": "✅", "Unfavorable": "⚠️ ", "On Track": "  "}.get(row["Status"], "")
        print(
            f"{row['Category']:<12} {row['Line_Item']:<28} "
            f"${row['Budget']:>9,.0f} ${row['Actual']:>9,.0f} "
            f"{sign}${row['Variance_$']:>8,.0f} {sign}{row['Variance_%']:>5.1f}% "
            f"{status_icon} {row['Status']}"
        )
    print("=" * 70)


def save_output(analysis: str, output_path: str = "output/variance_analysis.txt"):
    """Save the analysis to a text file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("FP&A VARIANCE ANALYSIS\n")
        f.write("=" * 60 + "\n\n")
        f.write(analysis)
    print(f"\n✅ Analysis saved to: {output_path}")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    import sys

    filepath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV

    print(f"\n📂 Loading data from: {filepath}")
    df = load_data(filepath)

    print("🔢 Calculating variances...")
    df = calculate_variances(df)
    summary = build_summary(df)

    print_variance_table(df)

    print("\n🤖 Sending to Claude API for analysis...")
    prompt = build_prompt(df, summary)
    analysis = get_analysis(prompt)

    print("\n" + "=" * 70)
    print("  CLAUDE FP&A ANALYSIS")
    print("=" * 70)
    print(analysis)

    save_output(analysis)


if __name__ == "__main__":
    main()
