resource "azurerm_subnet" "fraud_producer" {
  name                 = "snet-fraud-producer"
  resource_group_name  = "rg-dp750"
  virtual_network_name = azurerm_virtual_network.northmart_databricks.name
  address_prefixes     = ["10.20.3.0/24"]
}

resource "azurerm_network_security_group" "fraud_producer" {
  name                = "nsg-fraud-producer"
  location            = "Central India"
  resource_group_name = "rg-dp750"

  security_rule {
    name                   = "Allow-SSH-From-My-IP"
    priority               = 100
    direction              = "Inbound"
    access                 = "Allow"
    protocol               = "Tcp"
    source_port_range      = "*"
    destination_port_range = "22"
    source_address_prefixes = [
      for ip in var.dev_public_ips : "${ip}/32"
    ]
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "fraud_producer" {
  subnet_id                 = azurerm_subnet.fraud_producer.id
  network_security_group_id = azurerm_network_security_group.fraud_producer.id
}

resource "azurerm_public_ip" "fraud_producer" {
  name                = "pip-fraud-producer"
  location            = "Central India"
  resource_group_name = "rg-dp750"

  allocation_method = "Static"
  sku               = "Standard"
}

resource "azurerm_network_interface" "fraud_producer" {
  name                = "nic-fraud-producer"
  location            = "Central India"
  resource_group_name = "rg-dp750"

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.fraud_producer.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.fraud_producer.id
  }
}

resource "azurerm_linux_virtual_machine" "fraud_producer" {
  name                = "vm-fraud-producer"
  resource_group_name = "rg-dp750"
  location            = "Central India"

  size = "Standard_D2s_v6"

  admin_username = "azureuser"

  network_interface_ids = [
    azurerm_network_interface.fraud_producer.id
  ]

  admin_ssh_key {
    username   = "azureuser"
    public_key = var.fraud_producer_ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {

    publisher = "Canonical"

    offer = "0001-com-ubuntu-server-jammy"

    sku = "22_04-lts-gen2"

    version = "latest"

  }
}

