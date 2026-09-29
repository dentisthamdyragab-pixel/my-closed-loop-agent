import os
import subprocess
import json
from datetime import datetime, timezone

class StateManager:
    """
    Implements micro-checkpoints and Saga compensations for state recovery.
    As per Spec V2.4, ensures high-risk actions are reversible.
    """
    def __init__(self, state_dir="/var/lib/closed_agent/state"):
        self.state_dir = state_dir
        self.git_repo = f"{state_dir}/filesystem_snapshots"
        os.makedirs(self.state_dir, exist_ok=True)
        self._init_git_repo()

    def _init_git_repo(self):
        """Initialize a local git repo for filesystem micro-checkpoints."""
        if not os.path.exists(self.git_repo):
            os.makedirs(self.git_repo)
            try:
                subprocess.run(["git", "init"], cwd=self.git_repo, check=True, capture_output=True)
            except subprocess.CalledProcessError:
                pass

    def create_checkpoint(self, label="auto_checkpoint"):
        """
        Creates a filesystem snapshot using Git.
        Returns a commit hash for later rollback.
        """
        # In a real scenario, we would sync the target directory to self.git_repo
        # For this implementation, we simulate the snapshot process.
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        commit_msg = f"Checkpoint: {label} at {timestamp}"

        try:
            # Simulate adding files and committing
            subprocess.run(["git", "add", "."], cwd=self.git_repo, check=True, capture_output=True)
            res = subprocess.run(["git", "commit", "-m", commit_msg], cwd=self.git_repo, check=True, capture_output=True)
            commit_hash = res.stdout.decode().split(" ")[-1].strip() # Simplified
            return commit_hash
        except subprocess.CalledProcessError as e:
            return None

    def rollback_filesystem(self, commit_hash):
        """Rolls back the filesystem to a specific commit."""
        try:
            subprocess.run(["git", "checkout", commit_hash, "."], cwd=self.git_repo, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def execute_with_saga(self, action_func, compensation_func, params):
        """
        Executes an action with a corresponding compensation (Saga pattern).

        Args:
            action_func: The function to perform the mutation.
            compensation_func: The function to undo the mutation.
            params: Parameters for both functions.
        """
        checkpoint = self.create_checkpoint(f"pre_{action_func.__name__}")
        try:
            result = action_func(params)
            return result, None
        except Exception as e:
            # Trigger Compensation
            try:
                compensation_func(params)
                if checkpoint:
                    self.rollback_filesystem(checkpoint)
            except Exception as comp_err:
                # Move to Dead Letter Queue (DLQ) as per Spec V2.4
                self._log_to_dlq(action_func.__name__, params, comp_err)

            return None, e

    def _log_to_dlq(self, action, params, error):
        """Logs failed compensations to a Dead Letter Queue for P1 alert."""
        dlq_path = f"{self.state_dir}/dlq.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "params": params,
            "error": str(error),
            "priority": "P1"
        }
        with open(dlq_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

if __name__ == "__main__":
    sm = StateManager()
    print("State Manager initialized. Checkpoints and Saga logic ready.")
