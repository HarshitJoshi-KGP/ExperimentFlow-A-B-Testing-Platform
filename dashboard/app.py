"""
A/B Testing Dashboard — Streamlit
Full experiment management + live stats + SPRT + sample size calculator
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import init_db
from core import experiment as exp_svc
from core.stats import StatsEngine
from core.assigner import ExperimentAssigner

init_db()
stats = StatsEngine()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="A/B Testing Engine", page_icon="⚗️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500&display=swap');
:root {
    --orange: #ff8c32; --green: #4ade80; --red: #f87171;
    --bg: #08080e; --surface: rgba(255,255,255,0.04);
    --border: rgba(255,255,255,0.09); --text: #e0dbd2; --muted: #666;
}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;color:var(--text);}
.stApp{background:var(--bg);}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding:1.5rem 3rem;}

.metric-card{background:var(--surface);border:1px solid var(--border);
    border-radius:14px;padding:1.2rem 1.5rem;text-align:center;}
.metric-val{font-family:'Syne',sans-serif;font-size:2rem;font-weight:800;color:var(--orange);}
.metric-lbl{font-family:'DM Mono',monospace;font-size:0.6rem;
    letter-spacing:0.18em;color:var(--muted);text-transform:uppercase;margin-top:4px;}

.sig-badge{display:inline-block;padding:0.3rem 0.9rem;border-radius:20px;
    font-family:'DM Mono',monospace;font-size:0.7rem;font-weight:500;letter-spacing:0.08em;}
.sig-yes{background:rgba(74,222,128,0.15);color:#4ade80;border:1px solid rgba(74,222,128,0.3);}
.sig-no{background:rgba(248,113,113,0.12);color:#f87171;border:1px solid rgba(248,113,113,0.3);}

.sprt-stop{background:rgba(74,222,128,0.1);border:1px solid rgba(74,222,128,0.25);
    border-radius:10px;padding:0.8rem 1rem;}
.sprt-cont{background:rgba(255,140,50,0.08);border:1px solid rgba(255,140,50,0.2);
    border-radius:10px;padding:0.8rem 1rem;}

.verdict-card{border-radius:10px;padding:0.9rem 1.1rem;}
.verdict-ship{background:rgba(74,222,128,0.12);border:1px solid rgba(74,222,128,0.3);}
.verdict-wait{background:rgba(255,140,50,0.08);border:1px solid rgba(255,140,50,0.2);}
.verdict-keep{background:rgba(248,113,113,0.12);border:1px solid rgba(248,113,113,0.3);}
.check-list{font-family:'DM Mono',monospace;font-size:0.8rem;margin-top:0.5rem;line-height:1.7;}
.check-pass{color:#4ade80;}
.check-fail{color:#f87171;}

h1,h2,h3{font-family:'Syne',sans-serif !important;}
.stButton>button{background:var(--orange)!important;border:none!important;
    color:#080404!important;font-family:'Syne',sans-serif!important;
    font-weight:700!important;border-radius:10px!important;}
.stSelectbox>div>div{background:var(--surface)!important;border-color:var(--border)!important;}
.stTextInput input,.stNumberInput input{background:var(--surface)!important;
    border-color:var(--border)!important;color:var(--text)!important;}
</style>
""", unsafe_allow_html=True)

# ── Sidebar nav ────────────────────────────────────────────────────────────────
st.sidebar.markdown("## ⚗️ A/B Testing Engine")
page = st.sidebar.radio("Navigate", [
    "📊 Dashboard", "➕ New Experiment",
    "📈 Results", "🔢 Sample Size Calculator"
])

# ════════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Dashboard
# ════════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.markdown("# Experiment Dashboard")
    experiments = exp_svc.list_experiments()

    if not experiments:
        st.info("No experiments yet. Create one from the sidebar.")
    else:
        # Summary metrics
        total     = len(experiments)
        running   = sum(1 for e in experiments if e["status"] == "running")
        stopped   = total - running

        c1, c2, c3 = st.columns(3)
        for col, val, lbl in [(c1,total,"Total Experiments"),
                               (c2,running,"Running"),
                               (c3,stopped,"Stopped")]:
            col.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{val}</div>
                <div class="metric-lbl">{lbl}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### All Experiments")

        for exp in experiments:
            status_color = "#4ade80" if exp["status"] == "running" else "#888"
            with st.expander(f"**{exp['name']}** — {exp['status'].upper()}"):
                col1, col2 = st.columns([3,1])
                with col1:
                    st.markdown(f"**Hypothesis:** {exp.get('hypothesis','—')}")
                    st.markdown(f"**Metric:** `{exp['metric']}` | **Split:** {int(exp['split']*100)}/{int((1-exp['split'])*100)} | **Min samples:** {exp['min_samples']}")
                    st.markdown(f"**Created:** {exp['created_at'][:19]}")
                with col2:
                    if exp["status"] == "running":
                        if st.button("Stop", key=f"stop_{exp['id']}"):
                            exp_svc.stop_experiment(exp["id"])
                            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# PAGE 2 — New Experiment
# ════════════════════════════════════════════════════════════════════════════════
elif page == "➕ New Experiment":
    st.markdown("# Create Experiment")

    with st.form("new_exp"):
        name       = st.text_input("Experiment Name", placeholder="Orange vs Blue CTA")
        hypothesis = st.text_area("Hypothesis", placeholder="Orange button will increase conversion by 10%")
        metric     = st.text_input("Metric (event name to track)", placeholder="checkout_click")
        split      = st.slider("Traffic Split (treatment %)", 10, 90, 50) / 100
        min_samples= st.number_input("Minimum samples per variant", 50, 10000, 200)

        submitted = st.form_submit_button("Create Experiment")
        if submitted:
            if not name or not metric:
                st.error("Name and metric are required.")
            else:
                try:
                    e = exp_svc.create_experiment(name, hypothesis, metric, split, min_samples)
                    st.success(f"✅ Experiment created! ID: `{e['id']}`")
                    st.json(e)
                except Exception as ex:
                    st.error(str(ex))

    # Quick event simulator
    st.markdown("---")
    st.markdown("### 🎲 Simulate Events (for testing)")
    experiments = exp_svc.list_experiments()
    running = [e for e in experiments if e["status"] == "running"]

    if running:
        sel = st.selectbox("Select experiment", [e["name"] for e in running])
        sel_exp = next(e for e in running if e["name"] == sel)
        n_users = st.slider("Simulate N users", 50, 500, 200)
        ctrl_rate  = st.slider("Control conversion rate %",  1, 50, 10) / 100
        treat_rate = st.slider("Treatment conversion rate %", 1, 50, 14) / 100

        if st.button("▶ Run Simulation"):
            import random
            random.seed(42)
            bar = st.progress(0)
            for i in range(n_users):
                uid = f"sim_user_{i:05d}"
                exp_svc.track_event(sel_exp["id"], uid, "page_view", 1.0)
                from core.assigner import ExperimentAssigner
                variant = ExperimentAssigner().assign(uid, sel_exp["id"], sel_exp["split"])
                rate = treat_rate if variant == "treatment" else ctrl_rate
                if random.random() < rate:
                    exp_svc.track_event(sel_exp["id"], uid, sel_exp["metric"],
                                        round(random.uniform(20, 150), 2))
                bar.progress((i+1)/n_users)
            st.success(f"✅ Simulated {n_users} users")
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Results
# ════════════════════════════════════════════════════════════════════════════════
elif page == "📈 Results":
    st.markdown("# Experiment Results")
    experiments = exp_svc.list_experiments()

    if not experiments:
        st.info("No experiments found.")
    else:
        sel_name = st.selectbox("Select Experiment", [e["name"] for e in experiments])
        sel_exp  = next(e for e in experiments if e["name"] == sel_name)

        try:
            res = exp_svc.get_results(sel_exp["id"])
        except Exception as ex:
            st.error(str(ex))
            st.stop()

        if "error" in res:
            st.warning(res["error"])
            st.stop()

        s   = res["stats"]
        smr = res["summary"]
        sprt= res["sprt"]

        # ── Key metrics ──
        st.markdown("### Key Metrics")
        c1,c2,c3,c4 = st.columns(4)
        cards = [
            (smr["control_users"],   "Control Users"),
            (smr["treatment_users"], "Treatment Users"),
            (f"{s['lift_percent']:+.1f}%", "Lift"),
            (f"{s['confidence_pct']:.1f}%", "Confidence Score"),
        ]
        for col, (val, lbl) in zip([c1,c2,c3,c4], cards):
            col.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{val}</div>
                <div class="metric-lbl">{lbl}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Significance badge ──
        sig_cls  = "sig-yes" if s["significant"] else "sig-no"
        sig_text = "✅ STATISTICALLY SIGNIFICANT" if s["significant"] else "📊 MORE DATA REQUIRED"
        st.markdown(f'<span class="sig-badge {sig_cls}">{sig_text}</span>', unsafe_allow_html=True)
        st.markdown(f"p-value: **{s['p_value']}** | Test: `{s['test_type']}`")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── SPRT decision ──
        sprt_cls = "sprt-stop" if sprt["decision"] == "STOP" else "sprt-cont"
        st.markdown(f"""
        <div class="{sprt_cls}">
            <b style="font-family:'DM Mono';font-size:0.75rem;">
            SEQUENTIAL TEST (SPRT): {sprt['decision']}
            </b><br>
            <span style="font-size:0.85rem;">{sprt['reason']}</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Final Verdict — single source of truth, combines every check ──
        fv      = res["final_verdict"]
        checks  = fv["checks"]
        verdict = fv["verdict"]

        if verdict.startswith("🚀"):
            v_cls, action = "verdict-ship", ("✔", "Ready to deploy to all users")
        elif verdict.startswith("❌"):
            v_cls, action = "verdict-keep", ("✖", "Recommend keeping the control experience")
        else:
            v_cls, action = "verdict-wait", ("✔", "Continue collecting more samples")

        check_rows = [
            ("Treatment currently appears better",   "Treatment does not currently appear better",   checks["treatment_appears_better"]),
            ("Statistical significance reached",      "Statistical significance not reached",         checks["statistical_significance_reached"]),
            ("Confidence score ≥ 95% reached",         "Confidence score has not reached 95%",          checks["confidence_threshold_met"]),
            ("Sequential stopping boundary reached",   "Sequential stopping boundary not reached",      checks["sprt_agrees"]),
            ("Minimum sample size reached",           "Minimum sample size not yet reached",          checks["min_sample_reached"]),
        ]
        check_html = "<br>".join(
            f'<span class="{"check-pass" if passed else "check-fail"}">'
            f'{"✔" if passed else "✖"} {pass_label if passed else fail_label}</span>'
            for pass_label, fail_label, passed in check_rows
        )
        check_html += (f'<br><span class="{"check-pass" if action[0]=="✔" else "check-fail"}">'
                        f'{action[0]} {action[1]}</span>')

        st.markdown(f"""
        <div class="verdict-card {v_cls}">
            <b style="font-family:'DM Mono';font-size:0.75rem;">FINAL VERDICT: {verdict}</b>
            <div class="check-list">{check_html}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Conversion rate chart ──
        st.markdown("### Conversion Rates")
        col_l, col_r = st.columns(2)

        with col_l:
            fig = go.Figure()
            variants  = ["Control", "Treatment"]
            rates     = [s["control_mean"]*100, s["treatment_mean"]*100]
            colors    = ["#444", "#ff8c32"]
            fig.add_trace(go.Bar(
                x=variants, y=rates,
                marker_color=colors,
                text=[f"{r:.2f}%" for r in rates],
                textposition="outside"
            ))
            fig.update_layout(
                title="Conversion Rate by Variant",
                yaxis_title="Conversion Rate (%)",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0dbd2"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            # CI chart
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=["Control", "Treatment"],
                y=[s["control_mean"]*100, s["treatment_mean"]*100],
                error_y=dict(
                    type='data',
                    array=[(s["ci_upper"]-s["ci_lower"])*50,
                           (s["ci_upper"]-s["ci_lower"])*50],
                    visible=True, color="#ff8c32"
                ),
                mode='markers',
                marker=dict(size=14, color=["#444","#ff8c32"]),
            ))
            fig2.update_layout(
                title="Conversion Rate with 95% CI",
                yaxis_title="Rate (%)",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0dbd2"),
            )
            st.plotly_chart(fig2, use_container_width=True)

        # ── Events over time ──
        df = exp_svc.get_events_df(sel_exp["id"])
        if not df.empty:
            st.markdown("### Events Over Time")
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["date"] = df["timestamp"].dt.date
            daily = df.groupby(["date","variant"]).size().reset_index(name="events")
            fig3 = px.line(daily, x="date", y="events", color="variant",
                           color_discrete_map={"control":"#888","treatment":"#ff8c32"})
            fig3.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0dbd2")
            )
            st.plotly_chart(fig3, use_container_width=True)

        # ── Sample size progress ──
        needed = res["sample_size_needed"]
        actual = max(smr["control_users"], smr["treatment_users"])
        pct    = min(100, int(actual / needed["per_variant"] * 100))
        st.markdown("### Sample Size Progress")
        st.progress(pct/100)
        st.markdown(f"**{actual}** / **{needed['per_variant']}** users per variant ({pct}%)")


# ════════════════════════════════════════════════════════════════════════════════
# PAGE 4 — Sample Size Calculator
# ════════════════════════════════════════════════════════════════════════════════
elif page == "🔢 Sample Size Calculator":
    st.markdown("# Sample Size Calculator")
    st.markdown("Plan your experiment *before* running it.")

    col1, col2 = st.columns(2)
    with col1:
        baseline = st.slider("Baseline conversion rate (%)", 1, 50, 10) / 100
        mde      = st.slider("Minimum detectable effect (percentage points)", 1, 20, 5) / 100
        st.caption("E.g. baseline 10% + MDE 5pp → detect a move to 15%.")
    with col2:
        alpha = st.selectbox("Significance level (α)", [0.05, 0.01, 0.10], index=0)
        power = st.selectbox("Statistical power (1-β)", [0.80, 0.90, 0.95], index=0)

    result = stats.required_sample_size(baseline, mde, alpha, power)

    c1,c2,c3 = st.columns(3)
    for col, val, lbl in [
        (c1, result["per_variant"],       "Per Variant"),
        (c2, result["total"],             "Total Users Needed"),
        (c3, f"{result['expected_treatment_rate']*100:.2f}%", "Expected Treatment Rate"),
    ]:
        col.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{val}</div>
            <div class="metric-lbl">{lbl}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Power curve
    import numpy as np
    mde_range = np.linspace(0.01, 0.20, 30)
    sizes = [stats.required_sample_size(baseline, m, alpha, power)["per_variant"] for m in mde_range]
    fig = px.line(x=mde_range*100, y=sizes,
                  labels={"x":"Min Detectable Effect (percentage points)","y":"Sample Size per Variant"},
                  title="Sample Size vs Minimum Detectable Effect")
    fig.update_traces(line_color="#ff8c32")
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#e0dbd2"))
    st.plotly_chart(fig, use_container_width=True)
