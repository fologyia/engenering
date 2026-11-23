"""A malha do estudo do SolidWorks Simulation: o centro de cada elemento (macro exportar_casos_de_carga v18).

**Para que serve.** O "Listar forças da viga" escreve cada viga como ``Viga-n(<corpo>)``, com o nome
que o corpo tinha quando a viga foi criada no estudo. Renomear o corpo depois (na árvore, na lista
de corte ou por macro) não muda esse nome, nem rodando o estudo de novo. O esqueleto, gerado pela
macro da lista de corte, traz o nome de agora. Pelo nome, as duas listas não se encontram.

Os números dos elementos, porém, estão no arquivo de forças (coluna "Elemento"), e a malha diz onde
fica cada elemento. Com ela, :func:`core.leitura_do_modelo.correspondencia` liga cada viga ao corpo
do esqueleto pela **posição** dos elementos dela, qualquer que seja o nome.

A macro grava ``<estudo>-malha.csv``::

    sep=;
    14:12; 23/11/2026
    Nome do estudo:Análise estática 1
    Macro: Mecanica Toolkit - exportar_casos_de_carga v18

    Centros dos elementos da malha (como a malha devolve)
    Elemento;X;Y;Z
    709;-0,589399;0,08;0

As coordenadas saem como a malha devolve (o SOLIDWORKS 2026 deu metros com a malha em mm): a escala
(m ou mm) é achada pelo esqueleto, na hora de casar.

O projeto guarda só os elementos das vigas importadas (:func:`so_das_vigas`): a malha das chapas e
dos sólidos não serve para casar e faria o projeto crescer à toa.

Sem Streamlit e sem depender da leitura do modelo (ela importa daqui).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core import esforcos_modelo as em

CAMPO_DO_PROJETO = "malha_do_modelo"
TITULO = "centrosdoselementosdamalha"  # a linha do título, sem acento, espaço nem maiúscula


class MalhaInvalida(ValueError):
    """Arquivo da malha que o programa não lê; a mensagem diz o que fazer."""


@dataclass(frozen=True)
class MalhaDoEstudo:
    """O centro de cada elemento, nas unidades em que a malha devolveu."""

    centros: Mapping[str, tuple[float, float, float]] = field(default_factory=dict)
    arquivo: str = ""
    estudo: str = ""
    importado_em: str = ""

    @property
    def vazia(self) -> bool:
        return not self.centros


def chave_do_elemento(texto: Any) -> str:
    """'709' e ' 709 ' → '709'; '1.072' (milhar) → '1072'. Vazio se não for um número inteiro."""
    limpo = re.sub(r"[\s.]", "", str(texto))
    return limpo if limpo.isdigit() else ""


def e_arquivo_da_malha(conteudo: bytes) -> bool:
    texto = em._normal(em._decodificar(conteudo[:800]))
    return TITULO in texto


def ler_malha(conteudo: bytes, nome_arquivo: str) -> MalhaDoEstudo:
    texto = em._decodificar(conteudo)
    linhas = texto.splitlines()
    estudo = ""
    cabecalho = None
    for i, linha in enumerate(linhas[:30]):
        normal = em._normal(linha)
        if normal.startswith("nomedoestudo:"):
            estudo = linha.split(":", 1)[1].strip()
        if normal.startswith("elemento;"):
            cabecalho = i
            break
    if cabecalho is None:
        raise MalhaInvalida(
            "Não achei a linha das colunas (Elemento;X;Y;Z): gere o arquivo de novo pela macro "
            "dos casos de carga (v18 ou mais nova)."
        )
    centros: dict[str, tuple[float, float, float]] = {}
    for linha in linhas[cabecalho + 1 :]:
        partes = [p.strip() for p in linha.split(";")]
        if len(partes) < 4 or not partes[0]:
            continue
        chave = chave_do_elemento(partes[0])
        valores = [em.numero(p, decimal_virgula=True) for p in partes[1:4]]
        if not chave or any(v is None for v in valores):
            continue
        centros[chave] = (float(valores[0]), float(valores[1]), float(valores[2]))  # type: ignore[arg-type]
    if not centros:
        raise MalhaInvalida(
            f"{nome_arquivo} não tem nenhum elemento com posição: rode o estudo (Executar) e a "
            "macro de novo."
        )
    distintos = {tuple(round(c, 6) for c in p) for p in centros.values()}
    if len(centros) > 1 and len(distintos) == 1:
        raise MalhaInvalida(
            f"{nome_arquivo}: todos os elementos vieram no mesmo ponto — o Simulation não entregou "
            "as posições. Mande o arquivo e o …-diagnostico-da-macro.txt para conferir."
        )
    return MalhaDoEstudo(
        centros=centros,
        arquivo=nome_arquivo,
        estudo=estudo,
        importado_em=datetime.now().isoformat(timespec="seconds"),
    )


def elementos_dos_membros(dados: em.EsforcosDoModelo) -> dict[str, list[str]]:
    """Os elementos de cada viga do Simulation, pelos arquivos de forças importados."""
    elementos: dict[str, dict[str, None]] = {}
    for caso in dados.casos.values():
        for viga, pontos in caso.membros.items():
            alvo = elementos.setdefault(viga, {})
            for p in pontos:
                chave = chave_do_elemento(p.elemento)
                if chave:
                    alvo[chave] = None
    return {viga: list(lista) for viga, lista in elementos.items()}


def so_das_vigas(malha: MalhaDoEstudo, dados: em.EsforcosDoModelo) -> MalhaDoEstudo:
    """Só os elementos que aparecem nas forças das vigas (o que o projeto guarda)."""
    usados = {e for lista in elementos_dos_membros(dados).values() for e in lista}
    return MalhaDoEstudo(
        centros={e: p for e, p in malha.centros.items() if e in usados},
        arquivo=malha.arquivo,
        estudo=malha.estudo,
        importado_em=malha.importado_em,
    )


@dataclass(frozen=True)
class ConferenciaDaMalha:
    """Quantos elementos das vigas a malha tem: com 0, ela é de outro estudo (ou de outra malha)."""

    vigas: int
    vigas_com_posicao: int
    elementos: int
    elementos_achados: int

    @property
    def serve(self) -> bool:
        return self.elementos_achados > 0

    @property
    def completa(self) -> bool:
        return self.elementos > 0 and self.elementos_achados == self.elementos


def conferir(malha: MalhaDoEstudo, dados: em.EsforcosDoModelo) -> ConferenciaDaMalha:
    por_viga = elementos_dos_membros(dados)
    todos = {e for lista in por_viga.values() for e in lista}
    return ConferenciaDaMalha(
        vigas=len(por_viga),
        vigas_com_posicao=sum(
            1 for lista in por_viga.values() if any(e in malha.centros for e in lista)
        ),
        elementos=len(todos),
        elementos_achados=sum(1 for e in todos if e in malha.centros),
    )


def pontos_das_vigas(
    centros: Mapping[str, tuple[float, float, float]], dados: em.EsforcosDoModelo
) -> dict[str, list[tuple[float, float, float]]]:
    """Os centros dos elementos de cada viga (só as que têm algum elemento na malha)."""
    pontos: dict[str, list[tuple[float, float, float]]] = {}
    for viga, lista in elementos_dos_membros(dados).items():
        achados = [centros[e] for e in lista if e in centros]
        if achados:
            pontos[viga] = achados
    return pontos


def para_dicionario(malha: MalhaDoEstudo) -> dict[str, Any]:
    return {
        "arquivo": malha.arquivo,
        "estudo": malha.estudo,
        "importado_em": malha.importado_em,
        "centros": {e: [round(c, 7) for c in p] for e, p in malha.centros.items()},
    }


def de_dicionario(dados: Mapping[str, Any] | None) -> MalhaDoEstudo:
    if not isinstance(dados, Mapping):
        return MalhaDoEstudo()
    centros: dict[str, tuple[float, float, float]] = {}
    brutos = dados.get("centros")
    if isinstance(brutos, Mapping):
        for e, p in brutos.items():
            chave = chave_do_elemento(e)
            if not chave or not isinstance(p, (list, tuple)) or len(p) != 3:
                continue
            try:
                ponto = tuple(float(c) for c in p)
            except (TypeError, ValueError):
                continue
            if all(math.isfinite(c) for c in ponto):
                centros[chave] = ponto  # type: ignore[assignment]
    return MalhaDoEstudo(
        centros=centros,
        arquivo=str(dados.get("arquivo") or ""),
        estudo=str(dados.get("estudo") or ""),
        importado_em=str(dados.get("importado_em") or ""),
    )


def malha_do_projeto(projeto: Mapping[str, Any] | None) -> MalhaDoEstudo:
    if not isinstance(projeto, Mapping):
        return MalhaDoEstudo()
    return de_dicionario(projeto.get(CAMPO_DO_PROJETO))


def juntar(antiga: MalhaDoEstudo, nova: MalhaDoEstudo) -> MalhaDoEstudo:
    """A nova por cima da antiga (o mesmo elemento fica com a posição da nova)."""
    return MalhaDoEstudo(
        centros={**antiga.centros, **nova.centros},
        arquivo=nova.arquivo or antiga.arquivo,
        estudo=nova.estudo or antiga.estudo,
        importado_em=nova.importado_em or antiga.importado_em,
    )
