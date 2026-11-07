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
from typing import Any

import sympy as sp

from core import elementos_vigas as ev
from core import material_catalog as mc
from core import montador_grandezas as g
from core import montador_secoes as ms
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
    GRUPO_FLUIDO: "g-secao",
    GRUPO_TUBULACAO: "g-esforco",
    GRUPO_VERIFICACAO: "g-criterio",
    GRUPO_EQUACOES: "g-origem",
    GRUPO_RESULTADO: "g-resultado",
    GRUPO_OUTROS: "g-material",
}

RESULTADO = "resultado"
REFERENCIA = "referencia"
SEM_MATERIAL = "Escolha o material"
FLECHA_RELATIVA = "Relação L/δ"
FLECHA_ABSOLUTA = "Valor de δ"
FLECHAS = (FLECHA_RELATIVA, FLECHA_ABSOLUTA)
INFORMAR_FADIGA = "Informar alternado e médio"
EIXO_GIRANDO = "Eixo girando: flexão alternada e torque constante"
ESFORCOS_DA_FADIGA = (INFORMAR_FADIGA, EIXO_GIRANDO)

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
) -> Bloco:
    """Um bloco só de fórmulas. ``saidas``: chave, rótulo, dimensão e a função das letras."""

    def calcular(c: Contexto) -> dict[str, Any]:
        letras = [c.letra(g_) for g_ in entradas]
        return {k: funcao(*letras) for k, (_, _, funcao) in saidas.items()}

    portas = tuple(Porta(k, rotulo, VALOR, dim) for k, (rotulo, dim, _) in saidas.items())
    return Bloco(chave, nome, GRUPO_ORIGEM, dica, formula, (), portas, calcular)


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


def _goodman(c: Contexto) -> dict[str, Any]:
    estado = c.estado()
    fibra = estado.secao.pontos[0]
    kf, kfs = c.letra(g.KF), c.letra(g.KFS)
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
    ruptura = material.sut if material else c.letra(g.SUT)
    esquerda = alternada / c.letra(g.SE) + media / ruptura
    c.hipoteses.append(
        "Fadiga simplificada, para pré-dimensionamento: DE-Goodman com von Mises nas parcelas "
        "alternada e média. Confira em Análise de fadiga, e ligue também um critério de escoamento: "
        "Goodman não vê o escoamento no primeiro ciclo."
    )
    condicao = Condicao(
        "Fadiga (Goodman) na fibra externa",
        "Goodman",
        esquerda,
        1 / c.letra(g.FS),
        "\\frac{\\sigma_{a}'}{S_{e}} + \\frac{\\sigma_{m}'}{S_{ut}}",
        "fibra externa",
        (("\\sigma_{a}'", alternada), ("\\sigma_{m}'", media)),
        estado.validade,
    )
    return {"condicao": [condicao]}


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


def _resultado(c: Contexto) -> dict[str, Any]:
    return {}


def _referencia(c: Contexto) -> dict[str, Any]:
    valor = c.opcoes.get("valor")
    if valor in (None, ""):
        raise ErroDeBloco("Escolha o cálculo registrado.")
    return {"saida": sp.Float(float(valor))}


BLOCOS: tuple[Bloco, ...] = (
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
        },
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
        },
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
        },
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
        },
    ),
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
        "DE-Goodman simplificado. Usa os esforços da fila no eixo girando, ou os que você informar.",
        "σ_a'/S_e + σ_m'/S_ut ≤ 1/n",
        (_ENTRADA, _ENTRADA_MATERIAL),
        (_CONDICAO,),
        _goodman,
        (
            Opcao(
                "esforcos",
                "De onde vêm os esforços",
                "No eixo girando, a flexão da fila vira alternada e o torque fica constante, sem "
                "repetir valores. Para outros ciclos, informe as quatro parcelas.",
                ESFORCOS_DA_FADIGA,
                INFORMAR_FADIGA,
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
