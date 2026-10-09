"""Interface da página Contraventamento de estruturas abertas.

Só desenha: o cálculo está em :mod:`core.contraventamento_plataforma` (vento em
:mod:`core.vento_estrutura_aberta`, combinações em :mod:`core.load_combinations`, diagonais em
:mod:`core.contraventamento_barras`) e o registro em :mod:`core.contraventamento_estrutura_registro`.
Poucos campos à vista, com os valores usuais; o resto fica em "Ajustes". Entrada impossível vira
erro claro — nada é corrigido em silêncio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from components.contraventamento_estrutura_help import AJUDA
from components.project_tools import botao_registrar_calculo
from components.ui import fronteira_modelo
from components.verification_table import mostrar_tabela_verificacoes
from core import bolted_connection as bc
from core import contraventamento_barras as cb
from core import contraventamento_estrutura_registro as reg
from core import contraventamento_plataforma as cp
from core import load_combinations as comb
from core import section_catalog as sc
from core import steel_sections as ss
from core import vento_estrutura_aberta as va
from core import vento_nbr6123 as vb

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


def _pt(valor: float, casas: int = 1) -> str:
    if not math.isfinite(valor):
        return "∞"
    return f"{valor:.{casas}f}".replace(".", ",")


def _chave(nome: str) -> str:
    return PREFIXO + nome


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
            value=valor,
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
        alvo.toggle(rotulo, value=valor, key=_chave(chave), persist_state="session", help=ajuda)
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


def formulario_estrutura(erros: list[str]) -> DadosEstrutura:
    with st.container(border=True):
        st.subheader("2. Estrutura", help=AJUDA["sec_2"])
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
    )


def _tabela_equipamentos(erros: list[str]) -> tuple[va.Equipamento, ...]:
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


def formulario_cargas(erros: list[str]) -> tuple[cp.Cargas, tuple[va.Equipamento, ...]]:
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
            5.0,
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
            equipamentos = _tabela_equipamentos(erros)
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


def formulario_vento() -> va.ParametrosVento:
    with st.container(border=True):
        st.subheader("4. Vento (NBR 6123:2023)", help=AJUDA["sec_4"])
        linha = st.columns(4)
        v0 = _numero(
            "V₀ (m/s)", "v0", 35.0, AJUDA["v0"], minimo=10.0, maximo=70.0, passo=1.0, alvo=linha[0]
        )
        s1 = _numero(
            "S₁",
            "s1",
            1.0,
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
            padrao="III",
            alvo=linha[2],
        )
        grupo = _selecao(
            "Grupo de S₃",
            "grupo_s3",
            [str(g) for g in vb.GRUPOS_S3],
            AJUDA["grupo_s3"],
            formatar=lambda g: f"{g} (S₃ = {_pt(vb.GRUPOS_S3[int(g)][0], 2)})",
            padrao="3",
            alvo=linha[3],
        )
    return va.ParametrosVento(v0_m_s=v0, s1=s1, categoria=categoria, grupo_s3=int(grupo))


def _sistema(sufixo: str, titulo: str, alvo: Any) -> cp.SistemaDeContraventamento:
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
        if familia == cb.FAMILIA_BARRA_REDONDA:
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
                diagonal = cb.Diagonal(
                    familia=familia,
                    perfil=perfil,
                    aco=aco,
                    ligacao=ligacao,
                    parafuso=parafuso,
                    grau=grau,
                    rosca_no_plano=rosca,
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


def formulario_contraventamento() -> tuple[
    cp.SistemaDeContraventamento, cp.SistemaDeContraventamento
]:
    with st.container(border=True):
        st.subheader("5. Contraventamento", help=AJUDA["sec_5"])
        mesmo = _toggle(
            "Mesmo contraventamento nas duas direções",
            "mesmo_sistema",
            AJUDA["mesmo_sistema"],
            valor=True,
        )
        if mesmo:
            sistema = _sistema("_x", "", st.container())
            return sistema, sistema
        esquerda, direita = st.columns(2)
        sx = _sistema("_x", "Linhas paralelas a X (resistem ao vento em X)", esquerda)
        sy = _sistema("_y", "Linhas paralelas a Y (resistem ao vento em Y)", direita)
        return sx, sy


@dataclass(frozen=True)
class Ajustes:
    excentricidade: float
    cruzamento: bool
    combinacao_servico: str


def formulario_ajustes() -> Ajustes:
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
    return Ajustes(exc / 100.0, cruz, servico)


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
        f"{_pt(r.vento.x.total_kN)} / {_pt(r.vento.y.total_kN)}",
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


def _aba_vento(r: cp.ResultadoContraventamento) -> None:
    tabelas = reg.tabelas_para_memorial(r)
    st.subheader("Vento por nível", help=AJUDA["res_vento_niveis"])
    _tabela(tabelas[0])
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
    erros: list[str] = []
    ident = formulario_identificacao()
    estrutura = formulario_estrutura(erros)
    cargas, equipamentos = formulario_cargas(erros)
    vento = formulario_vento()
    sx, sy = formulario_contraventamento()
    ajustes = formulario_ajustes()
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
    _resumo(resultado)
    abas = st.tabs(["Verificações", "Vento", "Combinações e andares", "Ligação"])
    with abas[0]:
        _aba_verificacoes(resultado)
    with abas[1]:
        _aba_vento(resultado)
    with abas[2]:
        _aba_combinacoes(resultado)
    with abas[3]:
        _aba_ligacao(resultado)
    st.subheader("Referências", help=AJUDA["res_avisos"])
    st.caption("\n".join(f"- {item}" for item in reg.REFERENCIAS))
    _registrar(resultado, ident)
