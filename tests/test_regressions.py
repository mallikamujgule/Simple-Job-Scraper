"""Consumer-visible regressions for location, posting identity, history, and JD routing."""

import csv
import json
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest import TestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import verify_jobs
from apify_job_search import check_experience_and_location
from ats_scraper import _check_experience_and_location
from job_identity import load_seen_job_urls, normalize_job_url
from location_policy import (
    is_germany_location, is_eu_remote_location, is_parttime_city, is_role_location_eligible,
)
from verify_jobs import apply_judgment_answers
import haiku_judge


class GermanyLocationTests(TestCase):
    def test_accepts_explicit_country_and_observed_german_places(self):
        accepted = (
            "Germany",
            "Deutschland",
            "DE",
            "Berlin, DE",
            "Remote, DE",
            "Hamburg",
            "Kiel",
            "Augsburg, Bavaria",
            "88630 Pfullendorf",
            "94496 Ortenburg",
            "Bamberg",
            "Brühl",
            "Grasbrunn",
            "Hattingen",
            "Hirschau",
            "Karlsdorf-Neuthard",
            "Kleinostheim",
            "Mülheim (Ruhr)",
            "Schwanau",
            "Stormarn",
            "Munich",
            "Cologne",
            "Dusseldorf",
        )
        for location in accepted:
            with self.subTest(location=location):
                self.assertTrue(is_germany_location(location))

    def test_rejects_foreign_unknown_remote_and_negative_location_evidence(self):
        rejected = (
            "Paris, Île-de-France",
            "Rio de Janeiro",
            "Paris, de, France",
            "London, United Kingdom",
            "Bracknell, Bracknell Forest, United Kingdom",
            "Switzerland",
            "Zürich",
            "Remote Global",
            "Remote, AMER",
            "Remote Europe",
            "Remote EMEA",
            "North America",
            "Unknown",
            "Germany not eligible",
            "Berlin, New Hampshire",
            "",
            "   ",
        )
        for location in rejected:
            with self.subTest(location=location):
                self.assertFalse(is_germany_location(location))

    def test_mixed_locations_need_a_positive_german_option(self):
        self.assertTrue(is_germany_location("London, UK; Munich, Germany"))
        self.assertFalse(is_germany_location("London, UK; Remote Global"))

    def test_eu_remote_needs_remote_marker_and_eu_region(self):
        for location in ("Remote Europe", "Remote, Portugal", "Remote - EU", "Europe (Remote)"):
            with self.subTest(location=location):
                self.assertTrue(is_eu_remote_location(location))
        for location in ("Remote Global", "Remote EMEA", "Remote, AMER", "Lisbon, Portugal",
                         "Remote, United States", "Europe", ""):
            with self.subTest(location=location):
                self.assertFalse(is_eu_remote_location(location))

    def test_working_student_needs_berlin_potsdam_or_remote_germany(self):
        self.assertTrue(is_parttime_city("Berlin, Germany"))
        self.assertTrue(is_parttime_city("Potsdam"))
        self.assertTrue(is_parttime_city("Remote, Germany"))
        self.assertFalse(is_parttime_city("Hamburg, Germany"))
        self.assertFalse(is_parttime_city("Remote Europe"))
        self.assertFalse(is_role_location_eligible("Working Student", "Munich"))
        self.assertTrue(is_role_location_eligible("Full-Time / Entry-Level", "Munich"))
        self.assertTrue(is_role_location_eligible("Full-Time / Entry-Level", "Remote Europe"))

    def test_scraper_and_ats_paths_share_location_and_title_guards(self):
        for check in (check_experience_and_location, _check_experience_and_location):
            with self.subTest(check=check.__module__):
                self.assertFalse(check("Product Designer", "", "London, UK")[0])
                self.assertTrue(check("Product Designer", "", "Munich")[0])
                self.assertTrue(check("UX/UI Designer (m/f/d)", "", "Remote Europe")[0])
                self.assertFalse(check("Senior Product Designer", "", "Berlin")[0])
                self.assertFalse(check("Graphic Designer", "", "Berlin")[0])
                self.assertFalse(check("Data Analyst", "", "Berlin")[0])
                self.assertFalse(check("Werkstudent UX Designer", "", "Hamburg, Germany")[0])
                self.assertTrue(check("Werkstudent UX Designer", "", "Berlin, Germany")[0])


class PostingIdentityTests(TestCase):
    def test_linkedin_and_indeed_tracking_variants_keep_posting_identity(self):
        linkedin_a = (
            "https://www.linkedin.com/jobs/view/data-analyst-at-example-1234567890"
            "?trackingId=old&refId=one"
        )
        linkedin_b = (
            "http://de.linkedin.com/jobs/view/analytics-engineer-1234567890/"
            "?trk=public_jobs"
        )
        self.assertEqual(normalize_job_url(linkedin_a), "linkedin:1234567890")
        self.assertEqual(normalize_job_url(linkedin_a), normalize_job_url(linkedin_b))

        indeed_a = "https://de.indeed.com/viewjob?jk=AbC123&from=web"
        indeed_b = "http://www.indeed.com/viewjob?utm_source=board&jk=AbC123"
        self.assertEqual(normalize_job_url(indeed_a), "indeed:AbC123")
        self.assertEqual(normalize_job_url(indeed_a), normalize_job_url(indeed_b))
        self.assertNotEqual(normalize_job_url(indeed_a), normalize_job_url(
            "https://de.indeed.com/viewjob?jk=abc123"
        ))

    def test_generic_posting_identity_preserves_case_and_unknown_query_values(self):
        self.assertNotEqual(
            normalize_job_url("https://jobs.example/job/CaseID?requisition=123"),
            normalize_job_url("https://jobs.example/job/caseid?requisition=123"),
        )
        self.assertNotEqual(
            normalize_job_url("https://jobs.example/job/CaseID?requisition=AbC"),
            normalize_job_url("https://jobs.example/job/CaseID?requisition=abc"),
        )
        self.assertNotEqual(
            normalize_job_url("https://jobs.example/job?requisition=123"),
            normalize_job_url("https://jobs.example/job?requisition=456"),
        )
        self.assertEqual(
            normalize_job_url("https://jobs.example/job?b=2&a=1"),
            normalize_job_url("https://jobs.example/job?a=1&b=2"),
        )
        self.assertEqual(
            normalize_job_url("https://jobs.example/job/123?requisition=456&utm_source=one"),
            normalize_job_url("http://jobs.example/job/123?utm_source=two&requisition=456"),
        )

    def test_indeed_detection_requires_a_real_domain_boundary(self):
        impostor = normalize_job_url("https://notindeed.com/viewjob?jk=AbC123")
        legitimate = normalize_job_url("https://de.indeed.com/viewjob?jk=AbC123")
        self.assertEqual(impostor, "https://notindeed.com/viewjob?jk=AbC123")
        self.assertNotEqual(impostor, legitimate)


class DatedHistoryTests(TestCase):
    @staticmethod
    def _write_export(root: Path, run_date: str, urls: list[str]) -> Path:
        folder = root / run_date
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "Job_Search_history.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["job_url"])
            writer.writeheader()
            writer.writerows({"job_url": url} for url in urls)
        return path

    def test_history_uses_every_prior_date_but_not_current_or_future(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_export(root, "2026-10-01", [
                "https://www.linkedin.com/jobs/view/data-engineer-1234567890?trk=old"
            ])
            self._write_export(root, "2026-10-05", [
                "https://de.indeed.com/viewjob?jk=AbC123&from=old"
            ])
            self._write_export(root, "2026-10-07", ["https://jobs.example/current"])
            self._write_export(root, "2026-10-08", ["https://jobs.example/future"])

            self.assertEqual(
                load_seen_job_urls(root, date(2026, 10, 7)),
                {"linkedin:1234567890", "indeed:AbC123"},
            )

    def test_unreadable_dated_history_fails_with_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            folder = root / "2026-10-06"
            folder.mkdir()
            path = folder / "Job_Search_broken.csv"
            path.write_text("title\nData Analyst\n", encoding="utf-8")

            with self.assertRaises(RuntimeError) as context:
                load_seen_job_urls(root, date(2026, 10, 7))
            self.assertIn(str(path), str(context.exception))


class HaikuJudgmentTests(TestCase):
    GOOD = {"german": "a2_or_lower_ok", "experience": "minimum_3_years",
            "profile": "product_or_ux_designer"}

    def test_valid_answers_mark_row_reviewed(self):
        row = {}
        apply_judgment_answers(row, dict(self.GOOD))
        self.assertEqual(row["detail_review_status"], "Reviewed")
        self.assertEqual(row["detail_exp_years"], "3")
        self.assertEqual(row["detail_language"], "German A2 OK")

    def test_invalid_answers_do_not_mark_a_row_reviewed(self):
        row = {}
        with self.assertRaises(ValueError):
            apply_judgment_answers(row, {**self.GOOD, "experience": "invented_bucket"})
        self.assertNotEqual(row.get("detail_review_status"), "Reviewed")

    def test_missing_description_routes_to_explicit_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            rows = [{"description": "Too short"}]
            verify_jobs.prepare_jd_batches(rows, Path(temp_dir))
            self.assertTrue(rows[0]["detail_review_status"].startswith("Needs review:"))

    def test_missing_or_invalid_haiku_results_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            rows = [{"description": "Product designer role. " * 10} for _ in range(3)]
            verify_jobs.prepare_jd_batches(rows, run_dir)
            inputs = sorted(haiku_judge.batch_dir(run_dir).glob("jd_*.input.json"))
            self.assertEqual(len(inputs), 1)
            result = inputs[0].with_name("jd_001.result.json")
            result.write_text(json.dumps({"0": self.GOOD, "1": {**self.GOOD, "german": "x"}}))
            verify_jobs.apply_jd_results(rows, run_dir)
            self.assertEqual(rows[0]["detail_review_status"], "Reviewed")
            self.assertTrue(rows[1]["detail_review_status"].startswith("Needs review:"))
            self.assertTrue(rows[2]["detail_review_status"].startswith("Needs review:"))
            self.assertEqual(rows[2]["detail_language"], "")

    def test_batches_name_the_haiku_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            rows = [{"description": "UX designer role. " * 10}]
            verify_jobs.prepare_jd_batches(rows, Path(temp_dir))
            batch = next(haiku_judge.batch_dir(Path(temp_dir)).glob("jd_*.input.json"))
            self.assertEqual(json.loads(batch.read_text())["model"], "claude-haiku-5-5")
