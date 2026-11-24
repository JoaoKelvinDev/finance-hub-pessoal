"""Procedimento administrativo: cria o ÚNICO usuário proprietário no Supabase Auth.

Uso: uv run python -m app.cli create-owner --email voce@exemplo.com
A senha é lida de FH_OWNER_PASSWORD ou pedida no terminal. Imprime o UUID para OWNER_SUBJECT.
"""

import argparse
import getpass
import os
import sys

import httpx

from app.core.config import get_settings


def create_owner(email: str, password: str) -> str:
    s = get_settings()
    if not s.supabase_service_role_key:
        sys.exit("Defina SUPABASE_SERVICE_ROLE_KEY no .env (somente servidor).")
    if s.owner_subject:
        sys.exit("OWNER_SUBJECT já configurado. Trocar o proprietário exige remover o atual manualmente.")
    headers = {"apikey": s.supabase_service_role_key, "Authorization": f"Bearer {s.supabase_service_role_key}"}
    r = httpx.post(
        f"{s.supabase_url.rstrip('/')}/auth/v1/admin/users",
        headers=headers,
        json={"email": email, "password": password, "email_confirm": True},
        timeout=15,
    )
    if r.status_code >= 400:
        sys.exit(f"Falha ao criar proprietário ({r.status_code}): {r.text}")
    return r.json()["id"]


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    co = sub.add_parser("create-owner")
    co.add_argument("--email", required=True)
    args = parser.parse_args()

    if args.cmd == "create-owner":
        password = os.environ.get("FH_OWNER_PASSWORD") or getpass.getpass("Senha do proprietário: ")
        if len(password) < 10:
            sys.exit("A senha precisa de pelo menos 10 caracteres.")
        owner_id = create_owner(args.email, password)
        print(f"Proprietário criado. Adicione ao .env:\nOWNER_SUBJECT={owner_id}")


if __name__ == "__main__":
    main()
