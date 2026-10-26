#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
applications="$XDG_DATA_HOME/applications"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
systemctl --user disable --now dragon-codex-startup.service 2>/dev/null || true
rm -f "$config_home/systemd/user/dragon-codex-startup.service"
rm -f "$config_home/autostart/DragonCodexStartup.desktop"
systemctl --user daemon-reload 2>/dev/null || true
rm -f "$applications/dragon-codex-boot.desktop"

chatgpt_entry="$applications/chatgpt.desktop"
chatgpt_backup="$applications/chatgpt.desktop.dragon-codex-boot-backup"
if [[ -e "$chatgpt_backup" ]]; then
  mv -f "$chatgpt_backup" "$chatgpt_entry"
elif [[ -f "$chatgpt_entry" ]] && grep -qF "$root/dragon-codex-boot.sh" "$chatgpt_entry"; then
  rm -f "$chatgpt_entry"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$applications" >/dev/null 2>&1 || true
fi
printf '%s\n' 'Dragon Codex Boot 菜单入口和 ChatGPT 启动动画集成已移除。'
