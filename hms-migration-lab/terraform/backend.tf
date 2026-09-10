terraform {
  backend "azurerm" {
    resource_group_name  = "rg-northmart-tfstate"
    storage_account_name = "stnorthmarttfstate01"
    container_name       = "tfstate"
  }
}