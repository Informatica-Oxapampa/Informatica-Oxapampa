#!/usr/bin/env python3
"""Genera el perfil institucional a partir de los repositorios de GitHub."""

from __future__ import annotations

import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ACCOUNT = os.getenv("GITHUB_ACCOUNT", "Informatica-Oxapampa")
API_BASE_URL = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
API_VERSION = os.getenv("GITHUB_API_VERSION", "2026-03-10")
TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "README.template.md"
OUTPUT_PATH = ROOT / "README.md"
LANGUAGES_PATH = ROOT / "assets" / "lenguajes.svg"

EXCLUDED_REPOSITORIES = {".github", ".github-private", "Informatica-Oxapampa"}
MAX_RETRIES = 3

# Colores de marca de cada lenguaje, para que la barra sea reconocible de un
# vistazo. Los que no estén aquí usan el verde institucional.
COLOR_LENGUAJE = {
    "C#": "#512BD4",
    "Python": "#3776AB",
    "JavaScript": "#F7DF1E",
    "TypeScript": "#3178C6",
    "HTML": "#E34F26",
    "CSS": "#1572B6",
    "PowerShell": "#5391FE",
    "Shell": "#4EAA25",
    "Java": "#ED8B00",
    "Kotlin": "#7F52FF",
    "PHP": "#777BB4",
    "Go": "#00ADD8",
    "SQL": "#CC2927",
    "Batchfile": "#C1F12E",
    "Dockerfile": "#2496ED",
}
COLOR_INSTITUCIONAL = "#0E7A52"

# Distintivos de estado, en la paleta institucional (verde y plomo sobrio).
ESTADO_ARCHIVADO = (
    '<img src="https://img.shields.io/badge/Archivado-5A6B63?style=flat-square" alt="Archivado">'
)
ESTADO_DERIVADO = (
    '<img src="https://img.shields.io/badge/Derivado-5A6B63?style=flat-square" alt="Repositorio derivado">'
)

def request_json(url: str) -> Any:
    """Consulta GitHub con autenticación opcional y reintentos controlados."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": f"{ACCOUNT}-profile-generator",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    for attempt in range(1, MAX_RETRIES + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            retryable = error.code in {403, 429, 500, 502, 503, 504}
            if not retryable or attempt == MAX_RETRIES:
                detail = error.read().decode("utf-8", errors="replace")[:500]
                raise RuntimeError(
                    f"GitHub respondió HTTP {error.code}: {detail}"
                ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"No se pudo consultar GitHub: {error}") from error

        time.sleep(2 ** (attempt - 1))

    raise RuntimeError("No se pudo completar la consulta a GitHub.")


def fetch_repositories() -> list[dict[str, Any]]:
    """Obtiene todos los repositorios públicos, incluyendo paginación."""
    repositories: list[dict[str, Any]] = []
    page = 1

    while True:
        query = urllib.parse.urlencode(
            {
                "type": "owner",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            }
        )
        account = urllib.parse.quote(ACCOUNT, safe="")
        batch = request_json(f"{API_BASE_URL}/users/{account}/repos?{query}")
        if not isinstance(batch, list):
            raise RuntimeError("La API de GitHub devolvió un formato inesperado.")
        repositories.extend(batch)

        if len(batch) < 100:
            break
        page += 1

    return [
        repository
        for repository in repositories
        if repository.get("name") not in EXCLUDED_REPOSITORIES
    ]


def safe_text(value: Any, fallback: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return html.escape(text or fallback, quote=True)


def format_date(value: Any) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "Sin fecha"


def repository_card(repository: dict[str, Any]) -> str:
    """Tarjeta de un repositorio, con la marca institucional y sus metadatos."""
    name = safe_text(repository.get("name"), "Repositorio")
    display_name = name.replace("-", " ").replace("_", " ")
    description = safe_text(
        repository.get("description"),
        "Proyecto tecnológico institucional de la Municipalidad Provincial de Oxapampa.",
    )
    url = safe_text(repository.get("html_url"), "#")
    raw_language = repository.get("language")
    language = safe_text(raw_language) if raw_language else ""
    updated = format_date(repository.get("updated_at"))
    topics = [safe_text(topic) for topic in repository.get("topics", [])[:4]]
    topics_html = " ".join(f"<code>{topic}</code>" for topic in topics)
    topics_line = f"<p>{topics_html}</p>" if topics_html else ""

    estados = []
    if repository.get("archived"):
        estados.append(ESTADO_ARCHIVADO)
    if repository.get("fork"):
        estados.append(ESTADO_DERIVADO)
    estados_html = " ".join(estados)
    if estados_html:
        estados_html += " "

    metadata = []
    if language:
        metadata.append(f"<strong>{language}</strong>")
    metadata.append(f"Actualizado el {updated}")
    stars = int(repository.get("stargazers_count") or 0)
    forks = int(repository.get("forks_count") or 0)
    if stars:
        metadata.append(f"{stars} estrellas")
    if forks:
        metadata.append(f"{forks} bifurcaciones")

    lines = [
        "<table>",
        "  <tr>",
        '    <td width="80" align="center" valign="middle">',
        '      <img src="./assets/icono-repositorio.svg" width="46" alt="Repositorio institucional">',
        "    </td>",
        '    <td valign="top">',
        f'      <h3><a href="{url}">{display_name}</a></h3>',
        f"      <p>{description}</p>",
        f"      <p><sub>{estados_html}{' · '.join(metadata)}</sub></p>",
    ]
    if topics_line:
        lines.append(f"      {topics_line}")
    lines.extend(["    </td>", "  </tr>", "</table>"])
    return "\n".join(lines)


def cards_table(repositories: list[dict[str, Any]]) -> str:
    if not repositories:
        return ""
    return "\n\n".join(repository_card(repository) for repository in repositories)


def fetch_languages(repositories: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """Suma los bytes de cada lenguaje en todos los repositorios publicados.

    Se consulta el desglose real de cada repositorio, no solo su lenguaje
    principal: un proyecto en C# con scripts de PowerShell aporta a los dos.
    Se excluyen los archivados y los derivados, que no reflejan trabajo actual
    de la oficina.
    """
    totales: dict[str, int] = {}

    for repository in repositories:
        if repository.get("archived") or repository.get("fork"):
            continue

        nombre = repository.get("full_name") or f"{ACCOUNT}/{repository.get('name')}"
        try:
            desglose = request_json(f"{API_BASE_URL}/repos/{nombre}/languages")
        except RuntimeError as error:
            # Un repositorio que no responde no debe tumbar la generación
            # completa del perfil.
            print(f"Aviso: no se pudo leer los lenguajes de {nombre}: {error}")
            continue

        if not isinstance(desglose, dict):
            continue

        for lenguaje, bytes_ in desglose.items():
            try:
                totales[str(lenguaje)] = totales.get(str(lenguaje), 0) + int(bytes_)
            except (TypeError, ValueError):
                continue

    total = sum(totales.values())
    if not total:
        return []

    ordenados = sorted(totales.items(), key=lambda par: par[1], reverse=True)
    return [(nombre, valor * 100 / total) for nombre, valor in ordenados[:6]]


def generate_languages_svg(distribucion: list[tuple[str, float]]) -> bool:
    """Dibuja la distribución de lenguajes con la identidad institucional.

    Devuelve False si no hay nada que dibujar, para que la plantilla omita la
    imagen en lugar de mostrar un recuadro vacío.
    """
    if not distribucion:
        LANGUAGES_PATH.unlink(missing_ok=True)
        return False

    fuente = "Segoe UI,Helvetica Neue,Arial,sans-serif"
    ancho = 1280
    margen = 48
    ancho_barra = ancho - margen * 2 - 300
    alto = 92 + len(distribucion) * 46

    filas = []
    for indice, (lenguaje, porcentaje) in enumerate(distribucion):
        y = 92 + indice * 46
        color = COLOR_LENGUAJE.get(lenguaje, COLOR_INSTITUCIONAL)
        relleno = max(ancho_barra * porcentaje / 100, 6)
        filas.append(
            f"""<g transform="translate({margen} {y})">
    <text x="0" y="4" fill="#E4F0EA" font-family="{fuente}" font-size="15">{html.escape(lenguaje)}</text>
    <rect x="200" y="-9" width="{ancho_barra}" height="10" rx="5" fill="#FFFFFF" fill-opacity="0.10"/>
    <rect x="200" y="-9" width="{relleno:.1f}" height="10" rx="5" fill="{color}"/>
    <text x="{200 + ancho_barra + 16}" y="4" fill="#9FC4B4" font-family="{fuente}" font-size="14">{porcentaje:.1f}%</text>
  </g>"""
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" viewBox="0 0 {ancho} {alto}" role="img" aria-labelledby="titulo descripcion">
  <title id="titulo">Distribución de lenguajes</title>
  <desc id="descripcion">Proporción de cada lenguaje en el código publicado por la oficina.</desc>
  <rect width="{ancho}" height="{alto}" rx="12" fill="#0A2A20"/>
  <rect x="48" y="36" width="28" height="2" fill="#C9A227"/>
  <text x="48" y="62" fill="#FFFFFF" font-family="{fuente}" font-size="16" font-weight="600" letter-spacing="0.4">Distribución en el código publicado</text>
  {"".join(filas)}
</svg>
"""
    LANGUAGES_PATH.write_text(svg, encoding="utf-8", newline="\n")
    return True


def parse_github_date(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def generated_section(repositories: list[dict[str, Any]]) -> str:
    active = [repo for repo in repositories if not repo.get("archived") and not repo.get("fork")]
    derived = [repo for repo in repositories if not repo.get("archived") and repo.get("fork")]
    archived = [repo for repo in repositories if repo.get("archived")]

    now = datetime.now(timezone.utc)
    months = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    synchronization = f"{months[now.month - 1]} de {now.year}"
    parts = [
        '<div align="center">',
        f"  <sub>Revisión del catálogo · {synchronization}</sub>",
        "</div>",
        "",
    ]

    if active:
        parts.extend(["### En desarrollo y uso institucional", "", cards_table(active), ""])
    if derived:
        parts.extend(
            [
                "<details>",
                f"<summary><strong>Repositorios derivados ({len(derived)})</strong></summary>",
                "",
                cards_table(derived),
                "",
                "</details>",
                "",
            ]
        )
    if archived:
        parts.extend(
            [
                "<details>",
                f"<summary><strong>Archivo histórico ({len(archived)})</strong></summary>",
                "",
                cards_table(archived),
                "",
                "</details>",
                "",
            ]
        )
    if not repositories:
        parts.extend(
            [
                '<div align="center">',
                '  <img src="./assets/icono-repositorio.svg" width="72" alt="Catálogo de repositorios">',
                "  <p><strong>Aún no existen repositorios públicos para mostrar.</strong></p>",
                "</div>",
                "",
            ]
        )

    return "\n".join(parts).rstrip()


def main() -> int:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    marker = "{{REPOSITORIES_SECTION}}"
    if template.count(marker) != 1:
        raise RuntimeError("La plantilla debe contener exactamente un marcador de repositorios.")

    repositories = fetch_repositories()

    distribucion = fetch_languages(repositories)
    hay_grafico = generate_languages_svg(distribucion)
    bloque_lenguajes = (
        '<div align="center">\n'
        '  <img src="./assets/lenguajes.svg" width="100%" alt="Distribución de lenguajes en el código publicado">\n'
        "</div>"
        if hay_grafico
        else ""
    )

    output = template.replace(marker, generated_section(repositories))
    output = output.replace("{{LANGUAGES_CHART}}", bloque_lenguajes)
    OUTPUT_PATH.write_text(output.rstrip() + "\n", encoding="utf-8", newline="\n")
    print(
        f"Perfil generado con {len(repositories)} repositorios públicos "
        f"y {len(distribucion)} lenguajes detectados."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
