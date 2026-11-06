# ADR-004: Governed measures are pre-filtered in fct_orders
**Decision:** columns such as `net_revenue` are already 0 for non-countable orders. Raw amounts are kept with an `_inr` suffix.
**Why:** the most common revenue bug is a forgotten filter (cancelled, test or invalid-date orders). Encoding the rule once makes `SUM()` safe for every analyst, every Power BI measure, and the Copilot.
**Trade-off:** the fact is wider. Analysts must know that `_inr` columns are unfiltered, and the data dictionary says so.
