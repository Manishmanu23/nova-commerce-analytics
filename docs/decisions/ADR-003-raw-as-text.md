# ADR-003: Raw layer stores everything as TEXT
**Decision:** ingestion never casts. Staging casts with defensive macros (`safe_numeric`, `to_ist`).
**Why:** one malformed date in a 60k-row file must not block the whole load. A failed cast becomes NULL plus a failing test, which is visible, attributable and fixable. We also keep the exact bytes the source sent, for audits.
**Trade-off:** raw is larger, and type errors surface one layer later.
