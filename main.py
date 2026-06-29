"""Fetch geotarget alert data from Snowflake (Google / Meta / MS) and push to Google Sheets.

Sheet: https://docs.google.com/spreadsheets/d/1JgwUNRFXLcF0UNpVJLsbzbq0xLDarxjhKVqA0DLxbZc
Tab:   OUT-PUT

Run:
    python main.py

Prereqs:
    - .env with Snowflake conn params (already present)
    - rsa_key.p8 private key (already present)
    - client_secrets.json (Google OAuth desktop client) in project root
      token.pickle will be created on first run after browser consent.
"""
from __future__ import annotations

import pickle
from datetime import datetime
from pathlib import Path

import pandas as pd
import snowflake.connector as sc
from decouple import config
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
QUERY_DIR = ROOT / "query"
PRIVATE_KEY_FILE = ROOT / "rsa_key.p8"

SPREADSHEET_ID = "1JgwUNRFXLcF0UNpVJLsbzbq0xLDarxjhKVqA0DLxbZc"
SHEET_NAME = "OUT-PUT"
STATUS_SHEET = "alert_setting"
STATUS_CELL = "E2"
STATUS_VALUE = "ON"

CLIENT_SECRETS_FILE = ROOT / "client_secrets.json"
TOKEN_FILE = ROOT / "token.pickle"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

OUT_COL = [
    "CUSTOMER_ID",
    "CUSTOMER_DESCRIPTIVE_NAME",
    "CAMPAIGN_ID",
    "CAMPAIGN_NAME",
    "CAMPAIGN_STATUS",
    "ADG_ID",
    "ADG_NAME",
    "ADG_STATUS",
    "MEDIA",
    "DATE",
    "COUNTRY_CODE",
    "REGION_NAME",
    "CANONICAL_NAME",
    "TARGET_TYPE"
]


# ---------------------------------------------------------------------------
# Snowflake
# ---------------------------------------------------------------------------
def snowflake_connect():
    conn_params = {
        "account": config("ACCOUNT"),
        "user": config("USER"),
        "authenticator": config("AUTHENTICATOR"),
        "private_key_file": str(PRIVATE_KEY_FILE),
        "role": config("ROLE"),
        "warehouse": config("WAREHOUSE"),
        "database": config("DATABASE"),
        "schema": config("SCHEMA"),
    }
    return sc.connect(**conn_params)


def run_query(ctx, sql_file: Path) -> pd.DataFrame:
    sql = sql_file.read_text(encoding="utf-8")
    cur = ctx.cursor()
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        cur.close()
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Mapping helpers — produce a DataFrame whose columns match OUT_COL exactly
# ---------------------------------------------------------------------------
def _empty_frame(n_rows: int) -> pd.DataFrame:
    return pd.DataFrame({c: [""] * n_rows for c in OUT_COL})


def map_google(df: pd.DataFrame, run_date: str) -> pd.DataFrame:
    out = _empty_frame(len(df))
    out["CUSTOMER_ID"] = df["CUSTOMER_ID"].astype(str)
    out["CUSTOMER_DESCRIPTIVE_NAME"] = df["CUSTOMER_NAME"].fillna("")
    out["CAMPAIGN_ID"] = df["CAMPAIGN_ID"].astype(str)
    out["CAMPAIGN_NAME"] = df["CAMPAIGN_NAME"].fillna("")
    out["CAMPAIGN_STATUS"] = df["STATUS"].fillna("")
    out["MEDIA"] = df["MEDIA"].fillna("")
    out["COUNTRY_CODE"] = df["COUNTRY_CODE"].fillna("")
    out["DATE"] = run_date
    return out


def map_meta(df: pd.DataFrame, run_date: str) -> pd.DataFrame:
    out = _empty_frame(len(df))
    out["CUSTOMER_ID"] = df["ACCOUNT_ID"].astype(str)
    out["CUSTOMER_DESCRIPTIVE_NAME"] = df["ACCOUNT_NAME"].fillna("")
    out["CAMPAIGN_ID"] = df["CAMPAIGN_ID"].astype(str)
    out["CAMPAIGN_NAME"] = df["CAMPAIGN_NAME"].fillna("")
    out["ADG_ID"] = df["AD_SET_ID"].astype(str)
    out["ADG_NAME"] = df["AD_SET_NAME"].fillna("")
    out["ADG_STATUS"] = df["EFFECTIVE_STATUS"].fillna("")
    out["MEDIA"] = "Meta"
    out["DATE"] = run_date
    out["REGION_NAME"] = df["GLOBAL_REGIONS"].astype(str).fillna("")
    out["TARGET_TYPE"] = df["LOCATION_TYPES"].astype(str).fillna("")
    return out


def map_ms(df: pd.DataFrame, run_date: str) -> pd.DataFrame:
    out = _empty_frame(len(df))
    out["CUSTOMER_ID"] = df["ACCOUNT_NUMBER"].astype(str)
    out["CUSTOMER_DESCRIPTIVE_NAME"] = df["ACCOUNT_NAME"].fillna("")
    out["CAMPAIGN_ID"] = df["CAMPAIGN_ID"].astype(str)
    out["CAMPAIGN_NAME"] = df["CAMPAIGN_NAME"].fillna("")
    out["CAMPAIGN_STATUS"] = df["STATUS"].fillna("")
    out["MEDIA"] = "MS_" + df["MEDIA"].fillna("").astype(str)
    out["DATE"] = run_date
    out["CANONICAL_NAME"] = df["COUNTRY_TARGET"].fillna("")
    return out


# ---------------------------------------------------------------------------
# Google Sheets (OAuth Installed App flow)
# ---------------------------------------------------------------------------
def get_sheets_service():
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRETS_FILE.exists():
                raise FileNotFoundError(
                    f"Missing {CLIENT_SECRETS_FILE.name}. Tải OAuth desktop client từ "
                    "Google Cloud Console rồi đặt vào project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


CHUNK_ROWS = 20000


def _get_sheet_id(service, sheet_name: str) -> int:
    meta = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID,
        fields="sheets(properties(sheetId,title,gridProperties))",
    ).execute()
    for s in meta["sheets"]:
        if s["properties"]["title"] == sheet_name:
            return s["properties"]["sheetId"]
    raise ValueError(f"Sheet '{sheet_name}' not found in spreadsheet")


def _resize_grid(service, sheet_id: int, row_count: int, col_count: int) -> None:
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {
                                "rowCount": row_count,
                                "columnCount": col_count,
                            },
                        },
                        "fields": "gridProperties(rowCount,columnCount)",
                    }
                }
            ]
        },
    ).execute()


def overwrite_sheet(service, df: pd.DataFrame) -> None:
    sheets = service.spreadsheets()
    rng = f"'{SHEET_NAME}'!A:N"

    needed_rows = len(df) + 1
    sheet_id = _get_sheet_id(service, SHEET_NAME)
    _resize_grid(service, sheet_id, row_count=needed_rows, col_count=max(len(OUT_COL), 26))
    print(f"[sheets] grid resized to {needed_rows} rows")

    sheets.values().clear(spreadsheetId=SPREADSHEET_ID, range=rng, body={}).execute()

    sheets.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!A1",
        valueInputOption="RAW",
        body={"values": [OUT_COL]},
    ).execute()

    data = df.astype(str).where(df.notna(), "").values.tolist()
    total = len(data)
    written = 0
    for start in range(0, total, CHUNK_ROWS):
        chunk = data[start : start + CHUNK_ROWS]
        row_start = start + 2
        row_end = row_start + len(chunk) - 1
        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{SHEET_NAME}'!A{row_start}:N{row_end}",
            valueInputOption="RAW",
            body={"values": chunk},
        ).execute()
        written += len(chunk)
        print(f"[sheets] {written}/{total} rows written")
    print(f"[sheets] done -> '{SHEET_NAME}' ({total} rows)")


def set_status_on(service) -> None:
    rng = f"'{STATUS_SHEET}'!{STATUS_CELL}"
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=rng,
        valueInputOption="RAW",
        body={"values": [[STATUS_VALUE]]},
    ).execute()
    print(f"[sheets] status set -> {rng} = {STATUS_VALUE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    run_date = datetime.now().strftime("%Y-%m-%d")

    print("[snowflake] connecting...")
    ctx = snowflake_connect()
    try:
        print("[snowflake] running google query...")
        g_df = run_query(ctx, QUERY_DIR / "google.txt")
        print(f"           -> {len(g_df)} rows")

        print("[snowflake] running meta query...")
        m_df = run_query(ctx, QUERY_DIR / "meta.txt")
        print(f"           -> {len(m_df)} rows")

        print("[snowflake] running ms query...")
        s_df = run_query(ctx, QUERY_DIR / "ms.txt")
        print(f"           -> {len(s_df)} rows")
    finally:
        ctx.close()

    combined = pd.concat(
        [
            map_google(g_df, run_date),
            map_meta(m_df, run_date),
            map_ms(s_df, run_date),
        ],
        ignore_index=True,
    )[OUT_COL]
    print(f"[merge] total rows = {len(combined)}")

    print("[sheets] authenticating...")

    service = get_sheets_service()
    overwrite_sheet(service, combined)
    set_status_on(service)
    print("[done]")


if __name__ == "__main__":
    main()
