import re
import sys
import pdfplumber
import pandas as pd


def extract_lines(pdf_path: str) -> list:
    """Pull raw text from page 1 and split into lines."""
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text()
    return text.split("\n")


def clean_number(val: str) -> float:
    """Convert '$ 1,234', '(52)', '1,234' etc. into a float."""
    val = val.strip()
    negative = val.startswith("(") and val.endswith(")")
    val = val.replace("(", "").replace(")", "").replace(",", "").replace("$", "").strip()
    num = float(val)
    return -num if negative else num


def parse_financial_line(line: str):
    """
    Given a line like 'iPhone $ 56,994 $ 46,841 $ 142,263 $ 115,979',
    return (label, [list of numbers found]).
    """
    numbers = re.findall(r"\(?\$?\s?-?[\d,]+\.?\d*\)?", line)
    numbers = [n for n in numbers if re.search(r"\d", n)]
    if not numbers:
        return None, []

    # Label is everything before the first number
    first_num_pos = line.find(numbers[0])
    label = line[:first_num_pos].strip()
    values = [clean_number(n) for n in numbers]
    return label, values


def build_variance_csv(pdf_path: str, output_csv: str):
    """
    Parse Apple's condensed income statement PDF section-by-section
    (tracking which header each line falls under) and build a
    Budget (prior-year quarter) vs Actual (current quarter) CSV
    in the format analyzer.py expects.
    """
    lines = extract_lines(pdf_path)

    # Map of section header -> Category label for our CSV,
    # and which line labels within that section we want to keep.
    section_map = {
        "Cost of sales:": {
            "category": "COGS",
            "keep": {"Products": "Cost of Sales - Products", "Services": "Cost of Sales - Services"},
        },
        "Operating expenses:": {
            "category": "OpEx",
            "keep": {
                "Research and development": "Research & Development",
                "Selling, general and administrative": "SG&A",
            },
        },
        "(1) Net sales by category:": {
            "category": "Revenue",
            "keep": {
                "iPhone": "iPhone",
                "Mac": "Mac",
                "iPad": "iPad",
                "Wearables, Home and Accessories": "Wearables, Home & Accessories",
                "Services": "Services",
            },
        },
    }

    current_section = None
    rows = []

    for line in lines:
        stripped = line.strip()

        # Check if this line is a section header
        if stripped in section_map:
            current_section = stripped
            continue

        # Stop tracking a section once we hit a new header-like line
        if current_section and (stripped.endswith(":") and stripped not in section_map):
            current_section = None

        if current_section is None:
            continue

        section = section_map[current_section]
        label, values = parse_financial_line(line)
        if label is None or label not in section["keep"]:
            continue

        if len(values) < 2:
            continue

        # Column order in PDF: [Current Qtr, Prior-Year Qtr, Current 6mo, Prior-Year 6mo]
        actual, budget = values[0], values[1]
        rows.append({
            "Category": section["category"],
            "Line_Item": section["keep"][label],
            "Budget": budget,
            "Actual": actual,
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)

    print(f"✅ Parsed {len(df)} line items from PDF")
    print(f"✅ Saved structured data to: {output_csv}\n")
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "data/apple_10q.pdf"
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "data/apple_parsed.csv"
    build_variance_csv(pdf_path, output_csv)
