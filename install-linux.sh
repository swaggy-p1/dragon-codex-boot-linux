#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
/usr/bin/python3 - <<'PY'
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gst, Gtk
Gst.init(None)
if not Gst.ElementFactory.find('gtksink'):
    raise SystemExit('缺少嵌入式播放器，请安装 gstreamer1.0-gtk3。')
PY
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
mkdir -p "$XDG_DATA_HOME/applications"
python3 - "$root" "$XDG_DATA_HOME/applications/dragon-codex-boot.desktop" <<'PY'
import pathlib, sys
root=pathlib.Path(sys.argv[1]).resolve()
out=pathlib.Path(sys.argv[2])
out.write_text(
    '[Desktop Entry]\n'
    'Type=Application\n'
    'Name=Dragon Codex Boot\n'
    'Comment=播放龙娘启动动画后打开 ChatGPT/Codex\n'
    f'Exec="{root / "dragon-codex-boot.sh"}"\n'
    f'Path={root}\n'
    'Terminal=false\n'
    'Categories=Utility;\n', encoding='utf-8')
PY

# Shadow the official ChatGPT desktop entry for this user, preserving all its
# metadata and MIME handlers while routing launches through the animation.
chatgpt_entry="$XDG_DATA_HOME/applications/chatgpt.desktop"
chatgpt_backup="$XDG_DATA_HOME/applications/chatgpt.desktop.dragon-codex-boot-backup"
system_chatgpt_entry=""
IFS=: read -r -a data_dirs <<< "${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
for data_dir in "${data_dirs[@]}"; do
  if [[ -r "$data_dir/applications/chatgpt.desktop" ]]; then
    system_chatgpt_entry="$data_dir/applications/chatgpt.desktop"
    break
  fi
done

if [[ -n "$system_chatgpt_entry" ]]; then
  if [[ -e "$chatgpt_entry" && ! -e "$chatgpt_backup" ]] && ! grep -qF "$root/dragon-codex-boot.sh" "$chatgpt_entry"; then
    cp -p "$chatgpt_entry" "$chatgpt_backup"
  fi
  if [[ ! -e "$chatgpt_entry" ]]; then
    cp "$system_chatgpt_entry" "$chatgpt_entry"
  fi
  python3 - "$chatgpt_entry" "$root/dragon-codex-boot.sh" <<'PY'
import pathlib, sys
entry=pathlib.Path(sys.argv[1])
wrapper=sys.argv[2].replace('\\', '\\\\').replace('"', '\\"')
lines=entry.read_text(encoding='utf-8').splitlines()
for index, line in enumerate(lines):
    if line.startswith('Exec='):
        lines[index]=f'Exec="{wrapper}" %U'
        break
else:
    raise SystemExit(f'No Exec= key found in {entry}')
entry.write_text('\n'.join(lines)+'\n', encoding='utf-8')
PY
  printf '%s\n' 'ChatGPT 桌面入口已接入启动动画。'
else
  printf '%s\n' '未找到 chatgpt.desktop；可从 Dragon Codex Boot 菜单入口启动。'
fi

config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
mkdir -p "$config_home/systemd/user"
python3 - "$root" "$config_home/systemd/user/dragon-codex-startup.service" <<'PY'
import pathlib, sys
root=str(pathlib.Path(sys.argv[1]).resolve()).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
pathlib.Path(sys.argv[2]).write_text(
    '[Unit]\nDescription=ChatGPT Dragon startup animation watcher\n'
    'After=graphical-session-pre.target\nPartOf=graphical-session.target\n\n'
    '[Service]\nType=simple\n'
    f'ExecStart=/usr/bin/python3 "{root}/startup.py" --watch\n'
    'Restart=on-failure\nRestartSec=3\n\n'
    '[Install]\nWantedBy=graphical-session.target\n', encoding='utf-8')
PY

if systemctl --user daemon-reload && systemctl --user enable --now dragon-codex-startup.service; then
  rm -f "$config_home/autostart/DragonCodexStartup.desktop"
  printf '%s\n' 'ChatGPT 直接启动监听已启用。'
else
  mkdir -p "$config_home/autostart"
  cat > "$config_home/autostart/DragonCodexStartup.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ChatGPT Dragon startup watcher
Exec=/usr/bin/python3 "$root/startup.py" --watch
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
  printf '%s\n' '已添加登录会话启动监听；下次登录后生效。'
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$XDG_DATA_HOME/applications" >/dev/null 2>&1 || true
fi
printf '%s\n' 'Dragon Codex Boot 已加入当前用户应用菜单。'
