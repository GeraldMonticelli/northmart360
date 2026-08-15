resource "azurerm_storage_account" "northmart" {
  default_to_oauth_authentication = true
  name                            = "stnorthmartdev"
  resource_group_name             = "rg-dp750"
  location                        = "Central India"

  account_tier              = "Standard"
  account_replication_type  = "LRS"
  shared_access_key_enabled = false
  is_hns_enabled            = true
  tags = {
    "Environnement" = "Learning"
    "Projet"        = "dp-750"
  }
}

resource "azurerm_databricks_access_connector" "northmart" {
  name                = "ac-northmart-dev"
  resource_group_name = "rg-dp750"
  location            = "Central India"
  identity {
    type = "SystemAssigned"
  }
  tags = {
    "Environnement" = "Learning"
    "Projet"        = "dp-750"
  }
}

resource "azurerm_key_vault" "northmart" {
  name                       = "kv-northmart-gmkng"
  resource_group_name        = "rg-dp750"
  location                   = "Central India"
  sku_name                   = "standard"
  rbac_authorization_enabled = false
  tenant_id                  = "ba5562e5-5ac3-48be-a9c2-03e01afc4253"
}

resource "azurerm_databricks_workspace" "northmart" {
  name                          = "adb-dp750"
  resource_group_name           = "rg-dp750"
  public_network_access_enabled = true
  location                      = "Central India"
  sku                           = "premium"
  managed_resource_group_name   = "databricks-rg-adb-dp750-1ejtwyuys0j4z"
  custom_parameters {
    no_public_ip             = true
    storage_account_name     = "dbstoraged2ew5oif43myk"
    storage_account_sku_name = "Standard_ZRS"
  }
  tags = {}
}