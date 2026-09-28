"""O `uv.lock` instala sem compilar nada nas máquinas que rodam o Viking (Sessão 7, D45).

Medido em 2026-09-28: o cryptography deixou de publicar wheel para Mac Intel na 49.0.0, e o lock
pegou a 50.0.1; no Mac do dono (Intel de 2017, macOS 13, Python 3.13) o `uv sync` teria de compilar
do código-fonte. O `uv` não impede isso sozinho (código-fonte conta como "compatível"), e o
`no-build = true` que impedia no uv 0.12 faz o uv 0.11 do Mac recusar o próprio Viking. Então a
régua é esta: todo pacote do lock tem wheel para cada plataforma que o usa, nos dois Pythons.
"""

import functools
import re
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
# As máquinas: o Mac do dono (Python 3.13.5, medido em 2026-09-28) e o VPS/CI (3.12).
PYTHONS = (12, 13)
MACOS_MAXIMO = 13  # Ventura, sem upgrade (D4)


@functools.cache
def _lock() -> dict:
    return tomllib.loads((RAIZ / "uv.lock").read_text())


def _plataformas_que_usam(lock: dict) -> dict[str, set[str]]:
    """Para cada pacote, em quais das nossas plataformas ele entra, derivado dos marcadores das
    arestas do próprio lock: pacote pedido só com `sys_platform == 'win32'` não entra em nenhuma."""
    arestas: dict[str, list[str]] = {}
    for pacote in lock["package"]:
        grupos = [pacote.get("dependencies", [])]
        grupos += list(pacote.get("optional-dependencies", {}).values())
        for grupo in grupos:
            for dep in grupo:
                arestas.setdefault(dep["name"], []).append(dep.get("marker", ""))
    usos = {}
    for pacote in lock["package"]:
        marcadores = arestas.get(pacote["name"], [""])
        usos[pacote["name"]] = {
            plataforma
            for plataforma, outras in (
                ("darwin", ("win32", "linux")),
                ("linux", ("win32", "darwin")),
            )
            if any(not any(f"sys_platform == '{o}'" in m for o in outras) for m in marcadores)
        }
    return usos


def _serve(wheel: str, plataforma: str, menor: int) -> bool:
    """A wheel instala nesta plataforma, neste Python 3.<menor>? Lê as tags do nome do arquivo."""
    python, abi, sistema = wheel.removesuffix(".whl").split("-")[-3:]
    pythons = python.split(".")
    if "py3" in pythons:
        cabe = True
    elif abi == "abi3":
        cabe = any(re.fullmatch(r"cp3(\d+)", p) and int(p[3:]) <= menor for p in pythons)
    else:
        cabe = f"cp3{menor}" in pythons and abi == f"cp3{menor}"
    if not cabe:
        return False
    if sistema == "any":
        return True
    sistemas = sistema.split(".")
    if plataforma == "linux":
        return any(re.fullmatch(r"manylinux\w*_x86_64", s) for s in sistemas)
    return any(
        (m := re.fullmatch(r"macosx_(\d+)_\d+_(x86_64|universal2|intel)", s))
        and int(m.group(1)) <= MACOS_MAXIMO
        for s in sistemas
    )


def test_serve_le_as_tags_como_o_pip():
    """A régua da régua: cada caso é uma wheel de verdade do lock de 2026-09-28."""
    assert _serve("cryptography-48.0.1-cp311-abi3-macosx_10_9_universal2.whl", "darwin", 13)
    assert not _serve("cryptography-50.0.1-cp311-abi3-macosx_11_0_arm64.whl", "darwin", 13)
    assert not _serve("x-1.0-cp312-cp312-macosx_14_0_x86_64.whl", "darwin", 12)  # macOS 14
    assert not _serve("x-1.0-cp312-cp312-macosx_10_13_x86_64.whl", "darwin", 13)  # outro Python
    assert _serve("x-1.0-py3-none-any.whl", "linux", 12)
    assert _serve("x-1.0-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", "linux", 13)
    assert not _serve("x-1.0-cp313-cp313t-manylinux_2_17_x86_64.whl", "linux", 13)  # sem GIL


def _casos() -> list[tuple[str, str, str, int]]:
    lock = _lock()
    usos = _plataformas_que_usam(lock)
    casos = []
    for pacote in lock["package"]:
        if pacote.get("source", {}).get("editable"):
            continue  # o próprio Viking: instala do checkout
        for plataforma in sorted(usos[pacote["name"]]):
            for menor in PYTHONS:
                casos.append((pacote["name"], pacote["version"], plataforma, menor))
    return casos


def test_o_lock_tem_o_que_conferir():
    """Uma varredura que encolhe tem de reprovar, não emudecer: 103 pacotes em 2026-09-28."""
    casos = _casos()
    assert len({nome for nome, *_ in casos}) >= 90
    assert {plataforma for _, _, plataforma, _ in casos} == {"darwin", "linux"}


@pytest.mark.parametrize(("nome", "versao", "plataforma", "menor"), _casos())
def test_todo_pacote_tem_wheel_para_as_nossas_maquinas(nome, versao, plataforma, menor):
    (pacote,) = [p for p in _lock()["package"] if p["name"] == nome]
    wheels = [w["url"].rsplit("/", 1)[1] for w in pacote.get("wheels", [])]
    assert any(_serve(w, plataforma, menor) for w in wheels), (
        f"{nome} {versao} não tem wheel para {plataforma} com Python 3.{menor}: o `uv sync` "
        "compilaria do código-fonte"
    )
