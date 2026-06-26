"""
Deterministic hash-based variant assignment.
Same user_id + experiment_id always returns the same variant.
No database lookup needed — pure math.
"""
import hashlib


class ExperimentAssigner:
    def assign(self, user_id: str, experiment_id: str, split: float) -> str:
        """
        Returns 'treatment' or 'control'.
        Uses MD5 hash for uniform distribution across 10,000 buckets.
        """
        key = f"{user_id}:{experiment_id}"
        hash_hex = hashlib.md5(key.encode()).hexdigest()
        # Use first 8 hex chars → integer → bucket 0–9999
        bucket = int(hash_hex[:8], 16) % 10000
        threshold = int(split * 10000)
        return "treatment" if bucket < threshold else "control"

    def bulk_assign(self, user_ids: list, experiment_id: str, split: float) -> dict:
        return {uid: self.assign(uid, experiment_id, split) for uid in user_ids}
