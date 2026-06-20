# FP&A Variance Analyzer

A Python tool that reads budget vs. actual financial data from a CSV, calculates variances, and uses the Claude API to generate a plain-English variance analysis — the kind a junior FP&A analyst would write for a weekly finance review.

## What It Does

- Loads a CSV of budget vs. actual figures across revenue, COGS, and OpEx
- Calculates dollar and percentage variances for every line item
- Flags items that exceed a configurable threshold (default: ±5%)
- Builds a structured P&L summary (gross profit, net income)
- Sends the data to Claude with a finance analyst prompt
- Outputs a formatted variance report with executive summary, key concerns, and recommended actions

## Project Structure

```
fpa-variance-analyzer/
├── analyzer.py          # Main script
├── requirements.txt
├── README.md
├── data/
│   └── sample_data.csv  # Sample P&L dataset (revenue, COGS, OpEx)
└── output/
    └── variance_analysis.txt  # Generated after running
```

## Setup

**1. Clone the repo and install dependencies**
```bash
git clone https://github.com/yourusername/fpa-variance-analyzer.git
cd fpa-variance-analyzer
pip install -r requirements.txt
```

**2. Set your Anthropic API key**
```bash
# Mac/Linux
export ANTHROPIC_API_KEY="your-key-here"

# Windows (Command Prompt)
set ANTHROPIC_API_KEY=your-key-here
```
Get a free API key at [console.anthropic.com](https://console.anthropic.com)

**3. Run with the sample dataset**
```bash
python analyzer.py
```

**4. Run with your own CSV**
```bash
python analyzer.py path/to/your_data.csv
```

## CSV Format

Your CSV must have these four columns:

| Column | Description | Example |
|--------|-------------|---------|
| `Category` | Revenue, COGS, or OpEx | `Revenue` |
| `Line_Item` | Name of the line item | `Product Sales` |
| `Budget` | Budgeted amount (number) | `500000` |
| `Actual` | Actual amount (number) | `487000` |

## Sample Output

```
======================================================================
  FP&A VARIANCE REPORT — LINE ITEM DETAIL
======================================================================
Category     Line Item                    Budget     Actual      Var $   Var %  Status
------------------------------------------------------------------------------------------
Revenue      Product Sales             $500,000   $487,000   -$13,000  -2.6%    On Track
Revenue      Service Revenue           $150,000   $162,000   +$12,000  +8.0%  ✅ Favorable
...

======================================================================
  CLAUDE FP&A ANALYSIS
======================================================================
1. EXECUTIVE SUMMARY
Net income came in at $X vs. budget of $Y...
```

## Configuration

At the top of `analyzer.py` you can adjust:

```python
FAVORABLE_THRESHOLD = 5.0    # % above budget flagged as favorable (revenue)
UNFAVORABLE_THRESHOLD = 5.0  # % over budget flagged as unfavorable (expenses)
```

## Stack

- Python 3.9+
- [Pandas](https://pandas.pydata.org/) — data loading and variance calculations
- [Anthropic Python SDK](https://github.com/anthropic/anthropic-sdk-python) — Claude API
- Claude claude-opus-4-6 — variance narrative generation

## Use Cases

- Weekly or monthly finance review prep
- Budget vs. actual reporting automation
- Learning prompt engineering with structured financial data
- Resume project demonstrating AI + finance + Python
