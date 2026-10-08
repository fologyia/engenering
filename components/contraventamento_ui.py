"""Interface da página Ligação de contraventamento (chapa de nó, Método das Forças Uniformes).

Só desenha a interface: o cálculo está em :mod:`core.contraventamento_ligacao` (que usa
:mod:`core.contraventamento_ufm` e :mod:`core.contraventamento_chapa`) e o registro e as tabelas
em :mod:`core.contraventamento_registro`. A página recalcula a cada interação. Entrada que não dá
para calcular vira erro claro — nada é corrigido em silêncio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from components.contraventamento_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.ui import fronteira_modelo
from components.verification_table import mostrar_tabela_verificacoes
from core import bolted_connection as bc
from core import contraventamento_chapa as ch
from core import contraventamento_ligacao as lig
from core import contraventamento_registro as reg
from core import contraventamento_ufm as ufm
from core import section_catalog as sc
from core import steel_sections as ss
from core.verificacao import csv_verificacoes, status_geral

PREFIXO = "cv_"
ORIGEM_DIGITAR = "Digitar as medidas"
ORIGEM_CATALOGO = "Catálogo do programa"
ACO_PADRAO_PERFIL = "ASTM A992"
ACO_PADRAO_CHAPA = "ASTM A572 Gr 50"
PERFIS_PADRAO = {
    "viga": ("W 530 × 85", 535.0, 10.3, 16.5, 166.0, 32.0, 1970.0, 48200.0),
    "coluna": ("W 360 × 91", 353.0, 9.5, 16.4, 254.0, 30.0, 1168.0, 26755.0),
}


def _numero(
    rotulo: str,
    chave: str,
    valor: float,
    ajuda: str,
    *,
    minimo: float = 0.0,
    maximo: float | None = None,
    passo: float | None = None,
    formato: str | None = None,
    alvo: Any = st,
) -> float:
    return float(
        alvo.number_input(
            rotulo,
            min_value=float(minimo),
            max_value=maximo,
            value=float(valor),
            step=passo,
            format=formato,
            key=PREFIXO + chave,
            persist_state="session",
            help=ajuda,
        )
    )


def _inteiro(
    rotulo: str,
    chave: str,
    valor: int,
    ajuda: str,
    *,
    minimo: int,
    maximo: int,
    alvo: Any = st,
) -> int:
    return int(
        alvo.number_input(
            rotulo,
            min_value=minimo,
            max_value=maximo,
            value=valor,
            step=1,
            key=PREFIXO + chave,
            persist_state="session",
            help=ajuda,
        )
    )


def _selecao(
    rotulo: str,
    chave: str,
    opcoes: list[str],
    ajuda: str,
    *,
    formatar: Any = None,
    padrao: str | None = None,
    alvo: Any = st,
) -> str:
    chave_completa = PREFIXO + chave
    if st.session_state.get(chave_completa) not in opcoes:
        st.session_state.pop(chave_completa, None)
    return str(
        alvo.selectbox(
            rotulo,
            opcoes,
            index=opcoes.index(padrao) if padrao in opcoes else 0,
            format_func=formatar or str,
            key=chave_completa,
            persist_state="session",
            help=ajuda,
        )
    )


@dataclass(frozen=True)
class Identificacao:
    obra: str
    tag: str
    responsavel: str
    data: date


def formulario_identificacao() -> Identificacao:
    with st.container(border=True):
        st.subheader("1. Identificação", help=AJUDA["sec_1"])
        colunas = st.columns(4)
        obra = colunas[0].text_input(
            "Obra", key=PREFIXO + "obra", persist_state="session", help=AJUDA["obra"]
        )
        tag = colunas[1].text_input(
            "TAG", key=PREFIXO + "tag", persist_state="session", help=AJUDA["tag"]
        )
        responsavel = colunas[2].text_input(
            "Responsável",
            key=PREFIXO + "responsavel",
            persist_state="session",
            help=AJUDA["responsavel"],
        )
        data = colunas[3].date_input(
            "Data",
            value=date.today(),
            format="DD/MM/YYYY",
            key=PREFIXO + "data",
            persist_state="session",
            help=AJUDA["data"],
        )
    return Identificacao(obra.strip(), tag.strip(), responsavel.strip(), data)


@dataclass(frozen=True)
class DadosForca:
    metodo: str
    P_tracao: float
    P_compressao: float
    theta: float


def formulario_forca() -> DadosForca:
    with st.container(border=True):
        st.subheader("2. Contraventamento e método", help=AJUDA["sec_2"])
        metodo = st.radio(
            "Sistema de normas",
            list(ch.METODOS),
            format_func=lambda chave: ch.METODOS[chave],
            key=PREFIXO + "metodo",
            persist_state="session",
            horizontal=True,
            help=AJUDA["metodo"],
        )
        colunas = st.columns(3)
        p_tracao = _numero(
            "Força de tração P [kN]",
            "P_tracao",
            800.0,
            AJUDA["P_tracao"],
            passo=10.0,
            formato="%.1f",
            alvo=colunas[0],
        )
        p_compressao = _numero(
            "Força de compressão P [kN]",
            "P_compressao",
            800.0,
            AJUDA["P_compressao"],
            passo=10.0,
            formato="%.1f",
            alvo=colunas[1],
        )
        theta = _numero(
            "Ângulo θ com a vertical [°]",
            "theta",
            45.0,
            AJUDA["theta"],
            minimo=1.0,
            maximo=89.0,
            passo=1.0,
            formato="%.2f",
            alvo=colunas[2],
        )
        st.subheader("Força da barra a partir da horizontal", help=AJUDA["calc_P"])
        calc = st.columns(2)
        horizontal = _numero(
            "Força horizontal H [kN]",
            "H_horizontal",
            0.0,
            AJUDA["H_horizontal"],
            passo=10.0,
            formato="%.1f",
            alvo=calc[0],
        )
        if horizontal > 0 and 0.0 < theta < 90.0:
            calc[1].metric(
                "P = H / sen θ [kN]",
                reg_pt(horizontal / math.sin(math.radians(theta))),
                help=AJUDA["calc_P"],
            )
        else:
            calc[1].metric("P = H / sen θ [kN]", "—", help=AJUDA["calc_P"])
    return DadosForca(str(metodo), p_tracao, p_compressao, theta)


def reg_pt(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _perfil(papel: str, titulo: str) -> ch.PerfilDoNo:
    nome_padrao, d, tw, tf, bf, k, zx, ix = PERFIS_PADRAO[papel]
    st.markdown(f"**{titulo}**")
    origem = st.radio(
        "Origem das medidas",
        [ORIGEM_DIGITAR, ORIGEM_CATALOGO],
        key=f"{PREFIXO}{papel}_origem",
        persist_state="session",
        horizontal=True,
        help=AJUDA["perfil_origem"],
    )
    aco = _selecao(
        "Aço do perfil",
        f"{papel}_aco",
        list(lig.ACOS),
        AJUDA["aco_perfil"],
        padrao=ACO_PADRAO_PERFIL,
    )
    fy, fu = lig.ACOS[aco]
    if origem == ORIGEM_CATALOGO:
        catalogo = sc.listar_perfis()
        nomes = [n for n, p in catalogo.items() if ss.familia_do_perfil(p) in ("i", "w", "hp")]
        escolhido = _selecao(
            "Perfil do catálogo", f"{papel}_catalogo", nomes, AJUDA["perfil_catalogo"]
        )
        perfil = catalogo[escolhido]
        k_mm = _numero(
            "Distância k [mm]",
            f"{papel}_k_cat",
            perfil.espessura_mesa_mm + 6.0,
            AJUDA["k"],
            minimo=1.0,
            passo=1.0,
            formato="%.1f",
        )
        st.caption(
            f"Seção idealizada: d = {reg_pt(perfil.altura_mm, 0)} mm, t_w = "
            f"{reg_pt(perfil.espessura_alma_mm)} mm, t_f = {reg_pt(perfil.espessura_mesa_mm)} mm, "
            f"b_f = {reg_pt(perfil.largura_mm, 0)} mm."
        )
        return ch.PerfilDoNo(
            escolhido,
            perfil.altura_mm,
            perfil.espessura_alma_mm,
            perfil.espessura_mesa_mm,
            perfil.largura_mm,
            k_mm,
            fy,
            perfil.zx_mm3,
            perfil.ix_mm4,
            fu,
        )
    nome = st.text_input(
        "Nome do perfil",
        value=nome_padrao,
        key=f"{PREFIXO}{papel}_nome",
        persist_state="session",
        help=AJUDA["perfil_nome"],
    )
    linha1 = st.columns(4)
    linha2 = st.columns(3)
    medidas = {
        "d": _numero("d [mm]", f"{papel}_d", d, AJUDA["d"], minimo=1.0, alvo=linha1[0]),
        "tw": _numero(
            "t_w [mm]", f"{papel}_tw", tw, AJUDA["tw"], minimo=0.1, formato="%.2f", alvo=linha1[1]
        ),
        "tf": _numero(
            "t_f [mm]", f"{papel}_tf", tf, AJUDA["tf"], minimo=0.1, formato="%.2f", alvo=linha1[2]
        ),
        "bf": _numero("b_f [mm]", f"{papel}_bf", bf, AJUDA["bf"], minimo=1.0, alvo=linha1[3]),
        "k": _numero(
            "k [mm]", f"{papel}_k", k, AJUDA["k"], minimo=1.0, formato="%.1f", alvo=linha2[0]
        ),
        "Zx": _numero(
            "Z_x [cm³]", f"{papel}_Zx", zx, AJUDA["Zx"], minimo=1.0, formato="%.0f", alvo=linha2[1]
        ),
        "Ix": _numero(
            "I_x [cm⁴]", f"{papel}_Ix", ix, AJUDA["Ix"], minimo=1.0, formato="%.0f", alvo=linha2[2]
        ),
    }
    return ch.PerfilDoNo(
        nome.strip() or titulo,
        medidas["d"],
        medidas["tw"],
        medidas["tf"],
        medidas["bf"],
        medidas["k"],
        fy,
        medidas["Zx"] * 1.0e3,
        medidas["Ix"] * 1.0e4,
        fu,
    )


def formulario_perfis() -> tuple[ch.PerfilDoNo, ch.PerfilDoNo, bool]:
    with st.container(border=True):
        st.subheader("3. Viga e coluna", help=AJUDA["sec_3"])
        esquerda, direita = st.columns(2)
        with esquerda:
            viga = _perfil("viga", "Viga")
        with direita:
            coluna = _perfil("coluna", "Coluna")
        na_mesa = st.toggle(
            "Chapa soldada na mesa da coluna",
            value=True,
            key=PREFIXO + "mesa_coluna",
            persist_state="session",
            help=AJUDA["mesa_coluna"],
        )
    return viga, coluna, bool(na_mesa)


@dataclass(frozen=True)
class DadosUFM:
    caso: str
    ajuste: str
    reacao_viga: float
    transferencia: float
    x: float
    y: float
    delta_Vb: float
    anular_Vb: bool


def formulario_ufm() -> DadosUFM:
    with st.container(border=True):
        st.subheader("4. Forças nas interfaces (UFM)", help=AJUDA["sec_4"])
        colunas = st.columns(2)
        caso = _selecao(
            "Caso do método",
            "caso",
            list(ufm.CASOS),
            AJUDA["caso"],
            formatar=lambda chave: ufm.CASOS[chave],
            alvo=colunas[0],
        )
        ajuste = ufm.AJUSTE_BETA
        if caso != ufm.CASO_3:
            ajuste = _selecao(
                "O que o programa ajusta",
                "ajuste",
                list(ufm.AJUSTES),
                AJUDA["ajuste"],
                formatar=lambda chave: ufm.AJUSTES[chave],
                alvo=colunas[1],
            )
        linha = st.columns(2)
        reacao = _numero(
            "Reação da viga no nó [kN]",
            "reacao_viga",
            0.0,
            AJUDA["reacao_viga"],
            minimo=-1.0e6,
            passo=5.0,
            formato="%.1f",
            alvo=linha[0],
        )
        transferencia = _numero(
            "Força axial da viga no nó [kN]",
            "transferencia",
            0.0,
            AJUDA["transferencia"],
            minimo=-1.0e6,
            passo=5.0,
            formato="%.1f",
            alvo=linha[1],
        )
        x = y = delta = 0.0
        anular = False
        if caso == ufm.CASO_1:
            especial = st.columns(2)
            x = _numero(
                "x do ponto de trabalho [mm]",
                "x_mm",
                0.0,
                AJUDA["x_mm"],
                minimo=-1.0e5,
                passo=5.0,
                formato="%.1f",
                alvo=especial[0],
            )
            y = _numero(
                "y do ponto de trabalho [mm]",
                "y_mm",
                0.0,
                AJUDA["y_mm"],
                minimo=-1.0e5,
                passo=5.0,
                formato="%.1f",
                alvo=especial[1],
            )
        elif caso == ufm.CASO_2:
            especial = st.columns(2)
            anular = bool(
                especial[0].toggle(
                    "Passar toda a vertical da viga à chapa",
                    key=PREFIXO + "anular_Vb",
                    persist_state="session",
                    help=AJUDA["anular_Vb"],
                )
            )
            if not anular:
                delta = _numero(
                    "Cisalhamento retirado da viga–coluna [kN]",
                    "delta_Vb",
                    0.0,
                    AJUDA["delta_Vb"],
                    passo=5.0,
                    formato="%.1f",
                    alvo=especial[1],
                )
    return DadosUFM(caso, ajuste, reacao, transferencia, x, y, delta, anular)


@dataclass(frozen=True)
class DadosChapa:
    aco: str
    t: float
    lh: float
    corte_h: float
    lv: float
    corte_v: float
    t_topo: float


def formulario_chapa(caso: str) -> DadosChapa:
    with st.container(border=True):
        st.subheader("5. Chapa de nó", help=AJUDA["sec_5"])
        linha1 = st.columns(3)
        aco = _selecao(
            "Aço da chapa",
            "aco_chapa",
            list(lig.ACOS),
            AJUDA["aco_chapa"],
            padrao=ACO_PADRAO_CHAPA,
            alvo=linha1[0],
        )
        t = _numero(
            "Espessura t [mm]",
            "t_chapa",
            25.0,
            AJUDA["t_chapa"],
            minimo=1.0,
            formato="%.1f",
            alvo=linha1[1],
        )
        t_topo = _numero(
            "Chapa de topo da viga [mm]",
            "t_topo",
            0.0,
            AJUDA["t_topo"],
            passo=1.0,
            formato="%.1f",
            alvo=linha1[2],
        )
        linha2 = st.columns(2)
        lh = _numero(
            "Comprimento na viga l_h [mm]",
            "lh",
            800.0,
            AJUDA["lh"],
            minimo=1.0,
            passo=10.0,
            formato="%.0f",
            alvo=linha2[0],
        )
        corte_h = _numero(
            "Corte horizontal [mm]",
            "corte_h",
            20.0,
            AJUDA["corte_h"],
            passo=1.0,
            formato="%.1f",
            alvo=linha2[1],
        )
        lv = 600.0
        corte_v = 0.0
        if caso != ufm.CASO_3:
            linha3 = st.columns(2)
            lv = _numero(
                "Comprimento na coluna l_v [mm]",
                "lv",
                600.0,
                AJUDA["lv"],
                minimo=1.0,
                passo=10.0,
                formato="%.0f",
                alvo=linha3[0],
            )
            corte_v = _numero(
                "Corte vertical [mm]",
                "corte_v",
                20.0,
                AJUDA["corte_v"],
                passo=1.0,
                formato="%.1f",
                alvo=linha3[1],
            )
    return DadosChapa(aco, t, lh, corte_h, lv, corte_v, t_topo)


@dataclass(frozen=True)
class DadosParafusos:
    designacao: str
    grau: str
    rosca: bool
    planos: int
    fileiras: int
    por_fileira: int
    passo: float
    gabarito: float
    extremidade: float
    t_barra: float
    Fu_barra: float
    extremidade_barra: float


def formulario_parafusos() -> DadosParafusos:
    with st.container(border=True):
        st.subheader("6. Parafusos do contraventamento", help=AJUDA["sec_6"])
        linha1 = st.columns(4)
        designacao = _selecao(
            "Parafuso",
            "parafuso",
            list(bc.PARAFUSOS),
            AJUDA["parafuso"],
            padrao='7/8"',
            alvo=linha1[0],
        )
        grau = _selecao("Grau", "grau", list(lig.GRAUS_DE_PARAFUSO), AJUDA["grau"], alvo=linha1[1])
        planos = int(
            linha1[2].radio(
                "Planos de corte",
                [1, 2],
                index=1,
                key=PREFIXO + "planos",
                persist_state="session",
                horizontal=True,
                help=AJUDA["planos"],
            )
        )
        rosca = bool(
            linha1[3].toggle(
                "Rosca no plano de corte",
                key=PREFIXO + "rosca",
                persist_state="session",
                help=AJUDA["rosca"],
            )
        )
        linha2 = st.columns(5)
        fileiras = _inteiro(
            "Fileiras", "fileiras", 2, AJUDA["fileiras"], minimo=1, maximo=6, alvo=linha2[0]
        )
        por_fileira = _inteiro(
            "Parafusos por fileira",
            "por_fileira",
            5,
            AJUDA["por_fileira"],
            minimo=1,
            maximo=30,
            alvo=linha2[1],
        )
        passo = _numero(
            "Passo [mm]",
            "passo",
            75.0,
            AJUDA["passo"],
            minimo=1.0,
            passo=5.0,
            formato="%.0f",
            alvo=linha2[2],
        )
        gabarito = _numero(
            "Gabarito [mm]",
            "gabarito",
            75.0,
            AJUDA["gabarito"],
            minimo=1.0,
            passo=5.0,
            formato="%.0f",
            alvo=linha2[3],
        )
        extremidade = _numero(
            "Extremidade [mm]",
            "extremidade",
            38.0,
            AJUDA["extremidade"],
            minimo=1.0,
            passo=1.0,
            formato="%.0f",
            alvo=linha2[4],
        )
        linha3 = st.columns(3)
        t_barra = _numero(
            "Espessura da barra [mm]",
            "t_barra",
            0.0,
            AJUDA["t_barra"],
            passo=1.0,
            formato="%.1f",
            alvo=linha3[0],
        )
        fu_barra = _numero(
            "F_u da barra [MPa]",
            "Fu_barra",
            0.0,
            AJUDA["Fu_barra"],
            passo=10.0,
            formato="%.0f",
            alvo=linha3[1],
        )
        ext_barra = _numero(
            "Extremidade na barra [mm]",
            "extremidade_barra",
            0.0,
            AJUDA["extremidade_barra"],
            passo=1.0,
            formato="%.0f",
            alvo=linha3[2],
        )
    return DadosParafusos(
        designacao,
        grau,
        rosca,
        planos,
        fileiras,
        por_fileira,
        passo,
        gabarito,
        extremidade,
        t_barra,
        fu_barra,
        ext_barra,
    )


@dataclass(frozen=True)
class DadosWhitmore:
    comprimento: float
    K: float
    trecho_alma: float


def formulario_whitmore() -> DadosWhitmore:
    with st.container(border=True):
        st.subheader("7. Whitmore e flambagem da chapa", help=AJUDA["sec_7"])
        colunas = st.columns(3)
        comprimento = _numero(
            "Comprimento livre da chapa [mm]",
            "L_flamb",
            0.0,
            AJUDA["L_flamb"],
            passo=5.0,
            formato="%.0f",
            alvo=colunas[0],
        )
        k = _numero(
            "K da flambagem",
            "K_flamb",
            0.5,
            AJUDA["K_flamb"],
            minimo=0.1,
            maximo=2.5,
            passo=0.05,
            formato="%.2f",
            alvo=colunas[1],
        )
        trecho = _numero(
            "Trecho de Whitmore na alma [mm]",
            "trecho_alma",
            0.0,
            AJUDA["trecho_alma"],
            passo=5.0,
            formato="%.0f",
            alvo=colunas[2],
        )
    return DadosWhitmore(comprimento, k, trecho)


@dataclass(frozen=True)
class DadosSolda:
    FEXX: float
    perna_viga: float
    perna_coluna: float
    ductilidade: float


def formulario_solda() -> DadosSolda:
    with st.container(border=True):
        st.subheader("8. Soldas da chapa", help=AJUDA["sec_8"])
        colunas = st.columns(4)
        fexx = _numero(
            "F_EXX do eletrodo [MPa]",
            "FEXX",
            ch.ELETRODO_E70_MPA,
            AJUDA["FEXX"],
            minimo=100.0,
            passo=10.0,
            formato="%.1f",
            alvo=colunas[0],
        )
        perna_v = _numero(
            "Perna na viga [mm]",
            "perna_viga",
            10.0,
            AJUDA["perna_viga"],
            minimo=1.0,
            passo=1.0,
            formato="%.1f",
            alvo=colunas[1],
        )
        perna_c = _numero(
            "Perna na coluna [mm]",
            "perna_coluna",
            10.0,
            AJUDA["perna_coluna"],
            minimo=1.0,
            passo=1.0,
            formato="%.1f",
            alvo=colunas[2],
        )
        duct = _numero(
            "Fator de ductilidade",
            "ductilidade",
            ch.FATOR_DE_DUCTILIDADE_DA_SOLDA,
            AJUDA["ductilidade"],
            minimo=1.0,
            maximo=2.0,
            passo=0.05,
            formato="%.2f",
            alvo=colunas[3],
        )
    return DadosSolda(fexx, perna_v, perna_c, duct)


@dataclass(frozen=True)
class DadosDistorcao:
    considerar: bool
    area: float
    b: float
    c: float


def formulario_distorcao(caso: str) -> DadosDistorcao:
    with st.container(border=True):
        st.subheader("9. Distorção do pórtico (opcional)", help=AJUDA["sec_9"])
        considerar = bool(
            st.toggle(
                "Considerar as forças de distorção",
                key=PREFIXO + "distorcao",
                persist_state="session",
                help=AJUDA["distorcao"],
            )
        )
        area = b = c = 0.0
        if considerar:
            if caso == ufm.CASO_3:
                st.info("No caso especial 3 não há ligação à coluna: a distorção não se aplica.")
            colunas = st.columns(3)
            area = _numero(
                "Área do contraventamento [mm²]",
                "area_barra",
                5000.0,
                AJUDA["area_barra"],
                minimo=1.0,
                passo=100.0,
                formato="%.0f",
                alvo=colunas[0],
            )
            b = _numero(
                "b da viga [mm]",
                "b_viga",
                4000.0,
                AJUDA["b_viga"],
                minimo=1.0,
                passo=100.0,
                formato="%.0f",
                alvo=colunas[1],
            )
            c = _numero(
                "c da coluna [mm]",
                "c_coluna",
                2000.0,
                AJUDA["c_coluna"],
                minimo=1.0,
                passo=100.0,
                formato="%.0f",
                alvo=colunas[2],
            )
    return DadosDistorcao(considerar, area, b, c)


def montar_entrada(
    forca: DadosForca,
    viga: ch.PerfilDoNo,
    coluna: ch.PerfilDoNo,
    na_mesa: bool,
    ufm_: DadosUFM,
    chapa: DadosChapa,
    parafusos: DadosParafusos,
    whitmore: DadosWhitmore,
    solda: DadosSolda,
    distorcao: DadosDistorcao,
) -> lig.EntradaLigacao:
    fy_chapa, fu_chapa = lig.ACOS[chapa.aco]
    return lig.EntradaLigacao(
        perfil_viga=viga,
        perfil_coluna=coluna,
        metodo=forca.metodo,
        P_tracao_kN=forca.P_tracao,
        P_compressao_kN=forca.P_compressao,
        theta_graus=forca.theta,
        caso=ufm_.caso,
        ajuste=ufm_.ajuste,
        ligacao_na_mesa_da_coluna=na_mesa,
        reacao_viga_kN=ufm_.reacao_viga,
        transferencia_kN=ufm_.transferencia,
        x_mm=ufm_.x,
        y_mm=ufm_.y,
        delta_Vb_kN=ufm_.delta_Vb,
        anular_Vb=ufm_.anular_Vb,
        t_chapa_mm=chapa.t,
        Fy_chapa_MPa=fy_chapa,
        Fu_chapa_MPa=fu_chapa,
        lh_mm=chapa.lh,
        corte_h_mm=chapa.corte_h,
        lv_mm=chapa.lv,
        corte_v_mm=chapa.corte_v,
        t_chapa_de_topo_mm=chapa.t_topo,
        designacao_do_parafuso=parafusos.designacao,
        grau_do_parafuso=parafusos.grau,
        rosca_no_plano=parafusos.rosca,
        planos_de_corte=parafusos.planos,
        fileiras=parafusos.fileiras,
        por_fileira=parafusos.por_fileira,
        passo_mm=parafusos.passo,
        gabarito_mm=parafusos.gabarito,
        extremidade_mm=parafusos.extremidade,
        t_barra_mm=parafusos.t_barra,
        Fu_barra_MPa=parafusos.Fu_barra,
        extremidade_barra_mm=parafusos.extremidade_barra,
        comprimento_de_flambagem_mm=whitmore.comprimento,
        K_flambagem=whitmore.K,
        trecho_whitmore_na_alma_mm=whitmore.trecho_alma,
        FEXX_MPa=solda.FEXX,
        perna_na_viga_mm=solda.perna_viga,
        perna_na_coluna_mm=solda.perna_coluna,
        fator_de_ductilidade=solda.ductilidade,
        considerar_distorcao=distorcao.considerar and ufm_.caso != ufm.CASO_3,
        area_do_contraventamento_mm2=distorcao.area,
        b_viga_mm=distorcao.b,
        c_coluna_mm=distorcao.c,
    )


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------
def _resumo(r: lig.ResultadoLigacao) -> None:
    geral = status_geral(list(r.verificacoes))
    contagem = {s: 0 for s in ("OK", "NÃO OK", "ALERTA", "INFO", "N/A")}
    for v in r.verificacoes:
        contagem[v.status] = contagem.get(v.status, 0) + 1
    colunas = st.columns(4)
    colunas[0].metric("Status geral", geral, help=AJUDA["res_status"])
    colunas[1].metric(
        "Aproveitamento máximo",
        f"{100 * r.aproveitamento_maximo:.0f} %",
        help=AJUDA["res_aproveitamento"],
    )
    colunas[2].metric(
        "α̅ ideal / β̅ ideal [mm]",
        f"{reg_pt(r.forcas.alfa_ideal_mm, 0)} / {reg_pt(r.forcas.beta_ideal_mm, 0)}",
        help=AJUDA["res_geometria"],
    )
    colunas[3].metric(
        "Parafusos (mínimo necessário)",
        f"{r.entrada.fileiras * r.entrada.por_fileira} ({math.ceil(r.numero_minimo_de_parafusos - 1e-9)})",
        help=AJUDA["res_geometria"],
    )
    st.caption(" · ".join(f"{contagem[s]} {s}" for s in ("OK", "NÃO OK", "ALERTA", "INFO", "N/A")))
    for aviso in r.avisos:
        st.warning(aviso, icon=":material/warning:")


def _aba_verificacoes(r: lig.ResultadoLigacao) -> None:
    st.subheader(f"As {len(r.verificacoes)} verificações", help=AJUDA["res_verificacoes"])
    so_atencao = st.toggle(
        "Mostrar só o que merece atenção (NÃO OK, ALERTA e N/A)",
        key=PREFIXO + "so_atencao",
        persist_state="session",
        help=AJUDA["so_atencao"],
    )
    linhas = [
        v for v in r.verificacoes if not so_atencao or v.status in ("NÃO OK", "ALERTA", "N/A")
    ]
    mostrar_tabela_verificacoes(linhas)
    st.subheader("Exportar", help=AJUDA["res_exportar"])
    st.download_button(
        "Verificações em CSV",
        data=csv_verificacoes(list(r.verificacoes)),
        file_name="ligacao_contraventamento_verificacoes.csv",
        mime="text/csv",
        icon=":material/download:",
        key=PREFIXO + "baixar_csv",
        help=AJUDA["btn_csv"],
    )


def _aba_forcas(r: lig.ResultadoLigacao) -> None:
    st.subheader("Forças em cada interface", help=AJUDA["res_forcas"])
    tabelas = reg.tabelas_para_memorial(r)
    forcas = tabelas[0]
    st.dataframe(
        pd.DataFrame(forcas["linhas"], columns=forcas["cabecalhos"]),
        hide_index=True,
        width="stretch",
    )
    st.caption(forcas["legenda"])
    st.subheader("Geometria do nó", help=AJUDA["res_geometria"])
    geometria = tabelas[1]
    st.dataframe(
        pd.DataFrame(geometria["linhas"], columns=geometria["cabecalhos"]),
        hide_index=True,
        width="stretch",
    )


def _registrar(r: lig.ResultadoLigacao, ident: Identificacao) -> None:
    contexto: dict[str, Any] = {"data_do_calculo": ident.data.isoformat()}
    if ident.obra:
        contexto["obra"] = ident.obra
    if ident.tag:
        contexto["tag"] = ident.tag
    registro = reg.registro_ligacao(r, contexto=contexto, responsavel=ident.responsavel)
    with st.container(border=True):
        st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
        botao_registrar_calculo(
            registro,
            key="registrar_ligacao_contraventamento",
            rotulo="Registrar a ligação no projeto ativo",
        )


def mostrar_ligacao_de_contraventamento() -> None:
    """Desenha a página: entradas, resultados e registro."""
    fronteira_modelo(list(reg.FORA_DO_ESCOPO), titulo="O que esta página não faz")
    ident = formulario_identificacao()
    forca = formulario_forca()
    viga, coluna, na_mesa = formulario_perfis()
    dados_ufm = formulario_ufm()
    chapa = formulario_chapa(dados_ufm.caso)
    parafusos = formulario_parafusos()
    whitmore = formulario_whitmore()
    solda = formulario_solda()
    distorcao = formulario_distorcao(dados_ufm.caso)
    entrada = montar_entrada(
        forca, viga, coluna, na_mesa, dados_ufm, chapa, parafusos, whitmore, solda, distorcao
    )
    erros = lig.validar_entrada(entrada)
    if erros:
        for erro in erros:
            st.error(erro, icon=":material/error:")
        st.stop()
    try:
        resultado = lig.calcular_ligacao(entrada)
    except (ufm.UFMInvalido, ch.ChapaInvalida) as erro:
        st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
        st.stop()
    st.header("Resultados")
    _resumo(resultado)
    aba_verificacoes, aba_forcas = st.tabs(["Verificações", "Forças e geometria"])
    with aba_verificacoes:
        _aba_verificacoes(resultado)
    with aba_forcas:
        _aba_forcas(resultado)
    st.subheader("Referências", help=AJUDA["res_avisos"])
    st.caption("\n".join(f"- {item}" for item in reg.REFERENCIAS))
    _registrar(resultado, ident)
