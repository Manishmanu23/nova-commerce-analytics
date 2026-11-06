# ADR-006: Copilot is tool-constrained and validated
**Decision:** the LLM never sees the database. It only writes prose over evidence returned by read-only governed tools, and a validator rejects any answer with an ungrounded number, an uncertified metric name, or an uncited numeric paragraph. If the validator rejects a draft, the deterministic template answer is shown instead.
**Why:** a text-to-SQL chatbot can compute "revenue" in a way no department agrees with, and it can invent numbers. Constraining the Copilot to the governed layer makes answers auditable and reproducible.
**Trade-off:** it answers fewer question types (only certified metrics and dimensions). That limitation is intentional.
