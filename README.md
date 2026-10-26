# Dragon Codex Boot Linux

Linux 启动动画适配版。启动 ChatGPT 桌面应用时，在应用窗口的位置播放龙娘动画，再显示应用。

原项目作者：**yushua0808-cpu**。原仓库：[dragon-codex-boot](https://github.com/yushua0808-cpu/dragon-codex-boot)。本项目为 Linux 适配，角色和动画归属见 [ATTRIBUTION.md](ATTRIBUTION.md)。

## 当前修复版的行为

- 使用 GTK 窗口嵌入 GStreamer 视频，窗口置顶，明确显示视频画面。
- 动画窗口匹配 ChatGPT 当前窗口的位置和尺寸；应用尚未出现时使用已保存的窗口尺寸。
- 视频保持 16:9，按窗口容纳显示，留黑边，不拉伸、不裁掉画面。
- 从原有 ChatGPT 应用图标启动时触发。用户会话的启动监听也会检测直接运行 ChatGPT 程序的情况。
- 同一次启动只播放一个动画；按 `Esc` 可以跳过。

此目录对应 **v0.1.1 修复版**。旧 GitHub v0.1.0 压缩包不包含上述嵌入窗口和启动监听。

## Ubuntu / Debian 部署

先安装依赖：

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-gstreamer-1.0 \
  gir1.2-wnck-3.0 gstreamer1.0-gtk3 gstreamer1.0-tools \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-libav
```

确认已安装 ChatGPT Linux 桌面应用，本机启动命令为 `/usr/bin/chatgpt`。然后解压本修复版并安装：

```bash
tar -xzf dragon-codex-boot-linux-x86_64-v0.1.1.tar.gz
cd DragonCodexBootLinux
./install-linux.sh
```

安装器会配置当前用户的 `chatgpt.desktop`，保留应用原有图标和文件关联，并启用 `dragon-codex-startup.service` 用户服务。之后从原来的 **ChatGPT** 图标启动即可。

安装目录需要保留；移动目录后请重新运行安装脚本。

## 查看状态和预览

```bash
systemctl --user status dragon-codex-startup.service
/usr/bin/python3 startup.py --preview
```

运行状态保存在 `~/.cache/dragon-codex-boot/status.json`，包含窗口实际尺寸、视频画布尺寸、收到的视频帧数和 GTK 实际绘制次数。错误日志为同目录下的 `startup.log`。

应用窗口是 1280×820 时，动画窗口也是 1280×820；视频按比例放入其中。应用最大化时，动画跟随当前显示器内的应用窗口。

## 卸载

```bash
./uninstall-linux.sh
```

卸载会停止启动监听，恢复原始桌面入口。系统 ChatGPT 安装和本目录中的动画文件保留。

更多细节见 [DEPLOYMENT.md](DEPLOYMENT.md)。
