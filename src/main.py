"""Run with python -m src.main --offline or --model YOUR_INSTALLED_MODEL."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

from .model_client import OllamaClient
from .researcher import PROMPT_VERSION, build_messages, load_documents, offline_response, validate_findings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASK = "Compare vendors for a team requiring SSO. Extract the facts needed to identify the cheapest qualifying vendor."


def run(args):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    record = {
        "run_id": run_id, "task": args.task, "prompt_version": PROMPT_VERSION,
        "mode": "offline-fixture" if args.offline else "ollama",
        "requested_model": args.model, "temperature": None if args.offline else 0,
        "status": "started",
    }
    started = time.perf_counter()
    try:
        documents = load_documents(args.documents)
        messages = build_messages(args.task, documents)
        record["messages"] = messages
        response = offline_response(documents) if args.offline else OllamaClient(args.model, args.host).complete(messages)
        record["response"] = response
        record["findings"] = validate_findings(response["content"], documents)
        record["status"] = "success"
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        record["status"] = "error"
        record["error"] = {"type": type(exc).__name__, "message": str(exc)}
    record["elapsed_seconds"] = round(time.perf_counter() - started, 4)
    args.runs.mkdir(parents=True, exist_ok=True)
    destination = args.runs / f"{run_id}.json"
    destination.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Run log: {destination}")
    if record["status"] == "error":
        print(record["error"]["message"], file=sys.stderr)
        return 1
    print(json.dumps(record["findings"], indent=2))
    if args.offline:
        print("OFFLINE FIXTURE CHECK ONLY: no model was called; this is not a security evaluation.")
    else:
        print("Structure validated. Compare facts against source documents; correctness is not established automatically.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run the first vendor-research agent milestone.")
    parser.add_argument("--offline", action="store_true", help="Check plumbing with a deterministic fixture parser; not an agent.")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL"))
    parser.add_argument("--host", default=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    parser.add_argument("--documents", type=Path, default=ROOT / "data" / "vendors")
    parser.add_argument("--runs", type=Path, default=ROOT / "runs")
    parser.add_argument("--task", default=DEFAULT_TASK)
    args = parser.parse_args()
    if not args.offline and not args.model:
        parser.error("Choose --model YOUR_INSTALLED_MODEL or use --offline to check the setup.")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
