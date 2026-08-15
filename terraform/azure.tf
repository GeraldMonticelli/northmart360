resource "azurerm_storage_account" "northmart" {
  name                     = "stnorthmartdev"
  resource_group_name      = "rg-dp750"
  location                 = "Central India"

  account_tier             = "Standard"
  account_replication_type = "LRS"

  is_hns_enabled = true
}