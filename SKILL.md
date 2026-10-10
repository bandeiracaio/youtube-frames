---
name: youtube-frames
description: Watch a YouTube video visually (screen only, no audio). Use when the user gives a YouTube URL or video file and wants to know what is shown on screen. Extracts frames (scene-change, fixed interval or zoom), builds contact sheets, optionally reads on-screen text, and keeps a timeline file.
---

# YouTube frames (visual only, no audio)

Run: `python ~/.claude/skills/youtube-frames/frames.py "<url or local file>" [options]`
(`frames.sh` is a wrapper for the same script.)

## Pick a mode
- `--scene [T]` (default choice): frames only where the picture changes. Keeps the strongest `--max` changes (default 40) at least `--gap` seconds apart (default 2). Best for talking-head, slide and mixed videos. About 5 sheets for a 12-minute video.
- `--every SEC`: a frame every SEC seconds (default 10), thinned evenly if it exceeds `--max`. Best for steady screen recordings.
- `--zoom MM:SS [--span SEC]`: dense 1 fps, full size around one moment. Use to read small text or check a detail.

## Options
- `--from TIME --to TIME`: only a slice (seconds, MM:SS or H:MM:SS). Timestamps stay real video time.
- `--max N`: frame cap. `--gap SEC`: minimum spacing in scene mode.
- `--dense`: 4x4 sheets at a smaller size. Cheaper per frame, less legible. Good for a first rough pass.
- `--ocr`: read on-screen text into `timeline.md` and `ocr.tsv`. Uses Tesseract if installed, otherwise the built-in Windows OCR (no install). It misreads small or stylised text, so treat it as a hint and verify numbers by viewing the frame.
- `--no-dedupe`: keep near-identical frames (default drops them).
- `--keep-black`: keep near-black transition frames (default drops them; zoom mode never drops).

## Output
`~/Documents/YouTubeFrames/<video-id>/run-<timestamp>/` holds `f_NNN.jpg` (1280 px), `sheet_NN.jpg` (contact sheets), `times.txt` and `timeline.md`. The downloaded video is cached in `<video-id>/`, so re-runs and zooms do not download again. The script prints the sheet paths, the frame-to-time map and a token estimate for viewing everything.

## Workflow
1. Start with `--scene --ocr`. If the printed token estimate is large, add `--dense` or lower `--max`.
2. Read the `sheet_*.jpg` files with the Read tool, in small batches.
3. Describe what is on screen, using times from `timeline.md`. After viewing, set that row's `seen` to `yes` and fill `description`, so the file is a reusable record.
4. For anything unclear or too small, run `--zoom` on that moment, or `--from/--to` with `--every` to fill a gap.

## Honesty rules
- If Read returns "media removed: request limit" (or any image is not actually returned), those frames were NOT seen. Say so, never describe them, and retry in smaller batches or in a new turn.
- Scene mode can skip stretches where little changes. Say which time ranges are sparse, and offer `--from/--to` to fill them.
- Never claim to know what is said: this skill has no audio.
- If yt-dlp returns 403 or fails, run `yt-dlp -U` and retry.
