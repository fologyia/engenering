"""O arquivo do gerenciador de casos de carga do SolidWorks Simulation (CSV).

O gerenciador salva e carrega os dados de entrada num CSV separado por vírgula ("Salvar os dados em
um arquivo .csv externo" e "Carregar os dados de entrada de um arquivo .csv externo")::

    Tipo de carga,3,3,3,3,3,3,4,4,4,1
    Nome da carga:,Força-1,Força-1,Força-1,Força-1,Força-1,Força-1,Gravidade-1,…,Pressão-1
    Valor de:,Ao longo da face dir 1,Ao longo da face dir 2,Normal ao plano,…,Valor da pressão
    Valores originais/iniciais:,Suprimir (N),Suprimir (N),-700 N,Suprimir (N.m),…,5000 N/m^2
    PP,Suprimir,Suprimir,Suprimir,Suprimir,Suprimir,Suprimir,-9.81,Suprimir,Suprimir,Suprimir
    Combinações de casos de carga
    C01-ELU, 1.25*"PP" + 1.5*"SC"

Uma coluna por componente de cada carga: a força (tipo 3) tem seis — três de força e três de
momento, em relação a um plano —, a gravidade (tipo 4) três e a pressão (tipo 1) uma. A linha dos
valores originais traz a unidade de cada carga; os casos vão sem unidade, com ponto decimal, e
"Suprimir" desliga a componente no caso. O arquivo é do Windows (cp1252), com CRLF e sem aspas.

Este módulo:

* monta o arquivo a partir do plano de cargas (:func:`do_plano`), para quem cria as cargas no
  estudo com os nomes, os planos e os valores da aba "Cargas do estudo";
* lê o arquivo salvo pelo SolidWorks (:func:`ler`) e o preenche com os casos e as combinações do
  plano (:func:`preencher`) — o caminho mais seguro, porque o cabeçalho é o do próprio SolidWorks.
  Cada carga do estudo é ligada à do plano pelo nome; o valor e o sentido com que ela foi criada
  são conferidos, e o que difere do plano vira aviso.

Os valores são característicos: as combinações vão no arquivo só para ver no SolidWorks — o
programa importa os casos primários e combina pela NBR 8800.

Sem Streamlit.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from core import esforcos_modelo as em
from core import exportacao_cargas as ex
from core import plano_de_cargas as pc

MACRO_DOS_CASOS = (
    Path(__file__).resolve().parent.parent / "macros_solidworks" / "exportar_casos_de_carga.bas"
)


def macro_dos_casos_de_carga() -> bytes:
    """A macro do SolidWorks que exporta os resultados de cada caso primário do gerenciador.

    Para cada caso: ``<estudo>-<caso>-forcas.csv`` (o formato do "Listar forças da viga", elemento
    a elemento) e ``<estudo>-<caso>-reacoes.csv`` (o do "Listar forças resultantes"), com
    "Caso de carga: <caso>" no cabeçalho — o que :func:`core.esforcos_modelo.ler_arquivo` lê —, e o
    quadro dos sensores da Vista de resultados. Texto ASCII com CRLF, para colar no editor do VBA.
    """
    texto = MACRO_DOS_CASOS.read_text(encoding="ascii")
    return texto.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii")


ROTULOS = ("Tipo de carga", "Nome da carga:", "Valor de:", "Valores originais/iniciais:")
ROTULO_COMBINACOES = "Combinações de casos de carga"
SUPRIMIR = ex.SUPRIMIR

TIPO_PRESSAO = "1"
TIPO_FORCA = "3"
TIPO_GRAVIDADE = "4"

DIR_1 = "Ao longo da face dir 1"
DIR_2 = "Ao longo da face dir 2"
NORMAL = ex.NORMAL_AO_PLANO

FORCA = "força"
MOMENTO = "momento"
POR_METRO = "força por metro"
PRESSAO = "pressão"
ACELERACAO = "aceleração"
TEMPERATURA = "temperatura"

#: Unidade como o SolidWorks escreve (sem espaços, minúscula) → (fator para N e m, grandeza).
_UNIDADES: dict[str, tuple[float, str]] = {
    "n": (1.0, FORCA),
    "kn": (1e3, FORCA),
    "lbf": (4.4482216152605, FORCA),
    "n.m": (1.0, MOMENTO),
    "n.mm": (1e-3, MOMENTO),
    "kn.m": (1e3, MOMENTO),
    "lbf.in": (0.1129848290276167, MOMENTO),
    "lbf.ft": (1.3558179483314004, MOMENTO),
    "n/m": (1.0, POR_METRO),
    "n/mm": (1e3, POR_METRO),
    "kn/m": (1e3, POR_METRO),
    "lbf/in": (175.12683524647636, POR_METRO),
    "n/m^2": (1.0, PRESSAO),
    "n/m2": (1.0, PRESSAO),
    "pa": (1.0, PRESSAO),
    "kpa": (1e3, PRESSAO),
    "kn/m^2": (1e3, PRESSAO),
    "n/mm^2": (1e6, PRESSAO),
    "n/mm2": (1e6, PRESSAO),
    "mpa": (1e6, PRESSAO),
    "psi": (6894.757293168361, PRESSAO),
    "lbf/in^2": (6894.757293168361, PRESSAO),
    "m/s^2": (1.0, ACELERACAO),
    "mm/s^2": (1e-3, ACELERACAO),
    "in/s^2": (0.0254, ACELERACAO),
    "ft/s^2": (0.3048, ACELERACAO),
    "k": (1.0, TEMPERATURA),
    "kelvin": (1.0, TEMPERATURA),
    "c": (1.0, TEMPERATURA),
    "°c": (1.0, TEMPERATURA),
    "celsius": (1.0, TEMPERATURA),
    "f": (1.0, TEMPERATURA),
    "°f": (1.0, TEMPERATURA),
    "fahrenheit": (1.0, TEMPERATURA),
}
#: A grandeza de cada unidade do plano de cargas em N e m.
_GRANDEZA_DO_PLANO = {
    "N": FORCA,
    "N·m": MOMENTO,
    "N/m": POR_METRO,
    "N/m² (Pa)": PRESSAO,
    "m/s²": ACELERACAO,
    "°C": TEMPERATURA,
}


def _chave_da_unidade(unidade: str) -> str:
    return em._normal(unidade).replace("·", ".").replace("²", "^2")


def grandeza(unidade: str) -> str:
    """ "força", "pressão"… da unidade escrita pelo SolidWorks ("" se não reconhecida)."""
    return _UNIDADES.get(_chave_da_unidade(unidade), (0.0, ""))[1]


def _br(valor: float) -> str:
    return f"{valor:.6g}".replace(".", ",")


def numero_sw(valor: float) -> str:
    """O número como o SolidWorks escreve: ponto decimal, sem zeros sobrando (−9.81, 5000)."""
    texto = f"{valor:.9g}"
    if "e" in texto:
        texto = f"{valor:.12f}".rstrip("0").rstrip(".")
    return "0" if texto in ("-0", "", "-") else texto


# ---------------------------------------------------------------------------------------------
# O arquivo
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Coluna:
    """Uma componente de uma carga do estudo (uma coluna do arquivo)."""

    tipo: str  # o código do SolidWorks: "3" força, "4" gravidade, "1" pressão…
    carga: str  # o nome da carga no estudo (Força-1, PP…)
    componente: str  # "Normal ao plano", "Ao longo da face dir 1", "Valor da pressão"…
    original: str  # como está na linha dos valores originais ("-700 N", "Suprimir (N)")
    valor_original: float | None  # None quando a componente foi criada suprimida
    unidade: str  # "N", "N.m", "m/s^2", "N/m^2"…


@dataclass(frozen=True)
class ArquivoDoGerenciador:
    colunas: tuple[Coluna, ...]
    casos: tuple[tuple[str, tuple[str, ...]], ...]  # (nome do caso, célula de cada coluna)
    combinacoes: tuple[tuple[str, str], ...] = ()  # (nome, expressão)
    rotulos: tuple[str, ...] = ROTULOS
    rotulo_combinacoes: str = ROTULO_COMBINACOES

    def cargas(self) -> dict[str, list[int]]:
        """O nome de cada carga e as colunas dela, na ordem do arquivo."""
        grupos: dict[str, list[int]] = {}
        for indice, coluna in enumerate(self.colunas):
            grupos.setdefault(coluna.carga, []).append(indice)
        return grupos


def _campo(texto: object) -> str:
    """O SolidWorks não usa aspas: a vírgula e a quebra de linha não podem ir dentro de um campo."""
    return str(texto).replace(",", " ").replace("\r", " ").replace("\n", " ").strip()


def csv_do_gerenciador(arquivo: ArquivoDoGerenciador) -> bytes:
    """O CSV no formato que o gerenciador de casos de carga carrega (cp1252, vírgula, CRLF)."""
    cabecalho = (
        [c.tipo for c in arquivo.colunas],
        [c.carga for c in arquivo.colunas],
        [c.componente for c in arquivo.colunas],
        [c.original for c in arquivo.colunas],
    )
    linhas = [
        ",".join(_campo(t) for t in (rotulo, *campos))
        for rotulo, campos in zip(arquivo.rotulos, cabecalho, strict=True)
    ]
    linhas += [",".join(_campo(t) for t in (nome, *celulas)) for nome, celulas in arquivo.casos]
    if arquivo.combinacoes:
        linhas.append(_campo(arquivo.rotulo_combinacoes))
        linhas += [
            f"{_campo(nome)}, {expressao.strip()}" for nome, expressao in arquivo.combinacoes
        ]
    return "\r\n".join(linhas).encode("cp1252", errors="replace")


_SUPRIMIDA = re.compile(r"\s*(?:suprimir|suppress\w*)\s*(?:\((?P<u>[^)]*)\))?\s*", re.IGNORECASE)
_COM_VALOR = re.compile(r"\s*(?P<v>[-+]?\d[\d.,]*(?:[eE][-+]?\d+)?)\s*(?P<u>.*?)\s*")


def _valor_e_unidade(texto: str, decimal_virgula: bool) -> tuple[float | None, str]:
    if achado := _SUPRIMIDA.fullmatch(texto):
        return None, (achado.group("u") or "").strip()
    if achado := _COM_VALOR.fullmatch(texto):
        return em.numero(achado.group("v"), decimal_virgula=decimal_virgula), achado.group("u")
    return None, ""


def e_do_gerenciador(conteudo: bytes) -> bool:
    """O arquivo começa com a linha "Tipo de carga" do gerenciador de casos de carga?"""
    texto = em._decodificar(conteudo[:600]).lstrip()
    return em._normal(texto.split("\n", 1)[0]).startswith(("tipodecarga", "loadtype"))


def ler(conteudo: bytes) -> ArquivoDoGerenciador:
    """Lê o CSV salvo pelo gerenciador (também o reaberto e salvo no Excel, com ";")."""
    linhas = [linha for linha in em._decodificar(conteudo).splitlines() if linha.strip()]
    if len(linhas) < 4 or not e_do_gerenciador(linhas[0].encode("utf-8")):
        raise em.ArquivoInvalido(
            "Este não é o arquivo do gerenciador de casos de carga. No SolidWorks, abra o "
            "Gerenciador de casos de carga e use “Salvar os dados em um arquivo .csv externo”."
        )
    sep = ";" if linhas[0].count(";") > linhas[0].count(",") else ","
    decimal_virgula = sep == ";"
    cabecalho = [next(csv.reader([linha], delimiter=sep)) for linha in linhas[:4]]
    tipos = cabecalho[0]
    while len(tipos) > 1 and not tipos[-1].strip():
        tipos = tipos[:-1]
    total = len(tipos) - 1
    if total < 1:
        raise em.ArquivoInvalido("O arquivo do gerenciador não tem nenhuma carga.")

    def campo(linha: Sequence[str], indice: int) -> str:
        return linha[indice].strip() if indice < len(linha) else ""

    colunas = []
    for i in range(1, total + 1):
        original = campo(cabecalho[3], i)
        valor, unidade = _valor_e_unidade(original, decimal_virgula)
        colunas.append(
            Coluna(
                campo(cabecalho[0], i),
                campo(cabecalho[1], i),
                campo(cabecalho[2], i),
                original,
                valor,
                unidade,
            )
        )
    casos: list[tuple[str, tuple[str, ...]]] = []
    combinacoes: list[tuple[str, str]] = []
    rotulo_combinacoes = ROTULO_COMBINACOES
    nas_combinacoes = False
    for linha in linhas[4:]:
        primeiro = linha.split(sep, 1)[0].strip().strip('"')
        if not nas_combinacoes and em._normal(primeiro).startswith(
            ("combinacoesdecasos", "loadcasecombination")
        ):
            nas_combinacoes, rotulo_combinacoes = True, primeiro
            continue
        if nas_combinacoes:
            if sep in linha:
                nome, expressao = linha.split(sep, 1)
                expressao = expressao.strip()
                if (
                    len(expressao) > 1
                    and expressao[0] == expressao[-1] == '"'
                    and '""' in expressao
                ):
                    expressao = expressao[1:-1].replace('""', '"')  # salvo de novo pelo Excel
                combinacoes.append((nome.strip().strip('"'), expressao))
            continue
        campos = next(csv.reader([linha], delimiter=sep))
        if campos and campos[0].strip():
            casos.append((campos[0].strip(), tuple(campo(campos, i) for i in range(1, total + 1))))
    return ArquivoDoGerenciador(
        tuple(colunas),
        tuple(casos),
        tuple(combinacoes),
        tuple(campo(linha, 0) for linha in cabecalho),
        rotulo_combinacoes,
    )


# ---------------------------------------------------------------------------------------------
# Do plano de cargas
# ---------------------------------------------------------------------------------------------
_UNIDADE_SW = {"N": "N", "N·m": "N.m", "N/m": "N/m", "N/m² (Pa)": "N/m^2", "m/s²": "m/s^2"}


def _componente(
    tipo: str, carga: str, componente: str, unidade: str, valor: float | None = None
) -> Coluna:
    original = f"{SUPRIMIR} ({unidade})" if valor is None else f"{numero_sw(valor)} {unidade}"
    return Coluna(tipo, carga, componente, original, valor, unidade)


def _colunas_da_carga(carga: ex.CargaDoEstudo) -> tuple[list[Coluna], int, str]:
    """As colunas de uma carga do plano, a que leva o valor e, se ficar de fora, o porquê."""
    valor = carga.valor_ao_criar
    if carga.tipo == ex.TIPO_GRAVIDADE and carga.eixo:
        return (
            [
                _componente(TIPO_GRAVIDADE, carga.nome, NORMAL, "m/s^2", valor),
                _componente(TIPO_GRAVIDADE, carga.nome, DIR_2, "m/s^2", 0.0),
                _componente(TIPO_GRAVIDADE, carga.nome, DIR_1, "m/s^2", 0.0),
            ],
            0,
            "",
        )
    if carga.tipo == ex.TIPO_AREA:
        return (
            [_componente(TIPO_PRESSAO, carga.nome, ex.VALOR_DA_PRESSAO, "N/m^2", valor)],
            0,
            "",
        )
    if carga.tipo in (ex.TIPO_NODAL, ex.TIPO_LINHA, ex.TIPO_MOMENTO) and carga.eixo:
        momento = carga.tipo == ex.TIPO_MOMENTO
        forca = _UNIDADE_SW.get(carga.unidade, carga.unidade) if not momento else "N"
        return (
            [
                _componente(TIPO_FORCA, carga.nome, DIR_1, forca),
                _componente(TIPO_FORCA, carga.nome, DIR_2, forca),
                _componente(TIPO_FORCA, carga.nome, NORMAL, forca, None if momento else valor),
                _componente(TIPO_FORCA, carga.nome, DIR_1, "N.m"),
                _componente(TIPO_FORCA, carga.nome, DIR_2, "N.m"),
                _componente(TIPO_FORCA, carga.nome, NORMAL, "N.m", valor if momento else None),
            ],
            5 if momento else 2,
            "",
        )
    if carga.tipo == ex.TIPO_TEMPERATURA:
        motivo = (
            "temperatura — no SolidWorks a carga é a temperatura aplicada (a de referência do "
            "estudo + ΔT): crie e preencha à mão no gerenciador"
        )
    else:
        motivo = f"carga em mais de um eixo ({carga.referencia}) — no plano, uma carga por eixo"
    return [], 0, f"{carga.nome} ({carga.onde}) ficou de fora: {motivo}."


def _casos_e_combinacoes(
    plano: pc.PlanoDeCargas,
    estados: Sequence[str],
    cenario: ex.CenarioDeCarga,
    total: int,
    ligacoes: dict[int, tuple[int, float]],
    manter: dict[int, tuple[str, bool]] | None = None,
    anteriores: dict[str, tuple[str, ...]] | None = None,
) -> tuple[list[tuple[str, tuple[str, ...]]], list[tuple[str, str]], list[str]]:
    """As linhas dos casos primários e as combinações do plano.

    ``ligacoes``: número da carga do plano → (coluna que leva o valor, fator do valor em N e m para
    a unidade e o sinal da carga no SolidWorks). ``manter``: coluna que o programa não preenche →
    (célula quando o SolidWorks não tem o caso, se é carga); ela recebe a célula do caso de mesmo
    nome que já estava no SolidWorks (``anteriores``, pelo nome normalizado). Um caso sem nenhuma
    carga no estudo fica de fora (não tem o que calcular), e as combinações saem sem ele.
    """
    manter = manter or {}
    anteriores = anteriores or {}
    casos: list[tuple[str, tuple[str, ...]]] = []
    presentes: set[str] = set()
    vazios: list[str] = []
    for codigo, _ in cenario.casos:
        nome = ex.nome_no_solidworks(codigo)
        anterior = anteriores.get(em._normal(nome), ())
        celulas = [SUPRIMIR] * total
        for i, (sem_caso, _) in manter.items():
            celulas[i] = anterior[i] if i < len(anterior) else sem_caso
        for numero, (indice, fator) in ligacoes.items():
            valor = cenario.valores.get((codigo, numero))
            if valor is not None:
                celulas[indice] = numero_sw(valor * fator)
        cargas = [indice for indice, _ in ligacoes.values()]
        cargas += [i for i, (_, e_carga) in manter.items() if e_carga]
        if any(celulas[i] not in (SUPRIMIR, "") for i in cargas):
            casos.append((nome, tuple(celulas)))
            presentes.add(codigo)
        else:
            vazios.append(nome)
    lista = pc.combinacoes(plano, estados)
    combinacoes = []
    for c in lista:
        termos = [
            (codigo, fator)
            for codigo in plano.codigos
            if codigo in presentes and abs(fator := float(c.fatores.get(codigo, 0.0))) > 1e-12
        ]
        if termos:
            combinacoes.append(
                (ex.nome_da_combinacao(c, len(lista)), ex.expressao_da_combinacao(termos))
            )
    avisos: list[str] = []
    if vazios:
        avisos.append(
            f"Casos sem nenhuma carga no estudo ficaram de fora do arquivo: {', '.join(vazios)}. "
            "As combinações no SolidWorks saem sem eles (as do programa continuam completas)."
        )
    return casos, combinacoes, avisos


def do_plano(
    plano: pc.PlanoDeCargas, eixos: str, estados: Sequence[str]
) -> tuple[ArquivoDoGerenciador, list[str]]:
    """O arquivo do gerenciador montado do plano, em N e m, e o que ficou de fora.

    Vale para as cargas criadas no estudo como diz a aba "Cargas do estudo": na mesma ordem (os
    nomes Gravidade-1, Força-1, Pressão-1… batem), com o plano de referência do eixo e o valor com
    sinal em "Normal ao plano".
    """
    cenario = ex.cenario_de_carga(plano, ex.UNIDADES_N_M, eixos, estados)
    colunas: list[Coluna] = []
    ligacoes: dict[int, tuple[int, float]] = {}
    avisos: list[str] = []
    for carga in cenario.cargas:
        novas, alvo, motivo = _colunas_da_carga(carga)
        if motivo:
            avisos.append(motivo)
            continue
        ligacoes[carga.numero] = (len(colunas) + alvo, 1.0)
        colunas.extend(novas)
    casos, combinacoes, avisos_dos_casos = _casos_e_combinacoes(
        plano, estados, cenario, len(colunas), ligacoes
    )
    arquivo = ArquivoDoGerenciador(tuple(colunas), tuple(casos), tuple(combinacoes))
    return arquivo, avisos + avisos_dos_casos


# ---------------------------------------------------------------------------------------------
# Preencher o arquivo salvo pelo SolidWorks
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Ligacao:
    """Uma carga do estudo no SolidWorks e a carga do plano que ela recebe."""

    carga_sw: str
    carga_plano: str  # o título da carga do plano; "" quando não há
    componente: str  # a coluna que leva o valor ("Normal ao plano (N)")
    situacao: str


@dataclass(frozen=True)
class Preenchimento:
    arquivo: ArquivoDoGerenciador
    ligacoes: tuple[Ligacao, ...]
    avisos: tuple[str, ...]
    #: (caso, carga › componente, no SolidWorks, no arquivo preenchido) dos casos que já existiam.
    diferencas: tuple[tuple[str, str, str, str], ...]

    @property
    def ligadas(self) -> int:
        return sum(1 for ligacao in self.ligacoes if ligacao.carga_plano)


def _correspondencia(
    grupos: Sequence[str], cenario: ex.CenarioDeCarga
) -> dict[str, ex.CargaDoEstudo]:
    """Carga do SolidWorks → carga do plano: pelo nome (Força-1) ou, quando a carga foi chamada pelo
    código do caso (PP, SC), pela única carga do plano que só esse caso usa."""
    por_nome = {em._normal(carga.nome): carga for carga in cenario.cargas}
    escolha: dict[str, ex.CargaDoEstudo] = {}
    usadas: set[int] = set()
    for nome in grupos:
        carga = por_nome.get(em._normal(nome))
        if carga is not None and carga.numero not in usadas:
            escolha[nome] = carga
            usadas.add(carga.numero)
    casos_da_carga: dict[int, set[str]] = {}
    for caso, numero in cenario.valores:
        casos_da_carga.setdefault(numero, set()).add(caso)
    for nome in grupos:
        if nome in escolha:
            continue
        codigos = [
            codigo
            for codigo, _ in cenario.casos
            if em._normal(ex.nome_no_solidworks(codigo)) == em._normal(nome)
        ]
        if len(codigos) != 1:
            continue
        so_deste = [
            carga
            for carga in cenario.cargas
            if carga.numero not in usadas and casos_da_carga.get(carga.numero) == {codigos[0]}
        ]
        if len(so_deste) == 1:
            escolha[nome] = so_deste[0]
            usadas.add(so_deste[0].numero)
    return escolha


def _ligar(
    carga: ex.CargaDoEstudo, colunas: Sequence[Coluna]
) -> tuple[int | None, float, str, list[str]]:
    """A coluna que leva o valor, o fator (N e m → unidade e sinal do SolidWorks), a situação e os
    avisos de uma carga do estudo ligada a uma carga do plano."""
    if carga.tipo == ex.TIPO_TEMPERATURA:
        return (
            None,
            1.0,
            "temperatura: vale o que está no SolidWorks",
            [
                f"{carga.nome}: a temperatura fica como está no SolidWorks — lá a carga é a "
                "temperatura aplicada (a de referência do estudo + ΔT); preencha os casos à mão."
            ],
        )
    esperada = _GRANDEZA_DO_PLANO.get(carga.unidade, "")
    candidatas = [
        (k, coluna)
        for k, coluna in enumerate(colunas)
        if coluna.valor_original not in (None, 0.0) and grandeza(coluna.unidade) == esperada
    ]
    if not candidatas:
        unidades = sorted({c.unidade for c in colunas if c.unidade})
        por_item = esperada == POR_METRO and any(
            c.valor_original not in (None, 0.0) and grandeza(c.unidade) == FORCA for c in colunas
        )
        if por_item:
            return (
                None,
                1.0,
                "criada em N (“por item”), o plano tem carga por metro",
                [
                    f"{carga.nome}: no SolidWorks a força nas vigas foi criada em N — “por item”, o "
                    "valor vai inteiro em cada viga selecionada. Para a carga distribuída do plano "
                    f"({_br(carga.valor_ao_criar)} {carga.unidade}), marque “por unidade de "
                    "comprimento” e salve o arquivo do gerenciador de novo."
                ],
            )
        return (
            None,
            1.0,
            f"nenhuma componente em {esperada} ligada no SolidWorks"
            + (f" (unidades: {', '.join(unidades)})" if unidades else ""),
            [
                f"{carga.nome}: crie a carga com o valor da aba Cargas do estudo "
                f"({_br(carga.valor_ao_criar)} {carga.unidade}, {carga.referencia})."
            ],
        )
    if len(candidatas) > 1:
        return (
            None,
            1.0,
            "mais de uma componente ligada",
            [
                f"{carga.nome}: no SolidWorks há mais de uma componente com valor "
                f"({', '.join(c.componente for _, c in candidatas)}); deixe só a do plano "
                f"({carga.referencia})."
            ],
        )
    indice, coluna = candidatas[0]
    fator_si = _UNIDADES[_chave_da_unidade(coluna.unidade)][0]
    no_sw = float(coluna.valor_original or 0.0) * fator_si
    plano = carga.valor_ao_criar
    sinal = -1.0 if no_sw * plano < 0 else 1.0
    situacao = "ligada"
    avisos: list[str] = []
    if plano and abs(abs(no_sw / plano) - 1.0) > 0.02:
        situacao = "ligada; valor ao criar diferente do plano"
        texto = (
            f"{carga.nome}: criada no SolidWorks com {_br(coluna.valor_original or 0.0)} "
            f"{coluna.unidade}, mas o plano tem {_br(plano / fator_si)} {coluna.unidade}. O "
            "arquivo preenchido leva o valor do plano."
        )
        if carga.tipo == ex.TIPO_GRAVIDADE:
            texto += (
                " Se a diferença é o peso das ligações, chapas e parafusos que não estão no "
                "modelo, ponha o acréscimo na página Cargas do esqueleto — ele vai para o plano."
            )
        avisos.append(texto)
    if sinal < 0:
        situacao += "; sinal trocado"
        avisos.append(
            f"{carga.nome}: criada com o sinal oposto ao do plano. O programa considera que a "
            "seta no SolidWorks está no sentido certo (com “Inverter direção”) e troca o sinal "
            f"dos casos — confira a seta: {carga.referencia}."
        )
    return indice, sinal / fator_si, situacao, avisos


def preencher(
    lido: ArquivoDoGerenciador, plano: pc.PlanoDeCargas, eixos: str, estados: Sequence[str]
) -> Preenchimento:
    """O arquivo salvo pelo SolidWorks com os casos primários e as combinações do plano."""
    cenario = ex.cenario_de_carga(plano, ex.UNIDADES_N_M, eixos, estados)
    grupos = lido.cargas()
    escolha = _correspondencia(list(grupos), cenario)
    primeira = lido.casos[0][1] if lido.casos else ()
    ligacoes: dict[int, tuple[int, float]] = {}
    manter: dict[int, tuple[str, bool]] = {}
    lista: list[Ligacao] = []
    avisos: list[str] = []
    fora_do_plano: list[str] = []
    for nome, indices in grupos.items():
        colunas = [lido.colunas[i] for i in indices]
        carga = escolha.get(nome)
        if carga is None:
            if any(c.unidade or c.valor_original is not None for c in colunas):
                fora_do_plano.append(nome)
                lista.append(
                    Ligacao(nome, "", "", "não está no plano: suprimida em todos os casos")
                )
            else:
                for i in indices:
                    manter[i] = (primeira[i] if i < len(primeira) else "", False)
                lista.append(Ligacao(nome, "", "", "mantida como está no SolidWorks"))
            continue
        alvo, fator, situacao, avisos_da_carga = _ligar(carga, colunas)
        avisos += avisos_da_carga
        componente = ""
        if alvo is not None:
            ligacoes[carga.numero] = (indices[alvo], fator)
            componente = f"{colunas[alvo].componente} ({colunas[alvo].unidade})"
        else:  # a temperatura e a carga que não deu para ligar: vale o que está no SolidWorks
            for i in indices:
                manter[i] = (SUPRIMIR, True)
        lista.append(Ligacao(nome, carga.titulo, componente, situacao))
    if fora_do_plano:
        avisos.append(
            "Cargas do estudo que o plano não tem — ficam suprimidas em todos os casos: "
            f"{', '.join(fora_do_plano)}. Se são do projeto, inclua no plano de cargas; se a carga "
            "é do plano com outro nome, renomeie no SolidWorks como na aba Cargas do estudo."
        )
    faltam = [c for c in cenario.cargas if c not in escolha.values()]
    if faltam:
        avisos.append(
            "Cargas do plano que o estudo não tem (crie no SolidWorks com estes nomes, ou renomeie "
            "as que já existem): "
            + "; ".join(
                f"{c.nome} — {c.onde}, {c.referencia}, {_br(c.valor_ao_criar)} {c.unidade}"
                for c in faltam
            )
            + "."
        )
    anteriores = {em._normal(ex.nome_no_solidworks(nome)): c for nome, c in lido.casos}
    casos, combinacoes, avisos_dos_casos = _casos_e_combinacoes(
        plano, estados, cenario, len(lido.colunas), ligacoes, manter, anteriores
    )
    avisos += avisos_dos_casos
    novos = {em._normal(nome): celulas for nome, celulas in casos}
    diferencas: list[tuple[str, str, str, str]] = []
    substituidos = []
    for nome, celulas in lido.casos:
        preenchido = novos.get(em._normal(ex.nome_no_solidworks(nome)))
        if preenchido is None:
            substituidos.append(nome)
            continue
        for coluna, antes, depois in zip(lido.colunas, celulas, preenchido, strict=False):
            if not _mesma_celula(antes, depois):
                diferencas.append(
                    (nome, f"{coluna.carga} › {coluna.componente}", antes or "—", depois)
                )
    if substituidos:
        avisos.append(
            "Os casos do SolidWorks que não são do plano saem do arquivo preenchido (ele traz os "
            f"casos do plano: {', '.join(n for n, _ in casos)}): {', '.join(substituidos)}."
        )
    arquivo = ArquivoDoGerenciador(
        lido.colunas, tuple(casos), tuple(combinacoes), lido.rotulos, lido.rotulo_combinacoes
    )
    return Preenchimento(arquivo, tuple(lista), tuple(avisos), tuple(diferencas))


def _mesma_celula(antes: str, depois: str) -> bool:
    if antes.strip().casefold() == depois.strip().casefold():
        return True
    a = em.numero(antes, decimal_virgula="," in antes and "." not in antes)
    b = em.numero(depois, decimal_virgula=False)
    if a is None or b is None:
        return False
    return abs(a - b) <= max(1e-9, 0.005 * max(abs(a), abs(b)))
