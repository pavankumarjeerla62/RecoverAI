from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import joblib
import pandas as pd

# Default project-relative paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "07_AI_ML" / "models" / "recovery_model.pkl"

# Feature definitions aligned with training schema
NUMERICAL_FEATURES = [
    "amount",
    "customer_success_rate",
    "previous_retries",
    "retry_success_rate",
    "time_since_failure",
]

CATEGORICAL_FEATURES = [
    "failure_reason",
    "payment_method",
    "recovery_action",
]

REQUIRED_FEATURES = set(NUMERICAL_FEATURES + CATEGORICAL_FEATURES)


class RecoveryPredictionService:
    """Production prediction service for RecoverAI payment recovery probability."""

    def __init__(self, model_path: Optional[Union[str, Path]] = None) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self._pipeline = None
        self._load_model()

    def _load_model(self) -> None:
        """Safely load the trained scikit-learn Pipeline from disk."""
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Trained recovery model not found at '{self.model_path}'. "
                "Ensure P4 training has completed (run train_model.py)."
            )
        try:
            self._pipeline = joblib.load(self.model_path)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load recovery model from '{self.model_path}': {exc}"
            ) from exc

    def validate_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input payload for missing fields and valid feature ranges."""
        if not isinstance(data, dict):
            raise ValueError(f"Input data must be a dictionary, got {type(data).__name__}")

        missing = REQUIRED_FEATURES - set(data.keys())
        if missing:
            raise ValueError(f"Missing required feature(s): {sorted(missing)}")

        validated: Dict[str, Any] = {}

        # Validate numerical features
        for num_col in NUMERICAL_FEATURES:
            val = data[num_col]
            if val is None or isinstance(val, bool):
                raise ValueError(f"Feature '{num_col}' must be numeric, got {val!r}")
            try:
                num_val = float(val)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Feature '{num_col}' cannot be converted to float: {val!r}") from exc

            if num_col == "amount" and num_val <= 0:
                raise ValueError(f"Feature 'amount' must be positive, got {num_val}")
            if num_col in ("customer_success_rate", "retry_success_rate") and not (0.0 <= num_val <= 1.0):
                raise ValueError(f"Feature '{num_col}' must be between 0.0 and 1.0, got {num_val}")
            if num_col == "previous_retries" and num_val < 0:
                raise ValueError(f"Feature 'previous_retries' must be non-negative, got {num_val}")
            if num_col == "time_since_failure" and num_val < 0:
                raise ValueError(f"Feature 'time_since_failure' must be non-negative, got {num_val}")

            validated[num_col] = int(num_val) if num_col == "previous_retries" else num_val

        # Validate categorical features
        for cat_col in CATEGORICAL_FEATURES:
            val = data[cat_col]
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Feature '{cat_col}' must be a non-empty string, got {val!r}")
            validated[cat_col] = val.strip()

        return validated

    def predict(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recovery prediction for a single payment event.

        Returns:
            Dict containing:
                - recovery_probability (float): Probability that the payment will recover (0.0 to 1.0).
                - will_recover (int): Binary prediction (1 = will recover, 0 = will not recover).
        """
        validated = self.validate_features(payment_data)

        # Convert to single-row DataFrame matching the training schema
        df = pd.DataFrame([validated])

        try:
            # Predict using the loaded Pipeline (identical preprocessing & classification)
            proba = self._pipeline.predict_proba(df)[0]
            prediction = self._pipeline.predict(df)[0]

            # In scikit-learn binary classification, classes_ are typically [0, 1]
            pos_idx = list(self._pipeline.classes_).index(1) if 1 in self._pipeline.classes_ else 1
            recovery_prob = float(proba[pos_idx])
            will_rec = int(prediction)

            return {
                "recovery_probability": round(recovery_prob, 4),
                "will_recover": will_rec,
            }
        except Exception as exc:
            raise RuntimeError(f"Prediction service execution failed: {exc}") from exc


# Module-level convenience function and singleton
_service_instance: Optional[RecoveryPredictionService] = None


def get_prediction_service(model_path: Optional[Union[str, Path]] = None) -> RecoveryPredictionService:
    """Retrieve or initialize the singleton RecoveryPredictionService."""
    global _service_instance
    if _service_instance is None or model_path is not None:
        _service_instance = RecoveryPredictionService(model_path=model_path)
    return _service_instance


def predict_recovery(payment_data: Dict[str, Any], model_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Convenience function to obtain recovery prediction."""
    service = get_prediction_service(model_path=model_path)
    return service.predict(payment_data)


if __name__ == "__main__":
    # Real sample demonstration
    sample_payment = {
        "amount": 1200.0,
        "failure_reason": "insufficient_funds",
        "payment_method": "card",
        "customer_success_rate": 0.85,
        "previous_retries": 1,
        "retry_success_rate": 0.75,
        "time_since_failure": 30.0,
        "recovery_action": "retry",
    }

    print("=== RecoverAI Recovery Prediction Service ===")
    print("Input Payment Features:")
    for k, v in sample_payment.items():
        print(f"  {k}: {v}")

    result = predict_recovery(sample_payment)
    print("\nPrediction Result:")
    print(f"  recovery_probability: {result['recovery_probability']}")
    print(f"  will_recover:         {result['will_recover']}")
