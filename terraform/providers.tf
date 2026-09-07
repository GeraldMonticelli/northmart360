terraform {
  backend "azurerm" {
    resource_group_name  = "rg-northmart-tfstate"
    storage_account_name = "stnorthmarttfstate01"
    container_name       = "tfstate"

    use_azuread_auth = true
  }
}

provider "azapi" {}

provider "azurerm" {
  features {}
}

provider "databricks" {
  host = "https://${azurerm_databricks_workspace.northmart.workspace_url}"
}

provider "databricks" {
  alias      = "account"
  host       = "https://accounts.azuredatabricks.net"
  account_id = "72b31e8d-b148-4abf-bce7-a803d20310c5"
}

provider "azuread" {}