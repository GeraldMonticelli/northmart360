resource "azurerm_storage_account" "northmart" {
  default_to_oauth_authentication = true
  name                            = "stnorthmartdev"
  resource_group_name             = "rg-dp750"
  location                        = "Central India"

  account_tier              = "Standard"
  account_replication_type  = "LRS"
  shared_access_key_enabled = false
  is_hns_enabled            = true
  tags = {
    "Environnement" = "Learning"
    "Projet"        = "dp-750"
  }
}

resource "azurerm_databricks_access_connector" "northmart" {
  name                = "ac-northmart-dev"
  resource_group_name = "rg-dp750"
  location            = "Central India"
  identity {
    type = "SystemAssigned"
  }
  tags = {
    "Environnement" = "Learning"
    "Projet"        = "dp-750"
  }
}

resource "azurerm_key_vault" "northmart" {
  name                       = "kv-northmart-gmkng"
  resource_group_name        = "rg-dp750"
  location                   = "Central India"
  sku_name                   = "standard"
  rbac_authorization_enabled = false
  tenant_id                  = "ba5562e5-5ac3-48be-a9c2-03e01afc4253"
}

resource "azurerm_virtual_network" "northmart_databricks" {
  name                = "vnet-northmart-dev"
  resource_group_name = "rg-dp750"
  location            = "Central India"

  address_space = ["10.20.0.0/16"]
}

resource "azurerm_subnet" "databricks_public" {
  name                 = "snet-databricks-public"
  resource_group_name  = "rg-dp750"
  virtual_network_name = azurerm_virtual_network.northmart_databricks.name
  address_prefixes     = ["10.20.0.0/24"]

  delegation {
    name = "databricks"

    service_delegation {
      name = "Microsoft.Databricks/workspaces"

      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
        "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
        "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action"
      ]
    }
  }
}

resource "azurerm_subnet" "databricks_private" {
  name                 = "snet-databricks-private"
  resource_group_name  = "rg-dp750"
  virtual_network_name = azurerm_virtual_network.northmart_databricks.name
  address_prefixes     = ["10.20.1.0/24"]

  delegation {
    name = "databricks"

    service_delegation {
      name = "Microsoft.Databricks/workspaces"

      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
        "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
        "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action"
      ]
    }
  }
}

resource "azurerm_databricks_workspace" "northmart" {
  name                          = "adb-dp750"
  resource_group_name           = "rg-dp750"
  location                      = "Central India"
  public_network_access_enabled = true
  sku                           = "premium"
  managed_resource_group_name   = "databricks-rg-adb-dp750-1ejtwyuys0j4z"
  custom_parameters {
    no_public_ip       = true
    virtual_network_id = azurerm_virtual_network.northmart_databricks.id

    public_subnet_name  = azurerm_subnet.databricks_public.name
    private_subnet_name = azurerm_subnet.databricks_private.name

    storage_account_name     = "dbstoraged2ew5oif43myk"
    storage_account_sku_name = "Standard_ZRS"
  }
  tags = {}
}

resource "azurerm_network_security_group" "databricks_public" {
  name                = "nsg-databricks-public"
  resource_group_name = "rg-dp750"
  location            = "Central India"
}

resource "azurerm_network_security_group" "databricks_private" {
  name                = "nsg-databricks-private"
  resource_group_name = "rg-dp750"
  location            = "Central India"
}

resource "azurerm_subnet_network_security_group_association" "databricks_public" {
  subnet_id                 = azurerm_subnet.databricks_public.id
  network_security_group_id = azurerm_network_security_group.databricks_public.id
}

resource "azurerm_subnet_network_security_group_association" "databricks_private" {
  subnet_id                 = azurerm_subnet.databricks_private.id
  network_security_group_id = azurerm_network_security_group.databricks_private.id
}

// subnet for the private endpoint deployment
resource "azurerm_subnet" "private_endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = "rg-dp750"
  virtual_network_name = azurerm_virtual_network.northmart_databricks.name
  address_prefixes     = ["10.20.2.0/24"]
}

# ============================================================
# Private DNS Zones
# ============================================================

resource "azurerm_private_dns_zone" "adls_dfs" {
  name                = "privatelink.dfs.core.windows.net"
  resource_group_name = "rg-dp750"
}

resource "azurerm_private_dns_zone" "adls_blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = "rg-dp750"
}

resource "azurerm_private_dns_zone" "sql" {
  name                = "privatelink.database.windows.net"
  resource_group_name = "rg-dp750"
}


# ============================================================
# Link Private DNS Zones to NorthMart VNet
# ============================================================

resource "azurerm_private_dns_zone_virtual_network_link" "adls_dfs" {
  name                = "link-northmart-dfs"
  private_dns_zone_id = azurerm_private_dns_zone.adls_dfs.id
  virtual_network_id  = azurerm_virtual_network.northmart_databricks.id

  registration_enabled = false
}

resource "azurerm_private_dns_zone_virtual_network_link" "adls_blob" {
  name                = "link-northmart-blob"
  private_dns_zone_id = azurerm_private_dns_zone.adls_blob.id
  virtual_network_id  = azurerm_virtual_network.northmart_databricks.id

  registration_enabled = false
}

resource "azurerm_private_dns_zone_virtual_network_link" "sql" {
  name                = "link-northmart-sql"
  private_dns_zone_id = azurerm_private_dns_zone.sql.id
  virtual_network_id  = azurerm_virtual_network.northmart_databricks.id

  registration_enabled = false
}

# ============================================================
# ADLS Gen2 - DFS Private Endpoint
# ============================================================

resource "azurerm_private_endpoint" "northmart_adls_dfs" {
  name                = "pe-northmart-adls-dfs"
  location            = "Central India"
  resource_group_name = "rg-dp750"
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "psc-northmart-adls-dfs"
    private_connection_resource_id = azurerm_storage_account.northmart.id
    subresource_names              = ["dfs"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name = "default"

    private_dns_zone_ids = [
      azurerm_private_dns_zone.adls_dfs.id
    ]
  }
}


# ============================================================
# ADLS Gen2 - Blob Private Endpoint
# ============================================================

resource "azurerm_private_endpoint" "northmart_adls_blob" {
  name                = "pe-northmart-adls-blob"
  location            = "Central India"
  resource_group_name = "rg-dp750"
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "psc-northmart-adls-blob"
    private_connection_resource_id = azurerm_storage_account.northmart.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name = "default"

    private_dns_zone_ids = [
      azurerm_private_dns_zone.adls_blob.id
    ]
  }
}


# ============================================================
# Azure SQL logical server Private Endpoint
# ============================================================

resource "azurerm_private_endpoint" "northmart_sql" {
  name                = "pe-northmart-sql"
  location            = "Central India"
  resource_group_name = "rg-dp750"
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "psc-northmart-sql"
    private_connection_resource_id = azurerm_mssql_server.northmart.id
    subresource_names              = ["sqlServer"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name = "default"

    private_dns_zone_ids = [
      azurerm_private_dns_zone.sql.id
    ]
  }
}