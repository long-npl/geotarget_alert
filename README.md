# Geotarget Alert

Detects ad campaigns across **Google**, **Meta**, and **Microsoft Ads** that have no geo-targeting configured, then pushes the result list to a Google Sheets spreadsheet for alerting.

## How it works

1. Connects to Snowflake using JWT (RSA key-pair) authentication
2. Runs one SQL query per platform to find campaigns missing geo-targeting:
   - **Google** — GAC / GDN / YouTube / O2O campaigns with no country, province, or proximity target
   - **Meta** — Ad sets whose geo targeting includes "worldwide" regions
   - **Microsoft (Bing)** — Campaigns with no country-level location criterion
3. Merges results into a unified schema and writes them to the `OUT-PUT` tab of a shared Google Sheet
4. Sets a status cell in the `alert_setting` tab to `ON`

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | Tested on 3.12 |
| Snowflake account | Role, warehouse, database, and schema must be provided |
| RSA key pair | `rsa_key.p8` (private key) placed in the project root; public key registered in Snowflake |
| Google OAuth desktop client | `client_secrets.json` from Google Cloud Console, placed in project root |

## Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/long-npl/geotarget_alert.git
cd geotarget_alert
python -m venv venv
```

Activate:
- Windows: `venv\Scripts\activate.bat`
- Unix: `source venv/bin/activate`

### 2. Install dependencies

```bash
pip install snowflake-connector-python[pandas] pandas google-auth google-auth-oauthlib google-api-python-client python-decouple cryptography
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```ini
ACCOUNT=your_account_identifier
USER=your_snowflake_username
AUTHENTICATOR=snowflake_jwt
ROLE=your_role
WAREHOUSE=your_warehouse
DATABASE=DM_GEOTARGET_ALERT_PRD
SCHEMA=DATAMART_SCHEMA
```

### 4. Add RSA private key

Place your `rsa_key.p8` file in the project root. To get the public key fingerprint needed for Snowflake:

```bash
python fingerprint.py rsa_key.p8
# SHA256:xxxx...  <- register this in Snowflake
```

### 5. Add Google OAuth credentials

Download an **OAuth 2.0 Desktop** client JSON from Google Cloud Console and save it as `client_secrets.json` in the project root. On first run, a browser window will open for consent; the token is cached in `token.pickle` afterwards.

## Running

```bash
python main.py
```

Or on Windows double-click `__run.bat`.

Output:
```
[snowflake] connecting...
[snowflake] running google query...  -> N rows
[snowflake] running meta query...    -> N rows
[snowflake] running ms query...      -> N rows
[merge] total rows = N
[sheets] authenticating...
[sheets] grid resized to N rows
[sheets] N/N rows written
[sheets] done -> 'OUT-PUT' (N rows)
[sheets] status set -> 'alert_setting'!E2 = ON
[done]
```

## Project structure

```
geotarget_alert/
├── main.py              # Entry point — Snowflake → Google Sheets
├── fingerprint.py       # Utility: compute RSA public key fingerprint
├── test.py              # Quick Snowflake connection smoke test
├── __run.bat            # Windows batch launcher
├── lib/
│   └── get_driver.py    # Selenium WebDriver helper
├── query/
│   ├── google.txt       # SQL — Google Ads campaigns without geo-targeting
│   ├── meta.txt         # SQL — Meta ad sets with worldwide-only targeting
│   └── ms.txt           # SQL — Microsoft/Bing campaigns without geo-targeting
├── .env                 # Snowflake credentials (not committed)
└── rsa_key.p8           # RSA private key (not committed)
```

## Output schema

| Column | Description |
|---|---|
| CUSTOMER_ID | Platform account / customer ID |
| CUSTOMER_DESCRIPTIVE_NAME | Account name |
| CAMPAIGN_ID | Campaign ID |
| CAMPAIGN_NAME | Campaign name |
| CAMPAIGN_STATUS | Campaign status |
| ADG_ID | Ad set / ad group ID (Meta only) |
| ADG_NAME | Ad set / ad group name (Meta only) |
| ADG_STATUS | Effective status (Meta only) |
| MEDIA | Platform label (GAC / Google_GDN / YouTube / O2O / Meta / MS_*) |
| DATE | Run date (YYYY-MM-DD) |
| COUNTRY_CODE | Country code where available |
| REGION_NAME | Global region groups (Meta only) |
| CANONICAL_NAME | Country target name (Microsoft only) |
| TARGET_TYPE | Location types (Meta only) |
