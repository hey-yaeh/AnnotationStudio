
# Annotation Studio

用于在同一时间轴上查看动作捕捉、视频和音频，并记录带审核状态的区间标注和点事件。

[English README](README.md) · [英文图文操作指南](docs/Annotation_Studio_Illustrated_User_Guide_EN.pdf) · [中文标注规程](docs/ANNOTATION_PROTOCOL_CN.md)

## 安装与启动

使用 64 位 Python 3.11 或 3.12。

- Windows 建议放在短路径，例如 `C:\AS`。依次运行 `INSTALL_WINDOWS.bat` 和 `RUN_WINDOWS.bat`。参见 [Windows 安装说明](docs/WINDOWS_SETUP_CN.md)。
- Linux 运行 `bash install_linux.sh`，然后运行 `bash run_linux.sh`。

第一次试用可在 **File → Open synthetic annotation demo** 打开[合成示例](examples/README.md)。使用自己的数据时，新建项目，添加来源，选择 R01、R02 或场景，并在 **Timing / relink** 中核对时间偏移。

## 标注与导出

在各工作区选择轨道，创建区间或点事件。使用 **Auto-detect…** 生成运动或音频候选，再人工核对标签、角色和边界。可选的 Silero VAD 和 YAMNet 安装说明见[音频模型](docs/AUDIO_MODELS.md)。话轮候选来自已明确角色归属的 Speaking 区间。

通过 **Save project** 保存完整的 `.studio.json`。通过 **Export** 按标注类型和审核状态写出总表、分表或两者。详见 [CSV 导出](docs/EXPORT_CN.md)和[双语词表](docs/LABEL_GUIDE.md)。

开发与验证命令见 [English README](README.md)。
