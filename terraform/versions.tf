terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azapi = {
      source = "Azure/azapi"
    }

    azurerm = {
      source = "hashicorp/azurerm"
    }

    databricks = {
      source = "databricks/databricks"
    }

    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }
}

