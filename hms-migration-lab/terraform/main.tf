############################
# Azure resources
############################

resource "azurerm_storage_container" "legacy_hms" {
  name                  = "legacy-hms"
  storage_account_id    = data.azurerm_storage_account.northmart_dev.id
  container_access_type = "private"
}

resource "azurerm_postgresql_flexible_server" "hms" {
  name                = "psql-northmart-hms-dev"
  resource_group_name = data.azurerm_resource_group.northmart.name
  location            = data.azurerm_resource_group.northmart.location

  version                = "16"
  zone                   = "2"
  administrator_login    = "hmsadmin"
  administrator_password = data.azurerm_key_vault_secret.hms_postgres_password.value

  sku_name   = "B_Standard_B1ms"
  storage_mb = 32768

  backup_retention_days        = 7
  geo_redundant_backup_enabled = false

  public_network_access_enabled = true
}

resource "azurerm_postgresql_flexible_server_database" "hms" {
  name      = "hive_metastore"
  server_id = azurerm_postgresql_flexible_server.hms.id

  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "hms_vm" {
  name      = "allow-hms-vm"
  server_id = azurerm_postgresql_flexible_server.hms.id

  start_ip_address = data.azurerm_public_ip.fraud_producer.ip_address
  end_ip_address   = data.azurerm_public_ip.fraud_producer.ip_address
}

