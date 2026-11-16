"""Central configuration for the job pipeline (macOS + Claude Desktop only).

Everything is resolved relative to this repository or the user's home folder,
so there are no machine-specific absolute paths anywhere else in the code.
The candidate's name comes from the mallika-cv skill profile
(~/.claude/skills/mallika-cv/okf/profile.yaml) with candidate.json as the
local copy, so the two never need to be edited together by hand.
"""

import json
import os
import re
import sys
from pathlib import Path

if sys.platform != "darwin":
    raise SystemExit(
        "This pipeline runs only on macOS inside the Claude Desktop app "
        f"(detected platform: {sys.platform})."
    )

REPO_DIR = Path(__file__).resolve().parent

# ── Paths ────────────────────────────────────────────────────────────────────
JOB_SEARCH_DIR = Path(os.getenv("JOBSCRAPER_OUTPUT_DIR", REPO_DIR / "Job Search"))
CV_SKILL_DIR = Path(os.getenv("MALLIKA_CV_DIR", Path.home() / ".claude" / "skills" / "mallika-cv"))
APPLICATIONS_TRACKER_CSV = Path(os.getenv(
    "LLM_CV_TRACKER_CSV", Path.home() / "Documents" / "mallika_applications_tracker.csv"
))

# ── Candidate (name copied from the mallika-cv profile) ──────────────────────
def _load_candidate() -> dict:
    data: dict = {}
    local = REPO_DIR / "candidate.json"
    if local.exists():
        data = json.loads(local.read_text(encoding="utf-8"))
    profile = CV_SKILL_DIR / "okf" / "profile.yaml"
    if profile.exists():
        match = re.search(r'^name:\s*"?([^"#\n]+?)"?\s*(?:#.*)?$',
                          profile.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            data["name"] = match.group(1).strip()
    return data


CANDIDATE = _load_candidate()
CANDIDATE_NAME = CANDIDATE.get("name", "Mallika Mujgule")
SEARCH_ROLES = CANDIDATE.get("search_roles", ["Product Designer", "UX Designer"])
MAX_EXP_YEARS = int(CANDIDATE.get("max_required_experience_years", 4))
PARTTIME_CITIES = tuple(CANDIDATE.get("parttime_cities", ["Berlin", "Potsdam"]))
GERMAN_LEVEL = CANDIDATE.get("german_level", "A2")
CANDIDATE_SKILLS = [s.lower() for s in CANDIDATE.get("match_keywords", [])]

# ── Models ───────────────────────────────────────────────────────────────────
# Small tasks (JD verification, already-applied matching, title fit) run on
# Haiku 5.5 via Agent subagents inside the Claude Desktop session. The session
# model itself only orchestrates and handles anything needing real judgment.
HAIKU_MODEL_ID = "claude-haiku-5-5"
HAIKU_AGENT_ALIAS = "haiku"  # value for the Agent tool's `model` parameter
HAIKU_BATCH_SIZE = 8

FRESHNESS_HOURS = 24

# ── Title rules ──────────────────────────────────────────────────────────────
import re as _re

DOMAIN_TITLE_KEYWORDS = _re.compile(
    r"\b(product\s+design\w*|produktdesign\w*|ux|ui|ux\s*/\s*ui|ui\s*/\s*ux|"
    r"user\s+experience|user\s+interface|interaction\s+design\w*|"
    r"digital\s+product\s+design\w*|design\s+engineer\w*|experience\s+design\w*|"
    r"service\s+design\w*|ai\s+product\s+design\w*|visual\s+design\w*|"
    r"app\s+design\w*|mobile\s+design\w*|web\s+design\w*)",
    _re.IGNORECASE,
)

# Seniority above her target band (Product Designer / UX Designer / Design Engineer).
EXCLUDED_TITLE_PATTERNS = _re.compile(
    r"\b(senior|sr|lead|head|principal|staff|manager|director|vp|chief|expert|team lead)\b",
    _re.IGNORECASE,
)

# Design disciplines that are not product/UX work.
NON_TARGET_TITLE_PATTERNS = _re.compile(
    r"\b(graphic|interior|fashion|industrial|mechanical|hardware|chip|ic|game|"
    r"3d|motion|sound|packaging|landscape|floor|kitchen|jewelry|textile)\s+(?:designer|design)\b",
    _re.IGNORECASE,
)
