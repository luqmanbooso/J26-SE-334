# Journey seed contract

C4 exports a versioned `JourneyDocument` (`schema_version: "c4.journey/1"`) for
C1 and C2. The complete JSON schema is available with
`python -m c4 journeys --schema`.

## Fields

- `journey_id`, `session_id`, `source`, and `app_version` identify the
  production journey.
- `failing_screen`, `exception_type`, `reproducible`,
  `not_reproducible_reason`, `truncated`, and `action_count` describe its
  replayability and failure.
- `steps` preserves each event's index, canonical action, name, screen,
  locator, optional input value, event id, and timestamp.
- `failure` contains the failure name, type, message, and timestamp.
- `seed.targets` contains only `tap`, `input`, and `navigate` steps, in order.
  Each target has its original step index, action, label, locator, and screen.
- `seed.failing_step_index` is the last actionable step before the failure.
- `seed.perturbation_hints` contains optional `{stressor, step_index, reason,
  basis}` suggestions. `basis` is always `heuristic`.

## Example

```json
{
  "schema_version": "c4.journey/1",
  "journey_id": "session-1:failure-1",
  "session_id": "session-1",
  "source": "sentry",
  "app_version": "1.2.3",
  "failing_screen": "Settings",
  "exception_type": "SocketTimeoutException",
  "reproducible": true,
  "not_reproducible_reason": null,
  "truncated": false,
  "action_count": 1,
  "steps": [],
  "failure": {
    "name": "Crash",
    "type": "SocketTimeoutException",
    "message": "request timed out",
    "timestamp": "2026-01-01T00:01:00Z"
  },
  "seed": {
    "targets": [],
    "failing_step_index": 0,
    "failing_screen": "Settings",
    "exception_type": "SocketTimeoutException",
    "perturbation_hints": [
      {
        "stressor": "network",
        "step_index": 0,
        "reason": "The failure type suggests a network-related timeout or connection failure.",
        "basis": "heuristic"
      }
    ]
  }
}
```

## Consumers

C2 should tap `seed.targets` in order, resolving each label in the live
hierarchy. If a label is missing, it should fall back to its normal target
choice. C1 may apply the named stressor profile in
`seed.perturbation_hints` at the supplied step index. Hints are suggestions
only and are heuristic; absence of a hint means C4 found no matching rule.
