"""Página Modelo em 3D: o esqueleto do SolidWorks com o perfil real, as cargas, as reações, os
apoios e os resultados como cor. O desenho é o núcleo :mod:`core.cena_3d`; os dados vêm de
:mod:`core.cena_do_modelo`."""

from __future__ import annotations

from typing import Any

import streamlit as st

from components.base_tecnica_ui import base_ativa
from components.cena_3d_svg import svg_da_cena
from components.guarda_corpo_ui import escolha_inicial
from components.modelo_3d_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from core import cena_3d as c3
from core import cena_3d_png
from core import cena_do_modelo as cm
from core import cena_escada as cesc
from core import esforcos_modelo as em
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import vento_estrutura_aberta as va
from core import vento_por_barras as vpb

GRUPOS = (ld.TIPO_PILAR, ld.TIPO_VIGA, ld.TIPO_CONTRAVENTAMENTO)
CHAPAS = "Chapas de piso"
GUARDA_CORPOS = "Guarda-corpos (bordas)"
NOMES = "Nomes das barras"
OPCOES_DE_MOSTRAR = (*GRUPOS, CHAPAS, GUARDA_CORPOS, NOMES)
NENHUM = "—"
PERFIL_REAL = "Perfil real"
SO_EIXOS = "Só eixos"


def _pt(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _parametros_do_vento() -> va.ParametrosVento:
    base = base_ativa()
    if base is None:
        return va.ParametrosVento()
    v = base.vento
    try:
        s3 = v.s3
    except ValueError:
        s3 = None
    grupo = int(v.grupo_s3) if str(v.grupo_s3).isdigit() else 3
    return va.ParametrosVento(
        v0_m_s=v.v0_m_s,
        s1=v.s1,
        categoria=v.categoria,
        grupo_s3=grupo,
        s3=None if str(v.grupo_s3).isdigit() else s3,
    )


def mostrar_modelo_3d(projeto: Any) -> None:
    geometria = ld.geometria_do_projeto(projeto)
    if not geometria.corpos:
        st.info(
            "O projeto ainda não tem o esqueleto do modelo. Rode a macro do SolidWorks e envie o "
            "…_esqueleto.csv em **Cargas do esqueleto**: aqui aparece o modelo em 3D.",
            icon=":material/account_tree:",
        )
        st.page_link(
            "app_pages/cargas_esqueleto.py",
            label="Abrir Cargas do esqueleto",
            icon=":material/account_tree:",
        )
        return
    dados = em.esforcos_do_projeto(projeto)
    eixo = dados.eixo_vertical if dados.eixo_vertical in ("Y", "Z") else "Y"
    plano = pc.plano_do_projeto(projeto)
    nomes = cm.Nomes.do_projeto(geometria, dados)
    corpos = cm._corpos(geometria)
    tipos = {
        nomes.corpo_do_elemento(membro, corpos): cfg.tipo
        for membro, cfg in dados.membros.items()
        if cfg.tipo and cfg.tipo != "—"
    }
    casos_importados = list(dados.casos)

    # ------------------------------------------------------------------ controles
    linha = st.columns([3, 2, 3, 2])
    vista = (
        linha[0].segmented_control(
            "Vista",
            list(c3.VISTAS),
            default=c3.VISTA_ISOMETRICA,
            key="m3_vista",
            help=AJUDA["vista"],
        )
        or c3.VISTA_ISOMETRICA
    )
    giro = linha[1].select_slider(
        "Girar (°)", options=list(range(-180, 181, 15)), value=0, key="m3_giro", help=AJUDA["giro"]
    )
    opcoes_de_cor = [cm.COR_POR_TIPO, cm.COR_POR_PERFIL, cm.COR_POR_VENTO]
    if casos_importados:
        opcoes_de_cor += [cm.COR_POR_NORMAL, cm.COR_POR_APROVEITAMENTO]
    opcoes_de_cor.append(cm.COR_UNICA)
    cor_por = linha[2].selectbox("Cor por", opcoes_de_cor, key="m3_cor", help=AJUDA["cor_por"])
    desenho = linha[3].segmented_control(
        "Desenho", [PERFIL_REAL, SO_EIXOS], default=PERFIL_REAL, key="m3_desenho",
        help=AJUDA["desenho"],
    ) or PERFIL_REAL  # fmt: skip
    linha = st.columns([4, 2, 2, 2])
    mostrar = linha[0].multiselect(
        "Mostrar",
        list(OPCOES_DE_MOSTRAR),
        default=[*GRUPOS, CHAPAS, GUARDA_CORPOS],
        key="m3_mostrar",
        help=AJUDA["mostrar"],
    )
    caso_das_cargas = linha[1].selectbox(
        "Cargas do caso", [NENHUM, *plano.codigos], key="m3_cargas", help=AJUDA["cargas"]
    )
    reacoes = linha[2].toggle("Apoios e reações", value=True, key="m3_reacoes",
                              help=AJUDA["reacoes"])  # fmt: skip
    caso_das_reacoes = ""
    if reacoes and casos_importados:
        caso_das_reacoes = linha[3].selectbox(
            "Caso das reações", casos_importados, key="m3_caso_reacoes", help=AJUDA["caso_reacoes"]
        )
    linha = st.columns([3, 3])
    barra = linha[0].selectbox(
        "Barra selecionada", [NENHUM, *sorted(corpos)], key="m3_barra", help=AJUDA["barra"]
    )
    modo_escada = (
        linha[1].segmented_control(
            "Escadas e guarda-corpos",
            list(cesc.MODOS),
            default=cesc.MODO_DETALHADO,
            key="m3_modo",
            help=AJUDA["modo_escada"],
        )
        or cesc.MODO_DETALHADO
    )

    # ------------------------------------------------------------------ dados para a cor
    avisos: list[str] = []
    valores = None
    if cor_por == cm.COR_POR_VENTO:
        angulo = st.selectbox(
            "Vento", list(vpb.DIRECOES_COM_DIAGONAIS), format_func=lambda a: f"W{a} ({vpb.SENTIDOS[a]})",
            key="m3_vento", help=AJUDA["direcao_vento"],
        )  # fmt: skip
        try:
            valores = cm.valores_do_vento(geometria, eixo, _parametros_do_vento(), int(angulo))
        except (ValueError, ArithmeticError) as erro:
            avisos.append(f"O vento não foi calculado ({erro}).")
    elif cor_por == cm.COR_POR_NORMAL:
        caso = st.selectbox("Caso do esforço normal", casos_importados, key="m3_caso_n",
                            help=AJUDA["caso_normal"])  # fmt: skip
        valores = cm.valores_do_normal(dados, str(caso), nomes)
    elif cor_por == cm.COR_POR_APROVEITAMENTO:
        valores, avisos_verificacao = cm.valores_do_aproveitamento(dados, plano, nomes)
        avisos.extend(avisos_verificacao[:3])
    rotulos: dict[str, str] = {}
    if NOMES in mostrar:
        rotulos = {nome: nome.split(" - ")[-1] for nome in corpos}
    if valores is not None and barra != NENHUM and barra in valores.valores:
        rotulos[barra] = (
            f"{barra.split(' - ')[-1]}: {_pt(valores.valores[barra], 3)} {valores.unidade}"
        )
    elif barra != NENHUM:
        rotulos[barra] = barra.split(" - ")[-1]

    # ------------------------------------------------------------------ cena
    with secao_protegida("Modelo em 3D"):
        barras, legenda, escala = cm.barras_da_cena(
            geometria,
            eixo,
            cor_por=cor_por,
            valores=valores,
            tipos=tipos,
            ocultos=[g for g in GRUPOS if g not in mostrar],
            destaque="" if barra == NENHUM else str(barra),
            rotulos=rotulos,
        )
        paineis = []
        if CHAPAS in mostrar:
            degraus, paineis = cm.chapas_da_cena(geometria, eixo, str(modo_escada))
            barras += degraus
        if GUARDA_CORPOS in mostrar:
            escolha = escolha_inicial(projeto)
            bordas = gm.bordas_do_projeto(geometria, eixo, escolha)
            gc_barras, gc_paineis = cm.guarda_corpos_da_cena(
                bordas.marcados(escolha.trocados), eixo, escolha.altura_m, str(modo_escada)
            )
            barras += gc_barras
            paineis += gc_paineis
        cargas = cm.CargasNaCena((), (), (), (0.0, 0.0, 0.0))
        if caso_das_cargas != NENHUM:
            cargas = cm.cargas_do_caso(plano, str(caso_das_cargas), geometria, eixo, nomes)
        apoios = cm.ApoiosNaCena((), (), ())
        if reacoes:
            apoios = cm.apoios_e_reacoes(geometria, eixo, dados, nomes, caso_das_reacoes)
            avisos.extend(apoios.avisos)
        titulo = "Modelo em 3D"
        if caso_das_cargas != NENHUM:
            titulo += f" — cargas do caso {caso_das_cargas}"
        cena = c3.Cena(
            barras=tuple(barras),
            paineis=tuple(paineis),
            setas=(*cargas.setas, *apoios.reacoes),
            distribuidas=cargas.distribuidas,
            apoios=apoios.apoios,
            titulo=titulo,
            subtitulo=(
                f"{geometria.arquivo or 'esqueleto do modelo'} · {len(corpos)} barras · "
                f"vista {str(vista).lower()}"
                + (f", girada {giro}°" if giro else "")
                + (f" · reações do {caso_das_reacoes}" if apoios.reacoes else "")
            ),
            legenda=tuple(legenda),
            escala=escala,
            eixo_vertical_do_modelo=eixo,
        )
        azimute, elevacao = c3.VISTAS[str(vista)]
        resultado = c3.projetar(
            cena,
            azimute=azimute + float(giro),
            elevacao=elevacao,
            perfil_real=desenho == PERFIL_REAL,
        )
        colunas = st.columns([3, 1])
        colunas[0].image(svg_da_cena(resultado), width="stretch")
        with colunas[1]:
            _painel_lateral(barra, corpos, nomes, tipos, valores, eixo)
            if caso_das_cargas != NENHUM:
                st.metric("Cargas desenhadas (vertical)", f"{_pt(-cargas.total_kN[2], 2)} kN",
                          help=AJUDA["res_cargas"])  # fmt: skip
                if cargas.nao_localizadas:
                    st.caption(
                        f"{len(cargas.nao_localizadas)} linha(s) sem barra no esqueleto: "
                        + "; ".join(cargas.nao_localizadas[:4])
                        + ("…" if len(cargas.nao_localizadas) > 4 else ""),
                        help=AJUDA["res_fora"],
                    )
            if apoios.reacoes:
                st.metric("Reações verticais", f"{_pt(apoios.soma_vertical_kN, 2)} kN",
                          help=AJUDA["res_reacoes"])  # fmt: skip
            st.download_button(
                "Baixar a imagem (PNG)",
                data=cena_3d_png.png_da_cena(resultado),
                file_name="modelo_3d.png",
                mime="image/png",
                icon=":material/download:",
                key="m3_png",
                help=AJUDA["btn_png"],
                width="stretch",
            )
            descricao = (
                f"vista {str(vista).lower()}"
                + (f" girada {giro}°" if giro else "")
                + f", cor por {str(cor_por).lower()}, {str(modo_escada).lower()}"
                + (f", cargas do {caso_das_cargas}" if caso_das_cargas != NENHUM else "")
                + (f", reações do {caso_das_reacoes}" if apoios.reacoes else "")
            )
            registro = cm.registro_da_vista(
                cena,
                azimute=azimute + float(giro),
                elevacao=elevacao,
                perfil_real=desenho == PERFIL_REAL,
                descricao=descricao,
            )
            botao_registrar_calculo(
                registro, key="registrar_modelo_3d", rotulo="Registrar a vista no memorial"
            )
    for aviso in dict.fromkeys([*resultado.avisos, *avisos]):
        st.caption(f":material/info: {aviso}")


def _painel_lateral(
    barra: str,
    corpos: dict[str, ld.CorpoDoModelo],
    nomes: cm.Nomes,
    tipos: dict[str, str],
    valores: cm.ValoresPorBarra | None,
    eixo: str,
) -> None:
    if barra == NENHUM or barra not in corpos:
        st.caption(":material/touch_app: Escolha uma barra acima para ver os dados dela.")
        return
    corpo = corpos[barra]
    perfis = ld.perfis_do_esqueleto(ld.GeometriaDoModelo(corpos=(corpo,)))
    st.markdown(f"**{barra}**")
    linhas = [
        ("No Simulation", nomes.do_simulation.get(barra, "—")),
        ("Perfil", perfis.get(barra, ("", ""))[0] or corpo.descricao or "—"),
        ("Tipo", cm._tipo(corpo, eixo, tipos)),
        ("Comprimento", f"{_pt(corpo.comprimento_m, 2)} m"),
    ]
    if valores is not None and barra in valores.valores:
        valor = valores.valores[barra]
        texto = (
            f"{_pt(100 * valor, 0)} %"
            if valores.maximo_fixo == 1.0
            else f"{_pt(valor, 3)} {valores.unidade}"
        )
        linhas.append((valores.titulo.split(" (")[0].capitalize(), texto))
    st.markdown("\n".join(f"- {a}: **{b}**" for a, b in linhas))
