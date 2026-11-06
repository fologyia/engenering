"""Catálogo de todos os casos do Assistente de cargas, por área e por grupo."""

from __future__ import annotations

from dataclasses import dataclass

from core import (
    elementos_barras,
    elementos_eixos,
    elementos_estatica,
    elementos_icamento,
    elementos_mancais,
    elementos_molas,
    elementos_molas_atrito,
    elementos_parafusos,
    elementos_pinos,
    elementos_rotativos,
    elementos_secoes,
    elementos_transmissao,
    elementos_vigas,
)
from core.elementos_base import Caso

AREA_ESTATICA = "Estática e resistência"
AREA_MAQUINAS = "Elementos de máquinas"
AREA_SECOES = "Seção e tensão no ponto"
AREAS = (AREA_ESTATICA, AREA_MAQUINAS, AREA_SECOES)

_DE_ESTATICA: tuple[Caso, ...] = (
    *elementos_parafusos.CASOS,
    *elementos_vigas.CASOS,
    *elementos_barras.CASOS,
    *elementos_estatica.CASOS,
)
_DE_MAQUINAS: tuple[Caso, ...] = (
    *elementos_transmissao.CASOS,
    *elementos_eixos.CASOS,
    *elementos_mancais.CASOS,
    *elementos_molas_atrito.CASOS,
    *elementos_molas.CASOS,
    *elementos_icamento.CASOS,
    *elementos_rotativos.CASOS,
)
_DE_SECOES: tuple[Caso, ...] = (*elementos_secoes.CASOS, *elementos_pinos.CASOS)

CASOS: dict[str, Caso] = {caso.id: caso for caso in (*_DE_ESTATICA, *_DE_MAQUINAS, *_DE_SECOES)}

#: Grupos por área, na ordem em que aparecem; cada grupo lista os ids dos casos.
GRUPOS: dict[str, dict[str, list[str]]] = {area: {} for area in AREAS}
for area, casos in (
    (AREA_ESTATICA, _DE_ESTATICA),
    (AREA_MAQUINAS, _DE_MAQUINAS),
    (AREA_SECOES, _DE_SECOES),
):
    for caso in casos:
        GRUPOS[area].setdefault(caso.grupo, []).append(caso.id)


@dataclass(frozen=True)
class InfoDaArea:
    icone: str
    descricao: str


@dataclass(frozen=True)
class InfoDoGrupo:
    icone: str
    descricao: str


@dataclass(frozen=True)
class Atalho:
    """Um cartão do início do painel: uma pergunta do dia a dia que abre um caso."""

    caso: str
    pergunta: str
    detalhe: str
    icone: str


AREAS_INFO = {
    AREA_ESTATICA: InfoDaArea(
        ":material/balance:",
        "Parafusos, roscas, vigas, barras e perfis: as forças que chegam e se a peça aguenta.",
    ),
    AREA_MAQUINAS: InfoDaArea(
        ":material/settings:",
        "Do motor ao mancal: cada caso verifica uma peça e entrega o resultado para a próxima.",
    ),
    AREA_SECOES: InfoDaArea(
        ":material/target:",
        "Transforma esforços em tensões, para levar ao Círculo de Mohr ou à Análise estática.",
    ),
}

GRUPOS_INFO = {
    elementos_parafusos.GRUPO: InfoDoGrupo(
        ":material/hardware:", "Tração, arrancamento da rosca, torque de aperto e grupos."
    ),
    elementos_vigas.GRUPO: InfoDoGrupo(
        ":material/straighten:", "Reações, momentos, flecha e flexão de perfis."
    ),
    elementos_barras.GRUPO: InfoDoGrupo(
        ":material/architecture:", "Força axial, torção, flambagem, treliças e pórticos."
    ),
    elementos_estatica.GRUPO: InfoDoGrupo(
        ":material/category:", "Equilíbrio, propriedades de seção e chapas furadas."
    ),
    elementos_transmissao.GRUPO: InfoDoGrupo(
        ":material/settings_input_component:",
        "Motor, redutor, engrenagens, correia, corrente e flange.",
    ),
    elementos_eixos.GRUPO: InfoDoGrupo(
        ":material/horizontal_rule:", "Eixo inteiro, seção à fadiga, chaveta e ajuste prensado."
    ),
    elementos_mancais.GRUPO: InfoDoGrupo(
        ":material/motion_blur:", "Rolamento, bucha, pino e contato de Hertz."
    ),
    elementos_molas_atrito.GRUPO_MOLAS: InfoDoGrupo(
        ":material/compress:", "Compressão, tração, torção e prato: rigidez, tensão e fadiga."
    ),
    elementos_molas_atrito.GRUPO_ATRITO: InfoDoGrupo(
        ":material/album:", "Freio, embreagem e parafuso de potência."
    ),
    elementos_icamento.GRUPO: InfoDoGrupo(
        ":material/anchor:", "Ações, cabo, roda, mecanismo, gancho e olhal."
    ),
    elementos_rotativos.GRUPO_ROTATIVOS: InfoDoGrupo(
        ":material/vibration:", "Balanceamento, base de máquina e volante."
    ),
    elementos_rotativos.GRUPO_FLUIDO: InfoDoGrupo(
        ":material/water_drop:", "Cilindro hidráulico e tampas sob pressão."
    ),
    elementos_secoes.GRUPO_BARRAS: InfoDoGrupo(
        ":material/linear_scale:", "Força axial, excentricidade e tirantes."
    ),
    elementos_secoes.GRUPO_EIXOS: InfoDoGrupo(
        ":material/rotate_right:", "Torção e flexão em eixos, e tensão no fio da mola."
    ),
    elementos_secoes.GRUPO_VIGAS: InfoDoGrupo(
        ":material/crop_landscape:", "Flexão, oblíqua e cortante em seções cheias."
    ),
    elementos_secoes.GRUPO_PERFIS: InfoDoGrupo(
        ":material/view_column:", "Perfis I, U, L e tubos, ponto a ponto da seção."
    ),
    elementos_secoes.GRUPO_LIGACOES: InfoDoGrupo(
        ":material/push_pin:", "Vários planos de corte, pino em balanço e pino transversal."
    ),
    elementos_secoes.GRUPO_PRESSAO: InfoDoGrupo(
        ":material/propane_tank:", "Paredes finas, paredes grossas e esferas."
    ),
}

ATALHOS: tuple[Atalho, ...] = (
    Atalho(
        "parafuso_axial",
        "O parafuso aguenta a força?",
        "Tração com ou sem pré-carga, e a menor rosca que atende.",
        ":material/hardware:",
    ),
    Atalho(
        "rosca_arrancamento",
        "A rosca vai espanar?",
        "Quanto engrenar na peça para o parafuso romper antes.",
        ":material/rotate_right:",
    ),
    Atalho(
        "viga_reacoes",
        "Reações, momentos e flecha",
        "Escolha os apoios e as cargas e veja os diagramas.",
        ":material/straighten:",
    ),
    Atalho(
        "perfil_nbr8800",
        "O perfil aguenta a flexão?",
        "Momento resistente pela NBR 8800, com flambagem lateral.",
        ":material/view_column:",
    ),
    Atalho(
        "barra_axial",
        "Barra puxada ou comprimida",
        "Tensão, alongamento e reações, com trechos diferentes.",
        ":material/swap_horiz:",
    ),
    Atalho(
        "acionamento",
        "Do motor ao mancal",
        "Comece pela potência e siga peça por peça.",
        ":material/settings:",
    ),
)

CASO_PADRAO = elementos_parafusos.CASOS[0].id

#: Rótulos usados em versões antigas continuam valendo como entrada.
ALIASES = {"Seção I sob força axial e flexão": elementos_secoes.MODELO_SECAO_I}


def existe(valor: object) -> bool:
    """Diz se o valor abre um caso, direto ou por um rótulo antigo."""
    return isinstance(valor, str) and ALIASES.get(valor, valor) in CASOS


def resolver(valor: object) -> str:
    """Normaliza o id que vem de outra página ou de uma sessão antiga."""
    if isinstance(valor, str):
        valor = ALIASES.get(valor, valor)
        if valor in CASOS:
            return str(valor)
    return CASO_PADRAO


def area_do_caso(caso_id: str) -> str:
    for area, grupos in GRUPOS.items():
        if any(caso_id in ids for ids in grupos.values()):
            return area
    return AREA_SECOES


def info_do_grupo(grupo: str) -> InfoDoGrupo:
    return GRUPOS_INFO[grupo]
