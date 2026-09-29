import pynvml
import time
import logging
from typing import Dict, Any

class ResourceGovernor:
    """
    Implements VRAM monitoring and Adaptive Model Routing as per Spec V2.4.
    Ensures system stability by throttling execution when VRAM > 85%.
    """
    def __init__(self, vram_threshold=0.85):
        self.vram_threshold = vram_threshold
        try:
            pynvml.nvmlInit()
            self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception as e:
            logging.warning(f"NVML initialization failed: {e}. Falling back to mock monitoring.")
            self.gpu_handle = None

    def get_vram_utilization(self) -> float:
        """Returns current VRAM utilization as a float (0.0 to 1.0)."""
        if not self.gpu_handle:
            return 0.0 # Mocked

        info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
        used = info.used
        total = info.total
        return used / total

    def should_throttle(self) -> bool:
        """Checks if VRAM usage exceeds the defined threshold."""
        return self.get_vram_utilization() > self.vram_threshold

    def route_model(self, task_risk: str, confidence: float) -> str:
        """
        Adaptive Model Routing Logic:
        - Routine (LOW risk, High confidence) -> 1B-3B Models
        - Complex/High-Risk/Low-Confidence -> Heavy Models
        """
        if task_risk == "LOW" and confidence >= 0.8:
            return "small-model-1b-3b"

        return "heavy-reasoning-model"

    def __del__(self):
        try:
            pynvml.nvmlShutdown()
        except:
            pass

if __name__ == "__main__":
    gov = ResourceGovernor()
    print(f"Current VRAM Utilization: {gov.get_vram_utilization():.2%}")
    print(f"Route (LOW, 0.9): {gov.route_model('LOW', 0.9)}")
    print(f"Route (HIGH, 0.5): {gov.route_model('HIGH', 0.5)}")
