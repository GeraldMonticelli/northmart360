def get_fraud_threshold(config_client) -> float:
    """Read the fraud threshold from an external configuration provider."""
    return float(config_client.get("fraud_threshold"))


def is_high_value_transaction(amount: float, config_client) -> bool:
    threshold = get_fraud_threshold(config_client)
    return amount > threshold