from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS collection_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    keyword TEXT NOT NULL,
    requested_pages INTEGER NOT NULL,
    page_size INTEGER NOT NULL,
    sort_on TEXT NOT NULL,
    sort_order TEXT NOT NULL,
    status TEXT NOT NULL,
    collected_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    rate_limit_json TEXT
);

CREATE TABLE IF NOT EXISTS listing_snapshots (
    run_id TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    snapshot_at TEXT NOT NULL,
    keyword TEXT NOT NULL,
    result_rank INTEGER NOT NULL,
    shop_id INTEGER,
    taxonomy_id INTEGER,
    state TEXT,
    listing_type TEXT,
    listing_url TEXT,
    created_at TEXT,
    updated_at TEXT,
    listing_age_days REAL,
    price REAL,
    currency_code TEXT,
    quantity INTEGER,
    num_favorers INTEGER,
    tag_count INTEGER,
    materials_count INTEGER,
    title_length INTEGER,
    is_customizable INTEGER,
    is_personalizable INTEGER,
    has_variations INTEGER,
    is_supply INTEGER,
    processing_min INTEGER,
    processing_max INTEGER,
    who_made TEXT,
    when_made TEXT,
    PRIMARY KEY (run_id, listing_id),
    FOREIGN KEY (run_id) REFERENCES collection_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_listing_snapshots_listing_date
ON listing_snapshots(listing_id, snapshot_at);

CREATE INDEX IF NOT EXISTS idx_listing_snapshots_taxonomy_age
ON listing_snapshots(taxonomy_id, listing_age_days);

CREATE TABLE IF NOT EXISTS shop_snapshots (
    run_id TEXT NOT NULL,
    shop_id INTEGER NOT NULL,
    snapshot_at TEXT NOT NULL,
    transaction_sold_count INTEGER,
    review_count INTEGER,
    review_average REAL,
    listing_active_count INTEGER,
    digital_listing_count INTEGER,
    num_favorers INTEGER,
    PRIMARY KEY (run_id, shop_id),
    FOREIGN KEY (run_id) REFERENCES collection_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_shop_snapshots_shop_date
ON shop_snapshots(shop_id, snapshot_at);
"""


class SnapshotStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SnapshotStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def start_run(self, row: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT INTO collection_runs (
                run_id, started_at, keyword, requested_pages, page_size,
                sort_on, sort_order, status
            ) VALUES (
                :run_id, :started_at, :keyword, :requested_pages, :page_size,
                :sort_on, :sort_order, 'running'
            )
            """,
            row,
        )
        self.connection.commit()

    def insert_listings(self, rows: Iterable[dict[str, Any]]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        self.connection.executemany(
            """
            INSERT OR REPLACE INTO listing_snapshots (
                run_id, listing_id, snapshot_at, keyword, result_rank,
                shop_id, taxonomy_id, state, listing_type, listing_url,
                created_at, updated_at, listing_age_days, price, currency_code,
                quantity, num_favorers, tag_count, materials_count, title_length,
                is_customizable, is_personalizable, has_variations, is_supply,
                processing_min, processing_max, who_made, when_made
            ) VALUES (
                :run_id, :listing_id, :snapshot_at, :keyword, :result_rank,
                :shop_id, :taxonomy_id, :state, :listing_type, :listing_url,
                :created_at, :updated_at, :listing_age_days, :price, :currency_code,
                :quantity, :num_favorers, :tag_count, :materials_count, :title_length,
                :is_customizable, :is_personalizable, :has_variations, :is_supply,
                :processing_min, :processing_max, :who_made, :when_made
            )
            """,
            rows,
        )
        self.connection.commit()
        return len(rows)

    def insert_shop(self, row: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO shop_snapshots (
                run_id, shop_id, snapshot_at, transaction_sold_count,
                review_count, review_average, listing_active_count,
                digital_listing_count, num_favorers
            ) VALUES (
                :run_id, :shop_id, :snapshot_at, :transaction_sold_count,
                :review_count, :review_average, :listing_active_count,
                :digital_listing_count, :num_favorers
            )
            """,
            row,
        )
        self.connection.commit()

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        collected_count: int,
        finished_at: str,
        error: str | None = None,
        rate_limit_json: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE collection_runs
            SET status = ?, collected_count = ?, finished_at = ?,
                error = ?, rate_limit_json = ?
            WHERE run_id = ?
            """,
            (
                status,
                collected_count,
                finished_at,
                error,
                rate_limit_json,
                run_id,
            ),
        )
        self.connection.commit()
