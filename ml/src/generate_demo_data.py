from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def build_demo_dataset(rows: int, seed: int = 42) -> pd.DataFrame:
    """Create synthetic data only for validating the training pipeline.

    These rows must never be treated as real Etsy market observations.
    """
    if rows < 200:
        raise ValueError("rows must be at least 200")

    rng = np.random.default_rng(seed)
    categories = np.array([
        "digital_wall_art",
        "wedding_template",
        "svg_bundle",
        "personalized_gift",
    ])

    listing_age_days = rng.integers(1, 366, rows)
    favorites_7d = rng.poisson(8, rows)
    reviews_30d = rng.poisson(3, rows)
    estimated_sales_7d = rng.poisson(5, rows)
    competition_count = rng.integers(100, 50000, rows)
    image_count = rng.integers(1, 11, rows)
    tag_count = rng.integers(4, 14, rows)
    has_video = rng.integers(0, 2, rows)
    price_usd = np.round(rng.uniform(2.0, 80.0, rows), 2)
    trend_growth_14d = rng.normal(0.05, 0.35, rows)
    shop_total_sales = rng.integers(0, 100000, rows)

    raw_signal = (
        estimated_sales_7d * 0.34
        + favorites_7d * 0.12
        + reviews_30d * 0.18
        + trend_growth_14d * 2.2
        + has_video * 0.3
        + tag_count * 0.03
        - np.log1p(competition_count) * 0.18
        - np.maximum(listing_age_days - 90, 0) * 0.003
        + rng.normal(0, 0.8, rows)
    )

    threshold = np.quantile(raw_signal, 0.80)
    labels = (raw_signal >= threshold).astype(int)

    return pd.DataFrame(
        {
            "listing_id": [f"synthetic_{i:06d}" for i in range(rows)],
            "snapshot_date": pd.Timestamp("2026-01-01")
            + pd.to_timedelta(rng.integers(0, 210, rows), unit="D"),
            "category": rng.choice(categories, rows),
            "listing_age_days": listing_age_days,
            "price_usd": price_usd,
            "favorites_previous_7d": favorites_7d,
            "reviews_previous_30d": reviews_30d,
            "estimated_sales_previous_7d": estimated_sales_7d,
            "competition_count": competition_count,
            "image_count": image_count,
            "has_video": has_video,
            "tag_count": tag_count,
            "trend_growth_14d": trend_growth_14d.round(4),
            "shop_total_sales": shop_total_sales,
            "winner_label": labels,
            "data_source": "synthetic_demo_only",
        }
    ).sort_values("snapshot_date")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=3000)
    parser.add_argument("--output", type=Path, default=Path("ml/data/processed/demo_training.csv"))
    args = parser.parse_args()

    dataset = build_demo_dataset(args.rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(args.output, index=False)
    print(f"Wrote {len(dataset)} synthetic demo rows to {args.output}")


if __name__ == "__main__":
    main()
