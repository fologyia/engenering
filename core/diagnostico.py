"""Ocorrências internas — falhas inesperadas e valores que não passam na conferência interna.

Quem usa o programa não vê nada técnico: uma falha numa página ou numa seção vira uma
:class:`Ocorrencia` com uma **referência curta e estável** (o mesmo defeito dá sempre a mesma
referência), gravada com o traceback em ``diagnostico/ocorrencias.jsonl``, ao lado do banco de
projetos. A tela mostra só um aviso discreto no fim da página com a referência
(``components/robustez.py``); quem mantém o programa lê o arquivo.

Com ``MECANICA_TOOLKIT_ERROS=levantar`` (os testes ligam), a falha sobe em vez de ser contida:
um teste não pode passar escondendo um erro.

Gravar a ocorrência nunca pode derrubar o programa: qualquer falha de disco é engolida aqui.

Sem Streamlit.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import traceback
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VARIAVEL_MODO = "MECANICA_TOOLKIT_ERROS"
MODOS_LEVANTAR = frozenset({"levantar", "1", "sim", "true"})
NOME_PASTA = "diagnostico"
NOME_ARQUIVO = "ocorrencias.jsonl"
TAMANHO_MAXIMO = 1_000_000  # bytes; acima disso o arquivo gira (guardam-se 3)
COPIAS = 3
TIPO_FALHA = "falha"
TIPO_CONFERENCIA = "conferência"
RAIZ = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Ocorrencia:
    referencia: str
    tipo: str  # TIPO_FALHA ou TIPO_CONFERENCIA
    origem: str  # "Página › seção"
    resumo: str  # tipo da exceção e mensagem, ou o que a conferência achou
    detalhe: str = ""  # traceback
    momento: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


def levantar_erros() -> bool:
    """A falha sobe (testes, desenvolvimento) em vez de virar um aviso discreto."""
    return os.environ.get(VARIAVEL_MODO, "").strip().lower() in MODOS_LEVANTAR


def _quadro_do_programa(erro: BaseException) -> traceback.FrameSummary | None:
    """O quadro mais interno do código do programa (fora das bibliotecas)."""
    quadros = traceback.extract_tb(erro.__traceback__)
    do_programa = [
        q
        for q in quadros
        if _dentro_do_programa(q.filename) and "site-packages" not in q.filename.replace("\\", "/")
    ]
    if do_programa:
        return do_programa[-1]
    return quadros[-1] if quadros else None


def _dentro_do_programa(caminho: str) -> bool:
    try:
        Path(caminho).resolve().relative_to(RAIZ)
    except (ValueError, OSError):
        return False
    return True


def _relativo(caminho: str) -> str:
    try:
        return Path(caminho).resolve().relative_to(RAIZ).as_posix()
    except (ValueError, OSError):
        return Path(caminho).name


def _codigo(chave: str) -> str:
    return hashlib.sha1(chave.encode("utf-8")).hexdigest()[:6].upper()


def referencia_da_falha(erro: BaseException) -> str:
    """Mesmo tipo de exceção no mesmo ponto do código → mesma referência (não muda com a máquina)."""
    quadro = _quadro_do_programa(erro)
    onde = f"{_relativo(quadro.filename)}:{quadro.lineno}" if quadro else "?"
    return _codigo(f"{type(erro).__name__}|{onde}")


def ocorrencia_de_falha(origem: str, erro: BaseException) -> Ocorrencia:
    mensagem = str(erro).strip().splitlines()[0][:300] if str(erro).strip() else ""
    quadro = _quadro_do_programa(erro)
    onde = f" em {_relativo(quadro.filename)}:{quadro.lineno}" if quadro else ""
    return Ocorrencia(
        referencia=referencia_da_falha(erro),
        tipo=TIPO_FALHA,
        origem=origem,
        resumo=f"{type(erro).__name__}{onde}: {mensagem}".rstrip(": "),
        detalhe="".join(traceback.format_exception(type(erro), erro, erro.__traceback__)),
    )


def ocorrencia_de_conferencia(origem: str, resumo: str) -> Ocorrencia:
    return Ocorrencia(
        referencia=_codigo(f"conferência|{origem}|{resumo}"),
        tipo=TIPO_CONFERENCIA,
        origem=origem,
        resumo=resumo,
    )


# ---------------------------------------------------------------------------------------------
# Arquivo
# ---------------------------------------------------------------------------------------------
def pasta() -> Path:
    """Ao lado do banco de projetos (nos testes, o banco temporário de cada teste)."""
    from core import project_store

    return Path(project_store._banco(None)).expanduser().parent / NOME_PASTA


def _girar(arquivo: Path) -> None:
    if not arquivo.exists() or arquivo.stat().st_size < TAMANHO_MAXIMO:
        return
    for n in range(COPIAS - 1, 0, -1):
        antigo = arquivo.with_name(f"{arquivo.name}.{n}")
        if antigo.exists():
            antigo.replace(arquivo.with_name(f"{arquivo.name}.{n + 1}"))
    arquivo.replace(arquivo.with_name(f"{arquivo.name}.1"))
    excedente = arquivo.with_name(f"{arquivo.name}.{COPIAS + 1}")
    if excedente.exists():
        excedente.unlink()


def gravar(ocorrencia: Ocorrencia, *, destino: Path | None = None) -> bool:
    """Acrescenta a ocorrência ao arquivo (uma linha JSON). Nunca levanta: devolve se gravou."""
    try:
        arquivo = (destino or pasta()) / NOME_ARQUIVO
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        _girar(arquivo)
        with arquivo.open("a", encoding="utf-8") as saida:
            saida.write(json.dumps(asdict(ocorrencia), ensure_ascii=False) + "\n")
        return True
    except Exception:  # noqa: BLE001 — o diagnóstico nunca derruba o programa
        return False


def ler(*, limite: int = 50, destino: Path | None = None) -> list[dict[str, Any]]:
    """As últimas ocorrências gravadas (mais recentes no fim); linhas ilegíveis são puladas."""
    try:
        arquivo = (destino or pasta()) / NOME_ARQUIVO
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return []
    saida: list[dict[str, Any]] = []
    for linha in linhas[-limite:]:
        try:
            valor = json.loads(linha)
        except ValueError:
            continue
        if isinstance(valor, dict):
            saida.append(valor)
    return saida


# ---------------------------------------------------------------------------------------------
# Conferências de valores
# ---------------------------------------------------------------------------------------------
def numeros_invalidos(valor: Any, caminho: str = "", *, limite: int = 20) -> list[str]:
    """Onde há NaN ou infinito num valor aninhado (dict, lista, tupla, dataclass)."""
    achados: list[str] = []

    def visitar(item: Any, onde: str) -> None:
        if len(achados) >= limite:
            return
        if isinstance(item, bool):
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                achados.append(onde or "valor")
            return
        if isinstance(item, Mapping):
            for chave, sub in item.items():
                visitar(sub, f"{onde}.{chave}" if onde else str(chave))
            return
        if is_dataclass(item) and not isinstance(item, type):
            for campo in fields(item):
                visitar(getattr(item, campo.name), f"{onde}.{campo.name}" if onde else campo.name)
            return
        if isinstance(item, list | tuple):
            for indice, sub in enumerate(item):
                visitar(sub, f"{onde}[{indice}]")

    visitar(valor, caminho)
    return achados


def finito(valor: Any) -> bool:
    try:
        return math.isfinite(float(valor))
    except (TypeError, ValueError):
        return False


def resumo_das_ocorrencias(ocorrencias: Iterable[Ocorrencia]) -> str:
    """Referências sem repetição, na ordem em que apareceram."""
    vistas: dict[str, None] = {}
    for o in ocorrencias:
        vistas.setdefault(o.referencia, None)
    return ", ".join(vistas)
