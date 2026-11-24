"""O que o estudo aplicou em cada caso, pelo CSV do gerenciador de casos de carga, contra as reações
e o plano de cargas.

As reações dizem quanto o modelo recebeu; o plano, quanto deveria receber. Quando os dois não batem,
falta saber **onde** está a diferença: no valor que foi digitado no gerenciador, numa força "Por
item" (o valor entra inteiro em cada barra selecionada) ou no sentido. O CSV que o gerenciador salva
("Salvar os dados em um arquivo .csv externo") tem o valor de cada carga em cada caso; com ele, o
programa explica a diferença caso a caso:

* a reação é a soma dos valores digitados → cada força entrou uma vez;
* a reação é ``n`` vezes um valor (ou ``1 700 + 4 × 360``) → aquela força entrou ``n`` vezes —
  "Por item" em ``n`` barras (visto no PE do modelo es_v2 do usuário, 23/11/2026);
* o valor digitado não é o do plano → a diferença está no gerenciador, não no modelo;
* a reação empurra ao contrário do plano → o sentido (o "Inverter direção" ou o sinal do valor).

O arquivo do gerenciador não diz a direção das forças no espaço (só a componente: "Normal ao plano",
"Ao longo da face dir 1"…), então o sentido vem das reações; o valor vem do arquivo.

Sem Streamlit.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import esforcos_modelo as em
from core import gerenciador_solidworks as gs
from core import plano_de_cargas as pc

CAMPO_DO_PROJETO = "gerenciador_do_estudo"
VEZES_MAXIMAS = 20  # uma força "por item" em até 20 entidades
FORCAS_MAXIMAS = 4  # mais forças que isso num caso: a busca dos múltiplos não é feita
TOLERANCIA = 0.01  # 1 % da reação (o arquivo de reações tem o valor exato do modelo)
TOLERANCIA_DO_PLANO = 0.02
ANGULO_OPOSTO = 170.0
COLUNAS_DA_TABELA = (
    "Caso",
    "No gerenciador",
    "Reação do estudo (kN)",
    "Plano (kN)",
    "O que explica",
)


@dataclass(frozen=True)
class CargaNoCaso:
    """Uma componente com valor num caso do gerenciador."""

    carga: str  # o nome da carga no estudo (W0, PE, Força-1…)
    componente: str  # "Normal ao plano", "Ao longo da face dir 1", "Valor da pressão"…
    valor: float  # como está no caso, na unidade da coluna
    unidade: str
    grandeza: str  # gs.FORCA, gs.PRESSAO, gs.ACELERACAO…
    valor_si: float  # N, Pa, m/s²…

    @property
    def texto(self) -> str:
        return f"{self.carga} {gs._br(self.valor)} {self.unidade}"


@dataclass(frozen=True)
class CasoDoGerenciador:
    nome: str  # como está no gerenciador ("T-")
    codigo: str  # o código do plano ("T−"); vazio se não achou
    cargas: tuple[CargaNoCaso, ...]

    @property
    def forcas(self) -> tuple[CargaNoCaso, ...]:
        return tuple(c for c in self.cargas if c.grandeza == gs.FORCA)

    @property
    def outras(self) -> tuple[CargaNoCaso, ...]:
        """Gravidade, pressão, momento, temperatura: a reação não é só a soma das forças."""
        return tuple(c for c in self.cargas if c.grandeza != gs.FORCA)


def _fator_si(unidade: str) -> float:
    return gs._UNIDADES.get(gs._chave_da_unidade(unidade), (1.0, ""))[0]


def codigo_do_caso(nome: str, codigos: Iterable[str]) -> str:
    """O código do plano do caso do gerenciador: o próprio nome (com "-" → "−") ou o que aparece
    nele."""
    lista = list(codigos)
    for candidato in (nome, nome.replace("-", "−")):
        for codigo in lista:
            if em._normal(candidato) == em._normal(codigo):
                return codigo
    return em.caso_sugerido(nome, lista) or ""


def casos_do_arquivo(
    arquivo: gs.ArquivoDoGerenciador, codigos: Iterable[str]
) -> list[CasoDoGerenciador]:
    """Cada caso primário do arquivo com as componentes que têm valor (sem as suprimidas)."""
    lista = list(codigos)
    saida = []
    for nome, celulas in arquivo.casos:
        cargas = []
        for coluna, celula in zip(arquivo.colunas, celulas, strict=False):
            texto = celula.strip()
            if not texto or em._normal(texto).startswith("suprimir"):
                continue
            valor = em.numero(texto, decimal_virgula=False)
            if valor is None or valor == 0:
                continue
            grandeza = gs.grandeza(coluna.unidade)
            if grandeza == gs.TEMPERATURA:
                continue  # a temperatura não dá reação na soma (o modelo dilata)
            cargas.append(
                CargaNoCaso(
                    coluna.carga,
                    coluna.componente,
                    valor,
                    coluna.unidade,
                    grandeza,
                    valor * _fator_si(coluna.unidade),
                )
            )
        saida.append(CasoDoGerenciador(nome, codigo_do_caso(nome, lista), tuple(cargas)))
    return saida


def vezes_de_cada_forca(forcas_kN: Sequence[float], reacao_kN: float) -> tuple[int, ...] | None:
    """Quantas vezes cada força entrou para dar a reação: ``(1, 4)`` para 1 700 + 4 × 360 = 3 140.

    Procura de 1 a :data:`VEZES_MAXIMAS` vezes cada uma, fica com a menor soma de vezes que bate
    até 1 % da reação. ``None`` se nenhuma combinação bater (ou forças demais para procurar)."""
    if not forcas_kN or len(forcas_kN) > FORCAS_MAXIMAS or reacao_kN <= 0:
        return None
    limite = max(TOLERANCIA * reacao_kN, 0.005)
    melhor: tuple[int, ...] | None = None
    for vezes in itertools.product(range(1, VEZES_MAXIMAS + 1), repeat=len(forcas_kN)):
        soma = sum(n * f for n, f in zip(vezes, forcas_kN, strict=True))
        if abs(soma - reacao_kN) <= limite and (melhor is None or sum(vezes) < sum(melhor)):
            melhor = vezes
    return melhor


@dataclass(frozen=True)
class LinhaDaConferencia:
    caso: str
    no_gerenciador: str
    reacao_kN: float | None
    plano_kN: float | None
    explicacao: str
    nivel: str  # pc.NIVEL_OK, pc.NIVEL_ATENCAO

    def como_linha(self) -> dict[str, Any]:
        return {
            "Caso": self.caso,
            "No gerenciador": self.no_gerenciador,
            "Reação do estudo (kN)": self.reacao_kN,
            "Plano (kN)": self.plano_kN,
            "O que explica": self.explicacao,
        }


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _explicar(
    caso: CasoDoGerenciador,
    reacao: tuple[float, float, float] | None,
    esperado: tuple[float, float, float] | None,
) -> tuple[str, str]:
    """(texto, nível) de um caso."""
    if reacao is None:
        return "Sem o arquivo de reações deste caso: envie o -reacoes.csv.", pc.NIVEL_ATENCAO
    r = math.hypot(*reacao)
    p = math.hypot(*esperado) if esperado is not None else None
    partes: list[str] = []
    nivel = pc.NIVEL_OK
    if esperado is not None and p and r > em.REACAO_NULA_kN:
        produto = -(reacao[0] * esperado[0] + reacao[1] * esperado[1] + reacao[2] * esperado[2])
        cosseno = max(-1.0, min(1.0, produto / (r * p)))
        if math.degrees(math.acos(cosseno)) >= ANGULO_OPOSTO:
            partes.append(
                "o modelo empurra no sentido CONTRÁRIO ao do plano (o “Inverter direção” ou o "
                "sinal do valor)"
            )
            nivel = pc.NIVEL_ATENCAO
    if caso.outras:
        textos = []
        for c in caso.outras:
            if c.grandeza == gs.PRESSAO and c.valor_si:
                textos.append(
                    f"pressão de {gs._br(abs(c.valor))} {c.unidade}: a reação dá "
                    f"{_n(r * 1e3 / abs(c.valor_si), 2)} m² carregados"
                )
            elif c.grandeza == gs.ACELERACAO:
                textos.append(f"gravidade de {gs._br(c.valor)} {c.unidade}")
            else:
                textos.append(c.texto)
        partes.append("; ".join(textos))
        if p is not None and abs(r - p) > TOLERANCIA_DO_PLANO * p:
            partes.append(f"a reação ({_n(r)} kN) não é a do plano ({_n(p)} kN)")
            nivel = pc.NIVEL_ATENCAO
        return _juntar(partes), nivel
    forcas = [abs(c.valor_si) / 1e3 for c in caso.forcas]
    if not forcas:
        return "Nenhuma carga ligada neste caso.", pc.NIVEL_ATENCAO
    digitado = sum(forcas)
    vezes = vezes_de_cada_forca(forcas, r)
    if vezes is None:
        partes.append(
            f"a reação ({_n(r)} kN) não é a soma dos valores digitados ({_n(digitado)} kN) nem "
            "um múltiplo deles: confira as entidades de cada força e se há carga fora do "
            "gerenciador"
        )
        return _juntar(partes), pc.NIVEL_ATENCAO
    repetidas = [(c, n) for c, n in zip(caso.forcas, vezes, strict=True) if n > 1]
    if repetidas:
        partes.append(
            "; ".join(
                f"“{c.carga}” ({gs._br(abs(c.valor))} {c.unidade}) entrou {n} vezes — "
                f"“Por item” em {n} entidades = {_n(n * abs(c.valor_si) / 1e3)} kN"
                for c, n in repetidas
            )
        )
        nivel = pc.NIVEL_ATENCAO
    else:
        partes.append("cada força entrou uma vez: a reação é o valor digitado")
    if p is not None:
        if abs(r - p) <= TOLERANCIA_DO_PLANO * p:
            partes.append("e bate com o plano")
        elif repetidas and abs(digitado - p) <= TOLERANCIA_DO_PLANO * p:
            partes.append(
                f"o valor digitado ({_n(digitado)} kN) é o do plano: era para ser o total — use "
                "“Total” (ou divida o valor pelas entidades)"
            )
        else:
            partes.append(
                f"o valor digitado ({_n(digitado)} kN"
                + (f"; com as repetições, {_n(r)} kN" if repetidas else "")
                + f") não é o do plano ({_n(p)} kN): a diferença está no gerenciador"
            )
            nivel = pc.NIVEL_ATENCAO
    return _juntar(partes), nivel


def _juntar(partes: Sequence[str]) -> str:
    texto = "; ".join(p for p in partes if p)
    return (texto[:1].upper() + texto[1:] + ".") if texto else ""


def conferir(
    arquivo: gs.ArquivoDoGerenciador, dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas
) -> list[LinhaDaConferencia]:
    """Uma linha por caso do gerenciador que o projeto importou (ou que o plano tem)."""
    linhas = []
    for caso in casos_do_arquivo(arquivo, plano.codigos or list(dados.casos)):
        codigo = caso.codigo or caso.nome
        importado = dados.casos.get(codigo)
        reacao = (
            em.para_o_plano(importado.reacoes.modelo, dados.eixo_vertical)
            if importado is not None and importado.reacoes is not None
            else None
        )
        acao = plano.acao(codigo)
        esperado = em.total_esperado(acao) if acao is not None else None
        if importado is None and acao is None:
            continue
        texto, nivel = _explicar(caso, reacao, esperado)
        linhas.append(
            LinhaDaConferencia(
                codigo,
                "; ".join(c.texto for c in caso.cargas) or "—",
                round(math.hypot(*reacao), 3) if reacao is not None else None,
                round(math.hypot(*esperado), 3) if esperado is not None else None,
                texto,
                nivel,
            )
        )
    return linhas


def para_dicionario(arquivo_nome: str, conteudo: bytes) -> dict[str, Any]:
    return {"arquivo": arquivo_nome, "conteudo": em._decodificar(conteudo)}


def do_projeto(projeto: Mapping[str, Any] | None) -> tuple[str, gs.ArquivoDoGerenciador] | None:
    """O CSV do gerenciador gravado no projeto (nome, arquivo lido); ``None`` sem ele."""
    if not isinstance(projeto, Mapping):
        return None
    gravado = projeto.get(CAMPO_DO_PROJETO)
    if not isinstance(gravado, Mapping) or not isinstance(gravado.get("conteudo"), str):
        return None
    try:
        return str(gravado.get("arquivo") or ""), gs.ler(gravado["conteudo"].encode("utf-8"))
    except em.ArquivoInvalido:
        return None
