# Healing scope

## In scope and out of scope

| Area | In scope | Out of scope |
|---|---|---|
| Failure type | `locator_not_found` | Script, infrastructure, element-state, and unknown failures |
| Evidence | Captured page source; optional stored baseline | Inventing hierarchy, locator, or device state |
| Matching | ID, accessibility ID, UiSelector, XPath-derived descriptors; structural and semantic ranking | Arbitrary code rewriting or changing test intent |
| Actions | Existing generated tap, input, navigate, scroll, and back steps are considered by the engine's compatibility rules | Adding new actions, credentials, or destructive behavior |
| Output | A new versioned script after policy approval | In-place modification after refusal |
| Retry | Bounded by `max_heal_rounds` | Unbounded retries or automatic recovery from unrelated failures |

## Safety rules

1. A refusal is a valid result. The original script remains unchanged.
2. Candidates must pass action compatibility and narrowing rules before
   semantic ranking.
3. A baseline can remove unchanged nodes; without one, the decision records
   that this structural rule was skipped.
4. Healing requires the configured confidence threshold and the ambiguity
   margin/uniqueness policy.
5. Every accepted repair is written as a separate script and repository
   version with its parent and decision metadata.
6. The rerun loop stops after a pass, refusal, non-locator failure, missing
   page source, or the configured round limit.
7. Telemetry-only fallback descriptors use only the locator and selected
   journey context; they do not dump an entire context object.

