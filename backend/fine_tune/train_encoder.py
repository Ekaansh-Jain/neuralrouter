"""Train a small, CPU-servable complexity classifier (v2).

Why not QLoRA on Llama 3 8B? Because there is no free way to SERVE custom 8B
weights with acceptable latency, and a complexity label is a short-text
classification task -- it does not need a generative model. A TF-IDF +
LogisticRegression model trains in seconds, runs on CPU (so it deploys on the
same Railway box), and slots behind the existing `Classifier` protocol.

(QLoRA distillation of a generative router is kept as documented future work in
notebooks/qlora_future_work.ipynb.)

Requires: scikit-learn, joblib  (see fine_tune/requirements.txt)
Run:  python train_encoder.py classifier_dataset.jsonl
"""

from __future__ import annotations

import json
import sys


def load(path: str) -> tuple[list[str], list[str]]:
    texts, labels = [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            texts.append(row["text"])
            labels.append(row["label"])
    return texts, labels


def main(path: str) -> None:  # pragma: no cover - requires scikit-learn
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline

    texts, labels = load(path)
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2)),
        ("clf", LogisticRegression(max_iter=1000)),
    ])
    model.fit(x_train, y_train)
    print(classification_report(y_test, model.predict(x_test)))
    joblib.dump(model, "classifier_v2.joblib")
    print("saved classifier_v2.joblib -- load it behind a TfidfClassifier(Classifier)")


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) != 2:
        print("usage: python train_encoder.py <dataset.jsonl>")
        raise SystemExit(1)
    main(sys.argv[1])
