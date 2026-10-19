---
type: service
path: component4/src/c4/journeys/export.py
depends_on: [[SessionizationService]]
used_by: []
updated: 2026-10-20
---
# Journey seed export

Validates the editable perturbation-hint rules and serializes
`JourneyDocument` files plus a deterministic index. Journey creation is an
explicit stage between sessionization and synthesis; exported seeds are
available for the C1/C2 hand-off and reload into `FailureJourney` objects.
