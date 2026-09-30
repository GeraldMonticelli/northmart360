resource "azurerm_container_registry" "graph_rag" {
  name                = "acrgraphrag${random_string.suffix.result}"
  resource_group_name = data.azurerm_resource_group.northmart.name
  location            = data.azurerm_resource_group.northmart.location

  sku           = "Basic"
  admin_enabled = false
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}