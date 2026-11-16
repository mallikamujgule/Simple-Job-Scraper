#!/usr/bin/env python3
"""
applied_check.py — already-applied job detection (Haiku 5.5, macOS / Claude Desktop)
=====================================================================================

Reads the application tracker written by the mallika-cv skill
(~/Documents/mallika_applications_tracker.csv: Company, Position, Source URL, ...)
and today's scraped jobs. Candidate pairs are pre-filtered by company-token
overlap; Haiku 5.5 subagents then judge whether each pair is the same company
and role.

  1. prepare_match_input(csv_path, run_dir) -> writes applied_NNN.input.json batches
  2. Claude session: Haiku subagents write applied_NNN.result.json
  3. load_llm_matches(run_dir) -> matched URLs + company::title keys
  4. is_already_applied() -> exact URL/key match OR a Haiku-confirmed match
"""

import csv
import json
import re
from pathlib import Path
from tqdm import tqdm

from config import APPLICATIONS_TRACKER_CSV
import haiku_judge
from apify_job_search import normalize_key, _norm_company, _norm_title
from job_identity import normalize_job_url

BATCH_SIZE = 25  # pairs per Haiku batch

# Stopwords for company token pre-filtering (legal suffixes + generic words).
# These are stripped before token matching to avoid false candidate pairs
# (e.g., "Data GmbH" and "Tech GmbH" should not match on "gmbh").
_COMPANY_STOPWORDS = {
    "gmbh", "ag", "inc", "ltd", "co", "kg", "se", "corp", "group",
    "gruppe", "holding", "international", "deutschland", "germany",
    "global", "the", "und", "der", "die", "das", "gbr", "ug",
    "dienstleistungen", "services", "solutions", "technology",
    "technologies", "tech", "systems", "software", "consulting",
    "partners", "energy", "kgaa", "coming", "soon",
}


def _company_tokens(name: str) -> set[str]:
    """Extract meaningful tokens from a company name for pre-filtering.

    Lowercases, strips punctuation, removes legal suffixes and generic
    stopwords, and returns tokens of length >= 3.
    """
    name = name.lower()
    name = re.sub(r"[^\w\s]", " ", name)
    return {t for t in name.split() if len(t) >= 3 and t not in _COMPANY_STOPWORDS}


def load_applied_data() -> dict:
    """Build already-applied detection data from the tracker CSV.

    Returns dict with:
        keys:      set[str]  — normalized company::title keys
        companies: dict[str, list[str]] — normalized company → raw tracker titles
        urls:      set[str]  — normalized URLs
        entries:   list[dict] — raw {company, title, url} for LLM input prep
    """

    keys: set[str] = set()
    companies: dict[str, list[str]] = {}
    urls: set[str] = set()
    entries: list[dict] = []
    row_count = 0

    if not APPLICATIONS_TRACKER_CSV.exists():
        print(f"[!] Already-applied detection: CSV not found at {APPLICATIONS_TRACKER_CSV}")
        return {"keys": keys, "companies": companies, "urls": urls, "entries": entries}

    with open(APPLICATIONS_TRACKER_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            company = (row.get("Company") or "").strip()
            title = (row.get("Position") or "").strip()
            url = (row.get("Source URL") or "").strip()
            if not company or not title:
                continue
            nc = _norm_company(company)
            nt = _norm_title(title)
            keys.add(f"{nc}::{nt}")
            companies.setdefault(nc, []).append(title)
            if url:
                urls.add(normalize_job_url(url))
            entries.append({"company": company, "title": title, "url": url})
            row_count += 1

    print(
        f"[*] Already-applied detection: {row_count} CSV rows → "
        f"{len(keys)} keys, {len(companies)} companies, {len(urls)} URLs"
    )
    return {"keys": keys, "companies": companies, "urls": urls, "entries": entries}


def prepare_match_input(csv_path: Path, run_dir: Path) -> int:
    """Pre-filter candidate pairs between today's scraped jobs and tracker entries.

    Uses company token overlap (>= 1 shared meaningful token) to narrow
    the search space, then writes Haiku batch files into run_dir/_haiku.

    Returns the number of candidate pairs generated.
    """
    from collections import defaultdict

    # Load today's scraped jobs
    today_jobs: list[dict] = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            company = (row.get("company") or "").strip()
            title = (row.get("title") or "").strip()
            url = (row.get("job_url") or "").strip()
            if company or url:
                today_jobs.append({"company": company, "title": title, "url": url})

    # Load tracker entries
    applied_data = load_applied_data()
    tracker_entries = applied_data["entries"]

    # Build token index: tracker company tokens → list of tracker indices
    tracker_by_token: dict[str, list[int]] = defaultdict(list)
    for i, te in enumerate(tracker_entries):
        for token in _company_tokens(te["company"]):
            tracker_by_token[token].append(i)

    # For each today job, find candidate tracker entries
    candidate_pairs: list[dict] = []
    pair_id = 1
    for tj_idx, tj in enumerate(tqdm(today_jobs, desc="Already-applied pairs")):
        candidate_tracker_idxs: set[int] = set()

        # Token overlap
        for token in _company_tokens(tj["company"]):
            for ti in tracker_by_token.get(token, []):
                candidate_tracker_idxs.add(ti)

        # Also check URL match (exact)
        if tj["url"]:
            nu = normalize_job_url(tj["url"])
            for ti, te in enumerate(tracker_entries):
                if te["url"] and normalize_job_url(te["url"]) == nu:
                    candidate_tracker_idxs.add(ti)

        for ti in candidate_tracker_idxs:
            te = tracker_entries[ti]
            candidate_pairs.append({
                "id": pair_id,
                "scraped_company": tj["company"],
                "scraped_title": tj["title"],
                "scraped_url": tj["url"],
                "tracker_company": te["company"],
                "tracker_title": te["title"],
                "tracker_url": te["url"],
            })
            pair_id += 1

    items = {
        str(pair["id"]): {
            "scraped": f'{pair["scraped_company"]} / {pair["scraped_title"]} / {pair["scraped_url"]}',
            "tracker": f'{pair["tracker_company"]} / {pair["tracker_title"]} / {pair["tracker_url"]}',
        }
        for pair in candidate_pairs
    }
    pair_meta = {str(pair["id"]): pair for pair in candidate_pairs}
    haiku_judge.write_batches(run_dir, "applied", APPLIED_INSTRUCTIONS, None, items, size=BATCH_SIZE)
    (haiku_judge.batch_dir(run_dir) / "applied_pairs.json").write_text(
        json.dumps(pair_meta, ensure_ascii=False), encoding="utf-8")

    print(
        f"[*] Already-applied LLM input: {len(today_jobs)} scraped jobs × "
        f"{len(tracker_entries)} tracker entries → {len(candidate_pairs)} candidate pairs"
    )
    return len(candidate_pairs)


def load_llm_matches(run_dir: Path) -> dict:
    """Return {"urls", "keys"} for every pair Haiku confirmed as already applied."""
    pairs_path = haiku_judge.batch_dir(run_dir) / "applied_pairs.json"
    urls: set[str] = set()
    keys: set[str] = set()
    if not pairs_path.exists():
        return {"urls": urls, "keys": keys}
    pairs = json.loads(pairs_path.read_text(encoding="utf-8"))
    for pair_id, answer in haiku_judge.read_results(run_dir, "applied").items():
        if not (isinstance(answer, dict) and answer.get("match") is True):
            continue
        pair = pairs.get(str(pair_id))
        if not pair:
            continue
        nu = normalize_job_url(pair["scraped_url"])
        if nu:
            urls.add(nu)
        key = normalize_key(pair["scraped_company"], pair["scraped_title"])
        if key:
            keys.add(key)
    print(f"[*] Already-applied Haiku matches: {len(urls)} URLs, {len(keys)} keys")
    return {"urls": urls, "keys": keys}


APPLIED_INSTRUCTIONS = (
    "For each item in `items` (keyed by pair id) decide whether the SCRAPED job is the "
    "same company and the same role as the TRACKER entry. Ignore legal suffixes, "
    "location qualifiers, brand/legal-entity variants, seniority/gender markers and "
    "German-English title translations. The same URL is a match even with tracking "
    "parameters. Not a match: different roles at the same company, different "
    "companies sharing a word, or company 'Unknown' unless the URLs match. Answer "
    'each key with {"match": true|false, "reason": "<short>"}.'
)


def is_already_applied(
    company: str, title: str, url: str, applied_data: dict,
    llm_matches: dict | None = None,
) -> bool:
    """Exact tracker URL/key match, or a Haiku-confirmed company+role match."""
    nurl = normalize_job_url(url)
    key = normalize_key(company, title)
    if nurl and nurl in applied_data["urls"]:
        return True
    if key and key in applied_data["keys"]:
        return True
    if llm_matches:
        if nurl and nurl in llm_matches["urls"]:
            return True
        if key and key in llm_matches["keys"]:
            return True
    return False
