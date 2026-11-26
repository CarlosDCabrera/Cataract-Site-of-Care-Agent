import hashlib, json, os, re, sys, time, random, duckdb, subprocess, tempfile
from pathlib import Path
from typing import Literal, Optional
from google.genai import errors
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field
from tavily import TavilyClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ---------- Settings ----------
PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")
CLAUDE_CLI_MODEL = os.environ.get("CLAUDE_CLI_MODEL", "claude-haiku-5-5")
if PROVIDER == "claude_cli":
    MODEL = f"claude-code-{CLAUDE_CLI_MODEL}"
else:
    MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
AGENT_VERSION = f"v1-{MODEL}"
MAX_SEARCHES = 3

tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"]) if PROVIDER == "gemini" else None
con = duckdb.connect(str(ROOT / "cataract.duckdb"))
CACHE = ROOT / "cache" / "search"
CACHE.mkdir(parents=True, exist_ok=True)

# ---------- What the agent must return ----------
class Site(BaseModel):
    name: str
    site_type: Literal["practice_or_clinic", "surgery_center", "hospital", "unknown"]
    address: Optional[str]
    city: Optional[str]

class Evidence(BaseModel):
    url: str
    quote: str = Field(description="An exact sentence copied from that page")

class Finding(BaseModel):
    status: Literal["found", "not_found", "ambiguous", "retired_or_moved"]
    practice_name: Optional[str]
    practice_address: Optional[str]
    surgery_sites: list[Site]
    evidence: list[Evidence]
    confidence: Literal["high", "medium", "low"]
    reasoning: str = Field(description="One or two sentences on how you decided")
    next_query: Optional[str] = Field(description="A better search query if more searching would help, else null")

PROMPT = """You are verifying where one specific eye surgeon practices and operates today.

SURGEON
Name: {first_name} {last_name}
NPI: {npi}
Specialty on record: {specialty}
Registry address (may be outdated): {nppes_address}, {nppes_city}, WA

RULES
- Use only the pages below, never outside knowledge.
- Before using a page, confirm it is the same person: the name must match AND the page must show
  ophthalmology or eye surgery AND Washington State. If two different doctors share the name, use "ambiguous".
- Back every fact with an exact sentence copied from the page into "evidence".
- Prefer the surgeon's own practice website or a hospital directory over third-party listing sites.
- Record only professional practice locations. Ignore anything that looks like personal information.
- If a page says the surgeon retired or moved out of state, use "retired_or_moved".
- If you cannot confirm a current practice, use "not_found" and suggest a better next_query.

PAGES
{pages}
"""

# ---------- Model calls ----------
class DailyQuotaExhausted(Exception):
    pass

class UsageLimitReached(DailyQuotaExhausted):   # reuses the same clean-stop handler
    pass

def is_daily_quota(e) -> bool:
    msg = str(e)
    return e.code == 429 and ("PerDay" in msg or "per day" in msg.lower())

def call_gemini(contents: str):
    for attempt in range(5):
        try:
            return gemini.models.generate_content(
                model=MODEL,
                contents=contents,
                config={"response_mime_type": "application/json",
                        "response_schema": Finding, "temperature": 0})
        except errors.APIError as e:
            if is_daily_quota(e):
                raise DailyQuotaExhausted("Daily Gemini quota used up; resets in about 24 hours") from e
            if e.code in (429, 500, 503) and attempt < 4:
                wait = 5 * 2 ** attempt + random.uniform(0, 3)   # ~5s, 10s, 20s, 40s
                print(f"   Gemini busy ({e.code}), retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            raise

SCHEMA = json.dumps(Finding.model_json_schema())
WORKDIR = tempfile.mkdtemp()   # empty folder, so Claude Code can't read or edit your project

def call_claude_cli(prompt: str) -> Finding:
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}  # use Pro login, not API billing
    proc = subprocess.run(
        ["claude", "-p", "Follow the instructions in the input and record your finding.",
         "--output-format", "json",
         "--json-schema", SCHEMA,
         "--model", CLAUDE_CLI_MODEL,
         "--disallowedTools", "Bash,Read,Edit,Write,Glob,Grep,WebSearch,WebFetch"],
        input=prompt, capture_output=True, text=True, env=env, cwd=WORKDIR, timeout=300)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Claude Code failed: {(proc.stderr or proc.stdout)[:300]}")
    if out.get("is_error"):
        msg = str(out.get("result", ""))
        if "limit" in msg.lower():
            raise UsageLimitReached(f"Claude usage limit reached: {msg[:200]}")
        raise RuntimeError(msg[:300])
    if not out.get("structured_output"):
        raise RuntimeError(f"Claude Code returned no structured output: {str(out.get('result', ''))[:300]}")
    return Finding.model_validate(out["structured_output"])

# ---------- Tools ----------
def search(query: str) -> list[dict]:
    """Web search with a disk cache, so reruns are free and results are reproducible."""
    path = CACHE / (hashlib.md5(query.encode()).hexdigest() + ".json")
    if path.exists():
        return json.loads(path.read_text())
    res = tavily.search(query, max_results=5, include_raw_content=True)
    results = [{"url": r["url"], "title": r.get("title", ""),
                "text": (r.get("raw_content") or r.get("content") or "")[:8000]}
               for r in res.get("results", [])]
    path.write_text(json.dumps(results))
    time.sleep(0.5)
    return results

def extract(surgeon: dict, pages: list[dict]) -> Finding:
    page_block = "\n\n".join(
        f"[{i+1}] URL: {p['url']}\nTITLE: {p['title']}\n{p['text'][:6000]}"
        for i, p in enumerate(pages[:8]))
    prompt = PROMPT.format(**surgeon, pages=page_block)
    if PROVIDER == "claude_cli":
        return call_claude_cli(prompt)
    resp = call_gemini(prompt)
    return resp.parsed or Finding.model_validate_json(resp.text)

def norm(s: str) -> str:
    return re.sub(r"\W+", " ", s or "").lower().strip()

def grounding(finding: Finding, pages: list[dict]) -> tuple[int, int]:
    """How many cited quotes really appear on the cited page."""
    texts = {p["url"]: norm(p["text"]) for p in pages}
    supported = sum(1 for e in finding.evidence
                    if norm(e.quote) and norm(e.quote) in texts.get(e.url, ""))
    return supported, len(finding.evidence)

# ---------- The agent loop ----------
def investigate(surgeon: dict):
    queries = [f'"{surgeon["first_name"]} {surgeon["last_name"]}" ophthalmologist {surgeon["city"]} WA']
    pages, seen = [], set()
    while True:
        for p in search(queries[-1]):
            if p["url"] not in seen:
                seen.add(p["url"]); pages.append(p)
        finding = extract(surgeon, pages)
        confident = finding.status in ("found", "retired_or_moved") and finding.confidence != "low"
        if confident or len(queries) >= MAX_SEARCHES:
            break
        if not finding.next_query or finding.next_query in queries:
            break
        queries.append(finding.next_query)
    supported, total = grounding(finding, pages)
    if finding.status == "found" and supported == 0:
        finding.confidence = "low"            # claims it can't back up get downgraded
    return finding, queries, supported, total

# ---------- Run over the surgeon list ----------
def main(limit: int):
    print(f"Provider: {PROVIDER} | Model: {MODEL} | Saving as: {AGENT_VERSION}")
    con.execute("""CREATE TABLE IF NOT EXISTS agent_results (
        npi VARCHAR, agent_version VARCHAR, status VARCHAR, confidence VARCHAR,
        practice_name VARCHAR, practice_address VARCHAR, n_sites INTEGER,
        evidence_supported INTEGER, evidence_total INTEGER, n_searches INTEGER,
        queries VARCHAR, finding_json VARCHAR, run_at TIMESTAMP DEFAULT current_timestamp)""")
    surgeons = con.execute("""
        SELECT s.npi, s.first_name, s.last_name, s.city, s.specialty,
               n.address AS nppes_address, n.city AS nppes_city
        FROM surgeons s LEFT JOIN nppes n USING (npi)
        WHERE s.npi NOT IN (SELECT npi FROM agent_results WHERE agent_version = ?)
        ORDER BY s.cataract_procedures DESC
        LIMIT ?""", [AGENT_VERSION, limit]).df().to_dict("records")

    consecutive_errors = 0
    try:
        for i, s in enumerate(surgeons, 1):
            pauses = 0
            while True:
                try:
                    f, queries, supported, total = investigate(s)
                    break
                except DailyQuotaExhausted as e:
                    done = con.execute("SELECT COUNT(*) FROM agent_results WHERE agent_version = ?",
                                       [AGENT_VERSION]).fetchone()[0]
                    print(f"\n{e}. {done} surgeons saved for {AGENT_VERSION}. Rerun later to continue.")
                    return
                except errors.APIError as e:
                    if e.code in (429, 500, 503) and pauses < 3:
                        pauses += 1
                        print(f"   Model overloaded; pausing 3 min, then retrying {s['last_name']} ({pauses}/3)")
                        time.sleep(180)
                        continue
                    f = None
                    err = e
                    break
                except Exception as e:
                    f = None
                    err = e
                    break
            if f is None:
                consecutive_errors += 1
                print(f"[{i}/{len(surgeons)}] {s['first_name']} {s['last_name']}: error {err}")
                if consecutive_errors >= 3:
                    print("Stopping: 3 errors in a row. Fix the issue above, then rerun.")
                    break
                continue
            consecutive_errors = 0
            con.execute("INSERT INTO agent_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?, current_timestamp)", [
                s["npi"], AGENT_VERSION, f.status, f.confidence, f.practice_name, f.practice_address,
                len(f.surgery_sites), supported, total, len(queries), json.dumps(queries), f.model_dump_json()])
            print(f"[{i}/{len(surgeons)}] {s['first_name']} {s['last_name']}: {f.status} "
                  f"({f.confidence}), {supported}/{total} quotes verified, {len(queries)} searches")
    except KeyboardInterrupt:
        done = con.execute("SELECT COUNT(*) FROM agent_results WHERE agent_version = ?",
                           [AGENT_VERSION]).fetchone()[0]
        print(f"\nStopped. {done} surgeons saved for {AGENT_VERSION}. Rerun to continue.")

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)