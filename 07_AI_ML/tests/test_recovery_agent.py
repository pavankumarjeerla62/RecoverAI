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

from src.recovery_agent import (
    RecoveryAgent,
    execute_recovery,
)


class TestRecoveryAgent(unittest.TestCase):
    def setUp(self):
        self.agent = RecoveryAgent()

    def test_retry_action(self):
        """Action 'retry' produces status 'simulated' with correct message and steps."""
        decision_input = {
            "decision": "retry",
            "priority": "high",
            "recovery_probability": 0.9475,
            "will_recover": 1,
        }
        result = self.agent.execute(decision_input)

        self.assertEqual(result["action"], "retry")
        self.assertEqual(result["status"], "simulated")
        self.assertIn("retry", result["message"].lower())
        self.assertEqual(result["priority"], "high")
        self.assertEqual(result["recovery_probability"], 0.9475)
        self.assertEqual(result["will_recover"], 1)

    def test_notify_and_retry_action(self):
        """Action 'notify_and_retry' produces status 'simulated' with notification and retry steps."""
        decision_input = {
            "decision": "notify_and_retry",
            "priority": "medium",
            "recovery_probability": 0.65,
            "will_recover": 1,
        }
        result = self.agent.execute(decision_input)

        self.assertEqual(result["action"], "notify_and_retry")
        self.assertEqual(result["status"], "simulated")
        self.assertIn("notification", result["message"].lower())
        self.assertIn("customer_notification_sent", result["steps"])
        self.assertIn("retry_scheduled", result["steps"])

    def test_suggest_alternative_action(self):
        """Action 'suggest_alternative' produces status 'simulated' with alternative suggestion."""
        decision_input = {
            "decision": "suggest_alternative",
            "priority": "low",
            "recovery_probability": 0.35,
            "will_recover": 0,
        }
        result = self.agent.execute(decision_input)

        self.assertEqual(result["action"], "suggest_alternative")
        self.assertEqual(result["status"], "simulated")
        self.assertIn("alternative", result["message"].lower())
        self.assertIn("alternative_payment_methods_dispatched", result["steps"])

    def test_stop_action(self):
        """Action 'stop' produces status 'skipped' and halts recovery."""
        decision_input = {"decision": "stop"}
        result = self.agent.execute(decision_input)

        self.assertEqual(result["action"], "stop")
        self.assertEqual(result["status"], "skipped")
        self.assertIn("skipped", result["message"].lower())
        self.assertIn("recovery_halted", result["steps"])

    def test_string_decision_input(self):
        """Accept raw action strings directly."""
        result = self.agent.execute("retry")
        self.assertEqual(result["action"], "retry")
        self.assertEqual(result["status"], "simulated")

    def test_invalid_unsupported_decision(self):
        """Unsupported decisions must be rejected with ValueError."""
        unsupported_decisions = ["refund", "chargeback", "escalate", "unknown"]
        for decision in unsupported_decisions:
            with self.subTest(decision=decision):
                with self.assertRaises(ValueError) as ctx:
                    self.agent.execute({"decision": decision})
                self.assertIn("Unsupported recovery decision", str(ctx.exception))

    def test_malformed_decision_input(self):
        """Malformed inputs (None, empty strings, wrong types, missing 'decision' key) must raise ValueError."""
        malformed_inputs = [
            None,
            "",
            "   ",
            {},
            {"priority": "high"},
            {"decision": None},
            {"decision": ""},
            {"decision": "   "},
            {"decision": 123},
            [1, 2, 3],
            42,
        ]
        for mal_input in malformed_inputs:
            with self.subTest(mal_input=mal_input):
                with self.assertRaises(ValueError):
                    self.agent.execute(mal_input)

    def test_convenience_execute_recovery_function(self):
        """Test top-level execute_recovery helper function."""
        result = execute_recovery({
            "decision": "retry",
            "priority": "high",
            "recovery_probability": 0.9475,
            "will_recover": 1,
        })
        self.assertEqual(result["action"], "retry")
        self.assertEqual(result["status"], "simulated")


if __name__ == "__main__":
    unittest.main()
