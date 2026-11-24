-- DROP TABLE payments;

CREATE OR REPLACE TABLE payments AS
SELECT
  CAST(Covered_Recipient_NPI AS VARCHAR)                       AS npi,
  Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_Name AS company,
  Nature_of_Payment_or_Transfer_of_Value                       AS payment_type,
  Name_of_Drug_or_Biological_or_Device_or_Medical_Supply_1     AS product,
  Total_Amount_of_Payment_USDollars                            AS amount,
  Date_of_Payment
FROM read_csv_auto('raw/OP_DTL_GNRL_PGYR2024_P06302026_06032026.csv')
WHERE CAST(Covered_Recipient_NPI AS VARCHAR) IN (SELECT npi FROM surgeons);