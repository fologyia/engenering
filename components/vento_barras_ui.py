"""Interface do vento barra a barra (viga a viga, pilar a pilar), dentro da página Vento em
estruturas abertas. O cálculo está em :mod:`core.vento_por_barras`; o registro, em
:mod:`core.vento_por_barras_registro`; os desenhos, em :mod:`components.figuras_vento`."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import streamlit as st

from components import contraventamento_estrutura_ui as ce
from components.base_tecnica_ui import base_ativa, gravar_plano, plano_ativo
from components.figuras_vento import svg_vento_3d, svg_vento_planta, svg_vento_sombra
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.vento_barras_help import AJUDA
from core import base_tecnica as bt
from core import esforcos_modelo as em
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import vento_por_barras as vpb
from core import vento_por_barras_registro as vbr
from core import vento_por_nivel as vpn
from core.project_store import obter_projeto_ativo

ORIGEM_ESQUELETO = "Esqueleto do modelo (macro do SolidWorks)"
ORIGEM_DIGITADA = "Digitar as barras"
DIRECOES_8 = ce.DIRECOES_8
DIRECOES_4 = ce.DIRECOES_4
ALMA_MACRO = "da macro"
ALMA_NAO_SEI = "não sei"
OPCOES_ALMA = ("X", "Y", "Z", ALMA_MACRO, ALMA_NAO_SEI)
COLUNAS_BARRAS = (
    "Usar",
    "Barra",
    "X1",
    "Y1",
    "Z1",
    "X2",
    "Y2",
    "Z2",
    "Maior (mm)",
    "Menor (mm)",
    "Alma ao longo de",
    "Perfil",
)
COLUNAS_ELEMENTOS = (
    "Usar",
    "Nome",
    "Tipo",
    "X1",
    "Y1",
    "Z1",
    "X2",
    "Y2",
    "Z2",
    "Altura (m)",
    "Medida 1 (m)",
    "Medida 2 (m)",
    "φ",
    "C_a",
    "Barra",
)
FORA_DO_ESCOPO = (
    "Efeitos dinâmicos do vento (capítulo 9 da NBR 6123).",
    "Muros, placas e coberturas isoladas (Tabelas 23 a 25): use o módulo Vento nas estruturas.",
    "As chapas do esqueleto não recebem vento sozinhas (podem ser só apoio de carga do modelo): "
    "a superfície real entra como painel.",
    "As combinações: estas são forças características — as combinações saem do plano de cargas.",
)


def _pt(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _numero(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _rotulo_da_alma(vetor: tuple[float, float, float] | None) -> str:
    if vetor is None:
        return ALMA_NAO_SEI
    for eixo, componente in zip("XYZ", vetor, strict=True):
        if abs(componente) >= 0.98:
            return eixo
    return ALMA_MACRO


def _exemplo_digitado(eixo_vertical: str) -> pd.DataFrame:
    """Plataforma em duas colunas, com X entre elas e a plataforma em balanço (modelo, em m)."""

    def p(x: float, h: float, z: float) -> tuple[float, float, float]:
        return (x, h, z) if eixo_vertical == "Y" else (x, -z, h)

    alma_v = "Y" if eixo_vertical == "Y" else "Z"
    barras = [
        ("P1", p(0, 0, 0), p(0, 4, 0), 210, 134, "X", "W 200 x 31,3"),
        ("P2", p(0, 0, 1.8), p(0, 4, 1.8), 210, 134, "X", "W 200 x 31,3"),
        ("V1", p(-2.25, 4, 0), p(2.25, 4, 0), 203, 57, alma_v, 'U 8" x 17,10'),
        ("V2", p(-2.25, 4, 1.8), p(2.25, 4, 1.8), 203, 57, alma_v, 'U 8" x 17,10'),
        ("V3", p(-2.25, 4, 0), p(-2.25, 4, 1.8), 203, 57, alma_v, 'U 8" x 17,10'),
        ("V4", p(2.25, 4, 0), p(2.25, 4, 1.8), 203, 57, alma_v, 'U 8" x 17,10'),
        ("V5", p(0, 4, 0), p(0, 4, 1.8), 203, 57, alma_v, 'U 8" x 17,10'),
        ("D1", p(0, 0.2, 0), p(0, 3.8, 1.8), 64, 64, ALMA_NAO_SEI, 'L 2 1/2" × 1/4"'),
        ("D2", p(0, 0.2, 1.8), p(0, 3.8, 0), 64, 64, ALMA_NAO_SEI, 'L 2 1/2" × 1/4"'),
    ]
    return pd.DataFrame(
        [
            [True, nome, *a, *b, maior, menor, alma, perfil]
            for nome, a, b, maior, menor, alma, perfil in barras
        ],
        columns=COLUNAS_BARRAS,
    )


def _tabela_do_esqueleto(g: ld.GeometriaDoModelo) -> tuple[pd.DataFrame, dict[str, Any]]:
    perfis = ld.perfis_do_esqueleto(g)
    linhas, vetores = [], {}
    for corpo in g.corpos:
        if corpo.forma == ld.FORMA_CHAPA or corpo.comprimento_m <= 0:
            continue
        secao = corpo.secao_mm or (100.0, 100.0)
        vetores[corpo.nome] = corpo.direcao_secao
        linhas.append(
            [
                True,
                corpo.nome,
                *corpo.inicio,
                *corpo.fim,
                round(max(secao), 1),
                round(min(secao), 1),
                _rotulo_da_alma(corpo.direcao_secao),
                perfis.get(corpo.nome, ("", ""))[0],
            ]
        )
    return pd.DataFrame(linhas, columns=COLUNAS_BARRAS), vetores


def _editor_de_barras(tabela: pd.DataFrame, chave: str) -> pd.DataFrame:
    coordenada = {
        c: st.column_config.NumberColumn(format="%.3f", required=True, help=f"{c} em m (modelo).")
        for c in ("X1", "Y1", "Z1", "X2", "Y2", "Z2")
    }
    return st.data_editor(
        tabela,
        num_rows="dynamic",
        hide_index=True,
        key=chave,
        column_config={
            "Usar": st.column_config.CheckboxColumn(help="Desmarque para tirar a barra do vento."),
            "Barra": st.column_config.TextColumn(required=True, help="Nome da barra (único)."),
            **coordenada,
            "Maior (mm)": st.column_config.NumberColumn(
                min_value=1.0, format="%.1f", required=True,
                help="A maior medida da seção (altura de um I ou U, diâmetro de um tubo).",
            ),
            "Menor (mm)": st.column_config.NumberColumn(
                min_value=1.0, format="%.1f", required=True, help="A outra medida da seção."
            ),
            "Alma ao longo de": st.column_config.SelectboxColumn(
                options=list(OPCOES_ALMA), required=True,
                help="Eixo do modelo para onde aponta a medida maior; “da macro” = a direção lida "
                "pela macro; “não sei” = a medida maior vista de qualquer lado.",
            ),
            "Perfil": st.column_config.TextColumn(help="Só para identificar (não entra na conta)."),
        },
    )  # fmt: skip


def _barras_da_tabela(
    tabela: pd.DataFrame,
    eixo_vertical: str,
    vetores: dict[str, Any],
    nomes_no_simulation: dict[str, str],
    erros: list[str],
) -> list[vpb.BarraAoVento]:
    eixos = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}
    barras = []
    for i, linha in enumerate(tabela.to_dict("records"), start=1):
        if not bool(linha.get("Usar", True)):
            continue
        nome = str(linha.get("Barra") or "").strip()
        valores = [_numero(linha.get(c)) for c in ("X1", "Y1", "Z1", "X2", "Y2", "Z2")]
        maior, menor = _numero(linha.get("Maior (mm)")), _numero(linha.get("Menor (mm)"))
        if not nome or None in valores or not maior or not menor:
            erros.append(f"Barra da linha {i}: preencha o nome, as pontas e a seção.")
            continue
        alma = str(linha.get("Alma ao longo de") or ALMA_NAO_SEI)
        if alma in eixos:
            direcao = eixos[alma]
        elif alma == ALMA_MACRO and vetores.get(nome):
            direcao = vetores[nome]
        else:
            direcao = None
        a = (valores[0], valores[1], valores[2])
        b = (valores[3], valores[4], valores[5])
        barras.append(
            vpb.BarraAoVento(
                nome=nome,
                inicio=vpb.para_a_planta(a, eixo_vertical),  # type: ignore[arg-type]
                fim=vpb.para_a_planta(b, eixo_vertical),  # type: ignore[arg-type]
                maior_m=max(maior, menor) / 1000.0,
                menor_m=min(maior, menor) / 1000.0,
                direcao_maior=(
                    vpb._unitario(vpb.para_a_planta(direcao, eixo_vertical)) if direcao else None
                ),
                perfil=str(linha.get("Perfil") or ""),
                nome_no_modelo=nomes_no_simulation.get(nome, ""),
            )
        )
    return barras


def _guarda_corpos_das_bordas(
    projeto: Any, geometria: ld.GeometriaDoModelo, eixo_vertical: str, nomes: set[str]
) -> tuple[pd.DataFrame, gm.BordasDoPiso, gm.EscolhaDoGuardaCorpo]:
    """Uma linha de guarda-corpo por trecho marcado nas bordas do piso (Cargas do esqueleto)."""
    from components.guarda_corpo_ui import escolha_inicial

    escolha = escolha_inicial(projeto)
    bordas = gm.bordas_do_projeto(geometria, eixo_vertical, escolha)
    linhas = []
    for t in bordas.marcados(escolha.trocados):
        if t.viga not in nomes:
            continue
        linhas.append(
            [
                True,
                f"GC {t.id}",
                vpb.TIPO_GUARDA_CORPO,
                *t.inicio,
                *t.fim,
                escolha.altura_m,
                None,
                None,
                escolha.phi,
                None,
                t.viga,
            ]
        )
    return pd.DataFrame(linhas, columns=COLUNAS_ELEMENTOS), bordas, escolha


def _editor_de_elementos(
    chave: str, nomes_das_barras: list[str], inicial: pd.DataFrame | None = None
) -> pd.DataFrame:
    coordenada = {
        c: st.column_config.NumberColumn(format="%.3f", help=f"{c} em m (modelo).")
        for c in ("X1", "Y1", "Z1", "X2", "Y2", "Z2")
    }
    return st.data_editor(
        inicial if inicial is not None else pd.DataFrame(columns=COLUNAS_ELEMENTOS),
        num_rows="dynamic",
        hide_index=True,
        key=chave,
        column_config={
            "Usar": st.column_config.CheckboxColumn(default=True, help="Desmarque para ignorar."),
            "Nome": st.column_config.TextColumn(required=True, help="Nome do elemento."),
            "Tipo": st.column_config.SelectboxColumn(
                options=list(vpb.TIPOS_DE_ELEMENTO), required=True, help="O que é o elemento."
            ),
            **coordenada,
            "Altura (m)": st.column_config.NumberColumn(
                min_value=0.01, format="%.2f", help="Altura acima da base."
            ),
            "Medida 1 (m)": st.column_config.NumberColumn(
                min_value=0.01, format="%.2f",
                help="Equipamento: medida em X do modelo (diâmetro, no cilindro).",
            ),
            "Medida 2 (m)": st.column_config.NumberColumn(
                min_value=0.01, format="%.2f",
                help="Equipamento: medida na outra direção horizontal do modelo.",
            ),
            "φ": st.column_config.NumberColumn(
                min_value=0.01, max_value=1.0, format="%.2f",
                help="Parte cheia (guarda-corpo ≈ 0,30; escada ≈ 0,50; painel = 1). Vazio: esses.",
            ),
            "C_a": st.column_config.NumberColumn(
                min_value=0.1, format="%.2f", help="Só se tiver um valor próprio (vazio = norma)."
            ),
            "Barra": st.column_config.SelectboxColumn(
                options=nomes_das_barras, help="Quem recebe a força (vazio = o programa acha)."
            ),
        },
    )  # fmt: skip


def _elementos_da_tabela(
    tabela: pd.DataFrame, eixo_vertical: str, erros: list[str]
) -> list[vpb.ElementoAoVento]:
    elementos = []
    for i, linha in enumerate(tabela.to_dict("records"), start=1):
        if linha.get("Usar") is False:
            continue
        nome = str(linha.get("Nome") or "").strip()
        tipo = str(linha.get("Tipo") or "")
        p1 = [_numero(linha.get(c)) for c in ("X1", "Y1", "Z1")]
        p2 = [_numero(linha.get(c)) for c in ("X2", "Y2", "Z2")]
        altura = _numero(linha.get("Altura (m)"))
        if not nome and not tipo and all(v is None for v in p1):
            continue  # linha vazia que o editor deixa
        if not nome or tipo not in vpb.TIPOS_DE_ELEMENTO or None in p1 or not altura:
            erros.append(
                f"Elemento da linha {i}: preencha o nome, o tipo, a ponta 1 (ou o centro) e a altura."
            )
            continue
        em_linha = tipo in vpb.TIPOS_EM_LINHA
        if em_linha and None in p2:
            erros.append(f"{nome}: guarda-corpo, escada e painel precisam das duas pontas da base.")
            continue
        elementos.append(
            vpb.ElementoAoVento(
                nome=nome,
                tipo=tipo,
                ponto_1=vpb.para_a_planta(p1, eixo_vertical),  # type: ignore[arg-type]
                ponto_2=vpb.para_a_planta(p2, eixo_vertical) if em_linha else None,  # type: ignore[arg-type]
                altura_m=altura,
                largura_x_m=_numero(linha.get("Medida 1 (m)")) or 1.0,
                largura_y_m=_numero(linha.get("Medida 2 (m)")) or 1.0,
                phi=_numero(linha.get("φ")),
                ca=_numero(linha.get("C_a")),
                barra=str(linha.get("Barra") or "").strip(),
            )
        )
    return elementos


def _assinatura_da_tabela(tabela: pd.DataFrame) -> str:
    import zlib

    return f"{zlib.crc32(tabela.to_csv(index=False).encode('utf-8')):08x}"


def _rotulo_da_direcao(angulo: int) -> str:
    return f"W{angulo} · {angulo}° ({vpb.SENTIDOS[angulo]})"


def mostrar_vento_por_barras() -> None:
    projeto = obter_projeto_ativo()
    base = base_ativa()
    with st.container(border=True):
        st.subheader("Como o programa faz, viga a viga e pilar a pilar", help=AJUDA["sec_como"])
        st.markdown(
            "- Cada barra do modelo é olhada **em cada direção do vento**: a área que ela mostra "
            "para o vento (a *sombra*, ℓ·sen θ·c) vezes a pressão na altura dela e o coeficiente "
            "da norma — **F = C_a·η·q·A** (NBR 6123, 8.3).\n"
            "- No vento **perpendicular às faces** (0°, 90°, 180°, 270°), as barras de frente para "
            "o vento formam os planos (reticulados): cada plano tem o seu **φ** e **C_a** "
            "(Figura 12), e o que fica atrás de um plano é **protegido** pelo fator **η** "
            "(Figura 14).\n"
            "- Nos **diagonais** (45°, 135°…), a favor da segurança: **C_a = 2,0** e sem proteção.\n"
            "- Guarda-corpo, lateral de escada, painel e equipamento entram à parte e a força vai "
            "para a **viga que os apoia**.\n"
            "- Sai uma carga por metro em **cada barra**, por direção, pronta para o plano de "
            "cargas e o SolidWorks."
        )
    erros: list[str] = []
    geometria = ld.geometria_do_projeto(projeto)
    esforcos = em.esforcos_do_projeto(projeto)
    ident = ce.formulario_identificacao()
    nomes_no_simulation: dict[str, str] = {}
    with st.container(border=True), secao_protegida("Barras ao vento"):
        st.subheader("2. As barras", help=AJUDA["sec_barras"])
        opcoes = [ORIGEM_ESQUELETO, ORIGEM_DIGITADA] if geometria.corpos else [ORIGEM_DIGITADA]
        linha = st.columns([3, 1])
        origem = linha[0].radio(
            "De onde vêm as barras",
            opcoes,
            horizontal=True,
            key="vb_origem",
            help=AJUDA["origem"],
        )
        eixos = ["Y", "Z"]
        eixo_vertical = linha[1].radio(
            "Eixo vertical do modelo",
            eixos,
            index=eixos.index(esforcos.eixo_vertical) if esforcos.eixo_vertical in eixos else 0,
            horizontal=True,
            key="vb_eixo_vertical",
            help=AJUDA["eixo_vertical"],
        )
        if not geometria.corpos:
            st.caption(
                ":material/account_tree: O projeto ainda não tem o esqueleto do modelo: rode a "
                "macro do SolidWorks e envie o …_esqueleto.csv em **Cargas do esqueleto** para "
                "usar as barras do seu modelo. Abaixo, um exemplo para editar: plataforma em duas "
                "colunas, com X entre elas e a plataforma em balanço."
            )
            st.page_link(
                "app_pages/cargas_esqueleto.py",
                label="Abrir Cargas do esqueleto",
                icon=":material/account_tree:",
            )
        if origem == ORIGEM_ESQUELETO:
            tabela, vetores = _tabela_do_esqueleto(geometria)
            st.caption(
                f":material/account_tree: {geometria.arquivo}"
                + (f" — {geometria.origem}" if geometria.origem else "")
                + f" · {len(tabela)} barras (as chapas ficam de fora)."
            )
            nomes_no_simulation = {
                corpo.nome: barra
                for barra, corpo in ld.correspondencia(
                    geometria, esforcos.nomes_dos_membros, esforcos
                ).corpos.items()
            }
            em_pe = vpb.chapas_em_pe(geometria, eixo_vertical)
            if em_pe:
                st.caption(
                    ":material/info: Chapas em pé no esqueleto (não recebem vento sozinhas; se "
                    "forem superfície de verdade, entre com elas como painel): "
                    + ", ".join(em_pe[:8])
                    + ("…" if len(em_pe) > 8 else "")
                )
        else:
            tabela, vetores = _exemplo_digitado(eixo_vertical), {}
        st.caption("Barras (modelo, em m)", help=AJUDA["tabela_barras"])
        editada = _editor_de_barras(
            tabela, f"vb_barras_{'esq' if origem == ORIGEM_ESQUELETO else 'dig'}"
        )
        barras = _barras_da_tabela(editada, eixo_vertical, vetores, nomes_no_simulation, erros)
    with st.container(border=True), secao_protegida("Elementos ao vento"):
        st.subheader(
            "3. Guarda-corpos, escadas, painéis e equipamentos", help=AJUDA["sec_elementos"]
        )
        inicial = None
        chave_el = "vb_elementos_dig"
        if origem == ORIGEM_ESQUELETO:
            usar_bordas = st.toggle(
                "Guarda-corpos das bordas do piso (do esqueleto)",
                value=True,
                key="vb_gc_bordas",
                help=AJUDA["gc_bordas"],
            )
            chave_el = "vb_elementos_esq"
            if usar_bordas:
                inicial, bordas, escolha = _guarda_corpos_das_bordas(
                    projeto, geometria, eixo_vertical, {b.nome for b in barras}
                )
                chave_el += f"_{_assinatura_da_tabela(inicial)}"
                st.caption(
                    f":material/fence: {len(inicial)} guarda-corpos nas bordas "
                    f"({bordas.metodo}; altura {_pt(escolha.altura_m, 2)} m, φ "
                    f"{_pt(escolha.phi, 2)}) — os trechos e a altura se ajustam em **Cargas do "
                    "esqueleto › Guarda-corpo nas bordas do piso**."
                )
        st.caption("Elementos (modelo, em m)", help=AJUDA["tabela_elementos"])
        tabela_el = _editor_de_elementos(chave_el, [b.nome for b in barras], inicial)
        elementos = _elementos_da_tabela(tabela_el, eixo_vertical, erros)
    vento = ce.formulario_vento(base, titulo="4. Vento (NBR 6123:2023)")
    with st.container(border=True):
        st.subheader("5. Direções e opções", help=AJUDA["sec_opcoes"])
        linha = st.columns([2, 1, 1])
        direcoes = linha[0].radio(
            "Direções do vento",
            [DIRECOES_8, DIRECOES_4],
            key="vb_direcoes",
            help=AJUDA["direcoes"],
        )
        protecao = linha[1].toggle(
            "Proteção entre planos (η)", value=True, key="vb_protecao", help=AJUDA["protecao"]
        )
        terreno = linha[2].number_input(
            "Cota do terreno no modelo (m)",
            value=None,
            step=0.1,
            format="%.3f",
            placeholder="o pé dos pilares",
            key="vb_terreno",
            help=AJUDA["terreno"],
        )
    if erros:
        for erro in erros:
            st.error(erro, icon=":material/error:")
        st.stop()
    entrada = vpb.EntradaPorBarras(
        barras=tuple(barras),
        parametros=vento,
        elementos=tuple(elementos),
        direcoes=(
            vpb.DIRECOES_COM_DIAGONAIS if direcoes == DIRECOES_8 else vpb.DIRECOES_PERPENDICULARES
        ),
        cota_do_terreno_m=None if terreno is None else float(terreno),
        protecao=bool(protecao),
    )
    problemas = vpb.validar_entrada(entrada)
    if problemas:
        for erro in problemas:
            st.error(erro, icon=":material/error:")
        st.stop()
    try:
        r = vpb.calcular(entrada)
    except ValueError as erro:
        st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
        st.stop()
    _resultados(r, eixo_vertical, origem, geometria, ident, base)


def _forcas_por_nivel(vn: vpn.VentoPorNivel, eixo_vertical: str) -> None:
    """A força do vento em cada nível, em cada direção, e por onde ela passa."""
    st.subheader("Força do vento em cada nível", help=AJUDA["res_niveis"])
    principal = vn.nivel_principal
    if principal is None:
        for aviso in vn.avisos:
            st.warning(aviso, icon=":material/warning:")
        return
    nivel = vn.niveis[principal]
    st.caption(
        f"Nível {nivel.numero}, o de mais vigas (a plataforma): cota {_pt(nivel.cota_m, 2)} m "
        f"do terreno ({vpn.cota_no_modelo(nivel, eixo_vertical)} no modelo). A força do vento "
        "nele, em cada direção:"
    )
    colunas = st.columns(min(len(vn.direcoes), 4))
    for k, d in enumerate(vn.direcoes):
        forca = d.niveis[principal].forca_kN
        colunas[k % len(colunas)].metric(
            f"{d.codigo} ({vpb.SENTIDOS.get(d.angulo, '')})",
            f"{_pt(forca, 2 if forca < 10 else 1)} kN",
            help=AJUDA["res_nivel_principal"],
        )
    st.dataframe(
        pd.DataFrame(vpn.tabela_por_nivel(vn, eixo_vertical)),
        hide_index=True,
        width="stretch",
        column_config={
            c: st.column_config.NumberColumn(format="%.2f")
            for c in ("Cota (m)", "F_x (kN)", "F_y (kN)", "F (kN)")
        },
    )
    st.caption(
        "Cada barra manda metade do vento dela para cada ponta (a ponta que cai no meio de outra "
        "barra, como a mão francesa no pilar, passa às pontas dessa barra); guarda-corpos e "
        "equipamentos vão pela viga que os apoia. A linha **base** é o que chega no pé dos "
        "pilares: vai direto à fundação. Níveis + base = a força total do resumo."
    )
    for aviso in vn.avisos:
        st.warning(aviso, icon=":material/warning:")


def _forma_simplificada(
    vn: vpn.VentoPorNivel,
    eixo_vertical: str,
    acoes_barras: list[pc.Acao],
    acoes: list[pc.Acao],
) -> None:
    st.markdown("**Forma simplificada: a força de cada nível nas vigas na direção do vento**")
    if not vn.simplificada_possivel:
        st.error(
            "A forma simplificada não serve neste modelo (veja os avisos da força em cada nível): "
            "use a carga barra a barra.",
            icon=":material/error:",
        )
        return
    st.caption("Cargas por linha de vigas", help=AJUDA["res_simplificada"])
    st.dataframe(
        pd.DataFrame(vpn.tabela_simplificada(vn, eixo_vertical)),
        hide_index=True,
        width="stretch",
        column_config={
            "L (m)": st.column_config.NumberColumn(format="%.2f"),
            "F (kN)": st.column_config.NumberColumn(format="%.3f"),
            "q (kN/m)": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    maior = max(vn.direcoes, key=lambda d: d.flexao_local_kNm)
    st.caption(
        f":material/info: No SolidWorks: {vpn.numero_de_cargas_no_estudo(acoes)} cargas de vento "
        f"no estudo, contra {vpn.numero_de_cargas_no_estudo(acoes_barras)} barra a barra. "
        "Em cada viga da linha, força distribuída com o q da linha, na direção da própria viga. "
        "A força e a torção de cada nível são as do cálculo viga a viga; fica de fora só a flexão "
        "de cada barra pelo vento dela — a maior é "
        f"{_pt(maior.flexao_local_kNm, 2)} kN·m ({maior.barra_da_flexao or '—'}, {maior.codigo}): "
        "confira que é pequena perto da flexão das outras cargas."
    )


def _resultados(
    r: vpb.ResultadoPorBarras,
    eixo_vertical: str,
    origem: str,
    geometria: ld.GeometriaDoModelo,
    ident: Any,
    base: bt.BaseTecnica | None,
) -> None:
    st.header("Resultados")
    g = r.governante
    colunas = st.columns(4)
    colunas[0].metric("Direção que mais carrega", g.codigo, vpb.SENTIDOS[g.angulo],
                      delta_color="off", help=AJUDA["res_governante"])  # fmt: skip
    colunas[1].metric("Força total", f"{_pt(g.total_kN, 2)} kN", help=AJUDA["res_total"])
    colunas[2].metric(
        "Tombamento",
        f"{_pt(max(d.momento_tombamento_kNm for d in r.direcoes))} kN·m",
        help=AJUDA["res_tombamento"],
    )
    colunas[3].metric(
        "q no topo (kN/m²)", _pt(r.vento_no_topo.q_N_m2 / 1e3, 3), help=AJUDA["res_q"]
    )
    for aviso in r.avisos:
        st.warning(aviso, icon=":material/warning:")
    st.subheader("Resumo por direção", help=AJUDA["res_resumo"])
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Caso": d.codigo,
                    "Sentido": vpb.SENTIDOS[d.angulo],
                    "Direção": "perpendicular" if d.perpendicular else "diagonal",
                    "Barras (kN)": d.estrutura_kN,
                    "Elementos (kN)": d.elementos_kN,
                    "Total (kN)": d.total_kN,
                    "F_x (kN)": d.fx_kN,
                    "F_y (kN)": d.fy_kN,
                    "Tombamento (kN·m)": d.momento_tombamento_kNm,
                    "Torção (kN·m)": d.torcao_kNm,
                }
                for d in r.direcoes
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={
            c: st.column_config.NumberColumn(format="%.2f")
            for c in (
                "Barras (kN)",
                "Elementos (kN)",
                "Total (kN)",
                "F_x (kN)",
                "F_y (kN)",
                "Tombamento (kN·m)",
                "Torção (kN·m)",
            )
        },
    )
    vn = vpn.vento_por_nivel(r)
    with secao_protegida("Força do vento em cada nível"):
        _forcas_por_nivel(vn, eixo_vertical)
    angulos = [d.angulo for d in r.direcoes]
    angulo = st.radio(
        "Direção mostrada",
        angulos,
        index=angulos.index(g.angulo),
        format_func=_rotulo_da_direcao,
        horizontal=True,
        key="vb_ver",
        help=AJUDA["ver_direcao"],
    )
    direcao = r.direcao(int(angulo))
    abas = st.tabs(
        [
            "Estrutura em 3D",
            "Planta",
            "O que o vento vê",
            "Barra a barra",
            "Elementos",
            "Reticulados",
        ]
    )
    with abas[0], secao_protegida("Desenho 3D do vento"):
        st.subheader("Carga em cada barra", help=AJUDA["res_3d"])
        st.image(svg_vento_3d(r, direcao.angulo, eixo_vertical=eixo_vertical), width="stretch")
    with abas[1], secao_protegida("Planta do vento"):
        st.subheader("Planta", help=AJUDA["res_planta"])
        st.image(svg_vento_planta(r, direcao.angulo), width="stretch")
    with abas[2], secao_protegida("Sombra do vento"):
        st.subheader("O que o vento vê", help=AJUDA["res_sombra"])
        st.image(svg_vento_sombra(r, direcao.angulo), width="stretch")
    with abas[3]:
        st.subheader("Barra a barra", help=AJUDA["res_barras"])
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Barra": f.rotulo,
                        "Plano": f.plano,
                        "ℓ (m)": f.comprimento_m,
                        "Sombra A (m²)": f.area_m2,
                        "C_a": f.ca,
                        "η": f.eta,
                        "Cota (m)": f.cota_m,
                        "q (kN/m²)": f.q_N_m2 / 1e3,
                        "F (kN)": f.forca_kN,
                        "kN/m": f.kN_m,
                        "X (kN/m)": f.fx_kN_m,
                        "Y (kN/m)": f.fy_kN_m,
                        "Cálculo": f.calculo,
                    }
                    for f in sorted(direcao.barras, key=lambda f: -f.forca_kN)
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={
                **{
                    c: st.column_config.NumberColumn(format="%.3f")
                    for c in ("Sombra A (m²)", "η", "q (kN/m²)", "F (kN)", "kN/m", "X (kN/m)",
                              "Y (kN/m)")
                },
                **{c: st.column_config.NumberColumn(format="%.2f")
                   for c in ("ℓ (m)", "C_a", "Cota (m)")},
            },
        )  # fmt: skip
    with abas[4]:
        st.subheader("Elementos", help=AJUDA["res_elementos"])
        if direcao.elementos:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Elemento": el.elemento,
                            "Tipo": el.tipo,
                            "A (m²)": el.area_m2,
                            "C_a": el.ca,
                            "q (kN/m²)": el.q_N_m2 / 1e3,
                            "F (kN)": el.forca_kN,
                            "Vai para": "; ".join(
                                f"{p.rotulo} ({_pt(math.hypot(p.fx, p.fy), 3)} {p.unidade})"
                                for p in el.parcelas
                            ),
                            "Cálculo": el.calculo,
                        }
                        for el in direcao.elementos
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption("Nenhum guarda-corpo, escada, painel ou equipamento informado.")
    with abas[5]:
        st.subheader("Reticulados", help=AJUDA["res_reticulados"])
        if direcao.planos:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Plano": p.nome,
                            "Barras": len(p.barras),
                            "A_e (m²)": p.area_m2,
                            "Contorno (m²)": p.contorno_m2,
                            "φ": p.phi,
                            "C_a": p.ca,
                            "Afastamento (m)": p.afastamento_m,
                            "η": p.eta,
                            "Quais": ", ".join(p.barras),
                        }
                        for p in direcao.planos
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption("Vento diagonal: sem planos — todas as barras com C_a = 2,0 e η = 1.")

    with st.container(border=True), secao_protegida("Levar o vento barra a barra"):
        st.subheader("Levar ao projeto", help=AJUDA["sec_levar"])
        forma = st.radio(
            "Como aplicar o vento no modelo", vpn.FORMAS, key="vb_forma", help=AJUDA["forma"]
        )
        simplificada = forma == vpn.FORMA_SIMPLIFICADA
        acoes_barras = vpb.acoes_para_o_plano(r)
        acoes: list[pc.Acao] = acoes_barras
        if simplificada:
            acoes = vpn.acoes_simplificadas(vn) if vn.simplificada_possivel else []
            _forma_simplificada(vn, eixo_vertical, acoes_barras, acoes)
        else:
            st.caption(
                f":material/info: No SolidWorks: {vpn.numero_de_cargas_no_estudo(acoes_barras)} "
                "cargas de vento no estudo (uma por barra e eixo; cada caso muda só o valor)"
                + (
                    f" — na forma simplificada, "
                    f"{vpn.numero_de_cargas_no_estudo(vpn.acoes_simplificadas(vn))}."
                    if vn.simplificada_possivel
                    else "."
                )
            )
        colunas = st.columns(2)
        colunas[0].download_button(
            "Cargas do vento (CSV)",
            data=vpn.csv_simplificado(vn, eixo_vertical) if simplificada else vpb.csv_das_cargas(r),
            file_name="vento_por_nivel.csv" if simplificada else "vento_barra_a_barra.csv",
            mime="text/csv",
            icon=":material/download:",
            key="vb_csv",
            help=AJUDA["btn_csv"],
            width="stretch",
            disabled=not acoes,
        )
        codigos = ", ".join(d.codigo for d in r.direcoes)
        if colunas[1].button(
            "Enviar ao plano de cargas",
            icon=":material/table_chart:",
            key="vb_para_plano",
            help=AJUDA["btn_plano"],
            width="stretch",
            disabled=not acoes,
        ) and gravar_plano(
            vpb.plano_com_o_vento(plano_ativo(), r, acoes),
            f"Plano de cargas: {codigos} do vento barra a barra"
            + (" (forma simplificada)" if simplificada else ""),
        ):
            st.success(f"{codigos} gravados no plano de cargas.", icon=":material/check_circle:")
        st.caption(
            "Cada direção vira um caso primário (W0, W90…) no plano de cargas. **As combinações "
            "não precisam ser digitadas no SolidWorks**: o programa combina os casos primários "
            "quando você manda os resultados em Esforços do modelo, e o arquivo do Gerenciador de "
            "casos de carga (página Plano de cargas) já leva todas — no SolidWorks, “Carregar os "
            "dados de entrada de um arquivo .csv externo”."
        )

    contexto: dict[str, Any] = {"data_do_calculo": ident.data.isoformat()}
    if ident.obra:
        contexto["obra"] = ident.obra
    if ident.tag:
        contexto["tag"] = ident.tag
    origem_texto = (
        f"esqueleto do modelo ({geometria.arquivo})" if origem == ORIGEM_ESQUELETO else "digitadas"
    )
    registro = vbr.registro_vento_por_barras(
        r,
        eixo_vertical=eixo_vertical,
        origem_das_barras=origem_texto,
        contexto=contexto,
        responsavel=ident.responsavel,
        avisos_da_base=bt.avisos(base) if base else None,
    )
    with st.container(border=True):
        st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
        botao_registrar_calculo(
            registro,
            key="registrar_vento_por_barras",
            rotulo="Registrar o vento barra a barra no projeto ativo",
        )
