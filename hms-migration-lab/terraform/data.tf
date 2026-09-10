data "azurerm_resource_group" "northmart" {
  name = "rg-dp750"
}

data "azurerm_storage_account" "northmart_dev" {
  name                = "stnorthmartdev"
  resource_group_name = data.azurerm_resource_group.northmart.name
}

data "azurerm_virtual_network" "northmart_dev" {
  name                = "vnet-northmart-dev"
  resource_group_name = data.azurerm_resource_group.northmart.name
}

data "azurerm_virtual_machine" "fraud_producer" {
  name                = "vm-fraud-producer"
  resource_group_name = data.azurerm_resource_group.northmart.name
}

data "azurerm_key_vault" "northmart" {
  name                = "kv-northmart-gmkng"
  resource_group_name = "rg-dp750"
}

data "azurerm_key_vault_secret" "hms_postgres_password" {
  name         = "hms-postgres-admin-password"
  key_vault_id = data.azurerm_key_vault.northmart.id
}

data "azurerm_public_ip" "fraud_producer" {
  name                = "pip-fraud-producer"
  resource_group_name = data.azurerm_resource_group.northmart.name
}

data "databricks_storage_credential" "northmart" {
  name = "sc_northmart_dev"
}

data "azurerm_databricks_workspace" "northmart_dev" {

  name                = "adb-dp750"
  resource_group_name = data.azurerm_resource_group.northmart.name

}

data "databricks_mws_network_connectivity_config" "northmart" {
  provider = databricks.account

  name   = "ncc-northmart-dev"
  region = "centralindia"
}