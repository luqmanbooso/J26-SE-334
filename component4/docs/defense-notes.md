# Defense notes

These answers are limited to behavior visible in Component 4 source, tests,
and documentation. The repository currently has no `docs/evidence/` directory,
so no additional empirical evidence is assumed. Any unmeasured quantity is
marked `TODO`.

## Likely questions

### What does Component 4 do?

It loads Sentry or Crashlytics telemetry, normalizes events, groups them into
journeys, synthesizes an Appium script, optionally executes it, and can attempt
a bounded locator repair after a locator-not-found failure.

### Why are both Sentry and Crashlytics supported?

They have separate adapters but produce the same provider-neutral
`NormalizedEvent` model. The `run` command selects the adapter with
`--source`; the default is Sentry.

### How is a generated test constrained?

The versioned synthesis prompt allows only tap, input, navigate, scroll, and
back actions; restricts locator keys; requires JSON; and tells the model not to
invent text, credentials, or destructive actions.

### What causes healing to run?

The pipeline only invokes the healer when execution reports
`LOCATOR_NOT_FOUND` and healing is enabled. The service then requires page
source evidence and stops on pass, refusal, a non-locator failure, missing
page source, or the configured maximum number of rounds.

### Can healing silently change a test?

No. Accepted repairs are written to `healed_test_v<N>.py` and optionally the
versioned repository. A refusal does not modify the original script.

### How is a candidate selected safely?

The engine narrows by action compatibility and structural rules, ranks the
remaining candidates semantically, and applies confidence and ambiguity policy
before producing a healed script. Baseline comparison can remove unchanged
nodes.

### How is C3 used?

C3 is part of the synthesis and failure-artifact hand-off. It supplies visual
and contextual evidence, and the integration records whether the result was
used, unavailable, invalid, or had no evidence. In strict mode, unavailable or
invalid C3 responses make the record an error; otherwise the fallback is
recorded rather than hidden. `--no-c3` is reserved for explicit offline or
ablation runs.

### Does a successful replay prove the original crash was reproduced?

No. The evaluation documentation explicitly reports replay success because
telemetry without a real app bug cannot measure failure reproduction.

### What live infrastructure is required?

An Android emulator or device, Appium with UiAutomator2, ADB, a valid target
configuration, and Ollama `qwen3:8b` are required for the corresponding live
workflow. Offline tests can use lexical healing and injected fakes.

### What are the measured success rates or latency numbers?

No general result is asserted here. Record experiment-specific values in
`experiment-log.md`; unmeasured values are **TODO**.

### How many tests pass?

The answer must come from the exact clean-environment test run for the
submitted revision: **TODO** until that run is performed. Do not substitute a
previous run's count.
