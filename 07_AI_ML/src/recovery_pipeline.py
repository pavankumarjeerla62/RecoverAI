from typing import Any, Dict, Optional
from .decision_engine import DecisionEngine, get_decision_engine
from .prediction_service import RecoveryPredictionService, get_prediction_service
from .recovery_agent import RecoveryAgent, get_recovery_agent


class RecoveryPipeline:
    """End-to-end orchestration layer for RecoverAI AI/ML.

    Orchestrates the sequential lifecycle:
      Payment Input → Prediction Service (P5)
                    → Decision Engine (P6)
                    → Recovery Agent (P7)
                    → Final Structured Result

    Strict separation of concerns:
      - Prediction Service: computes recovery probability & outcome
      - Decision Engine: evaluates probability to choose action & priority
      - Recovery Agent: safely executes the approved simulated action
    """

    def __init__(
        self,
        prediction_service: Optional[RecoveryPredictionService] = None,
        decision_engine: Optional[DecisionEngine] = None,
        recovery_agent: Optional[RecoveryAgent] = None,
    ) -> None:
        self.prediction_service = prediction_service or get_prediction_service()
        self.decision_engine = decision_engine or get_decision_engine()
        self.recovery_agent = recovery_agent or get_recovery_agent()

    def run(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the complete recovery orchestration on a raw payment payload.

        Args:
            payment_data: Dictionary of 8 payment feature values required by P5.

        Returns:
            Dict containing:
                - prediction: {recovery_probability, will_recover}
                - decision: {decision, priority}
                - execution: {action, status, message}

        Raises:
            ValueError: If input validation fails or an unsupported decision is encountered.
            RuntimeError: If prediction or execution encounters an internal error.
        """
        # Step 1: Prediction Service (Validates inputs and computes recovery probability)
        # Any invalid input or prediction failure raises here, strictly halting the pipeline.
        prediction_res = self.prediction_service.predict(payment_data)

        # Step 2: Decision Engine (Determines business recovery action and priority)
        # Decision failures will halt before reaching the agent.
        decision_res = self.decision_engine.decide_from_prediction(prediction_res)

        # Step 3: Recovery Agent (Executes the approved recovery action in simulation)
        # Validates decision whitelist before dispatching simulation.
        execution_res = self.recovery_agent.execute(decision_res)

        # Step 4: Return clean, unified structured result
        return {
            "prediction": {
                "recovery_probability": prediction_res["recovery_probability"],
                "will_recover": prediction_res["will_recover"],
            },
            "decision": {
                "decision": decision_res["decision"],
                "priority": decision_res["priority"],
            },
            "execution": {
                "action": execution_res["action"],
                "status": execution_res["status"],
                "message": execution_res["message"],
            },
        }


# Module-level singleton and convenience helper
_pipeline_instance: Optional[RecoveryPipeline] = None


def get_recovery_pipeline() -> RecoveryPipeline:
    """Retrieve or initialize the singleton RecoveryPipeline."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = RecoveryPipeline()
    return _pipeline_instance


def run_recovery_pipeline(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute end-to-end recovery pipeline on payment data."""
    pipeline = get_recovery_pipeline()
    return pipeline.run(payment_data)


if __name__ == "__main__":
    import json

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

    print("=== RecoverAI End-to-End Recovery Pipeline (P8) ===")
    print("Input Payment Data:")
    print(json.dumps(sample_payment, indent=2))

    pipeline_result = run_recovery_pipeline(sample_payment)

    print("\nFinal Pipeline Result:")
    print(json.dumps(pipeline_result, indent=2))
