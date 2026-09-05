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

from src.decision_engine import (
    DecisionEngine,
    evaluate_prediction,
    make_decision,
)


class TestDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()

    def test_probability_greater_than_eighty(self):
        """Probability > 0.80 should map to retry and high priority."""
        for prob in [0.8001, 0.85, 0.9475, 1.0]:
            with self.subTest(prob=prob):
                res = self.engine.decide(recovery_probability=prob, will_recover=1)
                self.assertEqual(res["decision"], "retry")
                self.assertEqual(res["priority"], "high")
                self.assertEqual(res["recovery_probability"], round(prob, 4))
                self.assertEqual(res["will_recover"], 1)

    def test_probability_exactly_eighty(self):
        """Probability exactly 0.80 should map to notify_and_retry and medium priority."""
        res = self.engine.decide(recovery_probability=0.80, will_recover=1)
        self.assertEqual(res["decision"], "notify_and_retry")
        self.assertEqual(res["priority"], "medium")
        self.assertEqual(res["recovery_probability"], 0.80)
        self.assertEqual(res["will_recover"], 1)

    def test_probability_between_fifty_and_eighty(self):
        """Probability strictly between 0.50 and 0.80 should map to notify_and_retry and medium priority."""
        for prob in [0.5001, 0.60, 0.75, 0.7999]:
            with self.subTest(prob=prob):
                res = self.engine.decide(recovery_probability=prob, will_recover=1)
                self.assertEqual(res["decision"], "notify_and_retry")
                self.assertEqual(res["priority"], "medium")
                self.assertEqual(res["recovery_probability"], round(prob, 4))

    def test_probability_exactly_fifty(self):
        """Probability exactly 0.50 should map to notify_and_retry and medium priority."""
        res = self.engine.decide(recovery_probability=0.50, will_recover=1)
        self.assertEqual(res["decision"], "notify_and_retry")
        self.assertEqual(res["priority"], "medium")
        self.assertEqual(res["recovery_probability"], 0.50)
        self.assertEqual(res["will_recover"], 1)

    def test_probability_less_than_fifty(self):
        """Probability < 0.50 should map to suggest_alternative and low priority."""
        for prob in [0.4999, 0.35, 0.10, 0.0]:
            with self.subTest(prob=prob):
                res = self.engine.decide(recovery_probability=prob, will_recover=0)
                self.assertEqual(res["decision"], "suggest_alternative")
                self.assertEqual(res["priority"], "low")
                self.assertEqual(res["recovery_probability"], round(prob, 4))
                self.assertEqual(res["will_recover"], 0)

    def test_invalid_probability_raises_value_error(self):
        """Invalid probabilities (out of range, non-numeric, None, bool) must raise ValueError."""
        invalid_probabilities = [-0.01, -1.0, 1.01, 2.5, "high", None, True, False, [0.5]]
        for inv_prob in invalid_probabilities:
            with self.subTest(inv_prob=inv_prob):
                with self.assertRaises(ValueError):
                    self.engine.decide(recovery_probability=inv_prob, will_recover=1)

    def test_invalid_will_recover_raises_value_error(self):
        """will_recover values other than 0 or 1 must raise ValueError."""
        invalid_will_rec = [-1, 2, 5, "yes", "true", None, [1]]
        for inv_val in invalid_will_rec:
            with self.subTest(inv_val=inv_val):
                with self.assertRaises(ValueError):
                    self.engine.decide(recovery_probability=0.85, will_recover=inv_val)

    def test_convenience_functions(self):
        """Test module-level make_decision and evaluate_prediction."""
        res1 = make_decision(0.9475, 1)
        self.assertEqual(res1["decision"], "retry")
        self.assertEqual(res1["priority"], "high")

        prediction_dict = {"recovery_probability": 0.35, "will_recover": 0}
        res2 = evaluate_prediction(prediction_dict)
        self.assertEqual(res2["decision"], "suggest_alternative")
        self.assertEqual(res2["priority"], "low")


if __name__ == "__main__":
    unittest.main()
