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