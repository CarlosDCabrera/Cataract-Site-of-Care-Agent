# scripts/show_finding.py
import sys, json, duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
npi = sys.argv[1]
version = sys.argv[2] if len(sys.argv) > 2 else "v1-claude-code-claude-haiku-5-5"

con = duckdb.connect(str(ROOT / "cataract.duckdb"), read_only=True)
row = con.execute("""SELECT finding_json, queries FROM agent_results
                     WHERE npi = ? AND agent_version = ?""", [npi, version]).fetchone()
if not row:
    sys.exit(f"No result for NPI {npi} in {version}")
finding = json.loads(row[0])
print("Searches:", json.loads(row[1]))
print(json.dumps(finding, indent=2, ensure_ascii=False))