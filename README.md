# 音轨提取器

一个轻量的命令行工具，用 FFmpeg 从视频或音频文件中提取第一条音轨，可批量处理多个文件。

## 环境要求

- Python 3.10 或更高版本
- FFmpeg 已安装并加入 `PATH`（Windows 可从 [ffmpeg.org](https://ffmpeg.org/download.html) 获取）

Python 侧没有第三方依赖。工具不会上传或联网处理媒体文件。

## 使用

```powershell
python extract_audio.py "演示视频.mp4"
```

默认在源文件旁输出同名 MP3。支持 `mp3`、`wav`、`flac`、`m4a`、`aac` 和 `opus`：

```powershell
python extract_audio.py "演示视频.mp4" --format wav
```

批量处理并指定输出目录：

```powershell
python extract_audio.py "视频 1.mp4" "视频 2.mkv" -f flac -o .\音轨
```

覆盖已经存在的输出文件：

```powershell
python extract_audio.py "演示视频.mp4" --overwrite
```

如果 FFmpeg 不在 `PATH`，指定可执行文件路径：

```powershell
python extract_audio.py "演示视频.mp4" --ffmpeg "C:\工具\ffmpeg\bin\ffmpeg.exe"
```

查看参数：

```powershell
python extract_audio.py --help
```

## 说明

- 每个输入文件提取第一条音轨；没有音轨或输入无法解码时，FFmpeg 会报告错误。
- MP3 使用 VBR 质量等级 2；M4A/AAC 默认 192 kb/s；Opus 默认 128 kb/s；WAV 为 16 位 PCM。
- 输出已存在时默认跳过，避免意外覆盖。可用 `--overwrite` 显式覆盖。
- FFmpeg 按其自身许可证分发；本项目不捆绑 FFmpeg。

## 许可证

本项目采用 MIT 许可证，见 [LICENSE](LICENSE)。
