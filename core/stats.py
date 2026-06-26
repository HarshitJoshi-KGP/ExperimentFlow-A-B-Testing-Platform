"""
Statistics engine:
- Chi-squared test  → conversion rate experiments
- Welch t-test      → continuous metric experiments (revenue, time)
- SPRT              → sequential testing / early stopping
- Sample size calc  → pre-experiment planning
"""
import math
import numpy as np
from scipy import stats as sp_stats
from dataclasses import dataclass
from typing import Optional


@dataclass
class StatResult:
    control_mean: float
    treatment_mean: float
    lift_percent: float
    p_value: float
    significant: bool
    confidence_pct: float
    control_n: int
    treatment_n: int
    test_type: str
    power: Optional[float] = None
    ci_lower: float = 0.0
    ci_upper: float = 0.0


class StatsEngine:

    # ── Conversion rate test (chi-squared) ──────────────────────────────
    def analyze_conversion(
        self,
        control_conversions: int, control_total: int,
        treatment_conversions: int, treatment_total: int,
        alpha: float = 0.05,
    ) -> StatResult:
        control_rate = control_conversions / max(control_total, 1)
        treatment_rate = treatment_conversions / max(treatment_total, 1)
        lift = ((treatment_rate - control_rate) / max(control_rate, 1e-9)) * 100

        table = [
            [control_conversions,  control_total  - control_conversions],
            [treatment_conversions, treatment_total - treatment_conversions],
        ]
        chi2, p_value, _, _ = sp_stats.chi2_contingency(table, correction=False)

        # Wilson confidence interval for treatment rate
        ci_lower, ci_upper = self._wilson_ci(treatment_conversions, treatment_total)

        return StatResult(
            control_mean=round(control_rate, 4),
            treatment_mean=round(treatment_rate, 4),
            lift_percent=round(lift, 2),
            p_value=round(p_value, 4),
            significant=p_value < alpha,
            confidence_pct=round((1 - p_value) * 100, 1),
            control_n=control_total,
            treatment_n=treatment_total,
            test_type="chi-squared",
            ci_lower=round(ci_lower, 4),
            ci_upper=round(ci_upper, 4),
        )

    # ── Continuous metric test (Welch t-test) ───────────────────────────
    def analyze_continuous(
        self,
        control_values: list,
        treatment_values: list,
        alpha: float = 0.05,
    ) -> StatResult:
        c = np.array(control_values, dtype=float)
        t = np.array(treatment_values, dtype=float)

        t_stat, p_value = sp_stats.ttest_ind(c, t, equal_var=False)
        lift = ((t.mean() - c.mean()) / max(abs(c.mean()), 1e-9)) * 100

        # 95% CI on difference
        diff = t.mean() - c.mean()
        se = math.sqrt(c.var(ddof=1)/len(c) + t.var(ddof=1)/len(t))
        z = sp_stats.norm.ppf(1 - alpha/2)

        return StatResult(
            control_mean=round(float(c.mean()), 4),
            treatment_mean=round(float(t.mean()), 4),
            lift_percent=round(lift, 2),
            p_value=round(p_value, 4),
            significant=p_value < alpha,
            confidence_pct=round((1 - p_value) * 100, 1),
            control_n=len(c),
            treatment_n=len(t),
            test_type="welch-t",
            ci_lower=round(diff - z * se, 4),
            ci_upper=round(diff + z * se, 4),
        )

    # ── Sequential testing (SPRT) ────────────────────────────────────────
    def sprt_decision(
        self,
        control_conversions: int, control_total: int,
        treatment_conversions: int, treatment_total: int,
        alpha: float = 0.05,
        beta: float = 0.20,
        min_detectable_effect: float = 0.05,  # pre-specified H1 effect (absolute pp)
    ) -> dict:
        """
        Sequential Probability Ratio Test.

        H0: treatment rate == control rate (p0)
        H1: treatment rate == control rate + min_detectable_effect (p1)

        p1 MUST be a fixed, pre-specified effect size decided before looking at
        the data (kept consistent with the sample-size calculator's MDE) —
        never the treatment group's own observed/MLE rate. Plugging the data's
        own rate in as the alternative turns this into a self-fulfilling
        statistic that hits "STOP" far more easily than the classical test,
        which is what caused SPRT to contradict the chi-squared result.

        This method reports ONLY the sequential-test outcome (CONTINUE / STOP
        and which boundary). It never recommends shipping or deploying —
        that call belongs solely to `final_verdict()`.
        """
        A = math.log((1 - beta) / alpha)   # upper boundary → reject H0
        B = math.log(beta / (1 - alpha))   # lower boundary → accept H0

        p0 = control_conversions / max(control_total, 1)
        # Fixed, pre-specified alternative — clipped to a valid probability
        p1 = min(max(p0 + min_detectable_effect, 1e-6), 1 - 1e-6)

        if treatment_total == 0 or p0 <= 0 or p0 >= 1:
            return {
                "decision": "CONTINUE",
                "favors": None,
                "reason": "📊 Insufficient data — continue collecting samples",
                "llr": 0.0,
                "upper_boundary": round(A, 4),
                "lower_boundary": round(B, 4),
            }

        # Log-likelihood ratio of the observed treatment data under H1 vs H0
        llr = (treatment_conversions * math.log(p1 / p0) +
               (treatment_total - treatment_conversions) * math.log((1 - p1) / (1 - p0)))

        if llr >= A:
            decision, favors = "STOP", "treatment"
            reason = "✅ Sequential boundary reached — evidence favors the treatment"
        elif llr <= B:
            decision, favors = "STOP", "control"
            reason = "❌ Sequential boundary reached — no meaningful effect detected"
        else:
            decision, favors = "CONTINUE", None
            reason = (f"📊 Sequential boundary not reached — continue collecting data "
                       f"(LLR={llr:.3f}, need {B:.2f} to {A:.2f})")

        return {
            "decision": decision,
            "favors": favors,
            "reason": reason,
            "llr": round(llr, 4),
            "upper_boundary": round(A, 4),
            "lower_boundary": round(B, 4),
        }

    # ── Final deployment verdict — single source of truth ───────────────
    def final_verdict(
        self,
        stat_result,
        sprt_result: dict,
        min_samples_reached: bool,
        confidence_threshold: float = 95.0,
    ) -> dict:
        """
        The ONLY place a "ship it" decision gets made. Combines the classical
        test, the confidence score, the minimum-sample requirement, and the
        SPRT outcome so the dashboard can never show two contradictory
        recommendations from two different code paths.

        🚀 READY TO SHIP   — every one of the 4 checks below passes
        ❌ KEEP CONTROL    — strong evidence the treatment is NOT better
        📊 MORE DATA REQUIRED — anything else (the safe default)
        """
        s = stat_result if isinstance(stat_result, dict) else stat_result.__dict__

        significant     = bool(s["significant"])
        confidence_met  = s["confidence_pct"] >= confidence_threshold
        lift_positive   = s["lift_percent"] > 0
        sprt_favors_treatment = sprt_result.get("favors") == "treatment"
        sprt_favors_control   = sprt_result.get("favors") == "control"

        checks = {
            "treatment_appears_better":         lift_positive,
            "statistical_significance_reached": significant,
            "confidence_threshold_met":          confidence_met,
            "min_sample_reached":               bool(min_samples_reached),
            "sprt_agrees":                       sprt_favors_treatment,
        }

        ready_to_ship = (significant and confidence_met
                          and min_samples_reached and sprt_favors_treatment)

        if ready_to_ship:
            verdict = "🚀 READY TO SHIP"
        elif (significant and not lift_positive) or sprt_favors_control:
            verdict = "❌ KEEP CONTROL"
        else:
            verdict = "📊 MORE DATA REQUIRED"

        return {"verdict": verdict, "checks": checks}

    # ── Sample size calculator ───────────────────────────────────────────
    def required_sample_size(
        self,
        baseline_rate: float,
        min_detectable_effect: float,  # absolute lift in percentage points, e.g. 0.05 = +5pp
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> dict:
        p1 = baseline_rate
        p2 = baseline_rate + min_detectable_effect
        p_bar = (p1 + p2) / 2

        z_alpha = sp_stats.norm.ppf(1 - alpha / 2)
        z_beta  = sp_stats.norm.ppf(power)

        n = (2 * p_bar * (1 - p_bar) * (z_alpha + z_beta) ** 2) / ((p1 - p2) ** 2)
        n = math.ceil(n)

        return {
            "per_variant": n,
            "total": n * 2,
            "baseline_rate": baseline_rate,
            "expected_treatment_rate": round(p2, 4),
            "alpha": alpha,
            "power": power,
            "min_detectable_effect_pp": round(min_detectable_effect * 100, 1),
        }

    # ── Helpers ──────────────────────────────────────────────────────────
    def _wilson_ci(self, successes: int, total: int, z: float = 1.96):
        if total == 0:
            return 0.0, 0.0
        p = successes / total
        denom = 1 + z**2 / total
        centre = (p + z**2 / (2 * total)) / denom
        margin = (z * math.sqrt(p*(1-p)/total + z**2/(4*total**2))) / denom
        return max(0, centre - margin), min(1, centre + margin)
