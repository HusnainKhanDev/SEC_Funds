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

# +
import pandas as pd
from pathlib import Path

import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from gspread_formatting import *

# +
DIR_PATH = Path("Cascade_Private_Capital_Fund/2026-03-31/")
CONSOLIDATED_CSV_PATH = Path(DIR_PATH, "outputs/consolidated_schedule_master_deduped.csv")
ANALYSIS_PATH = Path(DIR_PATH, "analysis")
ANALYSIS_PATH.mkdir(exist_ok=True)

DIR_PATH.exists(), CONSOLIDATED_CSV_PATH.exists(), ANALYSIS_PATH.exists()
# -

df_investment = pd.read_csv(CONSOLIDATED_CSV_PATH)
df_investment.info()

df_investment[df_investment["portfolio_company"].str.contains("Platte River", na=False)]

df_investment[df_investment["industry"].str.contains("Credit Co-Investments — 3.2%", na=False)]

df_investment.head(275)

# +
# df_investment = df_investment[df_investment["fair_value"].notna()] # drop the rows with fv as na 

# convert cost 
for col in ["cost", "fair_value"]:
    df_investment[col] = (
        df_investment[col]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
        .replace("nan", pd.NA)
    )

    df_investment[col] = pd.to_numeric(df_investment[col], errors="coerce").astype("Int64")

df_investment.drop(columns=["part", "table_index", "row_index"], inplace=True)
df_investment
# -

df_investment["industry"].str.contains("Secondary Fund Investments — 40.4%", case=False, na=False).any()

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
        # remove total investment from here
        "Total Cost", 
        "Total FV", 
        "P&L"
    ],
    "b": [
        len(df_investment),
        int(df_investment["cost"].sum()),
        int(df_investment["fair_value"].sum()),
        int(df_investment["fair_value"].sum())-int(df_investment["cost"].sum()),
    ]
})

df_summary

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

display(df_company_level_analysis)
# platform_enhanced.to_csv(Path(ANALYSIS_PATH, "platform_level_analysis.csv"))

# +
# Industry-Level Analysis
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

display(df_industry_level_analysis)
# platform_enhanced.to_csv(Path(ANALYSIS_PATH, "platform_level_analysis.csv"))

# +
industry_list = list(df_industry_level_analysis["Industry"])
name = [v.split("—")[0].strip() for v in industry_list]
perc = [v.split("—")[1] for v in industry_list]

df_industry_level_analysis = df_industry_level_analysis.drop(columns=["Industry"])
df_industry_level_analysis.insert(0, "Industry", name)
df_industry_level_analysis.insert(1, "percentage", perc)

# display(name, perc)
df_industry_level_analysis

# +
# # Investment Type Level Analysis
# df_investment_type_level_analysis = (
#     df_investment.groupby("investment_type")
#       .agg(
#           total_investments=("portfolio_company", "count"),

#           # counts
#           profitable_count=("is_profit", "sum"),
#           loss_count=("is_loss", "sum"),
#           breakeven_count=("is_breakeven", "sum"),

#           # financials
#           total_cost=("cost", "sum"),
#           total_fair_value=("fair_value", "sum"),
#           total_profit=("profit", "sum"),

#           # averages
#           avg_profit=("profit", "mean"),

#           # risk
#           max_profit=("profit", "max"),
#           max_loss=("profit", "min")
#       )
# )

# df_investment_type_level_analysis.reset_index(names="Investment Type", inplace=True)
# df_investment_type_level_analysis["avg_profit"] = round(df_investment_type_level_analysis["avg_profit"], 2)

# # win, breakeven, and loss rate
# df_investment_type_level_analysis["win_rate"] = round(
#     df_investment_type_level_analysis["profitable_count"] /
#     df_investment_type_level_analysis["total_investments"]
# , 2)

# df_investment_type_level_analysis["breakeven_rate"] = round(
#     df_investment_type_level_analysis["breakeven_count"] /
#     df_investment_type_level_analysis["total_investments"]
# , 2)

# df_investment_type_level_analysis["loss_rate"] = round(
#     df_investment_type_level_analysis["loss_count"] /
#     df_investment_type_level_analysis["total_investments"]
# , 2)

# # sort by total no investments
# df_investment_type_level_analysis = df_investment_type_level_analysis.sort_values(
#     by="total_fair_value", ascending=False
# )


# column_mapping = {
#     "total_investments": "Total Investment Count",
#     "total_cost": "Total Investment Cost",
#     "total_fair_value": "Total Investment FV",
#     "total_profit": "Total Investment P&L",
#     "avg_profit": "Avg Profit/Investment",
#     "max_profit": "Max Profit Investment",
#     "max_loss": "Max Loss Investment",
#     "profitable_count": "Profitable Investment Count",
#     "win_rate": "Profitable %",
#     "breakeven_count": "Breakeven Investment Count",
#     "breakeven_rate": "Breakeven %",
#     "loss_count": "Loss Investment Count",
#     "loss_rate": "Loss %"
# }
# desired_order = [
#     "Investment Type",
#     "Total Investment Count",
#     "Total Investment Cost",
#     "Total Investment FV",
#     "Total Investment P&L",
#     "Avg Profit/Investment",
#     "Max Profit Investment",
#     "Max Loss Investment",
#     "Profitable Investment Count",
#     "Profitable %",
#     "Breakeven Investment Count",
#     "Breakeven %",
#     "Loss Investment Count",
#     "Loss %"
# ]

# df_investment_type_level_analysis = df_investment_type_level_analysis.rename(columns=column_mapping).reindex(columns=desired_order)

# display(df_investment_type_level_analysis)
# # platform_enhanced.to_csv(Path(ANALYSIS_PATH, "platform_level_analysis.csv"))

# +
# Fromatting df_investments
column_mapping = {
    # removed some unnecessary columns which is not present in actual filing 
        # investment_type": "Investment Type",
        # "interest_rate": "Interest Rate",
        # "reference_rate": "Reference Rate",
        # "basis_points_spread": "Basis Points Spread",
        # "maturity_date": "Maturity Date",
        # "currency": "Currency",
        # "principal_amount": "Principal Amount",
    
   
    "portfolio_company": "Portfolio Company",
    "initial_acquisition_date": "Initial Acquisition Date",
    "geographic_region": "Geographic Region",
    "shares_units": "Shares Units",
    "cost": "Cost",
    "fair_value": "Fair Value",
    "first_acquisition_date": "First Acquisition Date",
    "asset_class": "Asset Class",
    "industry": "Industry",
    "principal_amount": "Principal Amount",
    "profit": "Profit"
}

desired_order = [
    "Portfolio Company",
    "Initial Acquisition Date",
    "Geographic Region",
    "Principal Amount",
    "Shares Units",
    "Cost",
    "Fair Value",
    "Profit",
    "First Acquisition Date",
    "Asset Class",
    "Industry"
]
df_investment_formatted = df_investment.rename(columns=column_mapping).reindex(columns=desired_order)
df_investment_formatted
# -

# ### Dumping to GS

# +
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "service_account.json",
    scopes=SCOPES
)

client = gspread.authorize(creds)
# -

df_map = {
    "Summary": df_summary,
    "All Investments": df_investment_formatted,
    "Sector Level Analysis": df_industry_level_analysis,
    # "Investment Type Analysis": df_investment_type_level_analysis,
    "Company Level Analysis": df_company_level_analysis
}

spreadsheet = client.open("CPCF-NCSR-20260331")

for tab_name, df_analysis in df_map.items():
    try:
        worksheet = spreadsheet.worksheet(tab_name)
        worksheet.clear()
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=tab_name,
            rows=max(len(df_analysis) + 10, 100),
            cols=max(len(df_analysis.columns) + 10, 20)
        )

    display(df_analysis)
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






