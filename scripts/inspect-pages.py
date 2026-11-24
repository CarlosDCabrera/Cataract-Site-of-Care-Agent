# scripts/inspect_pages.py
import json, hashlib, sys, duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
npi, keyword = sys.argv[1], sys.argv[2].lower()
con = duckdb.connect(str(ROOT / "cataract.duckdb"), read_only=True)
queries = json.loads(con.execute(
    "SELECT queries FROM agent_results WHERE npi = ? ORDER BY run_at DESC LIMIT 1", [npi]).fetchone()[0])

seen = set()
for q in queries:
    f = ROOT / "cache" / "search" / (hashlib.md5(q.encode()).hexdigest() + ".json")
    for r in (json.loads(f.read_text()) if f.exists() else []):
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        pos = r["text"].lower().find(keyword)
        print(f"{'FOUND' if pos >= 0 else '-----'}  pos {pos:>5}  len {len(r['text']):>5}  {r['url']}")