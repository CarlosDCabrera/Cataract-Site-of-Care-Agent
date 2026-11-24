-- in DuckDB
-- DROP TABLE medicare_raw;
-- DROP TABLE surgeons;
-- DROP TABLE nppes;
CREATE OR REPLACE TABLE medicare_raw AS
SELECT
  CAST(Rndrng_NPI AS VARCHAR)  AS npi,
  Rndrng_Prvdr_Last_Org_Name   AS last_name,
  Rndrng_Prvdr_First_Name      AS first_name,
  Rndrng_Prvdr_City            AS city,
  Rndrng_Prvdr_Type            AS specialty,
  HCPCS_Cd                     AS cpt,
  Place_Of_Srvc                AS place_of_service,
  Tot_Benes, Tot_Srvcs
FROM read_csv_auto('raw/Medicare_Physician_Other_Practitioners_by_Provider_and_Service_2024.csv')
WHERE Rndrng_Prvdr_State_Abrvtn = 'WA' -- only state of washingon surgons
  AND HCPCS_Cd IN ('66984', '66982') -- cataract surgery codes
  AND Rndrng_Prvdr_Ent_Cd = 'I'
  AND Rndrng_Prvdr_Type = 'Ophthalmology';

-- one row per surgeon: a surgeon can have separate rows per code and place of service
CREATE OR REPLACE TABLE surgeons AS
SELECT npi, last_name, first_name, city, specialty,
       SUM(Tot_Srvcs) AS cataract_procedures,
       SUM(CASE WHEN cpt = '66982' THEN Tot_Srvcs ELSE 0 END) AS complex_cases
FROM medicare_raw
GROUP BY ALL
ORDER BY cataract_procedures DESC;