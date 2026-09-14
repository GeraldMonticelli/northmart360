def is_high_value_transaction(amount: float, threshold: float = 5000.0) -> bool:
    """Return True when the transaction amount exceeds the fraud threshold."""
    return amount > threshold