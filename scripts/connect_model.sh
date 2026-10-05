#!/usr/bin/env bash
set -euo pipefail
# 密码通过 SSH 的交互提示输入，不保存在项目里。
ssh_host="${1:-${SSH_HOST:-}}"
ssh_user="${2:-${SSH_USER:-}}"
ssh_port="${3:-${SSH_PORT:-22}}"
if [[ -z "$ssh_host" || -z "$ssh_user" ]]; then
  echo '用法：bash scripts/connect_model.sh <服务器地址> <SSH用户名> [SSH端口]' >&2
  echo '也可通过 SSH_HOST、SSH_USER、SSH_PORT 环境变量配置。' >&2
  exit 2
fi
exec ssh -N -p "$ssh_port" \
  -o StrictHostKeyChecking=yes \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:18080:127.0.0.1:18080 \
  "$ssh_user@$ssh_host"
