"""Publica o dashboard interativo em `docs/` (servido pelo GitHub Pages a
partir da raiz do mesmo repositório do código-fonte).

Funciona em dois contextos:
- Local (Task Scheduler): faz commit+push direto daqui.
- GitHub Actions: só grava os arquivos; o próprio workflow (.github/workflows/
  hourly.yml) faz commit+push depois, usando o token automático da Action.
  Detectamos esse caso pela env var GITHUB_ACTIONS e pulamos o git local.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from src.dashboard.data_export import write_data_json

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
APP_TEMPLATE = ROOT / "templates" / "dashboard_app.html"


def publish(dashboard_data: dict) -> bool:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(APP_TEMPLATE, DOCS_DIR / "index.html")
    write_data_json(dashboard_data, DOCS_DIR / "data.json")

    if os.getenv("GITHUB_ACTIONS") == "true":
        print("[publish] Rodando no GitHub Actions — arquivos escritos, commit/push fica com o workflow.")
        return True

    if not (ROOT / ".git").exists():
        print(f"[publish] {ROOT} não é um repo git ainda — pulando publicação no GitHub Pages.")
        return False

    def run(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)

    run(["add", "docs/index.html", "docs/data.json"])
    commit = run(["commit", "-m", "Atualiza dashboard"])
    if commit.returncode != 0 and "nothing to commit" not in commit.stdout:
        print(f"[publish] git commit falhou: {commit.stdout} {commit.stderr}")
        return False
    if "nothing to commit" in commit.stdout:
        print("[publish] Dashboard sem mudanças desde a última publicação.")
        return True

    push = run(["push"])
    if push.returncode != 0:
        print(f"[publish] git push falhou (credencial expirada? rode 'git push' manualmente uma vez): {push.stderr}")
        return False

    print("[publish] Dashboard publicado em https://mvapessanha.github.io/travel-radar-site/")
    return True
