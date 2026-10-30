"""Interface da página Contraventamento de estruturas abertas.

Só desenha: o cálculo está em :mod:`core.contraventamento_plataforma` (vento em
:mod:`core.vento_estrutura_aberta` ou, viga a viga, em :mod:`core.contraventamento_vento_barras`,
combinações em :mod:`core.load_combinations`, diagonais em
:mod:`core.contraventamento_barras`) e o registro em :mod:`core.contraventamento_estrutura_registro`.
Poucos campos à vista, com os valores usuais; o resto fica em "Ajustes". Entrada impossível vira
erro claro — nada é corrigido em silêncio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from components.base_tecnica_ui import (
    base_ativa,
    botao_recarregar_da_base,
    gravar_acoes_no_plano,
    gravar_plano,
    legenda_da_base,
    plano_ativo,
)
from components.contraventamento_estrutura_help import AJUDA
from components.figuras_estrutura import svg_elevacao_linha, svg_planta, svg_vento_elevacao
from components.figuras_vento import svg_vento_3d
from components.project_tools import botao_registrar_calculo
from components.robustez import secao_protegida
from components.ui import fronteira_modelo
from components.verification_table import mostrar_tabela_verificacoes
from core import base_tecnica as bt
from core import bolted_connection as bc
from core import contraventamento_barras as cb
from core import contraventamento_do_esqueleto as cesq
from core import contraventamento_estrutura_registro as reg
from core import contraventamento_plataforma as cp
from core import contraventamento_vento_barras as cvb
from core import esforcos_modelo as em
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import load_combinations as comb
from core import section_catalog as sc
from core import steel_sections as ss
from core import vento_aberto_registro as var
from core import vento_estrutura_aberta as va
from core import vento_nbr6123 as vb
from core import vento_por_barras as vpb
from core.project_store import obter_projeto_ativo

PREFIXO = "ce_"
PILAR_PADRAO = "W 200 x 46,1 (H)"
VIGA_PADRAO = "W 310 x 32,7"
COLUNAS_EQUIPAMENTOS = [
    "Nome",
    "Nível",
    "Forma",
    "Medida em X (m)",
    "Medida em Y (m)",
    "Altura (m)",
    "Peso (kN)",
    "C_a (vazio = automático)",
]
COLUNAS_FORCAS = ["Nome", "Direção", "Nível", "Valor (kN)", "Categoria", "Nos dois sentidos"]
METODO_GRADE = "Pórticos regulares (grade)"
METODO_BARRAS = "Viga a viga, pilar a pilar"
DIRECOES_8 = "As 8 direções (de 45° em 45°)"
DIRECOES_4 = "Só as 4 perpendiculares às faces (NBR 6123, 8.5)"


def _pt(valor: float, casas: int = 1) -> str:
    if not math.isfinite(valor):
        return "∞"
    return f"{valor:.{casas}f}".replace(".", ",")


def _chave(nome: str) -> str:
    return PREFIXO + nome


#: Valores que vieram do esqueleto (o botão "Preencher pelo esqueleto"): também o valor inicial
#: do campo quando ele é criado de novo (outra página, outra sessão).
PADROES = PREFIXO + "padroes_do_esqueleto"


def _padrao(chave: str, valor: Any) -> Any:
    return st.session_state.get(PADROES, {}).get(chave, valor)


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
            value=float(_padrao(chave, valor)),
            step=passo,
            format=formato,
            key=_chave(chave),
            persist_state="session",
            help=ajuda,
        )
    )


def _inteiro(
    rotulo: str, chave: str, valor: int, ajuda: str, *, minimo: int, maximo: int, alvo: Any = st
) -> int:
    return int(
        alvo.number_input(
            rotulo,
            min_value=minimo,
            max_value=maximo,
            value=int(_padrao(chave, valor)),
            step=1,
            key=_chave(chave),
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
    completa = _chave(chave)
    padrao = _padrao(chave, padrao)
    if st.session_state.get(completa) not in opcoes:
        st.session_state.pop(completa, None)
    return str(
        alvo.selectbox(
            rotulo,
            opcoes,
            index=opcoes.index(padrao) if padrao in opcoes else 0,
            format_func=formatar or str,
            key=completa,
            persist_state="session",
            help=ajuda,
        )
    )


def _toggle(rotulo: str, chave: str, ajuda: str, *, valor: bool = False, alvo: Any = st) -> bool:
    return bool(
        alvo.toggle(
            rotulo,
            value=bool(_padrao(chave, valor)),
            key=_chave(chave),
            persist_state="session",
            help=ajuda,
        )
    )


# ---------------------------------------------------------------------------------------------
# Formulários
# ---------------------------------------------------------------------------------------------
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
            "Obra", key=_chave("obra"), persist_state="session", help=AJUDA["obra"]
        )
        tag = colunas[1].text_input(
            "TAG", key=_chave("tag"), persist_state="session", help=AJUDA["tag"]
        )
        responsavel = colunas[2].text_input(
            "Responsável",
            key=_chave("responsavel"),
            persist_state="session",
            help=AJUDA["responsavel"],
        )
        data = colunas[3].date_input(
            "Data",
            value=date.today(),
            format="DD/MM/YYYY",
            key=_chave("data"),
            persist_state="session",
            help=AJUDA["data"],
        )
    return Identificacao(obra.strip(), tag.strip(), responsavel.strip(), data)


def _perfis_i() -> list[str]:
    return [
        n for n, p in sc.listar_perfis().items() if ss.familia_do_perfil(p) in ("w", "hp", "i", "u")
    ]


def _ler_cotas(texto: str) -> tuple[float, ...]:
    partes = [p.strip() for p in texto.replace("\n", ";").split(";") if p.strip()]
    try:
        return tuple(float(p.replace(",", ".")) for p in partes)
    except ValueError as erro:
        raise ValueError(
            "Cotas dos pisos: escreva números separados por ponto e vírgula (ex.: 3,5; 7,0)."
        ) from erro


@dataclass(frozen=True)
class DadosEstrutura:
    comprimento_x: float
    largura_y: float
    cotas: tuple[float, ...]
    vaos_x: int
    vaos_y: int
    largura_pilar_m: float
    altura_viga_m: float
    guarda_corpo: bool
    altura_gc: float
    phi_gc: float
    area_de_piso_m2: float | None = None


def esqueleto_do_projeto() -> cesq.EsqueletoDoContraventamento | None:
    """O que o esqueleto do projeto diz da estrutura (``None`` sem esqueleto)."""
    projeto = obter_projeto_ativo()
    geometria = ld.geometria_do_projeto(projeto)
    if not geometria.corpos:
        return None
    eixo = em.esforcos_do_projeto(projeto).eixo_vertical
    eixo = str(st.session_state.get(_chave("vb_eixo"), eixo if eixo in ("Y", "Z") else "Y"))
    try:
        return cesq.ler_esqueleto(geometria, eixo)
    except (ArithmeticError, ValueError):
        return None


def _preencher_pelo_esqueleto(esq: cesq.EsqueletoDoContraventamento) -> None:
    """Os campos da página com o que o esqueleto diz (só o que ele sabe)."""
    valores: dict[str, Any] = {
        "Lx": max(esq.lx_m, 0.5),
        "Ly": max(esq.ly_m, 0.5),
        "vaos_x": min(max(esq.vaos_x, 1), 20),
        "vaos_y": min(max(esq.vaos_y, 1), 20),
    }
    perfis = _perfis_i()
    if esq.pilar in perfis:
        valores["pilar"] = esq.pilar
    if esq.viga in perfis:
        valores["viga"] = esq.viga
    if esq.cotas_m:
        valores["n_pisos"] = min(len(esq.cotas_m), 8)
        valores["h_andar"] = max(round(esq.cotas_m[0], 2), 0.5)
    sistemas = {s: esq.sistema(d) for s, d in (("_x", "X"), ("_y", "Y"))}
    for sufixo, s in sistemas.items():
        if s is None:
            continue
        valores[f"tipo{sufixo}"] = s.tipo
        valores[f"linhas{sufixo}"] = min(s.linhas, 20)
        valores[f"paineis{sufixo}"] = min(s.paineis_por_linha, 20)
        if s.familia:
            valores[f"familia{sufixo}"] = s.familia
            valores[f"perfil{sufixo}"] = s.perfil
    sx, sy = sistemas["_x"], sistemas["_y"]
    valores["mesmo_sistema"] = (
        sx is not None
        and sy is not None
        and (sx.tipo, sx.linhas, sx.paineis_por_linha, sx.perfil)
        == (sy.tipo, sy.linhas, sy.paineis_por_linha, sy.perfil)
    )
    # O valor vai direto no campo (no navegador, o campo guarda o dele pela chave) e fica também
    # como o inicial, para quando o campo for criado de novo.
    st.session_state[PADROES] = {**st.session_state.get(PADROES, {}), **valores}
    for chave, valor in valores.items():
        st.session_state[_chave(chave)] = valor
    st.session_state[_chave("cotas_livres")] = "; ".join(_pt(z, 2) for z in esq.cotas_m)
    st.session_state[_chave("area_piso")] = esq.area_de_piso_m2


def mostrar_esqueleto(esq: cesq.EsqueletoDoContraventamento | None) -> None:
    """O resumo do que o esqueleto diz e o botão que preenche a página com isso."""
    if esq is None:
        return
    partes = [
        f"{len(esq.pilares)} pilares em {esq.linhas_de_pilares[0]} × {esq.linhas_de_pilares[1]} "
        f"linhas ({esq.pilar or 'perfil ?'})",
        f"L_x × L_y = {_pt(esq.lx_m, 2)} × {_pt(esq.ly_m, 2)} m",
        "pisos a " + ("; ".join(_pt(z, 2) for z in esq.cotas_m) or "—") + " m",
    ]
    if esq.area_de_piso_m2:
        partes.append(f"piso de {_pt(esq.area_de_piso_m2, 1)} m²")
    for direcao in cp.DIRECOES:
        s = esq.sistema(direcao)
        partes.append(
            f"{direcao}: "
            + (
                f"{cp.TIPOS[s.tipo].split(' (')[0].split(' —')[0]}, {s.linhas} linha(s)"
                if s
                else "sem diagonais"
            )
        )
    linha = st.columns([4, 1.4])
    linha[0].caption(":material/account_tree: Esqueleto do modelo: " + " · ".join(partes))
    linha[1].button(
        "Preencher pelo esqueleto",
        on_click=_preencher_pelo_esqueleto,
        args=(esq,),
        icon=":material/account_tree:",
        key=_chave("preencher_esqueleto"),
        help=AJUDA["preencher_esqueleto"],
        width="stretch",
    )


def formulario_estrutura(
    erros: list[str], esq: cesq.EsqueletoDoContraventamento | None = None
) -> DadosEstrutura:
    with st.container(border=True):
        st.subheader("2. Estrutura", help=AJUDA["sec_2"])
        mostrar_esqueleto(esq)
        linha = st.columns(4)
        lx = _numero(
            "Comprimento L_x (m)", "Lx", 12.0, AJUDA["Lx"], minimo=0.5, passo=0.5, alvo=linha[0]
        )
        ly = _numero(
            "Largura L_y (m)", "Ly", 6.0, AJUDA["Ly"], minimo=0.5, passo=0.5, alvo=linha[1]
        )
        vaos_x = _inteiro(
            "Vãos em X", "vaos_x", 2, AJUDA["vaos_x"], minimo=1, maximo=20, alvo=linha[2]
        )
        vaos_y = _inteiro(
            "Vãos em Y", "vaos_y", 1, AJUDA["vaos_y"], minimo=1, maximo=20, alvo=linha[3]
        )
        linha = st.columns(4)
        n_pisos = _inteiro(
            "Número de pisos", "n_pisos", 1, AJUDA["n_pisos"], minimo=1, maximo=8, alvo=linha[0]
        )
        h_andar = _numero(
            "Altura do andar (m)",
            "h_andar",
            4.0,
            AJUDA["h_andar"],
            minimo=0.5,
            passo=0.25,
            alvo=linha[1],
        )
        perfis = _perfis_i()
        pilar = _selecao(
            "Perfil dos pilares",
            "pilar",
            perfis,
            AJUDA["pilar"],
            padrao=PILAR_PADRAO,
            alvo=linha[2],
        )
        viga = _selecao(
            "Perfil das vigas", "viga", perfis, AJUDA["viga"], padrao=VIGA_PADRAO, alvo=linha[3]
        )
        guarda = _toggle(
            "Guarda-corpo no perímetro", "guarda_corpo", AJUDA["guarda_corpo"], valor=True
        )
        with st.expander("Ajustes da geometria"):
            texto = st.text_input(
                "Cotas dos pisos (m) — opcional",
                key=_chave("cotas_livres"),
                persist_state="session",
                help=AJUDA["cotas_livres"],
                placeholder="ex.: 3,5; 7,0",
            )
            colunas = st.columns(2)
            altura_gc = _numero(
                "Altura do guarda-corpo (m)",
                "h_gc",
                va.ALTURA_GUARDA_CORPO_PADRAO_M,
                AJUDA["h_gc"],
                minimo=0.1,
                passo=0.05,
                formato="%.2f",
                alvo=colunas[0],
            )
            phi_gc = _numero(
                "Índice φ do guarda-corpo",
                "phi_gc",
                va.INDICE_GUARDA_CORPO_PADRAO,
                AJUDA["phi_gc"],
                minimo=0.01,
                maximo=1.0,
                passo=0.05,
                formato="%.2f",
                alvo=colunas[1],
            )
            area_piso = st.number_input(
                "Área de piso por nível (m²) — opcional",
                min_value=0.0,
                value=None,
                step=0.5,
                format="%.2f",
                placeholder="L_x × L_y",
                key=_chave("area_piso"),
                persist_state="session",
                help=AJUDA["area_piso"],
            )
    cotas = tuple(h_andar * (k + 1) for k in range(n_pisos))
    if texto.strip():
        try:
            cotas = _ler_cotas(texto)
        except ValueError as erro:
            erros.append(str(erro))
    perfil_pilar = sc.obter_perfil(pilar)
    perfil_viga = sc.obter_perfil(viga)
    return DadosEstrutura(
        lx,
        ly,
        cotas,
        vaos_x,
        vaos_y,
        max(perfil_pilar.altura_mm, perfil_pilar.largura_mm) / 1e3,
        perfil_viga.altura_mm / 1e3,
        guarda,
        altura_gc,
        phi_gc,
        float(area_piso) if area_piso else None,
    )


def tabela_equipamentos(erros: list[str]) -> tuple[va.Equipamento, ...]:
    vazia = pd.DataFrame(columns=COLUNAS_EQUIPAMENTOS)
    editada = st.data_editor(
        vazia,
        num_rows="dynamic",
        hide_index=True,
        key=_chave("equipamentos"),
        column_config={
            "Nome": st.column_config.TextColumn(required=True, help="Nome do equipamento."),
            "Nível": st.column_config.NumberColumn(
                min_value=1, step=1, required=True, help="Piso em que ele se apoia (1 = primeiro)."
            ),
            "Forma": st.column_config.SelectboxColumn(
                options=list(va.FORMAS_DE_EQUIPAMENTO),
                required=True,
                help="Cilindro vertical (vaso, tanque) ou caixa/painel.",
            ),
            "Medida em X (m)": st.column_config.NumberColumn(
                min_value=0.0, help="Medida ao longo de X; no cilindro, o diâmetro."
            ),
            "Medida em Y (m)": st.column_config.NumberColumn(
                min_value=0.0, help="Medida ao longo de Y (no cilindro, repita o diâmetro)."
            ),
            "Altura (m)": st.column_config.NumberColumn(
                min_value=0.0, help="Altura acima do piso."
            ),
            "Peso (kN)": st.column_config.NumberColumn(
                min_value=0.0, help="Peso em operação (entra como permanente)."
            ),
            "C_a (vazio = automático)": st.column_config.NumberColumn(
                min_value=0.0, help="Coeficiente de arrasto, se você souber um melhor."
            ),
        },
    )
    equipamentos = []
    for _, linha in editada.iterrows():
        nome = str(linha.get("Nome") or "").strip()
        if not nome:
            continue
        try:
            ca = linha.get("C_a (vazio = automático)")
            equipamentos.append(
                va.Equipamento(
                    nome=nome,
                    nivel=int(linha["Nível"]),
                    forma=str(linha["Forma"] or va.FORMA_CAIXA),
                    dimensao_x_m=float(linha["Medida em X (m)"]),
                    dimensao_y_m=float(linha["Medida em Y (m)"]),
                    altura_m=float(linha["Altura (m)"]),
                    peso_kN=float(linha["Peso (kN)"] or 0.0),
                    ca=None if ca is None or pd.isna(ca) or float(ca) == 0 else float(ca),
                )
            )
        except (TypeError, ValueError):
            erros.append(f"Equipamento {nome}: preencha nível, forma, medidas e altura.")
    return tuple(equipamentos)


def _tabela_forcas(erros: list[str]) -> tuple[cp.ForcaHorizontal, ...]:
    vazia = pd.DataFrame(columns=COLUNAS_FORCAS)
    editada = st.data_editor(
        vazia,
        num_rows="dynamic",
        hide_index=True,
        key=_chave("forcas_horizontais"),
        column_config={
            "Nome": st.column_config.TextColumn(required=True, help="Nome da força."),
            "Direção": st.column_config.SelectboxColumn(
                options=list(cp.DIRECOES), required=True, help="Direção da força em planta."
            ),
            "Nível": st.column_config.NumberColumn(
                min_value=1, step=1, required=True, help="Piso em que ela atua."
            ),
            "Valor (kN)": st.column_config.NumberColumn(help="Valor característico (sem γ)."),
            "Categoria": st.column_config.SelectboxColumn(
                options=list(cp.CATEGORIAS_DE_FORCA_HORIZONTAL),
                required=True,
                help="Define γ e ψ (Tabelas 1 e 2 da NBR 8800).",
            ),
            "Nos dois sentidos": st.column_config.CheckboxColumn(
                default=True, help="Ligado: a força pode atuar nos dois sentidos."
            ),
        },
    )
    forcas = []
    for _, linha in editada.iterrows():
        nome = str(linha.get("Nome") or "").strip()
        if not nome:
            continue
        try:
            forcas.append(
                cp.ForcaHorizontal(
                    nome=nome,
                    direcao=str(linha["Direção"] or "X"),
                    nivel=int(linha["Nível"]),
                    valor_kN=float(linha["Valor (kN)"]),
                    categoria=str(linha["Categoria"] or cp.CATEGORIA_FORCA_HORIZONTAL),
                    reversivel=bool(linha.get("Nos dois sentidos", True)),
                )
            )
        except (TypeError, ValueError):
            erros.append(f"Força {nome}: preencha direção, nível e valor.")
    return tuple(forcas)


def formulario_cargas(
    erros: list[str], base: bt.BaseTecnica | None = None
) -> tuple[cp.Cargas, tuple[va.Equipamento, ...]]:
    with st.container(border=True):
        st.subheader("3. Cargas de cada piso", help=AJUDA["sec_3"])
        linha = st.columns(3)
        pp = _numero(
            "Peso da estrutura (kN/m²)",
            "peso_estrutura",
            0.60,
            AJUDA["peso_estrutura"],
            passo=0.05,
            formato="%.2f",
            alvo=linha[0],
        )
        piso = _numero(
            "Peso do piso (kN/m²)",
            "peso_piso",
            0.45,
            AJUDA["peso_piso"],
            passo=0.05,
            formato="%.2f",
            alvo=linha[1],
        )
        sobrecarga = _numero(
            "Sobrecarga (kN/m²)",
            "sobrecarga",
            base.sobrecarga_kN_m2 if base else 5.0,
            AJUDA["sobrecarga"],
            passo=0.5,
            formato="%.2f",
            alvo=linha[2],
        )
        with st.expander("Equipamentos, outras forças horizontais e categorias"):
            colunas = st.columns(2)
            cat_sc = _selecao(
                "Categoria da sobrecarga",
                "cat_sobrecarga",
                list(cp.CATEGORIAS_DE_SOBRECARGA),
                AJUDA["cat_sobrecarga"],
                padrao=cp.CATEGORIA_SOBRECARGA,
                alvo=colunas[0],
            )
            cat_eq = _selecao(
                "Categoria do peso dos equipamentos",
                "cat_equip",
                list(cp.CATEGORIAS_DE_EQUIPAMENTO),
                AJUDA["cat_equip"],
                alvo=colunas[1],
            )
            st.subheader("Equipamentos", help=AJUDA["equipamentos"])
            equipamentos = tabela_equipamentos(erros)
            st.subheader("Outras forças horizontais", help=AJUDA["forcas_h"])
            forcas = _tabela_forcas(erros)
    return (
        cp.Cargas(
            peso_estrutura_kN_m2=pp,
            peso_piso_kN_m2=piso,
            sobrecarga_kN_m2=sobrecarga,
            categoria_sobrecarga=cat_sc,
            categoria_equipamentos=cat_eq,
            forcas_horizontais=forcas,
        ),
        equipamentos,
    )


CHAVES_DO_VENTO = ("v0", "s1", "categoria", "grupo_s3")


def formulario_vento(
    base: bt.BaseTecnica | None = None, *, titulo: str = "4. Vento (NBR 6123:2023)"
) -> va.ParametrosVento:
    """V₀, S₁, terreno e S₃ — começando com os valores da base técnica do projeto."""
    vento = base.vento if base else bt.VentoDoLocal()
    opcoes = [str(g) for g in vb.GRUPOS_S3]
    if vento.grupo_s3 == bt.S3_DO_CLIENTE and vento.s3_cliente is not None:
        opcoes.append(bt.S3_DO_CLIENTE)

    def rotulo_s3(g: str) -> str:
        if g == bt.S3_DO_CLIENTE:
            return f"Critério do cliente (S₃ = {_pt(vento.s3_cliente or 0.0, 2)})"
        return f"{g} (S₃ = {_pt(vb.GRUPOS_S3[int(g)][0], 2)})"

    with st.container(border=True):
        st.subheader(titulo, help=AJUDA["sec_4"])
        linha = st.columns(4)
        v0 = _numero(
            "V₀ (m/s)",
            "v0",
            vento.v0_m_s,
            AJUDA["v0"],
            minimo=10.0,
            maximo=70.0,
            passo=1.0,
            alvo=linha[0],
        )
        s1 = _numero(
            "S₁",
            "s1",
            vento.s1,
            AJUDA["s1"],
            minimo=0.5,
            maximo=2.0,
            passo=0.05,
            formato="%.2f",
            alvo=linha[1],
        )
        categoria = _selecao(
            "Categoria do terreno",
            "categoria",
            list(vb.CATEGORIAS_RUGOSIDADE),
            AJUDA["categoria"],
            padrao=vento.categoria,
            alvo=linha[2],
        )
        grupo = _selecao(
            "Grupo de S₃",
            "grupo_s3",
            opcoes,
            AJUDA["grupo_s3"],
            formatar=rotulo_s3,
            padrao=vento.grupo_s3 if vento.grupo_s3 in opcoes else "3",
            alvo=linha[3],
        )
        if base is not None:
            botao_recarregar_da_base(
                [_chave(c) for c in CHAVES_DO_VENTO],
                key=_chave("recarregar_vento"),
                ajuda=AJUDA["btn_recarregar"],
            )
    if grupo == bt.S3_DO_CLIENTE:
        return va.ParametrosVento(
            v0_m_s=v0, s1=s1, categoria=categoria, grupo_s3=3, s3=vento.s3_cliente
        )
    return va.ParametrosVento(v0_m_s=v0, s1=s1, categoria=categoria, grupo_s3=int(grupo))


def _usar_cotas_do_esqueleto(niveis: tuple[float, ...]) -> None:
    st.session_state[_chave("cotas_livres")] = "; ".join(_pt(z, 2) for z in niveis)


def formulario_metodo_do_vento(
    estrutura: DadosEstrutura,
    equipamentos: tuple[va.Equipamento, ...],
    vento: va.ParametrosVento,
    erros: list[str],
) -> cvb.VentoDoEsqueleto | None:
    """Pórticos regulares (a grade da seção 2) ou viga a viga, pilar a pilar (o esqueleto do
    modelo); no segundo, o vento já levado aos pisos."""
    with st.container(border=True), secao_protegida("Como o vento chega à estrutura"):
        st.subheader("Como o vento chega à estrutura", help=AJUDA["sec_metodo_vento"])
        metodo = (
            st.segmented_control(
                "Método do vento",
                [METODO_GRADE, METODO_BARRAS],
                default=METODO_GRADE,
                key=_chave("metodo_vento"),
                help=AJUDA["metodo_vento"],
            )
            or METODO_GRADE
        )
        if metodo == METODO_GRADE:
            st.caption(
                "Pórticos regulares: a planta, os vãos e os perfis da seção 2, cada pórtico "
                "perpendicular ao vento como um reticulado, a 0° e 90° (nos dois sentidos)."
            )
            return None
        projeto = obter_projeto_ativo()
        geometria = ld.geometria_do_projeto(projeto)
        if not geometria.corpos:
            st.info(
                "O vento viga a viga usa o esqueleto do modelo: rode a macro do SolidWorks e "
                "envie o …_esqueleto.csv em **Cargas do esqueleto**.",
                icon=":material/account_tree:",
            )
            st.page_link(
                "app_pages/cargas_esqueleto.py",
                label="Abrir Cargas do esqueleto",
                icon=":material/account_tree:",
            )
            erros.append(
                "Vento viga a viga: o projeto ainda não tem o esqueleto do modelo. Envie o "
                "esqueleto em Cargas do esqueleto ou use os pórticos regulares."
            )
            return None
        esforcos = em.esforcos_do_projeto(projeto)
        linha = st.columns([1, 2, 1, 1])
        eixos = ["Y", "Z"]
        eixo = str(
            linha[0].radio(
                "Eixo vertical do modelo",
                eixos,
                index=eixos.index(esforcos.eixo_vertical) if esforcos.eixo_vertical in eixos else 0,
                horizontal=True,
                key=_chave("vb_eixo"),
                help=AJUDA["vb_eixo"],
            )
        )
        quais = linha[1].radio(
            "Direções do vento",
            [DIRECOES_8, DIRECOES_4],
            key=_chave("vb_direcoes"),
            help=AJUDA["vb_direcoes"],
        )
        protecao = _toggle(
            "Proteção entre planos (η)", "vb_protecao", AJUDA["vb_protecao"], valor=True,
            alvo=linha[2],
        )  # fmt: skip
        terreno = linha[3].number_input(
            "Cota do terreno no modelo (m)",
            value=None,
            step=0.1,
            format="%.3f",
            placeholder="o pé dos pilares",
            key=_chave("vb_terreno"),
            help=AJUDA["vb_terreno"],
        )
        guarda_corpos: list[vpb.ElementoAoVento] = []
        if estrutura.guarda_corpo:
            from components.guarda_corpo_ui import escolha_inicial

            escolha = escolha_inicial(projeto)
            bordas = gm.bordas_do_projeto(geometria, eixo, escolha)
            guarda_corpos = gm.elementos_ao_vento(
                bordas.marcados(escolha.trocados), eixo, altura_m=escolha.altura_m, phi=escolha.phi
            )
            st.caption(
                f":material/fence: {len(guarda_corpos)} guarda-corpos nas bordas do piso "
                f"({bordas.metodo}; altura {_pt(escolha.altura_m, 2)} m, φ "
                f"{_pt(escolha.phi, 2)}) — os trechos e a altura se ajustam em **Cargas do "
                "esqueleto › Guarda-corpo nas bordas do piso**."
            )
        nomes = {
            corpo.nome: barra
            for barra, corpo in ld.correspondencia(
                geometria, esforcos.nomes_dos_membros, esforcos
            ).corpos.items()
        }
        try:
            entrada = cvb.entrada_pelo_esqueleto(
                geometria,
                eixo,
                vento,
                cotas_m=estrutura.cotas,
                equipamentos=equipamentos,
                guarda_corpos=guarda_corpos,
                direcoes=(
                    vpb.DIRECOES_COM_DIAGONAIS
                    if quais == DIRECOES_8
                    else vpb.DIRECOES_PERPENDICULARES
                ),
                protecao=bool(protecao),
                cota_do_terreno_m=None if terreno is None else float(terreno),
                nomes_no_simulation=nomes,
            )
            problemas = vpb.validar_entrada(entrada)
            if problemas:
                erros.extend(f"Vento viga a viga: {p}" for p in problemas)
                return None
            r = vpb.calcular(entrada)
            ve = cvb.vento_nos_niveis(
                r, estrutura.cotas, eixo_vertical=eixo, arquivo=geometria.arquivo
            )
        except ValueError as erro:
            erros.append(f"Vento viga a viga: {erro}")
            return None
        px, py = ve.planta_m
        st.caption(
            f":material/account_tree: {geometria.arquivo} · {len(entrada.barras)} barras · "
            f"planta dos pisos {_pt(px, 2)} × {_pt(py, 2)} m · vigas nas cotas "
            + ("; ".join(_pt(z, 2) for z in ve.niveis_do_esqueleto_m) or "—")
            + " m (do terreno)"
        )
        if ve.niveis_do_esqueleto_m and not cvb.cotas_batem(
            ve.niveis_do_esqueleto_m, estrutura.cotas
        ):
            st.button(
                "Usar as cotas do esqueleto nos pisos",
                on_click=_usar_cotas_do_esqueleto,
                args=(ve.niveis_do_esqueleto_m,),
                icon=":material/height:",
                key=_chave("vb_usar_cotas"),
                help=AJUDA["vb_usar_cotas"],
            )
        return ve


def _sistema(
    sufixo: str, titulo: str, alvo: Any, *, com_ligacao: bool = True
) -> cp.SistemaDeContraventamento:
    with alvo:
        if titulo:
            st.markdown(f"**{titulo}**")
        linha = st.columns(3)
        tipo = _selecao(
            "Tipo",
            f"tipo{sufixo}",
            list(cp.TIPOS),
            AJUDA["tipo"],
            formatar=lambda k: cp.TIPOS[k],
            alvo=linha[0],
        )
        linhas = _inteiro(
            "Linhas contraventadas",
            f"linhas{sufixo}",
            2,
            AJUDA["linhas"],
            minimo=1,
            maximo=20,
            alvo=linha[1],
        )
        paineis = _inteiro(
            "Painéis por linha",
            f"paineis{sufixo}",
            1,
            AJUDA["paineis"],
            minimo=1,
            maximo=20,
            alvo=linha[2],
        )
        linha = st.columns(3)
        familia = _selecao(
            "Barra", f"familia{sufixo}", list(cb.FAMILIAS), AJUDA["familia"], alvo=linha[0]
        )
        perfis = cb.perfis_da_familia(familia)
        padrao = 'L 2 1/2" × 1/4"' if familia == cb.FAMILIA_CANTONEIRA else None
        perfil = _selecao(
            "Perfil", f"perfil{sufixo}", perfis, AJUDA["perfil"], padrao=padrao, alvo=linha[1]
        )
        aco = _selecao("Aço", f"aco{sufixo}", list(cb.ACOS), AJUDA["aco"], alvo=linha[2])
        diagonal = cb.Diagonal(familia=familia, perfil=perfil, aco=aco)
        if familia == cb.FAMILIA_BARRA_REDONDA or not com_ligacao:
            return cp.SistemaDeContraventamento(tipo, diagonal, linhas, paineis)
        with st.expander("Ligação da diagonal na chapa de nó"):
            opcoes_ligacao = (
                [cb.LIGACAO_SOLDADA] if familia == cb.FAMILIA_TUBO else list(cb.LIGACOES)
            )
            linha = st.columns(3)
            ligacao = _selecao(
                "Ligação", f"ligacao{sufixo}", opcoes_ligacao, AJUDA["ligacao"], alvo=linha[0]
            )
            t_chapa = _numero(
                "Chapa de nó t (mm)",
                f"t_chapa{sufixo}",
                9.5,
                AJUDA["t_chapa"],
                minimo=3.0,
                passo=0.5,
                formato="%.1f",
                alvo=linha[1],
            )
            aco_chapa = _selecao(
                "Aço da chapa",
                f"aco_chapa{sufixo}",
                list(cb.ACOS),
                AJUDA["aco_chapa"],
                alvo=linha[2],
            )
            if ligacao == cb.LIGACAO_PARAFUSADA:
                linha = st.columns(3)
                parafuso = _selecao(
                    "Parafuso",
                    f"parafuso{sufixo}",
                    list(bc.PARAFUSOS),
                    AJUDA["parafuso"],
                    padrao='5/8"',
                    alvo=linha[0],
                )
                grau = _selecao(
                    "Grau", f"grau{sufixo}", ["A325", "A307", "A490"], AJUDA["grau"], alvo=linha[1]
                )
                n_par = _inteiro(
                    "Nº de parafusos",
                    f"n_parafusos{sufixo}",
                    3,
                    AJUDA["n_parafusos"],
                    minimo=1,
                    maximo=12,
                    alvo=linha[2],
                )
                linha = st.columns(3)
                passo = _numero(
                    "Passo (mm)",
                    f"passo{sufixo}",
                    50.0,
                    AJUDA["passo"],
                    minimo=1.0,
                    passo=5.0,
                    formato="%.0f",
                    alvo=linha[0],
                )
                borda = _numero(
                    "Borda (mm)",
                    f"borda{sufixo}",
                    30.0,
                    AJUDA["borda"],
                    minimo=1.0,
                    passo=1.0,
                    formato="%.0f",
                    alvo=linha[1],
                )
                rosca = _toggle(
                    "Rosca no plano de corte",
                    f"rosca{sufixo}",
                    AJUDA["rosca"],
                    valor=True,
                    alvo=linha[2],
                )
                broca = _toggle(
                    "Furos feitos com broca (área líquida sem os 2 mm)",
                    f"broca{sufixo}",
                    AJUDA["furo_broca"],
                )
                diagonal = cb.Diagonal(
                    familia=familia,
                    perfil=perfil,
                    aco=aco,
                    ligacao=ligacao,
                    parafuso=parafuso,
                    grau=grau,
                    rosca_no_plano=rosca,
                    furo_com_broca=broca,
                    n_parafusos=n_par,
                    passo_mm=passo,
                    borda_mm=borda,
                    t_chapa_no_mm=t_chapa,
                    aco_chapa_no=aco_chapa,
                )
            else:
                linha = st.columns(2)
                comp = _numero(
                    "Comprimento do cordão (mm)",
                    f"comp_solda{sufixo}",
                    120.0,
                    AJUDA["comp_solda"],
                    minimo=10.0,
                    passo=10.0,
                    formato="%.0f",
                    alvo=linha[0],
                )
                perna = _numero(
                    "Perna da solda (mm)",
                    f"perna_solda{sufixo}",
                    5.0,
                    AJUDA["perna_solda"],
                    minimo=3.0,
                    passo=1.0,
                    formato="%.1f",
                    alvo=linha[1],
                )
                diagonal = cb.Diagonal(
                    familia=familia,
                    perfil=perfil,
                    aco=aco,
                    ligacao=ligacao,
                    comprimento_solda_mm=comp,
                    perna_solda_mm=perna,
                    t_chapa_no_mm=t_chapa,
                    aco_chapa_no=aco_chapa,
                )
    return cp.SistemaDeContraventamento(tipo, diagonal, linhas, paineis)


def formulario_contraventamento(
    *, com_ligacao: bool = True, titulo: str = "5. Contraventamento"
) -> tuple[cp.SistemaDeContraventamento, cp.SistemaDeContraventamento]:
    with st.container(border=True):
        st.subheader(titulo, help=AJUDA["sec_5"])
        mesmo = _toggle(
            "Mesmo contraventamento nas duas direções",
            "mesmo_sistema",
            AJUDA["mesmo_sistema"],
            valor=True,
        )
        if mesmo:
            sistema = _sistema("_x", "", st.container(), com_ligacao=com_ligacao)
            return sistema, sistema
        esquerda, direita = st.columns(2)
        sx = _sistema(
            "_x", "Linhas paralelas a X (resistem ao vento em X)", esquerda, com_ligacao=com_ligacao
        )
        sy = _sistema(
            "_y", "Linhas paralelas a Y (resistem ao vento em Y)", direita, com_ligacao=com_ligacao
        )
        return sx, sy


@dataclass(frozen=True)
class Ajustes:
    excentricidade: float
    cruzamento: bool
    combinacao_servico: str
    tipo_de_estrutura: str = ""
    criterio_anglo: bool = False


TIPO_NBR = ""


def formulario_ajustes(base: bt.BaseTecnica | None = None) -> Ajustes:
    with st.container(border=True):
        st.subheader("6. Ajustes do cálculo", help=AJUDA["sec_6"])
        linha = st.columns(3)
        exc = _numero(
            "Excentricidade (%)",
            "excentricidade",
            7.5,
            AJUDA["excentricidade"],
            maximo=50.0,
            passo=0.5,
            formato="%.1f",
            alvo=linha[0],
        )
        cruz = _toggle(
            "X ligado no cruzamento", "cruzamento", AJUDA["cruzamento"], valor=True, alvo=linha[1]
        )
        servico = _selecao(
            "Combinação dos deslocamentos",
            "comb_servico",
            list(reg.estados_disponiveis()),
            AJUDA["comb_servico"],
            alvo=linha[2],
        )
        linha = st.columns(2)
        tipos = [TIPO_NBR, *bt.TIPOS_DE_ESTRUTURA]
        tipo = _selecao(
            "Limite do deslocamento",
            "tipo_estrutura",
            tipos,
            AJUDA["tipo_estrutura"],
            formatar=lambda k: k or "NBR 8800, Tabela B.1 (pelo número de pisos)",
            padrao=base.tipo_de_estrutura if base else TIPO_NBR,
            alvo=linha[0],
        )
        anglo = _toggle(
            "Aplicar o critério Anglo AA-BR-DPST-DR-0001",
            "criterio_anglo",
            AJUDA["criterio_anglo"],
            valor=bool(base and base.anglo),
            alvo=linha[1],
        )
    return Ajustes(exc / 100.0, cruz, servico, tipo, anglo)


# ---------------------------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------------------------
def _resumo(r: cp.ResultadoContraventamento) -> None:
    colunas = st.columns(5)
    colunas[0].metric("Status geral", r.status, help=AJUDA["res_status"])
    colunas[1].metric(
        "Aproveitamento máximo",
        f"{_pt(100 * r.aproveitamento_maximo, 0)} %",
        help=AJUDA["res_aproveitamento"],
    )
    colunas[2].metric(
        "Vento X / Y (kN)",
        f"{_pt(r.vento_total_kN('X'))} / {_pt(r.vento_total_kN('Y'))}",
        help=AJUDA["res_vento"],
    )
    colunas[3].metric("B₂ máximo", _pt(max(a.b2 for a in r.andares), 3), help=AJUDA["res_b2"])
    colunas[4].metric(
        "Deslocamento do topo (mm)",
        _pt(max(r.deslocamento_topo_mm.values()), 2),
        help=AJUDA["res_desloc"],
    )
    contagem = {s: 0 for s in ("OK", "NÃO OK", "ALERTA", "INFO", "N/A")}
    for v in r.verificacoes:
        contagem[v.status] = contagem.get(v.status, 0) + 1
    st.caption(" · ".join(f"{contagem[s]} {s}" for s in contagem))
    for aviso in r.avisos:
        st.warning(aviso, icon=":material/warning:")


def _aba_verificacoes(r: cp.ResultadoContraventamento) -> None:
    st.subheader(f"As {len(r.verificacoes)} verificações", help=AJUDA["res_verificacoes"])
    so = _toggle(
        "Mostrar só o que merece atenção (NÃO OK, ALERTA e N/A)", "so_atencao", AJUDA["so_atencao"]
    )
    linhas = [v for v in r.verificacoes if not so or v.status in ("NÃO OK", "ALERTA", "N/A")]
    mostrar_tabela_verificacoes(linhas)
    st.subheader("Exportar", help=AJUDA["res_exportar"])
    st.download_button(
        "Verificações em CSV",
        data=reg.csv_das_verificacoes(r),
        file_name="contraventamento_verificacoes.csv",
        mime="text/csv",
        icon=":material/download:",
        key=_chave("baixar_csv"),
        help=AJUDA["btn_csv"],
    )


def _tabela(tabela: dict[str, Any]) -> None:
    st.dataframe(
        pd.DataFrame(tabela["linhas"], columns=tabela["cabecalhos"]),
        hide_index=True,
        width="stretch",
    )
    st.caption(tabela["legenda"])


def grafico_do_cortante(andares: list[cp.AndarNaDirecao]) -> alt.Chart:
    dados = pd.DataFrame(
        [
            {
                "Andar": f"{a.direcao} — andar {a.andar}",
                "Direção": a.direcao,
                "Cortante (kN)": abs(a.cortante_elu.valor),
                "Na linha mais carregada (kN)": a.forca_na_linha_kN,
            }
            for a in andares
        ]
    )
    return (
        alt.Chart(dados)
        .mark_bar()
        .encode(
            x=alt.X("Cortante (kN):Q"),
            y=alt.Y("Andar:N", sort=None),
            color=alt.Color("Direção:N", scale=alt.Scale(range=["#1f6feb", "#d4760a"])),
            tooltip=["Andar", "Cortante (kN)", "Na linha mais carregada (kN)"],
        )
        .properties(height=40 + 34 * len(andares))
    )


def _aba_desenhos(r: cp.ResultadoContraventamento) -> None:
    e = r.entrada
    st.subheader("Planta", help=AJUDA["res_desenhos"])
    st.image(svg_planta(e), width="stretch")
    direcao = st.radio(
        "Direção",
        list(cp.DIRECOES),
        key=_chave("desenho_direcao"),
        horizontal=True,
        help=AJUDA["desenho_direcao"],
    )
    st.subheader(f"Elevação da linha contraventada — {direcao}", help=AJUDA["res_desenhos"])
    st.image(svg_elevacao_linha(e, r.andares_da_direcao(direcao), direcao), width="stretch")
    ve = e.vento_do_esqueleto
    if ve is not None:
        angulo = 0 if direcao == "X" else 90
        st.subheader(f"Vento W{angulo} viga a viga", help=AJUDA["res_vento_3d"])
        st.image(
            svg_vento_3d(ve.resultado, angulo, eixo_vertical=ve.eixo_vertical), width="stretch"
        )
    else:
        st.subheader(f"Vento em {direcao} nos pórticos", help=AJUDA["res_vento_niveis"])
        st.image(
            svg_vento_elevacao(cp.geometria_do_vento(e), r.vento.direcao(direcao)),
            width="stretch",
        )
    st.subheader("Cortante de cálculo por andar", help=AJUDA["res_cortante"])
    st.altair_chart(grafico_do_cortante(list(r.andares)), width="stretch")


def _metros(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def mostrar_vento_simplificado(
    geometria: va.GeometriaAberta, resultado: va.ResultadoVentoAberto, *, ajuda: str
) -> None:
    """A carga de cada nível na forma simplificada, nas duas direções."""
    st.subheader("Vento simplificado: uma carga por nível", help=ajuda)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Direção": f"+{c.direcao} (W0)" if c.direcao == "X" else f"+{c.direcao} (W90)",
                    "Nível": c.nivel,
                    "Cota (m)": c.cota_m,
                    "Total do nível (kN)": c.total_kN,
                    "Vigas na direção do vento": f"{c.linhas} linhas × {_metros(c.comprimento_m)} m",
                    "q (kN/m)": c.q_kN_m,
                    "q (N/m)": c.q_kN_m * 1e3,
                }
                for d in (resultado.x, resultado.y)
                for c in va.cargas_simplificadas(geometria, d)
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Cota (m)": st.column_config.NumberColumn(format="%.2f"),
            "Total do nível (kN)": st.column_config.NumberColumn(format="%.2f"),
            "q (kN/m)": st.column_config.NumberColumn(format="%.3f"),
            "q (N/m)": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.caption(
        "W180 e W270 são as mesmas cargas com o sinal trocado. A faixa da base (meio primeiro "
        "andar) vai direto à fundação e os equipamentos ficam como força no centro deles."
    )


def _comparacao_com_a_grade(r: cp.ResultadoContraventamento) -> pd.DataFrame:
    ve = r.entrada.vento_do_esqueleto
    assert ve is not None
    linhas = []
    for d in cp.DIRECOES:
        grade = r.vento.direcao(d).cortantes_dos_andares_kN
        for i in range(1, len(r.entrada.cotas_m) + 1):
            barras = ve.maior_cortante_kN(d, i)
            linhas.append(
                {
                    "Direção / andar": f"{d} / {i}",
                    "Pórticos regulares (kN)": grade[i - 1],
                    "Viga a viga (kN)": barras,
                    "Diferença (%)": 100.0 * (barras / grade[i - 1] - 1.0)
                    if grade[i - 1]
                    else None,
                }
            )
    return pd.DataFrame(linhas)


def _aba_vento_por_barras(r: cp.ResultadoContraventamento) -> None:
    ve = r.entrada.vento_do_esqueleto
    assert ve is not None
    tabelas = reg.tabelas_para_memorial(r)
    st.subheader("Vento por nível, caso a caso", help=AJUDA["res_vento_casos"])
    _tabela(tabelas[0])
    st.subheader("Pórticos regulares × viga a viga", help=AJUDA["res_comparacao"])
    st.dataframe(
        _comparacao_com_a_grade(r),
        hide_index=True,
        width="stretch",
        column_config={
            c: st.column_config.NumberColumn(format="%.2f")
            for c in ("Pórticos regulares (kN)", "Viga a viga (kN)")
        }
        | {"Diferença (%)": st.column_config.NumberColumn(format="%+.0f")},
    )
    reais = ", ".join(
        f"{d}: {_pt(100 * ve.excentricidade_real.get(d, 0.0), 1)} %" for d in cp.DIRECOES
    )
    st.caption(
        "Cortante característico de cada andar (o maior entre os casos). Excentricidade da "
        f"resultante do vento viga a viga (da dimensão perpendicular): {reais}; a distribuição "
        "entre as linhas soma a excentricidade informada nos ajustes."
    )
    angulos = [c.angulo for c in ve.casos]
    angulo = st.radio(
        "Direção mostrada",
        angulos,
        format_func=lambda a: f"W{a} ({vpb.SENTIDOS.get(a, '')})",
        horizontal=True,
        key=_chave("vb_ver"),
        help=AJUDA["vb_ver"],
    )
    with secao_protegida("Desenho 3D do vento no contraventamento"):
        st.image(
            svg_vento_3d(ve.resultado, int(angulo), eixo_vertical=ve.eixo_vertical),
            width="stretch",
        )
    st.subheader("Reticulados (planos perpendiculares ao vento)", help=AJUDA["res_planos"])
    _tabela(tabelas[1])
    colunas = st.columns(2)
    colunas[0].download_button(
        "Cargas nas barras (CSV)",
        data=vpb.csv_das_cargas(ve.resultado),
        file_name="contraventamento_vento_barra_a_barra.csv",
        mime="text/csv",
        icon=":material/download:",
        key=_chave("vb_csv"),
        help=AJUDA["btn_csv_barras"],
        width="stretch",
    )
    codigos = ", ".join(c.codigo for c in ve.casos)
    if colunas[1].button(
        "Enviar ao plano de cargas",
        icon=":material/table_chart:",
        key=_chave("vb_para_plano"),
        help=AJUDA["btn_plano_barras"],
        width="stretch",
    ) and gravar_plano(
        vpb.plano_com_o_vento(plano_ativo(), ve.resultado),
        f"Plano de cargas: {codigos} do vento barra a barra (contraventamento)",
    ):
        st.success(f"{codigos} gravados no plano de cargas.", icon=":material/check_circle:")
    st.caption(" · ".join(ve.resultado.vento_no_topo.memoria))


def _aba_vento(r: cp.ResultadoContraventamento) -> None:
    if r.vento_por_barras:
        _aba_vento_por_barras(r)
        return
    tabelas = reg.tabelas_para_memorial(r)
    st.subheader("Vento por nível", help=AJUDA["res_vento_niveis"])
    _tabela(tabelas[0])
    st.subheader("Forças nos nós de cada pórtico (para o modelo)", help=AJUDA["res_nos"])
    nos = var.tabelas_para_memorial(r.vento)[2]
    _tabela(nos)
    forma = st.radio(
        "Como aplicar o vento no modelo",
        var.FORMAS,
        key=_chave("forma_do_vento"),
        help=AJUDA["forma"],
    )
    if forma == var.FORMA_SIMPLIFICADA:
        mostrar_vento_simplificado(r.vento.geometria, r.vento, ajuda=AJUDA["res_simplificada"])
    if st.button(
        "Enviar o vento ao plano de cargas (W0, W90, W180, W270)",
        icon=":material/table_chart:",
        key=_chave("vento_para_plano"),
        help=AJUDA["btn_plano"],
    ) and gravar_acoes_no_plano(
        var.acoes_para_o_plano(r.vento, forma=forma),
        origem="Contraventamento de estruturas abertas",
    ):
        st.success("Vento gravado no plano de cargas do projeto.", icon=":material/check_circle:")
    st.caption(" · ".join(r.vento.vento_no_topo.memoria))
    st.subheader("Pórticos (reticulados)", help=AJUDA["res_porticos"])
    _tabela(tabelas[1])
    detalhes = [*r.vento.x.detalhes_equipamentos, *r.vento.y.detalhes_equipamentos]
    if detalhes:
        st.caption("\n".join(f"- {t}" for t in detalhes))


def _aba_combinacoes(r: cp.ResultadoContraventamento) -> None:
    tabelas = reg.tabelas_para_memorial(r)
    st.subheader("Ações e coeficientes", help=AJUDA["res_acoes"])
    _tabela(tabelas[2])
    st.subheader("Andares — envoltória rigorosa", help=AJUDA["res_andares"])
    _tabela(tabelas[3])
    st.subheader("Lista de combinações", help=AJUDA["res_lista"])
    efeitos = [f"V_{a.direcao}_{a.andar}" for a in r.andares]
    lista = comb.gerar_combinacoes(r.acoes, comb.ESTADOS_PADRAO)
    linhas = []
    for c in lista:
        linha: dict[str, Any] = {"Combinação": c.nome, "Expressão": c.expressao}
        for efeito, a in zip(efeitos, r.andares, strict=True):
            chave = (
                efeito
                if c.estado_limite in comb.COMBINACOES_ULTIMAS
                else (f"S_{a.direcao}_{a.andar}")
            )
            linha[f"V {a.direcao}{a.andar} (kN)"] = c.valor(r.acoes, chave)
        linhas.append(linha)
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch", height=360)


def _aba_ligacao(r: cp.ResultadoContraventamento) -> None:
    forcas = cp.forcas_para_ligacao(r)
    st.subheader("Forças para a chapa de nó", help=AJUDA["res_ligacao"])
    colunas = st.columns(3)
    colunas[0].metric(
        f"Tração ({forcas.direcao}, andar {forcas.andar})",
        f"{_pt(forcas.tracao_kN)} kN",
        help=AJUDA["res_ligacao"],
    )
    colunas[1].metric("Compressão", f"{_pt(forcas.compressao_kN)} kN", help=AJUDA["res_ligacao"])
    colunas[2].metric(
        "Ângulo com a vertical", f"{_pt(forcas.theta_vertical_graus)}°", help=AJUDA["res_ligacao"]
    )
    st.caption(
        "Forças de cálculo pela NBR 8800 (ELU). A página Ligação de contraventamento verifica a "
        "chapa pelo AISC 360-16 em LRFD: os coeficientes de ponderação das duas normas são "
        "parecidos, mas não iguais — confira o critério do projeto."
    )
    if st.button(
        "Levar para a Ligação de contraventamento",
        icon=":material/hub:",
        key=_chave("levar_ligacao"),
        help=AJUDA["btn_ligacao"],
    ):
        st.session_state["cv_P_tracao"] = round(forcas.tracao_kN, 1)
        st.session_state["cv_P_compressao"] = round(forcas.compressao_kN, 1)
        st.session_state["cv_theta"] = round(forcas.theta_vertical_graus, 2)
        st.session_state["cv_metodo"] = "LRFD"
        st.session_state["cv_criterio_anglo"] = r.entrada.criterio_anglo
        st.switch_page("app_pages/ligacao_contraventamento.py")


def _registrar(r: cp.ResultadoContraventamento, ident: Identificacao) -> None:
    contexto: dict[str, Any] = {"data_do_calculo": ident.data.isoformat()}
    if ident.obra:
        contexto["obra"] = ident.obra
    if ident.tag:
        contexto["tag"] = ident.tag
    registro = reg.registro_contraventamento(r, contexto=contexto, responsavel=ident.responsavel)
    with st.container(border=True):
        st.subheader("Registrar no projeto", help=AJUDA["reg_registrar"])
        botao_registrar_calculo(
            registro,
            key="registrar_contraventamento_estrutura",
            rotulo="Registrar o contraventamento no projeto ativo",
        )


def mostrar_contraventamento_de_estrutura() -> None:
    fronteira_modelo(list(reg.FORA_DO_ESCOPO), titulo="O que esta página não faz")
    base = base_ativa()
    legenda_da_base(base)
    erros: list[str] = []
    ident = formulario_identificacao()
    esqueleto = esqueleto_do_projeto()
    estrutura = formulario_estrutura(erros, esqueleto)
    cargas, equipamentos = formulario_cargas(erros, base)
    vento = formulario_vento(base)
    vento_do_esqueleto = formulario_metodo_do_vento(estrutura, equipamentos, vento, erros)
    sx, sy = formulario_contraventamento()
    ajustes = formulario_ajustes(base)
    if erros:
        for erro in erros:
            st.error(erro, icon=":material/error:")
        st.stop()
    entrada = cp.EntradaContraventamento(
        comprimento_x_m=estrutura.comprimento_x,
        largura_y_m=estrutura.largura_y,
        cotas_m=estrutura.cotas,
        vaos_x=estrutura.vaos_x,
        vaos_y=estrutura.vaos_y,
        largura_pilar_m=estrutura.largura_pilar_m,
        altura_viga_m=estrutura.altura_viga_m,
        guarda_corpo=estrutura.guarda_corpo,
        altura_guarda_corpo_m=estrutura.altura_gc,
        indice_guarda_corpo=estrutura.phi_gc,
        equipamentos=equipamentos,
        vento=vento,
        cargas=cargas,
        contraventamento_x=sx,
        contraventamento_y=sy,
        excentricidade=ajustes.excentricidade,
        ligadas_no_cruzamento=ajustes.cruzamento,
        combinacao_de_servico=ajustes.combinacao_servico,
        criterio_anglo=ajustes.criterio_anglo,
        tipo_de_estrutura=ajustes.tipo_de_estrutura,
        vento_do_esqueleto=vento_do_esqueleto,
        area_de_piso_m2=estrutura.area_de_piso_m2,
    )
    problemas = cp.validar_entrada(entrada)
    if problemas:
        for erro in problemas:
            st.error(erro, icon=":material/error:")
        st.stop()
    try:
        resultado = cp.calcular(entrada)
    except (ValueError, ZeroDivisionError) as erro:
        st.error(f"Não foi possível calcular: {erro}", icon=":material/error:")
        st.stop()
    st.header("Resultados")
    if esqueleto is not None:
        diferencas = cesq.conferir_com_a_pagina(esqueleto, entrada)
        avisos_do_esqueleto = [
            *esqueleto.avisos,
            *(
                [
                    "A página está diferente do esqueleto do modelo: "
                    + "; ".join(diferencas)
                    + ". Use “Preencher pelo esqueleto” (seção 2) ou confira."
                ]
                if diferencas
                else []
            ),
        ]
        for aviso in avisos_do_esqueleto:
            st.warning(aviso, icon=":material/account_tree:")
    _resumo(resultado)
    abas = st.tabs(["Desenhos", "Verificações", "Vento", "Combinações e andares", "Ligação"])
    with abas[0]:
        _aba_desenhos(resultado)
    with abas[1]:
        _aba_verificacoes(resultado)
    with abas[2]:
        _aba_vento(resultado)
    with abas[3]:
        _aba_combinacoes(resultado)
    with abas[4]:
        _aba_ligacao(resultado)
    st.subheader("Referências", help=AJUDA["res_avisos"])
    st.caption("\n".join(f"- {item}" for item in reg.REFERENCIAS))
    _registrar(resultado, ident)
