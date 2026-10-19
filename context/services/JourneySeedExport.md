---
type: service
path: component4/src/c4/journeys/export.py
depends_on: [[SessionizationService]]
used_by: []
updated: 2026-10-19
---
# Journey seed export

Validates the editable perturbation-hint rules and serializes
`JourneyDocument` files plus a deterministic index. It also reloads exported
documents into `FailureJourney` objects for pipeline synthesis.
