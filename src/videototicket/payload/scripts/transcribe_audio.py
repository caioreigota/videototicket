#!/usr/bin/env python3
"""
Extrai o áudio de um vídeo e transcreve localmente com faster-whisper.

Uso:
    python transcribe_audio.py <video> [--lang pt] [--model small]

--lang aceita "auto" para deixar o faster-whisper detectar o idioma.

Imprime um JSON em stdout:
{
  "has_audio": bool, "language": "pt", "text": "...",
  "segments": [{"start": 0.0, "end": 2.3, "text": "..."}]
}
"""
import argparse
import json
import os
import sys
import tempfile
import subprocess

from ffmpeg_utils import find_ffmpeg, has_audio_stream

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def extract_audio(video, wav_path):
    ffmpeg = find_ffmpeg()
    proc = subprocess.run(
        [ffmpeg, "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav_path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou ao extrair áudio: {proc.stderr}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--lang", default="pt", help="Código do idioma (ex.: pt, en, es) ou 'auto' para detectar")
    ap.add_argument("--model", default="small", help="Tamanho do modelo faster-whisper (tiny/base/small/medium/large-v3)")
    args = ap.parse_args()

    if not has_audio_stream(args.video):
        print(json.dumps({"has_audio": False, "segments": [], "text": ""}, ensure_ascii=False))
        return

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = os.path.join(tmp, "audio.wav")
        extract_audio(args.video, wav_path)

        from faster_whisper import WhisperModel

        model = WhisperModel(args.model, device="cpu", compute_type="int8")
        language = None if args.lang == "auto" else args.lang
        segments, info = model.transcribe(wav_path, language=language, vad_filter=True)

        seg_list = []
        full_text = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                seg_list.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text})
                full_text.append(text)

    result = {
        "has_audio": True,
        "language": info.language,
        "segments": seg_list,
        "text": " ".join(full_text).strip(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
