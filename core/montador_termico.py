"""Os blocos do Montador térmico: estado do fluido, equipamentos, circuito e verificações.

O fio da **corrente** leva o fluido, a pressão absoluta, a entalpia e a vazão em massa. Pressão e
entalpia definem o estado mesmo dentro da mistura de líquido e vapor, e por isso são elas que andam
de bloco em bloco; temperatura, entropia e título saem delas pela CoolProp (:mod:`core.montador_
propriedades`). Cada equipamento muda o estado e entrega também a potência ou o calor dele, num fio
de valor, para as verificações e para o rendimento do ciclo.

Um ciclo fecha em laço. O bloco **Circuito** fica no laço e diz o fluido e a vazão, que num circuito
fechado não saem do desenho. O motor corta o fio que chega nele e fecha a pressão e a entalpia
supostas com as que de fato voltam (:mod:`core.montador_sistema`).

As contas são as de Çengel e Boles, Termodinâmica, capítulos 7, 10 e 11: compressão e expansão com
rendimento isentrópico, válvula a entalpia constante, troca de calor em pressão constante (menos a
perda de pressão informada) e mistura adiabática.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import sympy as sp

from core import montador_blocos as mb
from core import montador_grandezas as g
from core import montador_propriedades as mp
from core.montador_blocos import (
    CONDICAO,
    CORRENTE,
    TERMICO,
    VALOR,
    Bloco,
    Condicao,
    Contexto,
    ErroDeBloco,
    Opcao,
    Porta,
)
from core.montador_grandezas import Grandeza
from core.montador_secoes import Validade

#: Folga em J/kg para dizer que a entrada é líquida ou vapor: no líquido saturado, h fica em cima
#: da curva, e o arredondamento não pode virar aviso.
_FOLGA_DE_ENTALPIA = 50.0


@dataclass(frozen=True)
class Corrente:
    """O fluido num ponto do desenho. ``fluido`` é o número na lista de :mod:`montador_propriedades`."""

    fluido: int
    p: sp.Expr
    h: sp.Expr
    m: sp.Expr
    validade: tuple[Validade, ...] = ()

    @property
    def do_fluido(self) -> mp.Fluido:
        return mp.FLUIDOS[self.fluido]

    def temperatura(self) -> sp.Expr:
        return mp.de(self.fluido, mp.T, mp.PH, self.p, self.h)

    def entropia(self) -> sp.Expr:
        return mp.de(self.fluido, mp.S, mp.PH, self.p, self.h)

    def liquido_saturado(self) -> sp.Expr:
        return mp.de(self.fluido, mp.H, mp.PX, self.p, 0)

    def vapor_saturado(self) -> sp.Expr:
        return mp.de(self.fluido, mp.H, mp.PX, self.p, 1)

    def saturacao(self) -> sp.Expr:
        return mp.de(self.fluido, mp.T, mp.PX, self.p, 0)

    def titulo(self) -> sp.Expr:
        """(h − h_l)/(h_v − h_l): passa de 1 no vapor superaquecido e fica abaixo de 0 no líquido
        sub-resfriado. A CoolProp dá −1 fora da mistura, o que não serve para uma condição."""
        liquido, vapor = self.liquido_saturado(), self.vapor_saturado()
        return (self.h - liquido) / (vapor - liquido)


def _fluido(c: Contexto, chave: str = "fluido") -> int:
    rotulo = c.opcoes.get(chave, "Água")
    fluido = mp.POR_ROTULO.get(rotulo, mp.POR_ROTULO["Água"])
    return mp.FLUIDOS.index(fluido)


def _entrada(c: Contexto, porta: str = "entrada") -> Corrente:
    corrente = c.ligados.get(porta)
    if not isinstance(corrente, Corrente):
        raise ErroDeBloco(
            "Ligue aqui uma corrente: o estado do fluido ou a saída de um equipamento."
        )
    return corrente


def _com_validade(corrente: Corrente, *novas: Validade) -> Corrente:
    return replace(corrente, validade=(*corrente.validade, *novas))


def _hipotese_da_coolprop(c: Contexto, fluido: int) -> None:
    c.hipoteses.append(
        f"Propriedades de {mp.FLUIDOS[fluido].rotulo.lower()} pela CoolProp, pelo modelo de "
        "referência do fluido."
    )


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

PELA_TEMPERATURA_E_PRESSAO = "Temperatura e pressão"
LIQUIDO_PELA_PRESSAO = "Líquido saturado, pela pressão"
VAPOR_PELA_PRESSAO = "Vapor saturado, pela pressão"
TITULO_E_PRESSAO = "Título e pressão (mistura)"
LIQUIDO_PELA_TEMPERATURA = "Líquido saturado, pela temperatura"
VAPOR_PELA_TEMPERATURA = "Vapor saturado, pela temperatura"
SUPERAQUECIDO = "Vapor superaquecido: pressão e graus acima da saturação"
SUB_RESFRIADO = "Líquido sub-resfriado: pressão e graus abaixo da saturação"
COMO_DAR_O_ESTADO = (
    PELA_TEMPERATURA_E_PRESSAO,
    LIQUIDO_PELA_PRESSAO,
    VAPOR_PELA_PRESSAO,
    TITULO_E_PRESSAO,
    LIQUIDO_PELA_TEMPERATURA,
    VAPOR_PELA_TEMPERATURA,
    SUPERAQUECIDO,
    SUB_RESFRIADO,
)
_PRECISAM_DE_SATURACAO = frozenset(COMO_DAR_O_ESTADO) - {PELA_TEMPERATURA_E_PRESSAO}


def _faixa(fluido: int, t: sp.Expr) -> Validade:
    minimo, maximo = mp.faixa_de_temperatura(fluido)
    return Validade(
        (t - minimo) * (maximo - t),
        f"A temperatura saiu da faixa da tabela de {mp.FLUIDOS[fluido].rotulo.lower()}.",
        restringe=False,
    )


def _estado(c: Contexto) -> dict[str, Any]:
    fluido = _fluido(c)
    como = c.opcoes.get("como", PELA_TEMPERATURA_E_PRESSAO)
    if como in _PRECISAM_DE_SATURACAO and not mp.FLUIDOS[fluido].saturacao:
        raise ErroDeBloco(
            f"{mp.FLUIDOS[fluido].rotulo} não tem saturação na CoolProp: dê o estado pela "
            "temperatura e pela pressão."
        )
    validades: list[Validade] = []
    if como == PELA_TEMPERATURA_E_PRESSAO:
        t, p = c.letra(g.T_ESTADO), c.letra(g.P_ESTADO)
        h = mp.de(fluido, mp.H, mp.TP, t, p)
        validades.append(_faixa(fluido, t))
    elif como in (LIQUIDO_PELA_PRESSAO, VAPOR_PELA_PRESSAO, TITULO_E_PRESSAO):
        p = c.letra(g.P_ESTADO)
        titulo: Any = {LIQUIDO_PELA_PRESSAO: 0, VAPOR_PELA_PRESSAO: 1}.get(como)
        if titulo is None:
            titulo = c.letra(g.X_ESTADO)
        h = mp.de(fluido, mp.H, mp.PX, p, titulo)
    elif como in (LIQUIDO_PELA_TEMPERATURA, VAPOR_PELA_TEMPERATURA):
        t = c.letra(g.T_ESTADO)
        titulo = 0 if como == LIQUIDO_PELA_TEMPERATURA else 1
        p = mp.de(fluido, mp.PV, mp.TX, t, 0)
        h = mp.de(fluido, mp.H, mp.TX, t, titulo)
        validades.append(_faixa(fluido, t))
    else:
        p = c.letra(g.P_ESTADO)
        saturacao = mp.de(fluido, mp.T, mp.PX, p, 0)
        if como == SUPERAQUECIDO:
            t = saturacao + c.letra(g.DT_SUPER)
        else:
            t = saturacao - c.letra(g.DT_SUB)
        h = mp.de(fluido, mp.H, mp.TP, t, p)
    _hipotese_da_coolprop(c, fluido)
    return {"saida": Corrente(fluido, p, h, c.letra(g.M_DOT), tuple(validades))}


# ---------------------------------------------------------------------------
# Equipamentos
# ---------------------------------------------------------------------------


def _isentropica(corrente: Corrente, p_saida: sp.Expr) -> sp.Expr:
    """A entalpia na pressão de saída com a mesma entropia da entrada: o processo ideal."""
    return mp.de(corrente.fluido, mp.H, mp.PS, p_saida, corrente.entropia())


def _comprimir(
    c: Contexto, letra_p: Grandeza, letra_eta: Grandeza, liquido: bool, nome: str
) -> dict[str, Any]:
    entrada = _entrada(c)
    p2, eta = c.letra(letra_p), c.letra(letra_eta)
    ideal = _isentropica(entrada, p2)
    h2 = entrada.h + (ideal - entrada.h) / eta
    validades = [
        Validade(
            p2 - entrada.p,
            f"A pressão de saída da {nome} precisa ser maior que a de entrada.",
        )
    ]
    if entrada.do_fluido.saturacao:
        if liquido:
            validades.append(
                Validade(
                    entrada.liquido_saturado() - entrada.h + _FOLGA_DE_ENTALPIA,
                    "A bomba recebe vapor: na entrada dela o fluido precisa estar líquido, ou vai "
                    "cavitar.",
                    restringe=False,
                )
            )
        else:
            validades.append(
                Validade(
                    entrada.h - entrada.vapor_saturado() + _FOLGA_DE_ENTALPIA,
                    "O compressor recebe líquido: na entrada dele o fluido precisa estar todo em "
                    "vapor, de preferência superaquecido.",
                    restringe=False,
                )
            )
    c.hipoteses.append(
        f"{nome.capitalize()} adiabática: a entalpia de saída vem da isentrópica dividida pelo "
        "rendimento, h₂ = h₁ + (h₂ₛ − h₁)/η."
    )
    saida = _com_validade(replace(entrada, p=p2, h=h2), *validades)
    return {"saida": saida, "potencia": entrada.m * (h2 - entrada.h)}


def _bomba(c: Contexto) -> dict[str, Any]:
    return _comprimir(c, g.P_BOMBA, g.ETA_BOMBA, True, "bomba")


def _compressor(c: Contexto) -> dict[str, Any]:
    return _comprimir(c, g.P_COMPRESSOR, g.ETA_COMPRESSOR, False, "compressão")


def _turbina(c: Contexto) -> dict[str, Any]:
    entrada = _entrada(c)
    p2, eta = c.letra(g.P_TURBINA), c.letra(g.ETA_TURBINA)
    h2 = entrada.h - eta * (entrada.h - _isentropica(entrada, p2))
    c.hipoteses.append(
        "Turbina adiabática: a queda de entalpia é a isentrópica vezes o rendimento, "
        "h₂ = h₁ − η·(h₁ − h₂ₛ)."
    )
    saida = _com_validade(
        replace(entrada, p=p2, h=h2),
        Validade(
            entrada.p - p2, "A pressão de saída da turbina precisa ser menor que a de entrada."
        ),
    )
    return {"saida": saida, "potencia": entrada.m * (entrada.h - h2)}


def _valvula(c: Contexto) -> dict[str, Any]:
    entrada = _entrada(c)
    p2 = c.letra(g.P_VALVULA)
    c.hipoteses.append("Válvula de expansão adiabática: a entalpia não muda, h₂ = h₁.")
    saida = _com_validade(
        replace(entrada, p=p2),
        Validade(entrada.p - p2, "Depois da válvula a pressão precisa ser menor que antes."),
    )
    return {"saida": saida}


TEMPERATURA_DE_SAIDA = "Temperatura de saída"
LIQUIDO_NA_SAIDA = "Sai líquido saturado (condensador)"
VAPOR_NA_SAIDA = "Sai vapor saturado (evaporador)"
TITULO_NA_SAIDA = "Título de saída"
CALOR_TROCADO = "Calor trocado"
SAIDAS_DA_TROCA = (
    TEMPERATURA_DE_SAIDA,
    LIQUIDO_NA_SAIDA,
    VAPOR_NA_SAIDA,
    TITULO_NA_SAIDA,
    CALOR_TROCADO,
)


def _troca(c: Contexto) -> dict[str, Any]:
    entrada = _entrada(c)
    p2 = entrada.p - c.letra(g.DP_TROCA)
    como = c.opcoes.get("saida", TEMPERATURA_DE_SAIDA)
    if (
        como in (LIQUIDO_NA_SAIDA, VAPOR_NA_SAIDA, TITULO_NA_SAIDA)
        and not entrada.do_fluido.saturacao
    ):
        raise ErroDeBloco(
            f"{entrada.do_fluido.rotulo} não tem saturação na CoolProp: dê a temperatura de saída "
            "ou o calor."
        )
    validades = [Validade(p2, "A perda de pressão passou da pressão de entrada.")]
    if como == TEMPERATURA_DE_SAIDA:
        t = c.letra(g.T_SAIDA)
        h2 = mp.de(entrada.fluido, mp.H, mp.TP, t, p2)
        validades.append(_faixa(entrada.fluido, t))
    elif como == CALOR_TROCADO:
        h2 = entrada.h + c.letra(g.Q_DOT) / entrada.m
    else:
        titulo: Any = {LIQUIDO_NA_SAIDA: 0, VAPOR_NA_SAIDA: 1}.get(como)
        if titulo is None:
            titulo = c.letra(g.X_SAIDA)
        h2 = mp.de(entrada.fluido, mp.H, mp.PX, p2, titulo)
    c.hipoteses.append(
        "Troca de calor em regime permanente: Q̇ = ṁ·(h₂ − h₁), positivo quando o fluido recebe "
        "calor, com a pressão caindo só a perda informada."
    )
    saida = _com_validade(replace(entrada, p=p2, h=h2), *validades)
    return {"saida": saida, "calor": entrada.m * (h2 - entrada.h)}


def _misturador(c: Contexto) -> dict[str, Any]:
    a, b = _entrada(c, "a"), _entrada(c, "b")
    if a.fluido != b.fluido:
        raise ErroDeBloco("As duas correntes precisam ser do mesmo fluido.")
    m = a.m + b.m
    c.hipoteses.append(
        "Mistura adiabática em pressão constante: h₃ = (ṁ_a·h_a + ṁ_b·h_b)/(ṁ_a + ṁ_b), com a "
        "pressão da entrada A."
    )
    saida = Corrente(a.fluido, a.p, (a.m * a.h + b.m * b.h) / m, m, (*a.validade, *b.validade))
    return {"saida": saida}


def _divisor(c: Contexto) -> dict[str, Any]:
    entrada = _entrada(c)
    y = c.letra(g.Y_DIVISOR)
    return {"a": replace(entrada, m=entrada.m * y), "b": replace(entrada, m=entrada.m * (1 - y))}


def _circuito(c: Contexto) -> dict[str, Any]:
    fluido = _fluido(c)
    entrada = c.ligados.get("entrada")
    if isinstance(entrada, Corrente) and entrada.fluido >= 0 and entrada.fluido != fluido:
        raise ErroDeBloco("A corrente que chega é de outro fluido: escolha o mesmo do circuito.")
    if not isinstance(entrada, Corrente):
        raise ErroDeBloco("Feche o laço: ligue aqui a saída do último equipamento do ciclo.")
    _hipotese_da_coolprop(c, fluido)
    c.hipoteses.append(
        "Circuito fechado: o fluido que sai do último equipamento volta para o primeiro, e a "
        "vazão é a mesma em todo o laço."
    )
    return {
        "saida": Corrente(fluido, entrada.p, entrada.h, c.letra(g.M_CIRCUITO), entrada.validade)
    }


def rasgar(numero: int) -> tuple[Corrente, list[tuple[Grandeza, Any]]]:
    """O corte de um laço de corrente: pressão e entalpia supostas, que a conta fecha com as que
    voltam. O fluido e a vazão quem dá é o bloco Circuito, que recebe este fio."""
    pressao = Grandeza(
        f"p_lc{numero}",
        f"p laço {numero}",
        f"Pressão que volta pelo laço {numero}",
        g.PRESSAO,
        "Calculada: a pressão que sai do fim do laço e volta para o começo dele.",
        101325.0,
    )
    entalpia = Grandeza(
        f"h_lc{numero}",
        f"h laço {numero}",
        f"Entalpia que volta pelo laço {numero}",
        g.ENERGIA_ESPECIFICA,
        "Calculada: a entalpia que sai do fim do laço e volta para o começo dele.",
        2e5,
        sinal_livre=True,
    )
    suposta = Corrente(-1, pressao.simbolo, entalpia.simbolo, sp.S.One)
    return suposta, [(pressao, lambda c: c.p), (entalpia, lambda c: c.h)]


# ---------------------------------------------------------------------------
# Verificações
# ---------------------------------------------------------------------------


def _condicao(
    nome: str,
    esquerda: sp.Expr,
    direita: sp.Expr,
    letra: str,
    validade: Sequence[Validade] = (),
    igualdade: bool = False,
) -> dict[str, Any]:
    return {
        "condicao": [
            Condicao(
                nome, nome, esquerda, direita, letra, validade=tuple(validade), igualdade=igualdade
            )
        ]
    }


def _temperatura_maxima(c: Contexto) -> dict[str, Any]:
    entrada = _entrada(c)
    return _condicao(
        "Temperatura máxima", entrada.temperatura(), c.letra(g.T_MAXIMA), "T", entrada.validade
    )


def _temperatura_minima(c: Contexto) -> dict[str, Any]:
    entrada = _entrada(c)
    return _condicao(
        "Temperatura mínima",
        c.letra(g.T_MINIMA),
        entrada.temperatura(),
        "T_{mín}",
        entrada.validade,
    )


def _titulo_minimo(c: Contexto) -> dict[str, Any]:
    entrada = _entrada(c)
    if not entrada.do_fluido.saturacao:
        raise ErroDeBloco("Esse fluido não tem saturação na CoolProp: não há título.")
    return _condicao(
        "Título mínimo", c.letra(g.X_MINIMO), entrada.titulo(), "x_{mín}", entrada.validade
    )


def _superaquecimento(c: Contexto) -> dict[str, Any]:
    entrada = _entrada(c)
    if not entrada.do_fluido.saturacao:
        raise ErroDeBloco("Esse fluido não tem saturação na CoolProp: não há superaquecimento.")
    folga = entrada.temperatura() - entrada.saturacao()
    return _condicao(
        "Superaquecimento mínimo", c.letra(g.DT_MINIMO), folga, "\\Delta T_{mín}", entrada.validade
    )


def _subresfriamento(c: Contexto) -> dict[str, Any]:
    entrada = _entrada(c)
    if not entrada.do_fluido.saturacao:
        raise ErroDeBloco("Esse fluido não tem saturação na CoolProp: não há sub-resfriamento.")
    folga = entrada.saturacao() - entrada.temperatura()
    return _condicao(
        "Sub-resfriamento mínimo", c.letra(g.DT_MINIMO), folga, "\\Delta T_{mín}", entrada.validade
    )


def _soma(c: Contexto, porta: str) -> sp.Expr:
    valores = c.ligados.get(porta) or []
    if not isinstance(valores, list):
        valores = [valores]
    return sp.Add(*valores) if valores else sp.S.Zero


def _potencia_maxima(c: Contexto) -> dict[str, Any]:
    total = _soma(c, "potencias")
    if total == 0:
        raise ErroDeBloco("Ligue aqui a potência de um equipamento.")
    return _condicao("Potência disponível", sp.Abs(total), c.letra(g.P_MAXIMA), "\\dot{W}")


def _calor_pedido(c: Contexto) -> dict[str, Any]:
    total = _soma(c, "calores")
    if total == 0:
        raise ErroDeBloco("Ligue aqui o calor de uma troca de calor.")
    return _condicao("Calor pedido", sp.Abs(total), c.letra(g.Q_PEDIDO), "\\dot{Q}", igualdade=True)


def _rendimento(c: Contexto) -> dict[str, Any]:
    produzido, consumido = _soma(c, "produzidos"), _soma(c, "consumidos")
    recebido = _soma(c, "recebidos")
    if recebido == 0 or produzido == 0:
        raise ErroDeBloco("Ligue o trabalho da turbina e o calor que o ciclo recebe.")
    liquido = produzido - consumido
    return _condicao(
        "Rendimento térmico",
        liquido / recebido,
        c.letra(g.ETA_CICLO),
        "\\eta_{t}",
        igualdade=True,
    )


def _cop(c: Contexto) -> dict[str, Any]:
    util, consumido = _soma(c, "uteis"), _soma(c, "consumidos")
    if util == 0 or consumido == 0:
        raise ErroDeBloco("Ligue o calor útil (do evaporador) e o trabalho do compressor.")
    return _condicao("COP", sp.Abs(util) / consumido, c.letra(g.COP), "COP", igualdade=True)


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

_ENTRADA = Porta("entrada", "Entrada", CORRENTE)
_SAIDA = Porta("saida", "Saída", CORRENTE)
_POTENCIA = Porta("potencia", "Ẇ", VALOR, g.POTENCIA)
_CALOR = Porta("calor", "Q̇", VALOR, g.POTENCIA)
_CONDICAO = Porta("condicao", "Condição", CONDICAO)
_ROTULOS_DOS_FLUIDOS = tuple(f.rotulo for f in mp.FLUIDOS)
_FLUIDO = Opcao(
    "fluido",
    "Fluido",
    "Água e vapor pela IAPWS, ar, refrigerantes, CO₂, amônia, glicóis e óleos térmicos, todos pela "
    "CoolProp. Glicóis e óleos são líquidos de tabela: não evaporam.",
    _ROTULOS_DOS_FLUIDOS,
    "Água",
)


def _equipamento(
    chave: str,
    nome: str,
    dica: str,
    formula: str,
    calcular: Any,
    saidas: tuple[Porta, ...] = (_SAIDA,),
    entradas: tuple[Porta, ...] = (_ENTRADA,),
    opcoes: tuple[Opcao, ...] = (),
) -> Bloco:
    return Bloco(
        chave,
        nome,
        mb.GRUPO_EQUIPAMENTO,
        dica,
        formula,
        entradas,
        saidas,
        calcular,
        opcoes,
        numerar=True,
        dominio=TERMICO,
    )


def _verificacao(
    chave: str, nome: str, dica: str, formula: str, calcular: Any, entradas: tuple[Porta, ...]
) -> Bloco:
    return Bloco(
        chave,
        nome,
        mb.GRUPO_VERIFICACAO,
        dica,
        formula,
        entradas,
        (_CONDICAO,),
        calcular,
        dominio=TERMICO,
    )


def _muitas(chave: str, rotulo: str) -> Porta:
    return Porta(chave, rotulo, VALOR, g.POTENCIA, varias=True)


BLOCOS_TERMICOS: tuple[Bloco, ...] = (
    Bloco(
        "estado",
        "Estado do fluido",
        mb.GRUPO_ESTADO,
        "O começo da fila: o fluido, o estado dele e a vazão em massa.",
        "p · h · ṁ",
        (),
        (_SAIDA,),
        _estado,
        (
            _FLUIDO,
            Opcao(
                "como",
                "Como dar o estado",
                "Temperatura e pressão serve para líquido e gás. Na mistura de líquido e vapor, a "
                "temperatura e a pressão andam juntas: dê a pressão e o título.",
                COMO_DAR_O_ESTADO,
                PELA_TEMPERATURA_E_PRESSAO,
            ),
        ),
        numerar=True,
        dominio=TERMICO,
    ),
    Bloco(
        "circuito",
        "Circuito",
        mb.GRUPO_ESTADO,
        "Fecha o ciclo: recebe a saída do último equipamento e diz o fluido e a vazão do laço.",
        "laço · ṁ_c",
        (_ENTRADA,),
        (_SAIDA,),
        _circuito,
        (_FLUIDO,),
        numerar=True,
        dominio=TERMICO,
    ),
    _equipamento(
        "bomba_termica",
        "Bomba",
        "Sobe a pressão de um líquido. Entrega a potência que consome.",
        "h₂ = h₁ + (h₂ₛ − h₁)/η",
        _bomba,
        (_SAIDA, _POTENCIA),
    ),
    _equipamento(
        "compressor",
        "Compressor",
        "Sobe a pressão de um gás ou vapor. Entrega a potência que consome.",
        "h₂ = h₁ + (h₂ₛ − h₁)/η",
        _compressor,
        (_SAIDA, _POTENCIA),
    ),
    _equipamento(
        "turbina",
        "Turbina",
        "Expande vapor ou gás e entrega a potência que produz.",
        "h₂ = h₁ − η·(h₁ − h₂ₛ)",
        _turbina,
        (_SAIDA, _POTENCIA),
    ),
    _equipamento(
        "valvula",
        "Válvula de expansão",
        "Baixa a pressão sem trocar calor nem trabalho: a entalpia fica a mesma.",
        "h₂ = h₁",
        _valvula,
    ),
    _equipamento(
        "troca_de_calor",
        "Troca de calor",
        "Caldeira, aquecedor, condensador, evaporador ou resfriador: o fluido recebe ou perde calor.",
        "Q̇ = ṁ·(h₂ − h₁)",
        _troca,
        (_SAIDA, _CALOR),
        opcoes=(
            Opcao(
                "saida",
                "Como sai o fluido",
                "Pela temperatura de saída, saturado (condensador ou evaporador), pelo título, ou "
                "pelo calor trocado.",
                SAIDAS_DA_TROCA,
                TEMPERATURA_DE_SAIDA,
            ),
        ),
    ),
    _equipamento(
        "misturador",
        "Misturador",
        "Junta duas correntes do mesmo fluido, sem trocar calor.",
        "ṁ₃·h₃ = ṁ_a·h_a + ṁ_b·h_b",
        _misturador,
        entradas=(Porta("a", "Entrada A", CORRENTE), Porta("b", "Entrada B", CORRENTE)),
    ),
    _equipamento(
        "divisor",
        "Divisor",
        "Separa a corrente em duas, no mesmo estado, com a fração y para a saída A.",
        "ṁ_a = y·ṁ",
        _divisor,
        (Porta("a", "Saída A", CORRENTE), Porta("b", "Saída B", CORRENTE)),
    ),
    _verificacao(
        "temperatura_maxima",
        "Temperatura máxima",
        "A temperatura da corrente não pode passar do limite.",
        "T ≤ T_máx",
        _temperatura_maxima,
        (_ENTRADA,),
    ),
    _verificacao(
        "temperatura_minima",
        "Temperatura mínima",
        "A temperatura da corrente não pode ficar abaixo do limite.",
        "T ≥ T_mín",
        _temperatura_minima,
        (_ENTRADA,),
    ),
    _verificacao(
        "titulo_minimo",
        "Título mínimo",
        "Na saída da turbina a vapor: pouca umidade. Vapor superaquecido passa.",
        "x ≥ x_mín",
        _titulo_minimo,
        (_ENTRADA,),
    ),
    _verificacao(
        "superaquecimento_minimo",
        "Superaquecimento mínimo",
        "Na entrada do compressor: longe o bastante do vapor saturado para não chegar líquido.",
        "T − T_sat ≥ ΔT_mín",
        _superaquecimento,
        (_ENTRADA,),
    ),
    _verificacao(
        "subresfriamento_minimo",
        "Sub-resfriamento mínimo",
        "Na entrada da válvula ou da bomba: longe o bastante do líquido saturado para não vaporizar.",
        "T_sat − T ≥ ΔT_mín",
        _subresfriamento,
        (_ENTRADA,),
    ),
    _verificacao(
        "potencia_maxima",
        "Potência disponível",
        "A potência somada dos equipamentos ligados aqui não pode passar da disponível.",
        "Ẇ ≤ P_máx",
        _potencia_maxima,
        (_muitas("potencias", "Ẇ"),),
    ),
    _verificacao(
        "calor_pedido",
        "Calor pedido",
        "O calor da troca precisa ser este: peça a vazão, a temperatura ou a pressão que fecha.",
        "|Q̇| = Q_ped",
        _calor_pedido,
        (_muitas("calores", "Q̇"),),
    ),
    _verificacao(
        "rendimento_ciclo",
        "Rendimento do ciclo",
        "Trabalho líquido dividido pelo calor recebido: ligue turbinas, bombas e a caldeira.",
        "η_t = (Ẇ_prod − Ẇ_cons)/Q̇_rec",
        _rendimento,
        (
            _muitas("produzidos", "Ẇ produzido"),
            _muitas("consumidos", "Ẇ consumido"),
            _muitas("recebidos", "Q̇ recebido"),
        ),
    ),
    _verificacao(
        "cop",
        "COP",
        "Refrigeração: o calor tirado no evaporador dividido pelo trabalho do compressor.",
        "COP = |Q̇_útil|/Ẇ",
        _cop,
        (_muitas("uteis", "Q̇ útil"), _muitas("consumidos", "Ẇ consumido")),
    ),
)

mb.registrar(BLOCOS_TERMICOS)
mb.RASGAR[CORRENTE] = rasgar
mb.INICIO_DE_LACO.add("circuito")


def resumo_da_corrente(corrente: Corrente) -> Mapping[str, sp.Expr]:
    dados: dict[str, sp.Expr] = {
        "p": corrente.p,
        "T": corrente.temperatura(),
        "h": corrente.h,
        "s": corrente.entropia(),
        "ṁ": corrente.m,
    }
    if corrente.do_fluido.saturacao:
        dados["x"] = corrente.titulo()
    return dados


__all__ = [
    "BLOCOS_TERMICOS",
    "COMO_DAR_O_ESTADO",
    "Corrente",
    "SAIDAS_DA_TROCA",
    "rasgar",
    "resumo_da_corrente",
]
