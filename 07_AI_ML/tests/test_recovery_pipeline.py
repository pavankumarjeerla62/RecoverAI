import sys
from pathlib import Path
from unittest.mock import MagicMock
import unittest

# Ensure project root and 07_AI_ML are importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
AI_ML_DIR = PROJECT_ROOT / "07_AI_ML"
if str(AI_ML_DIR) not in sys.path:
    sys.path.insert(0, str(AI_ML_DIR))

from src.decision_engine import DecisionEngine
from src.prediction_service import RecoveryPredictionService
from src.recovery_agent import RecoveryAgent
from src.recovery_pipeline import (
    RecoveryPipeline,
    run_recovery_pipeline,
)


class TestRecoveryPipeline(unittest.TestCase):
    def setUp(self):
        # Real components without mocking
        self.pipeline = RecoveryPipeline()

        self.high_probability_payment = {
            "amount": 1200.0,
            "failure_reason": "insufficient_funds",
            "payment_method": "card",
            "customer_success_rate": 0.85,
            "previous_retries": 1,
            "retry_success_rate": 0.75,
            "time_since_failure": 30.0,
            "recovery_action": "retry",
        }

        self.low_probability_payment = {
            "amount": 5000.0,
            "failure_reason": "card_declined",
            "payment_method": "card",
            "customer_success_rate": 0.25,
            "previous_retries": 3,
            "retry_success_rate": 0.05,
            "time_since_failure": 300.0,
            "recovery_action": "alternative",
        }

    def test_end_to_end_retry_flow_real_components(self):
        """Happy path: Real P5 model + Real P6 Decision Engine + Real P7 Recovery Agent."""
        result = self.pipeline.run(self.high_probability_payment)

        # 1. Structure check
        self.assertIn("prediction", result)
        self.assertIn("decision", result)
        self.assertIn("execution", result)

        # 2. Prediction check
        self.assertAlmostEqual(result["prediction"]["recovery_probability"], 0.9475, places=2)
        self.assertEqual(result["prediction"]["will_recover"], 1)

        # 3. Decision check
        self.assertEqual(result["decision"]["decision"], "retry")
        self.assertEqual(result["decision"]["priority"], "high")

        # 4. Execution check
        self.assertEqual(result["execution"]["action"], "retry")
        self.assertEqual(result["execution"]["status"], "simulated")
        self.assertIn("retry", result["execution"]["message"].lower())

    def test_end_to_end_suggest_alternative_flow_real_components(self):
        """Happy path: Low recovery probability leads to alternative payment suggestion."""
        result = self.pipeline.run(self.low_probability_payment)

        self.assertLess(result["prediction"]["recovery_probability"], 0.50)
        self.assertEqual(result["prediction"]["will_recover"], 0)
        self.assertEqual(result["decision"]["decision"], "suggest_alternative")
        self.assertEqual(result["decision"]["priority"], "low")
        self.assertEqual(result["execution"]["action"], "suggest_alternative")
        self.assertEqual(result["execution"]["status"], "simulated")

    def test_notify_and_retry_flow(self):
        """Medium probability (0.50 <= p <= 0.80) orchestrates to notify_and_retry."""
        mock_pred = MagicMock()
        mock_pred.predict.return_value = {
            "recovery_probability": 0.65,
            "will_recover": 1,
        }
        pipeline = RecoveryPipeline(
            prediction_service=mock_pred,
            decision_engine=DecisionEngine(),
            recovery_agent=RecoveryAgent(),
        )

        result = pipeline.run(self.high_probability_payment)
        self.assertEqual(result["prediction"]["recovery_probability"], 0.65)
        self.assertEqual(result["decision"]["decision"], "notify_and_retry")
        self.assertEqual(result["decision"]["priority"], "medium")
        self.assertEqual(result["execution"]["action"], "notify_and_retry")
        self.assertEqual(result["execution"]["status"], "simulated")

    def test_stop_flow(self):
        """Decision 'stop' safely results in skipped execution."""
        mock_pred = MagicMock()
        mock_pred.predict.return_value = {
            "recovery_probability": 0.10,
            "will_recover": 0,
        }
        mock_dec = MagicMock()
        mock_dec.decide_from_prediction.return_value = {
            "decision": "stop",
            "priority": "low",
            "recovery_probability": 0.10,
            "will_recover": 0,
        }
        pipeline = RecoveryPipeline(
            prediction_service=mock_pred,
            decision_engine=mock_dec,
            recovery_agent=RecoveryAgent(),
        )

        result = pipeline.run(self.low_probability_payment)
        self.assertEqual(result["decision"]["decision"], "stop")
        self.assertEqual(result["execution"]["action"], "stop")
        self.assertEqual(result["execution"]["status"], "skipped")

    def test_invalid_payment_input_fails_before_execution(self):
        """Invalid payment data must raise ValueError in prediction and abort execution."""
        mock_agent = MagicMock()
        pipeline = RecoveryPipeline(
            prediction_service=self.pipeline.prediction_service,
            decision_engine=self.pipeline.decision_engine,
            recovery_agent=mock_agent,
        )

        invalid_payment = dict(self.high_probability_payment, amount=-200.0)
        with self.assertRaises(ValueError):
            pipeline.run(invalid_payment)

        # Agent execute must never have been called
        mock_agent.execute.assert_not_called()

    def test_failure_before_recovery_execution(self):
        """If prediction service fails, recovery agent must never be invoked."""
        mock_pred = MagicMock()
        mock_pred.predict.side_effect = RuntimeError("Prediction computation error")
        mock_agent = MagicMock()

        pipeline = RecoveryPipeline(
            prediction_service=mock_pred,
            decision_engine=self.pipeline.decision_engine,
            recovery_agent=mock_agent,
        )

        with self.assertRaises(RuntimeError):
            pipeline.run(self.high_probability_payment)

        mock_agent.execute.assert_not_called()

    def test_convenience_run_recovery_pipeline_function(self):
        """Test module-level run_recovery_pipeline convenience function."""
        result = run_recovery_pipeline(self.high_probability_payment)
        self.assertEqual(result["decision"]["decision"], "retry")
        self.assertEqual(result["execution"]["status"], "simulated")


if __name__ == "__main__":
    unittest.main()
