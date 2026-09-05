import sys
from pathlib import Path
import unittest

# Ensure project root and 07_AI_ML are importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
AI_ML_DIR = PROJECT_ROOT / "07_AI_ML"
if str(AI_ML_DIR) not in sys.path:
    sys.path.insert(0, str(AI_ML_DIR))

from src.prediction_service import (
    RecoveryPredictionService,
    predict_recovery,
)


class TestRecoveryPredictionService(unittest.TestCase):
    def setUp(self):
        self.service = RecoveryPredictionService()
        self.valid_input = {
            "amount": 1200.0,
            "failure_reason": "insufficient_funds",
            "payment_method": "card",
            "customer_success_rate": 0.85,
            "previous_retries": 1,
            "retry_success_rate": 0.75,
            "time_since_failure": 30.0,
            "recovery_action": "retry",
        }

    def test_valid_prediction_output_structure(self):
        """Test that a valid payment input produces recovery_probability and will_recover."""
        result = self.service.predict(self.valid_input)

        self.assertIsInstance(result, dict)
        self.assertIn("recovery_probability", result)
        self.assertIn("will_recover", result)

        self.assertIsInstance(result["recovery_probability"], float)
        self.assertGreaterEqual(result["recovery_probability"], 0.0)
        self.assertLessEqual(result["recovery_probability"], 1.0)

        self.assertIn(result["will_recover"], (0, 1))

    def test_convenience_predict_recovery_function(self):
        """Test the top-level predict_recovery convenience function."""
        result = predict_recovery(self.valid_input)
        self.assertIn("recovery_probability", result)
        self.assertIn("will_recover", result)
        self.assertEqual(result["will_recover"], 1)

    def test_missing_feature_raises_value_error(self):
        """Test that omission of any required feature raises ValueError."""
        incomplete_input = dict(self.valid_input)
        del incomplete_input["amount"]

        with self.assertRaises(ValueError) as ctx:
            self.service.predict(incomplete_input)
        self.assertIn("Missing required feature", str(ctx.exception))

    def test_invalid_amount_raises_value_error(self):
        """Test that negative or zero amount raises ValueError."""
        invalid_input = dict(self.valid_input, amount=-500.0)
        with self.assertRaises(ValueError) as ctx:
            self.service.predict(invalid_input)
        self.assertIn("amount", str(ctx.exception))

    def test_invalid_success_rate_raises_value_error(self):
        """Test that rate outside [0.0, 1.0] raises ValueError."""
        invalid_input = dict(self.valid_input, customer_success_rate=1.5)
        with self.assertRaises(ValueError) as ctx:
            self.service.predict(invalid_input)
        self.assertIn("customer_success_rate", str(ctx.exception))

    def test_missing_model_path_raises_file_not_found(self):
        """Test that non-existent model path raises FileNotFoundError."""
        non_existent_path = PROJECT_ROOT / "07_AI_ML" / "models" / "non_existent.pkl"
        with self.assertRaises(FileNotFoundError):
            RecoveryPredictionService(model_path=non_existent_path)


if __name__ == "__main__":
    unittest.main()
