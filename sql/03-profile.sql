-- DROP TABLE surgeon_profile;
-- DROP TABLE agent_results;
CREATE OR REPLACE TABLE surgeon_profile AS
SELECT s.*, n.address, n.city AS nppes_city, n.zip, n.taxonomy, n.last_updated,
       p.total_paid, p.top_company
FROM surgeons s
LEFT JOIN nppes n USING (npi)
LEFT JOIN (
  SELECT npi, SUM(amount) AS total_paid,
         arg_max(company, amount) AS top_company
  FROM payments GROUP BY npi
) p USING (npi);