terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.38"
    }
  }
}

provider "proxmox" {
  endpoint = var.proxmox_api_url
  api_token = "${var.proxmox_api_token_id}=${var.proxmox_api_token_secret}"
  insecure = var.proxmox_tls_insecure

  ssh {
    agent = false
    username = "root"
    password = var.proxmox_ssh_password
  }
}

resource "proxmox_virtual_environment_vm" "amazon_photos_sync" {
  name        = var.vm_name
  node_name   = var.proxmox_node
  description = "Amazon Photos Sync VM"

  clone {
    vm_id = 9000
    full  = true
  }

  cpu {
    cores   = var.vm_cores
    sockets = 1
    type    = "host"
  }

  memory {
    dedicated = var.vm_memory
    floating  = var.vm_memory_min
  }

  disk {
    datastore_id = var.storage_pool
    interface    = "scsi0"
    size         = var.vm_disk_size_gb
    file_format  = "raw"
  }

  network_device {
    bridge = var.network_bridge
    model  = "virtio"
  }

  agent {
    enabled = true
  }

  initialization {
    datastore_id = "local-zfs"
    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }
    dns {
      servers = [var.nameserver]
    }
    user_account {
      username = var.vm_user
      password = var.vm_password
      keys     = [var.ssh_public_key]
    }
  }

  lifecycle {
    ignore_changes = [
      initialization,
    ]
  }
}

resource "null_resource" "setup" {
  depends_on = [proxmox_virtual_environment_vm.amazon_photos_sync]

  connection {
    type        = "ssh"
    user        = var.vm_user
    private_key = file(var.ssh_private_key_path)
    host        = proxmox_virtual_environment_vm.amazon_photos_sync.ipv4_addresses[1][0]
    timeout     = "5m"
  }

  provisioner "remote-exec" {
    inline = ["cloud-init status --wait || true"]
  }

  provisioner "remote-exec" {
    script = "${path.module}/setup.sh"
  }
}

output "vm_ip" {
  description = "IP address of the VM"
  value       = proxmox_virtual_environment_vm.amazon_photos_sync.ipv4_addresses[1][0]
}

output "ssh_command" {
  description = "SSH command to connect to VM"
  value       = "ssh ${var.vm_user}@${proxmox_virtual_environment_vm.amazon_photos_sync.ipv4_addresses[1][0]}"
}

output "next_steps" {
  description = "Next steps after VM creation"
  value       = <<-EOT

    VM Created! Next steps:

    1. SSH into the VM:
       ssh ${var.vm_user}@${proxmox_virtual_environment_vm.amazon_photos_sync.ipv4_addresses[1][0]}

    2. Run the sync:
       ~/run_sync.sh login
       ~/run_sync.sh enumerate
       ~/start_download.sh

  EOT
}
