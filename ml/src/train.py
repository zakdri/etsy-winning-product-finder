from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, classification_report, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

TARGET = "winner_label"
EXCLUDED = {"listing_id", "snapshot_date", TARGET, "data_source"}


def train(input_path: Path, model_path: Path, metrics_path: Path) -> dict[str, float]:
    df = pd.read_csv(input_path, parse_dates=["snapshot_date"])
    if TARGET not in df.columns:
        raise ValueError(f"Missing required target column: {TARGET}")
    if df[TARGET].nunique() < 2:
        raise ValueError("Training data must contain both winner and loser labels")

    df = df.sort_values("snapshot_date").reset_index(drop=True)
    split_index = int(len(df) * 0.8)
    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()
    if train_df[TARGET].nunique() < 2 or test_df[TARGET].nunique() < 2:
        raise ValueError(
            "Chronological train/test partitions must each contain winners and losers. "
            "Collect more real snapshots or use a longer date range."
        )

    features = [column for column in df.columns if column not in EXCLUDED]
    categorical = [
        column
        for column in features
        if pd.api.types.is_object_dtype(df[column])
        or isinstance(df[column].dtype, pd.CategoricalDtype)
        or pd.api.types.is_string_dtype(df[column])
    ]
    numeric = [column for column in features if column not in categorical]

    for frame in (train_df, test_df):
        for column in categorical:
            frame[column] = frame[column].fillna("__missing__").astype(str)

    transformers = []
    if categorical:
        transformers.append(
            (
                "categorical",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value", unknown_value=-1
                ),
                categorical,
            )
        )
    if numeric:
        transformers.append(("numeric", "passthrough", numeric))
    if not transformers:
        raise ValueError("No model features remain after exclusions")

    preprocessor = ColumnTransformer(transformers)
    pipeline = Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "classifier",
                HistGradientBoostingClassifier(
                    learning_rate=0.05,
                    max_iter=250,
                    max_leaf_nodes=15,
                    min_samples_leaf=20,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )

    pipeline.fit(train_df[features], train_df[TARGET])
    probabilities = pipeline.predict_proba(test_df[features])[:, 1]
    predictions = (probabilities >= 0.5).astype(int)

    metrics = {
        "rows": float(len(df)),
        "train_rows": float(len(train_df)),
        "test_rows": float(len(test_df)),
        "winner_rate": float(df[TARGET].mean()),
        "roc_auc": float(roc_auc_score(test_df[TARGET], probabilities)),
        "average_precision": float(
            average_precision_score(test_df[TARGET], probabilities)
        ),
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipeline,
            "features": features,
            "categorical_features": categorical,
            "numeric_features": numeric,
        },
        model_path,
    )
    metrics_path.write_text(
        json.dumps(
            {
                "summary": metrics,
                "classification_report": classification_report(
                    test_df[TARGET], predictions, output_dict=True
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("ml/data/processed/demo_training.csv"),
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("ml/models/winner_classifier.joblib"),
    )
    parser.add_argument(
        "--metrics", type=Path, default=Path("ml/models/metrics.json")
    )
    args = parser.parse_args()

    metrics = train(args.input, args.model, args.metrics)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
