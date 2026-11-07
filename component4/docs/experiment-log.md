# Experiment log

Use one copy of this template per experiment. Replace every placeholder with
an observed value or command output. Do not estimate missing measurements.

## Environment

- Date:
- Repository commit:
- Operating system:
- Python version:
- Component 4 installation:
- Appium version/driver:
- Device or emulator:
- Target application/package:
- Ollama/model:
- C3 configuration:
- `HF_HUB_OFFLINE`:
- Other relevant environment variables:

## Commands

```text
# Paste the exact commands, including flags and working directory.
```

## Results

- Input files:
- Run directory:
- Synthesis result:
- Execution result:
- Healing result:
- Evaluation outputs:
- Test command and exact pass/skip/fail counts:

## Problems

- Problem:
- Reproduction command:
- Evidence/artifact:
- Resolution or follow-up:


---

# Recorded experiments

All three experiments use the AndroR2 dataset (https://github.com/SageSELab/AndroR2),
converted with `evaluation/andror2_import.py`. Generation only measures whether
the model's steps pass the checks; it does not execute them.

## Environment (shared)

- Operating system: Windows 10 Home 10.0.19045
- Python version: 3.10.2, run from `component4/`
- Ollama/model: Ollama 0.40.13, `qwen3:8b` (about 88% CPU, 12% GPU on a 2 GB MX330)
- Appium version/driver: Appium 3.8.0 with the UiAutomator2 driver (driver version not recorded)
- Device or emulator (experiment 3 only): Android emulator `Medium_Phone_API_35`, Android 15, headless
- C3 configuration: not used (`--no-c3`)
- Input: the 21 `crash` reports of AndroR2 that converted, 188 converted steps
  (23 crash scripts read, 2 had nothing convertible; 39 script statements dropped)
- Repository commit: `1b43518` plus the uncommitted APK replay support and shared-ADB fallback

## Experiment 1: generation before the coverage check (2026-11-01)

Commands:

```text
python -m evaluation.andror2_import --dataset evaluation/data/andror2 --out evaluation/data/andror2_traces_crash
python -m evaluation.run_synthesis_eval --telemetry-dir evaluation/data/andror2_traces_crash --source trace --config <target.json> --runs-dir evaluation/runs/andror2_crash --no-execute --no-c3
```

Results (prompt `synthesis_v1`, one request per journey, 120 s request timeout):

- Generation success 21 of 21; first attempt 76%; grounded steps 95%; valid scripts 100%.
- Median model time 56 s, 95th percentile 139 s.
- Steps kept in the generated tests: 43 of 188 (23%); 8 of 21 journeys complete.
- In 13 journeys the model returned a single step. On `andror2-276` (3 taps) the
  raw reply was one step. The prompt showed a one-step example and nothing
  checked that the test covered the journey.

## Experiment 2: generation after the fixes (2026-11-06)

Fixes: a coverage check that rejects output omitting journey events, prompt
`synthesis_v3` (one compact step per event), and generation in parts of 8 events.

Commands:

```text
python -m evaluation.run_synthesis_eval --telemetry-dir evaluation/data/andror2_traces_crash --source trace --config <target.json> --runs-dir evaluation/runs/andror2_crash_v3_full --no-execute --no-c3 --llm-timeout 300 --num-predict 2048
```

Results:

- Generation success 21 of 21; first attempt 100% (no retries); grounded steps 100%; valid scripts 100%.
- Steps kept: 188 of 188 (100%); 21 of 21 journeys complete.
- Total model time 31 minutes (25 minutes before); median per journey 45 s, 95th percentile 242 s.
- Intermediate checks: the six journeys shortened in experiment 1 went from 6 of 25
  steps to 25 of 25; the 18-step `andror2-198` took 748 s with prompt v2 and
  chunking, and 244 s with prompt v3 and chunking, with all 18 steps both times.

## Experiment 3: replay on six apps (2026-11-07)

Six crash traces with small APKs (`2`, `7`, `11`, `23`, `174`, `186`) were generated
and replayed, each on its own APK.

Commands:

```text
python -m evaluation.run_synthesis_eval --telemetry-dir evaluation/data/andror2_traces_replay --source trace --config <target.json> --runs-dir evaluation/runs/andror2_replay3 --no-c3 --apk-root evaluation/data/andror2 --llm-timeout 300 --num-predict 2048
```

Results:

- Generation 6 of 6 on the first attempt, grounded steps 100%.
- Replay success 1 of 6 (17%).

| Trace | Result | Cause |
|---|---|---|
| andror2-11 | passed | 2 steps ran end to end |
| andror2-186 | failed | `INSTALL_FAILED_DEPRECATED_SDK_VERSION`: the app targets SDK 23; Android 15 requires 24 |
| andror2-23, -2, -7 | failed | Appium reported the main activity "never started" (reports are for Android 7, 6.1, 8.1). Experiment 7 later found the same message on an app that was fine, caused by Appium's wait for the launch activity, so Android 15 incompatibility is not proven for these and they were not retested |
| andror2-174 | failed | locator not found at step 0 (`org.mozilla.focus:id/skip`) |

## Problems

- Problem: replay on an Android 15 emulator cannot test apps built for Android 6 to 8.
  Four of the five failures are install or launch failures, not test quality.
  Evidence: `execution_result.json` and `attempt-1.stderr.log` in each run folder.
  Follow-up: use an emulator image at the Android version each report names (not available here).
- Problem: install and launch failures are classified `unknown` by the execution
  classifier, not as an environment problem.
- Problem: replay success measures that the steps can be executed, not that the
  original bug was reproduced; the failure comes from the metadata.
- Problem: only 6 of the 21 journeys were replayed, chosen for small APKs, so the
  replay rate is not an estimate for the dataset.

---

# Healing experiments

## Environment (shared)

- Date: 2026-11-07
- Operating system: Windows 10 Home 10.0.19045; Python 3.10.2; libcst 1.9.0; pydantic 2.14.0
- Input: four real device hierarchy dumps in `evaluation/data/hierarchies`
  (`clock__alarms`, `contacts__list`, `settings__home`, `settings__network`)
- Seed 42, ambiguity margin 0.05, confidence threshold 0.5
- Embedders: `lexical`, and `sentence-transformers/all-MiniLM-L6-v2` (sentence-transformers 6.1.0)
- Latency is recorded as 0 by design so that outputs are identical for the same seed

## Experiment 4: healing on real screens with controlled mutations

Commands:

```text
python -m evaluation.run_healing_eval --hierarchies evaluation/data/hierarchies --embedder lexical --out evaluation/runs/healing_lexical
python -m evaluation.run_healing_eval --hierarchies evaluation/data/hierarchies --embedder lexical --targets-per-screen 40 --out evaluation/runs/healing_lexical_40
python -m evaluation.run_healing_eval --hierarchies evaluation/data/hierarchies --embedder lexical --targets-per-screen 40 --out evaluation/runs/healing_lexical_fixed
python -m evaluation.run_healing_eval --hierarchies evaluation/data/hierarchies --embedder sbert --targets-per-screen 40 --out evaluation/runs/healing_sbert
```

Results:

- With the default 3 targets per screen only 8 scenarios were built (7 in scope), and every
  method scored 100%. That cannot tell the methods apart.
- With 40 targets per screen: 84 scenarios, accuracy 94.4% and false repair 4.8% for every
  method. All 8 problem scenarios, in two change classes (`ambiguous_lookalike` false
  repairs, `remove_id_keep_text` missed heals), used the same unlabeled `Switch` widget on all four
  screens. A node with no text or description cannot keep its text or have a locatable
  lookalike, so the ground truth was invalid. The two mutations now require a labeled
  target. This changed the test, not the healer.
- Corrected set, 76 scenarios (68 in scope, 8 out of scope: removed elements):

| Method | Lexical accuracy | Sentence-BERT accuracy | False repair (SBERT) | Missed heal (SBERT) |
|---|---:|---:|---:|---:|
| B1 structure only | 100% | 100% | 0.0% | 0.0% |
| B2 semantic only | 100% | 83.8% | 5.3% | 10.3% |
| B3 proposed, with baseline | 100% | 95.6% | 0.0% | 4.4% |
| B4 proposed, telemetry only | 100% | 89.7% | 0.0% | 10.3% |

- Removed elements: 8 of 8 refused by every method with Sentence-BERT.
- Threshold sweep (Sentence-BERT, proposed method): accuracy 100% from 0.30 to 0.45, 95.6% at
  0.50 and 0.55, 89.7% at 0.60, 80.9% at 0.65, 63.2% at 0.70; false repair 0% at every
  threshold. Lexical: 100% to 0.50, 94.1% at 0.55 and 0.60, 73.5% at 0.65, 61.8% at 0.70.

## Experiment 5: healing on a real replay failure

Input: the one `locator_not_found` from experiment 3 (`andror2-174`, step 0, `org.mozilla.focus:id/skip`).

```text
python -m c4 heal --script <run>/synthesized_test.py --step 0 --new-hierarchy <run>/page_source.xml --embedder lexical
```

Result: refused (low confidence, best score 0.0). The captured screen was an Android system
dialog (package `android`; texts "Firefox Focus", "Check for update", "OK"), so the app's
button did not exist. A repair would have been wrong.

## Experiment 6: XPath locators

The AndroR2 converter writes positional XPath for about a quarter of its steps. The locator
lookup only understood `//tag[@attr='value']`, so a positional XPath matched nothing, even
with a real old and new screen, and the refusal said "low confidence".

Fix: the lookup resolves `(//Class)[n]`, `(//*[@clickable='true'])[n]` and
`(//Class[@clickable='true'])[n]` against the old screen, and a refusal says when the
original locator has nothing to compare. With a real old and new pair, a positional XPath
now heals to the correct element. Without the old screen it is still refused.

## Healing problems

- Problem: structure alone (B1) matched or beat the combined method (B3) with Sentence-BERT,
  so the evaluation does not show what the semantic layer adds. B2, without the structural
  rules, made false repairs.
- Problem: 60 of 68 in-scope scenarios are text changes, the set has four screens, and it has
  no genuinely ambiguous case, so the ambiguity policy is covered only by unit tests.
- Problem: the sweep shows no false repairs at any threshold, but only 8 scenarios could
  produce one, so a lower threshold is not shown to be safe. The default stays 0.5.
- Problem: the evaluation builds no XPath scenarios; XPath healing is covered by unit tests.
- Problem: the earlier evaluation of 84 scenarios contained 8 invalid scenarios, corrected as
  described above.

---

## Experiment 7: healing across two real releases of the same app (2026-11-07)

Goal: take a test written against one real release of an app, run it unchanged on another
real release, and heal what breaks, with the older release's screen as the baseline.

Data: 19 of the 43 AndroR2 apps have two or more distinct commits (65 reports). 64 APKs were
downloaded (one file was not available) and surveyed on the `Medium_Phone_API_35` emulator.

Commands:

```text
python -m evaluation.release_healing survey --traces evaluation/data/andror2_traces_multi/traces.jsonl --apk-root evaluation/data/andror2 --config <target.json> --out evaluation/runs/compat.json
python -m evaluation.release_healing run --traces evaluation/data/andror2_traces_multi/traces.jsonl --apk-root evaluation/data/andror2 --config <target.json> --compat evaluation/runs/compat.json --runs-dir evaluation/runs/release_healing_sbert2 --embedder sbert
```

Survey of 61 APKs: 36 install and launch; 11 refused (`INSTALL_FAILED_DEPRECATED_SDK_VERSION`,
target SDK below 24); 11 refused (`INSTALL_FAILED_NO_MATCHING_ABIS`, ARM-only on an x86_64
emulator); 2 did not stay running; 1 `INSTALL_FAILED_CONFLICTING_PROVIDER`. 16 apps had a
runnable release; 11 pairs across 6 apps were selected (Aegis, Anki, QKSMS, VinylMusicPlayer,
Firefox Focus, andOTP), using the shortest test (2 to 8 steps) as the source.

Results (11 pairs, Sentence-BERT):

| Outcome | Pairs |
|---|---:|
| Test passes on its own release | 6 |
| Passes unchanged on the other release | 5 |
| Fails on the other release, not a locator failure | 1 |
| Fails on its own release (no valid comparison) | 5 |
| Locator breaks between releases | **0** |
| Healed and verified | **0** |

- The failure that was not a locator failure (Anki 157 to 158, step 4) was Appium's
  "Could not proxy command to the remote server", an infrastructure error.
- The five tests that failed on their own release were QKSMS (two pairs, step 1), VinylMusicPlayer
  (two pairs, step 2) and Firefox Focus (step 3): the expected element was not on screen. These
  scripts depend on screens or dialogs that were removed (system dialogs) or that differ on Android 15.

Conclusion: no locator broke between two real releases in this sample, so healing on real
release changes is not demonstrated, and neither is a failure of it. The tests were short (2 to 6
steps, mostly first-run screens), which is where releases of an app change least.

Setup problems found and fixed along the way (these affect any replay on this dataset):

- Appium waits for the launch activity it resolves and reports "never started" when that
  activity redirects (Aegis). `wait_activity` (`appWaitActivity`) fixes it.
- The scripts begin by tapping permission dialogs whose ids differ between Android versions, and
  installing with permissions granted means the dialogs never appear. Steps that tap the Android
  system are dropped and counted per pair (`system_steps_removed`).
- Android 15 shows an older-version compatibility dialog on every launch of apps built for an
  older Android, which covers the app. `debug.wm.disable_deprecated_target_sdk_dialog=1` turns it
  off until the emulator restarts.

Problems:

- Problem: 0 healings were observed, so the healer was not exercised on a real release change.
  Follow-up: a larger sample with longer tests (`--max-steps`, `--per-app`) and an emulator at
  each report's Android version.
- Problem: five of the six apps that reached a pair needed workarounds above; results depend on them.
