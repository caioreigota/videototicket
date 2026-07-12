#!/usr/bin/env python3
"""
Cria um ticket (Bug/Issue) na plataforma configurada em config.json
(Azure DevOps, Jira ou GitHub), a partir dos dados extraídos de um vídeo.

Uso:
    python create_ticket.py --input dados.json [--dry-run] [--config caminho/config.json]

dados.json:
{
  "titulo": "[Área] Descrição curta do problema",
  "descricao": "...",
  "repro_steps": "1. ...\n2. ...\n3. ...",
  "parent": "222442",              // opcional, exceto se require_parent_link=true no config
  "area_path": "...",              // opcional, só Azure DevOps
  "tags": ["..."],                 // opcional, some com defaults.labels/tags do config
  "custom_fields": {"...": "..."}, // opcional, some com defaults.custom_fields do config
  "severity": "3 - Medium",        // opcional, só Azure DevOps
  "assigned_to": null,             // opcional, default vem de config.defaults.assignee
  "team": null,                    // opcional, só Azure DevOps (resolução de sprint atual)
  "attachments": ["C:/caminho/frame_0007.png", "C:/caminho/video.mp4"]
}

--dry-run: mostra os dados e a plataforma resolvida, mas não chama a API
(nenhum efeito colateral).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backends.common import load_config, TicketBackendError  # noqa: E402

BACKENDS = {}


def _get_backend(platform):
    if platform not in BACKENDS:
        if platform == "azure-devops":
            from backends import azure_devops as mod
        elif platform == "jira":
            from backends import jira as mod
        elif platform == "github":
            from backends import github as mod
        else:
            raise TicketBackendError(
                f"Plataforma '{platform}' desconhecida. Use 'azure-devops', 'jira' ou 'github' em config.json."
            )
        BACKENDS[platform] = mod
    return BACKENDS[platform]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    config = load_config(args.config)
    platform = config.get("platform")
    if not platform:
        print("config.json não define 'platform'. Veja config.example.json.", file=sys.stderr)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    attachments = data.get("attachments") or []
    for att in attachments:
        if not os.path.isfile(att):
            print(f"Anexo não encontrado: {att}", file=sys.stderr)
            sys.exit(1)

    if args.dry_run:
        preview = dict(data)
        preview["_platform_resolvida"] = platform
        preview["_require_parent_link"] = bool(config.get("require_parent_link"))
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return

    backend = _get_backend(platform)
    try:
        result = backend.create_ticket(config, data, attachments)
    except Exception as e:
        print(f"Erro ao criar ticket: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Ticket criado com sucesso: {result['id']}")
    print(f"URL: {result['url']}")
    pending = result.get("attachments_pending_manual")
    if pending:
        print("\nATENÇÃO: os anexos abaixo NÃO foram enviados automaticamente (limitação da plataforma) e precisam ser anexados manualmente:")
        for p in pending:
            print(f"  - {p}")


if __name__ == "__main__":
    main()
