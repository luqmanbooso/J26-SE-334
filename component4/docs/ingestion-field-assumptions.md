# Ingestion field assumptions

The ingestion adapters normalize provider payloads into the models in
`src/c4/schemas/`. Provider exports vary by SDK, platform, and export format,
so these mappings are deliberately isolated and must be verified against
representative exports before production use.

## Sentry

- `event_id`, `timestamp`, `breadcrumbs.values`, `exception.values`,
  `contexts.session.id`, `release`, `device`, and `os` follow the common Sentry
  event envelope shape.
- Breadcrumb `category`, `message`, `timestamp`, and `data` are supported.
- `data.view.id` and related `view.*` keys are supported as observed Android
  instrumentation conventions, but are not treated as universal Sentry fields.
- Navigation `data.to` is used as the normalized screen when no explicit
  `data.screen` exists.
- The last exception in `exception.values` supplies the normalized exception
  type/value while preserving the complete exception object in `error`.

## Firebase Crashlytics

- `breadcrumbs` and `logs` are accepted as export-specific interaction records.
- `timestamp` or `event_timestamp` is used for the crash event.
- `exception_type`, `issue_title`, `message`, and `stack_trace` are optional
  export fields and are preserved only when present.
- No timestamp is invented. Records without timestamps are quarantined.

These assumptions should be updated when real Sentry Android and Crashlytics
exports are added to `tests/fixtures/`.

## Redaction

Every event is redacted in `make_report`, before deduplication, so all
adapters and file formats share one path (`src/c4/ingestion/redaction.py`).
Free-text fields (`name`, `screen`, locator values, `attributes`, `error`,
`raw`) and quarantined records are masked. Event ids, session ids, timestamps,
and device fields are kept.

Masked patterns: email addresses, phone numbers with a `+` prefix or a
3-3-4 layout, card numbers that pass a Luhn check, JWTs, bearer tokens,
`password`/`token`/`secret`/`api_key`/`authorization` pairs, and any string
stored under a sensitive key such as `email` or `password`.

Limits: names, addresses, and free-form identifiers are not detected, and IP
addresses are not masked because app versions look the same. A locator whose
text is personal data is masked, so a test generated from it targets the
placeholder instead of the original value.
