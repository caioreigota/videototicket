"""Backend Jira Cloud para a skill videototicket.

Autenticação: Basic auth com e-mail (config["jira"]["email"]) + API token
(env var JIRA_API_TOKEN, gerado em https://id.atlassian.com/manage-profile/security/api-tokens).

Observação sobre hierarquia: em projetos "team-managed" o campo `parent`
funciona diretamente. Em projetos clássicos ("company-managed") com Epic
Link, configure `jira.epic_link_field` (ex.: "customfield_10014") em
config.json — o script usa esse campo em vez de `parent` quando presente.
"""
import os

import requests

from .common import TicketBackendError, require_env


def _cfg(config):
    jira = config.get("jira") or {}
    for key in ("site_url", "project_key"):
        if not jira.get(key):
            raise TicketBackendError(f"config.json: jira.{key} não definido.")
    return jira


def _auth(config):
    jira = _cfg(config)
    email = jira.get("email")
    if not email:
        raise TicketBackendError("config.json: jira.email não definido (necessário para autenticação básica).")
    token = require_env(
        "JIRA_API_TOKEN",
        "Gere um API token em https://id.atlassian.com/manage-profile/security/api-tokens e exporte como JIRA_API_TOKEN.",
    )
    return (email, token)


def _base_url(config):
    return _cfg(config)["site_url"].rstrip("/")


def _text_to_adf(text):
    """Converte texto simples (com quebras de linha) para Atlassian Document Format."""
    paragraphs = [p for p in (text or "").split("\n") if p.strip()] or [""]
    return {
        "type": "doc", "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs],
    }


def _find_account_id(config, email_or_name):
    base = _base_url(config)
    r = requests.get(f"{base}/rest/api/3/user/search", params={"query": email_or_name}, auth=_auth(config))
    r.raise_for_status()
    results = r.json()
    if not results:
        raise TicketBackendError(f"Nenhum usuário Jira encontrado para '{email_or_name}'.")
    return results[0]["accountId"]


def search_candidates(config, query, issue_types=None):
    jira = _cfg(config)
    base = _base_url(config)
    types = issue_types or jira.get("parent_issue_types") or ["Epic", "Story"]
    types_jql = ", ".join(f'"{t}"' for t in types)
    jql = f'project = "{jira["project_key"]}" AND issuetype in ({types_jql}) AND text ~ "{query}" ORDER BY updated DESC'
    r = requests.get(f"{base}/rest/api/3/search", params={"jql": jql, "maxResults": 20,
                                                            "fields": "summary,status,issuetype"},
                      auth=_auth(config))
    r.raise_for_status()
    out = []
    for issue in r.json().get("issues", []):
        f = issue["fields"]
        out.append({"id": issue["key"], "titulo": f["summary"], "estado": f["status"]["name"], "tipo": f["issuetype"]["name"]})
    return out


def attach_file(config, ticket_id, file_path, comment=None):
    base = _base_url(config)
    url = f"{base}/rest/api/3/issue/{ticket_id}/attachments"
    with open(file_path, "rb") as f:
        r = requests.post(url, headers={"X-Atlassian-Token": "no-check"},
                           files={"file": (os.path.basename(file_path), f)}, auth=_auth(config))
    r.raise_for_status()
    if comment:
        _add_comment(config, ticket_id, comment)
    return r.json()


def _add_comment(config, ticket_id, text):
    base = _base_url(config)
    r = requests.post(f"{base}/rest/api/3/issue/{ticket_id}/comment",
                       json={"body": _text_to_adf(text)}, auth=_auth(config))
    r.raise_for_status()


def create_ticket(config, data, attachments=None):
    jira = _cfg(config)
    base = _base_url(config)
    ticket_type = data.get("ticket_type") or config.get("ticket_type") or "Bug"
    defaults = config.get("defaults") or {}

    description_parts = []
    if data.get("descricao"):
        description_parts.append(data["descricao"])
    if data.get("repro_steps"):
        description_parts.append("Passos para reproduzir:\n" + data["repro_steps"])
    description = "\n\n".join(description_parts)

    fields = {
        "project": {"key": jira["project_key"]},
        "issuetype": {"name": ticket_type},
        "summary": data["titulo"],
    }
    if description:
        fields["description"] = _text_to_adf(description)

    labels = list(defaults.get("labels") or []) + list(data.get("tags") or [])
    labels = list(dict.fromkeys(labels))
    if labels:
        fields["labels"] = labels

    assignee = data.get("assigned_to") or defaults.get("assignee")
    if assignee:
        fields["assignee"] = {"accountId": _find_account_id(config, assignee)}

    for field, value in {**(defaults.get("custom_fields") or {}), **(data.get("custom_fields") or {})}.items():
        fields[field] = value

    parent = data.get("parent")
    if config.get("require_parent_link") and not parent:
        raise TicketBackendError("config.json define require_parent_link=true, mas 'parent' não foi informado nos dados do ticket.")
    if parent:
        epic_link_field = jira.get("epic_link_field")
        if epic_link_field:
            fields[epic_link_field] = parent
        else:
            fields["parent"] = {"key": parent}

    r = requests.post(f"{base}/rest/api/3/issue", json={"fields": fields}, auth=_auth(config))
    if not r.ok:
        raise TicketBackendError(f"Erro ao criar issue Jira ({r.status_code}): {r.text}")
    key = r.json()["key"]

    for att_path in (attachments or []):
        attach_file(config, key, att_path)

    return {"id": key, "url": f"{base}/browse/{key}"}
