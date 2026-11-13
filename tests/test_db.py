import tempfile
import unittest
from pathlib import Path

from src import db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.tmp.name) / "test.db"
        db.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_initializes_two_resume_profiles(self):
        rows = db.query_df("SELECT resume_type FROM resumes ORDER BY id")
        self.assertEqual(rows["resume_type"].tolist(), ["Project Management", "Product Management"])

    def test_job_and_assessment_are_persisted(self):
        job_id = db.execute(
            "INSERT INTO jobs(title, company, job_description) VALUES (?, ?, ?)",
            ("Technical Project Manager", "Example Co", "Own technical delivery.")
        )
        resume = db.query_one("SELECT id FROM resumes WHERE resume_type='Project Manager'")
        assessment_id = db.execute(
            """INSERT INTO assessments(job_id,resume_id,decision,rationale)
               VALUES(?,?,?,?)""",
            (job_id, resume["id"], "PENDING", "Awaiting evidence review.")
        )
        self.assertGreater(job_id, 0)
        self.assertGreater(assessment_id, 0)
        saved = db.query_one("SELECT decision FROM assessments WHERE job_id=?", (job_id,))
        self.assertEqual(saved["decision"], "PENDING")

    def test_foreign_keys_reject_orphan_assessments(self):
        with self.assertRaises(Exception):
            db.execute(
                "INSERT INTO assessments(job_id,resume_id,decision) VALUES(?,?,?)",
                (9999, 1, "PENDING")
            )


if __name__ == "__main__":
    unittest.main()
