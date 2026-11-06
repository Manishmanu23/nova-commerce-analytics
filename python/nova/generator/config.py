from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class GenConfig:
    seed: int = 42
    start: date = date(2024, 1, 1)
    end: date = date(2025, 12, 31)
    n_customers: int = 30_000          # registered customers (not all purchase)
    n_products_per_category: int = 60
    session_multiplier: float = 1.0    # scale non-converting web traffic (0.3 = 30%)
    extraction_date: date = date(2026, 1, 1)   # main batch
    late_batch_date: date = date(2026, 1, 12)  # late-arriving refunds/payments
