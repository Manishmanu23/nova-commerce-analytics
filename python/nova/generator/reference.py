"""Static reference data: geography, products, campaigns."""
from datetime import date

import numpy as np
import pandas as pd

from . import scenarios as S

CITIES = [  # city, state, region, tier, weight
    ("Mumbai", "Maharashtra", "West", 1, 9), ("Pune", "Maharashtra", "West", 1, 5),
    ("Nagpur", "Maharashtra", "West", 2, 2), ("Nashik", "Maharashtra", "West", 3, 1),
    ("Delhi", "Delhi", "North", 1, 10), ("Gurugram", "Haryana", "North", 1, 3),
    ("Noida", "Uttar Pradesh", "North", 1, 3), ("Lucknow", "Uttar Pradesh", "North", 2, 3),
    ("Kanpur", "Uttar Pradesh", "North", 2, 2), ("Varanasi", "Uttar Pradesh", "North", 3, 1.5),
    ("Jaipur", "Rajasthan", "North", 2, 3), ("Chandigarh", "Chandigarh", "North", 2, 1.5),
    ("Ludhiana", "Punjab", "North", 2, 1.5), ("Dehradun", "Uttarakhand", "North", 3, 1),
    ("Bengaluru", "Karnataka", "South", 1, 9), ("Mysuru", "Karnataka", "South", 3, 1),
    ("Chennai", "Tamil Nadu", "South", 1, 6), ("Coimbatore", "Tamil Nadu", "South", 2, 2),
    ("Hyderabad", "Telangana", "South", 1, 7), ("Visakhapatnam", "Andhra Pradesh", "South", 2, 1.5),
    ("Vijayawada", "Andhra Pradesh", "South", 3, 1), ("Kochi", "Kerala", "South", 2, 2),
    ("Thiruvananthapuram", "Kerala", "South", 2, 1.2),
    ("Kolkata", "West Bengal", "East", 1, 6), ("Howrah", "West Bengal", "East", 2, 1.2),
    ("Siliguri", "West Bengal", "East", 3, 1), ("Patna", "Bihar", "East", 2, 2.5),
    ("Gaya", "Bihar", "East", 3, 1), ("Bhubaneswar", "Odisha", "East", 2, 1.5),
    ("Ranchi", "Jharkhand", "East", 3, 1), ("Guwahati", "Assam", "North-East", 2, 1.5),
    ("Ahmedabad", "Gujarat", "West", 1, 5), ("Surat", "Gujarat", "West", 2, 3),
    ("Vadodara", "Gujarat", "West", 2, 1.5), ("Goa", "Goa", "West", 3, 0.8),
    ("Indore", "Madhya Pradesh", "Central", 2, 2), ("Bhopal", "Madhya Pradesh", "Central", 2, 1.5),
    ("Raipur", "Chhattisgarh", "Central", 3, 1),
]

CATEGORIES = {
    # name: (subcategories, brands, median price, sigma, cost ratio, line share, base refund prob)
    "Fashion": (["Men Apparel", "Women Apparel", "Footwear", "Accessories"],
                ["UrbanLoom", "Kaya", "StrideX", "Vesti"], 899, 0.55, 0.45, 0.27, 0.13),
    "Electronics": (["Mobile Accessories", "Audio", "Wearables", "Smart Home"],
                    ["VoltEdge", "Sonique", "Zentra", "Kraftel"], 1800, 0.75, 0.78, 0.18, 0.06),
    "Beauty & Personal Care": (["Skincare", "Haircare", "Fragrance"],
                               ["Glowveda", "PureRoot", "Aurelle"], 499, 0.5, 0.40, 0.16, 0.04),
    "Home & Kitchen": (["Cookware", "Decor", "Storage", "Appliances"],
                       ["Hearthly", "Casa Nova", "Kitchora"], 1100, 0.65, 0.55, 0.15, 0.05),
    "Grocery & Gourmet": (["Snacks", "Beverages", "Staples"],
                          ["Annapurna Farms", "Chai Co", "NutriBite"], 349, 0.45, 0.80, 0.14, 0.015),
    "Sports & Fitness": (["Yoga", "Gym", "Outdoor"], ["FitForge", "Trailox"], 1200, 0.6, 0.55, 0.10, 0.06),
}
PRICE_CHANGE_DATE = date(2025, 4, 1)

ACQ_CHANNELS = ["organic", "paid_search", "paid_social", "referral", "affiliate", "marketplace"]
ACQ_PROBS = [0.30, 0.22, 0.17, 0.08, 0.08, 0.15]
PAID_CHANNELS = {"paid_search", "paid_social", "affiliate", "marketplace"}
CHANNEL_LAMBDA = {"organic": 0.42, "referral": 0.45, "paid_search": 0.36, "paid_social": 0.30,
                  "affiliate": 0.30, "marketplace": 0.28}
CHANNEL_CHURN = {"organic": 0.10, "referral": 0.09, "paid_search": 0.12, "paid_social": 0.14,
                 "affiliate": 0.15, "marketplace": 0.15}
CHANNEL_CAC = {"paid_search": 520, "paid_social": 430, "affiliate": 380, "marketplace": 300}
CHANNEL_CODE = {"paid_search": "PSE", "paid_social": "PSO", "affiliate": "AFF",
                "marketplace": "MKT", "email": "EML"}
CAMPAIGN_CHANNEL_LABEL = {"paid_search": "Google Ads", "paid_social": "Meta", "affiliate": "Affiliate",
                          "marketplace": "Marketplace Ads", "email": "Email"}


def geography() -> pd.DataFrame:
    df = pd.DataFrame(CITIES, columns=["city", "state", "region", "city_tier", "weight"])
    df.insert(0, "geo_id", [f"G{str(i + 1).zfill(3)}" for i in range(len(df))])
    return df


def products(rng: np.random.Generator, n_per_cat: int) -> pd.DataFrame:
    rows, pid = [], 1
    for cat, (subs, brands, med, sig, cr, _share, _rf) in CATEGORIES.items():
        for _ in range(n_per_cat):
            sub = subs[rng.integers(len(subs))]
            brand = brands[rng.integers(len(brands))]
            price = float(np.round(np.exp(np.log(med) + rng.normal(0, sig)) / 10) * 10 - 1)
            price = max(price, 99.0)
            cost = round(price * cr * rng.uniform(0.9, 1.1), 2)
            rows.append(dict(product_id=f"PRD-{pid:05d}", sku=f"SKU{pid:06d}",
                             product_name=f"{brand} {sub} {rng.integers(100, 999)}",
                             category=cat, subcategory=sub, brand=brand,
                             list_price=price, unit_cost=cost, is_active=1,
                             valid_from="2023-06-01", popularity=rng.pareto(1.5) + 0.2))
            pid += 1
    df = pd.DataFrame(rows)
    return df


def campaigns(start: date, end: date) -> pd.DataFrame:
    rows = []
    for year in (2024, 2025):
        for q in range(4):
            qs = date(year, 3 * q + 1, 1)
            qe = date(year + (q == 3), (3 * q + 3) % 12 + 1, 1)
            qe = date.fromordinal(qe.toordinal() - 1)
            for ch in ["paid_search", "paid_social", "affiliate", "marketplace", "email"]:
                rows.append(dict(campaign_id=f"CMP-{CHANNEL_CODE[ch]}-{year}Q{q+1}",
                                 campaign_name=f"{CAMPAIGN_CHANNEL_LABEL[ch]} Always-On {year} Q{q+1}",
                                 channel=ch, objective="retention" if ch == "email" else "acquisition",
                                 first_order_discount_pct=0.0 if ch == "email" else 0.10,
                                 start_date=qs, end_date=qe))
    for year, (s, e) in {2024: (date(2024, 10, 1), date(2024, 11, 5)),
                         2025: (date(2025, 9, 20), date(2025, 10, 24))}.items():
        for ch in ["paid_search", "paid_social"]:
            rows.append(dict(campaign_id=f"CMP-{CHANNEL_CODE[ch]}-FEST{year}",
                             campaign_name=f"{CAMPAIGN_CHANNEL_LABEL[ch]} Festive Mega Sale {year}",
                             channel=ch, objective="acquisition", first_order_discount_pct=0.20,
                             start_date=s, end_date=e))
    rows.append(dict(campaign_id=S.S1_CAMPAIGN_ID, campaign_name="Meta Social Blitz - 40% off first order",
                     channel="paid_social", objective="acquisition", first_order_discount_pct=S.S1_DISCOUNT,
                     start_date=S.S1_START, end_date=S.S1_END))
    return pd.DataFrame(rows)
