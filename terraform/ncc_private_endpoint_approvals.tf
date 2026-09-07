data "azapi_resource_list" "storage_private_endpoint_connections" {
  type      = "Microsoft.Storage/storageAccounts/privateEndpointConnections@2025-01-01"
  parent_id = azurerm_storage_account.northmart.id

  response_export_values = ["*"]

  depends_on = [
    databricks_mws_ncc_private_endpoint_rule.northmart_adls_blob,
    databricks_mws_ncc_private_endpoint_rule.northmart_adls_dfs
  ]
}


locals {
  ncc_private_endpoint_connections = {
    blob = try(
      one([
        for connection in data.azapi_resource_list.storage_private_endpoint_connections.output.value :
        connection.id
        if endswith(
          connection.properties.privateEndpoint.id,
          databricks_mws_ncc_private_endpoint_rule.northmart_adls_blob.endpoint_name
        )
      ]),
      null
    )

    dfs = try(
      one([
        for connection in data.azapi_resource_list.storage_private_endpoint_connections.output.value :
        connection.id
        if endswith(
          connection.properties.privateEndpoint.id,
          databricks_mws_ncc_private_endpoint_rule.northmart_adls_dfs.endpoint_name
        )
      ]),
      null
    )
  }
}


resource "azapi_update_resource" "approve_ncc_storage_private_endpoints" {
  for_each = {
    blob = local.ncc_private_endpoint_connections.blob
    dfs  = local.ncc_private_endpoint_connections.dfs
  }

  type        = "Microsoft.Storage/storageAccounts/privateEndpointConnections@2025-01-01"
  resource_id = each.value

  body = {
    properties = {
      privateLinkServiceConnectionState = {
        status      = "Approved"
        description = "Automatically approved by Terraform for Databricks NCC."
      }
    }
  }
}