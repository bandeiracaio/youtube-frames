#!/usr/bin/env python3
"""Extract frames from a video (YouTube URL or local file), video only, no audio.

Modes (pick one):
  --every SEC          a frame every SEC seconds (default 10)
  --scene [T]          only frames where the picture changes by more than T (default start 0.05).
                       The threshold is raised automatically until the count fits --max.
  --zoom TIME          dense 1 fps, full size around TIME (use --span SEC, default 10)
Options:
  --from TIME --to TIME   only look at this slice (TIME = seconds, MM:SS or H:MM:SS)
  --max N                 frame cap (default 40; zoom default 12)
  --gap SEC               scene mode: minimum seconds between kept frames (default 2)
  --dense                 4x4 contact sheets at smaller size (cheaper, less legible)
  --ocr                   read on-screen text (Tesseract if installed, else Windows OCR)
  --no-dedupe             keep near-identical frames
  --keep-black            keep near-black transition frames (dropped by default)
  --out DIR               base folder (default ~/Documents/YouTubeFrames)
Output: <base>/<video-id>/run-<timestamp>/ with f_NNN.jpg, sheet_NN.jpg, times.txt,
        timeline.md (and ocr.tsv with --ocr). The downloaded video is cached in <base>/<video-id>/.
"""
import argparse, datetime, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

if sys.version_info < (3, 8):
    sys.exit(f"youtube-frames needs Python 3.8+ (this is {sys.version.split()[0]}). Try `python` instead of `python3`.")


def is_file(p):
    try:
        return Path(p).is_file()
    except (OSError, ValueError):  # a URL is not a valid path on Windows
        return False

HERE = Path(__file__).resolve().parent


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def parse_time(s):
    parts = [float(p) for p in str(s).split(":")]
    t = 0.0
    for p in parts:
        t = t * 60 + p
    return t


def fmt(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def get_video(src, base):
    """Return (video_path, video_id, folder). Downloads and caches YouTube videos."""
    if is_file(src):
        stem = Path(src).stem if Path(src).stem != "video" else Path(src).resolve().parent.name
        vid = re.sub(r"[^\w.-]", "_", stem)
        folder = base / vid
        folder.mkdir(parents=True, exist_ok=True)
        return Path(src), vid, folder
    r = run(["yt-dlp", "--no-warnings", "--no-playlist", "--print", "id", src], text=True)
    vid = r.stdout.strip().splitlines()[-1] if r.returncode == 0 and r.stdout.strip() else None
    if not vid:
        sys.exit(f"yt-dlp could not read this URL:\n{r.stderr.strip()[-400:]}\nTip: update with `yt-dlp -U`.")
    folder = base / vid
    folder.mkdir(parents=True, exist_ok=True)
    cached = [p for p in folder.glob("video.*") if p.suffix not in (".part", ".ytdl")]
    if cached:
        return cached[0], vid, folder
    r = run(["yt-dlp", "-q", "--no-warnings", "--no-playlist", "-f", "bv*[height<=720]/bv*/b",
             "-o", str(folder / "video.%(ext)s"), src], text=True)
    cached = [p for p in folder.glob("video.*") if p.suffix not in (".part", ".ytdl")]
    if not cached:
        sys.exit(f"Download failed:\n{r.stderr.strip()[-400:]}\nTip: update with `yt-dlp -U`.")
    return cached[0], vid, folder


def duration(video):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], text=True)
    return float(r.stdout.strip())


def scene_scores(video, start, end, workdir):
    """One pass over the slice -> list of (time, score)."""
    meta = workdir / "scores.txt"
    # run from workdir with a bare filename: ffmpeg filter option values choke on Windows drive-letter paths
    vf = "scale=320:-2,select='gte(scene,0)',metadata=print:key=lavfi.scene_score:file=scores.txt"
    run(["ffmpeg", "-nostats", "-loglevel", "error", "-ss", str(start), "-t", str(end - start), "-i",
         str(video), "-an", "-vf", vf, "-f", "null", "-"], cwd=workdir)
    out, t = [], None
    for line in meta.read_text().splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"lavfi.scene_score=([\d.]+)", line)
        if m and t is not None:
            out.append((start + t, float(m.group(1))))
    return out


def pick_scene(scores, start, thr, gap, cap):
    """Frames where the picture changes more than thr, at least gap seconds apart.
    If more than cap qualify, keep the cap strongest changes (not the earliest)."""
    cands = sorted(((sc, t) for t, sc in scores if sc > thr), reverse=True)
    picked = [start]
    for sc, t in cands:
        if len(picked) >= cap:
            break
        if all(abs(t - p) >= gap for p in picked):
            picked.append(t)
    qualifying = sum(1 for sc, t in cands)
    return sorted(picked), qualifying


def signature(video, t):
    r = run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
             "-vf", "scale=16:16,format=gray", "-f", "rawvideo", "-"])
    return r.stdout if len(r.stdout) == 256 else None


def similar(a, b, tol=3.0):
    return a is not None and b is not None and sum(abs(x - y) for x, y in zip(a, b)) / 256 < tol


def extract(video, t, dest, width=1280):
    r = run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
             "-vf", f"scale={width}:-2", "-q:v", "3", str(dest)])
    return dest.exists() and r.returncode == 0


def ocr(files, outdir):
    """Return {filename: text}. Tesseract if on PATH, else built-in Windows OCR."""
    result = {}
    if shutil.which("tesseract"):
        engine = "tesseract"
        for f in files:
            r = run(["tesseract", str(f), "-", "--psm", "11"], text=True)
            result[f.name] = " | ".join(l.strip() for l in r.stdout.splitlines() if l.strip())
    elif shutil.which("powershell.exe"):
        engine = "windows-ocr"
        tsv = outdir / "ocr.tsv"
        for i in range(0, len(files), 40):  # keep command lines short
            chunk = files[i:i + 40]
            part = outdir / f"ocr_part{i}.tsv"
            run(["powershell.exe", "-NoProfile", "-File", str(HERE / "ocr.ps1"), str(part)] + [str(f) for f in chunk])
            if part.exists():
                for line in part.read_text(encoding="utf-8").splitlines():
                    name, _, text = line.partition("\t")
                    result[name] = text.strip()
                part.unlink()
    else:
        return {}, "none"
    (outdir / "ocr.tsv").write_text("\n".join(f"{k}\t{v}" for k, v in result.items()), encoding="utf-8")
    return result, engine


def make_sheets(run_dir, n, dense):
    width, tile = (480, "4x4") if dense else (640, "3x3")
    r = run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "1", "-i", str(run_dir / "f_%03d.jpg"),
             "-vf", f"scale={width}:-2,tile={tile}", str(run_dir / "sheet_%02d.jpg")])
    return sorted(run_dir.glob("sheet_*.jpg"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--every", type=float)
    ap.add_argument("--scene", nargs="?", const=0.05, type=float)
    ap.add_argument("--zoom", type=str)
    ap.add_argument("--span", type=float, default=10)
    ap.add_argument("--from", dest="t_from", type=str)
    ap.add_argument("--to", dest="t_to", type=str)
    ap.add_argument("--max", type=int)
    ap.add_argument("--gap", type=float, default=2)
    ap.add_argument("--dense", action="store_true")
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--no-dedupe", action="store_true")
    ap.add_argument("--keep-black", action="store_true")
    ap.add_argument("--out", type=str, default=str(Path.home() / "Documents" / "YouTubeFrames"))
    a = ap.parse_args()

    base = Path(a.out)
    video, vid, folder = get_video(a.source, base)
    dur = duration(video)
    start = parse_time(a.t_from) if a.t_from else 0.0
    end = min(parse_time(a.t_to), dur) if a.t_to else dur

    mode, note = "every", ""
    if a.zoom is not None:
        mode = "zoom"
        c = parse_time(a.zoom)
        start, end = max(0, c - a.span / 2), min(dur, c + a.span / 2)
        cap = a.max or 12
        times = [start + i for i in range(int(end - start) + 1)][:cap]
    elif a.scene is not None:
        mode = "scene"
        cap = a.max or 40
        work = Path(tempfile.mkdtemp(prefix="l30-scene-"))
        scores = scene_scores(video, start, end, work)
        shutil.rmtree(work, ignore_errors=True)
        thr = a.scene
        times, qualifying = pick_scene(scores, start, thr, a.gap, cap)
        note = f"(threshold {thr}, {len(times)} frames" + (f", kept the strongest of {qualifying} candidate changes)" if qualifying + 1 > cap else ")")
    else:
        step = a.every or 10
        cap = a.max or 40
        times = [start + i * step for i in range(int((end - start) // step) + 1)]
        if len(times) > cap:  # thin evenly so the whole slice stays covered
            times = [times[int(i * len(times) / cap)] for i in range(cap)]
            note = f"thinned evenly to {cap} frames (effective step ~{(end - start) / cap:.0f}s)"
    times = [t for t in times if t < dur - 0.05] or [start]

    run_dir = folder / ("run-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    run_dir.mkdir(parents=True)

    kept, dropped, black, last_sig = [], 0, 0, None
    for t in times:
        if mode != "zoom":
            sig = signature(video, t)
            if sig is not None and not a.keep_black and max(sig) < 20:  # near-black transition frame (peak brightness, so dark UIs with bright text are kept)
                black += 1
                continue
            if not a.no_dedupe:
                if kept and similar(sig, last_sig):
                    dropped += 1
                    continue
                last_sig = sig
        dest = run_dir / f"f_{len(kept) + 1:03d}.jpg"
        if extract(video, t, dest):
            kept.append((t, dest))
    if not kept:
        sys.exit("No frames could be extracted.")

    sheets = make_sheets(run_dir, len(kept), a.dense)

    texts, engine = {}, "off"
    if a.ocr:
        texts, engine = ocr([d for _, d in kept], run_dir)

    (run_dir / "times.txt").write_text("\n".join(f"{d.name} {fmt(t)}" for t, d in kept), encoding="utf-8")
    rows = ["| time | frame | seen | on-screen text (OCR) | description |", "|---|---|---|---|---|"]
    for t, d in kept:
        txt = texts.get(d.name, "").replace("|", "/")
        rows.append(f"| {fmt(t)} | {d.name} | no | {txt} | |")
    (run_dir / "timeline.md").write_text(
        f"# Timeline: {a.source}\n\n- mode: {mode} {note}\n- range: {fmt(start)} to {fmt(end)} of {fmt(dur)}\n"
        f"- OCR: {engine}\n- 'seen' stays `no` until a frame has actually been viewed and described. "
        f"Anything not seen must not be described.\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    shutil.copyfile(run_dir / "timeline.md", folder / "timeline.md")

    per = 16 if a.dense else 9
    print(f"Run folder : {run_dir}")
    print(f"Video cache: {video}")
    print(f"Mode       : {mode} {note}".rstrip())
    print(f"Range      : {fmt(start)} to {fmt(end)} (video is {fmt(dur)})")
    print(f"Frames     : {len(kept)} kept, {dropped} near-duplicates and {black} near-black frames dropped")
    print(f"Sheets     : {len(sheets)} ({per} frames each){' [dense]' if a.dense else ''} ~{len(sheets) * (3500 if a.dense else 5000):,} tokens to view all")
    print(f"OCR        : {engine}" + (f", {sum(1 for v in texts.values() if v)} frames with text" if a.ocr else ""))
    print(f"Timeline   : {run_dir / 'timeline.md'}")
    for s in sheets:
        print(f"  {s}")
    print("--- frame -> time ---")
    print(" ".join(f"{d.name[2:5]}={fmt(t)}" for t, d in kept))


if __name__ == "__main__":
    main()
