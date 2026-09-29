import json
import hashlib
from datetime import datetime, timezone

class BatchGovernance:
    """
    Implements strict Batch Approval Governance to mitigate context drift.
    As per Spec V2.4, ensures structural invariants across high-frequency actions.
    """
    def __init__(self, max_iterations=50, max_window_minutes=15):
        self.max_iterations = max_iterations
        self.max_window_minutes = max_window_minutes
        self.active_batches = {}

    def verify_batch_invariants(self, batch_requests):
        """
        Verifies structural invariants for a group of requests.
        Returns (is_valid, error_message).
        """
        if not batch_requests:
            return False, "Empty batch"

        if len(batch_requests) > self.max_iterations:
            return False, f"Batch exceeds max iterations ({self.max_iterations})"

        # Base invariants from the first item
        first = batch_requests[0]
        base_tool = first.get("tool")
        base_risk = first.get("risk")
        base_schema = first.get("schema") # Expected schema ID
        base_origin = first.get("origin") # e.g., sub-domain

        for i, req in enumerate(batch_requests[1:], 1):
            # 1. Identical tool and risk
            if req.get("tool") != base_tool or req.get("risk") != base_risk:
                return False, f"Inconsistent tool/risk at index {i}"

            # 2. Bound to same target origin/sub-domain
            if req.get("origin") != base_origin:
                return False, f"Origin drift detected at index {i}"

            # 3. Schema match
            if req.get("schema") != base_schema:
                return False, f"Schema mismatch at index {i}"

            # 4. Pre-execution hash check (Parameter Invariant)
            # Ensures the structure of params hasn't changed (prevents injection mid-batch)
            if not self._verify_param_hash(first["params"], req["params"]):
                return False, f"Parameter invariant violation at index {i}"

        return True, "Batch invariants verified"

    def _verify_param_hash(self, base_params, current_params):
        """
        Checks if the parameter structure (keys) is identical.
        """
        if set(base_params.keys()) != set(current_params.keys()):
            return False
        return True

    def validate_batch_window(self, batch_id, start_time):
        """Checks if the batch has exceeded the 15-minute window."""
        now = datetime.now(timezone.utc)
        delta = now - start_time
        if delta.total_seconds() > (self.max_window_minutes * 60):
            return False, "Batch window expired"
        return True, "Window valid"

if __name__ == "__main__":
    bg = BatchGovernance()
    # Test valid batch
    batch = [
        {"tool": "web_write", "risk": "MEDIUM", "origin": "example.com", "schema": "web_v1", "params": {"id": 1}},
        {"tool": "web_write", "risk": "MEDIUM", "origin": "example.com", "schema": "web_v1", "params": {"id": 2}},
    ]
    valid, msg = bg.verify_batch_invariants(batch)
    print(f"Batch Valid: {valid} | Msg: {msg}")
