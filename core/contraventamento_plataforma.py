"""Contraventamento vertical de estruturas abertas — plataformas, mezaninos, pipe racks — pela
NBR 8800 (Projeto de revisão de 2024), com o vento da NBR 6123:2023 (capítulo 8).

Da geometria e das cargas à diagonal verificada, sem precisar montar o modelo:

1. **Vento** por nível nas direções X e Y (:mod:`core.vento_estrutura_aberta`).
2. **Ações** com os seus coeficientes (Tabelas 1 e 2): peso da estrutura, piso, equipamentos,
   sobrecarga, vento (+X, −X, +Y e −Y num grupo exclusivo) e forças horizontais informadas. Cada
   ação gravitacional leva junto a **força nocional** de 0,3 % do seu peso (4.10.7.1.1), sempre no
   sentido desfavorável e em todas as combinações (4.10.7.1.4-b).
3. **Combinações**: envoltória rigorosa (:func:`core.load_combinations.extremo`) do cortante de
   cada andar — ELU normal (e excepcional, se houver ação excepcional) e a de serviço escolhida.
4. **Segunda ordem**: ``B_2 = 1/(1 − ΣN_Sd/(K·h))`` por andar (Anexo C, ``R_s = 1``), com a
   rigidez das diagonais; classifica a deslocabilidade (4.10.4) e, na média, amplifica pelo
   ``B_2`` com 80 % da rigidez (4.10.7.1.2 e 4.10.7.1.3).
5. **Distribuição** entre as linhas contraventadas, com a excentricidade informada (a fração do
   cortante da linha mais carregada), e **força na diagonal**:
   ``N = f·V·B_2/(n_painéis·n_ativas·cos α)``.
6. **Verificação** das diagonais (:mod:`core.contraventamento_barras`), **deslocamentos** do Anexo B
   (H/300 com um piso; H/400 e h/500 com dois ou mais) e as forças que a **ligação** (chapa de
   nó) precisa resistir.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from core import contraventamento_barras as cb
from core import load_combinations as comb
from core import vento_estrutura_aberta as va
from core.verificacao import Verificacao, status_geral

REF = "NBR 8800:2024"
FATOR_NOCIONAL = 0.003
RIGIDEZ_REDUZIDA = 0.80
LIMITE_PEQUENA = 1.10
LIMITE_MEDIA = 1.40

TIPO_X_TRACAO = "x_tracao"
TIPO_X_TRACAO_COMPRESSAO = "x_tracao_compressao"
TIPO_DIAGONAL_SIMPLES = "diagonal_simples"
TIPO_V_INVERTIDO = "v_invertido"
TIPOS: dict[str, str] = {
    TIPO_X_TRACAO: "X — só tração (a diagonal comprimida é desprezada)",
    TIPO_X_TRACAO_COMPRESSAO: "X — tração e compressão (ligadas no cruzamento)",
    TIPO_DIAGONAL_SIMPLES: "Diagonal simples (trabalha à tração e à compressão)",
    TIPO_V_INVERTIDO: "V invertido / chevron (uma tracionada, outra comprimida)",
}

CATEGORIA_PP = "Peso próprio de estrutura metálica"
CATEGORIA_PISO = "Elementos construtivos industrializados (grades, pisos, guarda-corpos)"
CATEGORIA_EQUIPAMENTOS = "Peso próprio de equipamentos (Projeto NBR 8800:2024)"
CATEGORIA_SOBRECARGA = (
    "Sobrecarga de uso — predominância de equipamentos fixos ou concentração de pessoas"
)
CATEGORIA_VENTO = "Vento (NBR 6123)"
CATEGORIA_FORCA_HORIZONTAL = "Forças horizontais de equipamentos em operação"

CATEGORIAS_DE_SOBRECARGA = tuple(
    c.rotulo
    for c in comb.CATEGORIAS_NBR8800
    if c.tipo == comb.TIPO_VARIAVEL and c.rotulo.startswith(("Sobrecarga", "Guarda-corpo"))
)
CATEGORIAS_DE_EQUIPAMENTO = (
    CATEGORIA_EQUIPAMENTOS,
    "Elementos construtivos em geral e equipamentos",
)
CATEGORIAS_DE_FORCA_HORIZONTAL = (
    CATEGORIA_FORCA_HORIZONTAL,
    "Ação variável truncada (limitada fisicamente)",
    "Pontes rolantes — pilares e subestruturas das vigas de rolamento",
    "Ação excepcional (impacto, explosão, incêndio)",
)
DIRECOES = ("X", "Y")
GRUPO_VENTO = "Vento"


class ContraventamentoInvalido(ValueError):
    """Dado que o cálculo não aceita; a mensagem diz o que corrigir."""


def diagonais_por_painel(tipo: str) -> int:
    return 1 if tipo == TIPO_DIAGONAL_SIMPLES else 2


def diagonais_ativas(tipo: str) -> int:
    """Diagonais que dividem o cortante do painel (as que trabalham)."""
    return 1 if tipo in (TIPO_X_TRACAO, TIPO_DIAGONAL_SIMPLES) else 2


def trabalha_a_compressao(tipo: str) -> bool:
    return tipo != TIPO_X_TRACAO


# ---------------------------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ForcaHorizontal:
    """Força horizontal característica aplicada num nível (equipamento, impacto, tração de correia...)."""

    nome: str
    direcao: str  # "X" ou "Y"
    nivel: int
    valor_kN: float
    categoria: str = CATEGORIA_FORCA_HORIZONTAL
    reversivel: bool = True  # atua nos dois sentidos


@dataclass(frozen=True)
class Cargas:
    """Valores característicos por área de piso (cada nível) e forças horizontais."""

    peso_estrutura_kN_m2: float = 0.60
    peso_piso_kN_m2: float = 0.45
    sobrecarga_kN_m2: float = 5.00
    categoria_sobrecarga: str = CATEGORIA_SOBRECARGA
    categoria_equipamentos: str = CATEGORIA_EQUIPAMENTOS
    forcas_horizontais: tuple[ForcaHorizontal, ...] = ()


@dataclass(frozen=True)
class SistemaDeContraventamento:
    """O contraventamento das linhas de uma direção (as linhas paralelas a ela)."""

    tipo: str = TIPO_X_TRACAO
    diagonal: cb.Diagonal = field(default_factory=cb.Diagonal)
    linhas: int = 2
    paineis_por_linha: int = 1


@dataclass(frozen=True)
class EntradaContraventamento:
    comprimento_x_m: float = 12.0
    largura_y_m: float = 6.0
    cotas_m: tuple[float, ...] = (4.0,)
    vaos_x: int = 2
    vaos_y: int = 1
    largura_pilar_m: float = 0.25
    altura_viga_m: float = 0.30
    guarda_corpo: bool = True
    altura_guarda_corpo_m: float = va.ALTURA_GUARDA_CORPO_PADRAO_M
    indice_guarda_corpo: float = va.INDICE_GUARDA_CORPO_PADRAO
    equipamentos: tuple[va.Equipamento, ...] = ()
    vento: va.ParametrosVento = field(default_factory=va.ParametrosVento)
    cargas: Cargas = field(default_factory=Cargas)
    contraventamento_x: SistemaDeContraventamento = field(default_factory=SistemaDeContraventamento)
    contraventamento_y: SistemaDeContraventamento = field(default_factory=SistemaDeContraventamento)
    excentricidade: float = 0.075  # fração da dimensão perpendicular à força
    ligadas_no_cruzamento: bool = True  # X: as diagonais se travam no cruzamento
    combinacao_de_servico: str = comb.ELS_RARA

    def sistema(self, direcao: str) -> SistemaDeContraventamento:
        return self.contraventamento_x if direcao == "X" else self.contraventamento_y

    def painel_m(self, direcao: str) -> float:
        """Largura de um painel nas linhas paralelas à direção."""
        return (
            self.comprimento_x_m / self.vaos_x if direcao == "X" else self.largura_y_m / self.vaos_y
        )

    def dimensao_perpendicular_m(self, direcao: str) -> float:
        return self.largura_y_m if direcao == "X" else self.comprimento_x_m

    @property
    def area_planta_m2(self) -> float:
        return self.comprimento_x_m * self.largura_y_m


def geometria_do_vento(e: EntradaContraventamento) -> va.GeometriaAberta:
    """A geometria que o cálculo do vento usa, com as diagonais dos dois sistemas."""
    sx, sy = e.contraventamento_x, e.contraventamento_y
    return va.GeometriaAberta(
        comprimento_x_m=e.comprimento_x_m,
        largura_y_m=e.largura_y_m,
        cotas_m=tuple(e.cotas_m),
        vaos_x=e.vaos_x,
        vaos_y=e.vaos_y,
        largura_pilar_m=e.largura_pilar_m,
        altura_viga_m=e.altura_viga_m,
        largura_diagonal_x_m=cb.largura_vista_mm(sx.diagonal) / 1e3,
        diagonais_por_painel_x=diagonais_por_painel(sx.tipo),
        meio_painel_x=sx.tipo == TIPO_V_INVERTIDO,
        paineis_contraventados_x=sx.paineis_por_linha,
        linhas_contraventadas_x=sx.linhas,
        largura_diagonal_y_m=cb.largura_vista_mm(sy.diagonal) / 1e3,
        diagonais_por_painel_y=diagonais_por_painel(sy.tipo),
        meio_painel_y=sy.tipo == TIPO_V_INVERTIDO,
        paineis_contraventados_y=sy.paineis_por_linha,
        linhas_contraventadas_y=sy.linhas,
        guarda_corpo=e.guarda_corpo,
        altura_guarda_corpo_m=e.altura_guarda_corpo_m,
        indice_guarda_corpo=e.indice_guarda_corpo,
        equipamentos=tuple(e.equipamentos),
    )


def validar_entrada(e: EntradaContraventamento) -> list[str]:
    erros: list[str] = []
    for direcao in DIRECOES:
        s = e.sistema(direcao)
        if s.tipo not in TIPOS:
            erros.append(f"Tipo de contraventamento desconhecido em {direcao}: {s.tipo!r}.")
        erros.extend(f"Diagonal em {direcao}: {m}" for m in cb.validar(s.diagonal))
        if s.tipo != TIPO_X_TRACAO and s.diagonal.familia == cb.FAMILIA_BARRA_REDONDA:
            erros.append(
                f"Em {direcao}, a barra redonda (tirante) só serve para X só tração: ela não "
                "trabalha à compressão."
            )
    if erros:
        return erros
    erros.extend(va.validar_geometria(geometria_do_vento(e)))
    c = e.cargas
    for nome, valor in (
        ("O peso da estrutura", c.peso_estrutura_kN_m2),
        ("O peso do piso", c.peso_piso_kN_m2),
        ("A sobrecarga", c.sobrecarga_kN_m2),
    ):
        if not (math.isfinite(valor) and valor >= 0):
            erros.append(f"{nome} não pode ser negativo.")
    if c.categoria_sobrecarga not in CATEGORIAS_DE_SOBRECARGA:
        erros.append(f"Categoria de sobrecarga desconhecida: {c.categoria_sobrecarga!r}.")
    if c.categoria_equipamentos not in CATEGORIAS_DE_EQUIPAMENTO:
        erros.append(f"Categoria de equipamentos desconhecida: {c.categoria_equipamentos!r}.")
    nomes = set()
    for f in c.forcas_horizontais:
        if f.direcao not in DIRECOES:
            erros.append(f"{f.nome}: direção precisa ser X ou Y.")
        if not 1 <= f.nivel <= len(e.cotas_m):
            erros.append(f"{f.nome}: o nível precisa estar entre 1 e {len(e.cotas_m)}.")
        if f.categoria not in CATEGORIAS_DE_FORCA_HORIZONTAL:
            erros.append(f"{f.nome}: categoria desconhecida ({f.categoria!r}).")
        if not math.isfinite(f.valor_kN):
            erros.append(f"{f.nome}: valor inválido.")
        if not f.nome.strip() or f.nome in nomes:
            erros.append("Cada força horizontal precisa de um nome único.")
        nomes.add(f.nome)
    if not 0.0 <= e.excentricidade <= 0.5:
        erros.append("A excentricidade vai de 0 a 0,5 da dimensão perpendicular à força.")
    if e.combinacao_de_servico not in (comb.ELS_RARA, comb.ELS_FREQUENTE):
        erros.append("A combinação de serviço para os deslocamentos é a rara ou a frequente.")
    return erros


# ---------------------------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class AndarNaDirecao:
    direcao: str
    andar: int  # 1 = entre a base e o primeiro piso
    altura_mm: float
    painel_mm: float
    projecao_mm: float  # projeção horizontal da diagonal
    comprimento_diagonal_mm: float
    angulo_horizontal_graus: float
    cortante_elu: comb.Extremo
    cortante_servico: comb.Extremo | None
    gravidade_elu: comb.Extremo
    rigidez_kN_mm: float  # do andar (todas as linhas)
    b2: float
    b2_reduzido: float
    deslocabilidade: str
    amplificacao: float
    fracao_da_linha: float
    forca_na_linha_kN: float  # cortante de cálculo na linha mais carregada (já amplificado)
    tracao_kN: float
    compressao_kN: float
    deslocamento_mm: float  # do andar, em serviço, na linha mais carregada
    forca_no_pilar_kN: float  # acréscimo de força axial no pilar do painel (tombamento)

    @property
    def theta_vertical_graus(self) -> float:
        """Ângulo da diagonal com a vertical (o θ do Design Guide 29)."""
        return 90.0 - self.angulo_horizontal_graus


@dataclass(frozen=True)
class ResultadoContraventamento:
    entrada: EntradaContraventamento
    vento: va.ResultadoVentoAberto
    acoes: tuple[comb.AcaoEstrutural, ...]
    andares: tuple[AndarNaDirecao, ...]
    verificacoes: tuple[Verificacao, ...]
    deslocamento_topo_mm: dict[str, float]
    avisos: tuple[str, ...] = ()

    def andares_da_direcao(self, direcao: str) -> list[AndarNaDirecao]:
        return [a for a in self.andares if a.direcao == direcao]

    @property
    def status(self) -> str:
        return status_geral(list(self.verificacoes))

    @property
    def aproveitamento_maximo(self) -> float:
        valores = [
            v.aproveitamento
            for v in self.verificacoes
            if v.tipo == "resistencia" and v.aproveitamento is not None
        ]
        finitos = [v for v in valores if math.isfinite(v)]
        if len(finitos) < len(valores):
            return math.inf
        return max(finitos) if finitos else 0.0

    def diagonal_governante(self) -> AndarNaDirecao:
        """O andar e a direção com a maior força numa diagonal (tração ou compressão)."""
        return max(self.andares, key=lambda a: max(a.tracao_kN, a.compressao_kN))


# ---------------------------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------------------------
def _efeito(tipo: str, direcao: str | None, andar: int) -> str:
    return f"{tipo}_{direcao}_{andar}" if direcao else f"{tipo}_{andar}"


def montar_acoes(
    e: EntradaContraventamento, vento: va.ResultadoVentoAberto
) -> tuple[comb.AcaoEstrutural, ...]:
    """Ações características com os esforços de cada andar (cortante, serviço e gravidade).

    ``V_d_i``: cortante de cálculo do andar i na direção d (com a força nocional);
    ``S_d_i``: cortante para os deslocamentos (sem a nocional); ``P_i``: força gravitacional
    acima do andar i.
    """
    n = len(e.cotas_m)
    area = e.area_planta_m2
    acoes: list[comb.AcaoEstrutural] = []

    def gravitacional(nome: str, categoria: str, por_nivel: Sequence[float]) -> None:
        if not any(v > 0 for v in por_nivel):
            return
        efeitos: dict[str, float] = {}
        reversiveis: set[str] = set()
        for i in range(1, n + 1):
            acima = sum(por_nivel[i - 1 :])
            efeitos[_efeito("P", None, i)] = acima
            for d in DIRECOES:
                chave = _efeito("V", d, i)
                efeitos[chave] = FATOR_NOCIONAL * acima
                reversiveis.add(chave)
        acoes.append(
            comb.acao_da_categoria(
                nome, categoria, efeitos=efeitos, efeitos_reversiveis=reversiveis
            )
        )

    c = e.cargas
    gravitacional("Estrutura", CATEGORIA_PP, [c.peso_estrutura_kN_m2 * area] * n)
    gravitacional("Piso", CATEGORIA_PISO, [c.peso_piso_kN_m2 * area] * n)
    pesos_eq = [sum(eq.peso_kN for eq in e.equipamentos if eq.nivel == i) for i in range(1, n + 1)]
    gravitacional("Equipamentos", c.categoria_equipamentos, pesos_eq)
    gravitacional("Sobrecarga", c.categoria_sobrecarga, [c.sobrecarga_kN_m2 * area] * n)

    for d in DIRECOES:
        cortantes = vento.direcao(d).cortantes_dos_andares_kN
        for sinal, rotulo in ((1.0, "+"), (-1.0, "−")):
            efeitos = {}
            for i in range(1, n + 1):
                efeitos[_efeito("V", d, i)] = sinal * cortantes[i - 1]
                efeitos[_efeito("S", d, i)] = sinal * cortantes[i - 1]
            acoes.append(
                comb.acao_da_categoria(
                    f"Vento {rotulo}{d}", CATEGORIA_VENTO, grupo=GRUPO_VENTO, efeitos=efeitos
                )
            )
    for f in c.forcas_horizontais:
        efeitos = {}
        for i in range(1, f.nivel + 1):
            efeitos[_efeito("V", f.direcao, i)] = f.valor_kN
            efeitos[_efeito("S", f.direcao, i)] = f.valor_kN
        acoes.append(
            comb.acao_da_categoria(
                f.nome,
                f.categoria,
                efeitos=efeitos,
                efeitos_reversiveis=set(efeitos) if f.reversivel else (),
            )
        )
    return tuple(acoes)


# ---------------------------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------------------------
def _fracao_da_linha_mais_carregada(linhas: int, excentricidade: float) -> float:
    """``1/n + e·y_máx/Σy²`` com as linhas igualmente espaçadas na dimensão perpendicular ``L``
    (e em fração de L). Com duas linhas nas bordas: ``0,5 + e``."""
    if linhas <= 1:
        return 1.0
    posicoes = [k / (linhas - 1) - 0.5 for k in range(linhas)]
    soma = sum(y * y for y in posicoes)
    return 1.0 / linhas + excentricidade * max(abs(y) for y in posicoes) / soma


def _extremo_de_calculo(
    acoes: Sequence[comb.AcaoEstrutural], efeito: str, tem_excepcional: bool
) -> comb.Extremo:
    candidatos = [comb.maior_modulo(acoes, efeito, comb.ELU_NORMAL)]
    if tem_excepcional:
        candidatos.append(comb.maior_modulo(acoes, efeito, comb.ELU_EXCEPCIONAL))
    validos = [c for c in candidatos if c is not None]
    return max(validos, key=lambda c: abs(c.valor))


def calcular_contraventamento(e: EntradaContraventamento) -> ResultadoContraventamento:
    erros = validar_entrada(e)
    if erros:
        raise ContraventamentoInvalido(" ".join(erros))
    vento = va.calcular_vento_aberto(geometria_do_vento(e), e.vento)
    acoes = montar_acoes(e, vento)
    tem_excepcional = any(a.tipo == comb.TIPO_EXCEPCIONAL for a in acoes)
    n = len(e.cotas_m)
    alturas_m = (e.cotas_m[0], *(b - a for a, b in zip(e.cotas_m, e.cotas_m[1:], strict=False)))
    andares: list[AndarNaDirecao] = []
    linhas: list[Verificacao] = []
    avisos: list[str] = list(vento.avisos)
    deslocamento_topo: dict[str, float] = {}

    for d in DIRECOES:
        s = e.sistema(d)
        diag = s.diagonal
        area_diag = cb.area_bruta_mm2(diag)
        painel_mm = e.painel_m(d) * 1e3
        projecao_mm = painel_mm / 2.0 if s.tipo == TIPO_V_INVERTIDO else painel_mm
        fracao = _fracao_da_linha_mais_carregada(s.linhas, e.excentricidade)
        if s.linhas == 1:
            avisos.append(
                f"Direção {d}: uma só linha contraventada não resiste à torção em planta — a "
                "excentricidade precisa ser levada pelas linhas da outra direção e por um piso "
                "que funcione como diafragma."
            )
        topo = 0.0
        parciais = []
        for i in range(1, n + 1):
            h_mm = alturas_m[i - 1] * 1e3
            comprimento = math.hypot(projecao_mm, h_mm)
            cos_a = projecao_mm / comprimento
            k_linha = (
                s.paineis_por_linha
                * diagonais_ativas(s.tipo)
                * cb.E_MPA
                * area_diag
                * cos_a**2
                / comprimento
                / 1e3
            )
            cortante = _extremo_de_calculo(acoes, _efeito("V", d, i), tem_excepcional)
            gravidade = comb.extremo(acoes, _efeito("P", None, i), comb.ELU_NORMAL, 1)
            if gravidade is None:  # pragma: no cover - sempre há ELU normal
                raise ContraventamentoInvalido("Sem combinação para a força gravitacional.")
            servico = comb.maior_modulo(acoes, _efeito("S", d, i), e.combinacao_de_servico)
            k_andar = s.linhas * k_linha
            n_sd = max(gravidade.valor, 0.0)
            b2 = _b2(n_sd, k_andar, h_mm)
            b2_red = _b2(n_sd, RIGIDEZ_REDUZIDA * k_andar, h_mm)
            if b2 <= LIMITE_PEQUENA:
                classe, amplificacao = "pequena", 1.0
            elif b2 <= LIMITE_MEDIA:
                classe, amplificacao = "média", b2_red
            else:
                classe, amplificacao = "grande", b2_red
            parciais.append(
                (
                    i,
                    h_mm,
                    comprimento,
                    cos_a,
                    k_linha,
                    k_andar,
                    cortante,
                    gravidade,
                    servico,
                    b2,
                    b2_red,
                    classe,
                    amplificacao,
                )
            )
        # Momento de tombamento na base de cada andar: M_i = Σ_{k ≥ i} V_k·h_k (forças de cálculo).
        momentos = []
        for idx in range(len(parciais)):
            momentos.append(sum(abs(p[6].valor) * p[12] * p[1] for p in parciais[idx:]))
        for (
            (
                i,
                h_mm,
                comprimento,
                cos_a,
                k_linha,
                k_andar,
                cortante,
                gravidade,
                servico,
                b2,
                b2_red,
                classe,
                amplificacao,
            ),
            momento,
        ) in zip(parciais, momentos, strict=True):
            v_linha = fracao * abs(cortante.valor) * amplificacao
            n_diag = v_linha / (s.paineis_por_linha * diagonais_ativas(s.tipo) * cos_a)
            v_serv = abs(servico.valor) if servico is not None else 0.0
            desloc = fracao * v_serv / k_linha if k_linha > 0 else math.inf
            topo += desloc
            andar = AndarNaDirecao(
                direcao=d,
                andar=i,
                altura_mm=h_mm,
                painel_mm=painel_mm,
                projecao_mm=projecao_mm,
                comprimento_diagonal_mm=comprimento,
                angulo_horizontal_graus=math.degrees(math.atan2(h_mm, projecao_mm)),
                cortante_elu=cortante,
                cortante_servico=servico,
                gravidade_elu=gravidade,
                rigidez_kN_mm=k_andar,
                b2=b2,
                b2_reduzido=b2_red,
                deslocabilidade=classe,
                amplificacao=amplificacao,
                fracao_da_linha=fracao,
                forca_na_linha_kN=v_linha,
                tracao_kN=n_diag,
                compressao_kN=n_diag if trabalha_a_compressao(s.tipo) else 0.0,
                deslocamento_mm=desloc,
                forca_no_pilar_kN=fracao * momento / (s.paineis_por_linha * painel_mm),
            )
            andares.append(andar)
            linhas.extend(_verificacoes_do_andar(e, s, andar))
        deslocamento_topo[d] = topo
        linhas.extend(_verificacoes_de_deslocamento(e, d, topo))
    return ResultadoContraventamento(
        entrada=e,
        vento=vento,
        acoes=acoes,
        andares=tuple(andares),
        verificacoes=tuple(linhas),
        deslocamento_topo_mm=deslocamento_topo,
        avisos=tuple(dict.fromkeys(avisos)),
    )


def _b2(n_sd_kN: float, rigidez_kN_mm: float, altura_mm: float) -> float:
    """``B_2 = 1/(1 − (1/R_s)·(Δh/h)·ΣN_Sd/ΣH_Sd)`` com ``Δh/ΣH = 1/K`` e ``R_s = 1`` (Anexo C)."""
    if rigidez_kN_mm <= 0:
        return math.inf
    razao = n_sd_kN / (rigidez_kN_mm * altura_mm)
    return math.inf if razao >= 1.0 else 1.0 / (1.0 - razao)


def _n(valor: float, casas: int = 1) -> str:
    if not math.isfinite(valor):
        return "∞"
    return f"{valor:.{casas}f}".replace(".", ",")


def _verificacoes_do_andar(
    e: EntradaContraventamento, s: SistemaDeContraventamento, a: AndarNaDirecao
) -> list[Verificacao]:
    prefixo = f"{a.direcao}, andar {a.andar}"
    linhas: list[Verificacao] = []
    # Segunda ordem
    if math.isinf(a.b2):
        linhas.append(
            Verificacao(
                f"{prefixo}: estabilidade do andar (B₂)",
                None,
                None,
                "-",
                f"{REF} 4.10.4 e Anexo C",
                "ΣN_Sd ≥ K·h: o contraventamento não estabiliza o andar — aumente a seção das "
                "diagonais ou o número de painéis.",
                status="NÃO OK",
                tipo="limite",
            )
        )
    else:
        status = "NÃO OK" if a.deslocabilidade == "grande" else "OK"
        linhas.append(
            Verificacao(
                f"{prefixo}: deslocabilidade do andar (B₂ = {_n(a.b2, 3)})",
                a.b2,
                LIMITE_MEDIA,
                "-",
                f"{REF} 4.10.4, 4.10.7 e Anexo C",
                f"B₂ = 1/(1 − ΣN_Sd/(K·h)) com ΣN_Sd = {_n(a.gravidade_elu.valor)} kN, "
                f"K = {_n(a.rigidez_kN_mm, 2)} kN/mm, h = {_n(a.altura_mm, 0)} mm: "
                f"{a.deslocabilidade} deslocabilidade"
                + (
                    f"; esforços amplificados por B₂ com 80 % da rigidez = {_n(a.b2_reduzido, 3)}"
                    if a.deslocabilidade != "pequena"
                    else "; forças nocionais em todas as combinações (4.10.7.1.4)"
                ),
                status=status,
                aproveitamento=a.b2 / LIMITE_MEDIA,
                tipo="limite",
            )
        )
    # Esforço no andar (informativo, com a combinação governante)
    linhas.append(
        Verificacao(
            f"{prefixo}: cortante de cálculo do andar",
            None,
            abs(a.cortante_elu.valor),
            "kN",
            f"{REF} 4.8.7.2",
            f"{a.cortante_elu.estado_limite}: {a.cortante_elu.expressao}; linha mais carregada "
            f"recebe {_n(100 * a.fracao_da_linha, 1)} % → {_n(a.forca_na_linha_kN)} kN",
            status="INFO",
            tipo="informativo",
        )
    )
    resultado = cb.verificar_diagonal(
        s.diagonal,
        prefixo,
        comprimento_mm=a.comprimento_diagonal_mm,
        comprimento_destravado_mm=_comprimento_destravado(e, s, a),
        tracao_kN=a.tracao_kN,
        compressao_kN=a.compressao_kN,
    )
    linhas.extend(resultado.verificacoes)
    linhas.append(
        Verificacao(
            f"{prefixo}: acréscimo de força nos pilares do painel",
            None,
            a.forca_no_pilar_kN,
            "kN",
            f"{REF} 4.8.7.2",
            "Tração ou compressão nos pilares do painel contraventado pelo tombamento: "
            "M/(n_painéis·b), com M = Σ V_k·h_k dos andares acima — some às forças "
            "gravitacionais na verificação dos pilares e das bases (arrancamento).",
            status="INFO",
            tipo="informativo",
        )
    )
    return linhas


def _comprimento_destravado(
    e: EntradaContraventamento, s: SistemaDeContraventamento, a: AndarNaDirecao
) -> float:
    if s.tipo in (TIPO_X_TRACAO, TIPO_X_TRACAO_COMPRESSAO) and e.ligadas_no_cruzamento:
        return a.comprimento_diagonal_mm / 2.0
    return a.comprimento_diagonal_mm


def _verificacoes_de_deslocamento(
    e: EntradaContraventamento, d: str, topo_mm: float
) -> list[Verificacao]:
    altura_mm = e.cotas_m[-1] * 1e3
    linhas: list[Verificacao] = []
    estado = e.combinacao_de_servico
    if len(e.cotas_m) == 1:
        limite = altura_mm / 300.0
        linhas.append(
            Verificacao(
                f"{d}: deslocamento horizontal do topo",
                topo_mm,
                limite,
                "mm",
                f"{REF} Anexo B, Tabela B.1",
                f"{estado}; δ = Σ f·V_serv/K_linha (só a deformação axial das diagonais) ≤ H/300 "
                f"= {_n(altura_mm, 0)}/300",
                tipo="limite",
            )
        )
        return linhas
    linhas.append(
        Verificacao(
            f"{d}: deslocamento horizontal do topo",
            topo_mm,
            altura_mm / 400.0,
            "mm",
            f"{REF} Anexo B, Tabela B.1",
            f"{estado}; δ = Σ f·V_serv/K_linha ≤ H/400 = {_n(altura_mm, 0)}/400",
            tipo="limite",
        )
    )
    return linhas


def verificacoes_interpavimento(r: ResultadoContraventamento) -> list[Verificacao]:
    """``h/500`` entre pisos consecutivos (edificações de dois ou mais pavimentos)."""
    if len(r.entrada.cotas_m) < 2:
        return []
    return [
        Verificacao(
            f"{a.direcao}, andar {a.andar}: deslocamento entre pisos",
            a.deslocamento_mm,
            a.altura_mm / 500.0,
            "mm",
            f"{REF} Anexo B, Tabela B.1",
            f"{r.entrada.combinacao_de_servico}; Δ = f·V_serv/K_linha ≤ h/500 = "
            f"{_n(a.altura_mm, 0)}/500",
            tipo="limite",
        )
        for a in r.andares
    ]


def calcular(e: EntradaContraventamento) -> ResultadoContraventamento:
    """Cálculo completo, com o interpavimento junto das demais verificações."""
    r = calcular_contraventamento(e)
    extra = verificacoes_interpavimento(r)
    if not extra:
        return r
    return replace(r, verificacoes=(*r.verificacoes, *extra))


# ---------------------------------------------------------------------------------------------
# Para a ligação (chapa de nó)
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ForcasParaLigacao:
    direcao: str
    andar: int
    tracao_kN: float
    compressao_kN: float
    theta_vertical_graus: float
    diagonal: str


def forcas_para_ligacao(r: ResultadoContraventamento) -> ForcasParaLigacao:
    """A diagonal mais solicitada: forças de cálculo e o ângulo com a vertical (para o DG29)."""
    a = r.diagonal_governante()
    return ForcasParaLigacao(
        direcao=a.direcao,
        andar=a.andar,
        tracao_kN=a.tracao_kN,
        compressao_kN=a.compressao_kN,
        theta_vertical_graus=a.theta_vertical_graus,
        diagonal=r.entrada.sistema(a.direcao).diagonal.perfil,
    )
