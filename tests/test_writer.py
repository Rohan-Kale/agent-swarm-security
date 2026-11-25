import argparse
import copy
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import main, researcher, writer

ROOT = Path(__file__).resolve().parents[1]


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.documents = researcher.load_documents(ROOT / "data" / "vendors")
        self.research = researcher.offline_response(self.documents)
        self.findings = json.loads(self.research["content"])
        self.response = writer.offline_response(self.findings)

    def test_fixture_selects_atlas_and_explains_others(self):
        report = writer.validate_report(self.response["content"], self.findings)
        self.assertEqual(report["recommended_vendor"], "Atlas")
        alternatives = {v["name"]: v["reason"] for v in report["alternatives"]}
        self.assertIn("SSO", alternatives["Beacon"])
        self.assertIn("more expensive", alternatives["Cedar"])
        self.assertEqual(set(report["sources"]), {d["source"] for d in self.documents})

    def test_no_qualifying_vendor(self):
        for vendor in self.findings["vendors"]:
            vendor["features"] = ["audit logs"]
        response = writer.offline_response(self.findings)
        report = writer.validate_report(response["content"], self.findings)
        self.assertIsNone(report["recommended_vendor"])
        self.assertEqual(len(report["alternatives"]), 3)

    def test_ties_have_repeatable_fixture_selection(self):
        self.findings["vendors"][2]["monthly_price_usd"] = 40
        report = json.loads(writer.offline_response(self.findings)["content"])
        self.assertEqual(report["recommended_vendor"], "Atlas")

    def test_invalid_reports_fail(self):
        original = json.loads(self.response["content"])
        for field, value in [("recommended_vendor", "Unknown"), ("recommended_vendor", []),
                             ("reason", ""), ("sources", ["made-up.txt"]),
                             ("alternatives", [])]:
            with self.subTest(field=field):
                report = copy.deepcopy(original)
                report[field] = value
                with self.assertRaises(ValueError):
                    writer.validate_report(json.dumps(report), self.findings)
        for field, value in [("source", "atlas.txt"), ("name", "Atlas"), ("reason", "")]:
            report = copy.deepcopy(original)
            report["alternatives"][0][field] = value
            with self.assertRaises(ValueError):
                writer.validate_report(json.dumps(report), self.findings)

    def test_handoff_contains_findings_not_original_documents(self):
        messages = writer.build_messages("Recommend a vendor", self.findings)
        payload = json.loads(messages[1]["content"])
        self.assertEqual(payload["researcher_findings"], self.findings)
        self.assertNotIn("documents", payload)
        self.assertEqual(messages[0]["role"], "system")

    def test_observed_beacon_conflict_is_rejected_without_repair(self):
        content = (ROOT / "tests" / "fixtures" / "writer_beacon_conflict.json").read_text(encoding="utf-8")
        response = {"content": content, "model": "qwen3:4b-instruct", "usage": {}}
        with self.assertRaisesRegex(ValueError, "Beacon is both the recommendation and an alternative"):
            writer.validate_report(content, self.findings)
        code, record, calls = self.run_pipeline([self.research, response])
        self.assertEqual((code, calls), (1, 2))
        self.assertEqual(record["writer"]["response"]["content"], content)
        self.assertEqual(record["writer"]["prompt_version"], "writer-v4")
        self.assertNotIn("report", record["writer"])

    def test_unknown_and_duplicate_alternatives_have_specific_errors(self):
        report = json.loads(self.response["content"])
        report["alternatives"][0]["name"] = "Unknown"
        with self.assertRaisesRegex(ValueError, "Unknown vendor in alternatives: Unknown"):
            writer.validate_report(json.dumps(report), self.findings)
        report = json.loads(self.response["content"])
        report["alternatives"].append(copy.deepcopy(report["alternatives"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate vendor in alternatives: Beacon"):
            writer.validate_report(json.dumps(report), self.findings)

    def run_pipeline(self, responses, offline=False):
        with tempfile.TemporaryDirectory() as folder:
            args = argparse.Namespace(task=main.DEFAULT_TASK, offline=offline, model="test-model",
                                     host="http://localhost:11434", documents=ROOT / "data" / "vendors",
                                     runs=Path(folder), with_writer=True)
            with patch("src.main.OllamaClient.complete", side_effect=responses) as mock:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    code = main.run(args)
            logs = list(Path(folder).glob("*.json"))
            self.assertEqual(len(logs), 1)
            return code, json.loads(logs[0].read_text(encoding="utf-8")), mock.call_count

    def test_two_model_calls_and_logged_handoff(self):
        code, record, calls = self.run_pipeline([self.research, self.response])
        self.assertEqual((code, calls), (0, 2))
        handoff = json.loads(record["writer"]["messages"][1]["content"])
        self.assertEqual(handoff["researcher_findings"], record["findings"])
        self.assertEqual(record["writer"]["report"]["recommended_vendor"], "Atlas")
        self.assertEqual(record["writer"]["generation_mode"], "schema-constrained")

    def test_schema_excludes_selected_vendor_without_deciding_winner(self):
        schema = writer.report_schema(self.findings)
        selections = []
        for branch in schema["anyOf"]:
            props = branch["properties"]
            selected = props["recommended_vendor"]["const"]
            selections.append(selected)
            allowed = {item["properties"]["name"]["const"]
                       for item in props["alternatives"]["items"]["anyOf"]}
            expected = {v["name"] for v in self.findings["vendors"]} - {selected}
            self.assertEqual(allowed, expected)
        self.assertEqual(selections, ["Atlas", "Beacon", "Cedar", None])

    def test_transport_sends_writer_schema(self):
        from src.model_client import OllamaClient
        response = {"message": {"content": self.response["content"]}}
        schema = writer.report_schema(self.findings)
        with patch("src.model_client.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as mock:
            OllamaClient("test-model").complete(writer.build_messages(main.DEFAULT_TASK, self.findings, schema), schema=schema)
        payload = json.loads(mock.call_args.args[0].data)
        self.assertEqual(payload["format"], schema)

    def test_writer_failure_preserves_research_and_raw_response(self):
        invalid = {"content": "not JSON", "model": "test-model", "usage": {}}
        code, record, calls = self.run_pipeline([self.research, invalid])
        self.assertEqual((code, calls), (1, 2))
        self.assertIn("findings", record)
        self.assertEqual(record["writer"]["status"], "error")
        self.assertEqual(record["writer"]["response"], invalid)
        self.assertIn("elapsed_seconds", record["writer"])

    def test_researcher_failure_does_not_call_writer(self):
        invalid = {"content": "{}", "model": "test-model", "usage": {}}
        code, record, calls = self.run_pipeline([invalid])
        self.assertEqual((code, calls), (1, 1))
        self.assertNotIn("writer", record)

    def test_offline_pipeline_makes_no_model_calls(self):
        code, record, calls = self.run_pipeline([], offline=True)
        self.assertEqual((code, calls), (0, 0))
        self.assertEqual(record["mode"], "offline-fixture")
        self.assertEqual(record["writer"]["response"]["model"], "offline-fixture-writer")


if __name__ == "__main__":
    unittest.main()
