terraform {
  required_version = ">= 1.6.0"

  backend "azurerm" {
    resource_group_name  = "rg-northmart-tfstate"
    storage_account_name = "stnorthmarttfstate01"
    container_name       = "tfstate"
    use_azuread_auth     = true
    key                  = "northmart-graph-rag-dev.tfstate"
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.4"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

provider "azuread" {}