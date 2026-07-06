from pathlib import Path
from io import StringIO
import pandas as pd
import re

DIR = Path("Consolidated_Schedule_of_Investments/2026-03-31/")
DIR_FILES = Path(DIR, "CSI_Forms")
OUTDIR = Path(DIR, "outputs")
OUTDIR.mkdir(exist_ok=True)

SCHEDULE_ANCHORS = [
    'id="T04"',
    "Consolidated Schedule of Investments"
]

END_MARKERS = [
    "Consolidated Statement of Assets and Liabilities",
    "Statement of Assets and Liabilities",
    "Consolidated Statement of Operations",
    "Statement of Operations",
    "Financial Highlights",
]

ASSET_CLASS_PREFIXES = (
    "Senior Secured Loans",
    "Private Investment Vehicles",
    "Collateralized Loan Obligations",
    "Preferred Stocks",
    "Asset-Backed Securities",
    "Common Stocks",
    "Subordinated Debt",
    "Warrants",
    "Corporate Bonds",
    "Equity Investments",
    "Warrants",
    "Short-Term Investments",
    "Cash Equivalents",
)


INVESTMENT_TYPE_BY_SECTION = (
    ("Collateralized Loan Obligation", ("Collateralized Loan Obligation", "CLO")),
    ("Common Stock", ("Common Stock", "Common Stocks")),
    ("Investment Partnership", ("Investment Partnership", "Investment Partnerships")),
    ("Private Investment Vehicle", ("Private Investment Vehicle", "Private Investment Vehicles")),
    ("Warrant", ("Warrant", "Warrants")),
)

CURRENCIES = {"USD", "EUR", "GBP", "NOK", "CAD", "CHF", "JPY", "AUD"}
NUM_PAT = re.compile(r"^\(?[\d,]+(?:\.\d+)?\)?$")
FOOTNOTE_SUFFIX_PAT = re.compile(r"^[\)\u200b\s]*")

def extract_schedule_html(text: str) -> str:
    start = -1
    
    # returns the index of the first match if found, otherwise it returns -1
    for anchor in SCHEDULE_ANCHORS:
        idx = text.find(anchor)
        if idx != -1:
            start = idx
            break          
    if start == -1:
        return ""

    # finding ending point
    end_candidates = [] # multiple end points
    for marker in END_MARKERS:
        idx = text.find(marker, start) # Search after start position.
        if idx != -1:
            end_candidates.append(idx)
            
    # if markers found choose earliest one otherwise file length
    end = min(end_candidates) if end_candidates else len(text)
    
    # return the portion of that file
    return text[start:end]


def combine_currency_amount(vals, start_index, span: int = 3) -> str:
    if start_index is None:
        return ""

    parts = []
    for idx in range(start_index, min(start_index + span, len(vals))):
        part = clean(vals[idx])
        if not part or part == "$":
            continue
        parts.append(part)

    if not parts:
        return ""

    combined = "".join(parts)
    combined = combined.replace("$", "").strip()
    combined = re.sub(r"\)([^)\d].*)$", ")", combined)

    if combined.startswith("(") and not combined.endswith(")"):
        combined = f"{combined})"

    return combined.strip()


# +
# removes extra spaces
# standardizes text
# converts to uppercase
def normalize_header_label(label: str) -> str:
    return re.sub(r"\s+", " ", str(label)).strip().upper()

def clean(x):
    if pd.isna(x):
        return ""
    text = str(x).replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()

# any number of spaces / tabs / newlines replaces them with a single space
def normalize_header_label(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip().upper()


def filing_part_name(filepath: Path) -> str:
    return filepath.stem # Returns the file name without its extension.


def pick_value(vals, index):
    if index is None or index >= len(vals):
        return ""
    return vals[index]

def is_blank_row(vals) -> bool:
    return all(v == "" for v in vals)


def is_section_row(vals, positions) -> bool:
    portfolio = pick_value(vals, positions["portfolio_company"])
    if not portfolio:
        return False
    nonempty = [i for i, v in enumerate(vals) if v]
    return nonempty == [positions["portfolio_company"]]


def classify_section(text: str) -> str | None:
    # print("text:", text)
    if "(continued)" in text.lower():
        return None
    if text.lower().startswith("total "):
        return "total"
    for prefix in ASSET_CLASS_PREFIXES:
        if text.startswith(prefix):
            return "asset_class"
    if "%" in text:
        # print("industry:", text)
        return "industry"
    return None


def combine_fair_value(vals, start_index, footnotes_index) -> str:
    amount = combine_currency_amount(vals, start_index, span=2)
    if amount.startswith("(") and not amount.endswith(")"):
        close_cell = pick_value(vals, footnotes_index)
        if close_cell.startswith(")"):
            amount = f"{amount})"
    return amount


def infer_investment_type(asset_class: str, industry: str, investment_type: str) -> str:
    if investment_type:
        return investment_type

    sections = f"{asset_class} {industry}"
    for inferred, markers in INVESTMENT_TYPE_BY_SECTION:
        if any(marker in sections for marker in markers):
            return inferred
    return "Other"


def parse_footnotes(vals, footnotes_index) -> str:
    footnotes = pick_value(vals, footnotes_index)
    footnotes = FOOTNOTE_SUFFIX_PAT.sub("", footnotes).lstrip(")").strip()
    return footnotes


def is_skip_text(text: str) -> bool:
    t = text.lower()
    return (
        not t
        or "accompanying notes" in t
        or "consolidated schedule of investments" in t
        or t.startswith("total ")
        or t == "portfolio company"
    )


def normalize_numeric(v: str):
    v = clean(v)
    if v in {"", "-", "—"}:
        return pd.NA
    return v


# -

def detect_header_positions(df: pd.DataFrame):
    for ridx in range(min(5, len(df))):
        vals = [clean(v) for v in df.iloc[ridx].tolist()]
        normalized = [normalize_header_label(v) for v in vals if v]

        has_portfolio = any(v.startswith("PORTFOLIO COMPANY") for v in normalized)
        has_investment_type = any(v.startswith("INVESTMENT TYPE") for v in normalized)
        has_principal = any("PRINCIPAL AMOUNT" in v or "SHARES/ PRINCIPAL AMOUNT" in v for v in normalized)
        has_cost = "COST" in normalized
        has_fair_value = any(v.startswith("FAIR VALUE") or v == "FAIR VALUE" for v in normalized)

        if has_portfolio and has_investment_type and has_principal and has_cost and has_fair_value:
            label_map = {normalize_header_label(v): i for i, v in enumerate(vals) if v}

            def find_index(*candidates: str):
                for candidate in candidates:
                    idx = label_map.get(candidate)
                    if idx is not None:
                        return idx
                return None

            def leftmost_label_index(*labels: str):
                idxs = [
                    i
                    for i, v in enumerate(vals)
                    if normalize_header_label(v) in labels
                    or any(normalize_header_label(v).startswith(label) for label in labels)
                ]
                return min(idxs) if idxs else None

            return {
                "header_row": ridx,
                "portfolio_company": 0,
                "investment_type": find_index("INVESTMENT TYPE"),
                "interest_rate": find_index("INTEREST RATE"),
                "reference_rate": find_index("REFERENCE RATE"),
                "basis_points_spread": find_index("BASIS POINTS SPREAD"),
                "maturity_date": find_index("MATURITY DATE"),
                "currency": find_index("CURRENCY"),
                "principal_amount": find_index(
                    "SHARES/ PRINCIPAL AMOUNT",
                    "SHARES/PRINCIPAL AMOUNT",
                ),
                "cost_start": leftmost_label_index("COST"),
                "fair_value_start": leftmost_label_index("FAIR VALUE"),
                "footnotes": find_index("FOOTNOTES"),
            }
    return None
    


def detect_piv_header_positions(df: pd.DataFrame):
    for ridx in range(min(5, len(df))):
        vals = [clean(v) for v in df.iloc[ridx].tolist()]
        normalized = [normalize_header_label(v) for v in vals if v]
        
        has_security = any(v.startswith("SECURITY") for v in normalized)
        has_acquisition_date = any("FIRST ACQUISITION DATE" in v for v in normalized)
        has_cost = "COST" in normalized

        if has_security and has_acquisition_date and has_cost:
            cost_idxs = [i for i, v in enumerate(vals) if normalize_header_label(v) == "COST"]
            date_idxs = [
                i for i, v in enumerate(vals) if "FIRST ACQUISITION DATE" in normalize_header_label(v)
            ]
            return {
                "header_row": ridx,
                "portfolio_company": 0,
                "first_acquisition_date": min(date_idxs) if date_idxs else None,
                "cost_start": min(cost_idxs) if cost_idxs else None,
            }
    return None


def parse_table(
    df: pd.DataFrame,
    part: str,
    table_index: int,
    asset_class: str = "",
    industry: str = "",
):
    positions = detect_header_positions(df)
    if not positions:
        return [], [], asset_class, industry

    rows = []
    rejects = []

    for row_index in range(positions["header_row"] + 1, len(df)):
        vals = [clean(v) for v in df.iloc[row_index].tolist()]
        if is_blank_row(vals):
            continue

        portfolio_company = pick_value(vals, positions["portfolio_company"])

        if is_section_row(vals, positions):
            section_kind = classify_section(portfolio_company)
            if section_kind == "asset_class":
                asset_class = portfolio_company
            elif section_kind == "industry":
                industry = portfolio_company
            continue

        joined = " | ".join([v for v in vals if v])
        upper = joined.upper()
        if "PORTFOLIO COMPANY" in upper and "FAIR VALUE" in upper:
            continue

        investment_type = pick_value(vals, positions["investment_type"])
        interest_rate = pick_value(vals, positions["interest_rate"])
        reference_rate = pick_value(vals, positions["reference_rate"])
        basis_points_spread = pick_value(vals, positions["basis_points_spread"])
        maturity_date = pick_value(vals, positions["maturity_date"])
        currency = pick_value(vals, positions["currency"])
        principal = pick_value(vals, positions["principal_amount"])
        cost = combine_currency_amount(vals, positions["cost_start"])
        fair_value = combine_fair_value(
            vals, positions["fair_value_start"], positions["footnotes"]
        )
        
        footnotes = parse_footnotes(vals, positions["footnotes"])

        if investment_type in CURRENCIES:
            currency = investment_type
            principal = interest_rate
            interest_rate = ""
            reference_rate = ""
            basis_points_spread = ""
            maturity_date = ""
            investment_type = ""
        elif investment_type and "%" in investment_type:
            if not interest_rate or "%" not in interest_rate:
                interest_rate = investment_type
            investment_type = ""

        investment_type = infer_investment_type(asset_class, industry, investment_type)

        principal_ok = bool(NUM_PAT.match(principal))
        cost_ok = bool(NUM_PAT.match(cost)) or cost in {"", "-", "—"}
        fair_ok = bool(NUM_PAT.match(fair_value)) or fair_value in {"", "-", "—"}

        if not principal_ok and cost_ok:
            principal = "0"
            principal_ok = bool(NUM_PAT.match(principal))

        if (
            portfolio_company
            and not is_skip_text(portfolio_company)
            and principal_ok
            and cost_ok
            and fair_ok
        ):
            rows.append({
                "portfolio_company": portfolio_company,
                "investment_type": investment_type,
                "interest_rate": interest_rate,
                "reference_rate": reference_rate,
                "basis_points_spread": basis_points_spread,
                "maturity_date": maturity_date,
                "currency": currency,
                "principal_amount": normalize_numeric(principal),
                "cost": normalize_numeric(cost),
                "fair_value": normalize_numeric(fair_value),
                "footnotes": footnotes,
                "first_acquisition_date": "",
                "asset_class": asset_class,
                "industry": industry,
                "part": part,
                "table_index": table_index,
                "row_index": row_index,
            })
        else:
            if joined and not is_skip_text(portfolio_company):
                rejects.append({
                    "part": part,
                    "table_index": table_index,
                    "row_index": row_index,
                    "raw_row": joined,
                })

    if(table_index == 41):
        row_df = pd.DataFrame(rows)
        matching_rows = row_df[row_df["portfolio_company"].isin(["Liabilities Less Other Assets (4.2)%", "Net Assets 100.0%"])]
        if not matching_rows.empty:
            rows = [o for o in rows if o["portfolio_company"] not in {"Net Assets 100.0%", "Liabilities Less Other Assets (4.2)%"}]  
            
    return rows, rejects, asset_class, industry


def parse_piv_table(
    df: pd.DataFrame,
    part: str,
    table_index: int,
    asset_class: str = "",
    industry: str = "",
):
    positions = detect_piv_header_positions(df)
    if not positions:
        return [], [], asset_class, industry

        
    rows = []
    rejects = []

    for row_index in range(positions["header_row"] + 1, len(df)):
        vals = [clean(v) for v in df.iloc[row_index].tolist()]
        if is_blank_row(vals):
            continue

        portfolio_company = pick_value(vals, positions["portfolio_company"])
        if is_section_row(vals, positions):
            section_kind = classify_section(portfolio_company)
            if section_kind == "asset_class":
                asset_class = portfolio_company
            elif section_kind == "industry":
                industry = portfolio_company
            continue

        acquisition_date = pick_value(vals, positions["first_acquisition_date"])
        cost = combine_currency_amount(vals, positions["cost_start"])
        if not cost:
            numeric_cells = [v for v in vals if v and NUM_PAT.match(v)]
            cost = numeric_cells[-1] if numeric_cells else ""

        joined = " | ".join([v for v in vals if v])
        cost_ok = bool(NUM_PAT.match(cost))

        if portfolio_company and not is_skip_text(portfolio_company) and cost_ok:
            rows.append({
                "portfolio_company": portfolio_company,
                "investment_type": "Private Investment Vehicle",
                "interest_rate": "",
                "reference_rate": "",
                "basis_points_spread": "",
                "maturity_date": "",
                "currency": "",
                "principal_amount": normalize_numeric(cost),
                "cost": normalize_numeric(cost),
                "fair_value": pd.NA,
                "footnotes": "",
                "first_acquisition_date": acquisition_date,
                "asset_class": asset_class,
                "industry": industry,
                "part": part,
                "table_index": table_index,
                "row_index": row_index,
            })
        elif joined and not is_skip_text(portfolio_company):
            rejects.append({
                "part": part,
                "table_index": table_index,
                "row_index": row_index,
                "raw_row": joined,
            })

    return rows, rejects, asset_class, industry


# +
def main():
    all_clean = []

    for filepath in sorted(DIR_FILES.iterdir()):
        if filepath.suffix.lower() not in {".htm", ".html"}:
            continue

        part = filing_part_name(filepath)
        html = filepath.read_text(errors="ignore")
        snippet = extract_schedule_html(html)
        (OUTDIR / f"{part}_schedule_snippet.html").write_text(snippet, encoding="utf-8") # make new file and put extracted html in it

        tables = pd.read_html(StringIO(snippet), flavor="lxml")
        part_rows = []
        part_rejects = []
        candidate_tables = 0
        asset_class = ""
        industry = ""
        
        for table_index, df in enumerate(tables):
            if detect_header_positions(df):
                candidate_tables += 1
                rows, rejects, asset_class, industry = parse_table(
                    df, part, table_index, asset_class, industry
                )
                part_rows.extend(rows)
                part_rejects.extend(rejects)
                
            elif detect_piv_header_positions(df):
                candidate_tables += 1
                rows, rejects, asset_class, industry = parse_piv_table(
                    df, part, table_index, asset_class, industry
                )
                part_rows.extend(rows)
                part_rejects.extend(rejects)

        part_df = pd.DataFrame(part_rows)

        if not part_df.empty:
            part_df = part_df.sort_values(["table_index", "row_index"], kind="stable").reset_index(drop=True)

        all_clean.append(part_df)

    master_df = pd.concat(all_clean, ignore_index=True) if all_clean else pd.DataFrame()
    
    dedup_cols = [
        "portfolio_company",
        "investment_type",
        "interest_rate",
        "reference_rate",
        "basis_points_spread",
        "maturity_date",
        "currency",
        "principal_amount",
        "cost",
        "fair_value",
        "footnotes",
        "first_acquisition_date",
        "asset_class",
        "industry",
    ]
    if not master_df.empty:
        master_dedup_df = master_df.drop_duplicates(subset=dedup_cols, keep="first").reset_index(drop=True)
    else:
        master_dedup_df = master_df
    master_dedup_df.to_csv(OUTDIR / "consolidated_schedule_master_deduped.csv", index=False)


main()
# -








