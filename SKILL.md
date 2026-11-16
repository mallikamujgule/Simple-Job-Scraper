---
name: mallika-job-search
description: >-
  Use when Mallika wants to run the daily job search pipeline for product and UX
  design roles. Fetches fresh postings (< 24 hours old) from LinkedIn, Indeed,
  Arbeitnow, Xing, Stepstone, Wellfound, EU Remote Jobs and ATS Direct
  (Greenhouse/SmartRecruiters/Ashby); keeps Germany or explicit EU-remote roles
  (Werkstudent: Berlin/Potsdam/remote-Germany); drops exact URLs seen in earlier
  dated exports; then verifies each posting with Haiku 5.5 subagents (German
  level, required experience, design-profile fit, already-applied) and exports
  CSV/XLSX/JSON/MD. macOS and Claude Desktop only. Trigger on "job search",
  "job scraper", "find jobs", "fresh jobs", "design jobs", "ux jobs", "product
  designer jobs", "run job search", "job pipeline".
dependencies: python>=3.10, requests, openpyxl, beautifulsoup4, tqdm
---

# mallika-job-search (Claude Desktop, macOS)

Run everything from this folder. Python does the deterministic work (fetching,
filtering, dedup, exports). It never calls a model. Every small judgment task
runs on **Haiku 5.5** through Agent subagents that you spawn with `model: "haiku"`.
You (the session model) only orchestrate and answer Mallika.

```bash
cd ~/.claude/skills/mallika-job-search
source .venv/bin/activate   # create once: python3 -m venv .venv && pip install -r requirements.txt
```

The candidate (name, target profiles, search roles, skills) lives in
`candidate.json`. The name is read from the mallika-cv profile
(`~/.claude/skills/mallika-cv/okf/profile.yaml`). Do not hardcode either.

**Target profiles** (from Mallika's CV and tracker):
1. Product Designer / UX/UI Designer
2. AI-enabled Product Designer / Product Design Engineer
3. Werkstudent / intern UX (M.A. until Feb 2027)

## Step 1: Scrape

```bash
python3 apify_job_search.py
```

Prints counts per platform and writes `Job Search/YYYY-MM-DD/Job_Search_<Mon>_<D>_<YYYY>.{csv,json,md,xlsx}`.

## Step 2: Prepare verification

```bash
python3 verify_jobs.py prepare
```

Runs platform checks, then writes Haiku batch files to
`Job Search/YYYY-MM-DD/_haiku/`: `jd_NNN.input.json` (German level, required
experience, design-profile fit) and `applied_NNN.input.json` (scraped job vs
mallika-cv tracker). If it prints `0 JD batches` and `0 already-applied batches`,
skip to Step 4.

## Step 3: Judge with Haiku 5.5

List the `*.input.json` files in `_haiku/`. For each one, spawn an **Agent**
subagent with `model: "haiku"` (Haiku 5.5, id `claude-haiku-5-5`). Launch all of
them in one message so they run in parallel. Prompt for each:

> Read `<full path to the input file>` and follow its `instructions` and
> `questions` exactly. Write the answer JSON to the file named in `result_file`,
> in the same directory, following `result_format`. Do nothing else.

Wait for every subagent. If a result file is missing or unreadable, re-run that
one batch once. Do not fill in answers yourself and do not edit result files:
anything missing is routed to **Needs Review** by Step 4.

## Step 4: Finalize

```bash
python3 verify_jobs.py finalize
```

Routes rows into the verified workbook `Job_Search_<...>_verified.xlsx`:
**To Apply**, Reposted, Staffing Companies, Already Applied, Needs Review,
Previously Seen. Dropped without a row: German B2+ required, required
experience over 4 years, not a design target, closed postings, outside
Germany/EU-remote. German B1 required goes to Needs Review (Mallika is A2).

## Step 5: Report

Tell Mallika how many jobs are in To Apply, list the top ones with company,
title, location and link, and name how many need review and why. For any job she
wants to apply to, hand off to the `mallika-cv` skill with the job URL.

## Rules

- macOS only. `config.py` exits on any other platform.
- Never submit applications or send email from this pipeline.
- Do not use Python to judge job descriptions. Use Haiku batches.
- Never relax the Needs Review fallback to get more rows into To Apply.

## Regression checks

```bash
python3 -m unittest discover -s tests -v
```
