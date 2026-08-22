
# ============================================================
# Event Hubs namespace
# ============================================================

resource "azurerm_eventhub_namespace" "fraud" {
  name                = "evhns-northmart-fraud-dev"
  location            = "Central India"
  resource_group_name = "rg-dp750"

  sku      = "Standard"
  capacity = 1

  # Private access only
  public_network_access_enabled = false

  tags = {
    environment = "dev"
    workload    = "fraud-streaming"
  }
}


# ------------------------------------------------------------
# Kafka topic equivalent
# ------------------------------------------------------------

resource "azurerm_eventhub" "fraud_transactions" {
  name         = "fraud-transactions"
  namespace_id = azurerm_eventhub_namespace.fraud.id

  partition_count = 4

  retention_description {
    cleanup_policy          = "Delete"
    retention_time_in_hours = 24
  }
}

####
# Private DNS 
####
resource "azurerm_private_dns_zone" "eventhub" {
  name                = "privatelink.servicebus.windows.net"
  resource_group_name = "rg-dp750"
}

####
#Private Endpoint pour le namespace dans le subnet dédié aux endpoints
####
resource "azurerm_private_endpoint" "fraud_eventhub" {
  name                = "pe-northmart-eventhub-fraud"
  location            = "Central India"
  resource_group_name = "rg-dp750"

  subnet_id = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "psc-northmart-eventhub-fraud"
    private_connection_resource_id = azurerm_eventhub_namespace.fraud.id

    subresource_names    = ["namespace"]
    is_manual_connection = false
  }

  private_dns_zone_group {
    name = "default"

    private_dns_zone_ids = [
      azurerm_private_dns_zone.eventhub.id
    ]
  }
}

resource "azurerm_private_dns_zone_virtual_network_link" "eventhub" {
  name                = "link-northmart-eventhub"
  private_dns_zone_id = azurerm_private_dns_zone.eventhub.id
  virtual_network_id  = azurerm_virtual_network.northmart_databricks.id

  registration_enabled = false
}

# ------------------------------------------------------------
# Consumer group used by Databricks
# ------------------------------------------------------------

resource "azurerm_eventhub_consumer_group" "databricks_fraud" {
  name                = "databricks-fraud"
  namespace_name      = azurerm_eventhub_namespace.fraud.name
  eventhub_name       = azurerm_eventhub.fraud_transactions.name
  resource_group_name = "rg-dp750"
}


# ------------------------------------------------------------
# Producer credential
# Python simulator can SEND but cannot LISTEN / Shared Assess policies
# ------------------------------------------------------------

resource "azurerm_eventhub_authorization_rule" "fraud_producer" {
  name                = "fraud-producer"
  namespace_name      = azurerm_eventhub_namespace.fraud.name
  eventhub_name       = azurerm_eventhub.fraud_transactions.name
  resource_group_name = "rg-dp750"

  send   = true
  listen = false
  manage = false
}


# ------------------------------------------------------------
# Databricks consumer credential
# Can LISTEN but cannot SEND /Shared Assess policies
# ------------------------------------------------------------

resource "azurerm_eventhub_authorization_rule" "fraud_databricks_consumer" {
  name                = "fraud-databricks-consumer"
  namespace_name      = azurerm_eventhub_namespace.fraud.name
  eventhub_name       = azurerm_eventhub.fraud_transactions.name
  resource_group_name = "rg-dp750"

  send   = false
  listen = true
  manage = false
}


