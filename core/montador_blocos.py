"""O catálogo de blocos do montador de fórmulas.

Para acrescentar uma equação, basta acrescentar um ``Bloco`` a ``BLOCOS``: a prancheta, a tabela de
valores e a conta leem daqui. Um bloco declara as portas e tem uma função ``calcular`` que recebe o
``Contexto`` e devolve o valor de cada saída. Fórmula de viga ou de origem de esforço usa ``origem``,
que precisa só das expressões.

Há três tipos de fio. O da **seção** leva a seção e as tensões somadas até ali, e por isso os esforços
ficam em fila: Seção → Flexão → Cortante → Critério. O de **valor** troca uma letra pela fórmula de
outro bloco, como o M da flexão por F·L/4 da viga. O de **condição** leva "isto ≤ aquilo" até o bloco
do resultado.
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

GRUPO_SECAO = "Seção"
GRUPO_ORIGEM = "De onde vem o esforço"
GRUPO_ESFORCO = "Esforços"
GRUPO_MATERIAL = "Material"
GRUPO_CRITERIO = "Critério"
GRUPO_RESULTADO = "Resultado"
GRUPOS = (
    GRUPO_SECAO,
    GRUPO_ORIGEM,
    GRUPO_ESFORCO,
    GRUPO_MATERIAL,
    GRUPO_CRITERIO,
    GRUPO_RESULTADO,
)

RESULTADO = "resultado"
SEM_MATERIAL = "Escolha o material"
FLECHA_RELATIVA = "Relação L/δ"
FLECHA_ABSOLUTA = "Valor de δ"
FLECHAS = (FLECHA_RELATIVA, FLECHA_ABSOLUTA)


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
    """``esquerda`` ≤ ``direita``: a inequação de um critério num ponto da seção."""

    nome: str
    criterio: str
    esquerda: sp.Expr
    direita: sp.Expr
    letra: str  # LaTeX do lado esquerdo
    ponto: str = ""
    tensoes: tuple[tuple[str, sp.Expr], ...] = ()
    validade: tuple[Validade, ...] = ()
    positiva: bool = True  # no estado biaxial, σ_x − σ_y pode dar negativo, e o módulo fica

    @property
    def letras(self) -> set[sp.Symbol]:
        return self.esquerda.free_symbols | self.direita.free_symbols


@dataclass
class Contexto:
    """O que um bloco enxerga quando calcula."""

    indice: int
    opcoes: Mapping[str, str]
    ligados: Mapping[str, Any]
    numerar: bool = False
    grandezas: dict[str, Grandeza] = field(default_factory=dict)
    padroes: dict[str, float] = field(default_factory=dict)
    alertas: list[str] = field(default_factory=list)
    hipoteses: list[str] = field(default_factory=list)
    marcas: set[str] = field(default_factory=set)

    def letra(self, grandeza: Grandeza, porta: str | None = None) -> sp.Expr:
        """O que está ligado na porta, ou a própria letra, que vira uma linha na tabela de valores."""
        ligado = self.ligados.get(porta) if porta else None
        if ligado is not None:
            return ligado
        grandeza = grandeza.com_indice(self.indice) if self.numerar else grandeza
        self.grandezas.setdefault(grandeza.chave, grandeza)
        return grandeza.simbolo

    def estado(self) -> Estado:
        estado = self.ligados.get("entrada")
        if estado is None:
            raise ErroDeBloco("Ligue uma seção aqui.")
        return estado

    def opcao(self, bloco: Bloco, chave: str) -> str:
        opcao = next(o for o in bloco.opcoes if o.chave == chave)
        valor = self.opcoes.get(chave)
        return valor if valor in opcao.lista() else opcao.padrao


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


_ENTRADA = Porta("entrada", "Seção", SECAO)
_SAIDA = Porta("saida", "Seção", SECAO)
_CONDICAO = Porta("condicao", "Condição", CONDICAO)


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
    )
    c.hipoteses.append(
        "Pressão em parede fina, com o diâmetro externo: σ_c = p·d/(2·t) e σ_l = p·d/(4·t)."
    )
    return {"saida": estado.com_pressao(p * longitudinal, p * circunferencial).com_validade(fina)}


def _material(c: Contexto) -> dict[str, Any]:
    nome = c.opcoes.get("material", SEM_MATERIAL)
    if nome != SEM_MATERIAL:
        material = mc.obter(nome)
        if material.sy_MPa > 0:
            c.padroes[g.SY.chave] = material.sy_MPa
        else:
            c.marcas.add("fragil")
        c.padroes[g.SUT.chave] = material.sut_MPa
        c.grandezas.setdefault(g.SUT.chave, g.SUT)
    return {"sy": c.letra(g.SY), "sut": c.letra(g.SUT)}


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


def _von_mises(c: Contexto) -> dict[str, Any]:
    c.marcas.add("ductil")
    limite = c.letra(g.SY, "limite") / c.letra(g.FS)

    def funcao(t: ms.Tensao) -> Sequence[sp.Expr]:
        return (sp.sqrt(t.sx**2 - t.sx * t.sy + t.sy**2 + 3 * t.tau**2),)

    return _nos_pontos(c, "von Mises", "\\sigma_{eq}", limite, funcao)


def _tresca(c: Contexto) -> dict[str, Any]:
    c.marcas.add("ductil")
    limite = c.letra(g.SY, "limite") / c.letra(g.FS)

    def funcao(t: ms.Tensao) -> Sequence[sp.Expr]:
        # Com σ_y, as duas principais podem ter o mesmo sinal, e a terceira, zero, entra na diferença.
        diferenca = sp.sqrt((t.sx - t.sy) ** 2 + 4 * t.tau**2)
        return (diferenca,) if t.sy == 0 else (diferenca, _principal(t))

    return _nos_pontos(c, "Tresca", "\\sigma_{eq}", limite, funcao)


def _rankine(c: Contexto) -> dict[str, Any]:
    c.marcas.add("fragil_ok")
    limite = c.letra(g.SUT, "limite") / c.letra(g.FS)
    c.hipoteses.append("Maior tensão principal: critério de material frágil, em tração.")
    return _nos_pontos(c, "Maior principal", "\\sigma_{1}", limite, lambda t: (_principal(t),))


def _goodman(c: Contexto) -> dict[str, Any]:
    estado = c.estado()
    fibra = estado.secao.pontos[0]
    kf, kfs = c.letra(g.KF), c.letra(g.KFS)
    ma, mm = c.letra(g.MA), c.letra(g.MM)
    ta, tm = c.letra(g.TA), c.letra(g.TM)

    def equivalente(momento: sp.Expr, torque: sp.Expr) -> sp.Expr:
        sigma = kf * momento * fibra.por_momento
        tau = kfs * torque * fibra.por_torque
        return sp.sqrt(sigma**2 + 3 * tau**2)

    alternada, media = equivalente(ma, ta), equivalente(mm, tm)
    esquerda = alternada / c.letra(g.SE) + media / c.letra(g.SUT, "limite")
    c.hipoteses.append(
        "Fadiga pelo critério de Goodman com von Mises nas parcelas alternada e média (DE-Goodman)."
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
    esquerda = produto / (c.letra(g.E) * inercia)
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
    e, l_, k = c.letra(g.E), c.letra(g.L), c.letra(g.K_FLAMB)
    critica = sp.pi**2 * e * secao.inercia_min / (k * l_) ** 2
    esquerda = c.letra(g.FS) * forca
    validade = list(estado.validade)
    sy = c.ligados.get("limite")
    if sy is not None:
        validade.append(
            Validade(
                (k * l_) ** 2 * area_sobre_i - 2 * sp.pi**2 * e / sy,
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
    esquerda = c.letra(g.T, "valor") * c.letra(g.L) / (c.letra(g.G) * estado.secao.polar)
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


_LIMITE_SY = Porta("limite", "S_y", VALOR, g.TENSAO)
_LIMITE_SUT = Porta("limite", "S_ut", VALOR, g.TENSAO)

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
        "Traz S_y e S_ut do cadastro. A letra fica na fórmula, com o valor na tabela.",
        "S_y · S_ut",
        (),
        (Porta("sy", "S_y", VALOR, g.TENSAO), Porta("sut", "S_ut", VALOR, g.TENSAO)),
        _material,
        (
            Opcao(
                "material",
                "Material",
                "Vem do cadastro de materiais. Sem escolher, S_y e S_ut ficam em letra.",
                lambda: (SEM_MATERIAL, *mc.listar_nomes()),
                SEM_MATERIAL,
            ),
        ),
    ),
    Bloco(
        "von_mises",
        "von Mises",
        GRUPO_CRITERIO,
        "Material dúctil: junta σ e τ de cada ponto na tensão equivalente.",
        "√(σ² + 3·τ²) ≤ S_y/n",
        (_ENTRADA, _LIMITE_SY),
        (_CONDICAO,),
        _von_mises,
    ),
    Bloco(
        "tresca",
        "Tresca",
        GRUPO_CRITERIO,
        "Material dúctil, mais conservador que von Mises.",
        "√(σ² + 4·τ²) ≤ S_y/n",
        (_ENTRADA, _LIMITE_SY),
        (_CONDICAO,),
        _tresca,
    ),
    Bloco(
        "rankine",
        "Maior principal",
        GRUPO_CRITERIO,
        "Material frágil, como ferro fundido cinzento.",
        "σ₁ ≤ S_ut/n",
        (_ENTRADA, _LIMITE_SUT),
        (_CONDICAO,),
        _rankine,
    ),
    Bloco(
        "goodman",
        "Fadiga de eixo",
        GRUPO_CRITERIO,
        "DE-Goodman: flexão e torção alternadas e médias. Dispensa os blocos de esforço.",
        "σ_a'/S_e + σ_m'/S_ut ≤ 1/n",
        (_ENTRADA, _LIMITE_SUT),
        (_CONDICAO,),
        _goodman,
    ),
    Bloco(
        "flecha",
        "Flecha",
        GRUPO_CRITERIO,
        "Liga a seção e a saída δ·EI de um bloco de viga.",
        "δ = (δ·EI)/(E·I)",
        (_ENTRADA, Porta("flecha", "δ·EI", VALOR, g.FLECHA_EI)),
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
        (_ENTRADA, Porta("valor", "N", VALOR, g.FORCA), _LIMITE_SY),
        (_CONDICAO,),
        _flambagem,
    ),
    Bloco(
        "giro",
        "Giro por torção",
        GRUPO_CRITERIO,
        "Rigidez do eixo: o quanto ele torce no trecho.",
        "φ = T·L/(G·J)",
        (_ENTRADA, Porta("valor", "T", VALOR, g.MOMENTO)),
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
    ),
)

POR_CHAVE: dict[str, Bloco] = {b.chave: b for b in BLOCOS}


def catalogo_para_tela() -> list[dict[str, Any]]:
    """O que a prancheta precisa saber de cada bloco."""

    def porta(p: Porta) -> dict[str, Any]:
        return {
            "chave": p.chave,
            "rotulo": p.rotulo,
            "tipo": p.tipo,
            "dimensao": p.dimensao,
            "varias": p.varias,
        }

    return [
        {
            "chave": b.chave,
            "nome": b.nome,
            "grupo": b.grupo,
            "dica": b.dica,
            "formula": b.formula,
            "entradas": [porta(p) for p in b.entradas],
            "saidas": [porta(p) for p in b.saidas],
        }
        for b in BLOCOS
    ]
