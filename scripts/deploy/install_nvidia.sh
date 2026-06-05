#!/usr/bin/env bash
set -euo pipefail

if ! lspci | grep -i nvidia >/dev/null 2>&1; then
  echo "No NVIDIA GPU detected; skipping NVIDIA setup."
  exit 0
fi

apt-get update
apt-get install -y nvidia-driver-535 curl gnupg
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  >/etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update
apt-get install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
echo "NVIDIA Docker runtime installed."

