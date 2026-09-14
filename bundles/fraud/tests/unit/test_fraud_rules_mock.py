from unittest.mock import Mock

from src.quality.fraud_rules_mock import is_high_value_transaction


def test_high_value_transaction_with_mock():
    # Arrange
    config_client = Mock()
    config_client.get.return_value = "5000"

    # Act
    result = is_high_value_transaction(6000, config_client)

    # Assert
    assert result is True
    config_client.get.assert_called_once_with("fraud_threshold")