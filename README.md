# youtube-frames

A [Claude Code](https://claude.com/claude-code) skill that lets Claude **see** a video: it pulls frames from a YouTube URL or local file (video only, no audio), tiles them into contact sheets Claude can read as images, and keeps a timeline of what is on screen.

Claude can't watch video natively. This gives it eyes, cheaply: scene-change sampling turns a 12-minute video into about 4 to 5 images instead of hundreds.

## Install

Requirements: Python 3.8+, [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), and [`ffmpeg`](https://ffmpeg.org/) on your PATH.

```bash
git clone https://github.com/bandeiracaio/youtube-frames ~/.claude/skills/youtube-frames
```

Restart Claude Code, then ask: *"watch this video https://youtu.be/..."* (or run `/youtube-frames`).

## Use it directly

```bash
python frames.py "<url or file>" --scene --ocr          # recommended start
python frames.py "<url>" --every 15 --from 05:00 --to 08:00
python frames.py "<url>" --zoom 06:10 --span 6 --ocr    # re-read one moment, 1 fps, full size
```

| Option | What it does |
|---|---|
| `--scene [T]` | Keep only frames where the picture changes. Keeps the strongest `--max` changes (default 40), at least `--gap` seconds apart (default 2). |
| `--every SEC` | A frame every SEC seconds, thinned evenly to `--max`. |
| `--zoom TIME [--span SEC]` | Dense 1 fps, full-size frames around one moment. |
| `--from TIME --to TIME` | Only look at a slice (seconds, `MM:SS` or `H:MM:SS`). |
| `--dense` | 4x4 sheets at a smaller size: cheaper, less legible. |
| `--ocr` | Read on-screen text into `timeline.md`. Uses Tesseract if installed, otherwise Windows' built-in OCR. |
| `--no-dedupe` / `--keep-black` | Keep near-identical / near-black frames (dropped by default). |

Output goes to `~/Documents/YouTubeFrames/<video-id>/run-<timestamp>/`: `f_NNN.jpg`, `sheet_NN.jpg`, `times.txt`, `timeline.md`. Downloaded videos are cached per video, so re-runs and zooms don't download again.

## Notes

- **No audio.** It only sees the picture, so it can't tell you what is said.
- Scene mode can skip stretches where little changes. Use `--from/--to` with `--every` to fill gaps.
- OCR is a hint, not a transcript: it misreads small or stylised text. Check numbers by viewing the frame.
- The skill includes honesty rules: if an image isn't actually returned to Claude, it must say it didn't see it rather than describe it.
- Windows OCR works on Windows only; elsewhere install Tesseract for `--ocr`.
- Only use it on videos you are allowed to access, and respect the site's terms.

## License

MIT
