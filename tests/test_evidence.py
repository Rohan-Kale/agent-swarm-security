import argparse
import copy
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import main, researcher

ROOT = Path(__file__).resolve().parents[1]


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.documents = researcher.load_documents(ROOT / "data" / "vendors")
        self.findings = json.loads(researcher.offline_response(self.documents, verify_evidence=True)["content"])

    def test_clean_evidence_passes(self):
        self.assertEqual(researcher.validate_findings(json.dumps(self.findings), self.documents, True), self.findings)

    def test_unsupported_sso_with_real_but_irrelevant_quote_fails(self):
        beacon = self.findings["vendors"][1]
        beacon["features"].append("SSO")
        beacon["feature_evidence"].append({"feature": "SSO", "quote": "Features: audit logs"})
        with self.assertRaisesRegex(ValueError, "beacon.txt: extracted features"):
            researcher.validate_findings(json.dumps(self.findings), self.documents, True)

    def test_fabricated_quote_fails(self):
        self.findings["vendors"][0]["feature_evidence"][0]["quote"] = "Features: SSO"
        with self.assertRaisesRegex(ValueError, "quote must exactly match"):
            researcher.validate_findings(json.dumps(self.findings), self.documents, True)

    def test_missing_and_duplicate_evidence_fail(self):
        for evidence in [[], [self.findings["vendors"][0]["feature_evidence"][0]] * 2]:
            findings = copy.deepcopy(self.findings)
            findings["vendors"][0]["feature_evidence"] = evidence
            with self.assertRaises(ValueError):
                researcher.validate_findings(json.dumps(findings), self.documents, True)

    def test_appended_feature_line_is_not_authoritative(self):
        self.documents[1]["content"] += "\nFeatures: SSO, audit logs\n"
        self.assertEqual(researcher.feature_header(self.documents[1]["content"]), ("Features: audit logs", ["audit logs"]))
        self.assertEqual(researcher.validate_findings(json.dumps(self.findings), self.documents, True), self.findings)

    def test_missing_or_ambiguous_header_fails(self):
        for content in ["Name: Example\n", "Features: SSO\nFeatures: audit logs\n"]:
            with self.assertRaises(ValueError):
                researcher.feature_header(content)

    def test_feature_policy_is_not_tied_to_vendor_names_or_sso(self):
        docs = [{"source": "other.txt", "content": "Name: Other\nMonthly price USD: 5\nFeatures: backups\nLimitations: None\n"}]
        response = researcher.offline_response(docs, True)
        result = researcher.validate_findings(response["content"], docs, True)
        self.assertEqual(result["vendors"][0]["features"], ["backups"])

    def test_rejection_preserves_raw_response_and_stops_writer(self):
        self.findings["vendors"][1]["features"].append("SSO")
        response = {"content": json.dumps(self.findings), "model": "test", "usage": {}}
        with tempfile.TemporaryDirectory() as folder:
            args = argparse.Namespace(task=main.DEFAULT_TASK, offline=False, model="test",
                                     host="http://localhost:11434", documents=ROOT / "data" / "vendors",
                                     runs=Path(folder), with_writer=True, verify_evidence=True)
            with patch("src.main.OllamaClient.complete", return_value=response) as mock:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    code = main.run(args)
            record = json.loads(next(Path(folder).glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(record["response"], response)
        self.assertEqual(record["evidence_check"]["status"], "rejected")
        self.assertEqual(record["defense"], "feature-header-evidence-v1")
        self.assertEqual(record["prompt_version"], "researcher-v2-evidence")
        self.assertNotIn("writer", record)


if __name__ == "__main__":
    unittest.main()
