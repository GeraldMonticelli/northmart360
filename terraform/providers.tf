provider "azurerm" {
  features {}
}

provider "databricks" {
  host = "https://adb-7405613337187597.17.azuredatabricks.net/aad/auth"
}

provider "databricks" {
  alias      = "account"
  host       = "https://accounts.azuredatabricks.net"
  account_id = "72b31e8d-b148-4abf-bce7-a803d20310c5"
}