"""One run of the self-distilling loop.

  fetch -> teacher labels -> train challenger -> evaluate agreement
  -> drift check -> promote if better -> Claude writes the report

State lives in plain files that get committed each run, so the GitHub
Actions history *is* the training history:

  data/labeled.jsonl        every teacher-labeled paper we've seen
  models/production.pkl      current champion student
  models/metrics_history.json  one row per run
  reports/report_<ts>.md     the human-readable changelog
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import yaml

# allow running as `python src/run_pipeline.py` or `python -m src.run_pipeline`
try:
    from . import fetch_data, label_teacher, student, drift, report
except ImportError:
    import fetch_data, label_teacher, student, drift, report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "labeled.jsonl")
PROD = os.path.join(ROOT, "models", "production.pkl")
HIST = os.path.join(ROOT, "models", "metrics_history.json")
REPORTS = os.path.join(ROOT, "reports")


def _load_labeled() -> list[dict]:
    if not os.path.exists(DATA):
        return []
    with open(DATA) as f:
        return [json.loads(line) for line in f if line.strip()]


def _append_labeled(rows: list[dict]) -> None:
    with open(DATA, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _load_history() -> list[dict]:
    if not os.path.exists(HIST):
        return []
    with open(HIST) as f:
        return json.load(f)


def main(mock: bool = False) -> None:
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config.yaml")))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("\n" + "=" * 60)
    print(f"  SELF-DISTILLING RUN  ·  {ts}")
    print("=" * 60)

    # 1. FETCH new, unseen abstracts
    labeled = _load_labeled()
    seen = {r["id"] for r in labeled}
    print(f"\n[1/6] FETCH  · asking arXiv for the latest '{cfg['arxiv_category']}' papers...")
    fresh = fetch_data.fetch_recent(cfg["arxiv_category"], cfg["batch_size"], seen)
    if not fresh:
        print("      No new papers this run — nothing to do.")
        return
    print(f"      Got {len(fresh)} new papers not seen before.")
    print(f"      e.g. \"{fresh[0]['title'][:70]}...\"")

    # 2. TEACHER labels the batch
    teacher_name = "keyword heuristic (mock)" if (mock or not os.environ.get("GEMINI_API_KEY")) \
        else cfg["teacher_model"]
    print(f"\n[2/6] LABEL  · teacher = {teacher_name}")
    print(f"      labeling {len(fresh)} papers (yes/no)...")
    labels = label_teacher.label_batch(
        fresh, cfg["task_question"], cfg["teacher_model"], mock=mock)
    new_rows = [{"id": p["id"], "text": p["text"], "label": labels[p["id"]],
                 "run": ts} for p in fresh]
    positive_rate = sum(r["label"] for r in new_rows) / len(new_rows)
    print(f"      teacher said 'yes' to {positive_rate:.0%} of them.")

    # This newest batch is our held-out test set; everything prior is train.
    train = labeled
    test = new_rows

    # 3. TRAIN challenger (needs both classes present to be meaningful)
    train_labels = [r["label"] for r in train]
    can_train = len(train) >= 20 and len(set(train_labels)) == 2
    champion = student.load(PROD) if os.path.exists(PROD) else None

    challenger_agr = champion_agr = 0.0
    promoted = False

    print(f"\n[3/6] TRAIN  · student on {len(train)} labeled papers"
          f" (testing on {len(test)} newest)")
    if can_train:
        challenger = student.train_student(
            [r["text"] for r in train], train_labels)
        challenger_agr = student.agreement(
            challenger, [r["text"] for r in test], [r["label"] for r in test])
        print(f"      challenger agrees with teacher: {challenger_agr:.1%}")
        if champion is not None:
            champion_agr = student.agreement(
                champion, [r["text"] for r in test], [r["label"] for r in test])
            print(f"      current champion agrees:       {champion_agr:.1%}")
        # 4. PROMOTE only if the challenger beats the champion
        print(f"\n[4/6] PROMOTE · champion vs challenger")
        if champion is None or challenger_agr >= champion_agr + cfg["promotion_margin"]:
            student.save(challenger, PROD)
            promoted = True
            print(f"      challenger wins → PROMOTED as new champion.")
        else:
            print(f"      champion still better → kept the incumbent.")
    else:
        print(f"      not enough data yet (need 2 classes + 20 rows) —"
              f" just accumulating this run.")
        print(f"\n[4/6] PROMOTE · skipped (no model trained yet)")

    # 5. DRIFT signals
    history = _load_history()
    agr_series = [h["challenger_agreement"] for h in history if h.get("can_train")]
    agr_drift = drift.agreement_drift(challenger_agr, agr_series, cfg["rolling_window"])
    vocab_drift = drift.vocabulary_drift(
        [r["text"] for r in test], [r["text"] for r in train])
    drift_flag = agr_drift > cfg["drift_threshold"]
    print(f"\n[5/6] DRIFT  · new-vocabulary rate: {vocab_drift:.0%}"
          f"  |  agreement drift: {agr_drift:+.3f}"
          f"  {'⚠ DRIFT' if drift_flag else '(stable)'}")

    # persist the newly labeled data AFTER using it as the test set
    _append_labeled(new_rows)

    metrics = {
        "timestamp": ts,
        "batch_size": len(new_rows),
        "positive_rate": round(positive_rate, 4),
        "can_train": can_train,
        "challenger_agreement": round(challenger_agr, 4),
        "champion_agreement": round(champion_agr, 4),
        "promoted": promoted,
        "agreement_drift": agr_drift,
        "vocabulary_drift": vocab_drift,
        "drift_flag": drift_flag,
        "total_labeled": len(train) + len(test),
    }
    history.append(metrics)
    with open(HIST, "w") as f:
        json.dump(history, f, indent=2)

    # 6. REPORT
    os.makedirs(REPORTS, exist_ok=True)
    print(f"\n[6/6] REPORT · writing plain-English changelog...")
    text = report.write_report(metrics, cfg["teacher_model"],
                               use_llm=cfg.get("llm_report", False))
    fname = os.path.join(REPORTS, f"report_{ts.replace(':', '-')}.md")
    with open(fname, "w") as f:
        f.write(text)
    with open(os.path.join(REPORTS, "latest.md"), "w") as f:
        f.write(text)

    print("\n" + "-" * 60)
    print(f"  DONE. total labeled so far: {metrics['total_labeled']}"
          f"  |  promoted: {metrics['promoted']}")
    print(f"  report -> {fname}")
    print("-" * 60 + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true",
                    help="Label with a keyword heuristic instead of the LLM "
                         "(no API key / no cost) — for local testing.")
    args = ap.parse_args()
    main(mock=args.mock)
