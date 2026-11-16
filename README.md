# Jobscraper (Mallika Mujgule, product and UX design)

Daily job pipeline that fetches fresh postings (< 24 hours old) from 8 sources
(LinkedIn, Indeed, Arbeitnow, Xing, Stepstone, Wellfound, EU Remote Jobs, ATS Direct),
keeps product/UX design roles in Germany or explicitly EU-remote, and verifies each
posting with **Haiku 5.5** subagents. **macOS and the Claude Desktop app only**:
`config.py` exits on any other platform, and there is no OMP or API-key path.

## Target profiles

Derived from the mallika-cv folder (CV, project catalog, tracker):

1. Product Designer / UX/UI Designer
2. AI-enabled Product Designer / Product Design Engineer
3. Werkstudent / intern UX (M.A. until Feb 2027)

Name, search roles, German level (A2), experience ceiling (4 years) and skill
keywords live in [`candidate.json`](candidate.json). The name is read from
`~/.claude/skills/mallika-cv/okf/profile.yaml` when present.

## Quick start

```bash
cd ~/Documents/Simple-Job-Scraper
python3 -m venv .venv && source .venv/bin/activate   # needs Python 3.10+
pip install -r requirements.txt
python3 apify_job_search.py        # 1. scrape
python3 verify_jobs.py prepare     # 2. platform checks + Haiku batch files
# 3. in Claude Desktop: spawn Haiku 5.5 subagents on Job Search/<date>/_haiku/*.input.json
python3 verify_jobs.py finalize    # 4. route rows, write the verified XLSX
```

In Claude Desktop, ask "run job search" and the session runs all four steps
([`SKILL.md`](SKILL.md)). Output goes to `Job Search/YYYY-MM-DD/` inside this repo
(override with `JOBSCRAPER_OUTPUT_DIR`).

## Model split

| Task | Where it runs |
|---|---|
| Fetching, filtering, URL dedup, exports | Python, no model |
| German level, required experience, design-profile fit | Haiku 5.5 subagents (`model: "haiku"`) |
| Already-applied matching against the mallika-cv tracker | Haiku 5.5 subagents |
| Orchestration, final report, hand-off to `mallika-cv` | Claude Desktop session model |

Python writes `_haiku/<kind>_NNN.input.json`; each subagent writes the matching
`.result.json`. Missing or invalid answers route the row to **Needs Review**.

## Filters

| Rule | Value |
|---|---|
| Freshness | 24 hours |
| Titles | product/UX/UI/interaction/design-engineer keywords; graphic, interior, industrial etc. excluded |
| Seniority | senior, lead, head, principal, staff, manager, director excluded |
| Location | Germany (any city) or explicit EU-remote (`Remote Europe`, `Remote, Portugal`); global/EMEA/Americas rejected |
| Werkstudent | Berlin, Potsdam or remote-Germany only |
| German | B2+ required: dropped. B1 required: Needs Review. A2 or preferred: kept |
| Experience | required minimum over 4 years: dropped |
| Duplicates | exact stable posting URL across all earlier dated exports |
| Already applied | exact URL/company-title match plus Haiku-confirmed matches vs `~/Documents/mallika_applications_tracker.csv` |

## Project layout

```
config.py                # macOS guard, paths, candidate, regexes, Haiku settings
candidate.json           # name, search roles, skills, thresholds
apify_job_search.py      # 8 fetchers, filters, dedup, export
ats_scraper.py           # Greenhouse / SmartRecruiters / Ashby
location_policy.py       # Germany, EU-remote and Werkstudent location rules
haiku_judge.py           # batch-file protocol for Haiku subagents
verify_jobs.py           # prepare / finalize verification
applied_check.py         # tracker matching (Haiku batches)
job_identity.py          # stable posting URL identity
staffing_filter.py       # staffing agency blocklist
dedup_existing_sheets.py # one-off historical URL cleanup
tests/test_regressions.py
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

More detail: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`CHANGELOG.md`](CHANGELOG.md),
[`apify_job_search.md`](apify_job_search.md).
