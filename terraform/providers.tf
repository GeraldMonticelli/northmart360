terraform {
  backend "azurerm" {
    resource_group_name  = "rg-northmart-tfstate"
    storage_account_name = "stnorthmarttfstate01"
    container_name       = "tfstate"
    key                  = "northmart-dev.tfstate"

    use_azuread_auth = true
  }
}

provider "azurerm" {
  features {}
}

provider "databricks" {
  host = "https://adb-7405613337187597.17.azuredatabricks.net"
}

provider "databricks" {
  alias      = "account"
  host       = "https://accounts.azuredatabricks.net"
  account_id = "72b31e8d-b148-4abf-bce7-a803d20310c5"
}

provider "azuread" {}