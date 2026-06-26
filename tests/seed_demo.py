"""
Seeds demo data — run this once to populate the dashboard.
Simulates a button-color experiment: orange vs blue CTA.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import init_db
from core import experiment as exp_svc

random.seed(42)

def seed():
    init_db()

    # Create experiment
    try:
        e = exp_svc.create_experiment(
            name="Orange vs Blue CTA Button",
            hypothesis="Orange button will increase checkout clicks by 10%",
            metric="checkout_click",
            split=0.5,
            min_samples=200,
        )
        exp_id = e["id"]
        print(f"Created experiment: {exp_id}")
    except Exception as ex:
        # Already exists — fetch it
        exps = exp_svc.list_experiments()
        exp_id = exps[0]["id"]
        print(f"Using existing experiment: {exp_id}")

    # Simulate 400 users
    # Control (blue):    10% conversion
    # Treatment (orange): 14% conversion
    for i in range(400):
        user_id = f"user_{i:04d}"
        from core.assigner import ExperimentAssigner
        variant = ExperimentAssigner().assign(user_id, exp_id, 0.5)

        # Page view (everyone)
        exp_svc.track_event(exp_id, user_id, "page_view", 1.0)

        # Conversion with variant-specific probability
        conv_prob = 0.14 if variant == "treatment" else 0.10
        if random.random() < conv_prob:
            revenue = round(random.uniform(20, 120), 2)
            exp_svc.track_event(exp_id, user_id, "checkout_click", revenue)

    print("✅ Demo data seeded. Run the dashboard now.")

if __name__ == "__main__":
    seed()
