"""
Customer Campaign ETL Pipeline
------------------------------
Extract  : read the bank marketing campaign CSV (41,188 customer calls)
Transform: clean it with pandas and run data quality checks
Load     : write the clean table into PostgreSQL, then build KPI views

Run:  python etl.py
"""

import os
import getpass
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# ---------------- settings ----------------
BASE_DIR = Path(__file__).parent
RAW_FILE = BASE_DIR / "data" / "bank-additional-full.csv"
CLEAN_FILE = BASE_DIR / "data" / "campaign_clean.csv"
KPI_SQL = BASE_DIR / "sql" / "kpi_views.sql"
SOURCE_URL = "https://raw.githubusercontent.com/selva86/datasets/master/bank-full.csv"

DB_USER = "postgres"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "campaign_db"
TABLE_NAME = "campaign_contacts"

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


# ---------------- 1. EXTRACT ----------------
def extract():
    """Read the raw CSV. Download it first if it's not in the data folder."""
    if not RAW_FILE.exists():
        print("Raw file not found, downloading...")
        RAW_FILE.parent.mkdir(exist_ok=True)
        pd.read_csv(SOURCE_URL, sep=";").to_csv(RAW_FILE, sep=";", index=False)

    df = pd.read_csv(RAW_FILE, sep=";")   # the file uses ; not ,
    print(f"[Extract] {len(df):,} rows, {len(df.columns)} columns")
    return df


# ---------------- 2. TRANSFORM ----------------
def transform(df):
    """Clean the data so it's ready for SQL and Power BI."""
    rows_in = len(df)

    # a) Column names: 'emp.var.rate' -> 'emp_var_rate', 'y' -> 'subscribed'
    df.columns = [c.strip().replace(".", "_").lower() for c in df.columns]
    df = df.rename(columns={"y": "subscribed", "default": "credit_default"})

    # b) Trim spaces and lowercase all text columns
    text_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in text_cols:
        df[col] = df[col].str.strip().str.lower()

    # c) Remove exact duplicate rows
    df = df.drop_duplicates()
    print(f"[Transform] removed {rows_in - len(df)} duplicate rows")

    # d) Target column: 'yes'/'no' -> 1/0 so we can average it into a rate
    df["subscribed"] = (df["subscribed"] == "yes").astype(int)

    # e) pdays = 999 means "never contacted before" -> make it blank + a flag
    df["contacted_before"] = (df["pdays"] != 999).astype(int)
    df["pdays"] = df["pdays"].where(df["pdays"] != 999)

    # f) Helper columns for the dashboard
    df["age_group"] = pd.cut(df["age"],
                             bins=[0, 24, 34, 44, 54, 64, 200],
                             labels=["18-24", "25-34", "35-44", "45-54", "55-64", "65+"])
    df["age_group"] = df["age_group"].astype(str)
    df["month_num"] = df["month"].map(MONTHS)
    df["call_minutes"] = (df["duration"] / 60).round(2)

    # g) Give every row an ID (the source has none)
    df.insert(0, "contact_id", range(1, len(df) + 1))

    print(f"[Transform] {len(df):,} clean rows ready")
    return df


# ---------------- data quality checks ----------------
def validate(df):
    """Stop the pipeline if the data looks wrong."""
    checks = {
        "table is not empty": len(df) > 0,
        "contact_id is unique": df["contact_id"].is_unique,
        "no blanks in key columns": df[["age", "job", "month", "subscribed"]].notna().all().all(),
        "age between 17 and 100": df["age"].between(17, 100).all(),
        "subscribed is only 0 or 1": df["subscribed"].isin([0, 1]).all(),
        "campaign calls >= 1": (df["campaign"] >= 1).all(),
        "every month mapped": df["month_num"].notna().all(),
    }
    for name, passed in checks.items():
        print(f"   {'PASS' if passed else 'FAIL'}  {name}")
    if not all(checks.values()):
        raise ValueError("Data quality checks failed. Not loading.")

    # Info only: 'unknown' is a real answer in this dataset, so we keep it
    unknowns = (df.select_dtypes(include=["object", "string"]) == "unknown").sum()
    unknowns = unknowns[unknowns > 0]
    print("[Validate] 'unknown' values kept as their own category:")
    for col, n in unknowns.items():
        print(f"   {col}: {n:,}")


# ---------------- 3. LOAD ----------------
def load(df):
    """Write the clean table to PostgreSQL and create the KPI views."""
    password = os.getenv("PG_PASSWORD") or getpass.getpass("PostgreSQL password: ")
    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    with engine.begin() as conn:
        # drop old views first so the table can be replaced
        conn.execute(text("DROP VIEW IF EXISTS v_kpi_summary, v_by_age_group, v_by_job, "
                          "v_by_month, v_by_calls, v_by_previous_outcome, v_by_contact CASCADE"))

    df.to_sql(TABLE_NAME, engine, if_exists="replace", index=False, chunksize=5000)

    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {TABLE_NAME} ADD PRIMARY KEY (contact_id)"))
        conn.execute(text(KPI_SQL.read_text()))

        # check: rows in the database = rows we sent
        db_rows = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar()
    print(f"[Load] {db_rows:,} rows in PostgreSQL table '{TABLE_NAME}'")
    if db_rows != len(df):
        raise ValueError("Row count in database does not match the clean data!")

    return engine


def print_summary(engine):
    summary = pd.read_sql("SELECT * FROM v_kpi_summary", engine)
    print("\n===== KPI SUMMARY =====")
    for col in summary.columns:
        print(f"   {col}: {summary[col][0]}")


if __name__ == "__main__":
    raw = extract()
    clean = transform(raw)
    print("[Validate] running checks")
    validate(clean)
    clean.to_csv(CLEAN_FILE, index=False)
    print(f"[Transform] saved {CLEAN_FILE.name}")
    engine = load(clean)
    print_summary(engine)
    print("\nDone. Open Power BI and connect to the campaign_db database.")
