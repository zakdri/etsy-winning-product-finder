# Etsy Winning Product Finder

Research tooling for identifying promising Etsy listings using authorized Etsy API data and time-based machine-learning features.

> The term “Etsy” is a trademark of Etsy, Inc. This application uses the Etsy API but is not endorsed or certified by Etsy, Inc.

## ML baseline

The first pipeline validates the dataset schema and training workflow with synthetic demo rows. Synthetic results are not evidence that the model can predict real marketplace winners.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r ml/requirements.txt
python ml/src/generate_demo_data.py --rows 3000
python ml/src/train.py
```

Generated model files and datasets are ignored by Git. Never commit Etsy API keys, OAuth tokens, shared secrets, raw seller data, or model artifacts containing private data.

## Real training protocol

1. Collect authorized API snapshots at consistent intervals.
2. Keep only features available at each snapshot date.
3. After the observation window, label the top 20% of category-and-age-adjusted sales velocity as winners and the bottom 40% as losers.
4. Exclude ambiguous middle examples from training.
5. Split training and evaluation chronologically rather than randomly.
6. Report ROC-AUC, average precision, precision at the top-ranked products, and calibration.

Development work is added through pull requests.
