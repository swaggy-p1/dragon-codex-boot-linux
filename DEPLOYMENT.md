# Linux 部署说明

## 1. 安装系统依赖

Ubuntu/Debian 可执行：

```bash
sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-libav
```

同时需要本机存在 `chatgpt` 或 `codex` 命令。启动脚本优先调用 `chatgpt`，找不到时回退到 `codex`。

## 2. 安装入口

解压 Release 包后运行：

```bash
cd DragonCodexBootLinux
./install-linux.sh
```

安装脚本会把当前用户应用入口写入 `~/.local/share/applications/`，不会修改官方 ChatGPT/Codex 入口。

之后从应用菜单打开 **Dragon Codex Boot**：动画播放结束后会启动 ChatGPT/Codex。

## 3. 手动启动与卸载

```bash
./dragon-codex-boot.sh
rm ~/.local/share/applications/dragon-codex-boot.desktop
```

## 4. 校验下载包

GitHub Release 页面显示每个资产的 SHA256；也可以在下载目录执行：

```bash
sha256sum dragon-codex-boot-linux-x86_64-v0.1.0.tar.gz
```
