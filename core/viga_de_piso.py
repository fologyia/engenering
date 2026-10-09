"""Viga de piso de plataforma (a que apoia a grade): esforços, NBR 8800, flechas e critério Anglo.

Viga biapoiada com carga distribuída vinda do piso (largura de influência × carga por área), carga
linear extra (guarda-corpo, tubulação) e, se houver, uma carga concentrada no meio do vão
(equipamento). O peso próprio sai do perfil.

* **Combinações** pela NBR 8800 (Tabelas 1 e 2, :mod:`core.load_combinations`): o peso próprio do
  aço, o piso (elementos construtivos industrializados), a sobrecarga e o equipamento, cada um com
  a sua categoria; vale a combinação ELU de maior momento e a de maior cortante.
* **Flexão** pelo mesmo motor da página Flambagem de colunas (:mod:`core.column_buckling`): FLT com
  o comprimento destravado ``L_b`` e o ``C_b`` do diagrama de momentos, FLM, FLA e o limite de
  1,5·W·f_y.
* **Cortante** pela NBR 8800 5.4.3 (alma com k_v = 5, com a redução por flambagem da alma).
* **Flecha** sob as cargas de serviço (combinação rara: todas as cargas características) contra o
  critério Anglo (Tabela 3: vigas de piso principais L/350, secundárias L/300) e a NBR 8800 (Anexo
  C, vigas de piso L/350).
* **Informativos**: reação de apoio, a capacidade mínima da ligação do critério Anglo (9.1: 75 % da
  carga uniforme que a viga resiste) e a frequência natural (para comparar com equipamentos, 5.7).

Sem Streamlit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from core import column_buckling as cbk
from core import criterio_anglo as ca
from core import load_combinations as comb
from core import section_catalog as sc
from core.contraventamento_barras import ACOS
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "viga_de_piso"
MODULO_TITULO = "Vigas de piso"
TIPO_PRINCIPAL = "Viga de piso principal"
TIPO_SECUNDARIA = "Viga de piso secundária"
TIPOS = (TIPO_PRINCIPAL, TIPO_SECUNDARIA)
LIMITE_ANGLO = {TIPO_PRINCIPAL: 350.0, TIPO_SECUNDARIA: 300.0}  # Tabela 3
LIMITE_NBR = 350.0  # NBR 8800 Anexo C, Tabela C.1: vigas de piso
E_ACO = 200_000.0
GAMMA_A1 = cbk.GAMMA_A1
G = 9.80665

CATEGORIA_PP = "Peso próprio de estrutura metálica"
CATEGORIA_PE = "Elementos construtivos industrializados (grades, pisos, guarda-corpos)"
CATEGORIA_SC = "Sobrecarga de uso — predominância de equipamentos fixos ou concentração de pessoas"
CATEGORIA_EQ = "Peso próprio de equipamentos (Projeto NBR 8800:2024)"


class VigaInvalida(ValueError):
    """Dado que o cálculo não aceita; a mensagem diz o que corrigir."""


@dataclass(frozen=True)
class EntradaVigaDePiso:
    perfil: str = "W 200 x 15,0"
    aco: str = "ASTM A572 Gr 50"
    vao_m: float = 4.0
    largura_influencia_m: float = 1.0
    lb_m: float | None = None  # trecho sem travamento lateral; vazio = o vão
    pe_kN_m2: float = 0.45  # grade e acessórios
    sc_kN_m2: float = 5.0
    linear_extra_kN_m: float = 0.0  # guarda-corpo, tubulação (permanente)
    concentrada_kN: float = 0.0  # equipamento no meio do vão
    tipo: str = TIPO_PRINCIPAL
    norma: str = "NBR8800_2024"
    anglo: bool = False


@dataclass(frozen=True)
class ResultadoVigaDePiso:
    entrada: EntradaVigaDePiso
    peso_proprio_kN_m: float
    cargas_kN_m: dict[str, float]  # característica por ação (distribuídas)
    momento_sd_kNm: float
    cortante_sd_kN: float
    combinacao_momento: str
    combinacao_cortante: str
    momento_rd_kNm: float
    cortante_rd_kN: float
    cb: float
    lb_m: float
    flecha_mm: float
    flecha_sobrecarga_mm: float
    reacao_caracteristica_kN: float
    reacao_calculo_kN: float
    reacao_minima_ligacao_kN: float | None
    frequencia_Hz: float
    verificacoes: tuple[Verificacao, ...]

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))

    @property
    def aproveitamento_maximo(self) -> float:
        return max(
            (v.aproveitamento or 0.0 for v in self.verificacoes if v.tipo == "resistencia"),
            default=0.0,
        )


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def validar(e: EntradaVigaDePiso) -> list[str]:
    erros: list[str] = []
    if e.perfil not in sc.listar_perfis():
        erros.append(f"Perfil fora do catálogo: {e.perfil!r}.")
    if e.aco not in ACOS:
        erros.append(f"Aço desconhecido: {e.aco!r}.")
    if e.tipo not in TIPOS:
        erros.append(f"Tipo de viga desconhecido: {e.tipo!r}.")
    if not (0.3 <= e.vao_m <= 30.0):
        erros.append("O vão precisa estar entre 0,3 e 30 m.")
    if not (0.05 <= e.largura_influencia_m <= 15.0):
        erros.append("A largura de influência precisa estar entre 0,05 e 15 m.")
    if e.lb_m is not None and not (0.05 <= e.lb_m <= e.vao_m + 1e-9):
        erros.append("O trecho sem travamento precisa estar entre 0,05 m e o vão.")
    for nome, valor in (
        ("A carga do piso", e.pe_kN_m2),
        ("A sobrecarga", e.sc_kN_m2),
        ("A carga linear extra", e.linear_extra_kN_m),
        ("A carga concentrada", e.concentrada_kN),
    ):
        if not (math.isfinite(valor) and valor >= 0):
            erros.append(f"{nome} não pode ser negativa.")
    return erros


def cb_biapoiada(q_kN_m: float, p_kN: float, vao_m: float) -> float:
    """C_b da NBR 8800 (5.4.2.3, R_m = 1) para a viga inteira sem travamento."""

    def momento(x: float) -> float:
        meio = vao_m / 2
        return q_kN_m * x * (vao_m - x) / 2 + p_kN * (x if x <= meio else vao_m - x) / 2

    ma, mb, mc = (momento(vao_m * f) for f in (0.25, 0.5, 0.75))
    mmax = mb
    if mmax <= 0:
        return 1.0
    return min(3.0, 12.5 * mmax / (2.5 * mmax + 3 * ma + 4 * mb + 3 * mc))


def _cortante_rd(perfil: Any, fy: float) -> tuple[float, str]:
    """NBR 8800 5.4.3.1.1, alma sem enrijecedores (k_v = 5)."""
    h = perfil.altura_mm - 2 * perfil.espessura_mesa_mm
    tw = perfil.espessura_alma_mm
    aw = perfil.altura_mm * tw
    vpl = 0.60 * aw * fy
    esbeltez = h / tw
    lp = 1.10 * math.sqrt(5 * E_ACO / fy)
    lr = 1.37 * math.sqrt(5 * E_ACO / fy)
    if esbeltez <= lp:
        vrd, texto = (
            vpl / GAMMA_A1,
            f"h/t_w = {_n(esbeltez, 1)} ≤ λ_p = {_n(lp, 1)}: V_Rd = V_pl/γ_a1",
        )
    elif esbeltez <= lr:
        vrd = lp / esbeltez * vpl / GAMMA_A1
        texto = f"λ_p < h/t_w = {_n(esbeltez, 1)} ≤ λ_r: V_Rd = (λ_p/λ)·V_pl/γ_a1"
    else:
        vrd = 1.24 * (lp / esbeltez) ** 2 * vpl / GAMMA_A1
        texto = f"h/t_w = {_n(esbeltez, 1)} > λ_r: V_Rd = 1,24·(λ_p/λ)²·V_pl/γ_a1"
    return vrd / 1e3, f"{texto}; V_pl = 0,6·d·t_w·f_y = {_n(vpl / 1e3, 1)} kN"


def calcular(e: EntradaVigaDePiso) -> ResultadoVigaDePiso:
    erros = validar(e)
    if erros:
        raise VigaInvalida(" ".join(erros))
    perfil = sc.obter_perfil(e.perfil)
    fy = ACOS[e.aco][0]
    vao = e.vao_m
    pp = perfil.massa_kg_m * G / 1e3
    cargas = {
        "PP": pp,
        "PE": e.pe_kN_m2 * e.largura_influencia_m + e.linear_extra_kN_m,
        "SC": e.sc_kN_m2 * e.largura_influencia_m,
    }
    acoes = [
        comb.acao_da_categoria(nome, categoria, 0.0, q * vao / 2, q * vao**2 / 8)
        for nome, categoria, q in (
            ("PP", CATEGORIA_PP, cargas["PP"]),
            ("PE", CATEGORIA_PE, cargas["PE"]),
            ("SC", CATEGORIA_SC, cargas["SC"]),
        )
        if q > 0
    ]
    if e.concentrada_kN > 0:
        acoes.append(
            comb.acao_da_categoria(
                "EQ", CATEGORIA_EQ, 0.0, e.concentrada_kN / 2, e.concentrada_kN * vao / 4
            )
        )
    lista = comb.gerar_combinacoes(acoes, [comb.ELU_NORMAL])
    governa_m = max(lista, key=lambda c: abs(c.m_kNm))
    governa_v = max(lista, key=lambda c: abs(c.v_kN))
    m_sd, v_sd = abs(governa_m.m_kNm), abs(governa_v.v_kN)

    lb = e.lb_m if e.lb_m else vao
    q_total = sum(cargas.values())
    cb = cb_biapoiada(q_total, e.concentrada_kN, vao) if lb >= vao - 1e-9 else 1.0
    r = cbk.verificar_coluna(
        cbk.EntradaColuna(
            secao=cbk.secao_de_perfil(perfil),
            fy_MPa=fy,
            norma=e.norma,
            Lx_mm=vao * 1e3,
            Ly_mm=lb * 1e3,
            Lb_mm=lb * 1e3,
            Cb=cb,
            N_Sd_kN=1e-6,
            Mx_kNm=m_sd,
        )
    )
    linhas: list[Verificacao] = [
        v for v in r.verificacoes if v.nome.startswith(("Mx,Rd", "Flexão em torno de x"))
    ]
    m_rd = r.mrd_x_kNm or 0.0
    v_rd, texto_v = _cortante_rd(perfil, fy)
    linhas.append(
        Verificacao(
            "Cortante: V_Sd ≤ V_Rd",
            v_sd,
            v_rd,
            "kN",
            "NBR 8800 5.4.3",
            f"{decimal(governa_v.expressao)}; {texto_v}",
        )
    )
    ei = E_ACO * perfil.ix_mm4  # N·mm²
    l_mm = vao * 1e3

    def flecha_q(q_kN_m: float) -> float:
        return 5 * q_kN_m * l_mm**4 / (384 * ei)  # kN/m = N/mm

    flecha = flecha_q(q_total) + e.concentrada_kN * 1e3 * l_mm**3 / (48 * ei)
    flecha_sc = flecha_q(cargas["SC"])
    limite_anglo = LIMITE_ANGLO[e.tipo]
    if e.anglo:
        linhas.append(
            Verificacao(
                f"Flecha (serviço) ≤ L/{limite_anglo:g} — {e.tipo.lower()}",
                flecha,
                l_mm / limite_anglo,
                "mm",
                f"{ca.item('7')}, Tabela 3",
                f"δ = 5·q·L⁴/(384·E·I) + P·L³/(48·E·I), q = {_n(q_total, 3)} kN/m, P = "
                f"{_n(e.concentrada_kN)} kN (cargas características)",
            )
        )
    linhas.append(
        Verificacao(
            f"Flecha (serviço) ≤ L/{LIMITE_NBR:g} — vigas de piso",
            flecha,
            l_mm / LIMITE_NBR,
            "mm",
            "NBR 8800 Anexo C, Tabela C.1",
            f"combinação rara (todas as cargas características): δ = {_n(flecha, 1)} mm",
        )
    )
    if e.anglo:
        minimo = ca.ESPESSURAS_MINIMAS_MM["Perfis laminados H e W"]
        menor = min(perfil.espessura_alma_mm, perfil.espessura_mesa_mm)
        linhas.append(
            Verificacao(
                "Anglo: espessura mínima do perfil",
                minimo,
                menor,
                "mm",
                ca.item("8.8"),
                f"menor espessura (alma ou mesa) = {_n(menor, 1)} mm ≥ {_n(minimo, 2)} mm",
                tipo="limite",
            )
        )
    reacao_k = q_total * vao / 2 + e.concentrada_kN / 2
    reacao_d = v_sd
    w_rd_total = 8 * m_rd / vao if m_rd else 0.0  # carga uniforme total que a viga resiste
    minima = (
        max(ca.CAPACIDADE_MINIMA_VIGA * w_rd_total / 2, reacao_d) if (e.anglo and m_rd) else None
    )
    linhas.append(
        Verificacao(
            "Reação de apoio (para a ligação)",
            None,
            reacao_d,
            "kN",
            "—",
            f"característica {_n(reacao_k)} kN; de cálculo {_n(reacao_d)} kN"
            + (
                f"; critério Anglo 9.1: ligação para ≥ 75 % de W_Rd/2 = "
                f"{_n(ca.CAPACIDADE_MINIMA_VIGA * w_rd_total / 2)} kN (W_Rd = 8·M_Rd/L = "
                f"{_n(w_rd_total)} kN) → dimensionar para {_n(minima or 0.0)} kN"
                if minima is not None
                else ""
            ),
            status="INFO",
            tipo="informativo",
        )
    )
    flecha_perm = flecha_q(cargas["PP"] + cargas["PE"]) + e.concentrada_kN * 1e3 * l_mm**3 / (
        48 * ei
    )
    frequencia = 18.0 / math.sqrt(flecha_perm) if flecha_perm > 0 else math.inf
    linhas.append(
        Verificacao(
            "Frequência natural da viga (cargas permanentes)",
            None,
            frequencia,
            "Hz",
            ca.item("5.7") if e.anglo else "—",
            f"f ≈ 18/√δ = 18/√{_n(flecha_perm, 2)} mm: compare com a frequência dos equipamentos "
            "apoiados (critério Anglo 5.7: fora de 0,8 a 1,25 vez)",
            status="INFO",
            tipo="informativo",
        )
    )
    return ResultadoVigaDePiso(
        entrada=e,
        peso_proprio_kN_m=pp,
        cargas_kN_m=cargas,
        momento_sd_kNm=m_sd,
        cortante_sd_kN=v_sd,
        combinacao_momento=decimal(governa_m.expressao),
        combinacao_cortante=decimal(governa_v.expressao),
        momento_rd_kNm=m_rd,
        cortante_rd_kN=v_rd,
        cb=cb,
        lb_m=lb,
        flecha_mm=flecha,
        flecha_sobrecarga_mm=flecha_sc,
        reacao_caracteristica_kN=reacao_k,
        reacao_calculo_kN=reacao_d,
        reacao_minima_ligacao_kN=minima,
        frequencia_Hz=frequencia,
        verificacoes=tuple(linhas),
    )


def decimal(texto: str) -> str:
    from core.memorial_verificacoes import decimal_ptbr

    return decimal_ptbr(texto)


def registro_viga(
    r: ResultadoVigaDePiso, *, contexto: dict[str, Any] | None = None, responsavel: str = ""
) -> dict[str, Any]:
    e = r.entrada
    geral = r.status
    destaque = (
        f"{e.perfil} ({e.aco}), vão {_n(e.vao_m)} m e largura de influência "
        f"{_n(e.largura_influencia_m)} m: M_Sd = {_n(r.momento_sd_kNm)} kN·m para M_Rd = "
        f"{_n(r.momento_rd_kNm)} kN·m; flecha {_n(r.flecha_mm, 1)} mm (L/{e.vao_m * 1e3 / r.flecha_mm:.0f}); "
        f"reação de cálculo {_n(r.reacao_calculo_kN)} kN."
    )
    entradas: dict[str, Any] = {
        "perfil": e.perfil,
        "aco": e.aco,
        "tipo_de_viga": e.tipo,
        "vao_m": e.vao_m,
        "largura_de_influencia_m": e.largura_influencia_m,
        "trecho_sem_travamento_m": r.lb_m,
        "piso_kN_m2": e.pe_kN_m2,
        "sobrecarga_kN_m2": e.sc_kN_m2,
        "carga_linear_extra_kN_m": e.linear_extra_kN_m or None,
        "carga_concentrada_kN": e.concentrada_kN or None,
        "norma": cbk.NORMAS_ROTULOS.get(e.norma, e.norma),
        "criterio_do_cliente": f"Anglo American {ca.CODIGO} Rev. {ca.REVISAO}" if e.anglo else None,
    }
    entradas.update(contexto or {})
    entradas = {k: v for k, v in entradas.items() if v is not None}
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Viga de piso {e.perfil} — vão {_n(e.vao_m)} m",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas=entradas,
        resultados={
            "status_geral": geral,
            "verificações": linhas_para_registro(list(r.verificacoes)),
            "utilizacao_maxima": numero_json(r.aproveitamento_maximo, 4),
            "destaque_memorial": destaque,
        },
        metodo=(
            "Viga biapoiada. Combinações ELU da NBR 8800 (Tabelas 1 e 2) com o peso próprio do aço, "
            "o piso, a sobrecarga e o equipamento; flexão com FLT (C_b do diagrama de momentos), "
            "FLM e FLA; cortante pela 5.4.3; flecha sob as cargas características."
        ),
        premissas=[
            "Viga biapoiada; cargas do piso pela largura de influência.",
            "Carga concentrada no meio do vão (pior posição para momento e flecha).",
            "Flecha elástica sem contraflecha.",
        ],
        referencias=["ABNT NBR 8800 (Projeto 2024 e edição 2008): 5.4 e Anexo C."]
        + ([f"{ca.REFERENCIA}: 5.7, 7 (Tabela 3), 8.8 e 9.1."] if e.anglo else []),
        conclusao=destaque,
        responsavel=responsavel,
    )


def familia(perfil: str) -> str:
    """Família pelo prefixo do nome no catálogo (W, U, I, HP…)."""
    return sc.obter_perfil(perfil).familia


def perfil_mais_leve(e: EntradaVigaDePiso) -> tuple[str, ResultadoVigaDePiso] | None:
    """O perfil mais leve da mesma família que atende a todas as verificações."""
    alvo = familia(e.perfil)
    candidatos = sorted(
        (p for p in sc.listar_perfis().values() if p.familia == alvo),
        key=lambda p: (p.massa_kg_m, p.nome),
    )
    for perfil in candidatos:
        try:
            r = calcular(EntradaVigaDePiso(**{**e.__dict__, "perfil": perfil.nome}))
        except (VigaInvalida, ValueError):
            continue
        if r.status in ("OK", "ALERTA"):
            return perfil.nome, r
    return None
