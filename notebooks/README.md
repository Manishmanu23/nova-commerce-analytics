# Notebooks

Use notebooks for exploration only. Anything reusable moves into `python/nova/` with a test.
Connect with `from nova.common.db import read_sql` (set `PYTHONPATH=python`). Never read `data/ground_truth/` in an analysis notebook, because that would leak the answers.
