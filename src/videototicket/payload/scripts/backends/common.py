"""Config loading e helpers compartilhados pelos backends de ticket."""
import json
import os


def skill_root():
    # scripts/backends/common.py -> scripts -> skill root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def config_path(explicit=None):
    return (
        explicit
        or os.environ.get("VIDEO_TO_TICKET_CONFIG")
        or os.path.join(skill_root(), "config.json")
    )


def load_config(explicit=None):
    path = config_path(explicit)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Config não encontrado em '{path}'. Copie config.example.json para config.json "
            "e preencha os dados da sua plataforma (veja SKILL.md, seção 'Configuração inicial')."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TicketBackendError(RuntimeError):
    pass


def require_env(var_name, hint):
    value = os.environ.get(var_name)
    if not value:
        raise TicketBackendError(f"Variável de ambiente '{var_name}' não definida. {hint}")
    return value
