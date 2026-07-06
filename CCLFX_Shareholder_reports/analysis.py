import pandas as pd
from pathlib import Path
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from gspread_formatting import *

DIR_PATH = Path("Consolidated_Schedule_of_Investments/2025-09-30/")
CONSOLIDATED_CSV_PATH = Path(DIR_PATH, "outputs/consolidated_schedule_master_deduped.csv")
ANALYSIS_PATH = Path(DIR_PATH, "analysis")
ANALYSIS_PATH.mkdir(exist_ok=True)

DIR_PATH.exists(), CONSOLIDATED_CSV_PATH.exists(), ANALYSIS_PATH.exists()

df_investment = pd.read_csv(CONSOLIDATED_CSV_PATH)
df_investment.info()


for col in ["cost", "fair_value"]:
    df_investment[col] = (
        df_investment[col]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
        .replace("nan", pd.NA)
    )

    df_investment[col] = pd.to_numeric(df_investment[col], errors="coerce").astype("Int64")

df_investment.drop(columns=["part", "table_index", "row_index", "footnotes"], inplace=True)
df_investment
# -

df_investment["profit"] = df_investment["fair_value"] - df_investment["cost"]
df_investment["is_profit"] = df_investment["profit"] > 0
df_investment["is_loss"] = df_investment["profit"] < 0
df_investment["is_breakeven"] = df_investment["profit"] == 0
df_investment

# +
# High-Level Summary
df_summary = pd.DataFrame({
    "a": [
        "Total Investment Count",
        "Total Prinicipal Amount", 
        "Total Cost", 
        "Total FV", 
        "P&L"
    ],
    "b": [
        len(df_investment),
        int(df_investment["principal_amount"].sum()),
        int(df_investment["cost"].sum()),
        int(df_investment["fair_value"].sum()),
        int(df_investment["fair_value"].sum())-int(df_investment["cost"].sum()),
    ]
})

df_summary
# -

df_investment

# +
# Company-Level Analysis
df_company_level_analysis = (
    df_investment.groupby("portfolio_company")
      .agg(
          total_investments=("portfolio_company", "count"),

          # counts
          profitable_count=("is_profit", "sum"),
          loss_count=("is_loss", "sum"),
          breakeven_count=("is_breakeven", "sum"),

          # financials
          total_cost=("cost", "sum"),
          total_fair_value=("fair_value", "sum"),
          total_profit=("profit", "sum"),

          # averages
          avg_profit=("profit", "mean"),

          # risk
          max_profit=("profit", "max"),
          max_loss=("profit", "min")
      )
)

df_company_level_analysis.reset_index(names="Portfolio Company", inplace=True)
df_company_level_analysis["avg_profit"] = round(df_company_level_analysis["avg_profit"], 2)

# win, breakeven, and loss rate
df_company_level_analysis["win_rate"] = round(
    df_company_level_analysis["profitable_count"] /
    df_company_level_analysis["total_investments"]
, 2)

df_company_level_analysis["breakeven_rate"] = round(
    df_company_level_analysis["breakeven_count"] /
    df_company_level_analysis["total_investments"]
, 2)

df_company_level_analysis["loss_rate"] = round(
    df_company_level_analysis["loss_count"] /
    df_company_level_analysis["total_investments"]
, 2)

# sort by total no investments
df_company_level_analysis = df_company_level_analysis.sort_values(
    by="total_fair_value", ascending=False
)


column_mapping = {
    "total_investments": "Total Investment Count",
    "total_cost": "Total Investment Cost",
    "total_fair_value": "Total Investment FV",
    "total_profit": "Total Investment P&L",
    "avg_profit": "Avg Profit/Investment",
    "max_profit": "Max Profit Investment",
    "max_loss": "Max Loss Investment",
    "profitable_count": "Profitable Investment Count",
    "win_rate": "Profitable %",
    "breakeven_count": "Breakeven Investment Count",
    "breakeven_rate": "Breakeven %",
    "loss_count": "Loss Investment Count",
    "loss_rate": "Loss %"
}
desired_order = [
    "Portfolio Company",
    "Total Investment Count",
    "Total Investment Cost",
    "Total Investment FV",
    "Total Investment P&L",
    "Avg Profit/Investment",
    "Max Profit Investment",
    "Max Loss Investment",
    "Profitable Investment Count",
    "Profitable %",
    "Breakeven Investment Count",
    "Breakeven %",
    "Loss Investment Count",
    "Loss %"
]

df_company_level_analysis = df_company_level_analysis.rename(columns=column_mapping).reindex(columns=desired_order)


df_industry_level_analysis = (
    df_investment.groupby("industry")
      .agg(
          total_investments=("portfolio_company", "count"),

          # counts
          profitable_count=("is_profit", "sum"),
          loss_count=("is_loss", "sum"),
          breakeven_count=("is_breakeven", "sum"),

          # financials
          total_cost=("cost", "sum"),
          total_fair_value=("fair_value", "sum"),
          total_profit=("profit", "sum"),

          # averages
          avg_profit=("profit", "mean"),

          # risk
          max_profit=("profit", "max"),
          max_loss=("profit", "min")
      )
)

df_industry_level_analysis.reset_index(names="Industry", inplace=True)
df_industry_level_analysis["avg_profit"] = round(df_industry_level_analysis["avg_profit"], 2)

# win, breakeven, and loss rate
df_industry_level_analysis["win_rate"] = round(
    df_industry_level_analysis["profitable_count"] /
    df_industry_level_analysis["total_investments"]
, 2)

df_industry_level_analysis["breakeven_rate"] = round(
    df_industry_level_analysis["breakeven_count"] /
    df_industry_level_analysis["total_investments"]
, 2)

df_industry_level_analysis["loss_rate"] = round(
    df_industry_level_analysis["loss_count"] /
    df_industry_level_analysis["total_investments"]
, 2)

# sort by total no investments
df_industry_level_analysis = df_industry_level_analysis.sort_values(
    by="total_fair_value", ascending=False
)


column_mapping = {
    "total_investments": "Total Investment Count",
    "total_cost": "Total Investment Cost",
    "total_fair_value": "Total Investment FV",
    "total_profit": "Total Investment P&L",
    "avg_profit": "Avg Profit/Investment",
    "max_profit": "Max Profit Investment",
    "max_loss": "Max Loss Investment",
    "profitable_count": "Profitable Investment Count",
    "win_rate": "Profitable %",
    "breakeven_count": "Breakeven Investment Count",
    "breakeven_rate": "Breakeven %",
    "loss_count": "Loss Investment Count",
    "loss_rate": "Loss %"
}
desired_order = [
    "Industry",
    "Total Investment Count",
    "Total Investment Cost",
    "Total Investment FV",
    "Total Investment P&L",
    "Avg Profit/Investment",
    "Max Profit Investment",
    "Max Loss Investment",
    "Profitable Investment Count",
    "Profitable %",
    "Breakeven Investment Count",
    "Breakeven %",
    "Loss Investment Count",
    "Loss %"
]

df_industry_level_analysis = df_industry_level_analysis.rename(columns=column_mapping).reindex(columns=desired_order)




industry_list = list(df_industry_level_analysis["Industry"])


arrs = [v.split(" ") for v in industry_list]

perc = [v[-1] for v in arrs]
last = [v.pop() for v in arrs]

names = [" ".join(v) for v in arrs]

df_industry_level_analysis = df_industry_level_analysis.drop(columns=["Industry"])

df_industry_level_analysis.insert(0, "Industry", names)
df_industry_level_analysis.insert(1, "Percentage", perc)

# +
# Investment Type Level Analysis
df_investment_type_level_analysis = (
    df_investment.groupby("investment_type")
      .agg(
          total_investments=("portfolio_company", "count"),

          # counts
          profitable_count=("is_profit", "sum"),
          loss_count=("is_loss", "sum"),
          breakeven_count=("is_breakeven", "sum"),

          # financials
          total_cost=("cost", "sum"),
          total_fair_value=("fair_value", "sum"),
          total_profit=("profit", "sum"),

          # averages
          avg_profit=("profit", "mean"),

          # risk
          max_profit=("profit", "max"),
          max_loss=("profit", "min")
      )
)

df_investment_type_level_analysis.reset_index(names="Investment Type", inplace=True)
df_investment_type_level_analysis["avg_profit"] = round(df_investment_type_level_analysis["avg_profit"], 2)

# win, breakeven, and loss rate
df_investment_type_level_analysis["win_rate"] = round(
    df_investment_type_level_analysis["profitable_count"] /
    df_investment_type_level_analysis["total_investments"]
, 2)

df_investment_type_level_analysis["breakeven_rate"] = round(
    df_investment_type_level_analysis["breakeven_count"] /
    df_investment_type_level_analysis["total_investments"]
, 2)

df_investment_type_level_analysis["loss_rate"] = round(
    df_investment_type_level_analysis["loss_count"] /
    df_investment_type_level_analysis["total_investments"]
, 2)

# sort by total no investments
df_investment_type_level_analysis = df_investment_type_level_analysis.sort_values(
    by="total_fair_value", ascending=False
)


column_mapping = {
    "total_investments": "Total Investment Count",
    "total_cost": "Total Investment Cost",
    "total_fair_value": "Total Investment FV",
    "total_profit": "Total Investment P&L",
    "avg_profit": "Avg Profit/Investment",
    "max_profit": "Max Profit Investment",
    "max_loss": "Max Loss Investment",
    "profitable_count": "Profitable Investment Count",
    "win_rate": "Profitable %",
    "breakeven_count": "Breakeven Investment Count",
    "breakeven_rate": "Breakeven %",
    "loss_count": "Loss Investment Count",
    "loss_rate": "Loss %"
}
desired_order = [
    "Investment Type",
    "Total Investment Count",
    "Total Investment Cost",
    "Total Investment FV",
    "Total Investment P&L",
    "Avg Profit/Investment",
    "Max Profit Investment",
    "Max Loss Investment",
    "Profitable Investment Count",
    "Profitable %",
    "Breakeven Investment Count",
    "Breakeven %",
    "Loss Investment Count",
    "Loss %"
]

df_investment_type_level_analysis = df_investment_type_level_analysis.rename(columns=column_mapping).reindex(columns=desired_order)

# +
# Fromatting df_investments
column_mapping = {
    "portfolio_company": "Portfolio Company",
    "investment_type": "Investment Type",
    "interest_rate": "Interest Rate",
    "reference_rate": "Reference Rate",
    "basis_points_spread": "Basis Points Spread",
    "maturity_date": "Maturity Date",
    "currency": "Currency",
    "principal_amount": "Principal Amount",
    "cost": "Cost",
    "fair_value": "Fair Value",
    "first_acquisition_date": "First Acquisition Date",
    "asset_class": "Asset Class",
    "industry": "Industry",
    "profit": "Profit"
}

desired_order = [
    "Portfolio Company",
    "Investment Type",
    "Interest Rate",
    "Reference Rate",
    "Basis Points Spread",
    "Maturity Date",
    "Currency",
    "Principal Amount",
    "Cost",
    "Fair Value",
    "Profit",
    "First Acquisition Date",
    "Asset Class",
    "Industry"
]
df_investment_formatted = df_investment.rename(columns=column_mapping).reindex(columns=desired_order)
df_investment_formatted

# +
# asset-level Analysis
df_asset_level_analysis = (
    df_investment.groupby("asset_class")
      .agg(
          total_investments=("portfolio_company", "count"),

          # counts
          profitable_count=("is_profit", "sum"),
          loss_count=("is_loss", "sum"),
          breakeven_count=("is_breakeven", "sum"),

          # financials
          total_cost=("cost", "sum"),
          total_fair_value=("fair_value", "sum"),
          total_profit=("profit", "sum"),

          # risk
          max_profit=("profit", "max"),
          max_loss=("profit", "min")
      )
)

df_asset_level_analysis.reset_index(names="Industry", inplace=True)

# win, breakeven, and loss rate
df_asset_level_analysis["win_rate"] = round(
    df_asset_level_analysis["profitable_count"] /
    df_asset_level_analysis["total_investments"]
, 2)

df_asset_level_analysis["breakeven_rate"] = round(
    df_asset_level_analysis["breakeven_count"] /
    df_asset_level_analysis["total_investments"]
, 2)

df_asset_level_analysis["loss_rate"] = round(
    df_asset_level_analysis["loss_count"] /
    df_asset_level_analysis["total_investments"]
, 2)

# ✅ FIX 1: Sort df_asset_level_analysis using its own column
df_asset_level_analysis = df_asset_level_analysis.sort_values(
    by="total_fair_value", ascending=False
)

column_mapping = {
    "total_investments": "Total Investment Count",
    "total_cost": "Total Investment Cost",
    "total_fair_value": "Total Investment FV",
    "total_profit": "Total Investment P&L",
    "avg_profit": "Avg Profit/Investment",
    "max_profit": "Max Profit Investment",
    "max_loss": "Max Loss Investment",
    "profitable_count": "Profitable Investment Count",
    "win_rate": "Profitable %",
    "breakeven_count": "Breakeven Investment Count",
    "breakeven_rate": "Breakeven %",
    "loss_count": "Loss Investment Count",
    "loss_rate": "Loss %"
}

desired_order = [
    "Industry",
    "Total Investment Count",
    "Total Investment Cost",
    "Total Investment FV",
    "Total Investment P&L",
    "Avg Profit/Investment",
    "Max Profit Investment",
    "Max Loss Investment",
    "Profitable Investment Count",
    "Profitable %",
    "Breakeven Investment Count",
    "Breakeven %",
    "Loss Investment Count",
    "Loss %"
]

df_asset_level_analysis = df_asset_level_analysis.rename(columns=column_mapping).reindex(columns=desired_order)


# +
industry_list = list(df_asset_level_analysis["Industry"])
# print(industry_list)

arrs = [v.split(" ") for v in industry_list]

perc = [v[-1] for v in arrs]
last = [v.pop() for v in arrs]

names = [" ".join(v) for v in arrs]

df_asset_level_analysis = df_asset_level_analysis.drop(columns=["Industry"])

df_asset_level_analysis.insert(0, "Industry", names)
df_asset_level_analysis.insert(1, "Percentage", perc)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "service_account.json",
    scopes=SCOPES
)

client = gspread.authorize(creds)

df_map = {
    "Summary": df_summary,
    "All Investments": df_investment_formatted,
    "Industry Level Analysis": df_industry_level_analysis,
    "Investment Type Analysis": df_investment_type_level_analysis,
    "Asset Level Analysis": df_asset_level_analysis,
    "Company Level Analysis": df_company_level_analysis
}


spreadsheet = client.open("CELF-NCSR-20260331")

for tab_name, df_analysis in df_map.items():
    try:
        worksheet = spreadsheet.worksheet(tab_name)
        print(tab_name)
        worksheet.clear()
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=tab_name,
            rows=max(len(df_analysis) + 10, 100),
            cols=max(len(df_analysis.columns) + 10, 20)
        )

    # display(df_analysis)
    set_with_dataframe(worksheet, df_analysis)

    # Sheet formatting
    header_fmt = CellFormat(
        backgroundColor=Color(0.85, 0.90, 1.0),
        textFormat=TextFormat(bold=True)
    )

    format_cell_range(
        worksheet,
        "1:1",
        header_fmt
    )

    worksheet.freeze(rows=1)
    worksheet.columns_auto_resize(0, len(df_analysis.columns))




