from src.quality.fraud_rules import is_high_value_transaction


def test_high_value_transaction():
    assert is_high_value_transaction(6000.0) is True


def test_normal_transaction():
    assert is_high_value_transaction(1000.0) is False


def test_transaction_at_threshold():
    assert is_high_value_transaction(5000.0) is False