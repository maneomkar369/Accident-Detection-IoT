"""
detector.py — AI-powered crash detection using the trained ML model.

Loads model/crash_model.pkl (trained on your sensor_data.csv)
and classifies each reading as CRASH (1) or NORMAL (0).

Works alongside the threshold-based mpu6050_driver.py:
  - Threshold check   → fast, hardware-level, catches obvious impacts
  - ML model check    → smart, reduces false positives from bumps/potholes
Both must agree before triggering the emergency flow.
"""

import os
import sys
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

# Allow running from any directory
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "pi_system"))

from config import ML_MODEL_PATH


class CrashDetector:
    """
    Wraps the trained RandomForest / GradientBoosting model for inference.

    Expected input per reading: [x, y, z, mag, mag_mean_5, mag_std_5]
    (matches the features generated during training in improve_accuracy.py)
    """

    def __init__(self):
        model_path = _root / ML_MODEL_PATH
        if not model_path.exists():
            raise FileNotFoundError(
                f"ML model not found at {model_path}. "
                "Run improve_accuracy.py first to train the model."
            )
        self.model = joblib.load(model_path)
        self._history = []      # rolling buffer for mag_mean_5 / mag_std_5
        self._BUFFER_SIZE = 5
        print(f"[Detector] ✅ ML model loaded from {model_path}")

    def _compute_mag(self, x: float, y: float, z: float) -> float:
        return float(np.sqrt(x**2 + y**2 + z**2))

    def _rolling_stats(self, mag: float):
        """Keep a 5-sample rolling window and return (mean, std)."""
        self._history.append(mag)
        if len(self._history) > self._BUFFER_SIZE:
            self._history.pop(0)
        arr = np.array(self._history)
        return float(arr.mean()), float(arr.std()) if len(arr) > 1 else 0.0

    def _make_features(self, x, y, z):
        mag = self._compute_mag(x, y, z)
        mag_mean, mag_std = self._rolling_stats(mag)
        return pd.DataFrame([[x, y, z, mag, mag_mean, mag_std]],
                            columns=['x', 'y', 'z', 'mag', 'mag_mean_5', 'mag_std_5'])

    def predict(self, x: float, y: float, z: float) -> bool:
        """Returns True if the ML model classifies this reading as a CRASH."""
        df = self._make_features(x, y, z)
        return bool(self.model.predict(df)[0] == 1)

    def predict_proba(self, x: float, y: float, z: float) -> float:
        """Returns crash probability (0.0–1.0)."""
        try:
            df = self._make_features(x, y, z)
            return float(self.model.predict_proba(df)[0][1])
        except AttributeError:
            return 1.0 if self.predict(x, y, z) else 0.0
