#!/usr/bin/env bash
# 각 워커 노드에서 1회 실행. K3S_URL, K3S_TOKEN 환경변수 필수.
set -euo pipefail
: "${K3S_URL:?need K3S_URL=https://<master>:6443}"
: "${K3S_TOKEN:?need K3S_TOKEN=<from master>}"
curl -sfL https://get.k3s.io | sh -
sudo systemctl status k3s-agent --no-pager
