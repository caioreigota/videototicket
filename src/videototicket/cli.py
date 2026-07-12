"""CLI: `videototicket install` / `videototicket uninstall`."""
import argparse
import sys

from .installer import PLATFORMS, install_skill, uninstall_skill


def build_parser():
    parser = argparse.ArgumentParser(
        prog="videototicket",
        description="Instala/remove a skill videototicket no seu assistente de IA.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    install_p = sub.add_parser("install", help="Instala (ou atualiza) a skill")
    install_p.add_argument(
        "--project", action="store_true",
        help="Instala no projeto atual, em vez do perfil global do usuário",
    )
    install_p.add_argument(
        "--platform", choices=PLATFORMS, default="claude",
        help="Plataforma alvo (default: claude). Use 'codex' para CODEX_HOME/skills ou 'agents' para Agent-Skills.",
    )

    uninstall_p = sub.add_parser("uninstall", help="Remove a skill instalada")
    uninstall_p.add_argument(
        "--project", action="store_true",
        help="Remove a instalação do projeto atual, em vez da instalação global",
    )
    uninstall_p.add_argument(
        "--platform", choices=PLATFORMS, default="claude",
        help="Plataforma alvo usada na instalação (default: claude)",
    )

    return parser


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "install":
        install_skill(platform=args.platform, project=args.project)
    elif args.command == "uninstall":
        uninstall_skill(platform=args.platform, project=args.project)
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
