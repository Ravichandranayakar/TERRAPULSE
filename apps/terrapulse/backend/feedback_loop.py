"""
Feedback loop - the closed cycle that runs without an operator.

    new data / events -> field verification + curator -> curated dataset
      -> periodic retraining -> validation -> new model version
      -> improved predictions

What was manual before
  Curator approval already produced a dataset manifest, but the manifest was
  written with `"training_status": "not_automatically_run"` and
  `"model_updated": false`, and a person ran scripts/train_landslide_model.py by
  hand afterwards. This module removes the person from that step.

Safety, because an automatic retrain can silently degrade a working model
  A candidate is trained into its OWN version directory. It is promoted only if
  it clears a validation gate against the version currently serving. If it does
  not, it is kept on disk as a rejected candidate, the active version is left
  alone, and the reason is recorded. Automatic does not mean unsupervised.

Registry
  models/registry.json records every version, its metrics, its status
  (active / candidate / rejected / superseded) and why.
"""

import io
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))
MODELS_DIR = os.path.join(REPO, "models")
REGISTRY = os.path.join(MODELS_DIR, "registry.json")
TRAIN_SCRIPT = os.path.join(REPO, "scripts", "train_landslide_model.py")
BASE_DATASET = os.path.join(REPO, "TERRAPULSE_DATA", "13_MODEL_DATASETS",
                            "landslide_dataset_v0.1.csv")

# A candidate must not lose more than this on the leave-one-state-out bars.
TOLERANCE = {"recall": float(os.environ.get("TERRAPULSE_PROMOTE_RECALL_TOL", "0.02")),
             "roc_auc": float(os.environ.get("TERRAPULSE_PROMOTE_AUC_TOL", "0.02"))}

MIN_NEW_EVENTS = int(os.environ.get("TERRAPULSE_RETRAIN_MIN_EVENTS", "25"))
MAX_INTERVAL_DAYS = int(os.environ.get("TERRAPULSE_RETRAIN_MAX_DAYS", "30"))
TRAIN_TIMEOUT = int(os.environ.get("TERRAPULSE_RETRAIN_TIMEOUT", "5400"))


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

def load_registry() -> Dict[str, Any]:
    if os.path.exists(REGISTRY):
        with io.open(REGISTRY, encoding="utf-8") as fh:
            return json.load(fh)
    return {"active": None, "versions": [], "updated_at": None}


def save_registry(reg: Dict[str, Any]) -> None:
    reg["updated_at"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(MODELS_DIR, exist_ok=True)
    with io.open(REGISTRY, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2)


def read_metrics(directory: str) -> Dict[str, Any]:
    path = os.path.join(directory, "metrics.json")
    if not os.path.exists(path):
        return {}
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def loso_scores(metrics: Dict[str, Any]) -> Dict[str, float]:
    """Leave-one-state-out bars, averaged across the held-out states.

    leave_one_state_out is stored as {model: [one record per held-out state]},
    so the fold records are averaged rather than read from a single summary.
    """
    out: Dict[str, float] = {}
    loso = metrics.get("leave_one_state_out") or {}
    chosen = metrics.get("model_selected", "rf")
    entry = loso.get(chosen) if isinstance(loso, dict) else None

    records = []
    if isinstance(entry, list):
        records = [r for r in entry if isinstance(r, dict)]
    elif isinstance(entry, dict):
        records = [entry.get("summary", entry)]

    if not records:
        return out
    for key in ("recall", "roc_auc", "f1", "precision"):
        values = [float(r[key]) for r in records if r.get(key) is not None]
        if values:
            out[key] = round(sum(values) / len(values), 4)
    out["states"] = len(records)
    return out


def active_version() -> Dict[str, Any]:
    reg = load_registry()
    active = reg.get("active")
    if active:
        for version in reg.get("versions", []):
            if version.get("version") == active:
                return version
    # Fall back to the shipped artifact if the registry is empty.
    default_dir = os.path.join(MODELS_DIR, "landslide_v0.4")
    return {"version": "landslide_v0.4", "directory": default_dir,
            "status": "active", "metrics": loso_scores(read_metrics(default_dir))}


def next_version_label() -> str:
    """Next free version. Considers the registry AND directories already on disk,
    so a candidate can never be trained over an existing artifact."""
    highest = 0

    def consider(name: str) -> None:
        nonlocal highest
        if not name or not name.startswith("landslide_v"):
            return
        try:
            # Versions are major.minor (landslide_v0.1 -> minor 1), so the minor
            # is the number to advance, not the leading 0.
            tail = name.rsplit("v", 1)[1]
            minor = int(tail.split(".")[1]) if "." in tail else int(tail)
            highest = max(highest, minor)
        except (IndexError, ValueError):
            pass

    for version in load_registry().get("versions", []):
        consider(version.get("version", ""))
    if os.path.isdir(MODELS_DIR):
        for name in os.listdir(MODELS_DIR):
            if os.path.isdir(os.path.join(MODELS_DIR, name)):
                consider(name)
    return "landslide_v0.%d" % (highest + 1)


# --------------------------------------------------------------------------
# what has arrived
# --------------------------------------------------------------------------

def pending_curated_events(hazard_type: str = "landslide") -> Dict[str, Any]:
    """Approved field reports waiting to enter training.

    Uses get_eligible_reports, which returns individual reports carrying a
    location and a date. get_training_buffer must NOT be used here: it returns
    one grouped COUNT row per hazard type, so counting its length would report
    the number of hazard groups rather than the number of reports.
    """
    try:
        import main as backend
        repository = backend._verification_service.repository
        reports = repository.get_eligible_reports(hazard_type)
        return {"available": True, "pending": len(reports), "records": reports}
    except Exception as error:
        return {"available": False, "pending": 0, "reason": str(error), "records": []}


def due_for_retrain() -> Dict[str, Any]:
    pending = pending_curated_events()
    reg = load_registry()
    last = reg.get("last_retrain_at")
    days = None
    if last:
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - last_dt).days
        except ValueError:
            days = None

    reasons: List[str] = []
    if pending.get("pending", 0) >= MIN_NEW_EVENTS:
        reasons.append("%d new curated events (threshold %d)"
                       % (pending["pending"], MIN_NEW_EVENTS))
    if days is None or days >= MAX_INTERVAL_DAYS:
        reasons.append("scheduled refresh (%s days since last retrain)"
                       % ("never" if days is None else days))

    return {
        "due": bool(reasons),
        "reasons": reasons,
        "pending_events": pending.get("pending", 0),
        "days_since_retrain": days,
        "min_new_events": MIN_NEW_EVENTS,
        "max_interval_days": MAX_INTERVAL_DAYS,
    }


# --------------------------------------------------------------------------
# retrain, validate, promote
# --------------------------------------------------------------------------

def build_curated_dataset(version: str, hazard_type: str = "landslide",
                          curator_id: str = "automated_feedback_loop") -> Dict[str, Any]:
    """Turn approved reports into real feature rows, then record the manifest.

    Two steps, because they answer different questions:
      scripts/build_curated_dataset.py  -> the actual training rows
      verification service build_dataset -> the audit manifest, and it marks the
                                            reports as consumed so the same
                                            report cannot enter training twice
    """
    result: Dict[str, Any] = {"built": False}

    script = os.path.join(REPO, "scripts", "build_curated_dataset.py")
    if os.path.exists(script):
        try:
            proc = subprocess.run([sys.executable, script, version, hazard_type],
                                  cwd=REPO, capture_output=True, text=True,
                                  timeout=TRAIN_TIMEOUT, encoding="utf-8",
                                  errors="replace")
            dataset = os.path.join(REPO, "TERRAPULSE_DATA", "13_MODEL_DATASETS",
                                   "landslide_dataset_%s.csv" % version)
            result["rows_built"] = proc.returncode == 0 and os.path.exists(dataset)
            result["dataset"] = dataset if result["rows_built"] else None
            result["output_tail"] = (proc.stdout or "")[-800:]
            if proc.returncode != 0:
                result["reason"] = (proc.stderr or "")[-400:]
        except Exception as error:
            result["reason"] = str(error)

    try:
        import main as backend
        result["manifest"] = backend.build_training_dataset(hazard_type, curator_id)
        result["built"] = True
    except Exception as error:
        result.setdefault("reason", str(error))

    return result


def train_candidate(version: str, dataset: Optional[str] = None,
                    verbose: bool = False) -> Dict[str, Any]:
    """Train a candidate into its own directory. Nothing is promoted here."""
    directory = os.path.join(MODELS_DIR, version)
    os.makedirs(directory, exist_ok=True)

    env = dict(os.environ)
    env["TERRAPULSE_MODEL_DIR"] = directory
    env["TERRAPULSE_DATASET"] = dataset or BASE_DATASET
    env.setdefault("PYTHONIOENCODING", "utf-8")

    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, TRAIN_SCRIPT],
            cwd=REPO, env=env, capture_output=True, text=True,
            timeout=TRAIN_TIMEOUT, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"trained": False, "version": version, "directory": directory,
                "reason": "training exceeded %ds" % TRAIN_TIMEOUT}

    metrics = read_metrics(directory)
    return {
        "trained": proc.returncode == 0 and bool(metrics),
        "version": version,
        "directory": directory,
        "duration_s": round(time.time() - started, 1),
        "returncode": proc.returncode,
        "metrics": loso_scores(metrics),
        "tail": (proc.stdout or "")[-1200:] if verbose else None,
        "stderr_tail": (proc.stderr or "")[-800:] if proc.returncode != 0 else None,
    }


def evaluate_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Compare a candidate against the version currently serving."""
    current = active_version()
    current_scores = current.get("metrics") or loso_scores(
        read_metrics(current.get("directory", "")))
    candidate_scores = candidate.get("metrics") or {}

    if not candidate_scores:
        return {"promote": False, "reason": "candidate produced no metrics"}

    deltas = {}
    failures = []
    for key, tolerance in TOLERANCE.items():
        if key not in candidate_scores or key not in current_scores:
            continue
        delta = candidate_scores[key] - current_scores[key]
        deltas[key] = round(delta, 4)
        if delta < -tolerance:
            failures.append("%s fell by %.4f (tolerance %.2f)"
                            % (key, -delta, tolerance))

    return {
        "promote": not failures,
        "reason": ("clears the validation gate" if not failures
                   else "; ".join(failures)),
        "candidate": candidate_scores,
        "current": current_scores,
        "deltas": deltas,
        "current_version": current.get("version"),
    }


def promote(candidate: Dict[str, Any], evaluation: Dict[str, Any],
            dataset_version: Optional[str] = None) -> Dict[str, Any]:
    """Make a candidate the active version, or record why it was rejected."""
    reg = load_registry()
    version = candidate["version"]
    status = "active" if evaluation["promote"] else "rejected"

    for entry in reg.get("versions", []):
        if entry.get("status") == "active":
            entry["status"] = "superseded"

    reg.setdefault("versions", []).append({
        "version": version,
        "directory": candidate["directory"],
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "metrics": candidate.get("metrics", {}),
        "dataset_version": dataset_version,
        "evaluation": {"reason": evaluation["reason"], "deltas": evaluation.get("deltas", {})},
    })

    if evaluation["promote"]:
        reg["active"] = version
    elif not reg.get("active"):
        # A rejected candidate must not leave the registry without an active
        # version, or the next retrain would have nothing to compare against.
        reg["active"] = evaluation.get("current_version")
    reg["last_retrain_at"] = datetime.now(timezone.utc).isoformat()
    save_registry(reg)

    return {"version": version, "status": status, "active": reg.get("active"),
            "reason": evaluation["reason"]}


def run_feedback_cycle(force: bool = False, verbose: bool = False) -> Dict[str, Any]:
    """One turn of the loop. Safe to call on a schedule."""
    due = due_for_retrain()
    if not due["due"] and not force:
        return {"ran": False, "reason": "not due", "due": due}

    version = next_version_label()
    dataset_info = None
    dataset_path = BASE_DATASET

    # Approved reports must reach the model, otherwise the loop would retrain on
    # the same rows every time and never learn anything new. This runs the same
    # extractors used for the original training points over the new coordinates,
    # producing fresh values under the same column names.
    if due.get("pending_events", 0) > 0:
        dataset_info = build_curated_dataset(version)
        built = (dataset_info or {}).get("dataset")
        if built and os.path.exists(built):
            dataset_path = built
        elif (dataset_info or {}).get("built"):
            # a manifest was recorded but no feature rows were produced
            dataset_path = BASE_DATASET

    candidate = train_candidate(version, dataset_path, verbose=verbose)
    if not candidate.get("trained"):
        return {"ran": True, "version": version, "trained": False,
                "reason": candidate.get("reason") or "training failed",
                "stderr": candidate.get("stderr_tail")}

    evaluation = evaluate_candidate(candidate)
    outcome = promote(candidate, evaluation,
                      dataset_version=(dataset_info or {}).get("manifest", {})
                      .get("dataset_version"))

    return {"ran": True, "due": due, "candidate": candidate,
            "evaluation": evaluation, "outcome": outcome,
            "dataset": dataset_info}