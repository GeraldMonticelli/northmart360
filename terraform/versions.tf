terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
    }

    databricks = {
      source = "databricks/databricks"
    }
  }
}