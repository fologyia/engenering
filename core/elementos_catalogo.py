"""Catálogo de todos os casos do Cálculo de peças, por área e por grupo.

O painel se organiza pela peça que a pessoa tem na mão, e não pelo livro de onde a conta saiu:
:data:`PAINEL` diz a área, o grupo e a ordem de cada caso. O grupo que vale é o daqui (o do módulo
do caso é só o de origem), e um caso novo que não entrar no painel derruba a importação.

Padrão dos nomes: o nome técnico do cálculo, como nos livros e nas normas (Arrancamento de rosca,
Flambagem de coluna, Seleção de rolamento), nunca uma pergunta; peça no singular, sem dois-pontos;
o esforço vem com "sob"; parênteses só para o outro nome da peça ou para a norma.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace

from core import (
    elementos_barras,
    elementos_eixos,
    elementos_estatica,
    elementos_icamento,
    elementos_impacto,
    elementos_lingas,
    elementos_mancais,
    elementos_molas,
    elementos_molas_atrito,
    elementos_parafusos,
    elementos_pinos,
    elementos_rotativos,
    elementos_secoes,
    elementos_soldas,
    elementos_transmissao,
    elementos_vigas,
)
from core.elementos_base import Caso

AREA_FIXACAO = "Parafusos, pinos e soldas"
AREA_BARRAS = "Barras, vigas e perfis"
AREA_MAQUINAS = "Elementos de máquinas"
AREA_ICAMENTO = "Içamento e pressão"
AREAS = (AREA_FIXACAO, AREA_BARRAS, AREA_MAQUINAS, AREA_ICAMENTO)

#: Área → grupo → casos, na ordem em que aparecem no painel.
PAINEL: dict[str, dict[str, tuple[str, ...]]] = {
    AREA_FIXACAO: {
        "Parafusos e roscas": (
            "parafuso_axial",
            "rosca_arrancamento",
            "torque_aperto",
            "grupo_parafusos",
        ),
        "Pinos, chapas e soldas": (
            "Pinos ou parafusos sob cisalhamento",
            "pino_articulacao",
            "pino_balanco",
            "pino_transversal",
            "chapa_furo",
            "solda_filete",
        ),
    },
    AREA_BARRAS: {
        "Barras e colunas": (
            "Barra sob carga axial",
            "Barra sob carga axial excêntrica",
            "barra_axial",
            "barra_torcao",
            "coluna_simples",
        ),
        "Vigas": ("viga_reacoes", "flexao_secao", "perfil_nbr8800"),
        "Seções e perfis": (
            "secao_montada",
            "Viga de seção retangular",
            "Seção retangular com flexão biaxial",
            "Torção de seção retangular",
            elementos_secoes.MODELO_SECAO_I,
            "Perfil U sob força axial, flexão e cortante",
            "Cantoneira de abas iguais",
            "Perfil tubular retangular (caixão)",
        ),
        "Treliças e pórticos": ("trelica_plana", "portico_simples"),
    },
    AREA_MAQUINAS: {
        "Motor e transmissão": (
            "acionamento",
            "engrenagem",
            "engrenagem_conica",
            "sem_fim",
            "correia",
            "corrente",
            "acoplamento",
        ),
        "Eixos e cubos": (
            "eixo_transmissao",
            "eixo_secao",
            "Eixo circular maciço",
            "Eixo circular vazado",
            "chaveta",
            "ajuste_prensado",
        ),
        "Mancais e contato": ("rolamento", "bucha", "hertz"),
        "Molas": (
            "mola_compressao",
            "Mola helicoidal de compressão",
            "mola_tracao",
            "mola_torcao",
            "mola_prato",
        ),
        "Freios, embreagens e fusos": ("embreagem_disco", "freio_cinta", "parafuso_potencia"),
        "Máquinas e vibração": ("desbalanceamento", "base_maquina", "disco_girante", "impacto"),
    },
    AREA_ICAMENTO: {
        "Içamento": (
            "acoes_icamento",
            "cabo_tambor",
            "roda_ponte",
            "mecanismo_nbr8400",
            "gancho",
            "olhal",
            "linga_corrente",
        ),
        "Vasos e tubos sob pressão": (
            "Vaso cilíndrico de parede fina",
            "Vaso esférico de parede fina",
            "Cilindro de parede espessa",
        ),
        "Cilindros e tampas": ("cilindro_hidraulico", "placa_circular", "placa_retangular"),
    },
}

_DE_ORIGEM: dict[str, Caso] = {
    caso.id: caso
    for modulo in (
        elementos_parafusos,
        elementos_vigas,
        elementos_barras,
        elementos_estatica,
        elementos_transmissao,
        elementos_eixos,
        elementos_mancais,
        elementos_molas_atrito,
        elementos_molas,
        elementos_icamento,
        elementos_rotativos,
        elementos_secoes,
        elementos_pinos,
        elementos_soldas,
        elementos_impacto,
        elementos_lingas,
    )
    for caso in modulo.CASOS
}

CASOS: dict[str, Caso] = {
    caso_id: replace(_DE_ORIGEM[caso_id], grupo=grupo)
    for grupos in PAINEL.values()
    for grupo, ids in grupos.items()
    for caso_id in ids
}
if set(CASOS) != set(_DE_ORIGEM):  # pragma: no cover - erro de quem acrescenta um caso
    raise RuntimeError(f"Casos fora do painel: {sorted(set(_DE_ORIGEM) - set(CASOS))}")

#: Grupos por área, na ordem em que aparecem; cada grupo lista os ids dos casos.
GRUPOS: dict[str, dict[str, list[str]]] = {
    area: {grupo: list(ids) for grupo, ids in grupos.items()} for area, grupos in PAINEL.items()
}

#: Outros nomes que a pessoa digita na busca do painel: caso → palavras.
APELIDOS: dict[str, tuple[str, ...]] = {
    "parafuso_axial": ("pré-carga", "tração no parafuso"),
    "rosca_arrancamento": ("espanar", "comprimento de rosca", "furo roscado"),
    "torque_aperto": ("torquímetro", "aperto"),
    "grupo_parafusos": ("flange", "padrão de furos", "excêntrico"),
    "Pinos ou parafusos sob cisalhamento": ("corte simples", "corte duplo", "rebite"),
    "pino_articulacao": ("garfo", "olhal e garfo", "articulação"),
    "chapa_furo": ("concentração de tensão", "seção líquida"),
    "solda_filete": ("solda", "cordão", "suporte soldado", "console soldado", "Shigley"),
    "Barra sob carga axial": ("tirante", "tração", "compressão"),
    "barra_axial": ("alongamento", "escalonada"),
    "barra_torcao": ("ângulo de giro", "tubo torcido"),
    "coluna_simples": ("flambagem", "Euler", "pilar"),
    "viga_reacoes": ("diagrama", "cortante", "momento fletor", "flecha", "balanço"),
    "flexao_secao": ("módulo resistente", "von Mises"),
    "perfil_nbr8800": ("NBR 8800", "flambagem lateral"),
    "secao_montada": ("centroide", "momento de inércia", "seção composta"),
    elementos_secoes.MODELO_SECAO_I: ("viga I", "perfil W", "seção I"),
    "Perfil tubular retangular (caixão)": ("tubo quadrado", "metalon", "Bredt"),
    "Cantoneira de abas iguais": ("perfil L",),
    "trelica_plana": ("tesoura", "nós e barras"),
    "portico_simples": ("mão-francesa", "console em L", "quadro"),
    "acionamento": ("motorredutor", "potência", "torque do motor"),
    "engrenagem": ("dente reto", "helicoidal"),
    "sem_fim": ("rosca sem fim", "redutor de coroa"),
    "correia": ("correia em V", "polia"),
    "acoplamento": ("luva", "flange com parafusos"),
    "eixo_transmissao": ("árvore", "rotação crítica"),
    "eixo_secao": ("ressalto", "concentração de tensão", "diâmetro mínimo"),
    "Eixo circular maciço": ("eixo redondo", "barra redonda"),
    "Eixo circular vazado": ("tubo redondo",),
    "chaveta": ("DIN 6885", "rasgo de chaveta"),
    "ajuste_prensado": ("interferência", "prensagem", "montagem a quente"),
    "rolamento": ("vida L10", "carga estática", "mancal de rolamento"),
    "bucha": ("mancal de deslizamento", "pV"),
    "hertz": ("pressão de contato", "roda e trilho"),
    "Mola helicoidal de compressão": ("mola helicoidal",),
    "mola_prato": ("Belleville", "arruela cônica"),
    "parafuso_potencia": ("fuso", "rosca trapezoidal", "macaco"),
    "desbalanceamento": ("ressonância", "grau G"),
    "base_maquina": ("chumbador", "pés da máquina"),
    "disco_girante": ("volante de inércia",),
    "impacto": ("choque", "queda de peso", "batente", "carga dinâmica"),
    "acoes_icamento": ("coeficiente dinâmico", "NBR 8400"),
    "cabo_tambor": ("cabo de aço", "NBR 6327"),
    "gancho": ("viga curva", "Winkler"),
    "olhal": ("orelha de içamento",),
    "linga_corrente": ("linga", "corrente de içamento", "CMT", "estropo", "NBR 15516"),
    "Vaso cilíndrico de parede fina": ("tubo pressurizado", "tensão circunferencial"),
    "Cilindro de parede espessa": ("Lamé", "parede grossa"),
    "cilindro_hidraulico": ("atuador", "haste", "pistão"),
    "placa_circular": ("flange cego", "fundo de tanque"),
    "placa_retangular": ("parede de tanque", "janela de inspeção"),
}


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.casefold()) if not unicodedata.combining(c)
    )


def rotulo_da_busca(caso_id: str) -> str:
    """O que a busca do painel mostra e onde ela procura: título, grupo e os outros nomes."""
    caso = CASOS[caso_id]
    outros = APELIDOS.get(caso_id, ())
    return f"{caso.titulo} · {caso.grupo}" + (f" · {', '.join(outros)}" if outros else "")


def rotulo_do_modelo(caso_id: str) -> str:
    """Grupo e título de hoje para um rótulo que outra página guarda pelo nome antigo."""
    caso = CASOS.get(ALIASES.get(caso_id, caso_id))
    return f"{caso.grupo} · {caso.titulo}" if caso else caso_id


def procurar(texto: str) -> list[str]:
    """Casos que têm todas as palavras digitadas, sem ligar para acento nem maiúscula."""
    palavras = _sem_acento(texto).split()
    if not palavras:
        return []
    achados = []
    for caso_id, caso in CASOS.items():
        onde = _sem_acento(
            " ".join((caso.titulo, caso.grupo, caso.resumo, caso_id, *APELIDOS.get(caso_id, ())))
        )
        if all(palavra in onde for palavra in palavras):
            achados.append(caso_id)
    return achados


@dataclass(frozen=True)
class InfoDaArea:
    icone: str
    descricao: str


@dataclass(frozen=True)
class InfoDoGrupo:
    icone: str
    descricao: str


AREAS_INFO = {
    AREA_FIXACAO: InfoDaArea(
        ":material/hardware:",
        "O que une uma peça à outra: parafuso, rosca, pino, solda e a chapa em volta do furo.",
    ),
    AREA_BARRAS: InfoDaArea(
        ":material/straighten:",
        "A peça comprida: forças que chegam, tensão em cada ponto da seção e se ela aguenta.",
    ),
    AREA_MAQUINAS: InfoDaArea(
        ":material/settings:",
        "Do motor ao mancal: cada caso verifica uma peça e entrega o resultado para a próxima.",
    ),
    AREA_ICAMENTO: InfoDaArea(
        ":material/anchor:",
        "Equipamento de levantar carga (NBR 8400) e peças com pressão por dentro.",
    ),
}

GRUPOS_INFO = {
    "Parafusos e roscas": InfoDoGrupo(
        ":material/hardware:", "Tração, arrancamento da rosca, torque de aperto e grupos."
    ),
    "Pinos, chapas e soldas": InfoDoGrupo(
        ":material/push_pin:",
        "Pino ao corte, em balanço ou na articulação, chapa com furo e cordão de solda.",
    ),
    "Barras e colunas": InfoDoGrupo(
        ":material/linear_scale:", "Força axial, excentricidade, torção e flambagem."
    ),
    "Vigas": InfoDoGrupo(
        ":material/straighten:", "Reações, diagramas, flecha e flexão de seções e perfis."
    ),
    "Seções e perfis": InfoDoGrupo(
        ":material/view_column:",
        "Propriedades da seção e a tensão ponto a ponto em I, U, L e tubo.",
    ),
    "Treliças e pórticos": InfoDoGrupo(
        ":material/architecture:", "Força em cada barra, reações, diagramas e deformada."
    ),
    "Motor e transmissão": InfoDoGrupo(
        ":material/settings_input_component:",
        "Motor, redutor, engrenagens, correia, corrente e flange.",
    ),
    "Eixos e cubos": InfoDoGrupo(
        ":material/horizontal_rule:", "Eixo inteiro, seção à fadiga, chaveta e ajuste prensado."
    ),
    "Mancais e contato": InfoDoGrupo(
        ":material/motion_blur:", "Rolamento, bucha e contato de Hertz."
    ),
    "Molas": InfoDoGrupo(
        ":material/compress:", "Compressão, tração, torção e prato: rigidez, tensão e fadiga."
    ),
    "Freios, embreagens e fusos": InfoDoGrupo(
        ":material/album:", "Freio, embreagem e parafuso de potência."
    ),
    "Máquinas e vibração": InfoDoGrupo(
        ":material/vibration:", "Balanceamento, base de máquina, volante e impacto."
    ),
    "Içamento": InfoDoGrupo(
        ":material/anchor:", "Ações, cabo, roda, mecanismo, gancho, olhal e linga de corrente."
    ),
    "Vasos e tubos sob pressão": InfoDoGrupo(
        ":material/propane_tank:", "Paredes finas, paredes grossas e esferas."
    ),
    "Cilindros e tampas": InfoDoGrupo(
        ":material/water_drop:", "Cilindro hidráulico, tampa e chapa sob pressão."
    ),
}

#: Os cálculos que mais se abre, no topo do painel, pelo nome técnico.
MAIS_USADOS: tuple[str, ...] = (
    "parafuso_axial",
    "rosca_arrancamento",
    "viga_reacoes",
    "perfil_nbr8800",
    "coluna_simples",
    "eixo_transmissao",
    "rolamento",
    "acionamento",
)

CASO_PADRAO = "parafuso_axial"

#: Rótulos usados em versões antigas continuam valendo como entrada.
ALIASES = {"Seção I sob força axial e flexão": elementos_secoes.MODELO_SECAO_I}


#: Casos que saíram do painel e hoje moram em outra página: caso antigo → página.
MUDARAM_DE_PAGINA = {"equilibrio_peca": "app_pages/vigas_eixos.py"}


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
    return AREA_BARRAS


def info_do_grupo(grupo: str) -> InfoDoGrupo:
    return GRUPOS_INFO[grupo]
