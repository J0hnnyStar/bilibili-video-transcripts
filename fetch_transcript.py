"""
Fetch Bilibili video subtitles/transcript.

Usage:
    python fetch_transcript.py <video_url>

Reads SESSDATA from .env file in the same directory as this script.

Example:
    python fetch_transcript.py "https://www.bilibili.com/video/BV1DsXuBrESX/"
"""

import argparse
import glob as globmod
import json
import os
import re
import sys
import urllib.request
import urllib.parse


def find_ffmpeg() -> str | None:
    """Find ffmpeg in common Windows install locations."""
    search_patterns = [
        os.path.expanduser("~/AppData/Local/Microsoft/WinGet/Packages/**/ffmpeg.exe"),
        "C:/ProgramData/chocolatey/bin/ffmpeg.exe",
        "C:/ffmpeg/bin/ffmpeg.exe",
        "C:/tools/ffmpeg/bin/ffmpeg.exe",
    ]
    for pattern in search_patterns:
        matches = globmod.glob(pattern, recursive=True)
        if matches:
            return os.path.dirname(matches[0])
    return None


def load_env():
    """Load variables from .env file next to this script."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        print("Error: .env file not found.", file=sys.stderr)
        print(f"Create one at: {env_path}", file=sys.stderr)
        print("With contents: SESSDATA=your_cookie_value_here", file=sys.stderr)
        sys.exit(1)
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()


def extract_bvid(url: str) -> str:
    """Extract BV ID from a Bilibili URL."""
    match = re.search(r"(BV[0-9A-Za-z]{10})", url)
    if not match:
        print(f"Error: Could not extract BV ID from URL: {url}", file=sys.stderr)
        sys.exit(1)
    return match.group(1)


def api_get(url: str, sessdata: str) -> dict:
    """Make an authenticated GET request to the Bilibili API."""
    req = urllib.request.Request(url)
    req.add_header("Cookie", f"SESSDATA={sessdata}")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    req.add_header("Referer", "https://www.bilibili.com/")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in Windows filenames."""
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()


def get_video_info(bvid: str, sessdata: str) -> tuple:
    """Get the video title and cid."""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    data = api_get(url, sessdata)
    if data["code"] != 0:
        print(f"Error getting video info: {data.get('message', 'unknown error')}", file=sys.stderr)
        sys.exit(1)
    title = data["data"]["title"]
    cid = data["data"]["pages"][0]["cid"]
    return title, cid


def get_subtitle_urls(bvid: str, cid: int, sessdata: str) -> list:
    """Get subtitle URLs from the player API."""
    url = f"https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}"
    data = api_get(url, sessdata)
    if data["code"] != 0:
        print(f"Error getting player info: {data.get('message', 'unknown error')}", file=sys.stderr)
        sys.exit(1)

    subtitles = data["data"].get("subtitle", {}).get("subtitles", [])
    return subtitles


def download_subtitle(subtitle_url: str, sessdata: str) -> list:
    """Download subtitle JSON data."""
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    data = api_get(subtitle_url, sessdata)
    return data.get("body", [])


def download_audio(url: str, sessdata: str) -> str:
    """Download audio from a Bilibili video, return path to audio file."""
    try:
        import yt_dlp
    except ImportError:
        print("Error: yt-dlp is required for Whisper fallback.", file=sys.stderr)
        print("Install it: pip install yt-dlp", file=sys.stderr)
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    audio_dir = os.path.join(script_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, "_temp_audio")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": audio_path,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        "http_headers": {
            "Cookie": f"SESSDATA={sessdata}",
            "Referer": "https://www.bilibili.com/",
        },
    }
    ffmpeg_dir = find_ffmpeg()
    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir
    print("Downloading audio...", file=sys.stderr)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return audio_path + ".mp3"


def transcribe_audio(audio_path: str, model_name: str) -> list:
    """Transcribe audio using Whisper, return entries in subtitle format."""
    try:
        import whisper
    except ImportError:
        print("Error: openai-whisper is required for transcription.", file=sys.stderr)
        print("Install it: pip install openai-whisper", file=sys.stderr)
        sys.exit(1)

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading Whisper model '{model_name}' on {device}...", file=sys.stderr)
    model = whisper.load_model(model_name, device=device)
    print("Transcribing (this may take a while)...", file=sys.stderr)
    result = model.transcribe(audio_path)
    print(f"Detected language: {result.get('language', 'unknown')}", file=sys.stderr)

    entries = []
    for seg in result["segments"]:
        entries.append({
            "from": seg["start"],
            "to": seg["end"],
            "content": seg["text"].strip(),
        })
    return entries


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mm format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:05.2f}"
    return f"{m:02d}:{s:05.2f}"


def main():
    load_env()

    sessdata = os.environ.get("SESSDATA")
    if not sessdata or sessdata == "paste_your_sessdata_cookie_here":
        print("Error: Set your SESSDATA in the .env file.", file=sys.stderr)
        sys.exit(1)

    ffmpeg_dir = find_ffmpeg()
    if ffmpeg_dir:
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    parser = argparse.ArgumentParser(description="Fetch Bilibili video transcript")
    parser.add_argument("url", help="Bilibili video URL")
    parser.add_argument("--format", choices=["text", "srt", "json"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--output", "-o", help="Output file (default: auto-named from title)")
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model size when no subtitles exist (default: base)")
    args = parser.parse_args()

    bvid = extract_bvid(args.url)
    print(f"Video: {bvid}", file=sys.stderr)

    title, cid = get_video_info(bvid, sessdata)
    print(f"Title: {title}", file=sys.stderr)
    print(f"Content ID: {cid}", file=sys.stderr)

    subtitles_info = get_subtitle_urls(bvid, cid, sessdata)

    if subtitles_info:
        print(f"Found {len(subtitles_info)} subtitle(s):", file=sys.stderr)
        for i, sub in enumerate(subtitles_info):
            print(f"  [{i}] {sub.get('lan_doc', sub.get('lan', 'unknown'))}", file=sys.stderr)
        subtitle_url = subtitles_info[0]["subtitle_url"]
        entries = download_subtitle(subtitle_url, sessdata)
        print(f"Downloaded {len(entries)} subtitle entries.", file=sys.stderr)
    else:
        print("No subtitles found. Falling back to Whisper transcription...", file=sys.stderr)
        audio_path = download_audio(args.url, sessdata)
        try:
            entries = transcribe_audio(audio_path, args.whisper_model)
            print(f"Transcribed {len(entries)} segments.", file=sys.stderr)
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

    # Format output
    lines = []
    if args.format == "json":
        lines.append(json.dumps(entries, ensure_ascii=False, indent=2))
    elif args.format == "srt":
        for i, entry in enumerate(entries, 1):
            start = format_timestamp(entry["from"]).replace(".", ",")
            end = format_timestamp(entry["to"]).replace(".", ",")
            # Pad to SRT format (HH:MM:SS,mmm)
            lines.append(str(i))
            lines.append(f"{start} --> {end}")
            lines.append(entry["content"])
            lines.append("")
    else:  # text
        for entry in entries:
            ts = format_timestamp(entry["from"])
            lines.append(f"[{ts}] {entry['content']}")

    output = "\n".join(lines)

    # Auto-name using video title, save into transcripts/ folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    transcripts_dir = os.path.join(script_dir, "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)

    ext = {"text": ".txt", "srt": ".srt", "json": ".json"}[args.format]
    if args.output:
        out_path = args.output
    else:
        out_path = os.path.join(transcripts_dir, sanitize_filename(title) + ext)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"Saved to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
