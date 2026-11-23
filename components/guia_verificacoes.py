"""Capítulos do Guia geral das verificações complementares de estrutura metálica.

Cada capítulo traz o que a página faz, os campos (o que preencher e de onde tirar), um exemplo com
os valores de partida da página e o resultado que o núcleo calcula para eles — o mesmo número que
a pessoa vê ao abrir a página sem mexer em nada.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import streamlit as st

from core import verificacao_modulo as vm


@dataclass(frozen=True)
class Capitulo:
    pagina: str
    texto: str
    campos: tuple[tuple[str, str, str], ...]
    exemplo: tuple[tuple[str, str], ...]
    grupos: Callable[[], list[vm.Grupo]]


def _forcas() -> list[vm.Grupo]:
    from core import forcas_localizadas as m

    return m.calcular(m.EntradaForcas()).grupos


def _monovia() -> list[vm.Grupo]:
    from core import monovia as m

    return m.calcular(m.EntradaMonovia()).grupos


def _rigida() -> list[vm.Grupo]:
    from core import ligacao_rigida as m

    return m.calcular(m.EntradaRigida()).grupos


def _contencao() -> list[vm.Grupo]:
    from core import contencao_lateral as m

    return m.calcular(m.EntradaContencao()).grupos


def _fadiga() -> list[vm.Grupo]:
    from core import fadiga_estrutural as m

    return m.calcular(m.EntradaFadiga()).grupos


def _mista() -> list[vm.Grupo]:
    from core import viga_mista as m

    return m.calcular(m.EntradaMista()).grupos


def _nos() -> list[vm.Grupo]:
    from core import nos_tubulares as m

    return m.calcular(m.EntradaNo()).grupos


def _aberturas() -> list[vm.Grupo]:
    from core import aberturas_alma as m

    return m.calcular(m.EntradaAberturas()).grupos


def _tercas() -> list[vm.Grupo]:
    from core import tercas as m

    return m.calcular(m.EntradaTerca()).grupos


def _incendio() -> list[vm.Grupo]:
    from core import incendio as m

    return m.calcular(m.EntradaIncendio()).grupos


CAPITULOS: dict[str, Capitulo] = {
    "Forças localizadas na alma": Capitulo(
        "app_pages/forcas_localizadas.py",
        "Use quando uma força concentrada entra pela mesa de um perfil I ou H: a **reação de "
        "apoio** de uma viga, o **pé de um equipamento**, uma viga que apoia por cima ou por "
        "baixo, a mesa de uma viga ligada ao pilar. A flexão e o cortante da viga não pegam esse "
        "caso. O programa verifica a **ABNT NBR 8800:2025, 5.7**: flexão local da mesa, "
        "escoamento local e enrugamento da alma, flambagem lateral da alma e instabilidade por "
        "compressão — e, quando não passa, os **enrijecedores** (5.7.9).",
        (
            (
                "Perfil e aço",
                "Bitola do catálogo (W/HP com o raio, I laminado) ou perfil soldado",
                "Projeto",
            ),
            (
                "Forças",
                "Uma linha por força: valor de cálculo, tipo (compressão, tração ou par), "
                "comprimento de apoio ℓn, largura, distância à ponta e momento na seção",
                "Análise da estrutura, detalhe do apoio",
            ),
            (
                "Travamento",
                "ℓ destravado, rotação da mesa impedida e deslocamento lateral impedido",
                "Modelo e detalhes",
            ),
            (
                "Enrijecedores",
                "Largura, espessura, recorte, ponta ajustada ou soldada, filetes",
                "Detalhe a verificar",
            ),
        ),  # fmt: skip
        (
            ("Perfil", "W 410 x 46,1 em A572 Gr 50"),
            ("Forças", "reação de 150 kN na ponta (ℓn = 100 mm) e equipamento de 120 kN no vão"),
        ),
        _forcas,
    ),
    "Viga de monovia": Capitulo(
        "app_pages/monovia.py",
        "Use para a **viga da talha** (a talha corre na mesa de baixo). O programa coloca as "
        "rodas na posição mais desfavorável, soma o **impacto** do critério Anglo e a **força "
        "lateral**, e verifica flexão vertical (com FLT) e lateral, cortante, a **mesa de baixo "
        "sob as rodas** (EN 1993-6, 6.7), as flechas L/500 e L/400 e a mesa no apoio (5.7).",
        (
            ("Perfil e aço", "Bitola ou perfil soldado", "Projeto"),
            ("Viga", "Biapoiada ou balanço, vão e comprimento destravado", "Arranjo da monovia"),
            (
                "Talha",
                "Carga içada, peso da talha, eixos, rodas, entre eixos e a posição n da "
                "roda na mesa",
                "Catálogo do fabricante da talha",
            ),
            (
                "Impacto e coeficientes",
                "+20 % na carga, +10 % na talha, lateral 10 %, γ_g, γ_q",
                "Critério do cliente",
            ),
            ("Apoio", "Pendurada pela mesa de cima ou apoiada pela de baixo", "Detalhe"),
        ),  # fmt: skip
        (
            ("Viga", "W 310 x 38,7, biapoiada, vão 5 m"),
            ("Talha", "20 kN de carga, 3 kN de talha, 2 eixos a 300 mm, roda a 20 mm da borda"),
        ),
        _monovia,
    ),
    "Ligação rígida viga–pilar": Capitulo(
        "app_pages/ligacao_rigida.py",
        "Use para a **ligação de momento parafusada** com chapa de extremidade estendida (4 "
        "parafusos junto à mesa tracionada, 4E). Linhas de plastificação da chapa e da mesa do "
        "pilar pela **AISC 358** com chapa grossa (sem alavanca), resistências da **ABNT NBR "
        "8800:2025**, soldas da viga, alma e **painel de alma** do pilar (5.7.7) e os "
        "**enrijecedores de continuidade**.",
        (
            ("Viga e pilar", "Bitolas (ou soldados) e aços", "Projeto"),
            (
                "Esforços",
                "M e V da viga na face do pilar; N e V do pilar; viga do outro lado",
                "Análise da estrutura",
            ),
            ("Parafusos e chapa", "Diâmetro, grau, b_p, t_p, g, p_fo, p_fi, borda", "Detalhe"),
            ("Soldas", "Penetração total ou filete na mesa; filete da alma", "Detalhe"),
            ("Reforços", "Enrijecedores de continuidade e chapas de reforço da alma", "Detalhe"),
        ),  # fmt: skip
        (
            ("Ligação", "W 410 x 46,1 em HP 310 x 79,0, M = 120 kN·m, V = 80 kN"),
            ("Chapa", '160 × 22,4 mm, 8 parafusos de 3/4" A325, g = 100 mm'),
        ),
        _rigida,
    ),
    "Contenção lateral (travamentos)": Capitulo(
        "app_pages/contencao_lateral.py",
        "Use para conferir se o **travamento** que reduz o comprimento destravado tem a **força** "
        "e a **rigidez** da **ABNT NBR 8800:2025, 4.12**: pilares, vigas com contenção de "
        "translação na mesa comprimida e vigas com contenção de torção (nodal, por viga "
        "transversal, ou contínua). Sem isso, o comprimento destravado adotado não vale.",
        (
            ("Caso", "Pilar, viga com translação ou viga com torção", "Arranjo"),
            (
                "Esforço",
                "N_Sd ou M_Sd, barras em série, distância entre contenções, L_q",
                "Análise da estrutura",
            ),
            (
                "Barra de contenção",
                "Área, raio de giração, comprimento, ângulo, aço, rigidez da ligação",
                "Perfil da barra",
            ),
            (
                "Torção",
                "Enrijecedor da alma, rigidez β (ou viga transversal), M_Rd da ligação",
                "Detalhe",
            ),
        ),  # fmt: skip
        (
            ("Viga", "W 410 x 46,1 com M_Sd = 180 kN·m, contenções a cada 2 m"),
            ("Barra", "480 mm², r = 9,9 mm, 1,5 m, perpendicular"),
        ),
        _contencao,
    ),
    "Fadiga da estrutura": Capitulo(
        "app_pages/fadiga_estrutural.py",
        "Use em estruturas sob **carga repetida** (suporte de talha, peneira, britador, "
        "transportador). Cada detalhe — solda, furo, recorte, parafuso — tem uma **categoria** "
        "(A a G, C' e C'') da **Tabela H.1 da ABNT NBR 8800:2025**; a variação de tensão nele é "
        "comparada com a faixa admissível para o número de ciclos.",
        (
            (
                "Ciclos",
                "Ciclos por dia × dias por ano × anos, ou o total",
                "Operação do equipamento",
            ),
            (
                "Detalhes",
                "Caso da Tabela H.1 e as tensões máxima e mínima na combinação frequente",
                "Análise elástica",
            ),
        ),  # fmt: skip
        (
            ("Ciclos", "200 por dia, 300 dias, 25 anos = 1,5 milhão"),
            ("Detalhes", "pé de enrijecedor soldado (C), metal-base (A), garganta de filete (F)"),
        ),
        _fadiga,
    ),
    "Viga mista": Capitulo(
        "app_pages/viga_mista.py",
        "Use para viga de **mezanino ou piso com laje de concreto** ligada por **conectores** "
        "(stud). Pela **ABNT NBR 8800:2025, Anexo L**: largura efetiva, conector, momento com "
        "interação completa ou parcial, grau mínimo de interação, construção sem escoras e flecha "
        "com o momento de inércia efetivo.",
        (
            ("Perfil e vão", "Bitola, aço e vão", "Projeto"),
            ("Laje", "Vigas vizinhas, espessura, fôrma, f_ck e brita", "Projeto da laje"),
            (
                "Conectores",
                "Diâmetro, f_u, posição na fôrma, quantidade até o meio do vão",
                "Detalhe",
            ),
            (
                "Cargas",
                "Antes e depois da cura, construção e uso (kN/m, característicos)",
                "Levantamento de cargas",
            ),
        ),  # fmt: skip
        (
            ("Viga", "W 410 x 38,8, vão 8 m, vigas a 2,5 m"),
            ("Laje", "maciça de 100 mm, f_ck 25 MPa, 24 conectores Ø 19 até o meio do vão"),
        ),
        _mista,
    ),
    "Nós de treliça tubular": Capitulo(
        "app_pages/nos_tubulares.py",
        "Use em treliça de **tubo** com as diagonais soldadas direto no banzo. Pelo **EN 1993-1-8, "
        "capítulo 7** (as expressões da **ABNT NBR 16239**): nós T, Y, X e K/N com afastamento em "
        "tubo circular ou retangular, com a faixa de validade e os modos de falha do banzo e da "
        "diagonal.",
        (
            ("Nó", "Forma dos tubos, tipo de nó e aços", "Projeto"),
            ("Banzo", "Medidas, N₀ e M₀ junto do nó", "Análise da treliça"),
            ("Diagonais", "Medidas, ângulos, forças e afastamento", "Análise e detalhe"),
        ),
        (
            ("Banzo", "Ø 168,3 × 6,4 em VMB 350, N₀ = −400 kN"),
            ("Diagonais", "Ø 88,9 × 4,0 a 45°, −150 e +150 kN, afastamento 30 mm"),
        ),
        _nos,
    ),
    "Aberturas na alma": Capitulo(
        "app_pages/aberturas_alma.py",
        "Use quando a viga recebe **furos na alma** para tubulação, eletrocalha ou duto. O "
        "programa diz se o furo dispensa cálculo pela **ABNT NBR 8800:2025, F.3** e, quando não, "
        "verifica a viga na seção do furo pelo **AISC Design Guide 2** (momento, cortante e "
        "proporções).",
        (
            ("Viga", "Perfil, aço, vão e carga uniforme de cálculo", "Projeto"),
            ("Aberturas", "Forma, medidas, posição ao longo do vão e excentricidade", "Detalhe"),
        ),
        (
            ("Viga", "W 410 x 46,1, vão 7 m, q_d = 30 kN/m"),
            ("Aberturas", "furo Ø 150 a 2,5 m e rasgo 300 × 120 a 4,2 m do apoio"),
        ),
        _aberturas,
    ),
    "Terças e travessas": Capitulo(
        "app_pages/tercas.py",
        "Use para **terças de cobertura** e **travessas de fechamento** em perfil U enrijecido "
        "dobrado a frio. Pela **ABNT NBR 14762:2010**: seção efetiva, FLT entre linhas de "
        "corrente, distorcional, **sucção do vento** (fator R do Anexo F), cortante, flexão "
        "oblíqua e flechas da Tabela A.1.",
        (
            ("Perfil", "b_w, b_f, D, t e aço (ZAR)", "Catálogo do fornecedor"),
            ("Vão", "Vão, linhas de corrente, espaçamento e inclinação", "Projeto da cobertura"),
            ("Cargas", "Telha, sobrecarga, sucção e pressão (kN/m²)", "NBR 6123 e NBR 8800"),
            ("Critérios", "Telha trava a mesa, Anexo F, M_dist, limites de flecha", "Projeto"),
        ),
        (
            ("Terça", "Ue 200 × 75 × 20 × 2,65 em ZAR 345, vão 6 m, 1 linha de corrente"),
            ("Cargas", "0,15 + 0,25 kN/m²; sucção 0,60 kN/m²"),
        ),
        _tercas,
    ),
    "Estrutura em incêndio": Capitulo(
        "app_pages/incendio.py",
        "Use quando a edificação tem **tempo requerido de resistência ao fogo** (TRRF, NBR "
        "14432). Pelo método simplificado da **ABNT NBR 14323**: a temperatura do aço pela "
        "curva-padrão, com ou sem proteção, e a resistência a quente de pilar, tirante ou viga "
        "na combinação de incêndio.",
        (
            ("Elemento", "Pilar, tirante ou viga, perfil, aço e comprimento", "Projeto"),
            ("Incêndio", "TRRF e a exposição (contorno ou caixão, 3 ou 4 lados)", "NBR 14432"),
            (
                "Proteção",
                "Material e espessura (valores típicos a conferir)",
                "Catálogo do fabricante",
            ),
            ("Esforços", "G_k e Q_k característicos e a ocupação (ψ)", "Análise da estrutura"),
        ),  # fmt: skip
        (
            ("Pilar", "HP 250 x 62,0, 4 m, G = 400 kN, Q = 300 kN"),
            ("Incêndio", "TRRF 60 min, argamassa projetada de 20 mm"),
        ),
        _incendio,
    ),
}


def resultado_esperado(nome: str) -> str:
    """A frase do resultado que a página mostra com os valores de partida."""
    linhas = vm.decisivas(CAPITULOS[nome].grupos())
    situacao = vm.situacao(linhas)
    g = vm.governante(linhas)
    texto = f"Resultado esperado: {situacao.lower()}"
    if g is not None and g.aproveitamento is not None:
        texto += f", maior aproveitamento de {100 * g.aproveitamento:.0f} % ({g.nome.lower()})"
    return texto + "."


def mostrar_capitulo(
    nome: str,
    mostrar_tabela_campos: Callable[[list[list[str]]], None],
    mostrar_exemplo: Callable[[list[list[str]], str | None], None],
    link_modulo: Callable[[str, str], None],
) -> None:
    c = CAPITULOS[nome]
    st.header(nome)
    st.markdown(c.texto)
    mostrar_tabela_campos([list(x) for x in c.campos])
    mostrar_exemplo([list(x) for x in c.exemplo], resultado_esperado(nome))
    st.markdown(
        "Na página: **Memorial deste cálculo** baixa o trecho em Word (para colar no documento "
        "oficial) ou o PDF; **Registrar no projeto** leva o cálculo ao Memorial de cálculo do "
        "projeto."
    )
    link_modulo(c.pagina, f"Abrir {nome}")
