"""Escada fixa do tipo marinheiro (vertical), com ou sem gaiola: NR-12 e NBR 8800.

**Geometria** pela NR-12, Anexo III (texto vigente, "Meios de acesso a máquinas e
equipamentos"), item 13 e subitem 13.1, e pela Figura 1 (inclinação de 75° a 90°):

* a) dimensionamento seguro (a parte estrutural, abaixo); b) material resistente a intempéries e
  corrosão em ambiente externo ou corrosivo;
* c) gaiola acima de 3,50 m de altura, a partir de 2,0 m do piso, ultrapassando o piso de chegada
  de 1,10 m a 1,20 m; d) montantes (ou corrimão) ultrapassando o piso de chegada de 1,10 m a
  1,20 m; e) largura de 0,40 m a 0,60 m;
* f) lance único até 10,00 m; g) com vários lances, até 6,00 m entre plataformas de descanso, com
  os lances paralelos afastados ao menos 0,70 m;
* h) barras de 0,25 m a 0,30 m uma da outra; i) primeira barra até 0,55 m do piso; j) ao menos
  0,15 m da estrutura; k) barras de 25 mm a 38 mm; l) barras antiderrapantes;
* 13.1: gaiola de 0,65 m a 0,80 m de diâmetro, com a) barras verticais a até 0,30 m e arcos a
  até 1,50 m ou b) arcos a até 0,30 m com barra vertical de sustentação.

A marinheiro só vale na impossibilidade técnica de rampa, passarela, plataforma ou escada de
degraus (item 1.3); acima de 2 m de altura vale também a NR-35, com ou sem gaiola (Orientação
Técnica SIT nº 8/2023).

**Estrutura** pela NBR 8800 (γ_g = 1,25, γ_q = 1,50, γ_a1 = 1,10):

* degrau: barra maciça biapoiada entre os eixos dos montantes, com a carga concentrada de 2,5 kN
  no meio — a do degrau isolado da NBR 6120 (2.2.1.7 da edição de 1980; Tabela 10, nota t, da de
  2019); M_Rd = Z·f_y/γ_a1 ≤ 1,5·W·f_y/γ_a1;
* montante: barra chata comprimida (K = 1), χ da NBR 8800 5.3.3 com Q = 1 (seção maciça), pela
  maior esbeltez entre os dois eixos — para a estrutura, pela largura b, entre as fixações; no
  plano da escada, pela espessura t, entre as barras, que ligam um montante no outro; a carga do
  lance inteiro desce pelos montantes até o apoio de baixo — peso próprio da escada e da gaiola e
  as pessoas no lance;
* fixações: as forças de cálculo de cada suporte, para dimensionar o suporte e os chumbadores.

A NR-12 não dá carga para os montantes nem para a gaiola: "uma pessoa por lance, com 2,5 kN" é
critério do programa, que o usuário pode mudar (o cliente ou a ISO 14122-4 podem pedir outro).
A gaiola entra só pelo peso. Sem Streamlit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core import column_design as cd
from core.bolted_connection import ACOS
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "escada_marinheiro"
MODULO_TITULO = "Escada marinheiro"

E_ACO = 200_000.0
RHO_ACO = 7850.0  # kg/m³
G = 9.80665
GAMMA_G = 1.25  # peso próprio de estrutura metálica (NBR 8800, Tabela 1)
GAMMA_Q = 1.50  # ações variáveis de uso (NBR 8800, Tabela 1)
GAMMA_A1 = 1.10
ESBELTEZ_MAXIMA = 200.0  # NBR 8800 5.3.4.1

# NR-12, Anexo III (texto vigente)
INCLINACAO_MIN, INCLINACAO_MAX = 75.0, 90.0  # Figura 1
GAIOLA_EXIGIDA_ACIMA_M = 3.50  # 13 c
GAIOLA_INICIO_MAX_MM = 2000.0  # 13 c: a partir de 2,0 m do piso
ULTRAPASSA_MIN_MM, ULTRAPASSA_MAX_MM = 1100.0, 1200.0  # 13 c e 13 d
LARGURA_MIN_MM, LARGURA_MAX_MM = 400.0, 600.0  # 13 e
LANCE_UNICO_MAX_M = 10.0  # 13 f
ENTRE_PLATAFORMAS_MAX_M = 6.0  # 13 g
AFASTAMENTO_ENTRE_LANCES_MIN_MM = 700.0  # 13 g
PASSO_MIN_MM, PASSO_MAX_MM = 250.0, 300.0  # 13 h
PRIMEIRA_BARRA_MAX_MM = 550.0  # 13 i
AFASTAMENTO_ESTRUTURA_MIN_MM = 150.0  # 13 j
BARRA_MIN_MM, BARRA_MAX_MM = 25.0, 38.0  # 13 k
GAIOLA_DIAMETRO_MIN_MM, GAIOLA_DIAMETRO_MAX_MM = 650.0, 800.0  # 13.1
VERTICAIS_ESPACAMENTO_MAX_MM = 300.0  # 13.1 a
ARCOS_ESPACAMENTO_MAX_A_MM = 1500.0  # 13.1 a
ARCOS_ESPACAMENTO_MAX_B_MM = 300.0  # 13.1 b
ALTURA_NR35_M = 2.0  # NR-35 (Orientação Técnica SIT nº 8/2023, item 2)

CARGA_DO_DEGRAU_KN = 2.5  # degrau isolado: NBR 6120:1980 2.2.1.7; NBR 6120:2019 Tabela 10, nota t

REDONDA = "Barra redonda"
QUADRADA = "Barra quadrada"
FORMAS_DO_DEGRAU = (REDONDA, QUADRADA)

GAIOLA_VERTICAIS = "Barras verticais e arcos (13.1 a)"
GAIOLA_ARCOS = "Arcos próximos com barra de sustentação (13.1 b)"
TIPOS_DE_GAIOLA = (GAIOLA_VERTICAIS, GAIOLA_ARCOS)

REF_NR12 = "NR-12, Anexo III"

AVISOS = (
    "NR-12, Anexo III, 1.3: a escada marinheiro só vale quando não há como pôr rampa, passarela, "
    "plataforma ou escada de degraus. Registre por que não cabe uma delas.",
    "Acima de 2 m vale também a NR-35 (Orientação Técnica SIT nº 8/2023), com ou sem gaiola: "
    "a análise de risco define a proteção contra quedas (trava-quedas, linha de vida).",
    "A NR-12 não dá carga para os montantes nem para a gaiola: uma pessoa por lance, com a carga "
    "do degrau isolado (2,5 kN), é critério do programa. Confira com o cliente; a ISO 14122-4 pode "
    "pedir outro valor.",
    "A gaiola entra só pelo peso: a resistência dos arcos e das barras verticais não é verificada.",
)


class EscadaInvalida(ValueError):
    """Dado que o cálculo não aceita; a mensagem diz o que corrigir."""


@dataclass(frozen=True)
class EntradaMarinheiro:
    # Geometria (NR-12)
    altura_m: float = 6.0  # do piso ao piso de chegada
    lances: int = 1
    afastamento_entre_lances_mm: float = 700.0
    inclinacao_graus: float = 90.0
    largura_mm: float = 450.0  # livre entre montantes
    passo_mm: float = 300.0
    primeira_barra_mm: float = 300.0
    afastamento_mm: float = 200.0  # das barras à estrutura em que a escada é fixada
    ultrapassa_mm: float = 1100.0  # montantes acima do piso de chegada
    # Degraus
    forma_do_degrau: str = REDONDA
    degrau_mm: float = 25.4  # diâmetro ou lado
    antiderrapante: bool = True
    # Gaiola
    gaiola: bool = True
    inicio_gaiola_mm: float = 2000.0
    gaiola_ultrapassa_mm: float = 1100.0
    diametro_gaiola_mm: float = 700.0
    tipo_gaiola: str = GAIOLA_VERTICAIS
    verticais_mm: float = 300.0  # espaçamento das barras verticais
    arcos_mm: float = 1500.0  # espaçamento dos arcos
    arco_b_mm: float = 38.1  # chata do arco
    arco_t_mm: float = 6.35
    vertical_b_mm: float = 31.75  # chata das barras verticais
    vertical_t_mm: float = 4.76
    # Material e estrutura
    aco: str = "ASTM A36"
    montante_b_mm: float = 50.8  # chata do montante: largura (perpendicular à estrutura)
    montante_t_mm: float = 9.53  # espessura
    fixacoes_mm: float = 2000.0  # distância entre suportes, ao longo da altura
    ambiente_agressivo: bool = False
    protecao_contra_corrosao: bool = True
    # Cargas
    carga_degrau_kN: float = CARGA_DO_DEGRAU_KN
    pessoas_por_lance: int = 1


@dataclass(frozen=True)
class ResultadoMarinheiro:
    entrada: EntradaMarinheiro
    altura_do_lance_m: float
    barras_por_lance: int
    ultima_barra_ao_piso_mm: float
    peso_por_metro_kg: float
    peso_total_kg: float
    vao_do_degrau_mm: float
    momento_degrau_kNm: float
    momento_resistente_degrau_kNm: float
    normal_montante_kN: float
    resistencia_montante_kN: float
    esbeltez_montante: float
    suporte_vertical_kN: float  # de cálculo, por lado
    suporte_momento_kNm: float
    verificacoes: tuple[Verificacao, ...]
    avisos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))

    @property
    def aproveitamento_maximo(self) -> float:
        return max(
            (v.aproveitamento or 0.0 for v in self.verificacoes if v.tipo == "resistencia"),
            default=0.0,
        )

    @property
    def gaiola_exigida(self) -> bool:
        return self.entrada.altura_m > GAIOLA_EXIGIDA_ACIMA_M


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def validar(e: EntradaMarinheiro) -> list[str]:
    erros: list[str] = []
    numeros = {
        "A altura": e.altura_m,
        "A largura": e.largura_mm,
        "O espaçamento das barras": e.passo_mm,
        "A altura da primeira barra": e.primeira_barra_mm,
        "O afastamento da estrutura": e.afastamento_mm,
        "A barra do degrau": e.degrau_mm,
        "O montante": e.montante_b_mm * e.montante_t_mm,
        "A distância entre fixações": e.fixacoes_mm,
    }
    for nome, valor in numeros.items():
        if not (math.isfinite(valor) and valor > 0):
            erros.append(f"{nome} precisa ser maior que zero.")
    if not 1 <= e.lances <= 20:
        erros.append("O número de lances vai de 1 a 20.")
    if e.altura_m > 100:
        erros.append("A altura vai até 100 m.")
    if not (math.isfinite(e.inclinacao_graus) and 45 <= e.inclinacao_graus <= 90):
        erros.append("A inclinação vai de 45° a 90°.")
    if e.forma_do_degrau not in FORMAS_DO_DEGRAU:
        erros.append(f"Forma de degrau desconhecida: {e.forma_do_degrau!r}.")
    if e.tipo_gaiola not in TIPOS_DE_GAIOLA:
        erros.append(f"Tipo de gaiola desconhecido: {e.tipo_gaiola!r}.")
    if e.aco not in ACOS:
        erros.append(f"Aço desconhecido: {e.aco!r}.")
    if e.montante_t_mm > e.montante_b_mm:
        erros.append("A espessura do montante não pode passar da largura dele.")
    if not (math.isfinite(e.carga_degrau_kN) and e.carga_degrau_kN >= 0):
        erros.append("A carga no degrau não pode ser negativa.")
    if not 0 <= e.pessoas_por_lance <= 10:
        erros.append("As pessoas por lance vão de 0 a 10.")
    if e.gaiola:
        for nome, valor in (
            ("O diâmetro da gaiola", e.diametro_gaiola_mm),
            ("O espaçamento dos arcos", e.arcos_mm),
            ("O espaçamento das barras verticais", e.verticais_mm),
        ):
            if not (math.isfinite(valor) and valor > 0):
                erros.append(f"{nome} precisa ser maior que zero.")
    return erros


# ---------------------------------------------------------------------------------------------
# Linhas da tabela
# ---------------------------------------------------------------------------------------------
def _faixa(nome: str, valor: float, minimo: float, maximo: float, unidade: str, item: str,
           texto: str = "") -> Verificacao:  # fmt: skip
    ok = minimo - 1e-9 <= valor <= maximo + 1e-9
    # Na coluna do limite, o da faixa mais perto do valor (o que está mais perto de reprovar).
    limite = (
        maximo
        if valor > maximo or (valor >= minimo and maximo - valor < valor - minimo)
        else minimo
    )
    return Verificacao(
        nome, valor, limite, unidade, f"{REF_NR12}, {item}",
        texto or f"{_n(valor, 0)} {unidade} entre {_n(minimo, 0)} e {_n(maximo, 0)} {unidade}",
        status="OK" if ok else "NÃO OK", tipo="limite",
    )  # fmt: skip


def _maximo(nome: str, valor: float, maximo: float, unidade: str, item: str, texto: str = "",
            *, obrigatoria: bool = True) -> Verificacao:  # fmt: skip
    ok = valor <= maximo + 1e-9
    return Verificacao(
        nome, valor, maximo, unidade, f"{REF_NR12}, {item}" if item else "",
        texto or f"{_n(valor, 0)} ≤ {_n(maximo, 0)} {unidade}",
        status="OK" if ok else ("NÃO OK" if obrigatoria else "ALERTA"), tipo="limite",
        obrigatoria=obrigatoria,
    )  # fmt: skip


def _minimo(nome: str, valor: float, minimo: float, unidade: str, item: str,
            texto: str = "") -> Verificacao:  # fmt: skip
    ok = valor >= minimo - 1e-9
    return Verificacao(
        nome, valor, minimo, unidade, f"{REF_NR12}, {item}",
        texto or f"{_n(valor, 0)} ≥ {_n(minimo, 0)} {unidade}",
        status="OK" if ok else "NÃO OK", tipo="limite",
    )  # fmt: skip


def _sim(nome: str, atende: bool, item: str, texto: str) -> Verificacao:
    return Verificacao(nome, None, None, "—", f"{REF_NR12}, {item}", texto,
                       status="OK" if atende else "NÃO OK", tipo="limite")  # fmt: skip


def _informativo(nome: str, valor: float, unidade: str, referencia: str, texto: str) -> Verificacao:
    return Verificacao(nome, valor, None, unidade, referencia, texto, status="INFO",
                       tipo="informativo")  # fmt: skip


def linhas_da_geometria(e: EntradaMarinheiro, altura_do_lance_m: float,
                        ultima_mm: float) -> list[Verificacao]:  # fmt: skip
    linhas = [
        _faixa("Inclinação da escada", e.inclinacao_graus, INCLINACAO_MIN, INCLINACAO_MAX, "°",
               "2 (Figura 1)", f"{_n(e.inclinacao_graus, 0)}° entre 75° e 90° (marinheiro)"),
        _faixa("Largura da escada", e.largura_mm, LARGURA_MIN_MM, LARGURA_MAX_MM, "mm", "13 e)"),
        _faixa("Espaçamento entre as barras", e.passo_mm, PASSO_MIN_MM, PASSO_MAX_MM, "mm",
               "13 h)"),
        _maximo("Primeira barra acima do piso", e.primeira_barra_mm, PRIMEIRA_BARRA_MAX_MM, "mm",
                "13 i)"),
        _minimo("Distância das barras à estrutura", e.afastamento_mm,
                AFASTAMENTO_ESTRUTURA_MIN_MM, "mm", "13 j)"),
        _faixa("Diâmetro ou espessura da barra", e.degrau_mm, BARRA_MIN_MM, BARRA_MAX_MM, "mm",
               "13 k)"),
        _sim("Barras antiderrapantes", e.antiderrapante, "13 l)",
             "superfície, forma ou ranhura que impeça o pé de escorregar"
             if e.antiderrapante else "barras lisas: precisam de ranhura ou outra forma"),
        _faixa("Montantes acima do piso de chegada", e.ultrapassa_mm, ULTRAPASSA_MIN_MM,
               ULTRAPASSA_MAX_MM, "mm", "13 d)"),
    ]  # fmt: skip
    if e.lances == 1:
        linhas.append(_maximo("Altura do lance único", e.altura_m, LANCE_UNICO_MAX_M, "m",
                              "13 f)", f"{_n(e.altura_m)} ≤ 10,00 m"))  # fmt: skip
    else:
        linhas.append(_maximo("Altura entre plataformas de descanso", altura_do_lance_m,
                              ENTRE_PLATAFORMAS_MAX_M, "m", "13 g)",
                              f"{_n(e.altura_m)} m em {e.lances} lances iguais: "
                              f"{_n(altura_do_lance_m)} ≤ 6,00 m"))  # fmt: skip
        linhas.append(_minimo("Afastamento entre os lances", e.afastamento_entre_lances_mm,
                              AFASTAMENTO_ENTRE_LANCES_MIN_MM, "mm", "13 g)",
                              f"eixos paralelos a {_n(e.afastamento_entre_lances_mm, 0)} ≥ "
                              "700 mm"))  # fmt: skip
    linhas.append(
        _maximo("Última barra até o piso de chegada", ultima_mm, PASSO_MAX_MM, "mm", "",
                f"{_n(ultima_mm, 0)} mm da última barra ao piso de chegada (boa prática: no "
                "máximo o espaçamento das barras)", obrigatoria=False)
    )  # fmt: skip
    if e.ambiente_agressivo:
        linhas.append(_sim("Material resistente a intempéries e corrosão",
                           e.protecao_contra_corrosao, "13 b)",
                           "ambiente externo ou corrosivo: galvanizado, pintado ou inoxidável"
                           if e.protecao_contra_corrosao
                           else "ambiente externo ou corrosivo sem proteção"))  # fmt: skip
    return linhas


def linhas_da_gaiola(e: EntradaMarinheiro) -> list[Verificacao]:
    exigida = e.altura_m > GAIOLA_EXIGIDA_ACIMA_M
    if not e.gaiola:
        return [
            _sim("Gaiola de proteção", not exigida, "13 c)",
            f"{_n(e.altura_m)} m > 3,50 m: a gaiola é obrigatória" if exigida
            else f"{_n(e.altura_m)} m ≤ 3,50 m: a gaiola não é exigida")
        ]  # fmt: skip
    linhas = [
        _maximo("Início da gaiola acima do piso", e.inicio_gaiola_mm, GAIOLA_INICIO_MAX_MM, "mm",
                "13 c)", f"gaiola a partir de {_n(e.inicio_gaiola_mm, 0)} mm do piso "
                "(≤ 2000 mm)"),
        _faixa("Gaiola acima do piso de chegada", e.gaiola_ultrapassa_mm, ULTRAPASSA_MIN_MM,
               ULTRAPASSA_MAX_MM, "mm", "13 c)"),
        _faixa("Diâmetro da gaiola", e.diametro_gaiola_mm, GAIOLA_DIAMETRO_MIN_MM,
               GAIOLA_DIAMETRO_MAX_MM, "mm", "13.1"),
    ]  # fmt: skip
    if e.tipo_gaiola == GAIOLA_VERTICAIS:
        linhas += [
            _maximo("Espaçamento das barras verticais", e.verticais_mm,
                    VERTICAIS_ESPACAMENTO_MAX_MM, "mm", "13.1 a)"),
            _maximo("Distância entre os arcos", e.arcos_mm, ARCOS_ESPACAMENTO_MAX_A_MM, "mm",
                    "13.1 a)"),
        ]  # fmt: skip
    else:
        linhas.append(_maximo("Vão entre os arcos", e.arcos_mm, ARCOS_ESPACAMENTO_MAX_B_MM, "mm",
                              "13.1 b)", f"{_n(e.arcos_mm, 0)} ≤ 300 mm, com barra vertical de "
                              "sustentação dos arcos"))  # fmt: skip
    return linhas


# ---------------------------------------------------------------------------------------------
# Peso e estrutura
# ---------------------------------------------------------------------------------------------
def area_do_degrau(e: EntradaMarinheiro) -> float:
    d = e.degrau_mm
    return math.pi * d**2 / 4 if e.forma_do_degrau == REDONDA else d**2


def modulos_do_degrau(e: EntradaMarinheiro) -> tuple[float, float]:
    """(W, Z) da barra do degrau, em mm³."""
    d = e.degrau_mm
    if e.forma_do_degrau == REDONDA:
        return math.pi * d**3 / 32, d**3 / 6
    return d**3 / 6, d**3 / 4


def barras_verticais_da_gaiola(e: EntradaMarinheiro) -> int:
    """Barras verticais em volta da gaiola (fora o lado da escada), pelo espaçamento."""
    contorno = max(math.pi * e.diametro_gaiola_mm - e.largura_mm, e.verticais_mm)
    return max(1, math.ceil(contorno / e.verticais_mm))


def peso_por_metro(e: EntradaMarinheiro) -> float:
    """kg por metro de altura: montantes, barras e, se houver, a gaiola."""
    montantes = 2 * e.montante_b_mm * e.montante_t_mm
    degraus = area_do_degrau(e) * (e.largura_mm + 2 * e.montante_t_mm) * 1000 / e.passo_mm
    volume_mm3_por_m = montantes * 1000 + degraus
    if e.gaiola:
        arcos = math.pi * e.diametro_gaiola_mm * e.arco_b_mm * e.arco_t_mm * 1000 / e.arcos_mm
        verticais = barras_verticais_da_gaiola(e) * e.vertical_b_mm * e.vertical_t_mm * 1000
        volume_mm3_por_m += arcos + verticais
    return volume_mm3_por_m * 1e-9 * RHO_ACO


def calcular(e: EntradaMarinheiro) -> ResultadoMarinheiro:
    erros = validar(e)
    if erros:
        raise EscadaInvalida(" ".join(erros))
    fy = float(ACOS[e.aco][0])
    h_lance = e.altura_m / e.lances
    h_lance_mm = h_lance * 1000
    # Barras abaixo do piso de chegada: quando ele cai numa posição de barra, o piso é o degrau.
    barras = max(1, math.floor((h_lance_mm - e.primeira_barra_mm - 1e-6) / e.passo_mm) + 1)
    ultima = h_lance_mm - (e.primeira_barra_mm + (barras - 1) * e.passo_mm)
    linhas = linhas_da_geometria(e, h_lance, ultima) + linhas_da_gaiola(e)

    # Degrau: barra biapoiada entre os eixos dos montantes, carga no meio.
    vao = e.largura_mm + e.montante_t_mm
    w, z = modulos_do_degrau(e)
    m_sd = GAMMA_Q * e.carga_degrau_kN * vao / 4 / 1000  # kN·m
    m_rd = min(z, 1.5 * w) * fy / GAMMA_A1 / 1e6
    linhas.append(
        Verificacao(
            "Degrau: flexão com a carga concentrada (ELU)",
            m_sd, m_rd, "kN·m", "NBR 6120 (degrau isolado, 2,5 kN); NBR 8800 5.4.2.2",
            f"M_Sd = 1,5·P·L/4 = 1,5·{_n(e.carga_degrau_kN)}·{_n(vao, 0)}/4 = {_n(m_sd, 3)} kN·m; "
            f"M_Rd = mín(Z; 1,5·W)·f_y/γ_a1 = {_n(m_rd, 3)} kN·m "
            f"({e.forma_do_degrau.lower()} de {_n(e.degrau_mm, 1)} mm, f_y = {_n(fy, 0)} MPa)",
        )
    )  # fmt: skip

    # Montante: o lance inteiro desce até o apoio de baixo.
    peso_m = peso_por_metro(e)
    peso_lance_kN = peso_m * h_lance * G / 1000
    pessoas_kN = e.pessoas_por_lance * e.carga_degrau_kN
    n_sd = (GAMMA_G * peso_lance_kN + GAMMA_Q * pessoas_kN) / 2
    # Dois eixos: para a estrutura, a chata flete pela largura b entre as fixações; no plano da
    # escada, pela espessura t, travada pelas barras (que ligam um montante no outro).
    area = e.montante_b_mm * e.montante_t_mm
    r_b, r_t = e.montante_b_mm / math.sqrt(12), e.montante_t_mm / math.sqrt(12)
    esbeltez_b, esbeltez_t = e.fixacoes_mm / r_b, e.passo_mm / r_t
    esbeltez = max(esbeltez_b, esbeltez_t)
    lambda0 = esbeltez / math.pi * math.sqrt(fy / E_ACO)
    chi = cd.fator_chi(lambda0)
    n_rd = chi * area * fy / GAMMA_A1 / 1000
    eixos = (
        f"para a estrutura K·L/r = {_n(e.fixacoes_mm, 0)}/(b/√12 = {_n(r_b, 2)}) = "
        f"{_n(esbeltez_b, 1)}; no plano da escada, entre barras, {_n(e.passo_mm, 0)}/(t/√12 = "
        f"{_n(r_t, 2)}) = {_n(esbeltez_t, 1)}"
    )
    linhas.append(
        Verificacao(
            "Montante: compressão (ELU)",
            n_sd, n_rd, "kN", "NBR 8800 5.3 (Q = 1, seção maciça)",
            f"N_Sd = (1,25·{_n(peso_lance_kN, 3)} + 1,5·{_n(pessoas_kN)})/2 = {_n(n_sd, 3)} kN por "
            f"montante; {eixos}; λ₀ = {_n(lambda0, 3)}, χ = {_n(chi, 3)}; "
            f"N_c,Rd = χ·A·f_y/γ_a1 = {_n(n_rd, 2)} kN",
        )
    )  # fmt: skip
    linhas.append(
        Verificacao(
            "Montante: esbeltez", esbeltez, ESBELTEZ_MAXIMA, "—", "NBR 8800 5.3.4.1",
            f"{eixos}; a maior ≤ 200", status="OK" if esbeltez <= ESBELTEZ_MAXIMA else "NÃO OK",
            tipo="limite",
        )
    )  # fmt: skip

    # Suportes: o peso entre dois suportes e uma pessoa junto dele, por lado.
    v_sup = (GAMMA_G * peso_m * e.fixacoes_mm / 1000 * G / 1000 + GAMMA_Q * e.carga_degrau_kN) / 2
    braco = e.afastamento_mm + e.montante_b_mm / 2
    m_sup = v_sup * braco / 1000
    linhas.append(
        _informativo(
            "Suporte: força vertical de cálculo por lado",
            v_sup,
            "kN",
            "critério do programa",
            f"(1,25·peso entre suportes + 1,5·P)/2 = {_n(v_sup, 3)} kN; para dimensionar o "
            "suporte e os chumbadores",
        )
    )
    linhas.append(
        _informativo(
            "Suporte: momento na estrutura por lado",
            m_sup,
            "kN·m",
            "critério do programa",
            f"V·braço = {_n(v_sup, 3)}·{_n(braco, 0)} mm = {_n(m_sup, 3)} kN·m (braço até o eixo "
            "do montante)",
        )
    )
    avisos = list(AVISOS)
    if e.altura_m > ALTURA_NR35_M:
        avisos.append(f"Escada de {_n(e.altura_m)} m: acima de 2 m, trabalho em altura pela NR-35.")
    return ResultadoMarinheiro(
        entrada=e,
        altura_do_lance_m=h_lance,
        barras_por_lance=barras,
        ultima_barra_ao_piso_mm=ultima,
        peso_por_metro_kg=peso_m,
        peso_total_kg=peso_m * e.altura_m,
        vao_do_degrau_mm=vao,
        momento_degrau_kNm=m_sd,
        momento_resistente_degrau_kNm=m_rd,
        normal_montante_kN=n_sd,
        resistencia_montante_kN=n_rd,
        esbeltez_montante=esbeltez,
        suporte_vertical_kN=v_sup,
        suporte_momento_kNm=m_sup,
        verificacoes=tuple(linhas),
        avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------------------------
# Registro (memorial)
# ---------------------------------------------------------------------------------------------
def texto_de_destaque(r: ResultadoMarinheiro) -> str:
    e = r.entrada
    gaiola = (
        f"gaiola de {_n(e.diametro_gaiola_mm, 0)} mm a partir de {_n(e.inicio_gaiola_mm / 1000)} m"
        if e.gaiola
        else "sem gaiola"
    )
    return (
        f"Escada marinheiro de {_n(e.altura_m)} m em {e.lances} lance(s) de "
        f"{_n(r.altura_do_lance_m)} m, largura {_n(e.largura_mm, 0)} mm, barras de "
        f"{_n(e.degrau_mm, 1)} mm a cada {_n(e.passo_mm, 0)} mm, {gaiola}; degrau "
        f"{_n(100 * r.momento_degrau_kNm / r.momento_resistente_degrau_kNm, 0)} % e montante "
        f"{_n(100 * r.normal_montante_kN / r.resistencia_montante_kN, 0)} %; peso "
        f"{_n(r.peso_total_kg, 0)} kg."
    )


def registro(
    r: ResultadoMarinheiro,
    *,
    figuras: list[dict[str, object]] | None = None,
    contexto: dict[str, object] | None = None,
) -> dict[str, object]:
    e = r.entrada
    geral = r.status
    destaque = texto_de_destaque(r)
    entradas: dict[str, object] = {
        "altura_m": e.altura_m,
        "lances": e.lances,
        "afastamento_entre_lances_mm": e.afastamento_entre_lances_mm if e.lances > 1 else None,
        "inclinacao_graus": e.inclinacao_graus,
        "largura_mm": e.largura_mm,
        "espacamento_das_barras_mm": e.passo_mm,
        "primeira_barra_mm": e.primeira_barra_mm,
        "afastamento_da_estrutura_mm": e.afastamento_mm,
        "montantes_acima_do_piso_mm": e.ultrapassa_mm,
        "degrau": f"{e.forma_do_degrau} {_n(e.degrau_mm, 1)} mm",
        "barras_antiderrapantes": e.antiderrapante,
        "gaiola": e.gaiola,
        "inicio_da_gaiola_mm": e.inicio_gaiola_mm if e.gaiola else None,
        "gaiola_acima_do_piso_mm": e.gaiola_ultrapassa_mm if e.gaiola else None,
        "diametro_da_gaiola_mm": e.diametro_gaiola_mm if e.gaiola else None,
        "tipo_de_gaiola": e.tipo_gaiola if e.gaiola else None,
        "barras_verticais_mm": e.verticais_mm if e.gaiola else None,
        "arcos_mm": e.arcos_mm if e.gaiola else None,
        "aco": e.aco,
        "montante": f"chata {_n(e.montante_b_mm, 1)} × {_n(e.montante_t_mm, 2)} mm",
        "distancia_entre_fixacoes_mm": e.fixacoes_mm,
        "carga_no_degrau_kN": e.carga_degrau_kN,
        "pessoas_por_lance": e.pessoas_por_lance,
    }
    entradas.update(contexto or {})
    entradas = {k: v for k, v in entradas.items() if v is not None}
    resultados: dict[str, object] = {
        "status_geral": geral,
        "verificações": linhas_para_registro(list(r.verificacoes)),
        "utilizacao_maxima": numero_json(r.aproveitamento_maximo, 4),
        "destaque_memorial": destaque,
        "barras_por_lance": r.barras_por_lance,
        "peso_total_kg": numero_json(r.peso_total_kg, 1),
    }
    if figuras:
        resultados["figuras_2d"] = list(figuras)
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Escada marinheiro — H = {_n(e.altura_m)} m" + (" com gaiola" if e.gaiola else ""),
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas=entradas,
        resultados=resultados,
        metodo=(
            "Geometria pela NR-12, Anexo III, item 13 e subitem 13.1 (texto vigente) e Figura 1. "
            "Degrau biapoiado entre os eixos dos montantes com a carga concentrada do degrau "
            "isolado (NBR 6120) no meio; montante comprimido pela NBR 8800 5.3 (K = 1, Q = 1), "
            "pela largura entre as fixações e pela espessura entre as barras; forças nos "
            "suportes para o dimensionamento deles."
        ),
        premissas=[
            "Carga de 2,5 kN no degrau: a do degrau isolado da NBR 6120 (2.2.1.7 da edição de "
            "1980; Tabela 10, nota t, da de 2019), na posição mais desfavorável.",
            f"Montantes: o lance inteiro (peso próprio e {e.pessoas_por_lance} pessoa(s) de "
            f"{_n(e.carga_degrau_kN)} kN) desce até o apoio de baixo, metade em cada montante — "
            "critério do programa; a NR-12 não dá essa carga.",
            "Gaiola só pelo peso; a resistência dos arcos e das barras verticais não é verificada.",
            "Suportes: o peso entre dois suportes e uma pessoa junto dele; o braço vai até o eixo "
            "do montante.",
        ],
        alertas=[
            *(f"{v.nome}: {v.formula}" for v in r.verificacoes if v.status in ("NÃO OK", "ALERTA")),
            *r.avisos,
        ],
        referencias=[
            "NR-12, Anexo III — Meios de acesso a máquinas e equipamentos (itens 1.3, 2, 13 e "
            "13.1; texto vigente).",
            "Orientação Técnica SIT nº 8/2023 — escadas verticais (NR-12 e NR-35).",
            "ABNT NBR 6120 — Ações para o cálculo de estruturas de edificações (degrau isolado).",
            "ABNT NBR 8800 — Projeto de estruturas de aço (5.3, 5.4.2.2, Tabela 1).",
        ],
        conclusao=destaque,
    )
