# Linux 部署与启动关联

依赖和安装命令见 [README.md](README.md)。此说明对应 v0.1.2 修复版。

## 启动入口

安装器会读取系统的 chatgpt.desktop，在当前用户的应用目录创建覆写，将 Exec 指向本目录的 dragon-codex-boot.sh。系统级应用文件不被修改。

包装器运行 startup.py，先立即调用真正的 /usr/bin/chatgpt，再创建 GTK 动画窗口。原有 URL 和文件参数会传给客户端。客户端启动不再依赖视频解码或首帧回调。

动画结束时会关闭播放窗口，恢复被最小化的客户端窗口，切换到客户端所在工作区，并激活客户端。X11 会读取真实窗口状态，确认其 active=true、minimized=false 后才算完成交接。启动监听触发的动画也执行同一交接。Wayland 使用客户端激活请求，本机未验证其前台状态。

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

had_visible_video=true 且 video_draws>0 表示 GTK 已在映射的窗口中绘制视频；window_size 是实际窗口大小，video_allocation 是视频画布大小。phase=eos 表示自然播放结束。app_handoff=active 和 app_window.active=true 表示客户端已经进入前台；动画关闭后 mapped=false 是正常状态。

客户端输出保存在 ~/.cache/dragon-codex-boot/app-launch.log。若在有限重试后仍无法找到或激活应用窗口，启动器会发出桌面错误通知，而不是静默退出。

若缺少 gtksink，安装 gstreamer1.0-gtk3。如果 GTK 无法连接桌面，请在用户的图形登录会话中安装和启动。

## 恢复

运行 ./uninstall-linux.sh。它停止并移除用户级启动服务，恢复安装前已有的用户桌面文件备份；没有旧备份时移除本适配创建的桌面覆写，让系统入口重新生效。
