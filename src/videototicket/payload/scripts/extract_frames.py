#!/usr/bin/env python3
"""
Extrai frames de um vídeo para análise visual (bug, feedback, gravação de tela etc).

Regra:
- duração <= 120s -> 1 frame por segundo (fps=1)
- duração > 120s  -> detecção de cena (scene detection)

Uso:
    python extract_frames.py <video> <output_dir> [--threshold 0.3]

Imprime um JSON em stdout:
{
  "video": "...", "duration": 123.4, "mode": "fps=1" | "scene-detection",
  "frames": [{"file": "...", "timestamp": 12.0}, ...]
}
"""
import argparse
import json
import os
import re
import subprocess
import sys

from ffmpeg_utils import find_ffmpeg, get_duration

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def extract_fixed_fps(video, out_dir, fps=1):
    ffmpeg = find_ffmpeg()
    pattern = os.path.join(out_dir, "frame_%04d.png")
    proc = subprocess.run(
        [ffmpeg, "-y", "-i", video, "-vf", f"fps={fps}", pattern],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou na extração fps={fps}: {proc.stderr}")
    frames = []
    for fname in sorted(os.listdir(out_dir)):
        if fname.startswith("frame_") and fname.endswith(".png"):
            idx = int(fname[len("frame_"):-len(".png")])
            frames.append({"file": os.path.join(out_dir, fname), "timestamp": round((idx - 1) / fps, 2)})
    return frames


def extract_scene_detection(video, out_dir, threshold=0.3):
    ffmpeg = find_ffmpeg()
    pattern = os.path.join(out_dir, "scene_%04d.png")
    proc = subprocess.run(
        [ffmpeg, "-y", "-i", video, "-vf",
         f"select='gt(scene,{threshold})',showinfo", "-vsync", "vfr", pattern],
        capture_output=True, text=True,
    )
    log = proc.stderr or ""
    timestamps = [float(m) for m in re.findall(r"pts_time:([\d.]+)", log)]
    files = sorted(f for f in os.listdir(out_dir) if f.startswith("scene_") and f.endswith(".png"))
    frames = []
    for i, fname in enumerate(files):
        ts = round(timestamps[i], 2) if i < len(timestamps) else None
        frames.append({"file": os.path.join(out_dir, fname), "timestamp": ts})
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("output_dir")
    ap.add_argument("--threshold", type=float, default=0.3)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    duration = get_duration(args.video)
    if duration <= 120:
        mode = "fps=1"
        frames = extract_fixed_fps(args.video, args.output_dir, fps=1)
    else:
        mode = "scene-detection"
        frames = extract_scene_detection(args.video, args.output_dir, args.threshold)
        if not frames:
            mode = "fps=1 (fallback: scene-detection não gerou frames)"
            frames = extract_fixed_fps(args.video, args.output_dir, fps=1)

    print(json.dumps(
        {"video": args.video, "duration": duration, "mode": mode, "frames": frames},
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
