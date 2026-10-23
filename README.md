# Agent Swarm Security Lab

Study whether malicious document instructions can spread through agents and cause unauthorized actions, then evaluate defenses without breaking legitimate tasks.

## Current milestone: researcher and writer

Loads three fictional vendor documents, asks one local model to extract facts, validates the response structure, and writes a JSON run record. With `--with-writer`, a separate writer conversation receives only the task and researcher findings, recommends a vendor, explains the alternatives, and cites their source filenames. Both conversations can use the same installed model.

For the default SSO task, the expected recommendation is **Atlas ($40/month)**; Beacon costs $20 but lacks SSO, while Cedar costs $65. Neither agent has action tools. A coordinator, simulated action tools, attacks, and a security evaluator are future milestones. There are no security benchmark results yet.

## macOS

Requires Python 3.11 or newer. From the cloned repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m src.main --offline
python -m unittest discover -s tests -v
```

No pip dependencies are needed. Offline mode is a deterministic parser of the fixture documents, not an LLM agent. It verifies loading, validation, and logging only; do not use it to measure prompt injection susceptibility.

## Run a real researcher

Install and start [Ollama](https://ollama.com/download), then download a model that fits your available memory. This project does not choose or download a model automatically. Run `ollama list` to see installed names; use an exact name from that list:

```bash
python -m src.main --model YOUR_INSTALLED_MODEL
```

Run the researcher-to-writer workflow with your installed model:

```bash
python -m src.main --model qwen3:4b-instruct --with-writer
```

This makes two sequential model requests using separate message histories. The writer does not receive the original documents or researcher system instructions. Without `--with-writer`, the researcher-only command behaves as before.

Check the complete workflow without inference:

```bash
python -m src.main --offline --with-writer
```

The offline writer only handles the default SSO fixture task and rejects custom `--task` values. Its alphabetical tie-break and SSO comparison are deterministic test helpers; live recommendations are produced by the model. Offline mode does not measure model quality or security.

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

The writer uses prompt version `writer-v4` and passes an explicit JSON schema to Ollama's `format` parameter. The schema has a branch for each possible selected vendor (and no selection); each branch excludes that selection from the alternatives. It does not choose Atlas in advance or establish which recommendation is factually correct. Independent validation still rejects duplicates, incorrect source coverage, and conflicting reports. The exact `output_schema` and `generation_mode` are recorded for each writer run so this constraint is visible in later experiments. Live Ollama schema compatibility and generation quality must be checked on your machine; unsupported schemas fail visibly without falling back to unconstrained generation.

Version 4 separates feature eligibility from price ranking. For the default SSO task, the writer must first name every qualifying vendor and its price, then identify the cheapest, then explain exclusions. It prohibits claiming that a vendor is the only SSO option when multiple vendors list SSO. The prompt does not hardcode a winning vendor. This is a generation instruction, not a factual guarantee: retain original run logs and compare live explanations with the documents.

The prompt instructs the writer to filter vendors by the task requirements, compare qualifying prices, then return one internally consistent final report. An annual contract is not treated as evidence that a stated monthly price is unavailable. A structurally valid but incorrect recommendation remains possible and must be checked against the task.

The observed clean-task failure is preserved as `tests/fixtures/writer_beacon_conflict.json`: it selected Beacon while describing Atlas as the correct choice and listing Beacon as an alternative. The regression test verifies rejection with the explicit message `Beacon is both the recommendation and an alternative.` The original response remains in the run log; there is no automatic repair or retry.

Each invocation prints the path to a unique `runs/*.json` record. Inspect:

- `messages`: exact task, document contents, and system instructions.
- `response`: raw model text, actual reported model, and token counts when available.
- `findings`: structurally validated facts, on successful runs.
- `writer`: writer prompt version, exact messages, raw response, validated report, status, errors, and stage timing when `--with-writer` is used.
- `status`, `error`, and `elapsed_seconds`: execution outcome and timing.

Validation checks fields, source coverage, numeric prices, and types. Writer validation checks known vendor names, source references, and explanations for every alternative; it does not decide whether the recommendation or prose is correct. Unique vendor names are required for writer comparisons. A wrong recommendation can still pass structural validation. Manually compare output with the three documents. Logs contain all supplied content and are ignored by Git; fixtures are synthetic. API keys and local environments must never be committed.

If writer generation or validation fails, the run exits with an error and preserves the researcher findings, writer input, and any received raw writer response. If researcher validation fails, the writer is not invoked. Output is stored inside the run log; the writer cannot choose filesystem destinations.

## Read the code in this order

1. `data/vendors/`: inputs with an objectively checkable answer.
2. `src/researcher.py`: document loading, instructions, and validation.
3. `src/model_client.py`: local model request and response handling.
4. `src/writer.py`: writer instructions, handoff, report validation, and offline fixture.
5. `src/main.py`: CLI, sequential execution, and experiment records.
6. `tests/test_researcher.py` and `tests/test_writer.py`: fixture, handoff, failure-path, and mocked transport checks.

Tests use fixtures and a mocked HTTP response. A passing test suite does not mean live model inference was tested.

## Next milestones

1. Run a real model repeatedly and document extraction errors.
2. Verify writer recommendations and explanations on clean tasks before introducing attacks.
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
