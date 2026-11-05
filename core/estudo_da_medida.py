"""Estudo de uma medida: até onde ela passa, quem trava e qual medida pesa mais no resultado.

Nada aqui inverte fórmula. O estudo roda o próprio cálculo do caso em vários valores, e por isso
vale para qualquer caso, e o número que ele acha é o mesmo que a tela mostraria com aquele valor.

A resposta é uma **faixa**, e não só um mínimo. Para uma espessura, o limite é o menor valor; para
uma carga, o maior; há medidas que têm os dois lados, como o diâmetro de uma polia. A curva também
não precisa ser sempre crescente: a grade acha cada troca de passa para não passa, e a bisseção
fecha cada troca até a tolerância. Dado que o caso recusa (furo maior que a chapa) conta como não
passa, com o motivo.

Recomendação não reprova, então fica fora da conta dos 100 %. Ela aparece à parte: "sem ressalvas a
partir de tal valor".
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from core import cotas_dos_desenhos as cd
from core.beam_charts import so_a_conta
from core.cotas_dos_desenhos import CotaViva
from core.elementos_base import Caso, Resultado, calcular_caso
from core.medidas_comerciais import Serie, valores_que_cabem

PONTOS = 41
#: A busca vai deste tanto para cima e para baixo do valor atual.
RAZAO_DA_BUSCA = 8.0
PASSOS_DA_BISSECAO = 18
TOLERANCIA = 1e-4
#: Quantos valores comerciais experimentar: a curva pode não ser crescente.
TENTATIVAS_COMERCIAIS = 10
#: Quanto a medida anda para medir o peso dela no resultado.
ANDAR = 0.10
#: Abaixo disto a medida não influi: é só o ruído da conta.
PESO_DESPREZIVEL = 0.005
UNIDADES_DE_GEOMETRIA = {"mm", "cm", "m", "mm²"}
DECISIVOS = ("OK", "NÃO OK", "ALERTA")
#: O que um dado impossível pode levantar. TypeError é o campo numérico que ficou vazio.
FALHAS = (ValueError, ArithmeticError, TypeError)


@dataclass(frozen=True)
class Avaliacao:
    """O caso rodado com a medida em um valor."""

    valor: float
    status: str = "N/A"
    aproveitamento: float | None = None
    governa: str = ""
    criterios: Mapping[str, float] = field(default_factory=dict)
    metricas: Mapping[str, tuple[float, str]] = field(default_factory=dict)
    tem_obrigatorio: bool = False
    erro: str = ""

    @property
    def passa(self) -> bool:
        return not self.erro and self.status != "NÃO OK"

    @property
    def sem_ressalva(self) -> bool:
        return self.passa and self.status != "ALERTA"

    @property
    def quem_trava(self) -> str:
        return self.erro or self.governa


def _criterios(resultado: Resultado) -> tuple[dict[str, float], bool]:
    """O aproveitamento de cada critério obrigatório. Sem nenhum, valem as recomendações."""
    decisivas = [
        v
        for v in resultado.verificacoes
        if v.status in DECISIVOS
        and v.aproveitamento is not None
        and not math.isnan(v.aproveitamento)
    ]
    obrigatorias = [v for v in decisivas if v.obrigatoria]
    criterios: dict[str, float] = {}
    for verificacao in obrigatorias or decisivas:
        anterior = criterios.get(verificacao.nome, -math.inf)
        criterios[verificacao.nome] = max(anterior, float(verificacao.aproveitamento or 0.0))
    return criterios, bool(obrigatorias)


def avaliar(caso: Caso, valores: Mapping[str, Any], valor: float = 0.0) -> Avaliacao:
    """Roda o caso e resume. Dado recusado volta como ``erro``, sem levantar nada."""
    try:
        with so_a_conta():
            resultado = calcular_caso(caso, valores)
    except FALHAS as falha:
        return Avaliacao(valor, status="", erro=str(falha))
    criterios, obrigatorio = _criterios(resultado)
    governa = max(criterios, key=lambda nome: criterios[nome], default="")
    return Avaliacao(
        valor,
        resultado.status,
        criterios[governa] if governa else None,
        governa,
        criterios,
        cd.metricas_numericas(resultado.metricas),
        obrigatorio,
    )


class _Avaliador:
    """Guarda o que já rodou: a grade e a bisseção passam pelos mesmos pontos."""

    def __init__(self, caso: Caso, valores: Mapping[str, Any], medida: CotaViva) -> None:
        self.caso = caso
        self.valores = valores
        self.medida = medida
        self.vistos: dict[float, Avaliacao] = {}

    def __call__(self, valor: float) -> Avaliacao:
        chave = int(valor) if self.medida.inteiro else float(valor)
        if chave not in self.vistos:
            novos = cd.com_valor(self.valores, self.medida.alvo, chave)
            self.vistos[chave] = avaliar(self.caso, novos, chave)
        return self.vistos[chave]


# ---------------------------------------------------------------------------
# A faixa que passa
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Trecho:
    """Um pedaço contínuo que passa. Sem corte, o trecho chegou à ponta da faixa estudada."""

    inicio: float
    fim: float
    corta_inicio: bool = False
    corta_fim: bool = False
    trava_inicio: str = ""
    trava_fim: str = ""

    def contem(self, valor: float) -> bool:
        return self.inicio <= valor <= self.fim

    def distancia(self, valor: float) -> float:
        return max(self.inicio - valor, valor - self.fim, 0.0)


@dataclass(frozen=True)
class Opcao:
    """Um valor pronto para usar."""

    rotulo: str
    valor: float
    aproveitamento: float | None
    status: str
    ajuda: str = ""


def faixa_automatica(medida: CotaViva) -> tuple[float, float]:
    """De um oitavo a oito vezes o valor, dentro dos limites do campo."""
    valor = medida.valor
    if valor > 0:
        de, ate = valor / RAZAO_DA_BUSCA, valor * RAZAO_DA_BUSCA
    elif valor < 0:
        de, ate = valor * RAZAO_DA_BUSCA, valor / RAZAO_DA_BUSCA
    else:
        de, ate = 0.0, (medida.passo or 1.0) * 100.0
    if medida.minimo is not None:
        de = max(de, medida.minimo)
    if medida.maximo is not None:
        ate = min(ate, medida.maximo)
    return de, ate


def _grade(de: float, ate: float, inteiro: bool, pontos: int) -> list[float]:
    if ate <= de:
        return [de]
    if inteiro:
        inicio, fim = math.ceil(de), math.floor(ate)
        passo = max(1, math.ceil((fim - inicio) / (pontos - 1)))
        return [*range(inicio, fim + 1, passo), fim]
    if de > 0 or ate < 0:
        razao = (ate / de) ** (1.0 / (pontos - 1))
        return [de * razao**i for i in range(pontos)]
    return [de + (ate - de) * i / (pontos - 1) for i in range(pontos)]


def _fronteira(
    avaliador: _Avaliador,
    ruim: float,
    bom: float,
    teste: Callable[[Avaliacao], bool],
) -> tuple[float, float]:
    """Fecha a troca entre dois pontos. O ``bom`` que volta é um valor que rodou e passou."""
    inteiro = avaliador.medida.inteiro
    for _ in range(PASSOS_DA_BISSECAO):
        if inteiro and abs(bom - ruim) <= 1:
            break
        if not inteiro and abs(bom - ruim) <= TOLERANCIA * max(abs(bom), abs(ruim)):
            break
        meio = (ruim + bom) // 2 if inteiro else (ruim + bom) / 2.0
        if teste(avaliador(meio)):
            bom = meio
        else:
            ruim = meio
    return bom, ruim


def _trechos(
    vistos: Sequence[Avaliacao],
    avaliador: _Avaliador,
    teste: Callable[[Avaliacao], bool],
) -> list[Trecho]:
    trechos: list[Trecho] = []
    aberto: tuple[float, bool, str] | None = None
    if vistos and teste(vistos[0]):
        aberto = (vistos[0].valor, False, "")
    for anterior, seguinte in pairwise(vistos):
        if teste(anterior) == teste(seguinte):
            continue
        if teste(seguinte):
            bom, ruim = _fronteira(avaliador, anterior.valor, seguinte.valor, teste)
            aberto = (bom, True, avaliador(ruim).quem_trava)
        else:
            bom, ruim = _fronteira(avaliador, seguinte.valor, anterior.valor, teste)
            if aberto is not None:
                inicio, corta, trava = aberto
                trechos.append(Trecho(inicio, bom, corta, True, trava, avaliador(ruim).quem_trava))
            aberto = None
    if aberto is not None:
        inicio, corta, trava = aberto
        trechos.append(Trecho(inicio, vistos[-1].valor, corta, False, trava, ""))
    return trechos


def _mais_perto(trechos: Sequence[Trecho], valor: float) -> Trecho | None:
    return min(trechos, key=lambda t: t.distancia(valor), default=None)


def _arredondado(valor: float, subir: bool, algarismos: int) -> float:
    if not valor or not math.isfinite(valor):
        return valor
    casas = algarismos - 1 - math.floor(math.log10(abs(valor)))
    fator = 10.0**casas
    bruto = valor * fator
    # A folga evita que um 73,3 exato suba para 73,4 por causa da conta em binário.
    return round((math.ceil(bruto - 1e-9) if subir else math.floor(bruto + 1e-9)) / fator, 10)


def _valor_limpo(
    avaliador: _Avaliador,
    valor: float,
    subir: bool,
    teste: Callable[[Avaliacao], bool],
) -> Avaliacao:
    """O número curto mais próximo do limite, conferido antes de voltar.

    Tenta primeiro o arredondamento mais próximo: um limite exato de 4,80 chega aqui como 4,8003, e
    subir direto daria 4,81. Se o mais próximo reprovar, vai para o lado que passa.
    """
    if avaliador.medida.inteiro:
        return avaliador(valor)
    for algarismos in (3, 4, 5):
        casas = algarismos - 1 - math.floor(math.log10(abs(valor))) if valor else 0
        for candidato in (round(valor, casas), _arredondado(valor, subir, algarismos)):
            avaliacao = avaliador(candidato)
            if teste(avaliacao):
                return avaliacao
    return avaliador(valor)


def _comercial(
    serie: Serie,
    trecho: Trecho,
    avaliador: _Avaliador,
    teste: Callable[[Avaliacao], bool],
) -> Avaliacao | None:
    """O primeiro valor da série que passa, vindo do lado do limite."""
    candidatos = valores_que_cabem(serie, trecho.inicio, trecho.fim)
    if trecho.corta_fim and not trecho.corta_inicio:
        candidatos.reverse()
    for valor in candidatos[:TENTATIVAS_COMERCIAIS]:
        avaliacao = avaliador(valor)
        if teste(avaliacao):
            return avaliacao
    return None


# ---------------------------------------------------------------------------
# O estudo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Estudo:
    medida: CotaViva
    atual: Avaliacao
    pontos: tuple[Avaliacao, ...]
    trechos: tuple[Trecho, ...]
    limpos: tuple[Trecho, ...]
    opcoes: tuple[Opcao, ...]
    de: float
    ate: float
    so_recomendacoes: bool = False

    @property
    def tem_criterio(self) -> bool:
        return any(a.status in DECISIVOS for a in self.pontos)

    @property
    def util(self) -> Trecho | None:
        """O trecho do valor de agora, ou o mais perto dele."""
        return _mais_perto(self.trechos, self.medida.valor)

    @property
    def atual_passa(self) -> bool:
        return self.atual.sem_ressalva if self.so_recomendacoes else self.atual.passa

    def texto_do_valor(self, valor: float) -> str:
        return f"{cd.numero(valor)} {self.medida.unidade}".rstrip()

    def _opcao(self, rotulo: str) -> Opcao | None:
        return next((o for o in self.opcoes if o.rotulo == rotulo), None)

    def resumo(self) -> str:
        """A resposta em uma frase, com os mesmos números das opções."""
        if not self.tem_criterio:
            return "Este caso não tem critério de aprovação: o estudo só mostra como o número muda."
        faixa = f"de {cd.numero(self.de)} a {self.texto_do_valor(self.ate)}"
        trecho = self.util
        if trecho is None:
            melhor = min(self.pontos, key=_aproveitamento_ou_infinito, default=self.atual)
            motivo = f" Quem trava: {melhor.quem_trava}." if melhor.quem_trava else ""
            return f"Não passa em nenhum valor {faixa}.{motivo}"
        menor = self._opcao(MENOR)
        maior = self._opcao(MAIOR)
        if menor and maior:
            texto = f"Passa de {cd.numero(menor.valor)} a {self.texto_do_valor(maior.valor)}."
        elif menor:
            texto = f"Passa a partir de {self.texto_do_valor(menor.valor)}."
        elif maior:
            texto = f"Passa até {self.texto_do_valor(maior.valor)}."
        else:
            texto = f"Passa em toda a faixa estudada, {faixa}."
        if len(self.trechos) > 1:
            texto += " Há mais de um trecho que passa: veja o gráfico."
        return texto

    def quem_trava(self) -> str:
        trecho = self.util
        if trecho is None:
            return ""
        travas = [t for t in (trecho.trava_inicio, trecho.trava_fim) if t]
        return " · ".join(dict.fromkeys(travas))

    def criterios_que_governam(self, limite: int = 6) -> list[str]:
        """Só quem foi o maior em algum ponto. Um caso pode ter dez linhas, e a maioria nunca manda."""
        contagem: dict[str, int] = {}
        for ponto in self.pontos:
            if ponto.governa:
                contagem[ponto.governa] = contagem.get(ponto.governa, 0) + 1
        return sorted(contagem, key=lambda nome: -contagem[nome])[:limite]

    def para_a_caixinha(self) -> dict[str, Any]:
        """O que a caixinha do desenho mostra: a frase e os valores prontos para usar."""
        return {
            "texto": self.resumo(),
            "opcoes": [
                {
                    "rotulo": opcao.rotulo,
                    "valor": opcao.valor,
                    "texto": _texto_da_opcao(opcao, self.medida),
                }
                for opcao in self.opcoes
            ],
        }


MENOR = "Menor que passa"
MAIOR = "Maior que passa"
COMERCIAL = "Comercial"
SEM_RESSALVA = "Sem ressalvas"


def _aproveitamento_ou_infinito(avaliacao: Avaliacao) -> float:
    return math.inf if avaliacao.aproveitamento is None else avaliacao.aproveitamento


def texto_do_aproveitamento(avaliacao: Avaliacao | Opcao) -> str:
    valor = avaliacao.aproveitamento
    if valor is None:
        return ""
    return "∞" if math.isinf(valor) else f"{valor * 100:.0f} %"


def _texto_da_opcao(opcao: Opcao, medida: CotaViva) -> str:
    texto = f"{cd.numero(opcao.valor)} {medida.unidade}".rstrip()
    aproveitamento = texto_do_aproveitamento(opcao)
    return f"{texto} · {aproveitamento}" if aproveitamento else texto


def _opcao(rotulo: str, avaliacao: Avaliacao, ajuda: str = "") -> Opcao:
    return Opcao(rotulo, avaliacao.valor, avaliacao.aproveitamento, avaliacao.status, ajuda)


def _sem_ressalva(trecho: Trecho, limpo: Trecho | None, avaliador: _Avaliador) -> Opcao | None:
    """O valor limpo mais perto: para baixo se a medida passou da faixa recomendada."""
    if limpo is None:
        return None
    if avaliador.medida.valor > limpo.fim:
        alvo, subir = limpo.fim, False
    elif limpo.corta_inicio and limpo.inicio != trecho.inicio:
        alvo, subir = limpo.inicio, True
    else:
        return None
    sem = _valor_limpo(avaliador, alvo, subir, lambda a: a.sem_ressalva)
    return _opcao(SEM_RESSALVA, sem, "Daqui em diante, nenhuma recomendação fica de fora.")


def _opcoes(
    trecho: Trecho | None,
    limpo: Trecho | None,
    serie: Serie | None,
    avaliador: _Avaliador,
    teste: Callable[[Avaliacao], bool],
) -> list[Opcao]:
    opcoes: list[Opcao] = []
    if trecho is None:
        return opcoes
    if trecho.corta_inicio:
        menor = _valor_limpo(avaliador, trecho.inicio, True, teste)
        opcoes.append(_opcao(MENOR, menor, f"Abaixo disto, quem trava é: {trecho.trava_inicio}"))
    if serie is not None:
        comercial = _comercial(serie, trecho, avaliador, teste)
        if comercial is not None:
            opcoes.append(_opcao(COMERCIAL, comercial, f"{serie.nome}. {serie.fonte}"))
    sem = _sem_ressalva(trecho, limpo, avaliador)
    if sem is not None:
        opcoes.append(sem)
    if trecho.corta_fim:
        maior = _valor_limpo(avaliador, trecho.fim, False, teste)
        opcoes.append(_opcao(MAIOR, maior, f"Acima disto, quem trava é: {trecho.trava_fim}"))
    return opcoes


def estudar(
    caso: Caso,
    valores: Mapping[str, Any],
    medida: CotaViva,
    de: float | None = None,
    ate: float | None = None,
    pontos: int = PONTOS,
) -> Estudo:
    """Roda a medida na faixa, acha as trocas e prepara os valores prontos para usar."""
    auto_de, auto_ate = faixa_automatica(medida)
    inicio = auto_de if de is None else de
    fim = auto_ate if ate is None else ate
    avaliador = _Avaliador(caso, valores, medida)
    atual = avaliador(medida.valor)
    grade = _grade(inicio, fim, medida.inteiro, pontos)
    if inicio <= medida.valor <= fim:
        grade.append(medida.valor)
    vistos = [avaliador(valor) for valor in sorted(set(grade))]

    # Sem critério obrigatório no caso, quem separa é a recomendação.
    so_recomendacoes = not any(a.tem_obrigatorio for a in vistos)
    teste = (lambda a: a.sem_ressalva) if so_recomendacoes else (lambda a: a.passa)
    trechos = _trechos(vistos, avaliador, teste)
    limpos = []
    if not so_recomendacoes and any(a.passa and not a.sem_ressalva for a in vistos):
        limpos = _trechos(vistos, avaliador, lambda a: a.sem_ressalva)
    # Sem critério nenhum, um valor recusado não é um limite de projeto.
    opcoes = (
        _opcoes(
            _mais_perto(trechos, medida.valor),
            _mais_perto(limpos, medida.valor),
            medida.serie,
            avaliador,
            teste,
        )
        if any(a.status in DECISIVOS for a in vistos)
        else []
    )
    na_faixa = [a for a in avaliador.vistos.values() if inicio <= a.valor <= fim]
    return Estudo(
        medida,
        atual,
        tuple(sorted(na_faixa, key=lambda a: a.valor)),
        tuple(trechos),
        tuple(limpos),
        tuple(opcoes),
        inicio,
        fim,
        so_recomendacoes,
    )


# ---------------------------------------------------------------------------
# Qual medida pesa mais
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Peso:
    """Quanto o aproveitamento muda com a medida.

    ``peso`` é adimensional: 2 quer dizer que 1 % a mais na medida dá 2 % a mais de aproveitamento,
    e o sinal diz o sentido. ``melhora`` é o aproveitamento depois de andar no sentido que ajuda.
    """

    medida: CotaViva
    peso: float
    sentido: str
    andou: float
    melhora: float

    @property
    def de_geometria(self) -> bool:
        return e_geometria(self.medida)

    @property
    def influi(self) -> bool:
        return abs(self.peso) >= PESO_DESPREZIVEL

    def texto_do_efeito(self) -> str:
        if not self.influi:
            return "Não muda o aproveitamento de agora"
        passo = f"{cd.numero(abs(self.andou))} {self.medida.unidade}".rstrip()
        if not self.medida.inteiro:
            passo = f"{ANDAR * 100:.0f} %"
        return f"{self.sentido} {passo} leva a {self.melhora * 100:.0f} %"


def e_geometria(medida: CotaViva) -> bool:
    """Medida que se escolhe no projeto. Carga e material pesam, mas costumam vir dados."""
    return medida.unidade in UNIDADES_DE_GEOMETRIA or (medida.inteiro and not medida.unidade)


def _peso(caso: Caso, valores: Mapping[str, Any], medida: CotaViva, base: float) -> Peso | None:
    valor = medida.valor
    if not valor or not math.isfinite(base) or base <= 0:
        return None
    passo = max(1, round(abs(valor) * ANDAR)) if medida.inteiro else abs(valor) * ANDAR
    lados: list[tuple[float, float]] = []
    for sinal in (1, -1):
        novo = valor + sinal * passo
        if (medida.minimo is not None and novo < medida.minimo) or (
            medida.maximo is not None and novo > medida.maximo
        ):
            continue
        andou = avaliar(caso, cd.com_valor(valores, medida.alvo, novo), novo)
        if andou.aproveitamento is not None and math.isfinite(andou.aproveitamento):
            lados.append((novo, andou.aproveitamento))
    if not lados:
        return None
    pares = [(valor, base), *lados] if len(lados) == 1 else lados
    (x_0, u_0), (x_1, u_1) = pares[0], pares[-1]
    peso = (u_1 - u_0) / (x_1 - x_0) * valor / base
    novo, melhora = min(lados, key=lambda lado: lado[1])
    return Peso(medida, peso, "Subir" if novo > valor else "Descer", novo - valor, melhora)


def pesos(
    caso: Caso,
    valores: Mapping[str, Any],
    medidas: Sequence[CotaViva] | None = None,
    base: float | None = None,
) -> list[Peso]:
    """O peso de cada medida, da que mais pesa para a que menos pesa."""
    base = avaliar(caso, valores).aproveitamento if base is None else base
    if base is None:
        return []
    achados = [
        _peso(caso, valores, medida, base)
        for medida in (cd.medidas_do_caso(caso, valores) if medidas is None else medidas)
    ]
    return sorted((p for p in achados if p is not None), key=lambda p: -abs(p.peso))


@dataclass(frozen=True)
class Diagnostico:
    """Quem governa agora e qual medida do desenho mais pesa."""

    avaliacao: Avaliacao
    manda: Peso | None = None

    def texto(self) -> str:
        avaliacao = self.avaliacao
        if not avaliacao.governa:
            return ""
        quem = f"Quem governa: {avaliacao.governa}, {texto_do_aproveitamento(avaliacao)}."
        if self.manda is None:
            return quem
        efeito = self.manda.texto_do_efeito().lower()
        letra = self.manda.medida.letra
        return f"{quem} A medida que mais pesa, em laranja no desenho, é {letra}: {efeito}."


def diagnosticar(caso: Caso, valores: Mapping[str, Any], cotas: Sequence[CotaViva]) -> Diagnostico:
    """A medida em destaque sai só das cotas de geometria: é nelas que dá para mexer no desenho."""
    avaliacao = avaliar(caso, valores)
    if avaliacao.aproveitamento is None:
        return Diagnostico(avaliacao)
    candidatas = [c for c in cotas if e_geometria(c)]
    achados = [p for p in pesos(caso, valores, candidatas, avaliacao.aproveitamento) if p.influi]
    return Diagnostico(avaliacao, achados[0] if achados else None)
