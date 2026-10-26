# Linux 部署与启动关联

依赖和安装命令见 [README.md](README.md)。此说明对应 v0.1.1 修复版。

## 启动入口

安装器会读取系统的 chatgpt.desktop，在当前用户的应用目录创建覆写，将 Exec 指向本目录的 dragon-codex-boot.sh。系统级应用文件不被修改。

包装器运行 startup.py，先创建置顶的 GTK 视频窗口，确认视频被绘制后调用真正的 /usr/bin/chatgpt。原有 URL 和文件参数会传给客户端。动画结束时只关闭动画窗口。

用户服务 dragon-codex-startup.service 会检测 /usr/lib/chatgpt/ChatGPT 主进程启动。直接运行程序或旧快捷方式绕过桌面覆写时，也会触发同一个播放器。播放器锁会合并重复触发。

## 尺寸

X11 会优先读取实际 ChatGPT 窗口的位置和大小，并在动画播放期间跟随。尚未出现窗口时读取客户端保存的窗口大小；没有窗口信息时使用屏幕内的居中窗口。

动画窗口限制在显示器工作区域内；视频保持 16:9，以黑边补齐不同的窗口比例。不会强制采用原视频的 1920×1080 尺寸。

## 诊断

```bash
systemctl --user is-enabled dragon-codex-startup.service
systemctl --user is-active dragon-codex-startup.service
cat ~/.cache/dragon-codex-boot/status.json
tail -n 20 ~/.cache/dragon-codex-boot/startup.log
```

had_visible_video=true 且 video_draws>0 表示 GTK 已在映射的窗口中绘制视频；window_size 是实际窗口大小，video_allocation 是视频画布大小。phase=eos 表示自然播放结束。

若缺少 gtksink，安装 gstreamer1.0-gtk3。如果 GTK 无法连接桌面，请在用户的图形登录会话中安装和启动。

## 恢复

运行 ./uninstall-linux.sh。它停止并移除用户级启动服务，恢复安装前已有的用户桌面文件备份；没有旧备份时移除本适配创建的桌面覆写，让系统入口重新生效。
