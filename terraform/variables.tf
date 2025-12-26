# Proxmox Connection
variable "proxmox_api_url" {
  description = "Proxmox API URL (e.g., https://proxmox.local:8006/api2/json)"
  type        = string
}

variable "proxmox_api_token_id" {
  description = "Proxmox API token ID (e.g., user@pam!terraform)"
  type        = string
}

variable "proxmox_api_token_secret" {
  description = "Proxmox API token secret"
  type        = string
  sensitive   = true
}

variable "proxmox_tls_insecure" {
  description = "Skip TLS verification for Proxmox API"
  type        = bool
  default     = true
}

variable "proxmox_node" {
  description = "Proxmox node to create VM on"
  type        = string
}

# VM Template
variable "template_name" {
  description = "Name of the cloud-init template to clone (Ubuntu 22.04 recommended)"
  type        = string
  default     = "ubuntu-22.04-cloud"
}

# VM Configuration
variable "vm_name" {
  description = "Name of the VM"
  type        = string
  default     = "amazon-photos-sync"
}

variable "vm_cores" {
  description = "Number of CPU cores"
  type        = number
  default     = 4
}

variable "vm_memory" {
  description = "Memory in MB"
  type        = number
  default     = 4096
}

variable "vm_memory_min" {
  description = "Minimum memory (balloon) in MB"
  type        = number
  default     = 2048
}

variable "vm_disk_size" {
  description = "Boot disk size (e.g., '50G' - needs space for ~1.2TB photos)"
  type        = string
  default     = "2000G"
}

variable "storage_pool" {
  description = "Proxmox storage pool for VM disk"
  type        = string
  default     = "local-lvm"
}

# Network
variable "network_bridge" {
  description = "Network bridge to use"
  type        = string
  default     = "vmbr0"
}

variable "vm_ip_config" {
  description = "IP configuration (e.g., 'ip=dhcp' or 'ip=192.168.1.100/24,gw=192.168.1.1')"
  type        = string
  default     = "ip=dhcp"
}

variable "nameserver" {
  description = "DNS nameserver"
  type        = string
  default     = "8.8.8.8"
}

# VM Access
variable "vm_user" {
  description = "Default user for the VM"
  type        = string
  default     = "ubuntu"
}

variable "vm_password" {
  description = "Password for the VM user"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ssh_public_key" {
  description = "SSH public key for authentication"
  type        = string
}

variable "ssh_private_key_path" {
  description = "Path to SSH private key for provisioning"
  type        = string
  default     = "~/.ssh/id_rsa"
}

# GitHub
variable "github_repo" {
  description = "GitHub repository URL"
  type        = string
  default     = "https://github.com/sethdf/amazonphotossync.git"
}
