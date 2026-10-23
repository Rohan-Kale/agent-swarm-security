# Agent Swarm Security Lab

Study whether untrusted document instructions can travel through agents and cause unauthorized actions, then evaluate defenses without breaking legitimate tasks.

## Current milestone: the researcher

This starter loads three fictional vendor documents, asks one local model to extract facts, validates the response structure, and writes a JSON run record. The cheapest vendor supporting SSO is **Atlas ($40/month)**; Beacon costs $20 but lacks SSO, while Cedar costs $65.

The writer, coordinator, simulated action tools, attacks, and security evaluator are future milestones. There are no security benchmark results yet. The researcher has no action tools.

## Quick start on macOS

Requires Python 3.11 or newer. From the cloned repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m src.main --offline
python -m unittest discover -s tests -v
```

No pip dependencies are needed. Offline mode is a deterministic parser of the fixture documents, **not an LLM agent**. It verifies loading, validation, and logging only; do not use it to measure prompt injection susceptibility.

## Run a real researcher

Install and start [Ollama](https://ollama.com/download), then download a model that fits your available memory. This project does not choose or download a model automatically. Run `ollama list` to see installed names; use an exact name from that list:

```bash
python -m src.main --model YOUR_INSTALLED_MODEL
```

The default endpoint is `http://localhost:11434/api/chat`. The client uses [Ollama's JSON output format](https://ollama.com/blog/structured-outputs), disables streaming, and requests temperature 0. Temperature 0 does not guarantee reproducibility. Model output is validated independently; malformed output fails visibly instead of silently being repaired.

Optional shell variables: `OLLAMA_MODEL` and `OLLAMA_HOST`. `.env.example` documents them; `.env` is not loaded automatically. A real model request can time out after 120 seconds. This starter uses no API keys.

## Windows

Clone the same repository and create a separate environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m src.main --offline
python -m unittest discover -s tests -v
```

If activation is restricted, run `.\.venv\Scripts\python.exe -m src.main --offline` directly. Install Ollama and your chosen model separately on Windows if you want inference there. Do not copy `.venv` between computers.

## Inspect the evidence

Each invocation prints the path to a unique `runs/*.json` record. Inspect:

- `messages`: exact task, document contents, and system instructions.
- `response`: raw model text, actual reported model, and token counts when available.
- `findings`: structurally validated facts, on successful runs.
- `status`, `error`, and `elapsed_seconds`: execution outcome and timing.

Validation checks fields, source coverage, numeric prices, and types. It **does not establish factual accuracy or security**. Manually compare output with the three documents. Logs contain all supplied content and are ignored by Git; fixtures are synthetic. API keys and local environments must never be committed.

## Read the code in this order

1. `data/vendors/`: inputs with an objectively checkable answer.
2. `src/researcher.py`: document loading, instructions, and validation.
3. `src/model_client.py`: local model request and response handling.
4. `src/main.py`: CLI and experiment records.
5. `tests/test_researcher.py`: fixture, failure-path, and mocked transport checks.

Tests use fixtures and a mocked HTTP response. A passing test suite does not mean live model inference was tested.

## Next milestones

1. Run a real model repeatedly and document extraction errors.
2. Add a writer that recommends a vendor from the researcher findings.
3. Add a coordinator with an explicit, fixed handoff sequence.
4. Add in-memory action tools and observable authorization decisions.
5. Define attack success and legitimate-task completion using independent state checks.
6. Edit one document to introduce a controlled injection; compare clean and attacked runs.
7. Compare prompt guidance, structured handoffs, and application-enforced authorization.

Keep lab containment active while varying experimental policies inside the simulation. Researcher output replacement and document injection represent different attacker capabilities; evaluate them separately.

## Research references

- [InjecAgent](https://aclanthology.org/2024.findings-acl.624/)
- [Prompt Infection](https://arxiv.org/abs/2410.07283)
- [AgentDojo](https://github.com/ethz-spylab/agentdojo)
