#!/usr/bin/env python3
"""Extract the first audio stream from video or audio files using FFmpeg."""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

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
    parser.add_argument("--normalize", action="store_true", help="Normalize loudness with two-pass EBU R128 loudnorm")
    parser.add_argument("--target-lufs", type=float, default=-16.0, help="Integrated loudness target (default: -16 LUFS)")
    parser.add_argument("--true-peak", type=float, default=-1.5, help="Maximum true peak in dBTP (default: -1.5)")
    parser.add_argument("--lra", type=float, default=11.0, help="Loudness range target (default: 11 LU)")
    return parser.parse_args()


def output_for(source: Path, output_dir: Path | None, ext: str) -> Path:
    folder = output_dir if output_dir is not None else source.parent
    return folder / f"{source.stem}.{ext}"


def loudness_stats(ffmpeg: str, source: Path, target_lufs: float, true_peak: float, lra: float) -> dict | None:
    filter_spec = f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}:print_format=json"
    command = [
        ffmpeg, "-hide_banner", "-nostats", "-nostdin", "-loglevel", "info",
        "-i", str(source), "-map", "0:a:0", "-vn", "-af", filter_spec, "-f", "null", "-",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"响度分析失败：{source}\n{result.stderr.strip()}", file=sys.stderr)
        return None

    blocks = re.findall(r"\{\s*\"input_i\"[\s\S]*?\}", result.stderr)
    if not blocks:
        print(f"FFmpeg 未返回响度分析结果：{source}", file=sys.stderr)
        return None
    try:
        stats = json.loads(blocks[-1])
        for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
            if not math.isfinite(float(stats[key])):
                raise ValueError(f"{key} is not finite; source may be silent")
        return stats
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"无法读取响度分析结果：{source} ({exc})", file=sys.stderr)
        return None


def extract(
    ffmpeg: str,
    source: Path,
    target: Path,
    ext: str,
    overwrite: bool,
    normalize: bool = False,
    target_lufs: float = -16.0,
    true_peak: float = -1.5,
    lra: float = 11.0,
) -> bool:
    if not source.is_file():
        print(f"错误：找不到输入文件：{source}", file=sys.stderr)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        print(f"跳过（目标已存在；加 --overwrite 可覆盖）：{target}")
        return False

    codec, options = FORMATS[ext]
    filter_spec = None
    if normalize:
        print(f"分析响度：{source}")
        stats = loudness_stats(ffmpeg, source, target_lufs, true_peak, lra)
        if stats is None:
            return False
        filter_spec = (
            f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}"
            f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
            f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
            f":offset={stats['target_offset']}:linear=true:print_format=json"
        )
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "info" if normalize else "error",
        "-nostats",
        "-nostdin",
        "-y" if overwrite else "-n",
        "-i", str(source),
        "-map", "0:a:0",
        "-vn",
        "-map_metadata", "0",
        *( ["-af", filter_spec] if filter_spec else [] ),
        "-c:a", codec,
        *options,
        str(target),
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=normalize,
        text=normalize,
        encoding="utf-8" if normalize else None,
        errors="replace" if normalize else None,
    )
    if result.returncode == 0:
        print(f"完成：{source} -> {target}")
        if normalize:
            blocks = re.findall(r"\{\s*\"input_i\"[\s\S]*?\}", result.stderr)
            if blocks:
                try:
                    final_stats = json.loads(blocks[-1])
                    print(f"  输出响度：{final_stats['output_i']} LUFS；真峰值：{final_stats['output_tp']} dBTP")
                except (KeyError, ValueError, json.JSONDecodeError):
                    pass
        return True
    error = result.stderr.strip() if normalize else ""
    print(f"失败（FFmpeg 退出码 {result.returncode}）：{source}\n{error}", file=sys.stderr)
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
        if extract(
            ffmpeg,
            source,
            target,
            args.format,
            args.overwrite,
            args.normalize,
            args.target_lufs,
            args.true_peak,
            args.lra,
        ):
            succeeded += 1
        elif not target.exists() or args.overwrite:
            failed += 1

    print(f"处理结束：成功 {succeeded}，失败或跳过 {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
