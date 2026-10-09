"""Dimensionamento automático da chapa de nó (modo simplificado da Ligação de contraventamento).

Com a força, o ângulo, a viga, a coluna e o parafuso, o programa escolhe o resto e verifica:

1. **Parafusos**: duas fileiras, passo e gabarito de 3·d (arredondados a 5 mm), extremidade de
   1,5·d ou a mínima da tabela; o menor número por fileira cujo grupo resiste à força.
2. **Comprimentos da chapa**: o mínimo para caber o grupo (projeção do comprimento do grupo mais as
   extremidades e uma folga de 50 mm, arredondado a 25 mm, nunca menos que 150 mm) e, dentro disso,
   o par ``l_h``/``l_v`` que zera o momento nas interfaces pelo Método das Forças Uniformes
   (``α̅ − β̅·tanθ = e_b·tanθ − e_c``): fixa ``l_v`` e acha ``l_h``; se ``l_h`` não couber, fixa
   ``l_h`` e acha ``l_v``.
3. **Espessura**: a menor da série comercial em que todas as verificações da chapa, das soldas e
   dos parafusos passam; as **pernas das soldas** são as necessárias arredondadas para cima na série
   usual (nunca abaixo da mínima; com o critério Anglo, nunca abaixo da Tabela 6).

O resultado é um ponto de partida que fecha nas verificações — as dimensões precisam ir para o
desenho e ser conferidas (Whitmore, comprimento livre, folgas).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from core import bolted_connection as bc
from core import contraventamento_chapa as ch
from core import contraventamento_ligacao as lig
from core import contraventamento_ufm as ufm
from core import criterio_anglo as ca

ESPESSURAS_MM: tuple[float, ...] = (8.0, 9.5, 12.5, 16.0, 19.0, 22.4, 25.0, 31.5, 37.5, 44.5, 50.0)
PERNAS_MM: tuple[float, ...] = (5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0)
MAXIMO_POR_FILEIRA = 12
FOLGA_MM = 50.0
MINIMO_CHAPA_MM = 150.0

#: Linhas que o dimensionamento precisa fazer passar (as demais dependem da viga e da coluna).
PREFIXOS_DA_CHAPA = (
    "Parafusos do contraventamento",
    "Chapa de nó",
    "Chapa–viga",
    "Chapa–coluna",
    "Solda chapa",
)


def _acima(valor: float, passo: float) -> float:
    return passo * math.ceil(valor / passo - 1e-9)


def _perna(necessaria: float, minima: float) -> float:
    alvo = max(necessaria, minima)
    for perna in PERNAS_MM:
        if perna >= alvo - 1e-9:
            return perna
    return _acima(alvo, 2.0)


@dataclass(frozen=True)
class Dimensionamento:
    entrada: lig.EntradaLigacao
    resultado: lig.ResultadoLigacao
    passos: tuple[str, ...]
    chapa_atende: bool


def _linhas_da_chapa_ok(r: lig.ResultadoLigacao) -> bool:
    return all(
        v.status in ("OK", "INFO", "N/A")
        for v in r.verificacoes
        if v.nome.startswith(PREFIXOS_DA_CHAPA)
    )


def _parafusos_por_fileira(base: lig.EntradaLigacao, t: float, arranjo_base: dict) -> int | None:
    P = max(base.P_tracao_kN, base.P_compressao_kN)
    d = bc.PARAFUSOS[base.designacao_do_parafuso][0]
    for n in range(2, MAXIMO_POR_FILEIRA + 1):
        arranjo = ch.DisposicaoDosParafusos(fileiras=2, por_fileira=n, **arranjo_base)
        grupo = ch.resistencia_do_grupo(
            d,
            base.grau_do_parafuso,
            base.rosca_no_plano,
            base.planos_de_corte,
            arranjo,
            t,
            base.Fu_chapa_MPa,
            base.metodo,
            designacao=base.designacao_do_parafuso,
            t_barra_mm=base.t_barra_mm,
            Fu_barra_MPa=base.Fu_barra_MPa,
            extremidade_barra_mm=base.extremidade_barra_mm,
        )
        if grupo.grupo_kN >= P:
            return n
    return None


def _comprimentos(
    base: lig.EntradaLigacao, comprimento_ao_longo_mm: float
) -> tuple[float, float, str, str]:
    """``(l_h, l_v, ajuste, texto)`` que zeram o momento dentro do mínimo que cabe o grupo."""
    theta = math.radians(base.theta_graus)
    lh_min = max(MINIMO_CHAPA_MM, _acima(comprimento_ao_longo_mm * math.sin(theta) + FOLGA_MM, 25))
    lv_min = max(MINIMO_CHAPA_MM, _acima(comprimento_ao_longo_mm * math.cos(theta) + FOLGA_MM, 25))
    eb = base.perfil_viga.d_mm / 2.0
    ec = base.perfil_coluna.d_mm / 2.0 if base.ligacao_na_mesa_da_coluna else 0.0
    if base.caso == ufm.CASO_3:
        alfa = eb * math.tan(theta) - ec
        lh = ufm.comprimento_horizontal_para_alfa(alfa, base.t_chapa_de_topo_mm, base.corte_h_mm)
        lh = max(lh_min, _acima(lh, 5))
        return lh, base.lv_mm, base.ajuste, f"Caso 3: α̅ = {alfa:.0f} mm → l_h = {lh:.0f} mm."
    beta = ufm.centroide_da_solda_na_coluna(lv_min, base.corte_v_mm)
    alfa = ufm.alfa_ideal(beta, eb, ec, base.theta_graus)
    lh = ufm.comprimento_horizontal_para_alfa(alfa, base.t_chapa_de_topo_mm, base.corte_h_mm)
    if lh >= lh_min:
        lh = _acima(lh, 5)
        return (
            lh,
            lv_min,
            ufm.AJUSTE_BETA,
            f"l_v = {lv_min:.0f} mm (mínimo para o grupo); β = {beta:.0f} mm → α̅ = {alfa:.0f} mm "
            f"→ l_h = {lh:.0f} mm (sem momento nas interfaces).",
        )
    alfa_real = ufm.centroide_da_solda_na_viga(lh_min, base.corte_h_mm, base.t_chapa_de_topo_mm)
    beta_b = ufm.beta_ideal(alfa_real, eb, ec, base.theta_graus)
    lv = 2.0 * beta_b - base.corte_v_mm
    if lv >= lv_min:
        lv = _acima(lv, 5)
        return (
            lh_min,
            lv,
            ufm.AJUSTE_ALFA,
            f"l_h = {lh_min:.0f} mm (mínimo para o grupo); α = {alfa_real:.0f} mm → β̅ = "
            f"{beta_b:.0f} mm → l_v = {lv:.0f} mm (sem momento nas interfaces).",
        )
    return (
        lh_min,
        lv_min,
        ufm.AJUSTE_MINIMIZAR,
        f"l_h = {lh_min:.0f} mm e l_v = {lv_min:.0f} mm (mínimos para o grupo); o par ideal não "
        "cabe — o binário residual é distribuído e verificado nas interfaces.",
    )


def dimensionar_ligacao(base: lig.EntradaLigacao) -> Dimensionamento:
    """Escolhe parafusos, comprimentos, espessura e soldas a partir de ``base`` e verifica."""
    erros = lig.validar_entrada(replace(base, fileiras=2, por_fileira=2))
    if erros:
        raise ch.ChapaInvalida(" ".join(erros))
    d, _, e_min, _, _ = bc.PARAFUSOS[base.designacao_do_parafuso]
    passo = _acima(3.0 * d, 5)
    extremidade = max(_acima(1.5 * d, 5), float(e_min))
    arranjo_base = {"passo_mm": passo, "gabarito_mm": passo, "extremidade_mm": extremidade}
    ultimo: Dimensionamento | None = None
    for t in ESPESSURAS_MM:
        n = _parafusos_por_fileira(base, t, arranjo_base)
        if n is None:
            continue
        comprimento = (n - 1) * passo + 2.0 * extremidade
        lh, lv, ajuste, texto_geo = _comprimentos(base, comprimento)
        entrada = replace(
            base,
            t_chapa_mm=t,
            fileiras=2,
            por_fileira=n,
            passo_mm=passo,
            gabarito_mm=passo,
            extremidade_mm=extremidade,
            lh_mm=lh,
            lv_mm=lv,
            ajuste=ajuste,
            perna_na_viga_mm=PERNAS_MM[0],
            perna_na_coluna_mm=PERNAS_MM[0],
        )
        r = lig.calcular_ligacao(entrada)
        minima_cliente = ca.filete_minimo_mm(t) if base.criterio_anglo else 0.0
        perna_v = _perna(
            r.solda_viga.perna_necessaria_mm, max(r.solda_viga.perna_minima_mm, minima_cliente)
        )
        perna_c = (
            _perna(
                r.solda_coluna.perna_necessaria_mm,
                max(r.solda_coluna.perna_minima_mm, minima_cliente),
            )
            if r.solda_coluna is not None
            else entrada.perna_na_coluna_mm
        )
        entrada = replace(entrada, perna_na_viga_mm=perna_v, perna_na_coluna_mm=perna_c)
        r = lig.calcular_ligacao(entrada)
        passos = (
            f"Parafusos: 2 fileiras × {n} ({base.designacao_do_parafuso} {base.grau_do_parafuso}), "
            f"passo e gabarito {passo:.0f} mm, extremidade {extremidade:.0f} mm.",
            texto_geo,
            f"Espessura da chapa: {t:g} mm (a menor da série em que chapa, soldas e parafusos "
            "passam).",
            f"Pernas das soldas: {perna_v:g} mm na viga"
            + (f" e {perna_c:g} mm na coluna." if r.solda_coluna is not None else "."),
        )
        ultimo = Dimensionamento(entrada, r, passos, _linhas_da_chapa_ok(r))
        if ultimo.chapa_atende:
            return ultimo
    if ultimo is None:
        raise ch.ChapaInvalida(
            f"Nem com {MAXIMO_POR_FILEIRA} parafusos por fileira o grupo resiste à força: use um "
            "parafuso maior ou de grau mais alto."
        )
    return replace(
        ultimo,
        passos=(
            *ultimo.passos,
            "Nenhuma espessura da série fechou todas as verificações: veja as linhas NÃO OK.",
        ),
    )
