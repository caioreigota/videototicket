"""Resolve o diretório de destino por plataforma e copia o payload da skill para lá."""
import importlib.resources
import os
import shutil
from pathlib import Path

SKILL_NAME = "videototicket"

# Cada entrada resolve o diretório onde a skill deve ser escrita.
# "claude": convenção nativa do Claude Code.
# "agents"/"skills": spec genérica Agent-Skills (github.com/anthropics/skills),
# lida por outros frameworks compatíveis (Cursor, Codex e afins).
_PLATFORM_DIRS = {
    "claude": {
        "global": lambda: Path.home() / ".claude" / "skills" / SKILL_NAME,
        "project": lambda: Path.cwd() / ".claude" / "skills" / SKILL_NAME,
    },
    "agents": {
        "global": lambda: Path.home() / ".agents" / "skills" / SKILL_NAME,
        "project": lambda: Path.cwd() / ".agents" / "skills" / SKILL_NAME,
    },
}
_PLATFORM_DIRS["skills"] = _PLATFORM_DIRS["agents"]  # alias

PLATFORMS = sorted(_PLATFORM_DIRS)

# Pasta padrão (fixa) onde os vídeos são colocados/processados, criada na
# raiz do projeto por `install --project`. Continua configurável depois via
# folders.pending/folders.processed em config.json — isto é só o default.
DEFAULT_PENDING_DIR = "videototicket/pendentes"
DEFAULT_PROCESSED_DIR = "videototicket/processados"


def _payload_dir():
    return importlib.resources.files("videototicket") / "payload"


def target_dir(platform, project):
    if platform not in _PLATFORM_DIRS:
        raise ValueError(f"Plataforma desconhecida: '{platform}'. Opções: {PLATFORMS}")
    key = "project" if project else "global"
    return Path(_PLATFORM_DIRS[platform][key]())


def create_video_folders(base=None):
    """Cria a estrutura fixa de pastas para os vídeos (pendentes/processados)
    na raiz do projeto, com um .gitkeep para o git rastrear mesmo vazias."""
    base = Path(base) if base is not None else Path.cwd()
    created = []
    for rel in (DEFAULT_PENDING_DIR, DEFAULT_PROCESSED_DIR):
        folder = base / rel
        already_existed = folder.exists()
        folder.mkdir(parents=True, exist_ok=True)
        gitkeep = folder / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
        if not already_existed:
            created.append(folder)
    return created


def install_skill(platform="claude", project=False):
    src = _payload_dir()
    dst = target_dir(platform, project)
    dst.mkdir(parents=True, exist_ok=True)

    copied = []
    with importlib.resources.as_file(src) as src_path:
        for root, _, files in os.walk(src_path):
            rel_root = Path(root).relative_to(src_path)
            for fname in files:
                if fname.endswith((".pyc",)) or fname == "__pycache__":
                    continue
                src_file = Path(root) / fname
                dst_file = dst / rel_root / fname
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                copied.append(dst_file)

    print(f"Skill '{SKILL_NAME}' instalada em: {dst}")
    print(f"  {len(copied)} arquivo(s) copiado(s)/atualizado(s).")
    print("  config.json (se você já tiver configurado) não foi tocado — ele não faz parte do payload.")

    if project:
        try:
            rel = dst.relative_to(Path.cwd())
        except ValueError:
            rel = dst
        print(f"\nInstalação de projeto — se for versionar, rode: git add {rel}")

        created_video_dirs = create_video_folders()
        print(f"\nPasta de vídeos pronta em: {Path.cwd() / 'videototicket'}")
        print(f"  - {DEFAULT_PENDING_DIR}/   (coloque os vídeos a processar aqui)")
        print(f"  - {DEFAULT_PROCESSED_DIR}/  (destino automático após o ticket ser criado)")
        if not created_video_dirs:
            print("  (já existiam — nada foi sobrescrito)")
        print("  Pode mudar esses caminhos depois em config.json (folders.pending/folders.processed).")

    print('\nAbra seu assistente e peça algo como "criar ticket a partir de vídeo".')
    print("Na primeira execução, a skill guia você pela configuração (plataforma de tickets, credenciais etc).")
    return dst


def uninstall_skill(platform="claude", project=False):
    dst = target_dir(platform, project)
    if not dst.exists():
        print(f"Nada instalado em: {dst}")
        return dst
    shutil.rmtree(dst)
    print(f"Skill removida de: {dst}")
    return dst
