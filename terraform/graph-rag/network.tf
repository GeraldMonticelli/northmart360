data "azurerm_resource_group" "northmart" {
  name = "rg-dp750"
}

data "azurerm_virtual_network" "northmart" {
  name                = "vnet-northmart-dev"
  resource_group_name = data.azurerm_resource_group.northmart.name
}

resource "azurerm_subnet" "graph_rag" {
  name                 = "snet-graph-rag"
  resource_group_name  = data.azurerm_resource_group.northmart.name
  virtual_network_name = data.azurerm_virtual_network.northmart.name

  address_prefixes = ["10.20.5.0/24"]
}