"""Helpers para localizar ffmpeg/ffprobe, compartilhados pelos scripts da skill."""
import os
import shutil
import subprocess

WINGET_HINT = "Instale com: winget install --id=Gyan.FFmpeg -e (Windows) ou via seu gerenciador de pacotes (apt/brew/etc) em outros SOs."


def _find_in_winget(binary_name):
    base = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    if os.path.isdir(base):
        for root, _, files in os.walk(base):
            if binary_name in files:
                return os.path.join(root, binary_name)
    return None


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    exe = _find_in_winget("ffmpeg.exe")
    if exe:
        return exe
    raise FileNotFoundError(f"ffmpeg não encontrado no PATH. {WINGET_HINT}")


def find_ffprobe():
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    exe = _find_in_winget("ffprobe.exe")
    if exe:
        return exe
    ffmpeg_dir = os.path.dirname(find_ffmpeg())
    cand = os.path.join(ffmpeg_dir, "ffprobe.exe")
    if os.path.exists(cand):
        return cand
    raise FileNotFoundError(f"ffprobe não encontrado no PATH. {WINGET_HINT}")


def get_duration(path):
    ffprobe = find_ffprobe()
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"Não foi possível ler a duração de '{path}': {out.stderr}")
    return float(out.stdout.strip())


def has_audio_stream(path):
    ffprobe = find_ffprobe()
    out = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    return bool(out.stdout.strip())
