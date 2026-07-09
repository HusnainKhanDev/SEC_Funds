# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.19.4
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

from pathlib import Path
from io import StringIO
import pandas as pd
import re

DIR = Path("Consolidated_Schedule_of_Investments/2026-03-31/")
DIR_FILES = Path(DIR, "soi_forms")
OUTDIR = Path(DIR, "outputs")
OUTDIR.mkdir(exist_ok=True)

# +
SCHEDULE_ANCHORS = [
    'id="i7c329d3810f6476b8e4196721ec52e5a_6597069769709"',
    "Consolidated Schedule of Investments"
]

END_MARKERS = [
    "Consolidated Statement of Assets and Liabilities",
    "Statement of Assets and Liabilities",
    "Consolidated Statement of Operations",
    "Commitment Type",
    "Statement of Operations",
    'ix:footnote id="fn-1"',
    # "Financial Highlights",
]

industry_list = (
  "Aerospace & Defense", "Air Freight & Logistics", "Airlines (Passenger Airlines)", "Automotive", "Biotechnology", "Building Products",
  "Capital Markets", "Chemicals", "Commercial Services & Supplies", "Construction & Engineering", "Containers & Packaging", "Distributors",
  "Diversified Consumer Services", "Diversified REITs", "Diversified Telecommunication Services", "Electric Utilities", "Electrical Equipment",
  "Electronic Equipment, Instruments & Components", "Energy Equipment & Services", "Entertainment", "Financial Services","Food Products",
  "Ground Transportation", "Health Care Equipment & Supplies", "Health Care Providers & Services", "Health Care Technology",
  "Hotels, Restaurants & Leisure", "Household Durables", "Industrial Conglomerates", "Insurance", "Interactive Media & Services", "IT Services",
  "Life Sciences Tools & Services", "Machinery", "Marine Transportation", "Media", "Metals & Mining", "Oil, Gas & Consumable Fuels", "Paper & Forest Products",
  "Pharmaceuticals","Professional Services", "Real Estate Management & Development", "Semiconductors & Semiconductor Equipment",
  "Software", "Specialty Retail", "Technology Hardware, Storage & Peripherals", "Trading Companies & Distributors", "Transportation Infrastructure",
  "Wireless Telecommunication Services"
)

instrument = (
  "First Lien Debt",
  "Second Lien Debt",
  "Unsecured Debt",
  "Structured Finance Obligations",
  "Equity and other"
)


investment_type = (
  "First Lien Debt - non-controlled/non-affiliated",
  "First Lien Debt - non-controlled/affiliated",
  "First Lien Debt - controlled/affiliated",
  "Second Lien Debt - non-controlled/non-affiliated",
  "Unsecured Debt - non-controlled/non-affiliated",
  "Structured Finance Obligations - Debt Instruments - non-controlled/non-affiliated",
  "Structured Finance Obligations - Equity Instruments - non-controlled/non-affiliated",
  "Equity and other - non-controlled/non-affiliated",
  "Equity and other - non-controlled/affiliated",
  "Equity and other - controlled/affiliated (excluding Investments in Joint Ventures)",
  "Investments in Joint Ventures",
  "Cash and Cash Equivalents",
)

CURRENCIES = {"USD", "EUR", "GBP", "NOK", "CAD", "CHF", "JPY", "AUD"}
NUM_PAT = re.compile(r"^\(?[\d,]+(?:\.\d+)?\)?$")
FOOTNOTE_SUFFIX_PAT = re.compile(r"^[\)\u200b\s]*")


# -

def extract_schedule_html(text: str) -> str:
    start = -1
    
    # returns the index of the first match if found, otherwise it returns -1
    for anchor in SCHEDULE_ANCHORS:
        idx = text.find(anchor)
        if idx != -1:
            print("Start anchor: ", anchor, idx)
            start = idx
            break          
    if start == -1:
        return ""

    # finding ending point
    end_candidates = [] # multiple end points
    for marker in END_MARKERS:
        idx = text.find(marker, start) # Search after start position.
        if idx != -1:
            print("End marker: ", marker, idx)
            end_candidates.append(idx)
            
    # if markers found choose earliest one otherwise file length
    end = min(end_candidates) if end_candidates else len(text)
    print("End", end)
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
    val = re.sub(r"\s+", " ", label).strip().upper()
    return val


def filing_part_name(filepath: Path) -> str:
    return filepath.stem # Returns the file name without its extension.


def pick_value(vals, index):
    if index is None or index >= len(vals):
        return ""
    return vals[index]

def is_blank_row(vals) -> bool:
    return all(v == "" for v in vals)


from itertools import groupby

def is_section_row(vals, positions) -> bool:
    portfolio = pick_value(vals, positions["investments"])
    if not portfolio:
        return False

    values = [v for v in vals if v]

    if not values:
        return False
    
    return all(v == values[0] for v in values)


def normalize_section(text):
    return clean(text).replace("(continued)", "").strip().lower()

    
def classify_section(text: str) -> str | None:
        
    norm = normalize_section(text)
    
    
    
    if any(normalize_section(x) == norm for x in industry_list):
        return "industry", norm
    
    elif any(normalize_section(x) == norm for x in instrument):
        return "instrument", norm
    
    elif any(normalize_section(x) == norm for x in investment_type):
        print(norm)
        return "investment type", norm
        
    return None, text


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

def combine_rate_spread(v:str, v2:str):
    # print("v1", v)
    # print("v2", v2)
    # print("=" * 30)
    return v + " " + v2


# -

def detect_header_positions(df: pd.DataFrame):
    for ridx in range(min(5, len(df))):
        vals = [clean(v) for v in df.iloc[ridx].tolist()]
        normalized = [normalize_header_label(v) for v in vals if v]
        
        reference_rate = any(v.startswith("REFERENCE RATE AND SPREAD") for v in normalized)
        interest_rate = any(v.startswith("INTEREST RATE") for v in normalized)
        acquisition_date = any("ACQUISITION DATE" in v for v in normalized)
        maturity_date = any(v.startswith("MATURITY DATE") for v in normalized)
        par_amount_units  = any(v.startswith("PAR AMOUNT/UNITS") for v in normalized)
        net_assets = any(v.startswith("% OF NET ASSETS") for v in normalized)
        has_fair_value = any(v.startswith("FAIR VALUE") or v == "FAIR VALUE" for v in normalized)
        has_cost = any(v.startswith("COST") for v in normalized)

        if reference_rate and interest_rate and acquisition_date and maturity_date and par_amount_units and net_assets and has_fair_value and has_cost:
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

            obj = {
                "header_row": ridx,
                "investments": find_index("INVESTMENTS (1)(19)"),
                "reference_rate": find_index("REFERENCE RATE AND SPREAD (2)"),
                "interest_rate": find_index("INTEREST RATE (2)(15)"),
                "acquisition_date": find_index("ACQUISITION DATE"),
                "maturity_date": find_index("MATURITY DATE"),
                "par_amount_units": find_index("PAR AMOUNT/UNITS (1)") - 1, #40 - 1
                "net_assets": find_index("% OF NET ASSETS") - 2, # 59-2
                "cost_start": leftmost_label_index("COST (3)") + 1,
                "fair_value_start": leftmost_label_index("FAIR VALUE") + 1
            }
    
            return obj
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
    investment_type: str = "", 
    industry: str = "", 
    instrument: str = ""
):
    positions = detect_header_positions(df)
    print("positions", positions)
    if not positions:
        return [], [], asset_class, industry
        
    rows = []
    rejects = []

    for row_index in range(positions["header_row"], len(df)):
        vals = [clean(v) for v in df.iloc[row_index].tolist()]
        if is_blank_row(vals):
            continue


        investments = pick_value(vals, positions["investments"])
        if is_section_row(vals, positions):
            section_kind, sec = classify_section(investments)
            if section_kind == "industry":
                industry = sec
            elif section_kind == "instrument":
                instrument = sec
            elif section_kind == "investment type":
                investment_type = sec
            

        joined = " | ".join([v for v in vals if v])
        upper = joined.upper()
        if "INVESTMENTS" in upper and "FAIR VALUE" in upper:
            continue
            
        reference_rate = combine_rate_spread(pick_value(vals, 12), pick_value(vals, positions["reference_rate"]))
        interest_rate = pick_value(vals, positions["interest_rate"])
        acquisition_date = pick_value(vals, positions["acquisition_date"])
        maturity_date = pick_value(vals, positions["maturity_date"])
        par_amount_units = pick_value(vals, positions["par_amount_units"])
        net_assets = pick_value(vals, positions["net_assets"])
        cost = pick_value(vals, positions["cost_start"])
        fair_value = pick_value(vals, positions["fair_value_start"])
                      
        
        
        all_keys = positions.keys()
        
        
        cost_ok = bool(NUM_PAT.match(cost)) or cost in {"", "-", "—"}
        fair_ok = bool(NUM_PAT.match(fair_value)) or fair_value in {"", "-", "—"}


        if (
            investments
            and not is_skip_text(investments)
            and cost_ok
            and fair_ok
        ):

            obj = {
                "investments": investments,
                "reference_rate": reference_rate,
                "interest_rate": interest_rate,
                "industry": industry,
                "instrument": instrument,
                "investment_type": investment_type,
                "acquisition_date": acquisition_date,
                "maturity_date": maturity_date,
                "par_amount_units": normalize_numeric(par_amount_units),
                "net_assets": normalize_numeric(net_assets),
                "cost": normalize_numeric(cost),
                "fair_value": normalize_numeric(fair_value),
                "part": part,
                "table_index": table_index,
                "row_index": row_index,
            }
            if investment_type == "Cash and Cash Equivalents":
                print(obj)
                
            rows.append(obj)
            
        else:
            if joined and not is_skip_text(investments):
                rejects.append({
                    "par_amout": normalize_numeric(par_amount_units),
                    "part": part,
                    "table_index": table_index,
                    "row_index": row_index,
                    "raw_row": joined,
                })


    row_df = pd.DataFrame(rows)
    matching_rows = row_df[row_df["investments"].isin(["Other Cash and Cash Equivalents"])]
    if not matching_rows.empty:
        rows = [o for o in rows if o["investments"] not in {"Other Cash and Cash Equivalents"}]  
    
    return rows, rejects, investment_type, industry, instrument


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
    for row_index in range(positions["header_row"], len(df)):
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
        filename = str(filepath).split("/")[-1].split(".")[0]
        part = filing_part_name(filepath)
        html = filepath.read_text(errors="ignore")
        snippet = extract_schedule_html(html)
        tables = pd.read_html(StringIO(snippet), flavor="lxml")
        
        part_rows = []
        candidate_tables = 0
        investment_type = industry = instrument = ""
        
        for table_index, df in enumerate(tables):
            # if table_index == 1: break
            
            if detect_header_positions(df):
                candidate_tables += 1
                rows, rejects, investment_type, industry, instrument = parse_table(
                    df, part, table_index, investment_type, industry, instrument
                )
                part_rows.extend(rows)
                
            elif detect_piv_header_positions(df):
                candidate_tables += 1
                rows, rejects, asset_class, industry = parse_piv_table(
                    df, part, table_index, asset_class, industry
                )
                part_rows.extend(rows)

        part_df = pd.DataFrame(part_rows)
        if not part_df.empty:
            part_df = part_df.sort_values(["table_index", "row_index"], kind="stable").reset_index(drop=True)

        all_clean.append(part_df)
        master_df = pd.concat(all_clean, ignore_index=True) if all_clean else pd.DataFrame()

    dedup_cols = [
        "investments",
        "reference_rate",
        "interest_rate",
        "acquisition_date",
        "maturity_date",
        "par_amount_units",
        "net_assets",
        "cost",
        "fair_value",
    ]

    if not master_df.empty:
        master_dedup_df = master_df.drop_duplicates(subset=dedup_cols, keep="first").reset_index(drop=True)
    else:
        master_dedup_df = master_df
    master_dedup_df.to_csv(OUTDIR / f"{filename}.csv", index=False)

main()
# -






