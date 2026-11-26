# Hand-labeling guide

This guide defines how each surgeon in `data/ground_truth.csv` is labeled. The labels are the ground truth used to score the acquisition agent, so every surgeon is labeled with the same rules, in the same order, without looking at the agent's answer first.

Rules change only between batches, never in the middle of one. Any change is recorded in the [change log](#change-log) at the end of this file.

## Columns

| Column | What to enter |
|---|---|
| `npi`, `first_name`, `last_name`, `city`, `nppes_address`, `nppes_city` | Pre-filled from the data pipeline. Do not edit. |
| `true_status` | `found`, `not_found`, `ambiguous` or `retired_or_moved` (see [Status](#status)) |
| `true_practice_name` | The practice he or she works at today, written the way the practice names itself |
| `true_practice_address` | The street address where the surgeon sees patients, as shown on the source |
| `true_surgery_sites` | Surgery centers or hospitals where a source ties the surgeon to operating, separated by `; ` (leave blank if none can be confirmed) |
| `source_urls` | The page or pages that prove each fact, separated by `; ` |
| `label_confidence` | `sure`, `likely` or `unsure` |
| `minutes_spent` | Whole minutes spent on this surgeon |
| `checked_on` | Date labeled, as `YYYY-MM-DD` |
| `notes` | Anything unusual: name variants, conflicting sources, corrections, or "agent output seen before labeling" |

## Status

| Status | Use when |
|---|---|
| `found` | A current practice is confirmed by an acceptable source. The address or surgery sites may still be blank. |
| `not_found` | No current practice can be confirmed within the time limit. |
| `ambiguous` | Two or more different doctors match the name and the sources can't tell them apart. |
| `retired_or_moved` | A source says the surgeon retired or left Washington, or the Washington license is inactive or expired. |

A practice confirmed without an address is still `found`. Leave `true_practice_address` blank and say why in `notes`.

## Confirming identity

Count a page only if it shows all three:

1. The surgeon's name, allowing for accents, initials, nicknames and suffixes (Rondón = Rondon; "J. Leng" = Jason Leng if the rest matches)
2. Ophthalmology, cataract surgery or eye surgery
3. A Washington location

A page showing the matching NPI settles identity on its own. Record any name variant in `notes`.

## What counts as current

A fact counts only if a source viewable today shows it. Strong signals include "present" in a career timeline, the surgeon appearing on the practice's current doctors page, or a page dated within the last year.

These are leads, not proof:

- Newsletters, news articles and press releases
- Archived or dated pages more than a year old
- Third-party directories with no date

## Sources, in order of trust

Research every surgeon in this order:

1. **The practice's own website**, especially its "Our doctors" or "Providers" page. Best source for practice name and address.
2. **Medicare Care Compare** (medicare.gov/care-compare, "Doctors & clinicians"). Official CMS source for clinic locations and hospital affiliations.
3. **Hospital and surgery center directories.** Search "[name] surgery center" or use local hospitals' find-a-doctor pages to confirm where the surgeon operates.
4. **Washington Department of Health provider credential search.** Confirms the license is active; an inactive or expired license supports `retired_or_moved`.

Third-party listings (Healthgrades, Doximity, Healthline, NPI lookup sites) can point to leads, but every recorded fact must be confirmed by one of the sources above.

## Surgery sites

- List only surgery centers (ASCs) and hospitals, never the surgeon's clinic or office.
- List a site only if a source ties the surgeon to it, such as a surgery center's surgeon list or a hospital's medical staff directory.
- Never assume a surgeon operates at a surgery center because it's nearby or shares the practice's name.
- If the practice runs its own surgery center and a source says the surgeon operates there, list it.

## Practice address

- Record the address as the source shows it; formatting is standardized later by `clean_address`.
- For several clinic locations, record the one the surgeon's own profile lists first, and add the others in `notes`.
- Do not record the NPPES registry address unless a current source confirms it.

## Time limit

Stop at about 10 minutes per surgeon. If a current practice isn't confirmed by then, label `not_found`. An honest "not found" from the agent should score as correct when the information genuinely isn't findable.

## Keeping labels blind

- Do not look at `agent_results`, `agent_review_v1.csv` or `show_findings.py` output for a surgeon until his or her row is complete.
- Label in batches of 10, then compare the whole batch against the agent.
- If comparing reveals a labeling mistake, fix the label and record it in `notes` (for example, "corrected after review: missed second clinic").
- If the agent's answer was seen before labeling, label with the same rules and write "agent output seen before labeling" in `notes`.

## Consistency check

About a week after finishing, re-label 10 randomly chosen surgeons from scratch without looking at the first labels. Record the agreement rate in the write-up. It shows how much of any accuracy difference between agent versions is real rather than labeling noise.

## Privacy

Record professional practice information only. Skip personal addresses, personal phone numbers and anything else that isn't about where the surgeon practices. Don't use sites that require a login.

## Change log

| Date | Change | Applies from batch |
|---|---|---|
| 2026-11-25 | Initial version | 1 |