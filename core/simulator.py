"""
Simulate realistic A/B test traffic for demo purposes.
Run this to populate the DB before opening the dashboard.
"""
import sys, os, random, uuid, time
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.database import init_db, create_experiment, get_experiment, log_event
from core.assigner import ExperimentAssigner

assigner = ExperimentAssigner()

def simulate(experiment_name: str, n_users: int = 500,
             control_conv: float = 0.10, treatment_conv: float = 0.14):
    init_db()

    exp = get_experiment(name=experiment_name)
    if not exp:
        exp_id = create_experiment(
            name=experiment_name,
            hypothesis="Treatment button colour increases conversions",
            metric="conversion",
            split=0.5,
            min_samples=200
        )
        exp = get_experiment(exp_id=exp_id)

    exp_id = exp["id"]
    print(f"\n🔬 Simulating '{experiment_name}' with {n_users} users...")
    print(f"   Control conv rate:   {control_conv:.0%}")
    print(f"   Treatment conv rate: {treatment_conv:.0%}")

    for i in range(n_users):
        user_id = str(uuid.uuid4())
        variant = assigner.assign(user_id, exp_id, exp["split"])

        # Every user sees the page
        log_event(exp_id, user_id, variant, "view")

        # Conversion based on variant rate
        conv_rate = treatment_conv if variant == "treatment" else control_conv
        if random.random() < conv_rate:
            log_event(exp_id, user_id, variant, "purchase",
                      value=round(random.uniform(20, 200), 2))

        if (i + 1) % 100 == 0:
            print(f"   {i+1}/{n_users} users simulated...")

    print(f"✅ Done! Open dashboard to see results.\n")


if __name__ == "__main__":
    simulate("Button Colour Test",      n_users=600, control_conv=0.10, treatment_conv=0.135)
    simulate("Checkout Flow Test",      n_users=400, control_conv=0.08, treatment_conv=0.079)
    simulate("Homepage Headline Test",  n_users=300, control_conv=0.12, treatment_conv=0.155)
