"""Base dos casos do Assistente de cargas: campos, resultado e verificações, sem Streamlit.

Um caso é uma tabela (os campos que o usuário preenche) e uma função pura (``calcular``) que devolve
um :class:`Resultado`. A página monta o formulário e mostra o resultado sem saber nada do caso, e
por isso acrescentar um caso é escrever a função e a sua lista de campos: o campo já nasce com a
ajuda, o teste de fuzz já roda sobre ele e o memorial já recebe a tabela de verificações.

Unidades internas: N, mm e MPa. Cada campo diz a sua unidade de entrada (kN, N·m, kW, rpm, GPa) e a
função do caso faz a conversão.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from core.memorial_verificacoes import decimal_ptbr
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

Valores = Mapping[str, Any]
Grao = float | int | str | bool
Linha = Mapping[str, Grao | None]


@dataclass(frozen=True)
class Coluna:
    """Uma coluna de um campo em forma de tabela (cargas de uma viga, trechos de uma barra).

    ``opcional`` deixa a célula ficar vazia (o fim de uma carga concentrada, por exemplo); o cálculo
    recebe ``None``. Sem ``opcoes``, um ``padrao`` de texto vira célula de texto livre.
    """

    chave: str
    rotulo: str
    ajuda: str
    padrao: Grao | None = 0.0
    unidade: str = ""
    minimo: float | None = None
    maximo: float | None = None
    opcoes: tuple[str, ...] = ()
    opcional: bool = False

    @property
    def rotulo_completo(self) -> str:
        return f"{self.rotulo} ({self.unidade})" if self.unidade else self.rotulo


@dataclass(frozen=True)
class Campo:
    """Um dado de entrada. O tipo do widget sai do tipo de ``padrao``.

    ``float`` vira campo numérico, ``int`` campo inteiro, ``bool`` chave e ``str`` lista de
    ``opcoes``. ``quando`` mostra o campo só se outro campo valer um dos valores dados; escondido,
    ele fica no valor padrão. Limites que dependem de outro campo (diâmetro interno menor que o
    externo) são conferidos no cálculo, com ``ValueError``: limite de widget que muda de valor
    derruba a página quando o número digitado antes sai da nova faixa.

    Com ``colunas`` o campo vira tabela editável e ``padrao`` traz as linhas iniciais.
    ``opcoes_de`` busca a lista na hora de usar, para listas que o usuário aumenta, como o catálogo
    de perfis: a lista não pode ficar congelada no momento em que o programa abriu.
    """

    chave: str
    rotulo: str
    ajuda: str
    padrao: Grao | tuple[Linha, ...]
    unidade: str = ""
    minimo: float | None = None
    maximo: float | None = None
    passo: float | None = None
    opcoes: tuple[str, ...] = ()
    secao: str = ""
    quando: tuple[str, tuple[Grao, ...]] | None = None
    colunas: tuple[Coluna, ...] = ()
    opcoes_de: Callable[[], Sequence[str]] | None = None

    @property
    def rotulo_completo(self) -> str:
        return f"{self.rotulo} ({self.unidade})" if self.unidade else self.rotulo

    @property
    def e_tabela(self) -> bool:
        return bool(self.colunas)

    @property
    def lista_de_opcoes(self) -> tuple[str, ...]:
        return tuple(self.opcoes_de()) if self.opcoes_de else self.opcoes

    def visivel(self, valores: Valores) -> bool:
        if self.quando is None:
            return True
        chave, aceitos = self.quando
        return valores.get(chave) in aceitos


@dataclass(frozen=True)
class Metrica:
    """Um número de destaque do resultado."""

    rotulo: str
    valor: float | str
    unidade: str = ""
    casas: int = 2


@dataclass(frozen=True)
class Ponto:
    """Estado de tensão num ponto da peça. Tração positiva."""

    nome: str
    sigma_x: float
    sigma_y: float = 0.0
    tau_xy: float = 0.0
    sigma_z: float = 0.0

    @property
    def principais(self) -> tuple[float, float, float]:
        """As três tensões principais, em ordem decrescente (σz já é principal aqui)."""
        media = (self.sigma_x + self.sigma_y) / 2.0
        raio = math.hypot((self.sigma_x - self.sigma_y) / 2.0, self.tau_xy)
        s1, s2, s3 = sorted((media + raio, media - raio, self.sigma_z), reverse=True)
        return s1, s2, s3

    @property
    def von_mises(self) -> float:
        s1, s2, s3 = self.principais
        return math.sqrt(((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2) / 2.0)

    @property
    def tresca(self) -> float:
        s1, _, s3 = self.principais
        return s1 - s3


@dataclass(frozen=True)
class Envio:
    """Leva um resultado para outro caso: o usuário clica e o caso abre preenchido."""

    destino: str
    rotulo: str
    valores: Mapping[str, Grao]


@dataclass(frozen=True)
class Tabela:
    titulo: str
    linhas: tuple[Mapping[str, Any], ...]
    legenda: str = ""


@dataclass(frozen=True)
class Grafico:
    """Curvas de um gráfico simples: cada ponto é (x, y, nome da curva).

    ``area`` preenche até o zero, como nos diagramas de cortante e momento, e ``cor`` fixa a cor do
    diagrama. ``destaques`` são os pontos que recebem o valor escrito ao lado, (x, y, texto).
    """

    titulo: str
    rotulo_x: str
    rotulo_y: str
    pontos: tuple[tuple[float, float, str], ...]
    area: bool = False
    cor: str = ""
    destaques: tuple[tuple[float, float, str], ...] = ()


@dataclass(frozen=True)
class Figura:
    """Desenho feito com os valores do cálculo: na tela e no Word, sem precisar de navegador."""

    titulo: str
    png: bytes
    legenda: str = ""


@dataclass(frozen=True)
class Resultado:
    resumo: str
    metricas: tuple[Metrica, ...] = ()
    verificacoes: tuple[Verificacao, ...] = ()
    pontos: tuple[Ponto, ...] = ()
    tabelas: tuple[Tabela, ...] = ()
    graficos: tuple[Grafico, ...] = ()
    figuras: tuple[Figura, ...] = ()
    alertas: tuple[str, ...] = ()
    hipoteses: tuple[str, ...] = ()
    referencias: tuple[str, ...] = ()
    envios: tuple[Envio, ...] = ()
    fadiga: tuple[float, float] | None = None  # σ alternada e σ média nominais, em MPa

    @property
    def status(self) -> str:
        return status_geral(self.verificacoes)

    @property
    def ponto_critico(self) -> Ponto | None:
        return max(self.pontos, key=lambda p: p.von_mises, default=None)


@dataclass(frozen=True)
class Caso:
    """Um caso de análise do Assistente de cargas."""

    id: str
    titulo: str
    grupo: str
    resumo: str
    descricao: str
    campos: tuple[Campo, ...]
    calcular: Callable[[Valores], Resultado]
    formula: str = ""
    entradas_resumo: tuple[str, ...] = field(default=())

    def padroes(self) -> dict[str, Any]:
        return {campo.chave: campo.padrao for campo in self.campos}


def exigir(condicao: bool, mensagem: str) -> None:
    """Dado que o cálculo não aceita: a página mostra a mensagem no lugar do resultado."""
    if not condicao:
        raise ValueError(mensagem)


def _vazia(valor: Any) -> bool:
    """Célula sem nada: ``None``, texto em branco ou o NaN que a tabela da página manda."""
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    return isinstance(valor, float) and math.isnan(valor)


def _conferir_celula(campo: Campo, coluna: Coluna, valor: Any, posicao: int) -> Grao | None:
    nome = f"{campo.rotulo}, linha {posicao}, {coluna.rotulo}"
    if _vazia(valor):
        exigir(coluna.opcional, f"{nome}: preencha este valor.")
        return None
    if coluna.opcoes:
        exigir(valor in coluna.opcoes, f"{nome}: opção desconhecida.")
        return str(valor)
    if isinstance(coluna.padrao, str):
        return str(valor).strip()
    try:
        numero = float(valor)
    except (TypeError, ValueError) as erro:
        raise ValueError(f"{nome}: valor não é um número.") from erro
    exigir(math.isfinite(numero), f"{nome}: valor não é um número.")
    if coluna.minimo is not None:
        exigir(numero >= coluna.minimo, f"{nome}: mínimo {coluna.minimo:g}.")
    if coluna.maximo is not None:
        exigir(numero <= coluna.maximo, f"{nome}: máximo {coluna.maximo:g}.")
    return int(numero) if isinstance(coluna.padrao, int) else numero


def conferir_tabela(campo: Campo, linhas: Sequence[Mapping[str, Any]]) -> tuple[Linha, ...]:
    """Tira as linhas em branco e confere cada célula. A linha conta a partir de 1, como na tela."""
    conferidas: list[Linha] = []
    for posicao, linha in enumerate(linhas, start=1):
        if all(_vazia(linha.get(coluna.chave)) for coluna in campo.colunas):
            continue
        conferidas.append(
            {
                coluna.chave: _conferir_celula(campo, coluna, linha.get(coluna.chave), posicao)
                for coluna in campo.colunas
            }
        )
    return tuple(conferidas)


def _conferir_valores(caso: Caso, valores: Valores) -> dict[str, Any]:
    completos: dict[str, Any] = caso.padroes()
    for campo in caso.campos:
        if campo.chave not in valores or not campo.visivel({**completos, **valores}):
            continue
        valor = valores[campo.chave]
        if campo.e_tabela:
            completos[campo.chave] = conferir_tabela(campo, valor)
        elif isinstance(campo.padrao, bool):
            completos[campo.chave] = bool(valor)
        elif isinstance(campo.padrao, str):
            exigir(valor in campo.lista_de_opcoes, f"{campo.rotulo}: opção desconhecida.")
            completos[campo.chave] = str(valor)
        else:
            numero = float(valor)
            exigir(math.isfinite(numero), f"{campo.rotulo}: valor não é um número.")
            if campo.minimo is not None:
                exigir(numero >= campo.minimo, f"{campo.rotulo}: mínimo {campo.minimo:g}.")
            if campo.maximo is not None:
                exigir(numero <= campo.maximo, f"{campo.rotulo}: máximo {campo.maximo:g}.")
            completos[campo.chave] = int(numero) if isinstance(campo.padrao, int) else numero
    return completos


def calcular_caso(caso: Caso, valores: Valores | None = None) -> Resultado:
    """Completa os campos que faltam com o padrão, confere a faixa e roda o caso."""
    return caso.calcular(_conferir_valores(caso, valores or {}))


# ---------------------------------------------------------------------------
# Linhas da tabela de verificações
# ---------------------------------------------------------------------------


def limite(
    nome: str,
    solicitante: float,
    resistente: float,
    unidade: str,
    formula: str,
    referencia: str,
) -> Verificacao:
    """Critério obrigatório: o solicitante não pode passar do limite."""
    return Verificacao(nome, solicitante, resistente, unidade, referencia, formula)


def minimo(
    nome: str,
    obtido: float,
    exigido: float,
    unidade: str,
    formula: str,
    referencia: str,
) -> Verificacao:
    """Critério obrigatório ao contrário: o valor obtido não pode ficar abaixo do exigido.

    O exigido entra como solicitante e o obtido como resistente, e assim o aproveitamento tem a
    mesma leitura de todas as outras linhas: acima de 100 % reprova.
    """
    return Verificacao(nome, exigido, obtido, unidade, referencia, formula)


def recomendacao(
    nome: str,
    solicitante: float,
    resistente: float,
    unidade: str,
    formula: str,
    referencia: str,
) -> Verificacao:
    """Boa prática: passar do limite não reprova, mas pede atenção (``ALERTA``)."""
    aproveitamento = solicitante / resistente if resistente > 0 else math.inf
    return Verificacao(
        nome,
        solicitante,
        resistente,
        unidade,
        referencia,
        formula,
        status="OK" if aproveitamento <= 1.0 + 1e-9 else "ALERTA",
        aproveitamento=aproveitamento,
        obrigatoria=False,
    )


def recomendacao_minima(
    nome: str,
    obtido: float,
    exigido: float,
    unidade: str,
    formula: str,
    referencia: str,
) -> Verificacao:
    return recomendacao(nome, exigido, obtido, unidade, formula, referencia)


def faixa_recomendada(
    nome: str,
    valor: float,
    inferior: float,
    superior: float,
    unidade: str,
    formula: str,
    referencia: str,
) -> Verificacao:
    """Boa prática de faixa: dentro é OK e fora pede atenção. O aproveitamento não se aplica."""
    dentro = inferior <= valor <= superior
    return Verificacao(
        nome,
        valor,
        superior if valor >= inferior else inferior,
        unidade,
        referencia,
        formula or f"faixa usual {inferior:g} a {superior:g}",
        status="OK" if dentro else "ALERTA",
        tipo="limite",
        obrigatoria=False,
    )


def informativo(
    nome: str, valor: float, unidade: str, formula: str, referencia: str
) -> Verificacao:
    return Verificacao(
        nome, valor, None, unidade, referencia, formula, status="INFO", tipo="informativo"
    )


# ---------------------------------------------------------------------------
# Registro técnico (memorial)
# ---------------------------------------------------------------------------


def _valor_json(valor: Any) -> Any:
    if isinstance(valor, float):
        return numero_json(valor, 4)
    return valor


def _linha_json(linha: Mapping[str, Any]) -> dict[str, Any]:
    return {str(chave): _valor_json(valor) for chave, valor in linha.items()}


def _texto_da_celula(valor: Any) -> str:
    if isinstance(valor, float):
        return decimal_ptbr(f"{valor:g}")
    return str(valor)


def texto_da_tabela(campo: Campo, linhas: Sequence[Linha]) -> str:
    """Uma tabela em uma frase, para o registro: o memorial mostra cada entrada numa célula."""
    return "; ".join(
        ", ".join(
            f"{coluna.rotulo_completo}: {_texto_da_celula(linha.get(coluna.chave))}"
            for coluna in campo.colunas
            if linha.get(coluna.chave) is not None
        )
        for linha in linhas
    )


def entradas_legiveis(caso: Caso, valores: Valores) -> dict[str, Any]:
    """Os dados do caso com rótulo e unidade, sem os campos escondidos e sem as tabelas."""
    completos = {**caso.padroes(), **valores}
    return {
        campo.rotulo_completo: completos[campo.chave]
        for campo in caso.campos
        if campo.visivel(completos) and not campo.e_tabela
    }


def tabelas_de_entrada(caso: Caso, valores: Valores) -> dict[str, tuple[Campo, tuple[Linha, ...]]]:
    """Os campos em forma de tabela que estavam à vista, com as linhas preenchidas."""
    completos = {**caso.padroes(), **valores}
    return {
        campo.rotulo: (campo, tuple(completos[campo.chave]))
        for campo in caso.campos
        if campo.e_tabela and campo.visivel(completos)
    }


def dados_do_registro(
    caso: Caso, valores: Valores, resultado: Resultado, *, modulo: str, modulo_id: str
) -> dict[str, Any]:
    """Argumentos de ``construir_registro_tecnico`` para o caso calculado.

    Fica aqui, e não na página, para o teste percorrer todos os casos e garantir que nenhum registro
    leva NaN ou infinito: o hash do registro os recusa.
    """
    verificacoes = list(resultado.verificacoes)
    resultados: dict[str, Any] = {
        "caso": caso.titulo,
        "verificações": linhas_para_registro(verificacoes),
    }
    for metrica in resultado.metricas:
        nome = f"{metrica.rotulo} ({metrica.unidade})" if metrica.unidade else metrica.rotulo
        resultados[nome] = _valor_json(metrica.valor)
    critico = resultado.ponto_critico
    if critico is not None:
        # As mesmas chaves que o módulo sempre registrou, agora do ponto crítico.
        resultados["sigma_x_MPa"] = numero_json(critico.sigma_x)
        resultados["sigma_y_MPa"] = numero_json(critico.sigma_y)
        resultados["tau_xy_MPa"] = numero_json(critico.tau_xy)
        resultados["pontos_de_tensao"] = [
            {
                "ponto": ponto.nome,
                "sigma_x_MPa": numero_json(ponto.sigma_x),
                "sigma_y_MPa": numero_json(ponto.sigma_y),
                "sigma_z_MPa": numero_json(ponto.sigma_z),
                "tau_xy_MPa": numero_json(ponto.tau_xy),
                "von_mises_MPa": numero_json(ponto.von_mises),
            }
            for ponto in resultado.pontos
        ]
    for tabela in resultado.tabelas:
        resultados[tabela.titulo] = [_linha_json(linha) for linha in tabela.linhas]
    status = STATUS_REGISTRO.get(resultado.status, "Pendente")
    return {
        "modulo": modulo,
        "modulo_id": modulo_id,
        "titulo": f"{modulo} — {caso.titulo}",
        "status": status if verificacoes else "Calculado",
        "resumo": decimal_ptbr(resultado.resumo),
        "entradas": {
            "caso": caso.titulo,
            **entradas_legiveis(caso, valores),
            **{
                rotulo: texto_da_tabela(campo, linhas)
                for rotulo, (campo, linhas) in tabelas_de_entrada(caso, valores).items()
            },
        },
        "resultados": resultados,
        "premissas": list(resultado.hipoteses),
        "alertas": list(resultado.alertas),
        "referencias": list(resultado.referencias),
        "equacoes": [caso.formula] if caso.formula else [],
        "conclusao": decimal_ptbr(resultado.resumo),
    }


def ordenar_por_severidade(verificacoes: Sequence[Verificacao]) -> list[Verificacao]:
    """Na tela, o que reprovou vem primeiro; o resto segue pelo aproveitamento."""
    peso = {"NÃO OK": 0, "ALERTA": 1, "OK": 2, "INFO": 3, "N/A": 4}
    return sorted(verificacoes, key=lambda v: (peso.get(v.status, 5), -(v.aproveitamento or 0.0)))
