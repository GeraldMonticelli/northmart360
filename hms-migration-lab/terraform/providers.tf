terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }

    databricks = {
      source = "databricks/databricks"
    }
  }
}

provider "azurerm" {
  features {}
}

provider "databricks" {
  host = "https://${data.azurerm_databricks_workspace.northmart_dev.workspace_url}"
}

provider "databricks" {
  alias      = "account"
  host       = "https://accounts.azuredatabricks.net"
  account_id = "72b31e8d-b148-4abf-bce7-a803d20310c5"
}