"""Estudo parcial dos critérios de enrijecedor da ligação 4ES."""

from __future__ import annotations

import streamlit as st

from components import robot_esforcos_ui as robot_ui
from components.cena_3d_svg import svg_da_cena
from components.figuras import mostrar_figura
from components.verification_table import mostrar_tabela_verificacoes
from core import bolted_connection as bc
from core import desenho_4es
from core import desenho_ligacao_rigida as desenho_frontal
from core import enrijecedor_4es as en
from core import ligacao_rigida as lr
from core import perfil_i as pi
from core.verificacao import csv_verificacoes


def mostrar() -> None:
    st.warning(
        "Estudo preliminar do enrijecedor: não dimensiona nem aprova a ligação 4ES. Faltam soldas, verificações adicionais dos parafusos e do pilar, geometria completa e demais estados-limites. Não estabelece pré-qualificação sísmica."
    )
    st.caption(
        "O enrijecedor da chapa de extremidade é distinto dos enrijecedores de continuidade do pilar."
    )
    st.subheader(
        "Viga e material",
        help="Escolha um perfil do catálogo e os aços para obter a espessura da alma e as resistências ao escoamento.",
    )
    a, b, c = st.columns(3)
    familia = a.selectbox(
        "Família da viga",
        [pi.FAMILIA_W, pi.FAMILIA_I],
        key="4es_familia",
        help="Família laminada do catálogo; a espessura da alma é obtida do perfil selecionado.",
    )
    opcoes = pi.nomes(familia)
    perfil = b.selectbox(
        "Perfil da viga",
        opcoes,
        key="4es_perfil_" + familia[:1],
        help="Perfil usado para definir a espessura da alma.",
    )
    aco_viga = c.selectbox(
        "Aço da viga",
        list(pi.ACOS),
        key="4es_aco_viga",
        help="A resistência ao escoamento da viga entra na espessura mínima do enrijecedor.",
    )
    v = pi.perfil(perfil)
    st.caption(f"Alma da viga: {pi.numero(v.tw, 2)} mm · f_y da viga: {pi.ACOS[aco_viga][0]:g} MPa")
    st.subheader(
        "Enrijecedor da chapa de extremidade",
        help="A altura é medida da face externa da mesa da viga até a borda da chapa de extremidade, conforme AISC 358-16 6.8-10.",
    )
    a, b = st.columns(2)
    aco = a.selectbox(
        "Aço do enrijecedor",
        list(pi.ACOS),
        key="4es_aco",
        help="Material da chapa de enrijecimento da extremidade.",
    )
    esp = b.number_input(
        "Espessura do enrijecedor (mm)",
        min_value=0.1,
        value=12.5,
        step=0.5,
        key="4es_esp",
        help="Espessura real do enrijecedor.",
    )
    st.subheader(
        "Chapa de extremidade",
        help="Verificação parcial de plastificação da chapa 4ES pela AISC 358-22, Tabela 6.3, usando o fator LRFD 0,90.",
    )
    robot_ui.ligacao("lr_4es_robot", {"4es_m": "m"})
    a, b, c, d = st.columns(4)
    bp = a.number_input(
        "Largura da chapa b_p (mm)",
        min_value=1.0,
        value=200.0,
        key="4es_bp",
        help="Largura total da chapa de extremidade.",
    )
    tp = b.number_input(
        "Espessura da chapa t_p (mm)",
        min_value=1.0,
        value=25.0,
        key="4es_tp",
        help="Espessura adotada da chapa de extremidade.",
    )
    aco_chapa = c.selectbox(
        "Aço da chapa", list(pi.ACOS), key="4es_aco_chapa", help="Aço da chapa de extremidade."
    )
    momento = d.number_input(
        "Momento de cálculo (kN·m)",
        min_value=0.1,
        value=100.0,
        key="4es_m",
        help="Momento solicitante de cálculo na seção da ligação.",
    )
    a, b, c, d = st.columns(4)
    g = a.number_input(
        "Gabarito g (mm)",
        min_value=1.0,
        value=100.0,
        key="4es_g",
        help="Distância transversal entre colunas dos parafusos.",
    )
    pfo = b.number_input(
        "Distância externa p_fo (mm)",
        min_value=1.0,
        value=45.0,
        key="4es_pfo",
        help="Da face externa da mesa tracionada à fileira externa.",
    )
    pfi = c.number_input(
        "Distância interna p_fi (mm)",
        min_value=1.0,
        value=45.0,
        key="4es_pfi",
        help="Da face interna da mesa tracionada à fileira interna.",
    )
    borda = d.number_input(
        "Borda externa d_e (mm)",
        min_value=1.0,
        value=40.0,
        key="4es_de",
        help="Da fileira externa de parafusos à borda da chapa.",
    )
    st.subheader(
        "Pilar sem reforço",
        help="Verificações locais da mesa e da alma do pilar pela NBR no caso de viga de um lado, sem enrijecedores de continuidade.",
    )
    a, b, c, d = st.columns(4)
    familia_pilar = a.selectbox(
        "Família do pilar",
        [pi.FAMILIA_W, pi.FAMILIA_I],
        key="4es_familia_pilar",
        help="Família laminada do pilar.",
    )
    perfis_pilar = pi.nomes(familia_pilar)
    pilar = b.selectbox(
        "Perfil do pilar",
        perfis_pilar,
        index=perfis_pilar.index("HP 310 x 79,0 (H)") if "HP 310 x 79,0 (H)" in perfis_pilar else 0,
        key="4es_pilar_" + familia_pilar[:1],
        help="Perfil do pilar que recebe a chapa na mesa.",
    )
    aco_pilar = c.selectbox(
        "Aço do pilar", list(pi.ACOS), key="4es_aco_pilar", help="Aço do perfil do pilar."
    )
    normal_pilar = d.number_input(
        "Normal no pilar (kN)",
        value=0.0,
        step=10.0,
        key="4es_np",
        help="Força normal de cálculo no pilar, compressão positiva.",
    )
    cortante_pilar = st.number_input(
        "Cortante no pilar (kN)",
        value=0.0,
        step=5.0,
        key="4es_vp",
        help="Força cortante de cálculo no pilar usada no painel de alma.",
    )
    borda_pilar = st.number_input(
        "Fileira comprimida externa → extremo do pilar (mm)",
        min_value=1.0,
        value=100.0,
        key="4es_borda_pilar",
        help="Distância real do centro do furo externo comprimido ao extremo do pilar na direção do cortante; não é a borda da chapa.",
    )
    st.caption(
        "Pilar: resistências pelo modelo NBR existente; chapa e parafusos: estudo AISC LRFD. Cada linha mantém sua referência."
    )
    st.subheader(
        "Parafusos",
        help="O corte considera quatro parafusos no lado comprimido, como na AISC 358; é necessário confirmar essa disposição no detalhamento.",
    )
    a, b, c, d = st.columns(4)
    diametro = a.selectbox(
        "Diâmetro do parafuso",
        list(bc.PARAFUSOS),
        index=list(bc.PARAFUSOS).index('3/4"'),
        key="4es_diametro",
        help="Diâmetro nominal do parafuso de alta resistência.",
    )
    grau = b.selectbox(
        "Grau do parafuso",
        ("A325", "A490"),
        key="4es_grau",
        help="Resistência nominal do parafuso conforme o modelo AISC LRFD.",
    )
    cortante = c.number_input(
        "Cortante de cálculo (kN)",
        min_value=0.0,
        value=40.0,
        key="4es_cortante",
        help="Força cortante de cálculo na ligação.",
    )
    rosca = d.toggle(
        "Rosca no plano de corte",
        value=True,
        key="4es_rosca",
        help="Determina a resistência ao corte dos parafusos comprimidos.",
    )
    st.subheader(
        "Soldas da viga",
        help="Verificação preliminar das soldas da viga na chapa; adota penetração total nas mesas e filetes na alma.",
    )
    a, b = st.columns(2)
    perna_alma = a.number_input(
        "Perna do filete da alma (mm)",
        min_value=1.0,
        value=8.0,
        step=0.5,
        key="4es_solda_alma",
        help="Perna dos filetes da alma da viga, um de cada lado.",
    )
    eletrodo = b.selectbox(
        "Eletrodo da alma",
        list(lr.ELETRODOS),
        key="4es_eletrodo",
        help="Consumível dos filetes da alma; a compatibilidade do consumível ainda requer verificação.",
    )
    altura = pfo + borda
    comprimento = st.number_input(
        "Comprimento do enrijecedor L_st (mm)",
        min_value=1.0,
        value=160.0,
        step=5.0,
        key="4es_comprimento",
        help="Comprimento do reforço ao longo da mesa, medido a partir da chapa de extremidade.",
    )
    st.caption(f"Altura do enrijecedor h_st = p_fo + d_e = {altura:g} mm")
    entrada = en.EntradaEnrijecedor(v.tw, pi.ACOS[aco_viga][0], pi.ACOS[aco][0], esp, altura)
    linhas = list(en.verificar(entrada))
    linhas.insert(0, en.verificar_comprimento(altura, comprimento))
    st.subheader(
        "Geometria do enrijecedor",
        help="Vista lateral local, desenhada com as medidas informadas; ainda não representa recortes, trechos planos e soldas.",
    )
    mostrar_figura(svg_da_cena(desenho_4es.vista_lateral(altura, comprimento, tp, v.tf)))
    try:
        dh = bc.dados_parafuso(diametro)["d_h"]
        if g <= max(v.tw, esp) + dh:
            raise ValueError(
                "Os furos devem ficar fora da alma da viga e do enrijecedor; aumente o gabarito."
            )
        if bp - g <= dh or min(pfo, pfi, borda) <= dh / 2:
            raise ValueError(
                "Os furos devem caber na chapa e ficar afastados das mesas e da borda."
            )
        if pi.perfil(pilar).bf - g <= dh:
            raise ValueError("Os furos não cabem na largura da mesa do pilar escolhido.")
        chapa = en.Chapa4ES(bp, g, pfo, pfi, borda, v.d, v.tf, tp, pi.ACOS[aco_chapa][0], momento)
        linhas.insert(0, en.verificar_chapa(chapa))
        linhas[1:1] = en.verificar_parafusos(chapa, diametro, grau, cortante, rosca)
        linhas.insert(
            1,
            en.verificar_contato_chapa_simetrica(chapa, diametro, pi.ACOS[aco_chapa][1], cortante),
        )
        caso_pilar = lr.EntradaRigida(
            viga=lr.PerfilEscolhido(familia, perfil),
            pilar=lr.PerfilEscolhido(familia_pilar, pilar),
            aco_viga=aco_viga,
            aco_pilar=aco_pilar,
            aco_chapa=aco_chapa,
            M=momento,
            V=cortante,
            N_pilar=normal_pilar,
            V_pilar=cortante_pilar,
            diametro=diametro,
            grau=grau,
            rosca_no_plano=rosca,
            bp=bp,
            tp=tp,
            g=g,
            pfo=pfo,
            pfi=pfi,
            de=borda,
            simetrica=True,
            solda_mesa=lr.PENETRACAO,
            perna_alma=perna_alma,
            eletrodo=eletrodo,
        )
        linhas.extend(en.verificar_pilar_sem_continuidade(caso_pilar))
        linhas.extend(en.verificar_soldas_viga(caso_pilar))
        perfil_pilar = pi.perfil(pilar)
        linhas.append(
            en.verificar_contato_pilar(
                chapa, diametro, perfil_pilar.tf, pi.ACOS[aco_pilar][1], borda_pilar, cortante
            )
        )
        frente = lr.EntradaRigida(
            viga=lr.PerfilEscolhido(familia, perfil),
            bp=bp,
            tp=tp,
            g=g,
            pfo=pfo,
            pfi=pfi,
            de=borda,
            diametro=diametro,
            simetrica=True,
        )
        st.caption(
            "Vista frontal da extensão tracionada; a parte comprimida e suas fileiras não estão detalhadas neste estudo."
        )
        mostrar_figura(svg_da_cena(desenho_frontal.vista_chapa(frente, esp_enrijecedor=esp)))
    except ValueError as erro:
        st.error(str(erro))
    st.subheader(
        "Critérios parciais",
        help="Plastificação da chapa em LRFD, espessura e esbeltez do enrijecedor; a linha de alerta identifica verificações não implementadas.",
    )
    mostrar_tabela_verificacoes(linhas)
    st.download_button(
        "Baixar critérios parciais (CSV)",
        csv_verificacoes(list(linhas)),
        "4es_preliminar.csv",
        "text/csv",
        key="4es_csv",
        help="Exporta as verificações parciais e o alerta de escopo.",
    )
