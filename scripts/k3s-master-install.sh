#!/usr/bin/env bash
# 마스터 노드에서 1회 실행. Ubuntu 24.04 기준.
set -euo pipefail
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --disable traefik --write-kubeconfig-mode 644" sh -
sudo systemctl status k3s --no-pager
echo "--- node token (워커 조인 시 사용) ---"
sudo cat /var/lib/rancher/k3s/server/node-token
echo "--- kubeconfig 복사 (로컬 kubectl 용) ---"
echo "scp <master>:/etc/rancher/k3s/k3s.yaml ~/.kube/config-k3s"
echo "그리고 server 주소를 마스터 IP로 치환 후 사용."
