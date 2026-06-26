"""
FastAPI routes for A/B Testing engine.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import init_db
from core import experiment as exp_svc
from core.stats import StatsEngine
from core.assigner import ExperimentAssigner

app = FastAPI(title="A/B Testing Engine", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

init_db()
stats = StatsEngine()
assigner = ExperimentAssigner()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateExperimentRequest(BaseModel):
    name: str
    hypothesis: str = ""
    metric: str = Field(..., description="Event name to track e.g. 'click', 'purchase'")
    split: float = Field(0.5, ge=0.0, le=1.0)
    min_samples: int = Field(100, ge=10)

class TrackEventRequest(BaseModel):
    experiment_id: str
    user_id: str
    event: str
    value: float = 1.0

class SampleSizeRequest(BaseModel):
    baseline_rate: float
    min_detectable_effect: float = 0.05
    alpha: float = 0.05
    power: float = 0.80


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"service": "A/B Testing Engine", "status": "running"}


@app.post("/experiments")
def create(req: CreateExperimentRequest):
    try:
        return exp_svc.create_experiment(
            req.name, req.hypothesis, req.metric, req.split, req.min_samples
        )
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/experiments")
def list_all():
    return exp_svc.list_experiments()


@app.get("/experiments/{exp_id}")
def get_one(exp_id: str):
    e = exp_svc.get_experiment(exp_id)
    if not e:
        raise HTTPException(404, "Not found")
    return e


@app.post("/experiments/{exp_id}/stop")
def stop(exp_id: str):
    exp_svc.stop_experiment(exp_id)
    return {"status": "stopped"}


@app.post("/track")
def track(req: TrackEventRequest):
    try:
        return exp_svc.track_event(req.experiment_id, req.user_id, req.event, req.value)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/experiments/{exp_id}/results")
def results(exp_id: str):
    try:
        return exp_svc.get_results(exp_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/experiments/{exp_id}/assign")
def assign(exp_id: str, user_id: str):
    e = exp_svc.get_experiment(exp_id)
    if not e:
        raise HTTPException(404, "Experiment not found")
    variant = assigner.assign(user_id, exp_id, e["split"])
    return {"user_id": user_id, "experiment_id": exp_id, "variant": variant}


@app.post("/sample-size")
def sample_size(req: SampleSizeRequest):
    return stats.required_sample_size(
        req.baseline_rate, req.min_detectable_effect, req.alpha, req.power
    )
