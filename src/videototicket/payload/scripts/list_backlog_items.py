#!/usr/bin/env python3
"""
Busca candidatos a item pai (Epic/Feature/PBI) na plataforma configurada,
para linkar o ticket criado a partir do vídeo (fluxo opcional, controlado por
config.json -> require_parent_link).

Uso:
    python list_backlog_items.py --query "texto" [--config caminho/config.json]

Imprime um JSON: [{"id": "...", "titulo": "...", "estado": "...", "tipo": "..."}, ...]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backends.common import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    config = load_config(args.config)
    platform = config.get("platform")

    if platform == "azure-devops":
        from backends import azure_devops as backend
    elif platform == "jira":
        from backends import jira as backend
    elif platform == "github":
        from backends import github as backend
    else:
        print(f"Plataforma '{platform}' desconhecida em config.json.", file=sys.stderr)
        sys.exit(1)

    try:
        items = backend.search_candidates(config, args.query)
    except Exception as e:
        print(f"Erro ao buscar candidatos: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(items, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
