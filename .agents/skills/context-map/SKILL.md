---
name: context-map
description: Use for every planning or implementation task in this repo — architecture, database, API endpoints, services, repositories, or frontend components. Navigates the Obsidian context map in context/ by hopping through [[wikilinks]] instead of reading the whole codebase, and updates the map after finishing each task. Always trigger this before touching code.
---

# Context Map Protocol

This is the actual behavior contract for the agent. It has two phases per task.

## Orientation phase (before writing any code)
1. Read `context/CONTEXT-MAP.md` only. It is a one-page index of every top-level MOC. Never skip past it into deep files first.
2. From the task description, identify which domain(s) it touches (e.g. "add order cancellation" → api + services + repositories, maybe database).
3. Open only the MOC(s) for those domains. Do not open MOCs for domains you don't need.
4. In each MOC, match the task against the one-line descriptions to find the relevant leaf note(s). If none exists yet, note that you'll create one.
5. From each opened leaf note, follow its `depends_on` / `used_by` links **one hop at a time**, opening only what the current task actually needs (an endpoint's own service and schema — not that service's other unrelated dependents).
6. Stop traversing once you have enough to act. Never re-open a note already read this task. Never fall back to grepping/reading the whole source tree "just in case" — if the map is missing an entry, that's a map problem to fix in the update phase, not a reason to abandon link-hopping.
7. Only open actual source files (via each note's `path:` field) right before editing them. Notes tell you *where* and *what*; code is ground truth for *how it's currently written*.

**Budget guideline:** a typical task should open roughly 1 root index + 1–2 MOCs + 3–8 leaf notes. If you're past ~10 notes, stop and check you haven't wandered into an irrelevant branch.

## Update phase (after finishing the task, before ending the turn)
1. Update every leaf note whose underlying code you touched. Keep it to 2–6 lines. **Overwrite stale info, don't append to it** — a note is current truth, not a changelog.
2. If you created something new (endpoint, service, repository, table, component), create a new leaf note from the matching template and add exactly one link to it from the relevant MOC(s) — nowhere else.
3. Update `depends_on` / `used_by` on **both ends** of any new relationship (if A now calls B: A gets `depends_on: [[B]]`, B gets `used_by: [[A]]`).
4. Set `updated:` to today's date on every note you touched.
5. Append exactly one entry to today's `log/YYYY-MM-DD.md` (create it from the task-log template if it doesn't exist yet, and link it from `log/log.md` if it's a new day) listing: what you did, links to every note you created or edited, and the actual repo files changed.
6. Do not touch a note you didn't need to read for this task, or whose described behavior didn't change. Resist unrelated "helpful" edits.

## Staleness rule
If a note contradicts what the code actually does, fix the note during this task and say so in the log entry — don't leave it wrong for the next task.

## Never do
- Never paste large code blocks into a note — link to `path:` instead.
- Never give two notes the same title; every title is unique vault-wide.
- Never let a note exceed ~30–40 lines; split it into more granular notes instead of letting one grow.
- Never read the whole codebase or run a project-wide search as a substitute for link traversal, except as a genuine last resort when the map has no entry point for the task at all — and if that happens, add the missing entry point during the update phase so it never happens again for this area.

---

# Note templates

Every leaf note has YAML frontmatter so relationships are machine-readable, not just prose. Copy these templates when creating new notes.

### MOC (e.g. `api/endpoints.md`)
```markdown
---
type: moc
domain: api
updated: 2026-10-17
---
# API Endpoints

## Orders
- [[POST-api-v1-orders|POST /api/v1/orders]] — create a new order
- [[GET-api-v1-orders-id|GET /api/v1/orders/:id]] — fetch a single order
```

### Endpoint (`api/POST-api-v1-orders.md`)
```markdown
---
type: endpoint
method: POST
route: /api/v1/orders
status: done
path: src/routes/orders.routes.ts
depends_on: [[OrderService]], [[OrdersTable]]
used_by: []
updated: 2026-10-17
---
# POST /api/v1/orders

Creates an order for the authenticated user. Validates items against
[[ProductsTable]] stock, then calls [[OrderService]] to persist via
[[OrdersRepository]]. Returns 201 with the order, 400 on validation error.
```

### Service (`services/OrderService.md`)
```markdown
---
type: service
path: src/services/order.service.ts
depends_on: [[OrdersRepository]], [[ProductsTable]]
used_by: [[POST-api-v1-orders]], [[GET-api-v1-orders-id]]
updated: 2026-10-17
---
# OrderService

Business logic for orders: stock validation, price calculation, status
transitions. No direct DB access — always goes through [[OrdersRepository]].
```

### Repository (`repositories/OrdersRepository.md`)
```markdown
---
type: repository
path: src/repositories/orders.repository.ts
depends_on: [[OrdersTable]]
used_by: [[OrderService]]
updated: 2026-10-17
---
# OrdersRepository

CRUD + queries for the orders table. Only place raw SQL/ORM calls for orders
are allowed to live.
```

### DB table / schema (`database/schema/OrdersTable.md`)
```markdown
---
type: schema
table: orders
path: migrations/0004_create_orders.sql
columns: id, user_id, status, total_cents, created_at
depends_on: [[UsersTable]]
used_by: [[OrdersRepository]]
updated: 2026-10-17
---
# orders table

Order header rows. `status` is an enum: pending|paid|shipped|cancelled.
`user_id` FKs to [[UsersTable]].
```

### ADR (`architecture/decisions/ADR-0002-auth-strategy.md`)
```markdown
---
type: adr
status: accepted
updated: 2026-10-17
---
# ADR-0002: JWT-based auth

Decision: stateless JWT access tokens (15m) + refresh tokens (7d) in httpOnly
cookies. Rejected sessions-in-DB for horizontal scaling simplicity. Affects
[[POST-api-v1-auth-register]] and every authenticated endpoint.
```

### Frontend component (`frontend/OrderSummaryCard.md`)
```markdown
---
type: component
path: web/src/components/OrderSummaryCard.tsx
depends_on: [[GET-api-v1-orders-id]]
used_by: []
updated: 2026-10-17
---
# OrderSummaryCard

Renders one order's status + line items. Fetches via [[GET-api-v1-orders-id]].
Pure presentational — no local business logic.
```

### Task log entry (`log/2026-10-17.md`, append-only, one file per day)
```markdown
---
type: task-log
date: 2026-10-17
---
## 14:32 — Add order cancellation
Implemented PATCH /api/v1/orders/:id/cancel.
Touched: [[PATCH-api-v1-orders-id-cancel]], [[OrderService]], [[OrdersRepository]]
Notes: fixed stale description in [[OrderService]].
```
