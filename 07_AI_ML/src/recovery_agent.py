from typing import Any, Dict, Optional, Union

# Whitelist of strictly approved recovery actions for MVP
SUPPORTED_ACTIONS = {
    "retry",
    "notify_and_retry",
    "suggest_alternative",
    "stop",
}


class RecoveryAgent:
    """Executes simulated payment recovery actions based on Decision Engine output.

    Separation of concerns:
    - Prediction Service = predicts recovery probability
    - Decision Engine = determines recommended decision/priority
    - Recovery Agent = executes controlled recovery action (simulated for MVP)
    """

    def validate_decision_input(self, decision_input: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Validate the incoming decision structure and action whitelist.

        Raises:
            ValueError: If input is malformed, missing required fields, or unsupported.
        """
        if decision_input is None:
            raise ValueError("Malformed decision input: input cannot be None")

        if isinstance(decision_input, str):
            decision_str = decision_input.strip()
            if not decision_str:
                raise ValueError("Malformed decision input: decision string cannot be empty")
            structured = {"decision": decision_str}
        elif isinstance(decision_input, dict):
            if "decision" not in decision_input:
                raise ValueError("Malformed decision input: missing required key 'decision'")
            decision_val = decision_input["decision"]
            if not isinstance(decision_val, str) or not decision_val.strip():
                raise ValueError(
                    f"Malformed decision input: 'decision' must be a non-empty string, got {decision_val!r}"
                )
            structured = dict(decision_input)
            structured["decision"] = decision_val.strip()
        else:
            raise ValueError(
                f"Malformed decision input: expected dict or str, got {type(decision_input).__name__}"
            )

        decision = structured["decision"]
        if decision not in SUPPORTED_ACTIONS:
            raise ValueError(
                f"Unsupported recovery decision: '{decision}'. Supported actions are: {sorted(SUPPORTED_ACTIONS)}"
            )

        return structured

    def execute(self, decision_input: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Execute the validated recovery action in a safe, simulated environment.

        Returns:
            Dict containing at minimum:
                - action: The executed action name
                - status: 'simulated' | 'skipped' | 'failed'
                - message: Human-readable execution summary
        """
        validated = self.validate_decision_input(decision_input)
        action = validated["decision"]

        # Deterministic simulated execution without real payment API calls
        if action == "retry":
            status = "simulated"
            message = "Payment retry simulated successfully"
            steps = ["retry_scheduled"]

        elif action == "notify_and_retry":
            status = "simulated"
            message = "Customer notification and payment retry simulated successfully"
            steps = ["customer_notification_sent", "retry_scheduled"]

        elif action == "suggest_alternative":
            status = "simulated"
            message = "Alternative payment method suggestion simulated successfully"
            steps = ["alternative_payment_methods_dispatched"]

        elif action == "stop":
            status = "skipped"
            message = "Recovery action skipped; process stopped"
            steps = ["recovery_halted"]

        else:
            # Defensive guard against future extensions
            raise ValueError(f"Unhandled action: '{action}'")

        result: Dict[str, Any] = {
            "action": action,
            "status": status,
            "message": message,
            "steps": steps,
        }

        # Preserve upstream decision metadata if present
        for optional_key in ("priority", "recovery_probability", "will_recover"):
            if optional_key in validated:
                result[optional_key] = validated[optional_key]

        return result


# Module-level singleton and convenience helper
_agent_instance: Optional[RecoveryAgent] = None


def get_recovery_agent() -> RecoveryAgent:
    """Retrieve or initialize singleton RecoveryAgent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = RecoveryAgent()
    return _agent_instance


def execute_recovery(decision_input: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """Convenience function to execute recovery action."""
    agent = get_recovery_agent()
    return agent.execute(decision_input)


if __name__ == "__main__":
    # Real example using the P5/P6 result
    p5_p6_result = {
        "recovery_probability": 0.9475,
        "will_recover": 1,
        "decision": "retry",
        "priority": "high",
    }

    print("=== RecoverAI Recovery Agent (Simulated Execution) ===")
    print("Input Decision Engine Result:")
    for k, v in p5_p6_result.items():
        print(f"  {k}: {v}")

    execution_result = execute_recovery(p5_p6_result)
    print("\nExecution Output:")
    print(f"  action:  {execution_result['action']}")
    print(f"  status:  {execution_result['status']}")
    print(f"  message: {execution_result['message']}")
    print(f"  steps:   {execution_result['steps']}")
