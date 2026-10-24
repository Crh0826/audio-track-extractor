#!/usr/bin/env python3
"""Extract the first audio stream from video or audio files using FFmpeg."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

FORMATS = {
    "mp3": ("libmp3lame", ["-q:a", "2"]),
    "wav": ("pcm_s16le", []),
    "flac": ("flac", []),
    "m4a": ("aac", ["-b:a", "192k"]),
    "aac": ("aac", ["-b:a", "192k"]),
    "opus": ("libopus", ["-b:a", "128k"]),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract the first audio track from media files with FFmpeg.",
        epilog="Supported output formats: " + ", ".join(FORMATS),
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Input media file(s)")
    parser.add_argument("-f", "--format", choices=FORMATS, default="mp3", help="Output format (default: mp3)")
    parser.add_argument("-o", "--output-dir", type=Path, help="Output directory (default: next to each input)")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output files")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable or full path (default: ffmpeg on PATH)")
    return parser.parse_args()


def output_for(source: Path, output_dir: Path | None, ext: str) -> Path:
    folder = output_dir if output_dir is not None else source.parent
    return folder / f"{source.stem}.{ext}"


def extract(ffmpeg: str, source: Path, target: Path, ext: str, overwrite: bool) -> bool:
    if not source.is_file():
        print(f"错误：找不到输入文件：{source}", file=sys.stderr)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        print(f"跳过（目标已存在；加 --overwrite 可覆盖）：{target}")
        return False

    codec, options = FORMATS[ext]
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-nostdin",
        "-y" if overwrite else "-n",
        "-i", str(source),
        "-map", "0:a:0",
        "-vn",
        "-map_metadata", "0",
        "-c:a", codec,
        *options,
        str(target),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode == 0:
        print(f"完成：{source} -> {target}")
        return True
    print(f"失败（FFmpeg 退出码 {result.returncode}）：{source}", file=sys.stderr)
    return False


def main() -> int:
    args = parse_args()
    ffmpeg = shutil.which(args.ffmpeg) if args.ffmpeg == "ffmpeg" else args.ffmpeg
    if not ffmpeg or (args.ffmpeg != "ffmpeg" and not Path(ffmpeg).is_file()):
        print("错误：找不到 FFmpeg。请安装 FFmpeg 并加入 PATH，或用 --ffmpeg 指定其完整路径。", file=sys.stderr)
        return 2

    succeeded = 0
    failed = 0
    for item in args.inputs:
        source = item.expanduser().resolve()
        target = output_for(source, args.output_dir.expanduser().resolve() if args.output_dir else None, args.format)
        if source == target.resolve(strict=False):
            print(f"错误：输入和输出路径相同：{source}", file=sys.stderr)
            failed += 1
            continue
        if extract(ffmpeg, source, target, args.format, args.overwrite):
            succeeded += 1
        elif not target.exists() or args.overwrite:
            failed += 1

    print(f"处理结束：成功 {succeeded}，失败或跳过 {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
