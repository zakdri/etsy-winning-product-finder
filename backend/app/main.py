from __future__ import annotations

import html
import math
from datetime import datetime, timezone
from statistics import median
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from ml.src.etsy_client import EtsyAPIError, EtsyClient


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ResearchRequest(APIModel):
    keyword: str = Field(min_length=2, max_length=120)
    limit: int = Field(default=100, ge=1, le=100)
    enrich_shops: bool = True
    max_shop_lookups: int = Field(default=100, ge=0, le=100)
    sort_on: Literal["created", "score", "price", "updated"] = "created"
    sort_order: Literal["asc", "desc"] = "desc"


class ScoreBreakdown(APIModel):
    momentum: float
    freshness: float
    demand: float
    seo: float
    shop_validation: float
    price_fit: float


class ListingResult(APIModel):
    listing_id: int
    title: str
    url: str
    image_url: str | None
    shop_id: int | None
    taxonomy_id: int | None
    price: float | None
    currency_code: str | None
    listing_age_days: float | None
    num_favorers: int
    tag_count: int
    result_rank: int
    shop_sales: int | None
    shop_review_count: int | None
    opportunity_score: int
    data_confidence: int
    score_label: Literal["High potential", "Promising", "Watch", "Low signal"]
    score_breakdown: ScoreBreakdown


class ResearchResponse(APIModel):
    keyword: str
    generated_at: str
    source: Literal["etsy_official_api"] = "etsy_official_api"
    result_count: int
    auth_mode: Literal["api_key", "oauth"]
    warnings: list[str]
    items: list[ListingResult]


app = FastAPI(
    title="TrendScout Local API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
    allow_credentials=False,
)


def optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def money(value: Any) -> tuple[float | None, str | None]:
    if not isinstance(value, dict):
        return None, None
    try:
        amount = float(value.get("amount"))
        divisor = float(value.get("divisor") or 1)
        return amount / divisor, value.get("currency_code")
    except (TypeError, ValueError, ZeroDivisionError):
        return None, value.get("currency_code")


def listing_age_days(listing: dict[str, Any]) -> float | None:
    created = (
        listing.get("original_creation_timestamp")
        or listing.get("created_timestamp")
        or listing.get("creation_timestamp")
    )
    try:
        return max(0.0, (datetime.now(timezone.utc).timestamp() - float(created)) / 86400)
    except (TypeError, ValueError):
        return None


def first_image(listing: dict[str, Any]) -> str | None:
    images = listing.get("images") or listing.get("Images") or []
    if not isinstance(images, list) or not images:
        return None
    image = images[0]
    if not isinstance(image, dict):
        return None
    for key in ("url_570xN", "url_300x300", "url_fullxfull", "url_170x135"):
        if image.get(key):
            return str(image[key])
    return None


def bounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def score_listing(
    *,
    favorers: int,
    age_days: float | None,
    tag_count: int,
    result_rank: int,
    price: float | None,
    median_price: float | None,
    shop_sales: int | None,
    shop_review_count: int | None,
    has_image: bool,
) -> tuple[int, int, str, ScoreBreakdown]:
    effective_age = max(age_days or 365.0, 1.0)
    favorite_velocity = favorers / max(effective_age, 7.0) * 30.0
    momentum = bounded(100 * (1 - math.exp(-favorite_velocity / 8.0)))
    freshness = bounded(100 * math.exp(-effective_age / 170.0))
    demand = bounded(100 * (1 - math.exp(-favorers / 75.0)))
    seo = bounded((min(tag_count, 13) / 13) * 100)
    shop_validation = bounded(100 * (1 - math.exp(-(shop_sales or 0) / 1800.0))) if shop_sales is not None else 42.0
    if price is None or not median_price or median_price <= 0:
        price_fit = 50.0
    else:
        distance = abs(math.log(max(price, 0.01) / median_price))
        price_fit = bounded(100 * math.exp(-distance / 0.8))

    visibility = bounded(100 - max(0, result_rank - 1) * 0.65)
    opportunity = round(
        momentum * 0.27
        + freshness * 0.24
        + demand * 0.15
        + seo * 0.12
        + shop_validation * 0.10
        + price_fit * 0.07
        + visibility * 0.05
    )

    completeness = [
        age_days is not None,
        price is not None,
        tag_count > 0,
        has_image,
        shop_sales is not None,
        shop_review_count is not None,
    ]
    confidence = round(52 + sum(completeness) / len(completeness) * 43)
    label = (
        "High potential"
        if opportunity >= 75
        else "Promising"
        if opportunity >= 60
        else "Watch"
        if opportunity >= 45
        else "Low signal"
    )
    return opportunity, confidence, label, ScoreBreakdown(
        momentum=momentum,
        freshness=freshness,
        demand=demand,
        seo=seo,
        shop_validation=shop_validation,
        price_fit=price_fit,
    )


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    try:
        client = EtsyClient.from_env()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "status": "ok",
        "service": "TrendScout Local API",
        "version": "0.1.0",
        "authMode": client.auth_mode,
    }


@app.post("/api/v1/research", response_model=ResearchResponse)
def research(request: ResearchRequest) -> ResearchResponse:
    try:
        client = EtsyClient.from_env()
        payload = client.find_active_listings(
            keywords=request.keyword.strip(),
            limit=request.limit,
            offset=0,
            sort_on=request.sort_on,
            sort_order=request.sort_order,
            include_images=True,
        )
    except (RuntimeError, EtsyAPIError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    raw_items = payload.get("results") or []
    if not isinstance(raw_items, list):
        raw_items = []

    shop_ids = {
        shop_id
        for item in raw_items
        if isinstance(item, dict)
        and (shop_id := optional_int(item.get("shop_id"))) is not None
    }
    shops: dict[int, dict[str, Any]] = {}
    warnings = [
        "Opportunity scores are transparent research signals, not verified future sales predictions.",
        "Public marketplace search is currently limited to the first 100 results per keyword for this API access mode.",
    ]

    if request.enrich_shops:
        for shop_id in sorted(shop_ids)[: request.max_shop_lookups]:
            try:
                shop = client.get_shop(shop_id)
                if isinstance(shop, dict):
                    shops[shop_id] = shop
            except EtsyAPIError:
                continue
        if len(shops) < min(len(shop_ids), request.max_shop_lookups):
            warnings.append("Some shop metrics could not be enriched; confidence is reduced for those listings.")

    normalized: list[dict[str, Any]] = []
    prices: list[float] = []
    for rank, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict) or optional_int(item.get("listing_id")) is None:
            continue
        price, currency = money(item.get("converted_price") or item.get("price"))
        if price is not None and price > 0:
            prices.append(price)
        normalized.append(
            {
                "listing": item,
                "rank": rank,
                "price": price,
                "currency": currency,
                "age": listing_age_days(item),
            }
        )

    median_price = median(prices) if prices else None
    results: list[ListingResult] = []
    for record in normalized:
        item = record["listing"]
        shop_id = optional_int(item.get("shop_id"))
        shop = shops.get(shop_id or -1, {})
        image_url = first_image(item)
        favorers = optional_int(item.get("num_favorers")) or 0
        tags = item.get("tags") or []
        tag_count = len(tags) if isinstance(tags, list) else 0
        shop_sales = optional_int(shop.get("transaction_sold_count"))
        shop_reviews = optional_int(shop.get("review_count"))
        opportunity, confidence, label, breakdown = score_listing(
            favorers=favorers,
            age_days=record["age"],
            tag_count=tag_count,
            result_rank=record["rank"],
            price=record["price"],
            median_price=median_price,
            shop_sales=shop_sales,
            shop_review_count=shop_reviews,
            has_image=image_url is not None,
        )
        results.append(
            ListingResult(
                listing_id=int(item["listing_id"]),
                title=html.unescape(str(item.get("title") or "Untitled listing")),
                url=str(item.get("url") or f"https://www.etsy.com/listing/{item['listing_id']}"),
                image_url=image_url,
                shop_id=shop_id,
                taxonomy_id=optional_int(item.get("taxonomy_id")),
                price=record["price"],
                currency_code=record["currency"],
                listing_age_days=round(record["age"], 2) if record["age"] is not None else None,
                num_favorers=favorers,
                tag_count=tag_count,
                result_rank=record["rank"],
                shop_sales=shop_sales,
                shop_review_count=shop_reviews,
                opportunity_score=opportunity,
                data_confidence=confidence,
                score_label=label,
                score_breakdown=breakdown,
            )
        )

    return ResearchResponse(
        keyword=request.keyword.strip(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        result_count=len(results),
        auth_mode=client.auth_mode,
        warnings=warnings,
        items=results,
    )
