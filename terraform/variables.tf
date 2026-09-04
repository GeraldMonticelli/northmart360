variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "test"], var.environment)
    error_message = "environment must be dev or test."
  }
}

variable "resource_group_name" {
  description = "Resource group containing the NorthMart environment"
  type        = string
}

variable "sql_admin_login" {
  type = string
}

variable "sql_admin_password" {
  type      = string
  sensitive = true
}

variable "dev_public_ips" {
  type = list(string)
}

variable "fraud_producer_ssh_public_key" {
  description = "SSH public key for the fraud producer VM"
  type        = string
}

variable "workload_name" {
  type    = string
  default = "northmart"
}

variable "location" {
  type    = string
  default = "Central India"
}

variable "storage_account_name" {
  type = string
}

variable "key_vault_name" {
  type = string
}

variable "workspace_name" {
  type = string
}

variable "databricks_managed_resource_group_name" {
  type = string
}

locals {
  catalog_name            = "${var.workload_name}_${var.environment}"
  sql_server_name         = "sql-${var.workload_name}-${var.environment}"
  sql_database_name       = "sqldb-${var.workload_name}-${var.environment}"
  eventhub_namespace_name = "evhns-${var.workload_name}-fraud-${var.environment}"
  vnet_name               = "vnet-${var.workload_name}-${var.environment}"
  access_connector_name   = "ac-${var.workload_name}-${var.environment}"
  ncc_name                = "ncc-${var.workload_name}-${var.environment}"
}