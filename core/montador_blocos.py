"""O catálogo de blocos do montador de fórmulas.

Para acrescentar uma equação, basta acrescentar um ``Bloco`` a ``BLOCOS``: a prancheta, os campos e a
conta leem daqui. Um bloco declara as portas e tem uma função ``calcular`` que recebe o ``Contexto`` e
devolve o valor de cada saída. Fórmula de viga ou de origem de esforço usa ``origem``, que precisa só
das expressões. Os blocos de fluidos ficam em :mod:`core.montador_fluidos`.

Há quatro tipos de fio. O da **seção** leva a seção e os esforços somados até ali, e por isso os
esforços ficam em fila: Seção → Flexão → Cortante → Critério. O de **valor** troca uma letra pela
fórmula de outro bloco, como o M da flexão por F·L/4 da viga. O de **material** leva as propriedades
de uma vez. O de **condição** leva "isto ≤ aquilo" até o bloco do resultado.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import sympy as sp

from core import elementos_eixos as ee
from core import elementos_vigas as ev
from core import fatigue as ft
from core import material_catalog as mc
from core import montador_formula as mf
from core import montador_grandezas as g
from core import montador_secoes as ms
from core.montador_funcoes import (
    MATERIAIS_DE_FADIGA,
    FatorSuperficie,
    FatorTamanho,
    KtRessalto,
    LimiteBase,
    ResistenciaEmVida,
    SensibilidadeNeuber,
)
from core.montador_grandezas import Grandeza
from core.montador_secoes import Estado, Secao, Validade

SECAO = "secao"
VALOR = "valor"
CONDICAO = "condicao"
MATERIAL = "material"
LINHA = "linha"

SOLIDOS = "solidos"
FLUIDOS = "fluidos"
COMUM = "comum"

GRUPO_SECAO = "Seção"
GRUPO_ORIGEM = "De onde vem o esforço"
GRUPO_ESFORCO = "Esforços"
GRUPO_MATERIAL = "Material"
GRUPO_CRITERIO = "Critério"
GRUPO_PECAS = "Peças do eixo"
GRUPO_FLUIDO = "Fluido"
GRUPO_TUBULACAO = "Tubulação"
GRUPO_VERIFICACAO = "Verificações"
GRUPO_EQUACOES = "Equações"
GRUPO_RESULTADO = "Resultado"
GRUPO_OUTROS = "Outros cálculos"
GRUPOS = (
    GRUPO_SECAO,
    GRUPO_ORIGEM,
    GRUPO_ESFORCO,
    GRUPO_MATERIAL,
    GRUPO_CRITERIO,
    GRUPO_PECAS,
    GRUPO_FLUIDO,
    GRUPO_TUBULACAO,
    GRUPO_VERIFICACAO,
    GRUPO_EQUACOES,
    GRUPO_RESULTADO,
    GRUPO_OUTROS,
)
#: A cor do cabeçalho do bloco na prancheta.
#: A ordem da biblioteca: primeiro o que começa a montagem, e o resultado no fim.
ORDEM_DOS_GRUPOS = (
    GRUPO_SECAO,
    GRUPO_ORIGEM,
    GRUPO_ESFORCO,
    GRUPO_MATERIAL,
    GRUPO_CRITERIO,
    GRUPO_PECAS,
    GRUPO_FLUIDO,
    GRUPO_TUBULACAO,
    GRUPO_VERIFICACAO,
    GRUPO_EQUACOES,
    GRUPO_RESULTADO,
    GRUPO_OUTROS,
)
#: A faixa de cima de cada cartão da prancheta.
CATEGORIA_DO_GRUPO = {
    GRUPO_SECAO: "SEÇÃO",
    GRUPO_ORIGEM: "ORIGEM DO ESFORÇO",
    GRUPO_ESFORCO: "ESFORÇO",
    GRUPO_MATERIAL: "PROPRIEDADES",
    GRUPO_CRITERIO: "VERIFICAÇÃO",
    GRUPO_PECAS: "PEÇA DO EIXO",
    GRUPO_FLUIDO: "FLUIDO",
    GRUPO_TUBULACAO: "TUBULAÇÃO",
    GRUPO_VERIFICACAO: "VERIFICAÇÃO",
    GRUPO_EQUACOES: "EQUAÇÃO",
    GRUPO_RESULTADO: "DECISÃO",
    GRUPO_OUTROS: "OUTROS CÁLCULOS",
}
CLASSE_DO_GRUPO = {
    GRUPO_SECAO: "g-secao",
    GRUPO_ORIGEM: "g-origem",
    GRUPO_ESFORCO: "g-esforco",
    GRUPO_MATERIAL: "g-material",
    GRUPO_CRITERIO: "g-criterio",
    GRUPO_PECAS: "g-criterio",
    GRUPO_FLUIDO: "g-secao",
    GRUPO_TUBULACAO: "g-esforco",
    GRUPO_VERIFICACAO: "g-criterio",
    GRUPO_EQUACOES: "g-origem",
    GRUPO_RESULTADO: "g-resultado",
    GRUPO_OUTROS: "g-material",
}

RESULTADO = "resultado"
REFERENCIA = "referencia"
FORMULA = "formula"
SEM_MATERIAL = "Escolha o material"
FLECHA_RELATIVA = "Relação L/δ"
FLECHA_ABSOLUTA = "Valor de δ"
FLECHAS = (FLECHA_RELATIVA, FLECHA_ABSOLUTA)
INFORMAR_FADIGA = "Informar alternado e médio"
EIXO_GIRANDO = "Eixo girando: flexão alternada e torque constante"
ESFORCOS_DA_FADIGA = (INFORMAR_FADIGA, EIXO_GIRANDO)
GOODMAN = "DE-Goodman"
GERBER = "DE-Gerber"
SODERBERG = "DE-Soderberg"
ELIPTICO = "DE-ASME elíptico"
CRITERIOS_DE_FADIGA = (GOODMAN, GERBER, SODERBERG, ELIPTICO)
_FORMULA_DA_FADIGA = {
    GOODMAN: "σ_a'/S_e + σ_m'/S_ut ≤ 1/n",
    GERBER: "n·σ_a'/S_e + (n·σ_m'/S_ut)² ≤ 1",
    SODERBERG: "σ_a'/S_e + σ_m'/S_y ≤ 1/n",
    ELIPTICO: "(n·σ_a'/S_e)² + (n·σ_m'/S_y)² ≤ 1",
}
VIDA_INFINITA = "Vida infinita"
VIDA_FINITA = "Vida finita: N_c ciclos"
VIDAS = (VIDA_INFINITA, VIDA_FINITA)
TAMANHO_PELO_D = "Pelo diâmetro d da seção"
TAMANHO_INFORMADO = "Informar k_b"
TAMANHOS = (TAMANHO_PELO_D, TAMANHO_INFORMADO)
#: k_c de Shigley. Com von Mises das parcelas, que é o que o bloco de fadiga usa, k_c é 1.
CARREGAMENTOS = {"Flexão ou combinado": 1.0, "Axial": 0.85, "Torção pura": 0.59}
ACABAMENTO_PADRAO = "Usinado ou estirado a frio"
CONFIABILIDADE_PADRAO = "50 %"

#: E e G típicos por categoria do cadastro, em MPa. O cadastro só guarda S_y e S_ut.
MODULOS_POR_CATEGORIA = {
    "aco": (200000.0, 80000.0, "aço"),
    "aluminio": (71000.0, 27000.0, "alumínio"),
    "cobre": (110000.0, 41000.0, "liga de cobre"),
    "ferro_fundido": (100000.0, 41000.0, "ferro fundido"),
}


class ErroDeBloco(ValueError):
    """O que falta no bloco, em palavras de quem está montando."""


@dataclass(frozen=True)
class Porta:
    chave: str
    rotulo: str
    tipo: str
    dimensao: str | None = None  # no fio de valor, só liga com a mesma dimensão
    varias: bool = False  # aceita mais de um fio


@dataclass(frozen=True)
class Opcao:
    """Escolha do bloco que não é uma letra: a tela mostra uma lista."""

    chave: str
    rotulo: str
    ajuda: str
    escolhas: tuple[str, ...] | Callable[[], tuple[str, ...]]
    padrao: str

    def lista(self) -> tuple[str, ...]:
        return self.escolhas() if callable(self.escolhas) else self.escolhas


@dataclass(frozen=True)
class Condicao:
    """``esquerda`` ≤ ``direita``: a inequação de um critério num ponto da seção.

    Com ``igualdade``, é uma equação: não há limite, e o que se quer é a letra que fecha a conta.
    """

    nome: str
    criterio: str
    esquerda: sp.Expr
    direita: sp.Expr
    letra: str  # LaTeX do lado esquerdo
    ponto: str = ""
    tensoes: tuple[tuple[str, sp.Expr], ...] = ()
    validade: tuple[Validade, ...] = ()
    positiva: bool = True  # no estado biaxial, σ_x − σ_y pode dar negativo, e o módulo fica
    igualdade: bool = False
    no: str = ""  # o bloco que gerou a condição
    caso: str = ""  # o caso de carga, quando a montagem tem mais de um

    @property
    def letras(self) -> set[sp.Symbol]:
        return self.esquerda.free_symbols | self.direita.free_symbols


@dataclass(frozen=True)
class Material:
    """O que passa no fio de material. A letra fica na fórmula, com o valor nos campos."""

    sy: sp.Expr
    sut: sp.Expr
    e: sp.Expr
    g: sp.Expr


@dataclass
class Contexto:
    """O que um bloco enxerga quando calcula."""

    indice: int
    opcoes: Mapping[str, str]
    ligados: Mapping[str, Any]
    numerar: bool = False
    zeros: frozenset[str] = frozenset()  # letras com valor zero: somem da conta
    grandezas: dict[str, Grandeza] = field(default_factory=dict)
    padroes: dict[str, float] = field(default_factory=dict)
    origens: dict[str, str] = field(default_factory=dict)
    alertas: list[str] = field(default_factory=list)
    hipoteses: list[str] = field(default_factory=list)
    marcas: set[str] = field(default_factory=set)
    proprias: list[str] = field(default_factory=list)
    #: Hipóteses do bloco que só se conferem com os números, como a ≤ L/2 na viga.
    validades: list[Validade] = field(default_factory=list)

    def _numerada(self, grandeza: Grandeza, fixa: bool = False) -> Grandeza:
        return grandeza.com_indice(self.indice) if self.numerar and not fixa else grandeza

    def letra(self, grandeza: Grandeza, porta: str | None = None, *, fixa: bool = False) -> sp.Expr:
        """O que está ligado na porta, ou a própria letra, que vira um campo de valor."""
        ligado = self.ligados.get(porta) if porta else None
        if ligado is not None:
            return ligado
        grandeza = self._numerada(grandeza, fixa)
        self.grandezas.setdefault(grandeza.chave, grandeza)
        self.proprias.append(grandeza.chave)
        return sp.S.Zero if grandeza.chave in self.zeros else grandeza.simbolo

    def padrao(self, grandeza: Grandeza, valor: float, origem: str) -> None:
        """Um valor que o bloco sugere, com a procedência dele."""
        grandeza = self._numerada(grandeza)
        self.grandezas.setdefault(grandeza.chave, grandeza)
        self.padroes[grandeza.chave] = valor
        self.origens[grandeza.chave] = origem

    def estado(self) -> Estado:
        estado = self.ligados.get("entrada")
        if estado is None:
            raise ErroDeBloco("Ligue uma seção aqui.")
        return estado

    def material(self) -> Material | None:
        return self.ligados.get("material")


@dataclass(frozen=True)
class Bloco:
    chave: str
    nome: str
    grupo: str
    dica: str
    formula: str  # para a face do bloco, sem LaTeX
    entradas: tuple[Porta, ...]
    saidas: tuple[Porta, ...]
    calcular: Callable[[Contexto], Mapping[str, Any]]
    opcoes: tuple[Opcao, ...] = ()
    numerar: bool = False  # o segundo bloco igual usa outra letra: M₂
    face: Callable[[Mapping[str, str]], str] | None = None  # a fórmula muda com a escolha
    dominio: str = SOLIDOS


_ENTRADA = Porta("entrada", "Seção", SECAO)
_SAIDA = Porta("saida", "Seção", SECAO)
_CONDICAO = Porta("condicao", "Condição", CONDICAO)
_ENTRADA_MATERIAL = Porta("material", "Material", MATERIAL)


def _secao(
    chave: str,
    nome: str,
    dica: str,
    formula: str,
    fabrica: Callable[[Contexto], Secao],
    opcoes: tuple[Opcao, ...] = (),
) -> Bloco:
    def calcular(c: Contexto) -> dict[str, Any]:
        secao = fabrica(c)
        for grandeza in secao.grandezas:
            c.grandezas.setdefault(grandeza.chave, grandeza)
            c.proprias.append(grandeza.chave)
        c.hipoteses.extend(secao.hipoteses)
        c.alertas.extend(secao.avisos)
        return {"saida": Estado.inicial(secao)}

    return Bloco(chave, nome, GRUPO_SECAO, dica, formula, (), (_SAIDA,), calcular, opcoes)


MOMENTO_DIRETO = "Valor do momento"
FORCA_BRACO = "Força × distância"
FORCA_COM_CORTANTE = "Força × distância, com a cortante da força"
_ENTRADA_DO_MOMENTO = Opcao(
    "entrada",
    "Como entra o momento",
    "Pelo valor, ou por força vezes distância, para achar a força ou a distância máxima. A força "
    "que tem braço também corta a seção: a terceira opção já soma essa cortante.",
    (MOMENTO_DIRETO, FORCA_BRACO, FORCA_COM_CORTANTE),
    MOMENTO_DIRETO,
)
_LADO = Opcao(
    "lado_maior",
    "Lado maior",
    "Na torção e na inércia fraca a fórmula depende de qual lado é o maior.",
    ms.LADOS,
    ms.LADO_H,
)
_DESENHO = Opcao(
    "desenho",
    "Seção desenhada",
    "A seção salva em Desenhar seção. A forma real entra na conta, com os furos.",
    lambda: ev.nomes_dos_desenhos(),
    ev.SEM_DESENHO,
)


def _retangular(c: Contexto) -> Secao:
    return ms.retangular(c.opcoes.get("lado_maior", ms.LADO_H))


def _desenhada(c: Contexto) -> Secao:
    nome = c.opcoes.get("desenho", ev.SEM_DESENHO)
    return ms.desenhada(nome)


def origem(
    chave: str,
    nome: str,
    dica: str,
    formula: str,
    entradas: Sequence[Grandeza],
    saidas: Mapping[str, tuple[str, str, Callable[..., sp.Expr]]],
    *,
    entram: Sequence[Grandeza] = (),
    numerar: bool = False,
    validar: Callable[..., Sequence[Validade]] | None = None,
) -> Bloco:
    """Um bloco só de fórmulas. ``saidas``: chave, rótulo, dimensão e a função das letras.

    As letras de ``entram`` também ganham bolinha de entrada: a força da viga pode vir da
    engrenagem. Com ``numerar``, só elas mudam no segundo bloco igual; vão e posição continuam as
    mesmas, porque os dois planos de um eixo têm o mesmo vão.
    """
    com_porta = {g_.chave for g_ in entram}

    def calcular(c: Contexto) -> dict[str, Any]:
        letras = [
            c.letra(g_, g_.chave if g_.chave in com_porta else None, fixa=g_.chave not in com_porta)
            for g_ in entradas
        ]
        if validar is not None:
            c.validades.extend(validar(*letras))
        return {k: funcao(*letras) for k, (_, _, funcao) in saidas.items()}

    portas_de_entrada = tuple(Porta(g_.chave, g_.texto, VALOR, g_.dimensao) for g_ in entram)
    portas = tuple(Porta(k, rotulo, VALOR, dim) for k, (rotulo, dim, _) in saidas.items())
    return Bloco(
        chave,
        nome,
        GRUPO_ORIGEM,
        dica,
        formula,
        portas_de_entrada,
        portas,
        calcular,
        numerar=numerar,
    )


def _esforco(
    chave: str,
    nome: str,
    dica: str,
    formula: str,
    letra: Grandeza,
    tipo: str,
    rotulo: str | None = None,
) -> Bloco:
    def calcular(c: Contexto) -> dict[str, Any]:
        return {"saida": c.estado().somar(tipo, c.letra(letra, "valor"))}

    return Bloco(
        chave,
        nome,
        GRUPO_ESFORCO,
        dica,
        formula,
        (_ENTRADA, Porta("valor", rotulo or letra.texto, VALOR, letra.dimensao)),
        (_SAIDA,),
        calcular,
        numerar=True,
    )


def _flexao(
    chave: str,
    eixo: str,
    momento: Grandeza,
    forca: Grandeza,
    distancia: Grandeza,
    tipo: str,
    tipo_cortante: str,
) -> Bloco:
    def calcular(c: Contexto) -> dict[str, Any]:
        estado = c.estado()
        entrada = c.opcoes.get("entrada", MOMENTO_DIRETO)
        if entrada == MOMENTO_DIRETO or c.ligados.get("valor") is not None:
            return {"saida": estado.somar(tipo, c.letra(momento, "valor"))}
        f = c.letra(forca)
        estado = estado.somar(tipo, f * c.letra(distancia))
        if entrada == FORCA_COM_CORTANTE:
            return {"saida": estado.somar(tipo_cortante, f)}
        return {"saida": estado.lembrar_forca(forca.texto)}

    def face(opcoes: Mapping[str, str]) -> str:
        entrada = opcoes.get("entrada", MOMENTO_DIRETO)
        if entrada == MOMENTO_DIRETO:
            return f"σ = {momento.texto}·c/I"
        extra = " · V = F" if entrada == FORCA_COM_CORTANTE else ""
        return f"M = {forca.texto}·{distancia.texto}{extra}"

    return Bloco(
        chave,
        f"Flexão em {eixo}",
        GRUPO_ESFORCO,
        f"Soma o momento em {eixo}. Entra pelo valor, ou por força vezes distância.",
        f"σ = {momento.texto}·c/I",
        (_ENTRADA, Porta("valor", "M", VALOR, g.MOMENTO)),
        (_SAIDA,),
        calcular,
        (_ENTRADA_DO_MOMENTO,),
        numerar=True,
        face=face,
    )


def _concentracao(c: Contexto) -> dict[str, Any]:
    return {"saida": c.estado().multiplicar(c.letra(g.KT), c.letra(g.KTS))}


def _pressao(c: Contexto) -> dict[str, Any]:
    estado = c.estado()
    if estado.secao.pressao is None:
        raise ErroDeBloco("A pressão interna só vale para tubo circular.")
    p = c.letra(g.P_INT)
    longitudinal, circunferencial = estado.secao.pressao
    fina = Validade(
        1 / circunferencial - sp.Rational(1, 10),
        "A parede não está fina: acima de t = d/20 as tensões da pressão pedem a fórmula de Lamé.",
        restringe=False,
    )
    c.hipoteses.append(
        "Pressão em parede fina, com o diâmetro externo: σ_c = p·d/(2·t) e σ_l = p·d/(4·t)."
    )
    return {"saida": estado.com_pressao(p * longitudinal, p * circunferencial).com_validade(fina)}


def _material(c: Contexto) -> dict[str, Any]:
    nome = c.opcoes.get("material", SEM_MATERIAL)
    if nome != SEM_MATERIAL:
        material = mc.obter(nome)
        fonte = f"Cadastro: {nome}"
        c.marcas.add(f"categoria:{material.categoria}")
        if material.sy_MPa > 0:
            c.padrao(g.SY, material.sy_MPa, fonte)
        else:
            c.marcas.add("fragil")
        c.padrao(g.SUT, material.sut_MPa, fonte)
        modulos = MODULOS_POR_CATEGORIA.get(material.categoria)
        if modulos is not None:
            e, cisalhamento, rotulo = modulos
            c.padrao(g.E, e, f"Valor típico de {rotulo}: confira")
            c.padrao(g.G, cisalhamento, f"Valor típico de {rotulo}: confira")
    saida = Material(c.letra(g.SY), c.letra(g.SUT), c.letra(g.E), c.letra(g.G))
    return {"saida": saida}


def _principal(t: ms.Tensao) -> sp.Expr:
    meio = (t.sx + t.sy) / 2
    return meio + sp.sqrt(((t.sx - t.sy) / 2) ** 2 + t.tau**2)


def _no_ponto(criterio: str, ponto: str) -> str:
    artigo = "no" if ponto.startswith(("canto", "centro", "meio")) else "na"
    return f"{criterio} {artigo} {ponto}"


def _nos_pontos(
    c: Contexto,
    criterio: str,
    letra: str,
    direita: sp.Expr,
    funcoes: Callable[[ms.Tensao], Sequence[sp.Expr]],
) -> dict[str, Any]:
    estado = c.estado()
    condicoes = []
    for t in estado.tensoes:
        if t.nula:
            continue
        tensoes = [("\\sigma_{x}", t.sx), ("\\tau", t.tau)]
        if t.sy != 0:
            tensoes.insert(1, ("\\sigma_{y}", t.sy))
        for esquerda in funcoes(t):
            condicoes.append(
                Condicao(
                    _no_ponto(criterio, t.ponto),
                    criterio,
                    esquerda,
                    direita,
                    letra,
                    t.ponto,
                    tuple(tensoes),
                    estado.validade,
                    t.sy == 0,
                )
            )
    if not condicoes:
        raise ErroDeBloco("Ponha ao menos um esforço antes deste bloco.")
    for forca in estado.forcas_sem_cortante:
        c.alertas.append(
            f"A força {forca} também corta a seção. Escolha a opção com a cortante da força, ou ligue "
            "um bloco de cortante, se ela não passa por esta seção."
        )
    return {"condicao": condicoes}


def _limite_de_escoamento(c: Contexto) -> sp.Expr:
    material = c.material()
    resistencia = material.sy if material else c.letra(g.SY)
    return resistencia / c.letra(g.FS)


def _von_mises(c: Contexto) -> dict[str, Any]:
    c.marcas.add("ductil")

    def funcao(t: ms.Tensao) -> Sequence[sp.Expr]:
        return (sp.sqrt(t.sx**2 - t.sx * t.sy + t.sy**2 + 3 * t.tau**2),)

    return _nos_pontos(c, "von Mises", "\\sigma_{eq}", _limite_de_escoamento(c), funcao)


def _tresca(c: Contexto) -> dict[str, Any]:
    c.marcas.add("ductil")

    def funcao(t: ms.Tensao) -> Sequence[sp.Expr]:
        # Com σ_y, as duas principais podem ter o mesmo sinal, e a terceira, zero, entra na diferença.
        diferenca = sp.sqrt((t.sx - t.sy) ** 2 + 4 * t.tau**2)
        return (diferenca,) if t.sy == 0 else (diferenca, _principal(t))

    return _nos_pontos(c, "Tresca", "\\sigma_{eq}", _limite_de_escoamento(c), funcao)


def _rankine(c: Contexto) -> dict[str, Any]:
    material = c.material()
    resistencia = material.sut if material else c.letra(g.SUT)
    limite = resistencia / c.letra(g.FS)
    c.hipoteses.append("Maior tensão principal: critério de material frágil, em tração.")
    return _nos_pontos(c, "Maior principal", "\\sigma_{1}", limite, lambda t: (_principal(t),))


def _criterio_de_fadiga(
    criterio: str, sa: sp.Expr, sm: sp.Expr, se: sp.Expr, c: Contexto
) -> tuple[sp.Expr, sp.Expr, str]:
    """Os dois lados do critério, e o lado esquerdo em LaTeX. S_e pode ser S_f, na vida finita."""
    material = c.material()
    n = c.letra(g.FS)
    if criterio in (SODERBERG, ELIPTICO):
        escoamento = material.sy if material else c.letra(g.SY)
        if criterio == SODERBERG:
            return (
                sa / se + sm / escoamento,
                1 / n,
                "\\frac{\\sigma_{a}'}{S_{e}} + \\frac{\\sigma_{m}'}{S_{y}}",
            )
        return (
            (n * sa / se) ** 2 + (n * sm / escoamento) ** 2,
            sp.S.One,
            "\\left(\\frac{n \\sigma_{a}'}{S_{e}}\\right)^{2} + "
            "\\left(\\frac{n \\sigma_{m}'}{S_{y}}\\right)^{2}",
        )
    ruptura = material.sut if material else c.letra(g.SUT)
    if criterio == GERBER:
        return (
            n * sa / se + (n * sm / ruptura) ** 2,
            sp.S.One,
            "\\frac{n \\sigma_{a}'}{S_{e}} + \\left(\\frac{n \\sigma_{m}'}{S_{ut}}\\right)^{2}",
        )
    return (
        sa / se + sm / ruptura,
        1 / n,
        "\\frac{\\sigma_{a}'}{S_{e}} + \\frac{\\sigma_{m}'}{S_{ut}}",
    )


def _goodman(c: Contexto) -> dict[str, Any]:
    estado = c.estado()
    fibra = estado.secao.pontos[0]
    kf, kfs = c.letra(g.KF, "kf"), c.letra(g.KFS, "kfs")
    if c.opcoes.get("esforcos", INFORMAR_FADIGA) == EIXO_GIRANDO:
        if not estado.secao.redonda:
            raise ErroDeBloco("Eixo girando vale para seção redonda.")
        if estado.mx == 0 and estado.my == 0 and estado.t == 0:
            raise ErroDeBloco("Ponha flexão ou torção antes deste bloco.")
        ma, mm = sp.sqrt(estado.mx**2 + estado.my**2), sp.S.Zero
        ta, tm = sp.S.Zero, estado.t
        c.hipoteses.append(
            "Eixo girando: a flexão alterna por inteiro a cada volta, e o torque fica constante."
        )
    else:
        ma, mm = c.letra(g.MA), c.letra(g.MM)
        ta, tm = c.letra(g.TA), c.letra(g.TM)

    def equivalente(momento: sp.Expr, torque: sp.Expr) -> sp.Expr:
        sigma = kf * momento * fibra.por_momento
        tau = kfs * torque * fibra.por_torque
        return sp.sqrt(sigma**2 + 3 * tau**2)

    alternada, media = equivalente(ma, ta), equivalente(mm, tm)
    material = c.material()
    criterio = c.opcoes.get("criterio", GOODMAN)
    resistencia = c.letra(g.SE, "se")
    validade = estado.validade
    if c.opcoes.get("vida", VIDA_INFINITA) == VIDA_FINITA:
        ruptura = material.sut if material else c.letra(g.SUT)
        ciclos = c.letra(g.N_CICLOS)
        resistencia = ResistenciaEmVida(sp.Rational(9, 10) * ruptura, resistencia, ciclos)
        validade = (
            *validade,
            Validade(
                1e6 - ciclos,
                "Acima de 10⁶ ciclos o aço entra na vida infinita: vale S_e, e a reta usada aqui "
                "fica a favor da segurança.",
                restringe=False,
            ),
        )
        c.hipoteses.append(
            "Vida finita: S_f na reta log-log entre 0,9·S_ut em 10³ ciclos e S_e em 10⁶ ciclos."
        )
    esquerda, direita, letra = _criterio_de_fadiga(criterio, alternada, media, resistencia, c)
    c.hipoteses.append(
        f"Fadiga para pré-dimensionamento: {criterio} com von Mises nas parcelas alternada e média."
    )
    curto = criterio.removeprefix("DE-").removeprefix("ASME ")
    condicoes = [
        Condicao(
            f"Fadiga ({curto}) na fibra externa",
            curto.capitalize(),
            esquerda,
            direita,
            letra,
            "fibra externa",
            (("\\sigma_{a}'", alternada), ("\\sigma_{m}'", media)),
            validade,
        )
    ]
    if material is not None and "fragil" not in c.marcas:
        maxima = equivalente(ma + mm, ta + tm)
        condicoes.append(
            Condicao(
                "Escoamento no primeiro ciclo",
                "Escoamento",
                maxima,
                material.sy / c.letra(g.FS),
                "\\sigma_{max}'",
                "fibra externa",
                (("\\sigma_{max}'", maxima),),
                estado.validade,
            )
        )
    else:
        c.hipoteses.append(
            "Sem o material ligado, o escoamento no primeiro ciclo não é conferido: ligue o bloco "
            "Material, ou um critério de escoamento."
        )
    return {"condicao": condicoes}


def _flecha(c: Contexto) -> dict[str, Any]:
    estado = c.estado()
    produto = c.ligados.get("flecha")
    if produto is None:
        raise ErroDeBloco("Ligue aqui a saída δ·EI de um bloco de viga.")
    if c.opcoes.get("limite", FLECHA_RELATIVA) == FLECHA_RELATIVA:
        limite = c.letra(g.L) / c.letra(g.RELACAO_FLECHA)
    else:
        limite = c.letra(g.DELTA_ADM)
    secao = estado.secao
    inercia = secao.inercia_y if c.opcoes.get("eixo") == ms.EIXO_YY else secao.inercia
    material = c.material()
    esquerda = produto / ((material.e if material else c.letra(g.E)) * inercia)
    return {
        "condicao": [
            Condicao("Flecha", "Flecha", esquerda, limite, "\\delta", "", (), estado.validade)
        ]
    }


def _flambagem(c: Contexto) -> dict[str, Any]:
    estado = c.estado().usando_o_lado()
    secao = estado.secao
    area_sobre_i = secao.area / secao.inercia_min
    forca = c.letra(g.N, "valor")
    material = c.material()
    e = material.e if material else c.letra(g.E)
    l_, k = c.letra(g.L), c.letra(g.K_FLAMB)
    critica = sp.pi**2 * e * secao.inercia_min / (k * l_) ** 2
    esquerda = c.letra(g.FS) * forca
    validade = list(estado.validade)
    if material is not None:
        validade.append(
            Validade(
                (k * l_) ** 2 * area_sobre_i - 2 * sp.pi**2 * e / material.sy,
                "A coluna ficou curta: abaixo da esbeltez de transição, Euler passa da carga real. "
                "Use a fórmula de Johnson ou a Flambagem de colunas.",
            )
        )
    else:
        c.hipoteses.append("Euler só vale para coluna esbelta. Ligue o material para conferir.")
    condicao = Condicao(
        "Flambagem de Euler",
        "Flambagem",
        esquerda,
        critica,
        "n \\cdot N",
        "",
        (("P_{cr}", critica),),
        tuple(validade),
    )
    return {"condicao": [condicao]}


def _giro(c: Contexto) -> dict[str, Any]:
    estado = c.estado().usando_o_lado()
    material = c.material()
    modulo = material.g if material else c.letra(g.G)
    esquerda = c.letra(g.T, "valor") * c.letra(g.L) / (modulo * estado.secao.polar)
    condicao = Condicao(
        "Giro por torção",
        "Giro",
        esquerda,
        c.letra(g.PHI_ADM),
        "\\varphi",
        "",
        (),
        estado.validade,
    )
    return {"condicao": [condicao]}


def _limite_fadiga(c: Contexto) -> dict[str, Any]:
    material = c.material()
    sut = material.sut if material else c.letra(g.SUT)
    categoria = next(
        (m.split(":", 1)[1] for m in c.marcas if m.startswith("categoria:")),
        MATERIAIS_DE_FADIGA[0],
    )
    if categoria not in MATERIAIS_DE_FADIGA:
        categoria = MATERIAIS_DE_FADIGA[0]
    if categoria in ("aluminio", "cobre"):
        c.alertas.append(
            "Alumínio e cobre não têm limite de fadiga de verdade: S_e' vale para 5·10⁸ ciclos."
        )
    a, b = ft.COEFICIENTES_SUPERFICIE[ee.ACABAMENTOS[c.opcoes.get("acabamento", ACABAMENTO_PADRAO)]]
    ka = sp.S.One if categoria == "ferro_fundido" else FatorSuperficie(sut, a, b)
    if c.opcoes.get("tamanho", TAMANHO_PELO_D) == TAMANHO_PELO_D:
        kb = FatorTamanho(c.letra(g.D))
    else:
        kb = c.letra(g.K_TAMANHO)
    kc = sp.Float(CARREGAMENTOS[c.opcoes.get("carregamento", next(iter(CARREGAMENTOS)))])
    confianca = c.opcoes.get("confiabilidade", CONFIABILIDADE_PADRAO)
    c.padrao(
        g.K_CONFIANCA,
        ft.fator_confiabilidade(ee.CONFIABILIDADES[confianca]),
        f"Tabela: confiabilidade de {confianca}",
    )
    c.hipoteses.append(
        "S_e pelos fatores de Marin de Shigley, os mesmos do Assistente de cargas. O k_b pelo "
        "diâmetro vale para eixo girando, de 2,79 a 254 mm."
    )
    base = LimiteBase(sut, MATERIAIS_DE_FADIGA.index(categoria))
    se = (
        base
        * ka
        * kb
        * kc
        * c.letra(g.K_TEMPERATURA)
        * c.letra(g.K_CONFIANCA)
        * c.letra(g.K_DIVERSOS)
    )
    return {"se": se}


def _entalhe(c: Contexto) -> dict[str, Any]:
    tipo = c.opcoes.get("entalhe", ee.ENTALHE_LISO)
    if tipo == ee.ENTALHE_LISO:
        return {"kf": sp.S.One, "kfs": sp.S.One}
    material = c.material()
    sut = material.sut if material else c.letra(g.SUT)
    kt: sp.Expr
    kts: sp.Expr
    if tipo == ee.ENTALHE_RESSALTO:
        d, maior, raio = c.letra(g.D), c.letra(g.D_MAIOR), c.letra(g.R_ENTALHE)
        kt, kts = KtRessalto(maior, d, raio, 0), KtRessalto(maior, d, raio, 1)
        q, qs = SensibilidadeNeuber(sut, raio, 0), SensibilidadeNeuber(sut, raio, 1)
        c.hipoteses.append(
            "K_t pelas curvas de Peterson (Norton, apêndice E) e q de Neuber (Shigley, eq. 6-35)."
        )
    elif tipo == ee.ENTALHE_MANUAL:
        kt, kts = c.letra(g.KT), c.letra(g.KTS)
        q, qs = c.letra(g.Q_NORMAL), c.letra(g.Q_CORTE)
    else:
        na_flexao, na_torcao, _ = ee.KT_FIXOS[tipo]
        kt, kts = sp.Float(na_flexao), sp.Float(na_torcao)
        if tipo == ee.ENTALHE_CHAVETA:
            raio = sp.Rational(1, 50) * c.letra(g.D)
            q, qs = SensibilidadeNeuber(sut, raio, 0), SensibilidadeNeuber(sut, raio, 1)
        else:
            q, qs = sp.S.One, sp.S.One  # lado seguro: sem raio definido, não há sensibilidade
    return {"kf": 1 + q * (kt - 1), "kfs": 1 + qs * (kts - 1)}


def _formula(c: Contexto) -> dict[str, Any]:
    texto = c.opcoes.get("texto", "").strip()
    if not texto:
        raise ErroDeBloco("Digite a fórmula no inspetor.")
    try:
        formula = mf.ler(texto)
    except mf.ErroDeFormula as erro:
        raise ErroDeBloco(str(erro)) from erro
    sistema = c.opcoes.get("sistema", g.SISTEMA_SOLIDOS.chave)
    dimensoes = mf.dimensoes_das_letras(c.opcoes.get("dimensoes"))
    trocas = {
        sp.Symbol(letra, positive=True): c.letra(
            mf.grandeza_da_letra(letra, sistema, dimensoes), letra
        )
        for letra in formula.letras
    }
    c.alertas.extend(mf.problemas_de_unidade(formula, sistema, dimensoes))
    direita = formula.direita.subs(trocas)
    saida: dict[str, Any] = {}
    if formula.tem_valor:
        saida["saida"] = direita
    if formula.esquerda is None:
        return saida
    if formula.nome:
        dimensao = mf.dimensao_da_saida(formula, sistema, dimensoes, c.opcoes.get("saida"))
        grandeza = mf.grandeza_da_letra(
            formula.nome, sistema, {**dimensoes, formula.nome: dimensao}
        )
        esquerda = direita
        limite = c.letra(grandeza)
    else:
        esquerda = formula.esquerda.subs(trocas)
        limite = direita
        if formula.sinal == mf.MAIOR_IGUAL:
            esquerda, limite = limite, esquerda
    nome = f"Fórmula {texto}" if len(texto) <= 40 else f"Fórmula {texto[:37]}..."
    saida["condicao"] = [
        Condicao(
            nome,
            "Fórmula própria",
            esquerda,
            limite,
            sp.latex(esquerda),
            igualdade=formula.sinal == mf.IGUAL,
        )
    ]
    return saida


def _resultado(c: Contexto) -> dict[str, Any]:
    return {}


def _referencia(c: Contexto) -> dict[str, Any]:
    valor = c.opcoes.get("valor")
    if valor in (None, ""):
        raise ErroDeBloco("Escolha o cálculo registrado.")
    return {"saida": sp.Float(float(valor))}


def _carga_fora_do_meio(f: sp.Expr, a: sp.Expr, l_: sp.Expr) -> list[Validade]:
    return [
        Validade(
            l_ / 2 - a,
            "Na viga com a carga fora do meio, a_m é a distância até o apoio mais perto da carga: "
            "precisa ficar até L/2. Se a carga está mais perto do outro apoio, meça a partir dele.",
            restringe=False,
        )
    ]


def _reacoes(
    f1: sp.Expr, f2: sp.Expr, a1: sp.Expr, a2: sp.Expr, l_: sp.Expr
) -> tuple[sp.Expr, sp.Expr]:
    return (f1 * (l_ - a1) + f2 * (l_ - a2)) / l_, (f1 * a1 + f2 * a2) / l_


def _giro_no_apoio(f: sp.Expr, a: sp.Expr, l_: sp.Expr) -> sp.Expr:
    """θ·EI no apoio a uma distância a da força: P·a·b·(L + b)/(6L), com b = L − a."""
    b = l_ - a
    return f * a * b * (l_ + b) / (6 * l_)


SOB_F1 = "Sob a força F_1"
SOB_F2 = "Sob a força F_2"
_ONDE_NA_VIGA = Opcao(
    "secao",
    "Seção conferida",
    "O momento e a cortante que saem são os da seção sob a força escolhida. Confira as duas, uma "
    "de cada vez, ou ponha dois blocos.",
    (SOB_F1, SOB_F2),
    SOB_F1,
)


def _calcular_duas_cargas(c: Contexto) -> dict[str, Any]:
    f1 = c.letra(g.F_1, g.F_1.chave)
    f2 = c.letra(g.F_2, g.F_2.chave)
    a1, a2, l_ = c.letra(g.A_1), c.letra(g.A_2), c.letra(g.L)
    c.validades.extend(
        (
            Validade(a2 - a1, "A primeira força precisa ficar antes da segunda: a_1 ≤ a_2.", False),
            Validade(l_ - a2, "As duas forças precisam ficar dentro do vão: a_2 ≤ L.", False),
        )
    )
    ra, rb = _reacoes(f1, f2, a1, a2, l_)
    if c.opcoes.get("secao", SOB_F1) == SOB_F2:
        momento, cortante = rb * (l_ - a2), rb
    else:
        momento, cortante = ra * a1, ra
    c.hipoteses.append(
        "Viga com duas forças no mesmo sentido: o maior momento fica sob uma delas, e a cortante "
        "que sai é a do trecho entre o apoio e a força escolhida."
    )
    return {
        "M": momento,
        "V": cortante,
        "R_A": ra,
        "R_B": rb,
        "giro": _giro_no_apoio(f1, a1, l_) + _giro_no_apoio(f2, a2, l_),
        "giro_b": _giro_no_apoio(f1, l_ - a1, l_) + _giro_no_apoio(f2, l_ - a2, l_),
    }


_VIGAS_NOVAS: tuple[Bloco, ...] = (
    origem(
        "biapoiada_fora",
        "Biapoiada: carga fora do meio",
        "Uma força a uma distância a_m do apoio mais perto. É o eixo com a engrenagem fora do meio.",
        "M = F·a·(L − a)/L",
        (g.F, g.A_CARGA, g.L),
        {
            "M": ("M", g.MOMENTO, lambda f, a, l_: f * a * (l_ - a) / l_),
            "V": ("V", g.FORCA, lambda f, a, l_: f * (l_ - a) / l_),
            "flecha": (
                "δ·EI",
                g.FLECHA_EI,
                lambda f, a, l_: (
                    f * a * (l_**2 - a**2) ** sp.Rational(3, 2) / (9 * sp.sqrt(3) * l_)
                ),
            ),
            "R": ("R", g.FORCA, lambda f, a, l_: f * (l_ - a) / l_),
            "giro": ("θ·EI", g.GIRO_EI, _giro_no_apoio),
            "giro_carga": (
                "θ·EI na carga",
                g.GIRO_EI,
                lambda f, a, l_: f * a * (l_ - a) * (l_ - 2 * a) / (3 * l_),
            ),
        },
        entram=(g.F,),
        numerar=True,
        validar=_carga_fora_do_meio,
    ),
    Bloco(
        "biapoiada_duas",
        "Biapoiada: duas cargas",
        GRUPO_ORIGEM,
        "Duas forças no mesmo sentido, como duas engrenagens no mesmo eixo. Posições a partir do "
        "apoio A.",
        "R_A = Σ F·(L − a)/L",
        (
            Porta(g.F_1.chave, g.F_1.texto, VALOR, g.FORCA),
            Porta(g.F_2.chave, g.F_2.texto, VALOR, g.FORCA),
        ),
        (
            Porta("M", "M", VALOR, g.MOMENTO),
            Porta("V", "V", VALOR, g.FORCA),
            Porta("R_A", "R_A", VALOR, g.FORCA),
            Porta("R_B", "R_B", VALOR, g.FORCA),
            Porta("giro", "θ·EI em A", VALOR, g.GIRO_EI),
            Porta("giro_b", "θ·EI em B", VALOR, g.GIRO_EI),
        ),
        _calcular_duas_cargas,
        (_ONDE_NA_VIGA,),
        face=lambda opcoes: (
            "M = R_B·(L − a_2)" if opcoes.get("secao", SOB_F1) == SOB_F2 else "M = R_A·a_1"
        ),
    ),
    origem(
        "biapoiada_balanco",
        "Biapoiada com balanço",
        "Eixo em dois mancais com a engrenagem ou a polia do lado de fora, a c_b do mancal.",
        "M = F·c · R = F·(L + c)/L",
        (g.F, g.C_BALANCO, g.L),
        {
            "M": ("M", g.MOMENTO, lambda f, c_, l_: f * c_),
            "V": ("V", g.FORCA, lambda f, c_, l_: f),
            "flecha": ("δ·EI", g.FLECHA_EI, lambda f, c_, l_: f * c_**2 * (l_ + c_) / 3),
            "R": ("R", g.FORCA, lambda f, c_, l_: f * (l_ + c_) / l_),
            "giro": ("θ·EI", g.GIRO_EI, lambda f, c_, l_: f * c_ * l_ / 3),
            "giro_carga": (
                "θ·EI na carga",
                g.GIRO_EI,
                lambda f, c_, l_: f * c_ * (2 * l_ + 3 * c_) / 6,
            ),
        },
        entram=(g.F,),
        numerar=True,
    ),
    origem(
        "engastada_apoiada_meio",
        "Engastada e apoiada: carga no meio",
        "Uma ponta presa e a outra apoiada, com a força no meio do vão.",
        "M = 3·F·L/16 · R = 11·F/16",
        (g.F, g.L),
        {
            "M": ("M", g.MOMENTO, lambda f, l_: 3 * f * l_ / 16),
            "V": ("V", g.FORCA, lambda f, l_: 11 * f / 16),
            "flecha": ("δ·EI", g.FLECHA_EI, lambda f, l_: f * l_**3 / (48 * sp.sqrt(5))),
            "R": ("R", g.FORCA, lambda f, l_: 11 * f / 16),
            "giro": ("θ·EI", g.GIRO_EI, lambda f, l_: f * l_**2 / 32),
        },
        entram=(g.F,),
    ),
    origem(
        "engastada_apoiada_distribuida",
        "Engastada e apoiada: distribuída",
        "Uma ponta presa e a outra apoiada, com carga uniforme.",
        "M = q·L²/8 · R = 5·q·L/8",
        (g.Q, g.L),
        {
            "M": ("M", g.MOMENTO, lambda q, l_: q * l_**2 / 8),
            "V": ("V", g.FORCA, lambda q, l_: 5 * q * l_ / 8),
            "flecha": (
                "δ·EI",
                g.FLECHA_EI,
                lambda q, l_: (39 + 55 * sp.sqrt(33)) / 65536 * q * l_**4,
            ),
            "R": ("R", g.FORCA, lambda q, l_: 5 * q * l_ / 8),
            "giro": ("θ·EI", g.GIRO_EI, lambda q, l_: q * l_**3 / 48),
        },
        entram=(g.Q,),
    ),
)


_BLOCO_DA_FORMULA = Bloco(
    FORMULA,
    "Fórmula própria",
    GRUPO_OUTROS,
    "Digite a sua fórmula no inspetor: as letras viram bolinhas, e as unidades são conferidas.",
    "M = q*L^2/8",
    (),
    (),
    _formula,
    dominio=COMUM,
)

BLOCOS: tuple[Bloco, ...] = (
    _BLOCO_DA_FORMULA,
    _secao(
        "circular",
        "Circular maciça",
        "Eixos, pinos e barras redondas.",
        "π·d²/4 · π·d⁴/64",
        lambda c: ms.circular(),
    ),
    _secao(
        "tubo_parede",
        "Tubo: d e parede",
        "Tubo com diâmetro externo e espessura.",
        "d_i = d − 2·t",
        lambda c: ms.tubo_por_parede(),
    ),
    _secao(
        "tubo_relacao",
        "Tubo: d e k",
        "Tubo com relação fixa entre os diâmetros. Isola d em forma fechada.",
        "d_i = k·d",
        lambda c: ms.tubo_por_relacao(),
    ),
    _secao(
        "retangular",
        "Retangular",
        "Base, altura e flexão em torno do eixo da base.",
        "b·h²/6",
        _retangular,
        (_LADO,),
    ),
    _secao(
        "perfil_i",
        "Perfil I",
        "Perfil simétrico: confere a fibra, a junção alma-mesa e a linha neutra.",
        "b_f · h · t_f · t_w",
        lambda c: ms.perfil_i(),
    ),
    _secao(
        "desenhada",
        "Seção desenhada",
        "A seção salva em Desenhar seção. Vira números, e o que varia é a escala s do desenho.",
        "A·s² · I·s⁴",
        _desenhada,
        (_DESENHO,),
    ),
    origem(
        "biapoiada_central",
        "Biapoiada: carga no meio",
        "Viga em dois apoios com uma força no meio do vão.",
        "M = F·L/4 · V = F/2",
        (g.F, g.L),
        {
            "M": ("M", g.MOMENTO, lambda f, l_: f * l_ / 4),
            "V": ("V", g.FORCA, lambda f, l_: f / 2),
            "flecha": ("δ·EI", g.FLECHA_EI, lambda f, l_: f * l_**3 / 48),
            "R": ("R", g.FORCA, lambda f, l_: f / 2),
            "giro": ("θ·EI", g.GIRO_EI, lambda f, l_: f * l_**2 / 16),
        },
        entram=(g.F,),
    ),
    origem(
        "biapoiada_distribuida",
        "Biapoiada: distribuída",
        "Viga em dois apoios com carga uniforme.",
        "M = q·L²/8 · V = q·L/2",
        (g.Q, g.L),
        {
            "M": ("M", g.MOMENTO, lambda q, l_: q * l_**2 / 8),
            "V": ("V", g.FORCA, lambda q, l_: q * l_ / 2),
            "flecha": ("δ·EI", g.FLECHA_EI, lambda q, l_: 5 * q * l_**4 / 384),
            "R": ("R", g.FORCA, lambda q, l_: q * l_ / 2),
            "giro": ("θ·EI", g.GIRO_EI, lambda q, l_: q * l_**3 / 24),
        },
        entram=(g.Q,),
    ),
    origem(
        "balanco_ponta",
        "Balanço: carga na ponta",
        "Viga engastada com uma força na ponta livre.",
        "M = F·L · V = F",
        (g.F, g.L),
        {
            "M": ("M", g.MOMENTO, lambda f, l_: f * l_),
            "V": ("V", g.FORCA, lambda f, l_: f),
            "flecha": ("δ·EI", g.FLECHA_EI, lambda f, l_: f * l_**3 / 3),
            "R": ("R", g.FORCA, lambda f, l_: f),
            "giro": ("θ·EI", g.GIRO_EI, lambda f, l_: f * l_**2 / 2),
        },
        entram=(g.F,),
    ),
    origem(
        "balanco_distribuida",
        "Balanço: distribuída",
        "Viga engastada com carga uniforme.",
        "M = q·L²/2 · V = q·L",
        (g.Q, g.L),
        {
            "M": ("M", g.MOMENTO, lambda q, l_: q * l_**2 / 2),
            "V": ("V", g.FORCA, lambda q, l_: q * l_),
            "flecha": ("δ·EI", g.FLECHA_EI, lambda q, l_: q * l_**4 / 8),
            "R": ("R", g.FORCA, lambda q, l_: q * l_),
            "giro": ("θ·EI", g.GIRO_EI, lambda q, l_: q * l_**3 / 6),
        },
        entram=(g.Q,),
    ),
    *_VIGAS_NOVAS,
    origem(
        "potencia",
        "Potência e rotação",
        "Torque de um eixo que transmite potência.",
        "T = 30·P/(π·n)",
        (g.POT, g.ROT),
        {"T": ("T", g.MOMENTO, lambda p, n: 30 * p / (sp.pi * n))},
    ),
    _flexao("flexao", ms.EIXO_XX, g.M, g.F_XX, g.D_XX, "Mx", "Vy"),
    _flexao("flexao_y", ms.EIXO_YY, g.MY, g.F_YY, g.D_YY, "My", "Vx"),
    _esforco("normal", "Força normal", "Soma σ = N/A, tração ou compressão.", "σ = N/A", g.N, "N"),
    _esforco(
        "cortante",
        "Cortante vertical",
        "Soma τ = V·Q/(I·b): zero na fibra de XX e máximo na linha neutra.",
        "τ = V_y·Q/(I·b)",
        g.V,
        "Vy",
        "V",
    ),
    _esforco(
        "cortante_x",
        "Cortante horizontal",
        "A cortante no plano de b, que vem junto com o momento em YY.",
        "τ = V_x·Q/(I·h)",
        g.VX,
        "Vx",
        "V",
    ),
    _esforco("torcao", "Torção", "Soma τ da torção em cada ponto da seção.", "τ = T·r/J", g.T, "T"),
    Bloco(
        "pressao_interna",
        "Pressão interna",
        GRUPO_ESFORCO,
        "Tensões de parede fina em tubo: dá o estado biaxial.",
        "σ_c = p·d/(2·t)",
        (_ENTRADA,),
        (_SAIDA,),
        _pressao,
    ),
    Bloco(
        "concentracao",
        "Concentração de tensão",
        GRUPO_ESFORCO,
        "Multiplica as tensões somadas até aqui por K_t e K_ts: furo, rasgo ou mudança de diâmetro.",
        "σ·K_t · τ·K_ts",
        (_ENTRADA,),
        (_SAIDA,),
        _concentracao,
    ),
    Bloco(
        "material",
        "Material",
        GRUPO_MATERIAL,
        "Traz S_y, S_ut, E e G de uma vez. As letras ficam na fórmula, com o valor nos campos.",
        "S_y · S_ut · E · G",
        (),
        (Porta("saida", "Material", MATERIAL),),
        _material,
        (
            Opcao(
                "material",
                "Material",
                "Vem do cadastro de materiais. Sem escolher, as propriedades ficam em letra.",
                lambda: (SEM_MATERIAL, *mc.listar_nomes()),
                SEM_MATERIAL,
            ),
        ),
        numerar=True,
    ),
    Bloco(
        "von_mises",
        "von Mises",
        GRUPO_CRITERIO,
        "Material dúctil: junta σ e τ de cada ponto na tensão equivalente.",
        "√(σ² + 3·τ²) ≤ S_y/n",
        (_ENTRADA, _ENTRADA_MATERIAL),
        (_CONDICAO,),
        _von_mises,
    ),
    Bloco(
        "tresca",
        "Tresca",
        GRUPO_CRITERIO,
        "Material dúctil, mais conservador que von Mises.",
        "√(σ² + 4·τ²) ≤ S_y/n",
        (_ENTRADA, _ENTRADA_MATERIAL),
        (_CONDICAO,),
        _tresca,
    ),
    Bloco(
        "rankine",
        "Maior principal",
        GRUPO_CRITERIO,
        "Material frágil, como ferro fundido cinzento.",
        "σ₁ ≤ S_ut/n",
        (_ENTRADA, _ENTRADA_MATERIAL),
        (_CONDICAO,),
        _rankine,
    ),
    Bloco(
        "goodman",
        "Fadiga de eixo",
        GRUPO_CRITERIO,
        "Goodman, Gerber, Soderberg ou ASME elíptico. Usa os esforços da fila, ou os informados.",
        "σ_a'/S_e + σ_m'/S_ut ≤ 1/n",
        (
            _ENTRADA,
            _ENTRADA_MATERIAL,
            Porta("se", "S_e", VALOR, g.TENSAO),
            Porta("kf", "K_f", VALOR, g.PURO),
            Porta("kfs", "K_fs", VALOR, g.PURO),
        ),
        (_CONDICAO,),
        _goodman,
        (
            Opcao(
                "criterio",
                "Critério de fadiga",
                "Goodman é o usual e fica a favor da segurança. Gerber segue melhor os ensaios. "
                "Soderberg e ASME elíptico usam S_y no lugar de S_ut.",
                CRITERIOS_DE_FADIGA,
                GOODMAN,
            ),
            Opcao(
                "vida",
                "Vida",
                "Vida infinita usa S_e. Vida finita troca S_e por S_f em N_c ciclos.",
                VIDAS,
                VIDA_INFINITA,
            ),
            Opcao(
                "esforcos",
                "De onde vêm os esforços",
                "No eixo girando, a flexão da fila vira alternada e o torque fica constante, sem "
                "repetir valores. Para outros ciclos, informe as quatro parcelas.",
                ESFORCOS_DA_FADIGA,
                INFORMAR_FADIGA,
            ),
        ),
        face=lambda opcoes: _FORMULA_DA_FADIGA[opcoes.get("criterio", GOODMAN)],
    ),
    Bloco(
        "limite_fadiga",
        "Limite de fadiga",
        GRUPO_MATERIAL,
        "S_e pelos fatores de Marin. Com d em aberto, k_b acompanha a resposta sozinho.",
        "S_e = k_a·k_b·k_c·k_d·k_e·S_e'",
        (_ENTRADA_MATERIAL,),
        (Porta("se", "S_e", VALOR, g.TENSAO),),
        _limite_fadiga,
        (
            Opcao(
                "acabamento",
                "Acabamento",
                "Superfície mais grossa rende menos em fadiga. Dá o k_a.",
                tuple(ee.ACABAMENTOS),
                ACABAMENTO_PADRAO,
            ),
            Opcao(
                "tamanho",
                "Fator de tamanho",
                "Pelo diâmetro vale para eixo girando. Em outra forma, informe k_b.",
                TAMANHOS,
                TAMANHO_PELO_D,
            ),
            Opcao(
                "carregamento",
                "Carregamento",
                "Com o bloco de fadiga vale Flexão ou combinado, que já traz von Mises.",
                tuple(CARREGAMENTOS),
                next(iter(CARREGAMENTOS)),
            ),
            Opcao(
                "confiabilidade",
                "Confiabilidade",
                "Dá o k_e. 50 % é o valor médio do ensaio; projeto costuma pedir de 90 a 99 %.",
                tuple(ee.CONFIABILIDADES),
                CONFIABILIDADE_PADRAO,
            ),
        ),
    ),
    Bloco(
        "entalhe",
        "Entalhe",
        GRUPO_MATERIAL,
        "K_f e K_fs do ressalto, da chaveta, do canal de anel, do furo ou do cubo prensado.",
        "K_f = 1 + q·(K_t − 1)",
        (_ENTRADA_MATERIAL,),
        (Porta("kf", "K_f", VALOR, g.PURO), Porta("kfs", "K_fs", VALOR, g.PURO)),
        _entalhe,
        (
            Opcao(
                "entalhe",
                "Tipo de entalhe",
                "Os mesmos do Assistente de cargas. Sem raio definido, q fica em 1, a favor.",
                ee.ENTALHES,
                ee.ENTALHE_LISO,
            ),
        ),
    ),
    Bloco(
        "flecha",
        "Flecha",
        GRUPO_CRITERIO,
        "Liga a seção e a saída δ·EI de um bloco de viga.",
        "δ = (δ·EI)/(E·I)",
        (_ENTRADA, Porta("flecha", "δ·EI", VALOR, g.FLECHA_EI), _ENTRADA_MATERIAL),
        (_CONDICAO,),
        _flecha,
        (
            Opcao(
                "limite",
                "Limite da flecha",
                "Relação L/δ, como L/300, ou a flecha admissível em milímetros.",
                FLECHAS,
                FLECHA_RELATIVA,
            ),
            Opcao(
                "eixo",
                "Eixo da flexão",
                "XX flete no plano de h, e YY no plano de b. A inércia da flecha vem daí.",
                ms.EIXOS,
                ms.EIXO_XX,
            ),
        ),
    ),
    Bloco(
        "flambagem",
        "Flambagem de Euler",
        GRUPO_CRITERIO,
        "Coluna esbelta em compressão, na inércia mais fraca da seção.",
        "n·N ≤ π²·E·I/(K·L)²",
        (_ENTRADA, Porta("valor", "N", VALOR, g.FORCA), _ENTRADA_MATERIAL),
        (_CONDICAO,),
        _flambagem,
    ),
    Bloco(
        "giro",
        "Giro por torção",
        GRUPO_CRITERIO,
        "Rigidez do eixo: o quanto ele torce no trecho.",
        "φ = T·L/(G·J)",
        (_ENTRADA, Porta("valor", "T", VALOR, g.MOMENTO), _ENTRADA_MATERIAL),
        (_CONDICAO,),
        _giro,
    ),
    Bloco(
        RESULTADO,
        "Em função de",
        GRUPO_RESULTADO,
        "Junta as condições e isola a grandeza que você escolher.",
        "x = ?",
        (Porta("condicoes", "Condições", CONDICAO, varias=True),),
        (),
        _resultado,
        dominio=COMUM,
    ),
    Bloco(
        REFERENCIA,
        "Cálculo registrado",
        GRUPO_OUTROS,
        "Traz um resultado de outro cálculo do projeto, com identidade e revisão: se ele mudar, a "
        "página avisa.",
        "registro · resultado",
        (),
        (Porta("saida", "Valor", VALOR, "livre"),),
        _referencia,
        dominio=COMUM,
    ),
)

POR_CHAVE: dict[str, Bloco] = {b.chave: b for b in BLOCOS}
#: Blocos cujas bolinhas dependem do que foi escolhido neles, como o eixo com trechos.
PORTAS_VARIAVEIS: dict[
    str, Callable[[Mapping[str, Any]], tuple[tuple[Porta, ...], tuple[Porta, ...]]]
] = {}


@lru_cache(maxsize=256)
def _portas_da_formula(
    texto: str, dimensoes: str, escolhida: str, sistema: str
) -> tuple[tuple[Porta, ...], tuple[Porta, ...]]:
    """As bolinhas nascem das letras do texto. Com erro na fórmula, o bloco fica sem nenhuma."""
    try:
        formula = mf.ler(texto)
    except mf.ErroDeFormula:
        return (), ()
    medidas = mf.dimensoes_das_letras(dimensoes)
    entradas = tuple(
        Porta(letra, item.texto, VALOR, item.dimensao)
        for letra, item in (
            (letra, mf.grandeza_da_letra(letra, sistema, medidas)) for letra in formula.letras
        )
    )
    saidas: list[Porta] = []
    if formula.tem_valor:
        dimensao = mf.dimensao_da_saida(formula, sistema, medidas, escolhida)
        saidas.append(Porta("saida", formula.nome or "Valor", VALOR, dimensao))
    if formula.tem_condicao:
        saidas.append(_CONDICAO)
    return entradas, tuple(saidas)


def portas_de(tipo: str, opcoes: Mapping[str, Any]) -> tuple[tuple[Porta, ...], tuple[Porta, ...]]:
    """Entradas e saídas de um bloco. Só a fórmula própria depende do que foi escolhido nele."""
    if tipo == FORMULA:
        return _portas_da_formula(
            str(opcoes.get("texto", "")),
            str(opcoes.get("dimensoes", "")),
            str(opcoes.get("saida", "")),
            str(opcoes.get("sistema", g.SISTEMA_SOLIDOS.chave)),
        )
    variavel = PORTAS_VARIAVEIS.get(tipo)
    if variavel is not None:
        return variavel(opcoes)
    bloco = POR_CHAVE[tipo]
    return bloco.entradas, bloco.saidas


def portas_para_a_tela(tipo: str, opcoes: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    entradas, saidas = portas_de(tipo, opcoes)
    return {
        "entradas": [porta_para_tela(p) for p in entradas],
        "saidas": [porta_para_tela(p) for p in saidas],
    }


def registrar(blocos: Sequence[Bloco]) -> None:
    """Outra parte do Montador acrescenta os blocos dela ao mesmo motor."""
    POR_CHAVE.update({b.chave: b for b in blocos})


def porta_para_tela(p: Porta) -> dict[str, Any]:
    return {
        "chave": p.chave,
        "rotulo": p.rotulo,
        "tipo": p.tipo,
        "dimensao": p.dimensao,
        "varias": p.varias,
    }


def catalogo_para_tela(dominio: str = SOLIDOS) -> list[dict[str, Any]]:
    """O que a prancheta precisa saber de cada bloco desta parte do Montador."""
    return [
        {
            "chave": b.chave,
            "nome": b.nome,
            "grupo": b.grupo,
            "classe": CLASSE_DO_GRUPO.get(b.grupo, "g-secao"),
            "categoria": CATEGORIA_DO_GRUPO.get(b.grupo, ""),
            "dica": b.dica,
            "formula": b.formula,
            "entradas": [porta_para_tela(p) for p in b.entradas],
            "saidas": [porta_para_tela(p) for p in b.saidas],
        }
        for b in sorted(POR_CHAVE.values(), key=lambda x: ORDEM_DOS_GRUPOS.index(x.grupo))
        if b.dominio in (dominio, COMUM)
    ]
