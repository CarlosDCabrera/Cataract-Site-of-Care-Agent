# scripts/make_label_sheet.py
import sys, duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out = ROOT / "data" / "ground-truth.csv"
version = sys.argv[1] if len(sys.argv) > 1 else "v1-gemini-3.5-flash"
if out.exists():
    sys.exit(f"{out} already exists; not overwriting your labels.")

con = duckdb.connect(str(ROOT / "cataract.duckdb"), read_only=True)
con.execute("""
COPY (
  SELECT s.npi, s.first_name, s.last_name, s.city,
         n.address AS nppes_address, n.city AS nppes_city,
         '' AS true_status, '' AS true_practice_name, '' AS true_practice_address,
         '' AS true_surgery_sites, '' AS source_urls, '' AS label_confidence,
         '' AS minutes_spent, '' AS checked_on, '' AS notes
  FROM surgeons s
  JOIN (SELECT DISTINCT npi FROM agent_results WHERE agent_version = ?) a USING (npi)
  LEFT JOIN nppes n USING (npi)
  ORDER BY s.npi              -- a neutral order, not the agent's order
) TO ? (HEADER)""", [version, str(out)])
print(f"Wrote {out}")