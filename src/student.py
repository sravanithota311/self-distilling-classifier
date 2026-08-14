"""The student: a lightweight, fast model that learns to imitate the teacher.

TF-IDF + Logistic Regression keeps this dependency-light and CI-friendly
(no model downloads). Swap in sentence-embeddings later for an easy upgrade —
see the README's "Upgrade paths" section.
"""
from __future__ import annotations

import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


def train_student(texts: list[str], labels: list[int]) -> Pipeline:
    """Fit a fresh student on teacher-labeled data."""
    model = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2),
                                  stop_words="english")),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    model.fit(texts, labels)
    return model


def agreement(model: Pipeline, texts: list[str], teacher_labels: list[int]) -> float:
    """Fraction of predictions that match the teacher (student–teacher agreement)."""
    if not texts:
        return 0.0
    preds = model.predict(texts)
    correct = sum(int(p == t) for p, t in zip(preds, teacher_labels))
    return correct / len(texts)


def save(model: Pipeline, path: str) -> None:
    with open(path, "wb") as f:
        pickle.dump(model, f)


def load(path: str) -> Pipeline:
    with open(path, "rb") as f:
        return pickle.load(f)
