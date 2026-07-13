"""Backend GitHub Issues para a skill videototicket.

Autenticação: usa a `gh` CLI já autenticada (`gh auth login` / `gh auth status`).
Não requer token em config.json nem em variável de ambiente.

Limitação importante: a REST API pública do GitHub NÃO tem endpoint para
anexar arquivos (imagem/vídeo) a uma issue — isso só acontece via upload no
navegador (drag-and-drop), que gera uma URL em user-images.githubusercontent.com.
Por isso `create_ticket` aqui NUNCA sobe os anexos automaticamente: ele cria a
issue e devolve, junto com o resultado, a lista de arquivos que precisam ser
arrastados manualmente para o corpo da issue (ou anexados via comentário).
"""
import json
import shutil
import subprocess

from .common import TicketBackendError


def _gh():
    exe = shutil.which("gh")
    if not exe:
        raise TicketBackendError(
            "GitHub CLI ('gh') não encontrado no PATH. Instale em https://cli.github.com "
            "e rode 'gh auth login' antes de usar a plataforma github."
        )
    return exe


def _run(args):
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise TicketBackendError(f"Comando 'gh' falhou: {' '.join(args)}\n{proc.stderr}")
    return proc.stdout


def _cfg(config):
    gh_cfg = config.get("github") or {}
    if not gh_cfg.get("repo"):
        raise TicketBackendError("config.json: github.repo não definido (formato 'dono/repositorio').")
    return gh_cfg


def search_candidates(config, query, extra_search=None):
    gh_cfg = _cfg(config)
    gh = _gh()
    search = query
    if extra_search:
        search += " " + extra_search
    out = _run([gh, "issue", "list", "--repo", gh_cfg["repo"], "--search", search,
                "--state", "all", "--limit", "20", "--json", "number,title,state"])
    items = json.loads(out or "[]")
    return [{"id": it["number"], "titulo": it["title"], "estado": it["state"], "tipo": "issue"} for it in items]


def attach_file(config, ticket_id, file_path, comment=None):
    raise TicketBackendError(
        "A API do GitHub não permite anexar arquivos a uma issue de forma automatizada. "
        f"Anexe manualmente '{file_path}' arrastando-o para a issue #{ticket_id} no navegador, "
        "ou use 'gh issue comment' para linkar um arquivo já hospedado em outro lugar."
    )


def create_ticket(config, data, attachments=None):
    gh_cfg = _cfg(config)
    gh = _gh()
    defaults = config.get("defaults") or {}

    body_parts = []
    if data.get("descricao"):
        body_parts.append(data["descricao"])
    if data.get("repro_steps"):
        body_parts.append("### Passos para reproduzir\n" + data["repro_steps"])
    parent = data.get("parent") or config.get("default_parent")
    if parent:
        body_parts.append(f"Relacionado a #{parent}")
    body = "\n\n".join(body_parts) or "(sem descrição)"

    args = [gh, "issue", "create", "--repo", gh_cfg["repo"], "--title", data["titulo"], "--body", body]

    labels = list(defaults.get("labels") or []) + list(data.get("tags") or [])
    labels = list(dict.fromkeys(labels))
    for label in labels:
        args += ["--label", label]

    assignee = data.get("assigned_to") or defaults.get("assignee")
    if assignee:
        args += ["--assignee", assignee]

    if config.get("require_parent_link") and not parent:
        raise TicketBackendError("config.json define require_parent_link=true, mas 'parent' não foi informado nos dados do ticket.")

    out = _run(args).strip()
    issue_url = out.splitlines()[-1] if out else ""
    number = issue_url.rstrip("/").rsplit("/", 1)[-1]

    pending_attachments = list(attachments or [])
    if pending_attachments:
        file_list = "\n".join(f"- `{p}`" for p in pending_attachments)
        _run([gh, "issue", "comment", "--repo", gh_cfg["repo"], number, "--body",
              "Arquivos capturados no vídeo original (anexar manualmente, a API do GitHub não faz upload automático):\n" + file_list])

    return {"id": number, "url": issue_url, "attachments_pending_manual": pending_attachments}
