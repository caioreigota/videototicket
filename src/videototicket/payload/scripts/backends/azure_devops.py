"""Backend Azure DevOps (Boards) para a skill videototicket.

Autenticação: PAT (padrão, via env var AZURE_DEVOPS_PAT) ou az CLI
(config["azure_devops"]["auth"] == "az_cli", requer `az login` prévio).
"""
import base64
import html
import os
import shutil
import subprocess
import tempfile

import requests

from .common import TicketBackendError, require_env

AZURE_DEVOPS_RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798"

MAX_ATTACHMENT_BYTES = 59 * 1024 * 1024
TARGET_COMPRESSED_BYTES = 45 * 1024 * 1024
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def _cfg(config):
    ado = config.get("azure_devops") or {}
    for key in ("organization", "project"):
        if not ado.get(key):
            raise TicketBackendError(f"config.json: azure_devops.{key} não definido.")
    return ado


def _headers(config):
    ado = _cfg(config)
    auth = ado.get("auth", "pat")
    if auth == "az_cli":
        az = shutil.which("az") or "az"
        proc = subprocess.run(
            [az, "account", "get-access-token", "--resource", AZURE_DEVOPS_RESOURCE,
             "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise TicketBackendError("Falha ao obter token via az CLI. Rode 'az login' primeiro.\n" + proc.stderr)
        token = proc.stdout.strip()
        if not token:
            raise TicketBackendError("Token vazio retornado pelo az CLI.")
        return {"Authorization": f"Bearer {token}"}
    else:
        pat = require_env(
            "AZURE_DEVOPS_PAT",
            "Gere um Personal Access Token (escopo 'Work Items: Read & Write') em "
            "https://dev.azure.com/<sua-org>/_usersSettings/tokens e exporte como AZURE_DEVOPS_PAT.",
        )
        b64 = base64.b64encode(f":{pat}".encode()).decode()
        return {"Authorization": f"Basic {b64}"}


def _org_project(config):
    ado = _cfg(config)
    org = ado["organization"].rstrip("/")
    return org, ado["project"]


def _to_html(texto):
    if not texto:
        return ""
    return f"<div>{html.escape(texto).replace(chr(10), '<br>' + chr(10))}</div>"


def _find_ffmpeg():
    # scripts/ (onde mora ffmpeg_utils.py) já está em sys.path, pois é lá que
    # o entrypoint create_ticket.py roda a partir de.
    from ffmpeg_utils import find_ffmpeg
    return find_ffmpeg()


def _get_duration(path):
    from ffmpeg_utils import get_duration
    return get_duration(path)


def _compress_video_for_upload(path, tmp_dir):
    ffmpeg = _find_ffmpeg()
    duration = _get_duration(path)
    audio_bitrate = 96_000
    total_bitrate = max(int(TARGET_COMPRESSED_BYTES * 8 / duration), 300_000)
    video_bitrate = max(total_bitrate - audio_bitrate, 150_000)

    out_path = os.path.join(tmp_dir, "compactado_" + os.path.basename(path))
    proc = subprocess.run(
        [ffmpeg, "-y", "-i", path,
         "-c:v", "libx264", "-b:v", str(video_bitrate), "-maxrate", str(video_bitrate),
         "-bufsize", str(video_bitrate * 2),
         "-c:a", "aac", "-b:a", str(audio_bitrate),
         out_path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise TicketBackendError(f"ffmpeg falhou ao comprimir o vídeo: {proc.stderr}")
    return out_path


def get_current_iteration(config, team=None):
    ado = _cfg(config)
    org, project = _org_project(config)
    team = team or ado.get("team") or f"{project} Team"
    url = f"{org}/{project}/{team}/_apis/work/teamsettings/iterations"
    r = requests.get(
        url, params={"$timeframe": "current", "api-version": "7.1"},
        headers=_headers(config),
    )
    r.raise_for_status()
    values = r.json().get("value", [])
    if not values:
        raise TicketBackendError(f"Nenhuma sprint atual configurada para o time '{team}'.")
    return values[0]["path"]


def upload_attachment(config, file_path):
    org, project = _org_project(config)
    filename = os.path.basename(file_path)
    url = f"{org}/{project}/_apis/wit/attachments"
    headers = dict(_headers(config))
    headers["Content-Type"] = "application/octet-stream"
    with open(file_path, "rb") as f:
        content = f.read()
    r = requests.post(url, params={"fileName": filename, "api-version": "7.1"}, headers=headers, data=content)
    r.raise_for_status()
    return r.json()["url"]


def attach_file(config, ticket_id, file_path, comment=None):
    org, project = _org_project(config)
    att_url = upload_attachment(config, file_path)
    patch = [{
        "op": "add", "path": "/relations/-",
        "value": {"rel": "AttachedFile", "url": att_url,
                   "attributes": {"comment": comment or os.path.basename(file_path)}},
    }]
    headers = dict(_headers(config))
    headers["Content-Type"] = "application/json-patch+json"
    r = requests.patch(f"{org}/{project}/_apis/wit/workitems/{ticket_id}",
                        params={"api-version": "7.1"}, headers=headers, json=patch)
    r.raise_for_status()
    return r.json()


def search_candidates(config, query, work_item_types=None):
    ado = _cfg(config)
    org, project = _org_project(config)
    types = work_item_types or ado.get("parent_work_item_types") or ["Product Backlog Item", "Feature", "Epic", "User Story"]
    types_wiql = ", ".join(f"'{t}'" for t in types)
    wiql = {
        "query": (
            f"SELECT [System.Id], [System.Title], [System.State], [System.WorkItemType] "
            f"FROM WorkItems WHERE [System.TeamProject] = '{project}' "
            f"AND [System.WorkItemType] IN ({types_wiql}) "
            f"AND [System.Title] CONTAINS WORDS '{query}' "
            f"ORDER BY [System.ChangedDate] DESC"
        )
    }
    headers = dict(_headers(config))
    headers["Content-Type"] = "application/json"
    r = requests.post(f"{org}/{project}/_apis/wit/wiql", params={"api-version": "7.1"}, headers=headers, json=wiql)
    r.raise_for_status()
    ids = [str(wi["id"]) for wi in r.json().get("workItems", [])][:20]
    if not ids:
        return []
    r2 = requests.get(f"{org}/_apis/wit/workitems", params={"ids": ",".join(ids), "api-version": "7.1"}, headers=_headers(config))
    r2.raise_for_status()
    out = []
    for wi in r2.json().get("value", []):
        f = wi["fields"]
        out.append({"id": wi["id"], "titulo": f.get("System.Title"), "estado": f.get("System.State"), "tipo": f.get("System.WorkItemType")})
    return out


def create_ticket(config, data, attachments=None):
    ado = _cfg(config)
    org, project = _org_project(config)
    ticket_type = data.get("ticket_type") or config.get("ticket_type") or "Bug"
    defaults = config.get("defaults") or {}

    patch = []

    def add(field, value):
        patch.append({"op": "add", "path": f"/fields/{field}", "value": value})

    add("System.Title", data["titulo"])
    if data.get("descricao"):
        add("System.Description", _to_html(data["descricao"]))
    if data.get("repro_steps"):
        add("Microsoft.VSTS.TCM.ReproSteps", _to_html(data["repro_steps"]))
    add("System.AreaPath", data.get("area_path") or defaults.get("area_path") or project)

    assigned_to = data.get("assigned_to") or defaults.get("assignee")
    if assigned_to:
        add("System.AssignedTo", assigned_to)

    labels = list(defaults.get("tags") or []) + list(data.get("tags") or [])
    labels = list(dict.fromkeys(labels))  # dedup mantendo ordem
    if labels:
        add("System.Tags", "; ".join(labels))

    for field, value in {**(defaults.get("custom_fields") or {}), **(data.get("custom_fields") or {})}.items():
        add(field, value)

    if data.get("iteration_path"):
        iteration_path = data["iteration_path"]
    elif config.get("require_parent_link") is not False:
        # só resolve sprint atual automaticamente quando fizer sentido para o fluxo do time
        try:
            iteration_path = get_current_iteration(config, data.get("team"))
        except TicketBackendError:
            iteration_path = None
    else:
        iteration_path = None
    if iteration_path:
        add("System.IterationPath", iteration_path)

    if data.get("severity"):
        add("Microsoft.VSTS.Common.Severity", data["severity"])

    if config.get("require_parent_link"):
        parent = data.get("parent")
        if not parent:
            raise TicketBackendError("config.json define require_parent_link=true, mas 'parent' não foi informado nos dados do ticket.")
        patch.append({
            "op": "add", "path": "/relations/-",
            "value": {"rel": "System.LinkTypes.Hierarchy-Reverse", "url": f"{org}/_apis/wit/workItems/{parent}"},
        })
    elif data.get("parent"):
        patch.append({
            "op": "add", "path": "/relations/-",
            "value": {"rel": "System.LinkTypes.Hierarchy-Reverse", "url": f"{org}/_apis/wit/workItems/{data['parent']}"},
        })

    tmp_dir = tempfile.mkdtemp(prefix="videototicket_")
    try:
        for att_path in (attachments or []):
            upload_path = att_path
            comment = os.path.basename(att_path)
            size = os.path.getsize(att_path)
            if size > MAX_ATTACHMENT_BYTES:
                ext = os.path.splitext(att_path)[1].lower()
                if ext not in VIDEO_EXTENSIONS:
                    raise TicketBackendError(
                        f"Anexo '{att_path}' tem {size / 1024 / 1024:.1f} MB e excede o limite de 60 MB "
                        "do Azure DevOps. Compressão automática só é aplicada a vídeos."
                    )
                upload_path = _compress_video_for_upload(att_path, tmp_dir)
                new_size = os.path.getsize(upload_path)
                comment = f"{os.path.basename(att_path)} (comprimido de {size / 1024 / 1024:.0f} MB para {new_size / 1024 / 1024:.0f} MB — limite de 60 MB do Azure DevOps)"
            att_url = upload_attachment(config, upload_path)
            patch.append({
                "op": "add", "path": "/relations/-",
                "value": {"rel": "AttachedFile", "url": att_url, "attributes": {"comment": comment}},
            })
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    headers = dict(_headers(config))
    headers["Content-Type"] = "application/json-patch+json"
    r = requests.post(f"{org}/{project}/_apis/wit/workitems/${ticket_type}",
                       params={"api-version": "7.1"}, headers=headers, json=patch)
    if not r.ok:
        raise TicketBackendError(f"Erro ao criar work item ({r.status_code}): {r.text}")
    result = r.json()
    return {"id": result["id"], "url": f"{org}/{project}/_workitems/edit/{result['id']}"}
