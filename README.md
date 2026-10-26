# Dragon Codex Boot Linux

Linux 适配版：播放龙娘启动动画，然后启动 ChatGPT/Codex。原项目作者为 GitHub 账号 `yushua0808-cpu`，原仓库见 https://github.com/yushua0808-cpu/dragon-codex-boot。

## 快速部署

### 1. 安装依赖

Ubuntu/Debian：

```bash
sudo apt update
sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-libav
```

并确认本机存在 `chatgpt` 或 `codex`：

```bash
command -v chatgpt || command -v codex
```

### 2. 解压并安装

从 [v0.1.0 Release](https://github.com/swaggy-p1/dragon-codex-boot-linux/releases/tag/v0.1.0) 下载 `dragon-codex-boot-linux-x86_64-v0.1.0.tar.gz`，然后：

```bash
tar -xzf dragon-codex-boot-linux-x86_64-v0.1.0.tar.gz
cd DragonCodexBootLinux
./install-linux.sh
```

安装后在应用菜单中打开 **Dragon Codex Boot**。动画播放完成后会优先启动 `chatgpt`，找不到时回退到 `codex`。

### 3. 手动启动

```bash
./dragon-codex-boot.sh
```

## 卸载

只移除应用菜单入口：

```bash
rm ~/.local/share/applications/dragon-codex-boot.desktop
```

不会修改官方 ChatGPT/Codex 入口。

## 常见问题

- `gst-play-1.0: command not found`：重新安装 `gstreamer1.0-tools`。
- 播放器无法解码 MP4：安装 `gstreamer1.0-libav`。
- 动画后没有打开客户端：确认 `command -v chatgpt` 或 `command -v codex` 能找到命令。

## 归属和许可

详细说明见 [ATTRIBUTION.md](ATTRIBUTION.md)，部署细节见 [DEPLOYMENT.md](DEPLOYMENT.md)。原项目源码为 MIT；原仓库中的媒体和第三方内容以原作者说明为准。
