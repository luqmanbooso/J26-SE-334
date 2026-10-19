# Component 4

Component 4 turns mobile telemetry into reproducible Appium tests and can
repair locator failures against a newly captured Android hierarchy. It is
provider-neutral after ingestion and keeps synthesis, execution, healing, and
artifacts under one run directory.

## Pipeline

```text
Sentry or Crashlytics JSON/JSONL
        |
        v
provider adapter -> normalized events -> sessions/journeys
        |
        v
C3 verdict/evidence -> Qwen3 prompt -> parsed Appium script
        |
        v
Appium + UiAutomator2 execution -> result and failure artifacts
        |
        +--> locator failure -> hierarchy narrowing/ranking/policy
                              -> healed script -> bounded re-run
```

## Installation

From the repository root, make the repository importable so the execution
shared-ADB integration can import `common/adb.py`, then install Component 4:

```powershell
pip install -e "component4[semantic]"
```

For tests only, `pip install -e "component4[dev]"` is sufficient. The
semantic extra installs Sentence-BERT support. An Android emulator or device,
Appium with the UiAutomator2 driver, and a reachable Ollama service running
`qwen3:8b` are required for live runs. Offline test runs can explicitly use
`--no-c3`, `--embedder lexical`, and a fake/local LLM; set
`HF_HUB_OFFLINE=1` when the Hugging Face cache is intentionally offline.

## Commands

All commands can also be invoked as `c4 ...` after installation.

### Preflight

Check ADB, the device, Appium, and the configured package:

```powershell
python -m c4 preflight --config component4/configs/target_app.example.json
```

### Run

Run Sentry telemetry with execution and healing enabled:

```powershell
python -m c4 run `
  --telemetry component4/data/events.json `
  --source sentry `
  --config component4/configs/target_app.example.json `
  --runs-dir component4/runs `
  --heal --capture-baseline `
  --baseline-dir component4/baselines `
  --repo-dir component4/test-repository `
  --embedder sbert
```

Crashlytics input uses the same command and selects its existing adapter:

```powershell
python -m c4 run --telemetry crash.json --source crashlytics `
  --config app.json --runs-dir runs
```

Useful run options include `--dry-run`, `--no-c3` (offline/test mode),
`--c3-strict`,
`--limit`, `--model`, `--ollama-url`, `--heal-threshold`, and
`--max-heal-rounds`. `--source` defaults to `sentry`.

### Offline healing

Heal one generated script without a device or LLM:

```powershell
python -m c4 heal --script runs/journey/synthesized_test.py `
  --step 0 --new-hierarchy runs/journey/page_source.xml `
  --baseline-hierarchy baselines/journey/step_0.xml `
  --embedder lexical --out decision.json
```

The command prints JSON unless `--out` is supplied. It exits `0` for a healed
decision, `1` for a safe refusal, and `2` for bad input.

### Evaluation

Create deterministic Settings telemetry:

```powershell
python -m evaluation.make_settings_journeys `
  --labels labels.json --out evaluation/input
```

Run synthesis/replay evaluation:

```powershell
python -m evaluation.run_synthesis_eval `
  --telemetry-dir evaluation/input `
  --config component4/configs/target_app.example.json `
  --runs-dir evaluation/runs --model qwen3:8b `
  --ollama-url http://127.0.0.1:11434
```

Use `--no-execute` for synthesis-only evaluation, `--no-c3` only for an
explicit no-C3 ablation, `--repeats N` for stability, and `--limit N` to cap
journeys.

## Configuration

- [`configs/target_app.example.json`](configs/target_app.example.json) contains
  package, activity/APK, device, Appium, ADB, reset, and setup-command settings.
  Copy it to a local file and adjust it; local device configuration is not
  committed by this project.
- [`configs/prompts/synthesis_v1.txt`](configs/prompts/synthesis_v1.txt) is
  the versioned synthesis prompt. It restricts actions and locator fields and
  requires JSON output.
- CLI flags control model, C3, healing, capture, and output locations.

## Run-folder layout

With `--runs-dir runs`, each journey is stored below `runs/<journey-id>/`.

```text
runs/
  <journey-id>/
    synthesized_test.py       generated script
    result.json                execution result and attempts
    attempt-*.stdout.log      captured subprocess stdout
    attempt-*.stderr.log      captured subprocess stderr
    failure.json               generated-script failure details, when present
    page_source.xml            hierarchy captured after a failure, when present
    screenshot.png             screenshot captured after a failure, when present
    c3_verdict.json            artifact-based C3 verdict, when available
    baseline/step_<n>.xml      optional per-step baseline snapshots
    healed_test_v<N>.py        accepted healed script versions
    healing_report.json        healing decisions, reruns, and final outcome
  pipeline_report.json         all pipeline records
```

Baseline repositories and versioned scripts may instead be placed in the
directories selected by `--baseline-dir` and `--repo-dir`. Their indexes are
deterministic JSON metadata; no current timestamp is used.

## Healing scope

Healing is intentionally narrow: it handles locator-not-found failures,
compares hierarchy structure when a baseline exists, ranks compatible
candidates, and writes a new script only after policy accepts a unique,
confident replacement. Refusals do not modify the original script. Non-locator
failures, ambiguous candidates, unsupported actions, and missing evidence are
not silently repaired. See [`docs/healing-scope.md`](docs/healing-scope.md).

## Limitations

- Execution requires a real Android emulator/device, Appium, UiAutomator2,
  ADB, and an app configuration that launches the target.
- Qwen synthesis requires a reachable Ollama service unless a test double is
  injected.
- Sentence-BERT requires the optional semantic dependency and an available
  model cache; lexical mode is the offline alternative.
- Telemetry adapters depend on the provider export shapes documented in
  [`docs/ingestion-field-assumptions.md`](docs/ingestion-field-assumptions.md).
- Replay success is not proof that the original production crash was
  reproduced; telemetry alone does not provide the app bug.

## Tests

From `component4/` in a clean environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs
```

The live Ollama and Sentence-BERT tests are opt-in through their environment
flags. The live C3 test also depends on its additional external packages.

Experiment records should follow [`docs/experiment-log.md`](docs/experiment-log.md).
