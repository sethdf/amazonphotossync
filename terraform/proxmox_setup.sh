#!/bin/bash
# Run this script on your Proxmox server (10.20.30.3)
# Usage: bash proxmox_setup.sh

set -e

echo "========================================"
echo "Proxmox Setup for Amazon Photos Sync VM"
echo "========================================"
echo ""

# 1. Create API user and token
echo "Step 1: Creating API user and token..."
pveum user add terraform@pve --password terraform123 2>/dev/null || echo "  User already exists"
pveum aclmod / -user terraform@pve -role Administrator
TOKEN_OUTPUT=$(pveum user token add terraform@pve terraform --privsep=0 2>/dev/null || pveum user token add terraform@pve terraform --privsep=0 --force)
echo ""
echo "API Token created:"
echo "$TOKEN_OUTPUT"
echo ""
echo ">>> COPY THE TOKEN VALUE (the long UUID after 'value:') <<<"
echo ""

# 2. Download Ubuntu cloud image
echo "Step 2: Downloading Ubuntu 22.04 cloud image..."
cd /var/lib/vz/template/iso
if [ -f "jammy-server-cloudimg-amd64.img" ]; then
    echo "  Image already exists, skipping download"
else
    wget -q --show-progress https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img
fi

# 3. Create VM template
echo ""
echo "Step 3: Creating VM template (ID 9000)..."

# Check if template already exists
if qm status 9000 &>/dev/null; then
    echo "  Template 9000 already exists, skipping"
else
    # Create VM
    qm create 9000 --memory 2048 --net0 virtio,bridge=vmbr0 --name ubuntu-22.04-cloud

    # Import disk
    qm importdisk 9000 jammy-server-cloudimg-amd64.img local-lvm

    # Attach disk
    qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0

    # Add cloud-init drive
    qm set 9000 --ide2 local-lvm:cloudinit

    # Set boot order
    qm set 9000 --boot c --bootdisk scsi0

    # Enable serial console
    qm set 9000 --serial0 socket --vga serial0

    # Enable QEMU agent
    qm set 9000 --agent enabled=1

    # Convert to template
    qm template 9000

    echo "  Template created successfully!"
fi

echo ""
echo "========================================"
echo "SETUP COMPLETE!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Copy the API token value shown above"
echo ""
echo "2. On your workstation, update terraform.tfvars:"
echo '   proxmox_api_token_secret = "YOUR_TOKEN_HERE"'
echo ""
echo "3. Also verify these settings match your Proxmox:"
echo '   proxmox_node = "pve"        # run: hostname'
echo '   storage_pool = "local-lvm"  # run: pvesm status'
echo ""
echo "4. Run terraform:"
echo "   cd terraform && terraform init && terraform apply"
echo ""
