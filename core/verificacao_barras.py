"""Verificação de todas as barras do modelo com os esforços importados do SolidWorks.

Para cada barra da tabela (perfil, tipo, eixo forte, aço e comprimentos), com os esforços de cálculo
de todas as combinações ELU do plano em todos os pontos da barra (:mod:`core.esforcos_modelo`):

1. **Varredura rápida** — com as resistências da barra (N_c,Rd, N_t,Rd, M_x,Rd e M_y,Rd, calculadas
   uma vez), o índice da interação da NBR 8800 5.5.1.2 em cada combinação e ponto.
2. **Verificação completa** dos pontos mais críticos (os de maior índice na compressão e na tração e
   o de maior compressão) pelo mesmo motor da página Flambagem de colunas
   (:mod:`core.column_buckling`): todos os modos de flambagem, flambagem local, FLT/FLM/FLA, B₁ com
   C_m = 1 (a favor da segurança), interação N + M_x + M_y e o limite de esbeltez do critério Anglo.
   Cantoneiras simples: compressão por 5.3.5.4 (:mod:`core.contraventamento_barras`).
3. **Cortante** (resultante de V₁ e V₂ contra a alma) e **torção** informada.

O estudo estático do SolidWorks é de primeira ordem: os esforços são multiplicados pelo **B₂** do
tipo de barra (todos os esforços, sem separar a parcela de translação — a favor da segurança).
Ruptura da seção líquida e as ligações ficam para as páginas das ligações.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from core import cantoneiras as ct
from core import column_buckling as cbk
from core import contraventamento_barras as cbar
from core import esforcos_modelo as em
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import section_catalog as sc
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "esforcos_modelo"
MODULO_TITULO = "Esforços do modelo"
ACOS: Mapping[str, tuple[float, float]] = cbar.ACOS
GAMMA_A1 = cbk.GAMMA_A1
STATUS_PENDENTE = "PENDENTE"
REFERENCIA_INTERACAO = "NBR 8800 5.5.1.2"
CANDIDATOS = 3  # pontos de cada tipo levados à verificação completa


@dataclass(frozen=True)
class ResultadoDaBarra:
    membro: str
    perfil: str
    tipo: str
    status: str  # "OK", "ALERTA", "NÃO OK" ou "PENDENTE"
    aproveitamento: float | None
    combinacao: str = ""
    ponto: str = ""
    n: float = 0.0  # de cálculo, já com B₂ (tração positiva)
    m_forte: float = 0.0
    m_fraco: float = 0.0
    n_rd: float | None = None  # N_c,Rd na compressão, N_t,Rd na tração
    mx_rd: float | None = None
    my_rd: float | None = None
    governante: str = ""
    motivo: str = ""
    linhas: tuple[Verificacao, ...] = ()
    metodo: str = ""


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _pendente(membro: str, cfg: em.ConfiguracaoDoMembro, motivo: str) -> ResultadoDaBarra:
    return ResultadoDaBarra(membro, cfg.perfil, cfg.tipo, STATUS_PENDENTE, None, motivo=motivo)


def _indice(n_ratio: float, mx_ratio: float, my_ratio: float) -> float:
    """NBR 8800 5.5.1.2 (a mesma forma na tração e na compressão)."""
    soma = mx_ratio + my_ratio
    return n_ratio + 8.0 / 9.0 * soma if n_ratio >= 0.2 else n_ratio / 2.0 + soma


def _razao(solicitante: float, resistente: float | None) -> float:
    if abs(solicitante) < 1e-12:
        return 0.0
    if not resistente or resistente <= 0:
        return math.inf
    return abs(solicitante) / resistente


@dataclass(frozen=True)
class _Tripla:
    combinacao: str
    ponto: str
    n: float
    m_forte: float
    m_fraco: float
    v: float
    t: float


def _triplas(combinados: Sequence[em.Combinado], eixo_forte: str, b2: float) -> list[_Tripla]:
    forte, fraco = (4, 3) if eixo_forte == em.EIXO_M2 else (3, 4)
    return [
        _Tripla(
            nome,
            ponto,
            b2 * v[0],
            b2 * v[forte],
            b2 * v[fraco],
            b2 * math.hypot(v[1], v[2]),
            v[5],
        )
        for nome, ponto, v in combinados
    ]


def _linhas_comuns(
    triplas: Sequence[_Tripla], v_rd: float | None, rotulo_vrd: str
) -> list[Verificacao]:
    linhas: list[Verificacao] = []
    maior_v = max(triplas, key=lambda x: x.v)
    if v_rd:
        linhas.append(
            Verificacao(
                "Cortante (resultante de V₁ e V₂) ≤ V_Rd",
                maior_v.v,
                v_rd,
                "kN",
                "NBR 8800 5.4.3",
                f"{maior_v.combinacao}, {maior_v.ponto}; {rotulo_vrd}",
            )
        )
    maior_t = max(triplas, key=lambda x: abs(x.t))
    linhas.append(
        Verificacao(
            "Torção (informativo)",
            None,
            abs(maior_t.t),
            "kN·m",
            "—",
            f"maior torque {_n(abs(maior_t.t), 3)} kN·m ({maior_t.combinacao}, {maior_t.ponto}): "
            "não verificado — confira se a barra trabalha à torção",
            status="INFO",
            tipo="informativo",
        )
    )
    return linhas


def _verificar_perfil(
    membro: str,
    cfg: em.ConfiguracaoDoMembro,
    triplas: Sequence[_Tripla],
    fy: float,
    lx_mm: float,
    ly_mm: float,
    lb_mm: float,
    cb: float,
    norma: str,
) -> ResultadoDaBarra:
    perfil = sc.obter_perfil(cfg.perfil)
    secao = cbk.secao_de_perfil(perfil)
    base = cbk.EntradaColuna(
        secao=secao,
        fy_MPa=fy,
        norma=norma,
        Lx_mm=lx_mm,
        Ly_mm=ly_mm,
        Lb_mm=lb_mm,
        Cb=cb,
        N_Sd_kN=1e-3,
        Mx_kNm=1e-3,
        My_kNm=1e-3,
    )
    referencia = cbk.verificar_coluna(base)
    nc_rd = referencia.compressao["Nc_Rd"] if referencia.compressao else None
    mx_rd, my_rd = referencia.mrd_x_kNm, referencia.mrd_y_kNm
    nt_rd = perfil.area_mm2 * fy / GAMMA_A1 / 1e3
    v_rd = 0.60 * fy * perfil.area_cisalhamento_mm2 / GAMMA_A1 / 1e3

    def rapido(t: _Tripla) -> float:
        n_ratio = _razao(t.n, nc_rd) if t.n < 0 else _razao(t.n, nt_rd)
        return _indice(n_ratio, _razao(t.m_forte, mx_rd), _razao(t.m_fraco, my_rd))

    compressao = sorted((t for t in triplas if t.n < 0), key=rapido, reverse=True)
    tracao = sorted((t for t in triplas if t.n >= 0), key=rapido, reverse=True)
    candidatos: list[_Tripla] = [*compressao[:CANDIDATOS], *tracao[:CANDIDATOS]]
    if compressao:
        candidatos.append(min(compressao, key=lambda t: t.n))
    melhor: tuple[float, _Tripla, list[Verificacao], str, float | None] | None = None
    for t in candidatos:
        if t.n < 0:
            r = cbk.verificar_coluna(
                replace(base, N_Sd_kN=-t.n, Mx_kNm=abs(t.m_forte), My_kNm=abs(t.m_fraco))
            )
            indice = r.indice_interacao if r.indice_interacao is not None else 0.0
            indice = max(indice, r.aproveitamento_max or 0.0)
            linhas = list(r.verificacoes)
            governante = r.governante
            n_rd = nc_rd
        else:
            r = cbk.verificar_coluna(
                replace(base, N_Sd_kN=0.0, Mx_kNm=abs(t.m_forte) or 1e-6, My_kNm=abs(t.m_fraco))
            )
            mxr = r.mrd_x_kNm or mx_rd
            myr = r.mrd_y_kNm or my_rd
            indice = _indice(_razao(t.n, nt_rd), _razao(t.m_forte, mxr), _razao(t.m_fraco, myr))
            linhas = [
                v
                for v in r.verificacoes
                if not v.nome.startswith(("Compressão axial", "Interação N + Mx + My"))
            ]
            linhas.append(
                Verificacao(
                    "Tração: escoamento da seção bruta",
                    t.n,
                    nt_rd,
                    "kN",
                    "NBR 8800 5.2.2-a",
                    f"N_t,Rd = A_g·f_y/γ_a1 = {_n(perfil.area_mm2, 0)}·{_n(fy, 0)}/{_n(GAMMA_A1)} "
                    "(a ruptura da seção líquida depende da ligação)",
                )
            )
            linhas.append(
                Verificacao(
                    "Interação N + Mx + My (tração)",
                    indice,
                    1.0,
                    "—",
                    REFERENCIA_INTERACAO,
                    f"N/N_t,Rd = {_n(_razao(t.n, nt_rd), 3)}; Mx/Mx,Rd = "
                    f"{_n(_razao(t.m_forte, mxr), 3)}; My/My,Rd = {_n(_razao(t.m_fraco, myr), 3)}",
                )
            )
            governante = "Interação N + Mx + My (tração)"
            n_rd = nt_rd
            if not compressao:  # barra sem compressão: vale o limite de esbeltez da tração
                linhas = [v for v in linhas if not v.nome.startswith("Esbeltez limite")]
                esbeltez = max(lx_mm / perfil.rx_mm, ly_mm / perfil.ry_mm)
                linhas.append(
                    Verificacao(
                        "Esbeltez limite (tração)",
                        esbeltez,
                        cbk.ESBELTEZ_MAXIMA_TRACAO,
                        "—",
                        "NBR 8800 5.2.8; Anglo 8.3",
                        f"máx(L_x/r_x; L_y/r_y) = {_n(esbeltez, 0)} ≤ 300",
                        tipo="limite",
                    )
                )
            indice = max(
                indice,
                max((v.aproveitamento or 0.0) for v in linhas if v.tipo == "resistencia"),
            )
        if melhor is None or indice > melhor[0]:
            melhor = (indice, t, linhas, governante, n_rd)
    assert melhor is not None
    indice, t, linhas, governante, n_rd = melhor
    linhas = [*linhas, *_linhas_comuns(triplas, v_rd, "V_Rd = 0,6·f_y·A_w/γ_a1")]
    return ResultadoDaBarra(
        membro,
        cfg.perfil,
        cfg.tipo,
        status_geral(linhas),
        max(indice, max((v.aproveitamento or 0.0) for v in linhas if v.tipo == "resistencia")),
        t.combinacao,
        t.ponto,
        t.n,
        t.m_forte,
        t.m_fraco,
        n_rd,
        mx_rd,
        my_rd,
        governante,
        linhas=tuple(linhas),
    )


def _verificar_cantoneira(
    membro: str,
    cfg: em.ConfiguracaoDoMembro,
    triplas: Sequence[_Tripla],
    fy: float,
    comprimento_mm: float,
) -> ResultadoDaBarra:
    cant = ct.obter_cantoneira(cfg.perfil)
    nt_rd = cant.area_mm2 * fy / GAMMA_A1 / 1e3
    pior_c = min(triplas, key=lambda t: t.n)
    pior_t = max(triplas, key=lambda t: t.n)
    linhas: list[Verificacao] = []
    nc_rd = None
    if pior_c.n < 0:
        nc_rd, linhas_c = cbar.compressao_de_cantoneira_simples(
            cant, fy, comprimento_mm, -pior_c.n, "Cantoneira"
        )
        linhas += linhas_c
    if pior_t.n > 0:
        linhas.append(
            Verificacao(
                "Cantoneira: tração (escoamento da seção bruta)",
                pior_t.n,
                nt_rd,
                "kN",
                "NBR 8800 5.2.2-a",
                f"{pior_t.combinacao}, {pior_t.ponto}; a ruptura da seção líquida depende da ligação",
            )
        )
    maior_m = max(triplas, key=lambda t: math.hypot(t.m_forte, t.m_fraco))
    m = math.hypot(maior_m.m_forte, maior_m.m_fraco)
    tensao = m * 1e6 * (cant.b_mm - cant.x_barra_mm) / cant.i_z_mm4 if m else 0.0
    linhas.append(
        Verificacao(
            "Cantoneira: flexão",
            None,
            None,
            "MPa",
            "NBR 8800 5.5",
            f"M = {_n(m, 3)} kN·m dá cerca de {_n(tensao, 0)} MPa no eixo de menor inércia"
            + (": flexão relevante, verifique a cantoneira à flexão" if tensao > 0.1 * fy else ""),
            status="ALERTA" if tensao > 0.1 * fy else "INFO",
            tipo="informativo",
        )
    )
    linhas += _linhas_comuns(triplas, None, "")
    governante = max(
        (v for v in linhas if v.tipo == "resistencia"),
        key=lambda v: v.aproveitamento or 0.0,
        default=None,
    )
    usada = pior_c if (nc_rd and pior_c.n < 0) else pior_t
    return ResultadoDaBarra(
        membro,
        cfg.perfil,
        cfg.tipo,
        status_geral(linhas),
        None if governante is None else governante.aproveitamento,
        usada.combinacao,
        usada.ponto,
        usada.n,
        usada.m_forte,
        usada.m_fraco,
        nc_rd if usada.n < 0 else nt_rd,
        None,
        None,
        "" if governante is None else governante.nome,
        linhas=tuple(linhas),
    )


def estados_ultimos(estados: Sequence[str]) -> list[str]:
    ultimos = [e for e in estados if e in comb.COMBINACOES_ULTIMAS]
    return ultimos or [comb.ELU_NORMAL]


def verificar_barras(
    dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas, estados: Sequence[str] = (comb.ELU_NORMAL,)
) -> tuple[list[ResultadoDaBarra], list[str]]:
    """Verifica todas as barras com as combinações ELU escolhidas (as de serviço ficam de fora)."""
    preparo = em.preparar_combinacoes(dados, plano, estados_ultimos(estados))
    if preparo is None:
        return [], ["Nenhum caso do plano de cargas foi importado."]
    resultados: list[ResultadoDaBarra] = []
    avisos: list[str] = []
    for membro in dados.nomes_dos_membros:
        cfg = dados.membros.get(membro, em.ConfiguracaoDoMembro())
        tipo = dados.parametros_do_tipo(cfg.tipo)
        if not cfg.perfil:
            resultados.append(_pendente(membro, cfg, "escolha o perfil na tabela das barras"))
            continue
        lx = cfg.lx_m or tipo.lx_m
        ly = cfg.ly_m or tipo.ly_m
        if not lx or not ly:
            resultados.append(
                _pendente(
                    membro,
                    cfg,
                    "informe os comprimentos de flambagem L_x e L_y (na barra ou no tipo "
                    f"{cfg.tipo if cfg.tipo != '—' else 'sem tipo'})",
                )
            )
            continue
        lb = cfg.lb_m or tipo.lb_m or ly
        aco = cfg.aco or tipo.aco
        if aco not in ACOS:
            resultados.append(_pendente(membro, cfg, f"aço desconhecido: {aco!r}"))
            continue
        fy = ACOS[aco][0]
        combinados, metodo, aviso = em.combinados_do_membro(membro, preparo)
        if aviso:
            avisos.append(aviso)
        triplas = _triplas(combinados, cfg.eixo_forte, tipo.b2)
        try:
            if cfg.perfil in ct.CATALOGO_CANTONEIRAS:
                resultado = _verificar_cantoneira(membro, cfg, triplas, fy, max(lx, ly) * 1e3)
            else:
                resultado = _verificar_perfil(
                    membro,
                    cfg,
                    triplas,
                    fy,
                    lx * 1e3,
                    ly * 1e3,
                    lb * 1e3,
                    tipo.cb,
                    dados.norma,
                )
        except (KeyError, ValueError) as erro:
            resultados.append(_pendente(membro, cfg, f"não foi possível verificar: {erro}"))
            continue
        resultados.append(replace(resultado, metodo=metodo))
    return resultados, avisos


# ---------------------------------------------------------------------------------------------
# Tabela, CSV e registro
# ---------------------------------------------------------------------------------------------
COLUNAS = (
    "Barra",
    "Tipo",
    "Perfil",
    "Situação",
    "Aproveitamento (%)",
    "Combinação",
    "Ponto",
    "N (kN)",
    "M forte (kN·m)",
    "M fraco (kN·m)",
    "N_Rd (kN)",
    "Mx,Rd (kN·m)",
    "My,Rd (kN·m)",
    "Governa",
)


def linhas_da_tabela(resultados: Sequence[ResultadoDaBarra]) -> list[list[object]]:
    return [
        [
            r.membro,
            r.tipo,
            r.perfil or "—",
            r.status,
            "" if r.aproveitamento is None else 100 * r.aproveitamento,
            r.combinacao,
            r.ponto,
            "" if r.status == STATUS_PENDENTE else r.n,
            "" if r.status == STATUS_PENDENTE else r.m_forte,
            "" if r.status == STATUS_PENDENTE else r.m_fraco,
            "" if r.n_rd is None else r.n_rd,
            "" if r.mx_rd is None else r.mx_rd,
            "" if r.my_rd is None else r.my_rd,
            r.governante or r.motivo,
        ]
        for r in resultados
    ]


def csv_das_barras(resultados: Sequence[ResultadoDaBarra]) -> bytes:
    return pc._csv(COLUNAS, linhas_da_tabela(resultados))


def resumo(resultados: Sequence[ResultadoDaBarra]) -> dict[str, Any]:
    verificadas = [r for r in resultados if r.status != STATUS_PENDENTE]
    pior = max(verificadas, key=lambda r: r.aproveitamento or 0.0, default=None)
    return {
        "total": len(resultados),
        "atendem": sum(r.status in ("OK", "ALERTA") for r in verificadas),
        "nao_atendem": sum(r.status == "NÃO OK" for r in verificadas),
        "atencao": sum(r.status == "ALERTA" for r in verificadas),
        "pendentes": len(resultados) - len(verificadas),
        "pior": pior,
    }


def _linha_do_registro(r: ResultadoDaBarra) -> Verificacao:
    if r.status == STATUS_PENDENTE:
        return Verificacao(
            f"{r.membro} — {r.perfil or 'sem perfil'}",
            None,
            None,
            "—",
            "—",
            r.motivo,
            status="N/A",
        )
    return Verificacao(
        f"{r.membro} — {r.perfil} ({r.tipo})",
        r.aproveitamento,
        1.0,
        "—",
        f"{REFERENCIA_INTERACAO}; NBR 8800 5.3 e 5.4",
        f"{r.combinacao}, {r.ponto}: N = {_n(r.n)} kN; M forte = {_n(r.m_forte)} kN·m; M fraco = "
        f"{_n(r.m_fraco)} kN·m; governa: {r.governante}",
        status=r.status,
        aproveitamento=r.aproveitamento,
    )


def registro_das_barras(
    resultados: Sequence[ResultadoDaBarra],
    dados: em.EsforcosDoModelo,
    estados: Sequence[str],
    *,
    contexto: Mapping[str, Any] | None = None,
    responsavel: str = "",
) -> dict[str, Any]:
    linhas = [_linha_do_registro(r) for r in resultados]
    sintese = resumo(resultados)
    geral = status_geral(linhas)
    pior = sintese["pior"]
    destaque = (
        f"{sintese['total']} barras do modelo: {sintese['atendem']} atendem, "
        f"{sintese['nao_atendem']} não atendem e {sintese['pendentes']} sem dados para verificar."
        + (
            f" Maior aproveitamento: {_n(100 * (pior.aproveitamento or 0.0), 1)} % em {pior.membro} "
            f"({pior.perfil}, {pior.combinacao})."
            if pior is not None
            else ""
        )
    )
    tabela = {
        "legenda": "Verificação das barras do modelo — combinação e ponto que governam cada uma.",
        "cabecalhos": [
            "Barra",
            "Perfil",
            "Tipo",
            "Combinação",
            "N (kN)",
            "M forte",
            "Aprov.",
            "Situação",
        ],
        "linhas": [
            [
                r.membro,
                r.perfil or "—",
                r.tipo,
                r.combinacao or "—",
                "—" if r.status == STATUS_PENDENTE else _n(r.n),
                "—" if r.status == STATUS_PENDENTE else _n(r.m_forte),
                "—" if r.aproveitamento is None else f"{_n(100 * r.aproveitamento, 1)} %",
                r.status if r.status != STATUS_PENDENTE else "pendente",
            ]
            for r in resultados
        ],
        "larguras": [2200, 1500, 900, 1000, 900, 900, 900, 1060],
        "fonte": 7.0,
    }
    entradas: dict[str, Any] = {
        "casos_do_modelo": ", ".join(dados.casos),
        "estados_limites": ", ".join(estados_ultimos(estados)),
        "norma": cbk.NORMAS_ROTULOS.get(dados.norma, dados.norma),
        "eixo_vertical_do_modelo": dados.eixo_vertical,
        "barras": len(resultados),
        "b2_por_tipo": "; ".join(
            f"{tipo}: {_n(p.b2)}" for tipo, p in dados.parametros.items() if abs(p.b2 - 1.0) > 1e-9
        )
        or None,
    }
    entradas.update(dict(contexto or {}))
    entradas = {k: v for k, v in entradas.items() if v is not None}
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Verificação das barras do modelo — {len(resultados)} barras",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas=entradas,
        resultados={
            "status_geral": geral,
            "verificações": linhas_para_registro(linhas),
            "utilizacao_maxima": None
            if pior is None
            else numero_json(pior.aproveitamento or 0.0, 4),
            "destaque_memorial": destaque,
            "tabelas_memorial": [tabela],
        },
        metodo=(
            "Esforços de cálculo de cada barra em todas as combinações ELU do plano de cargas, ponto "
            "a ponto, a partir dos estudos do SolidWorks Simulation (um por caso de carga). "
            "Verificação pela NBR 8800 (compressão com todos os modos de flambagem e flambagem "
            "local, flexão com FLT, FLM e FLA, B₁ e interação N + Mx + My numa única equação); "
            "cantoneiras simples pela 5.3.5.4."
        ),
        premissas=[
            "Esforços de primeira ordem do SolidWorks multiplicados pelo B₂ do tipo de barra, em "
            "todos os esforços (a favor da segurança).",
            "B₁ com C_m = 1 (a favor da segurança); comprimentos de flambagem K·L informados.",
            "Ruptura da seção líquida e ligações verificadas à parte; torção não verificada.",
        ],
        referencias=[
            "ABNT NBR 8800 (Projeto de revisão 2024 e edição de 2008): 5.2, 5.3, 5.4, 5.5.1.2 e "
            "Anexo D.",
        ],
        conclusao=destaque,
        responsavel=responsavel,
    )
