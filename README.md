# Etsy Winning Product Finder

Research tooling for identifying promising Etsy listings using authorized Etsy Open API data and time-based machine-learning features.

> The term “Etsy” is a trademark of Etsy, Inc. This application uses the Etsy API but is not endorsed or certified by Etsy, Inc.

## Security first

The API credentials previously visible in a screenshot must be rotated before use. Never commit Etsy API keys, shared secrets, OAuth tokens, seller data, databases, or model artifacts.

```bat
copy .env.example .env
```

Open `.env` locally and add the **rotated** keystring and shared secret. The real `.env` file is ignored by Git.

## Install

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r ml/requirements.txt
```

## Collect the first real snapshot

This collector uses Etsy's official public active-listings endpoint, stores derived fields in SQLite, respects pagination limits, paces requests, records quota headers, and retries `429`/temporary server responses.

```bat
python ml/src/collect_snapshots.py --keyword "vintage horse wall art" --pages 3 --page-size 100 --enrich-shops --max-shop-lookups 150
```

The database is created at:

```text
ml/data/raw/etsy_snapshots.sqlite3
```

Run the same command for several niches. Keep each keyword consistent so the same listings can be observed again.

## Collect the follow-up snapshot

Run the same collection commands again around 14 days later. A single collection cannot produce a valid future-performance label.

```bat
python ml/src/collect_snapshots.py --keyword "vintage horse wall art" --pages 3 --page-size 100 --enrich-shops --max-shop-lookups 150
```

For stronger data, collect daily or every 2–3 days for at least 60–90 days.

## Build real labels

The public Etsy API does **not** expose verified per-listing competitor sales. The first real dataset therefore labels products by future favorite-growth velocity, adjusted by taxonomy and listing-age bucket. It predicts engagement momentum, not guaranteed sales.

```bat
python ml/src/build_training_data.py --horizon-days 14 --tolerance-days 4
```

Generated files:

```text
ml/data/processed/etsy_momentum_training.csv
ml/data/processed/etsy_momentum_diagnostics.json
```

The top 20% of future favorite velocity are labeled winners, the bottom 40% are labeled losers, and ambiguous middle rows are excluded.

## Train the real momentum model

```bat
python ml/src/train.py --input ml/data/processed/etsy_momentum_training.csv --model ml/models/etsy_momentum_classifier.joblib --metrics ml/models/etsy_momentum_metrics.json
```

The trainer uses chronological splitting and supports mixed categorical/numeric Etsy fields.

## Synthetic smoke test

Synthetic rows only verify that the code runs. They are not evidence of marketplace accuracy.

```bat
python ml/src/generate_demo_data.py --rows 3000
python ml/src/train.py
```

## Real sales model later

A verified sales model requires seller-authorized transaction or receipt data, normally from participating shops that explicitly grant the required OAuth scopes. Public competitor listing snapshots should not be presented as verified sales counts.

## Data protocol

1. Collect authorized API snapshots at consistent intervals.
2. Keep only features available at each snapshot date.
3. Label outcomes using a later observation window.
4. Compare products inside similar taxonomy and listing-age groups.
5. Exclude ambiguous middle examples.
6. Split training and evaluation chronologically.
7. Report ROC-AUC, average precision, top-ranked precision, and calibration.

Development work is added through pull requests.
