"""Pilares do modelo: todos os pilares do SolidWorks verificados com os travamentos do esqueleto.

O esqueleto da macro (:mod:`core.leitura_do_modelo`) diz onde cada barra encosta no pilar. Cada
barra que chega trava o pilar na direção dela (:data:`core.travamentos.COS_TRAVA`): a viga que
chega na direção da alma trava **L_x** (impede o pilar de andar na direção da alma, a flexão em
torno de x), e a que chega na direção da mesa trava **L_y**. Com a orientação da seção (macro v5
ou mais nova) cada travamento vai ao seu eixo. Sem ela, o programa não sabe qual direção é a da
alma: testa as duas posições e fica com a pior.

As alturas viram a mesma tabela de travamentos da página Flambagem de colunas
(:mod:`core.travamentos_da_coluna`), e cada trecho recebe o K da Tabela E.1 pelas suas pontas:

* **Base:** no apoio do modelo, rotulada ou engastada, como o usuário escolher (o arquivo do
  SolidWorks não diz como o pé é preso). Fora do apoio (um poste sobre uma viga), é um nó: pino.
* **Topo:** com outra barra encostada, é um nó da estrutura: pino. Sem nada, é ponta livre, e o
  trecho de cima sai da flambagem da coluna inteira, contínua. Um resto de esqueleto de até
  0,40 m acima do último travamento não é balanço (a peça vai até a face, o corte tem folga).
* Os nós contam como travados de lado. O deslocamento da estrutura inteira entra pelo **B₂** do
  tipo Pilar (página Esforços do modelo), como no método da amplificação dos esforços da NBR 8800.

A verificação é a mesma das barras do modelo (:mod:`core.verificacao_barras`): esforços de cálculo
de todas as combinações ELU em todos os pontos do pilar, com o K·L do trecho que governa em cada
eixo, o B₁ no maior trecho e o L_b entre os travamentos de L_y.

Sem Streamlit.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from core import column_buckling as cbk
from core import desenho_da_coluna as dc
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import section_catalog as sc
from core import travamentos as tv
from core import travamentos_da_coluna as tc
from core import verificacao_barras as vb
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "colunas_do_modelo"
MODULO_TITULO = "Pilares do modelo"
STATUS_PENDENTE = vb.STATUS_PENDENTE
BASE_ROTULADA = "Rotulada (pino)"
BASE_ENGASTADA = "Engastada"
BASES = (BASE_ROTULADA, BASE_ENGASTADA)
NOME_DA_PONTA = {
    tc.PINO: "rotulada (pino)",
    tc.ENGASTE: "engastada",
    tc.LIVRE: "livre",
    tc.GUIADO: "engaste que anda",
}
POSICAO_1 = "alma na direção 1"
POSICAO_2 = "alma na direção 2"

Vetor = tuple[float, float, float]


# ---------------------------------------------------------------------------------------------
# O pilar no esqueleto
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PilarNoModelo:
    """O pilar lido do esqueleto: o tamanho, os travamentos e as pontas de cada eixo."""

    corpo: str
    comprimento_mm: float
    travamentos: tuple[tc.Travamento, ...]
    base: str  # tc.PINO, tc.ENGASTE ou tc.LIVRE
    topo_x: str
    topo_y: str
    orientada: bool  # a direção da alma veio da macro
    notas: tuple[str, ...] = ()

    def alturas(self, eixo: str) -> tuple[float, ...]:
        em_x, em_y, _ = tc.organizar(self.travamentos, self.comprimento_mm)
        return em_x if eixo == "x" else em_y


def _unitario(v: Sequence[float]) -> Vetor | None:
    norma = math.sqrt(sum(c * c for c in v))
    if norma < 1e-12:
        return None
    return (v[0] / norma, v[1] / norma, v[2] / norma)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> Vetor:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _m(valor_mm: float) -> str:
    return f"{valor_mm / 1000:.2f}".replace(".", ",")


def e_pilar(corpo: ld.CorpoDoModelo, eixo_vertical: str) -> bool:
    u = _unitario(corpo.vetor)
    return u is not None and abs(_dot(u, tv.vertical(eixo_vertical))) >= ld.VERTICAL_MINIMO


def direcoes_da_secao(corpo: ld.CorpoDoModelo, eixo_vertical: str) -> tuple[Vetor, Vetor, bool]:
    """A direção da alma e a da mesa, em planta, e se a da alma veio da macro.

    Sem a orientação da seção, devolve os dois eixos horizontais do modelo (a alma no primeiro):
    quem chama testa também a posição trocada.
    """
    u = _unitario(corpo.vetor) or tv.vertical(eixo_vertical)
    if corpo.direcao_secao is not None:
        projetada = tuple(
            a - _dot(corpo.direcao_secao, u) * b
            for a, b in zip(corpo.direcao_secao, u, strict=True)
        )
        alma = _unitario(projetada)
        if alma is not None:
            mesa = _unitario(_cross(u, alma)) or (0.0, 0.0, 1.0)
            return alma, mesa, True
    horizontais = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0) if eixo_vertical == "Y" else (0.0, 1.0, 0.0))
    return horizontais[0], horizontais[1], False


def ler_pilar(
    g: ld.GeometriaDoModelo,
    corpo: ld.CorpoDoModelo,
    eixo_vertical: str,
    base_no_apoio: str,
    *,
    trocar_direcoes: bool = False,
) -> PilarNoModelo:
    """Os travamentos do pilar pelas barras que encostam nele, com a altura medida da base.

    ``base_no_apoio`` é :data:`core.travamentos_da_coluna.PINO` ou ``ENGASTE``: como o pé preso
    ao apoio do modelo trabalha. ``trocar_direcoes`` põe a alma na outra direção horizontal (só
    faz diferença sem a orientação da seção).
    """
    comprimento_m = corpo.comprimento_m
    comprimento = comprimento_m * 1000.0
    i = 1 if eixo_vertical == "Y" else 2
    inicio_embaixo = corpo.inicio[i] <= corpo.fim[i]
    alma, mesa, orientada = direcoes_da_secao(corpo, eixo_vertical)
    if trocar_direcoes:
        alma, mesa = mesa, alma
    perto = max(tv.PONTA_RELATIVA * comprimento_m, tv.TOLERANCIA_NO_M)
    na_base = na_topo = False
    pontos: list[tuple[float, bool, bool, str]] = []
    for lig in tv.ligacoes(g, corpo):
        altura_m = lig.posicao_m if inicio_embaixo else comprimento_m - lig.posicao_m
        if altura_m <= perto + 1e-9:
            na_base = True
            continue
        if altura_m >= comprimento_m - perto - 1e-9:
            na_topo = True
            continue
        trava_x = abs(_dot(lig.direcao, alma)) >= tv.COS_TRAVA
        trava_y = abs(_dot(lig.direcao, mesa)) >= tv.COS_TRAVA
        if trava_x or trava_y:
            pontos.append((altura_m * 1000.0, trava_x, trava_y, lig.corpo))
    travamentos = _juntar(pontos)
    ponto_da_base = corpo.inicio if inicio_embaixo else corpo.fim
    notas: list[str] = []
    if tv._no_apoio(g, ponto_da_base, eixo_vertical):
        base = base_no_apoio
    elif na_base:
        base = tc.PINO
        notas.append("o pé não está no apoio do modelo: ele encosta em outra barra (um nó, pino)")
    else:
        base = tc.LIVRE
        notas.append("o pé não está no apoio e não encosta em nada")
    topos = {}
    for eixo in ("x", "y"):
        if na_topo:
            topos[eixo] = tc.PINO
            continue
        alturas = [t.altura_mm for t in travamentos if (t.trava_x if eixo == "x" else t.trava_y)]
        sobra = comprimento - max(alturas, default=-math.inf)
        if sobra <= tv.BALANCO_DESPREZAVEL_M * 1000.0:
            topos[eixo] = tc.PINO
            notas.append(
                f"em {eixo}, o esqueleto passa {_m(sobra)} m do último travamento: resto da peça, "
                "não é balanço"
            )
        else:
            topos[eixo] = tc.LIVRE
    if not na_topo and tc.LIVRE in topos.values():
        notas.append("o topo não encosta em nada: ponta livre, e o trecho de cima é um balanço")
    return PilarNoModelo(
        corpo.nome,
        comprimento,
        travamentos,
        base,
        topos["x"],
        topos["y"],
        orientada,
        tuple(notas),
    )


def _juntar(pontos: Sequence[tuple[float, bool, bool, str]]) -> tuple[tc.Travamento, ...]:
    """Barras que chegam a menos de 0,10 m uma da outra são o mesmo nó do pilar."""
    grupos: list[list[tuple[float, bool, bool, str]]] = []
    for ponto in sorted(pontos):
        if grupos and ponto[0] - grupos[-1][-1][0] <= tv.TOLERANCIA_NO_M * 1000.0:
            grupos[-1].append(ponto)
        else:
            grupos.append([ponto])
    travamentos = []
    for grupo in grupos:
        nomes = list(dict.fromkeys(p[3] for p in grupo))
        travamentos.append(
            tc.Travamento(
                round(sum(p[0] for p in grupo) / len(grupo), 1),
                any(p[1] for p in grupo),
                any(p[2] for p in grupo),
                ", ".join(nomes),
            )
        )
    return tuple(travamentos)


def trechos_do_pilar(
    pilar: PilarNoModelo, recomendado: bool = True
) -> tuple[tc.EixoTravado, tc.EixoTravado]:
    """Os trechos de L_x e de L_y, com o K da Tabela E.1 pelas pontas de cada trecho."""
    return (
        tc.trechos_pelas_pontas(
            "x", pilar.comprimento_mm, pilar.alturas("x"), pilar.base, pilar.topo_x, recomendado
        ),
        tc.trechos_pelas_pontas(
            "y", pilar.comprimento_mm, pilar.alturas("y"), pilar.base, pilar.topo_y, recomendado
        ),
    )


# ---------------------------------------------------------------------------------------------
# A verificação de todos os pilares
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ColunaVerificada:
    barra: str
    perfil: str
    status: str  # "OK", "ALERTA", "NÃO OK" ou "PENDENTE"
    pilar: PilarNoModelo | None = None
    eixo_x: tc.EixoTravado | None = None
    eixo_y: tc.EixoTravado | None = None
    resultado: vb.ResultadoDaBarra | None = None
    motivo: str = ""  # por que ficou pendente
    posicao: str = ""  # sem a orientação da seção: a posição da alma que governou
    b2: float = 1.0
    base_escolhida: str = BASE_ROTULADA

    @property
    def aproveitamento(self) -> float | None:
        return self.resultado.aproveitamento if self.resultado is not None else None


def _pendente(barra: str, perfil: str, motivo: str, **outros: Any) -> ColunaVerificada:
    return ColunaVerificada(barra, perfil, STATUS_PENDENTE, motivo=motivo, **outros)


def coluna_em_pe(c: ColunaVerificada) -> dc.ColunaEmPe | None:
    """O pilar em pé para o desenho (página e memorial): o perfil do catálogo, o trecho que
    governa em cada eixo e os travamentos do esqueleto. ``None`` quando não há desenho: sem os
    eixos, perfil fora do catálogo ou pontas que não estão na Tabela E.1 (base rotulada com o
    topo livre)."""
    pilar = c.pilar
    if pilar is None or c.eixo_x is None or c.eixo_y is None:
        return None
    nomes_dos_apoios = {pontas: nome for nome, pontas in dc.APOIOS_NAS_PONTAS.items()}
    apoio_x = nomes_dos_apoios.get((pilar.base, pilar.topo_x), "")
    apoio_y = nomes_dos_apoios.get((pilar.base, pilar.topo_y), "")
    if not apoio_x or not apoio_y:
        return None
    try:
        secao = cbk.secao_de_perfil(sc.obter_perfil(c.perfil))
    except KeyError:
        return None
    return dc.ColunaEmPe(
        secao,
        pilar.comprimento_mm,
        c.eixo_x.governa.comprimento_mm,
        c.eixo_y.governa.comprimento_mm,
        c.eixo_x.governa.k,
        c.eixo_y.governa.k,
        apoio_x,
        apoio_y,
        travas_x_mm=c.eixo_x.alturas_mm,
        travas_y_mm=c.eixo_y.alturas_mm,
    )


def pilares_do_modelo(
    dados: em.EsforcosDoModelo, leituras: Sequence[ld.LeituraDaBarra]
) -> list[ld.LeituraDaBarra]:
    """As barras que são pilar: pelo tipo da tabela das barras ou, sem ele, pelo esqueleto."""
    pilares = []
    for leitura in leituras:
        cfg = dados.membros.get(leitura.barra, em.ConfiguracaoDoMembro())
        tipo = cfg.tipo if cfg.tipo != "—" else leitura.tipo_sugerido
        if tipo == ld.TIPO_PILAR:
            pilares.append(leitura)
    return pilares


def _verificar(
    barra: str,
    cfg: em.ConfiguracaoDoMembro,
    pilar: PilarNoModelo,
    combinados: Sequence[em.Combinado],
    parametros: em.ParametrosDoTipo,
    norma: str,
    recomendado: bool,
) -> tuple[tc.EixoTravado, tc.EixoTravado, vb.ResultadoDaBarra]:
    eixo_x, eixo_y = trechos_do_pilar(pilar, recomendado)
    continua = tuple(e.eixo for e in (eixo_x, eixo_y) if e.governa.pela_coluna_inteira)
    resultado = vb.verificar_com_comprimentos(
        barra,
        cfg,
        combinados,
        b2=parametros.b2,
        aco=cfg.aco or parametros.aco,
        norma=norma,
        cb=parametros.cb,
        lx_mm=eixo_x.governa.kl_mm,
        ly_mm=eixo_y.governa.kl_mm,
        lb_mm=eixo_y.maior_trecho_mm,
        extras={
            "Lx_B1_mm": eixo_x.maior_trecho_mm,
            "Ly_B1_mm": eixo_y.maior_trecho_mm,
            "k_pela_coluna_continua": continua,
        },
    )
    return eixo_x, eixo_y, resultado


def verificar_colunas(
    dados: em.EsforcosDoModelo,
    geometria: ld.GeometriaDoModelo,
    plano: pc.PlanoDeCargas,
    estados: Sequence[str],
    *,
    base: str = BASE_ROTULADA,
    recomendado: bool = True,
    leituras: Sequence[ld.LeituraDaBarra] | None = None,
) -> tuple[list[ColunaVerificada], list[str]]:
    """Todos os pilares do modelo, cada um com os travamentos do esqueleto."""
    if leituras is None:
        leituras = ld.ler_barras(dados, geometria, plano)
    preparo = em.preparar_combinacoes(dados, plano, vb.estados_ultimos(estados))
    if preparo is None:
        return [], ["Nenhum caso do plano de cargas foi importado."]
    catalogo = set(em._catalogo())
    ponta_da_base = tc.ENGASTE if base == BASE_ENGASTADA else tc.PINO
    resultados: list[ColunaVerificada] = []
    avisos: list[str] = []
    for leitura in pilares_do_modelo(dados, leituras):
        barra = leitura.barra
        cfg = dados.membros.get(barra, em.ConfiguracaoDoMembro())
        perfil = cfg.perfil or (
            leitura.perfil_sugerido if leitura.perfil_sugerido in catalogo else ""
        )
        cfg = replace(cfg, perfil=perfil, tipo=ld.TIPO_PILAR)
        parametros = dados.parametros_do_tipo(ld.TIPO_PILAR)
        comum: dict[str, Any] = {"b2": parametros.b2, "base_escolhida": base}
        if not perfil:
            resultados.append(
                _pendente(barra, "", "escolha o perfil na tabela das barras", **comum)
            )
            continue
        if leitura.corpo is None:
            resultados.append(
                _pendente(
                    barra,
                    perfil,
                    "o pilar não está no esqueleto do modelo: envie o esqueleto da macro em "
                    "Esforços do modelo",
                    **comum,
                )
            )
            continue
        if not e_pilar(leitura.corpo, dados.eixo_vertical):
            resultados.append(
                _pendente(
                    barra,
                    perfil,
                    "no esqueleto a barra não está em pé: os travamentos por altura valem só "
                    "para pilar (confira o tipo na tabela das barras)",
                    **comum,
                )
            )
            continue
        combinados, _, aviso = em.combinados_do_membro(barra, preparo)
        if aviso:
            avisos.append(aviso)
        posicoes = [False] if leitura.corpo.direcao_secao is not None else [False, True]
        melhor: ColunaVerificada | None = None
        erro = ""
        for trocar in posicoes:
            pilar = ler_pilar(
                geometria, leitura.corpo, dados.eixo_vertical, ponta_da_base, trocar_direcoes=trocar
            )
            try:
                eixo_x, eixo_y, resultado = _verificar(
                    barra, cfg, pilar, combinados, parametros, dados.norma, recomendado
                )
            except (KeyError, ValueError) as falha:
                erro = str(falha)
                continue
            candidata = ColunaVerificada(
                barra,
                perfil,
                resultado.status,
                pilar,
                eixo_x,
                eixo_y,
                resultado,
                posicao="" if pilar.orientada else (POSICAO_2 if trocar else POSICAO_1),
                **comum,
            )
            if melhor is None or (candidata.aproveitamento or 0.0) > (melhor.aproveitamento or 0.0):
                melhor = candidata
        if melhor is None:
            pilar = ler_pilar(geometria, leitura.corpo, dados.eixo_vertical, ponta_da_base)
            motivo = erro or "não foi possível verificar"
            if pilar.base == tc.PINO and tc.LIVRE in (pilar.topo_x, pilar.topo_y):
                motivo += (
                    " Com a base rotulada e o topo solto, só um travamento no meio segura o pilar: "
                    "escolha a base engastada, se o pé for mesmo engastado, ou confira se falta "
                    "a junta no topo."
                )
            resultados.append(_pendente(barra, perfil, motivo, pilar=pilar, **comum))
            continue
        resultados.append(melhor)
    return resultados, avisos


# ---------------------------------------------------------------------------------------------
# Tabela, CSV e registro
# ---------------------------------------------------------------------------------------------
COLUNAS = (
    "Pilar",
    "Perfil",
    "L (m)",
    "Travado em L_x (m)",
    "Travado em L_y (m)",
    "K·L_x (m)",
    "K·L_y (m)",
    "L_b (m)",
    "Aproveitamento",
    "Situação",
    "O que governa",
)


def _pct(valor: float | None) -> str:
    if valor is None:
        return "—"
    return "∞" if math.isinf(valor) else f"{100 * valor:.1f} %".replace(".", ",")


def _alturas(alturas: Sequence[float]) -> str:
    return "; ".join(_m(a) for a in alturas) or "—"


def linhas_da_tabela(colunas: Sequence[ColunaVerificada]) -> list[list[object]]:
    linhas: list[list[object]] = []
    for c in colunas:
        pilar = c.pilar
        r = c.resultado
        linhas.append(
            [
                c.barra,
                c.perfil or "—",
                _m(pilar.comprimento_mm) if pilar else "—",
                _alturas(pilar.alturas("x")) if pilar else "—",
                _alturas(pilar.alturas("y")) if pilar else "—",
                _m(c.eixo_x.governa.kl_mm) if c.eixo_x else "—",
                _m(c.eixo_y.governa.kl_mm) if c.eixo_y else "—",
                _m(c.eixo_y.maior_trecho_mm) if c.eixo_y else "—",
                _pct(c.aproveitamento),
                "pendente" if c.status == STATUS_PENDENTE else c.status,
                (r.governante if r is not None else c.motivo) or "—",
            ]
        )
    return linhas


def csv_das_colunas(colunas: Sequence[ColunaVerificada]) -> bytes:
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(COLUNAS)
    escritor.writerows(linhas_da_tabela(colunas))
    return saida.getvalue().encode("utf-8-sig")


def resumo(colunas: Sequence[ColunaVerificada]) -> dict[str, Any]:
    verificadas = [c for c in colunas if c.status != STATUS_PENDENTE]
    pior = max(verificadas, key=lambda c: c.aproveitamento or 0.0, default=None)
    return {
        "total": len(colunas),
        "atendem": sum(1 for c in verificadas if c.status in ("OK", "ALERTA")),
        "nao_atendem": sum(1 for c in verificadas if c.status == "NÃO OK"),
        "pendentes": len(colunas) - len(verificadas),
        "pior": pior,
    }


def _linha_do_registro(c: ColunaVerificada) -> Verificacao:
    if c.status == STATUS_PENDENTE or c.resultado is None:
        return Verificacao(
            f"Pilar {c.barra}", None, None, "—", "—", f"pendente: {c.motivo}", tipo="informativo"
        )
    r = c.resultado
    trechos = (
        f"L_x: {tc.texto_dos_trechos(c.eixo_x)}. L_y: {tc.texto_dos_trechos(c.eixo_y)}."
        if c.eixo_x and c.eixo_y
        else ""
    )
    return Verificacao(
        f"Pilar {c.barra} ({c.perfil})",
        r.aproveitamento,
        1.0,
        "—",
        r.governante or "NBR 8800",
        f"{r.combinacao}, {r.ponto}. {trechos}".strip(),
        status=r.status,
    )


def registro_das_colunas(
    colunas: Sequence[ColunaVerificada],
    dados: em.EsforcosDoModelo,
    estados: Sequence[str],
    *,
    base: str,
    recomendado: bool,
    responsavel: str = "",
) -> dict[str, Any]:
    linhas = [_linha_do_registro(c) for c in colunas]
    sintese = resumo(colunas)
    pior: ColunaVerificada | None = sintese["pior"]
    geral = status_geral([v for v in linhas if v.tipo != "informativo"]) if colunas else "PENDENTE"
    destaque = (
        f"{sintese['total']} pilares do modelo: {sintese['atendem']} atendem, "
        f"{sintese['nao_atendem']} não atendem e {sintese['pendentes']} sem dados para verificar."
        + (
            f" Maior aproveitamento: {_pct(pior.aproveitamento)} em {pior.barra} ({pior.perfil})."
            if pior is not None
            else ""
        )
    )
    tabela = {
        "legenda": "Pilares do modelo — travamentos do esqueleto e o trecho que governa.",
        "cabecalhos": list(COLUNAS[:-1]),
        "linhas": [linha[:-1] for linha in linhas_da_tabela(colunas)],
        "fonte": 7.0,
    }
    # O pilar de maior aproveitamento em pé, com os travamentos: o memorial o desenha de novo.
    em_pe = coluna_em_pe(pior) if pior is not None else None
    figura = None if em_pe is None else dc.coluna_para_o_registro(em_pe, com_secao=False)
    if figura is not None and pior is not None:
        figura["legenda"] = (
            f"Pilar {pior.barra} ({pior.perfil}), o de maior aproveitamento, em pé: os "
            "travamentos lidos do esqueleto e o trecho que governa em cada eixo."
        )
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Pilares do modelo — {len(colunas)} pilares",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas={
            "casos_do_modelo": ", ".join(dados.casos),
            "estados_limites": ", ".join(vb.estados_ultimos(estados)),
            "norma": cbk.NORMAS_ROTULOS.get(dados.norma, dados.norma),
            "base_dos_pilares_no_apoio": base,
            "k_da_tabela_e1": "recomendado" if recomendado else "teórico",
            "b2_dos_pilares": numero_json(dados.parametros_do_tipo(ld.TIPO_PILAR).b2, 3),
            "pilares": len(colunas),
        },
        resultados={
            "status_geral": geral,
            "verificações": linhas_para_registro(linhas),
            "utilizacao_maxima": None
            if pior is None
            else numero_json(pior.aproveitamento or 0.0, 4),
            "destaque_memorial": destaque,
            "tabelas_memorial": [tabela],
            "figura_coluna": figura,
        },
        metodo=(
            "Travamentos de cada pilar lidos do esqueleto do SolidWorks: a barra que encosta no "
            "pilar o trava na direção dela. Em cada eixo, os travamentos dividem o pilar em "
            "trechos, e cada trecho recebe o K da Tabela E.1 da NBR 8800 pelas suas pontas (o "
            "travamento como pino); o trecho de maior K·L governa. Esforços de cálculo de todas as "
            "combinações ELU, ponto a ponto, e a verificação da NBR 8800 (compressão, flexão, B₁ "
            "no maior trecho, L_b entre os travamentos de L_y e interação N + Mx + My)."
        ),
        premissas=[
            "Os nós da estrutura contam como travados de lado; o deslocamento da estrutura entra "
            "pelo B₂ do tipo Pilar, que multiplica todos os esforços.",
            f"Base no apoio do modelo: {base.lower()}.",
            "Travamento suposto rígido e resistente; as barras que travam são verificadas à parte.",
            "Sem a orientação da seção (macro anterior à v5), as duas posições da alma foram "
            "testadas e vale a pior.",
        ],
        referencias=[
            "ABNT NBR 8800 (edições de 2025 e 2008): 4.9.7, 5.3, 5.4, 5.5.1.2 e Anexo E.",
        ],
        conclusao=destaque,
        responsavel=responsavel,
    )
