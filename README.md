# ⚗️ A/B Testing Framework

A production-grade A/B testing engine built from scratch.

## Features
- **Deterministic hash-based bucketing** — same user always gets same variant, no DB lookup
- **Chi-squared + Welch t-test** — correct test for conversion vs continuous metrics
- **Sequential testing (SPRT)** — stop experiments early when significance reached
- **Sample size calculator** — plan experiments before running them
- **FastAPI backend** — plug any app into the engine via REST API
- **Streamlit dashboard** — live results, confidence intervals, SPRT decisions

## Statistical methods used
- **Chi-squared test** for conversion-rate comparison between control and treatment
- **Welch's t-test** for continuous metrics (revenue, time-on-page, etc.) — doesn't assume equal variance between groups
- **Sequential Probability Ratio Test (SPRT)** for early-stopping guidance, so you don't have to wait for a fixed sample size to get a read
- **Wilson confidence intervals** for conversion rates — more reliable than the normal approximation at small sample sizes or rates near 0%/100%
- **Sample size estimation** using an absolute Minimum Detectable Effect (in percentage points) — e.g. a 10% baseline with a 5pp MDE plans for detecting a move to 15%, not a 5% relative change

## Quickstart
```bash
pip install -r requirements.txt

# Seed demo data
python tests/seed_demo.py

# Run dashboard
streamlit run dashboard/app.py

# Run API server (optional)
uvicorn api.routes:app --reload
```

## API Usage
```bash
# Create experiment
curl -X POST http://localhost:8000/experiments \
  -H "Content-Type: application/json" \
  -d '{"name":"Button Color Test","metric":"checkout_click","split":0.5}'

# Track event
curl -X POST http://localhost:8000/track \
  -H "Content-Type: application/json" \
  -d '{"experiment_id":"<id>","user_id":"user_123","event":"checkout_click","value":49.99}'

# Get results
curl http://localhost:8000/experiments/<id>/results
```

## Resume Bullet
> Built A/B testing engine from scratch with hash-based deterministic bucketing,
> sequential testing (SPRT) for early stopping, and chi-squared significance analysis;
> exposed via FastAPI with real-time Streamlit dashboard tracking conversion lift
> and confidence intervals.
