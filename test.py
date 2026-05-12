import os
import pandas as pd
import snowflake.connector as sc
from decouple import config

private_key_file = 'rsa_key.p8'

conn_params = {
    'account': config('ACCOUNT'),
    'user': config('USER'),
    'authenticator': config('AUTHENTICATOR'),
    'private_key_file': private_key_file,
    'role': config('ROLE'),
    'warehouse': config('WAREHOUSE'),
    'database': config('DATABASE'),
    'schema': config('SCHEMA')
}

ctx = sc.connect(**conn_params)
cs = ctx.cursor()

test = cs.execute(
    """
      SELECT
        c.CUSTOMER_ID,
        cust.DESCRIPTIVE_NAME AS CUSTOMER_NAME,
        c.ID AS CAMPAIGN_ID,
        c.NAME AS CAMPAIGN_NAME,
        c.STATUS,
        CASE
            WHEN c.ADVERTISING_CHANNEL_TYPE = 'MULTI_CHANNEL' THEN 'GAC'
            WHEN c.ADVERTISING_CHANNEL_TYPE = 'DISPLAY' THEN 'Google_GDN'
            WHEN c.ADVERTISING_CHANNEL_TYPE = 'VIDEO' THEN 'YouTube'
            WHEN c.ADVERTISING_CHANNEL_TYPE = 'LOCAL' THEN 'O2O'
            ELSE c.ADVERTISING_CHANNEL_TYPE
        END AS MEDIA,
        geo.COUNTRY_CODE
    FROM DM_GEOTARGET_ALERT_PRD.DATAMART_SCHEMA.GOOGLE_CAMPAIGN c
    LEFT JOIN DM_GEOTARGET_ALERT_PRD.DATAMART_SCHEMA.GOOGLE_CUSTOMER cust
        ON c.CUSTOMER_ID = cust.ID
    LEFT JOIN DM_GEOTARGET_ALERT_PRD.DATAMART_SCHEMA.GOOGLE_CAMPAIGN_CRITERION cc
        ON cc.CAMPAIGN_ID = c.ID AND cc.TYPE = 'LOCATION' AND cc.NEGATIVE = FALSE
    LEFT JOIN DM_GEOTARGET_ALERT_PRD.DATAMART_SCHEMA.GOOGLE_GEO_TARGET_CONSTANT geo
        ON cc.LOCATION_GEO_TARGET_CONSTANT = geo.RESOURCE_NAME
    WHERE c.ADVERTISING_CHANNEL_TYPE IN ('MULTI_CHANNEL', 'DISPLAY', 'VIDEO', 'LOCAL')
        AND geo.COUNTRY_CODE IS NULL
    ORDER BY MEDIA, c.NAME;
    """
)

df = test.fetchall()
df = pd.DataFrame(df, columns=['DATE', 'CUSTOMER_ID', 'CAMPAIGN_ID', 'CAMPAIGN_NAME'])
print(df)