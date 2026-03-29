# Bilibili Video Transcripts

Fetch transcripts from Bilibili videos. Uses Bilibili's built-in subtitles when available, falls back to [OpenAI Whisper](https://github.com/openai/whisper) for local speech-to-text when not.

Output files are auto-named using the video title.

---

B站视频字幕/文稿提取工具。优先使用B站自带字幕（AI生成或UP主上传），若无字幕则自动调用 [OpenAI Whisper](https://github.com/openai/whisper) 进行本地语音转文字。

输出文件自动以视频标题命名。

## Requirements / 环境要求

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) (required for Whisper fallback / Whisper 转写时需要)

### Python packages / Python 依赖

```bash
pip install yt-dlp openai-whisper
```

For GPU acceleration (NVIDIA), install PyTorch with CUDA:

如需 GPU 加速（NVIDIA 显卡），请安装 CUDA 版 PyTorch：

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

## Setup / 配置

1. Clone this repo / 克隆仓库：

```bash
git clone https://github.com/YOUR_USERNAME/bilibili-video-transcripts.git
cd bilibili-video-transcripts
```

2. Create a `.env` file in the project root / 在项目根目录创建 `.env` 文件：

```
SESSDATA=your_bilibili_sessdata_cookie_here
```

**How to get your SESSDATA / 如何获取 SESSDATA：**

1. Log in to [bilibili.com](https://www.bilibili.com) / 登录B站
2. Press `F12` to open DevTools / 按 `F12` 打开开发者工具
3. Go to **Application** > **Cookies** > `https://www.bilibili.com` / 进入 **应用** > **Cookies**
4. Copy the value of `SESSDATA` / 复制 `SESSDATA` 的值

## Usage / 使用方法

```bash
python fetch_transcript.py "https://www.bilibili.com/video/BV1DsXuBrESX/"
```

Transcripts are saved to the `transcripts/` folder, auto-created on first run.

字幕文件保存在 `transcripts/` 文件夹中，首次运行时自动创建。

### Options / 可选参数

| Flag | Description |
|---|---|
| `--format text` | Plain text with timestamps (default / 默认) |
| `--format srt` | SRT subtitle format / SRT 字幕格式 |
| `--format json` | Raw JSON |
| `-o <path>` | Custom output path / 自定义输出路径 |
| `--whisper-model <size>` | `tiny`, `base` (default), `small`, `medium`, `large` |

### Examples / 示例

```bash
# SRT format / SRT 格式
python fetch_transcript.py "https://www.bilibili.com/video/BV1DsXuBrESX/" --format srt

# Better accuracy with larger Whisper model / 使用更大的 Whisper 模型提高准确度
python fetch_transcript.py "https://www.bilibili.com/video/BV1EHAPzvEPB/" --whisper-model medium
```

## Project Structure / 项目结构

```
.
├── fetch_transcript.py   # Main script / 主脚本
├── .env                  # Your SESSDATA cookie (not committed / 不会被提交)
├── transcripts/          # Output files (auto-created / 自动创建)
└── audio/                # Temp audio for Whisper (auto-cleaned / 自动清理)
```
