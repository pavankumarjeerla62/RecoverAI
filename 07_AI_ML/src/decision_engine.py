from typing import Any, Dict, Optional, Union


class DecisionEngine:
    """Evaluates ML recovery predictions to produce deterministic action decisions."""

    @staticmethod
    def validate_inputs(
        recovery_probability: Any, will_recover: Any
    ) -> tuple[float, int]:
        """Validate recovery prediction inputs.

        Raises:
            ValueError: If recovery_probability or will_recover are invalid.
            TypeError: If types are non-numeric or incompatible.
        """
        # Validate recovery_probability
        if recovery_probability is None or isinstance(recovery_probability, bool):
            raise ValueError(
                f"recovery_probability must be a numeric value, got {type(recovery_probability).__name__}"
            )

        try:
            prob = float(recovery_probability)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"recovery_probability must be numeric, got {recovery_probability!r}"
            ) from exc

        if not (0.0 <= prob <= 1.0):
            raise ValueError(
                f"recovery_probability must be between 0.0 and 1.0, got {prob}"
            )

        # Validate will_recover
        if will_recover is None:
            raise ValueError("will_recover cannot be None")

        if isinstance(will_recover, bool):
            will_rec = int(will_recover)
        elif isinstance(will_recover, (int, float)):
            if will_recover not in (0, 1, 0.0, 1.0):
                raise ValueError(
                    f"will_recover must be 0 or 1, got {will_recover!r}"
                )
            will_rec = int(will_recover)
        else:
            raise ValueError(
                f"will_recover must be 0 or 1, got {will_recover!r}"
            )

        return prob, will_rec

    def decide(
        self,
        recovery_probability: Union[float, int],
        will_recover: Union[int, bool],
    ) -> Dict[str, Any]:
        """Evaluate prediction values and return action decision and priority.

        Decision Rules:
            - recovery_probability > 0.80:
                decision = "retry", priority = "high"
            - 0.50 <= recovery_probability <= 0.80:
                decision = "notify_and_retry", priority = "medium"
            - recovery_probability < 0.50:
                decision = "suggest_alternative", priority = "low"

        Returns:
            Dict containing:
                - decision (str)
                - priority (str)
                - recovery_probability (float)
                - will_recover (int)
        """
        prob, will_rec = self.validate_inputs(recovery_probability, will_recover)

        if prob > 0.80:
            decision = "retry"
            priority = "high"
        elif prob >= 0.50:
            decision = "notify_and_retry"
            priority = "medium"
        else:
            decision = "suggest_alternative"
            priority = "low"

        return {
            "decision": decision,
            "priority": priority,
            "recovery_probability": round(prob, 4),
            "will_recover": will_rec,
        }

    def decide_from_prediction(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience method accepting the dictionary output of the prediction service."""
        if not isinstance(prediction, dict):
            raise ValueError(
                f"Prediction input must be a dictionary, got {type(prediction).__name__}"
            )
        if "recovery_probability" not in prediction or "will_recover" not in prediction:
            raise ValueError(
                "Prediction dictionary must contain 'recovery_probability' and 'will_recover'"
            )
        return self.decide(
            recovery_probability=prediction["recovery_probability"],
            will_recover=prediction["will_recover"],
        )


# Module-level convenience functions
_engine_instance: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Retrieve or initialize the singleton DecisionEngine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DecisionEngine()
    return _engine_instance


def make_decision(
    recovery_probability: Union[float, int],
    will_recover: Union[int, bool],
) -> Dict[str, Any]:
    """Evaluate prediction values and return structured decision."""
    engine = get_decision_engine()
    return engine.decide(recovery_probability, will_recover)


def evaluate_prediction(prediction: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate prediction dictionary directly."""
    engine = get_decision_engine()
    return engine.decide_from_prediction(prediction)


if __name__ == "__main__":
    # Real example using the P5 prediction output
    sample_prediction = {
        "recovery_probability": 0.9475,
        "will_recover": 1,
    }

    print("=== RecoverAI Decision Engine ===")
    print("Input Prediction:")
    print(f"  recovery_probability: {sample_prediction['recovery_probability']}")
    print(f"  will_recover:         {sample_prediction['will_recover']}")

    decision_result = evaluate_prediction(sample_prediction)
    print("\nDecision Output:")
    print(f"  decision:             {decision_result['decision']}")
    print(f"  priority:             {decision_result['priority']}")
    print(f"  recovery_probability: {decision_result['recovery_probability']}")
    print(f"  will_recover:         {decision_result['will_recover']}")
