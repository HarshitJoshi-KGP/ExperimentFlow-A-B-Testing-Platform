"""
Experiment CRUD and event tracking.
"""
from .database import get_conn, new_id, now_iso
from .assigner import ExperimentAssigner
from .stats import StatsEngine
import pandas as pd

assigner = ExperimentAssigner()
stats_engine = StatsEngine()


# ── Experiment management ────────────────────────────────────────────────────

def create_experiment(name, hypothesis, metric, split=0.5, min_samples=100) -> dict:
    conn = get_conn()
    exp_id = new_id()
    conn.execute(
        """INSERT INTO experiments
           (id, name, hypothesis, metric, split, min_samples, status, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (exp_id, name, hypothesis, metric, split, min_samples, "running", now_iso())
    )
    conn.commit()
    conn.close()
    return get_experiment(exp_id)


def get_experiment(exp_id: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_experiments() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def stop_experiment(exp_id: str):
    conn = get_conn()
    conn.execute("UPDATE experiments SET status='stopped' WHERE id=?", (exp_id,))
    conn.commit()
    conn.close()


# ── Event tracking ────────────────────────────────────────────────────────────

def track_event(experiment_id: str, user_id: str, event: str, value: float = 1.0) -> dict:
    exp = get_experiment(experiment_id)
    if not exp:
        raise ValueError(f"Experiment {experiment_id} not found")
    if exp["status"] != "running":
        raise ValueError("Experiment is not running")

    variant = assigner.assign(user_id, experiment_id, exp["split"])

    conn = get_conn()
    conn.execute(
        """INSERT INTO experiment_events
           (id, experiment_id, user_id, variant, event, value, timestamp)
           VALUES (?,?,?,?,?,?,?)""",
        (new_id(), experiment_id, user_id, variant, event, value, now_iso())
    )
    conn.commit()
    conn.close()
    return {"user_id": user_id, "variant": variant, "event": event, "value": value}


# ── Analytics ─────────────────────────────────────────────────────────────────

def get_results(experiment_id: str) -> dict:
    exp = get_experiment(experiment_id)
    if not exp:
        raise ValueError("Experiment not found")

    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM experiment_events WHERE experiment_id=?", (experiment_id,)
    ).fetchall()
    conn.close()

    if not rows:
        return {"experiment": exp, "error": "No events recorded yet"}

    df = pd.DataFrame([dict(r) for r in rows])

    # Split by variant
    ctrl  = df[df["variant"] == "control"]
    treat = df[df["variant"] == "treatment"]

    metric = exp["metric"]

    # Conversion analysis (event count / unique users)
    ctrl_users  = ctrl["user_id"].nunique()
    treat_users = treat["user_id"].nunique()

    # Users who fired the tracked event at least once = converted
    ctrl_converted  = ctrl[ctrl["event"] == metric]["user_id"].nunique()
    treat_converted = treat[treat["event"] == metric]["user_id"].nunique()

    stat_result = stats_engine.analyze_conversion(
        ctrl_converted, ctrl_users,
        treat_converted, treat_users,
    )

    sprt = stats_engine.sprt_decision(
        ctrl_converted, ctrl_users,
        treat_converted, treat_users,
    )

    # Has the experiment's own pre-registered minimum sample size been met?
    min_samples_reached = (ctrl_users >= exp["min_samples"]
                            and treat_users >= exp["min_samples"])

    # Revenue / continuous if value column has real data
    revenue_stats = None
    if df["value"].max() > 1.0:
        ctrl_vals  = ctrl[ctrl["event"] == metric]["value"].tolist()
        treat_vals = treat[treat["event"] == metric]["value"].tolist()
        if ctrl_vals and treat_vals:
            revenue_stats = stats_engine.analyze_continuous(ctrl_vals, treat_vals)

    return {
        "experiment": exp,
        "summary": {
            "control_users":       ctrl_users,
            "treatment_users":     treat_users,
            "control_converted":   ctrl_converted,
            "treatment_converted": treat_converted,
            "total_events":        len(df),
        },
        "stats": stat_result.__dict__,
        "sprt":  sprt,
        "min_samples_reached": min_samples_reached,
        "final_verdict": stats_engine.final_verdict(
            stat_result, sprt, min_samples_reached,
        ),
        "revenue_stats": revenue_stats.__dict__ if revenue_stats else None,
        "sample_size_needed": stats_engine.required_sample_size(
            baseline_rate=stat_result.control_mean or 0.1,
            min_detectable_effect=0.05,  # detect a +5 percentage-point absolute lift
        ),
    }


def get_events_df(experiment_id: str) -> pd.DataFrame:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM experiment_events WHERE experiment_id=?", (experiment_id,)
    ).fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
