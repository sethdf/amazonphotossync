terraform {
  required_providers {
    proxmox = {
      source  = "Telmate/proxmox"
      version = "~> 3.0"
    }
  }
}

provider "proxmox" {
  pm_api_url          = var.proxmox_api_url
  pm_api_token_id     = var.proxmox_api_token_id
  pm_api_token_secret = var.proxmox_api_token_secret
  pm_tls_insecure     = var.proxmox_tls_insecure
}

resource "proxmox_vm_qemu" "amazon_photos_sync" {
  name        = var.vm_name
  target_node = var.proxmox_node
  desc        = "Amazon Photos Sync VM"

  # Clone from template (Ubuntu 22.04 recommended)
  clone      = var.template_name
  full_clone = true

  # VM Resources
  cores   = var.vm_cores
  sockets = 1
  memory  = var.vm_memory
  balloon = var.vm_memory_min

  # CPU type
  cpu = "host"

  # Boot disk
  disks {
    scsi {
      scsi0 {
        disk {
          size    = var.vm_disk_size
          storage = var.storage_pool
        }
      }
    }
  }

  # Network
  network {
    model  = "virtio"
    bridge = var.network_bridge
  }

  # Cloud-init configuration
  os_type    = "cloud-init"
  ipconfig0  = var.vm_ip_config
  nameserver = var.nameserver
  ciuser     = var.vm_user
  cipassword = var.vm_password
  sshkeys    = var.ssh_public_key

  # Enable QEMU agent
  agent = 1

  # Lifecycle
  lifecycle {
    ignore_changes = [
      network,
      cipassword,
    ]
  }

  # Wait for cloud-init to complete
  provisioner "remote-exec" {
    inline = ["cloud-init status --wait"]

    connection {
      type        = "ssh"
      user        = var.vm_user
      private_key = file(var.ssh_private_key_path)
      host        = self.default_ipv4_address
      timeout     = "5m"
    }
  }

  # Run setup script
  provisioner "remote-exec" {
    script = "${path.module}/setup.sh"

    connection {
      type        = "ssh"
      user        = var.vm_user
      private_key = file(var.ssh_private_key_path)
      host        = self.default_ipv4_address
      timeout     = "15m"
    }
  }
}

output "vm_ip" {
  description = "IP address of the VM"
  value       = proxmox_vm_qemu.amazon_photos_sync.default_ipv4_address
}

output "ssh_command" {
  description = "SSH command to connect to VM"
  value       = "ssh ${var.vm_user}@${proxmox_vm_qemu.amazon_photos_sync.default_ipv4_address}"
}

output "next_steps" {
  description = "Next steps after VM creation"
  value       = <<-EOT

    VM Created! Next steps:

    1. SSH into the VM:
       ssh ${var.vm_user}@${proxmox_vm_qemu.amazon_photos_sync.default_ipv4_address}

    2. Navigate to the project:
       cd ~/amazonphotossync

    3. Activate the virtual environment:
       source .venv/bin/activate

    4. Login to Amazon (headless):
       python amazon_headless_login.py

    5. Run full enumeration:
       python amazon_photos_sync.py enumerate --full

    6. Start downloading:
       python amazon_photos_sync.py download

  EOT
}
