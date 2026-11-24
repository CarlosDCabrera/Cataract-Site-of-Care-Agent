import duckdb, requests, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # .../Cataract-Site-of-Care-Agent
con = duckdb.connect(str(ROOT / "cataract.duckdb"))

con = duckdb.connect("cataract.duckdb")
rows = []
for (npi,) in con.execute("SELECT npi FROM surgeons").fetchall():
    r = requests.get("https://npiregistry.cms.hhs.gov/api/",
                     params={"version": "2.1", "number": npi}, timeout=30).json()
    if not r.get("results"):
        continue
    res = r["results"][0]
    loc = next((a for a in res["addresses"] if a["address_purpose"] == "LOCATION"), {})
    tax = next((t for t in res["taxonomies"] if t.get("primary")), {})
    rows.append((npi, loc.get("address_1"), loc.get("city"), loc.get("postal_code", "")[:5],
                 loc.get("telephone_number"), tax.get("desc"),
                 res["basic"].get("last_updated")))
    time.sleep(0.2)  # be polite to the API

con.execute("""CREATE OR REPLACE TABLE nppes (npi VARCHAR, address VARCHAR, city VARCHAR,
               zip VARCHAR, phone VARCHAR, taxonomy VARCHAR, last_updated VARCHAR)""")
con.executemany("INSERT INTO nppes VALUES (?, ?, ?, ?, ?, ?, ?)", rows)