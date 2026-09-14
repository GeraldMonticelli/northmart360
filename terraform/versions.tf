terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.12"
    }

    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.4"
    }

    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.130"
    }

    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }
}

