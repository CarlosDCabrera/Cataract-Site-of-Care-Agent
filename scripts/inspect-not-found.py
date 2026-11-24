import json, hashlib, duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = duckdb.connect(str(ROOT / "cataract.duckdb"), read_only=True)
rows = con.execute("""SELECT npi, queries, json_extract_string(finding_json, '$.reasoning')
                      FROM agent_results WHERE status = 'not_found'""").fetchall()
for npi, queries, reasoning in rows:
    print(f"\nNPI {npi}\nModel's reasoning: {reasoning}")
    for q in json.loads(queries):
        print(f"  QUERY: {q}")
        f = ROOT / "cache" / "search" / (hashlib.md5(q.encode()).hexdigest() + ".json")
        for r in (json.loads(f.read_text()) if f.exists() else []):
            print(f"     {r['url']}")