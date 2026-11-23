# Annotation Studio · Audio models

## 本版实现和验证范围

本版提供三个真实的本地适配器入口。模型安装与载入状态会明确显示；启动界面和查询状态不会联网下载模型。

## Windows 双模型离线包

从 `dist/AnnotationStudio-Audio/AnnotationStudio-Audio.exe` 启动。移动程序时复制整个 `AnnotationStudio-Audio` 文件夹。包内包括 CPU 版 PyTorch、Silero VAD、TensorFlow 和 YAMNet v1 权重。打开项目并导入 WAV／FLAC 后，在 **Auto-detect… → Audio** 选择 **Speaking · Silero VAD** 或 **YAMNet**。YAMNet 自动使用随包 SavedModel，也可手动指定其他本地目录。

离线包可从空白项目开始，也可用 **File → Open project…** 打开已有项目。项目和录音按本地路径打开。从源码运行时，同样可以把完整 SavedModel 放在 `models/yamnet/`。模型权重和下载来源的 SHA-256 记录在该目录的 `model-manifest.json`。

在已有项目 `.venv` 中准备 CPU PyTorch、`silero-vad`、`tensorflow` 和 PyInstaller，以及 [Google 官方 YAMNet v1 SavedModel](https://www.kaggle.com/models/google/yamnet/TensorFlow2/yamnet/1) 后，运行以下命令生成单独的离线包。

```powershell
.\BUILD_WINDOWS_EXE.bat --with-audio
```

本机使用了 Silero VAD 6.2.3、PyTorch 2.15.0+cpu、TensorFlow 2.21.0 与 PyInstaller 6.22.3。如果 TensorFlow wheel 的头文件路径超限，可以用 Windows 扩展路径格式指向同一 `.venv`。

```powershell
$annotationVenv = '\\?\' + (Resolve-Path -LiteralPath .venv).Path
.\.venv\Scripts\python.exe -m pip install --prefix $annotationVenv 'tensorflow==2.21.0'
```

使用一份本地单声道 WAV／FLAC 和一个新建的报告路径，可以直接验证打包后的两个适配器。此命令只运行推理并写出诊断 JSON。

```powershell
Start-Process -Wait -FilePath .\dist\AnnotationStudio-Audio\AnnotationStudio-Audio.exe `
  -ArgumentList '--check-audio-bundle', '"D:\path\test.wav"', '"D:\path\audio-check.json"'
```

## 适配器

| 模块 | 输出 | 运行条件 | 本次验证 |
| --- | --- | --- | --- |
| Audio activity (energy) | 达到 RMS 阈值的声音活动候选 | 主程序依赖、WAV/FLAC | 用实际生成的 WAV/FLAC 验证声道、偏移、范围、取消与保存 |
| Silero VAD | Speaking 候选 | `silero-vad`、PyTorch，权重随 Silero 包提供 | Windows 实际加载 JIT 权重并从公开语音样本生成 Speaking 候选 |
| YAMNet | Laughter、Sigh、Gasp、Cough、Throat clearing、Sneeze、Sniff 等候选 | TensorFlow 和本地 YAMNet SavedModel | Windows 实际加载官方 v1 权重并从公开咳嗽样本生成发声候选，另有 521 类映射和分块契约测试 |

这些检查使用公开样本验证模型加载、推理和候选输出。OCUMO 对话的准确率、召回率和时间边界误差需要使用人工复核样本评估。

### Silero 实际运行记录

2026-11-18 在 Linux x86_64 / Python 3.12 上完成：

```text
python -m pip install --user torch --index-url https://download.pytorch.org/whl/cpu
  -> torch 2.15.0+cpu，CPU wheel 209.5 MB，没有安装 CUDA 依赖
python -m pip install --user "silero-vad>=6.2,<7"
  -> silero-vad 6.2.3，包 11.3 MB
```

真实 `load_silero_vad(onnx=False)` 成功。512 采样静音输入的前向分数约 0.00167；4 秒 220 Hz 纯音经完整适配器返回 0 条候选。本地 FFmpeg/libflite 生成的 7.14 秒英文合成语音，以 5 秒块、0.25 秒项目偏移处理后返回 1 条 pending Speaking：native 0.194–7.140 秒，project 0.444–7.390 秒。校验了合法时间区间、来源、未核实人物归属与原始候选字段。

这些是安装、模型加载、时间转换和返回数据的集成冒烟检查，不是语音准确率或性能基准。没有执行 Windows 运行测试。PyTorch 2.15 对 `torch.jit.load` 给出未来弃用提示；当前 Silero 官方 JIT 路径仍成功执行。

能量阈值不能识别说话、笑声或叹气，它只显示“声音活动”。模型运行失败会报告错误，不会静默换成能量阈值后仍使用模型名称。

## Windows 安装

建议使用主程序创建的 Python 3.11/3.12 虚拟环境。以下命令在程序根目录 PowerShell 中运行。

也可以直接双击 `INSTALL_AUDIO_SILERO_WINDOWS.bat` 或 `INSTALL_AUDIO_YAMNET_WINDOWS.bat`。前者先准备官方 CPU PyTorch，再安装并加载 Silero 包内模型；后者只安装 TensorFlow/Hub 库，不下载 YAMNet 权重。

Silero VAD：

```powershell
# 可选：先安装 CPU 版 PyTorch，避免为这个任务安装 GPU 运行时。
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-audio-silero.txt
```

本适配器自己用 SoundFile 解码、SciPy 重采样，然后向 Silero 传入 tensor。因此无需使用其 `read_audio()`，也无需为 WAV/FLAC 安装 torchaudio、torchcodec 或 FFmpeg。采用包内模型的 `load_silero_vad(onnx=False)`，不使用 `torch.hub` 动态克隆仓库。

YAMNet：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-audio-yamnet.txt
```

程序优先使用指定的本地 SavedModel，留空时使用 `models/yamnet/` 中的随包模型。未配置这两种本地来源时，可在安装 TensorFlow Hub 扩展后显式选择下载。仅仅启动程序、切换工作区或查看模型状态都不会下载。下载需要联网，失败时不会提交部分候选。

示例：先在联网电脑下载至本地缓存，再复制完整目录；不要只复制 `saved_model.pb`，还需要 variables/assets 等文件。

```powershell
.\.venv\Scripts\python.exe -c "import tensorflow_hub as hub; print(hub.resolve('https://tfhub.dev/google/yamnet/1'))"
```

上面的命令是**明确的模型下载操作**。原生 Windows 上本版按 CPU 使用 TensorFlow；当前 TensorFlow 官方 CUDA 支持应使用 WSL2。无需为标注界面本身改用 Ubuntu。

## 时间与人物归属

- `channel=0` 是文件的第一个声道，`channel=1` 是第二个声道。多声道文件必须指定声道或明确选择 `mix`；不会默认把立体声左右声道识别为 R01/R02。
- `role` 来自使用者设置的资产/声道归属。每个候选都保存 `attribution_verified=false`。领夹麦串音依然可能造成误标。
- 不根据“没有 Speaking 候选”自动创建 Listener、Silence 或 Attention 标签。
- Speaking 与 Laughter 等可以同时存在，分别放在对应标注轨道。
- `offset_s` 将原始音频时间映射到项目时间：`project_time = native_time + offset_s`。负偏移会裁掉项目零点之前的不可见部分，原始检测边界仍保存在 provenance 中。
- `start_s` / `end_s` 是**原始音频坐标**的处理范围，不是项目时间。主界面若从项目时间选择范围，应先减去音频偏移。
- 原文件始终只读。重采样、混音和模型输入限幅仅发生在内存中的分析副本上。

## 模型分工与边界精度

### Silero VAD

识别语音活动，不做转录、说话人聚类或 Listener 推断。默认 16 kHz 分析输入、60 秒处理块、块边界前后最多 1 秒上下文；本地时间戳转换后合并块边界。可调阈值、最短片段、合并间隙和语音补边。

官方 `get_speech_timestamps()` 返回时间戳，本适配器不虚构每段概率：`confidence=None`，阈值和模型版本写入 attributes。

### YAMNet

官方模型具有 521 个 AudioSet 输出。这里默认只取 7 个常用非言语发声类别；Breathing 与 Crying 可额外启用。

| Studio 标签 | 官方输出索引与名称 |
| --- | --- |
| Laughter | 13 Laughter、15 Giggle、16 Snicker、17 Belly laugh、18 Chuckle, chortle；每窗取最大值 |
| Sigh | 23 Sigh |
| Gasp | 39 Gasp |
| Cough | 42 Cough |
| Throat clearing | 43 Throat clearing |
| Sneeze | 44 Sneeze |
| Sniff | 45 Sniff |
| Breathing（可选） | 36 Breathing |
| Crying（可选） | 19 Crying, sobbing |

它的特征窗为 0.96 秒，hop 为 0.48 秒；第一窗实际需要 0.975 秒波形。候选边界按分析窗覆盖范围产生，在末尾裁到录音范围内。**这不是精确的事件起止分割**，短叹气和短清嗓特别需要拖拽修边。

阈值以上的窗按类别合并，不强制不同事件互斥。默认 `threshold=0.35` 是初始工作参数，不是经 OCUMO 数据验证的最优阈值。应挑选有人工标签的样本调整每类阈值。

`confidence` 保存触发窗的最大类别分数；它不是校准后的事件正确率。原始类别峰值、正窗平均分、窗数量和全部参数另存于 attributes。

## Python API

```python
from annotationstudio.audio_models import (
    model_status, detect_audio, AudioModelError, AudioCancelled,
)

# 轻量检查：不导入 torch/tensorflow，不下载任何模型。
for row in model_status():
    print(row['id'], row['available'], row['detail'])

proposals = detect_audio(
    'R01_microphone.wav',
    model_id='silero',
    role='R01',
    channel=0,
    offset_s=0.125,
    threshold=0.5,
    min_duration=0.25,
    merge_gap=0.10,
    source_asset_id='asset-123',
    progress=print,                       # callback(message: str)
    cancel=lambda: False,                 # 或 threading.Event
)

vocal_events = detect_audio(
    'R01_microphone.wav', model_id='yamnet', channel=0,
    model_path='models/yamnet',            # 本地 SavedModel
    labels=['Laughter', 'Sigh', 'Cough'],
    threshold=0.35,
    thresholds={'Sigh': 0.3},
)

# 没有本地模型时，显式启用 TensorFlow Hub 下载。
# detect_audio(..., model_id='yamnet', download=True)
```

`available` 表示依赖可发现，不代表权重已载入或动态链接库已经通过测试；`needs_model` 表示需另行选择权重。首次 Run 完成才算该电脑成功执行模型。取消会抛出 `AudioCancelled`，不返回部分结果。模型加载和一个推理块内部不能强行终止；程序会在下一次安全检查点响应取消。

所有结果都是 `Annotation(status='pending')`，来源为 `auto:energy`、`auto:silero` 或 `auto:yamnet`。`original` 保存初始候选，`attributes` 保存模型、参数、native sample/time boundaries、声道、偏移和归属未核实状态。调用者决定如何加入轨道，自动结果不覆盖已经 Accept 的人工工作。

## 为什么未默认打包另外两套模型

**Surround Sound** 的官方项目确实存在，可产生带时间戳的多类声音事件，但 Hugging Face 权重需要申请访问，许可为 CC BY-NC-SA 4.0。本版不下载或再分发这些权重，也未把未经测试的适配器显示为已完成。

**LAION VocalBurst Locator v2** 可定位 vocal burst，官方推荐 `model_v2.pt`，约 972 MB。它本身是 burst/not-burst 二分类，不能直接输出 Laughter/Sigh 类型。其配套 captioner 生成自由文本，仍需映射和人工确认。当前版本不安装这些大型模型。以后可接入相同候选协议，而不改变人工标注结构。

## 官方资料（核查日期 2026-11-18）

- Silero VAD、MIT 许可、包内模型与 API：<https://github.com/snakers4/silero-vad>
- Silero loader 源码：<https://github.com/snakers4/silero-vad/blob/master/src/silero_vad/model.py>
- Silero 依赖：<https://github.com/snakers4/silero-vad/blob/master/pyproject.toml>
- YAMNet 官方调用：<https://www.tensorflow.org/hub/tutorials/yamnet>
- YAMNet 时间窗与架构：<https://github.com/tensorflow/models/blob/master/research/audioset/yamnet/README.md>
- YAMNet 官方类别表：<https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv>
- TensorFlow Windows 支持：<https://www.tensorflow.org/install/pip>
- Surround Sound：<https://github.com/theboringai-work/surround-sound>；<https://huggingface.co/theboringai-work/surround-sound>
- LAION locator：<https://huggingface.co/laion/vocalburst-locator>
- LAION captioner：<https://huggingface.co/laion/vocalburst-captioning-whisper>

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_audio_models.py -q
```

测试不联网、不下载模型权重，也不代表真实性能评测。19 项确定性测试包括真实文件的单/双声道解码、44.1 kHz FLAC、负偏移、native 范围裁剪、文件只读、取消、缺失依赖、禁止隐式下载、YAMNet 类别映射与跨块事件合并、Silero 采样级接口，以及项目保存后的 provenance 完整性。另有 1 项真实 Silero 权重加载/前向冒烟测试；仅在 Torch 与 Silero 已安装时运行，否则明确跳过。
