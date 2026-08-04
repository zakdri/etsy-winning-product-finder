from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etsy_client import EtsyClient
from snapshot_store import SnapshotStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_to_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def money_to_float(value: Any) -> tuple[float | None, str | None]:
    if not isinstance(value, dict):
        return None, None
    amount = value.get("amount")
    divisor = value.get("divisor") or 1
    try:
        price = float(amount) / float(divisor)
    except (TypeError, ValueError, ZeroDivisionError):
        price = None
    currency = value.get("currency_code")
    return price, str(currency) if currency else None


def optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def boolean_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(bool(value))


def normalize_listing(
    listing: dict[str, Any],
    *,
    run_id: str,
    snapshot_at: datetime,
    keyword: str,
    result_rank: int,
) -> dict[str, Any]:
    created_epoch = (
        listing.get("original_creation_timestamp")
        or listing.get("created_timestamp")
        or listing.get("creation_timestamp")
    )
    created_at = timestamp_to_iso(created_epoch)
    updated_at = timestamp_to_iso(
        listing.get("updated_timestamp") or listing.get("last_modified_timestamp")
    )
    age_days: float | None = None
    if created_epoch:
        try:
            age_days = max(
                0.0,
                (snapshot_at.timestamp() - float(created_epoch)) / 86400.0,
            )
        except (TypeError, ValueError):
            pass

    price, currency_code = money_to_float(
        listing.get("converted_price") or listing.get("price")
    )
    title = listing.get("title") or ""
    tags = listing.get("tags") or []
    materials = listing.get("materials") or []

    return {
        "run_id": run_id,
        "listing_id": int(listing["listing_id"]),
        "snapshot_at": snapshot_at.isoformat(),
        "keyword": keyword,
        "result_rank": result_rank,
        "shop_id": optional_int(listing.get("shop_id")),
        "taxonomy_id": optional_int(listing.get("taxonomy_id")),
        "state": listing.get("state"),
        "listing_type": listing.get("listing_type"),
        "listing_url": listing.get("url"),
        "created_at": created_at,
        "updated_at": updated_at,
        "listing_age_days": age_days,
        "price": price,
        "currency_code": currency_code,
        "quantity": optional_int(listing.get("quantity")),
        "num_favorers": optional_int(listing.get("num_favorers")) or 0,
        "tag_count": len(tags) if isinstance(tags, list) else 0,
        "materials_count": len(materials) if isinstance(materials, list) else 0,
        "title_length": len(str(title)),
        "is_customizable": boolean_int(listing.get("is_customizable")),
        "is_personalizable": boolean_int(listing.get("is_personalizable")),
        "has_variations": boolean_int(listing.get("has_variations")),
        "is_supply": boolean_int(listing.get("is_supply")),
        "processing_min": optional_int(listing.get("processing_min")),
        "processing_max": optional_int(listing.get("processing_max")),
        "who_made": listing.get("who_made"),
        "when_made": listing.get("when_made"),
    }


def normalize_shop(
    shop: dict[str, Any],
    *,
    run_id: str,
    snapshot_at: datetime,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "shop_id": int(shop["shop_id"]),
        "snapshot_at": snapshot_at.isoformat(),
        "transaction_sold_count": optional_int(shop.get("transaction_sold_count")),
        "review_count": optional_int(shop.get("review_count")),
        "review_average": (
            float(shop["review_average"])
            if shop.get("review_average") is not None
            else None
        ),
        "listing_active_count": optional_int(shop.get("listing_active_count")),
        "digital_listing_count": optional_int(shop.get("digital_listing_count")),
        "num_favorers": optional_int(shop.get("num_favorers")),
    }


def collect(args: argparse.Namespace) -> dict[str, Any]:
    client = EtsyClient.from_env()
    run_id = str(uuid.uuid4())
    started_at = utc_now()
    collected_count = 0
    unique_shop_ids: set[int] = set()

    with SnapshotStore(args.db) as store:
        store.start_run(
            {
                "run_id": run_id,
                "started_at": started_at.isoformat(),
                "keyword": args.keyword,
                "requested_pages": args.pages,
                "page_size": args.page_size,
                "sort_on": args.sort_on,
                "sort_order": args.sort_order,
            }
        )
        try:
            for page_index in range(args.pages):
                offset = page_index * args.page_size
                if offset > 12000:
                    break

                payload = client.find_active_listings(
                    keywords=args.keyword,
                    limit=args.page_size,
                    offset=offset,
                    sort_on=args.sort_on,
                    sort_order=args.sort_order,
                )
                results = payload.get("results") or []
                if not isinstance(results, list) or not results:
                    break

                snapshot_at = utc_now()
                normalized = []
                for item_index, listing in enumerate(results):
                    if not isinstance(listing, dict) or "listing_id" not in listing:
                        continue
                    row = normalize_listing(
                        listing,
                        run_id=run_id,
                        snapshot_at=snapshot_at,
                        keyword=args.keyword,
                        result_rank=offset + item_index + 1,
                    )
                    normalized.append(row)
                    if row["shop_id"]:
                        unique_shop_ids.add(int(row["shop_id"]))

                collected_count += store.insert_listings(normalized)
                total_count = optional_int(payload.get("count"))
                if total_count is not None and offset + len(results) >= total_count:
                    break

            enriched_shops = 0
            if args.enrich_shops:
                for shop_id in sorted(unique_shop_ids)[: args.max_shop_lookups]:
                    shop = client.get_shop(shop_id)
                    if not isinstance(shop, dict) or "shop_id" not in shop:
                        continue
                    store.insert_shop(
                        normalize_shop(shop, run_id=run_id, snapshot_at=utc_now())
                    )
                    enriched_shops += 1

            finished_at = utc_now()
            store.finish_run(
                run_id,
                status="completed",
                collected_count=collected_count,
                finished_at=finished_at.isoformat(),
                rate_limit_json=json.dumps(client.last_rate_limits),
            )
            return {
                "run_id": run_id,
                "keyword": args.keyword,
                "listings_collected": collected_count,
                "shops_enriched": enriched_shops,
                "database": str(args.db),
                "rate_limits": client.last_rate_limits,
            }
        except Exception as exc:
            store.finish_run(
                run_id,
                status="failed",
                collected_count=collected_count,
                finished_at=utc_now().isoformat(),
                error=str(exc)[:2000],
                rate_limit_json=json.dumps(client.last_rate_limits),
            )
            raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect derived snapshots from Etsy's official Open API."
    )
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("ml/data/raw/etsy_snapshots.sqlite3"),
    )
    parser.add_argument(
        "--sort-on",
        choices=["created", "price", "updated", "score"],
        default="created",
    )
    parser.add_argument(
        "--sort-order",
        choices=["asc", "ascending", "desc", "descending", "up", "down"],
        default="desc",
    )
    parser.add_argument("--enrich-shops", action="store_true")
    parser.add_argument("--max-shop-lookups", type=int, default=250)
    args = parser.parse_args()

    if args.pages < 1:
        parser.error("--pages must be at least 1")
    if not 1 <= args.page_size <= 100:
        parser.error("--page-size must be between 1 and 100")
    if args.max_shop_lookups < 0:
        parser.error("--max-shop-lookups cannot be negative")

    print(json.dumps(collect(args), indent=2))


if __name__ == "__main__":
    main()
