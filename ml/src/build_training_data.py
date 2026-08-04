from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

AGE_BINS = [-np.inf, 7, 14, 30, 60, 90, 180, 365, np.inf]
AGE_LABELS = [
    "0_7",
    "8_14",
    "15_30",
    "31_60",
    "61_90",
    "91_180",
    "181_365",
    "366_plus",
]


def load_snapshots(db_path: Path) -> pd.DataFrame:
    query = """
    SELECT
        l.listing_id,
        l.snapshot_at,
        l.taxonomy_id,
        l.listing_type,
        l.listing_age_days,
        l.price,
        l.currency_code,
        l.quantity,
        l.num_favorers,
        l.tag_count,
        l.materials_count,
        l.title_length,
        l.is_customizable,
        l.is_personalizable,
        l.has_variations,
        l.is_supply,
        l.processing_min,
        l.processing_max,
        l.who_made,
        l.when_made,
        s.transaction_sold_count AS shop_transaction_sold_count,
        s.review_count AS shop_review_count,
        s.review_average AS shop_review_average,
        s.listing_active_count AS shop_listing_active_count,
        s.num_favorers AS shop_num_favorers
    FROM listing_snapshots AS l
    LEFT JOIN shop_snapshots AS s
      ON s.run_id = l.run_id AND s.shop_id = l.shop_id
    ORDER BY l.listing_id, l.snapshot_at
    """
    with sqlite3.connect(db_path) as connection:
        df = pd.read_sql_query(query, connection, parse_dates=["snapshot_at"])
    if df.empty:
        raise ValueError("No listing snapshots found in the database")
    return df


def create_pairs(
    snapshots: pd.DataFrame,
    *,
    horizon_days: int,
    tolerance_days: int,
) -> pd.DataFrame:
    pairs: list[dict[str, object]] = []
    minimum_days = horizon_days - tolerance_days
    maximum_days = horizon_days + tolerance_days

    for _, group in snapshots.groupby("listing_id", sort=False):
        group = group.sort_values("snapshot_at").reset_index(drop=True)
        chosen: dict[str, object] | None = None
        for base_index in range(len(group) - 1):
            base = group.iloc[base_index]
            future = group.iloc[base_index + 1 :].copy()
            future["observed_days"] = (
                future["snapshot_at"] - base["snapshot_at"]
            ).dt.total_seconds() / 86400.0
            future = future[
                future["observed_days"].between(minimum_days, maximum_days)
            ]
            if future.empty:
                continue
            nearest_index = (future["observed_days"] - horizon_days).abs().idxmin()
            target = future.loc[nearest_index]
            observed_days = float(target["observed_days"])
            favorite_growth = float(target["num_favorers"] - base["num_favorers"])
            chosen = base.to_dict()
            chosen["observed_days"] = observed_days
            chosen["favorite_growth"] = favorite_growth
            chosen["favorite_velocity"] = favorite_growth / max(observed_days, 1.0)
            break
        if chosen is not None:
            pairs.append(chosen)

    result = pd.DataFrame(pairs)
    if result.empty:
        raise ValueError(
            "No valid snapshot pairs found. Collect the same keyword/listings again "
            f"about {horizon_days} days later (tolerance ±{tolerance_days} days)."
        )
    return result


def add_percentile_labels(
    pairs: pd.DataFrame,
    *,
    winner_percentile: float,
    loser_percentile: float,
    minimum_group_size: int,
) -> pd.DataFrame:
    result = pairs.copy()
    result["category"] = result["taxonomy_id"].fillna(-1).astype(int).astype(str)
    result["age_bucket"] = pd.cut(
        result["listing_age_days"], bins=AGE_BINS, labels=AGE_LABELS
    ).astype(str)

    result["group_size"] = result.groupby(
        ["category", "age_bucket"], dropna=False
    )["listing_id"].transform("size")
    result["momentum_percentile"] = result.groupby(
        ["category", "age_bucket"], dropna=False
    )["favorite_velocity"].rank(method="average", pct=True)

    small_group = result["group_size"] < minimum_group_size
    category_size = result.groupby("category")["listing_id"].transform("size")
    category_rank = result.groupby("category")["favorite_velocity"].rank(
        method="average", pct=True
    )
    use_category = small_group & (category_size >= minimum_group_size)
    result.loc[use_category, "momentum_percentile"] = category_rank[use_category]

    global_rank = result["favorite_velocity"].rank(method="average", pct=True)
    still_small = small_group & ~use_category
    result.loc[still_small, "momentum_percentile"] = global_rank[still_small]

    result["winner_label"] = np.where(
        result["momentum_percentile"] >= winner_percentile,
        1,
        np.where(result["momentum_percentile"] <= loser_percentile, 0, -1),
    )
    return result


def build_dataset(
    db_path: Path,
    output_path: Path,
    diagnostics_path: Path,
    *,
    horizon_days: int,
    tolerance_days: int,
    winner_percentile: float,
    loser_percentile: float,
    minimum_group_size: int,
) -> dict[str, object]:
    snapshots = load_snapshots(db_path)
    pairs = create_pairs(
        snapshots, horizon_days=horizon_days, tolerance_days=tolerance_days
    )
    labeled = add_percentile_labels(
        pairs,
        winner_percentile=winner_percentile,
        loser_percentile=loser_percentile,
        minimum_group_size=minimum_group_size,
    )
    training = labeled[labeled["winner_label"].isin([0, 1])].copy()
    if training.empty or training["winner_label"].nunique() < 2:
        raise ValueError(
            "The labeled dataset does not contain both winners and losers. "
            "Collect more repeated snapshots before training."
        )

    selected_columns = [
        "listing_id",
        "snapshot_at",
        "category",
        "listing_type",
        "listing_age_days",
        "price",
        "currency_code",
        "quantity",
        "num_favorers",
        "tag_count",
        "materials_count",
        "title_length",
        "is_customizable",
        "is_personalizable",
        "has_variations",
        "is_supply",
        "processing_min",
        "processing_max",
        "who_made",
        "when_made",
        "shop_transaction_sold_count",
        "shop_review_count",
        "shop_review_average",
        "shop_listing_active_count",
        "shop_num_favorers",
        "winner_label",
    ]
    training = training[selected_columns].rename(
        columns={"snapshot_at": "snapshot_date"}
    )
    training["data_source"] = "etsy_public_api_favorite_momentum"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    training.to_csv(output_path, index=False)

    diagnostics: dict[str, object] = {
        "snapshot_rows": int(len(snapshots)),
        "paired_listings": int(len(pairs)),
        "training_rows": int(len(training)),
        "winner_rows": int((training["winner_label"] == 1).sum()),
        "loser_rows": int((training["winner_label"] == 0).sum()),
        "ambiguous_rows_excluded": int((labeled["winner_label"] == -1).sum()),
        "horizon_days": horizon_days,
        "tolerance_days": tolerance_days,
        "label_basis": "future favorite growth per observed day",
        "warning": (
            "Public Etsy listing data does not expose actual per-listing sales. "
            "These labels predict engagement momentum, not verified sales."
        ),
    }
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    return diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("ml/data/raw/etsy_snapshots.sqlite3"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ml/data/processed/etsy_momentum_training.csv"),
    )
    parser.add_argument(
        "--diagnostics",
        type=Path,
        default=Path("ml/data/processed/etsy_momentum_diagnostics.json"),
    )
    parser.add_argument("--horizon-days", type=int, default=14)
    parser.add_argument("--tolerance-days", type=int, default=4)
    parser.add_argument("--winner-percentile", type=float, default=0.80)
    parser.add_argument("--loser-percentile", type=float, default=0.40)
    parser.add_argument("--minimum-group-size", type=int, default=20)
    args = parser.parse_args()

    if args.horizon_days < 1:
        parser.error("--horizon-days must be positive")
    if not 0 <= args.tolerance_days < args.horizon_days:
        parser.error("--tolerance-days must be >= 0 and less than the horizon")
    if not 0 < args.loser_percentile < args.winner_percentile < 1:
        parser.error("Percentiles must satisfy 0 < loser < winner < 1")

    diagnostics = build_dataset(
        args.db,
        args.output,
        args.diagnostics,
        horizon_days=args.horizon_days,
        tolerance_days=args.tolerance_days,
        winner_percentile=args.winner_percentile,
        loser_percentile=args.loser_percentile,
        minimum_group_size=args.minimum_group_size,
    )
    print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    main()
