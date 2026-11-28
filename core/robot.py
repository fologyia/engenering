"""Importação de tabelas do Autodesk Robot e preparação das verificações estáticas."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from core import apoios_do_modelo as am
from core import esforcos_modelo as em
from core import exportacao_cargas as ex
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import robot_documentos as rd

CAMPO = "modelo_robot"
CAMPO_ORIGEM = "origem_do_modelo"
ROBOT = "Robot"
SOLIDWORKS = "SolidWorks"
TOOLKIT = "Toolkit"
LINEAR = "Estática linear de primeira ordem"
SEGUNDA_ORDEM = "Estática de segunda ordem"
ANALISES = ("", LINEAR, SEGUNDA_ORDEM)
FORCAS = {"kN": 1.0, "N": 0.001, "MN": 1000.0, "kgf": 0.00980665, "tf": 9.80665}
MOMENTOS = {"kN·m": 1.0, "N·m": 0.001, "N·mm": 1e-6, "kN·mm": 0.001, "tf·m": 9.80665}
COMPRIMENTOS = {"m": 1.0, "cm": 0.01, "mm": 0.001}
POSICOES = ("Relativa (0–1)", "%", *COMPRIMENTOS)
COMPONENTES = ("FX", "FY", "FZ", "MX", "MY", "MZ")


class ImportacaoRobotInvalida(ValueError):
    """A remessa ou a seleção de combinações requer correção."""


@dataclass(frozen=True)
class Coluna:
    nome: str
    aliases: tuple[str, ...]
    obrigatoria: bool = True


def _coluna(nome: str, aliases: str = "", *, opcional: bool = False) -> Coluna:
    return Coluna(nome, tuple(aliases.split("|")) if aliases else (), not opcional)


NO = _coluna("Nó", "Node|Node no|Nº do nó|Número do nó|No de nó")
BARRA = _coluna("Barra", "Bar|Member|Bar no|Nº da barra|Número da barra|Elemento")
CASO = _coluna(
    "Caso",
    "Case|Load case|Case no|Nº do caso|Número do caso|Caso de carga|Combinação|Combinações|Combinations",
)
NOME = _coluna("Nome", "Nome do caso|Case name|Name|Descrição|Description|Designação|Label")
ANALISE = _coluna("Análise", "Analysis|Analysis type|Tipo de análise", opcional=True)
ESTADO = _coluna(
    "Estado-limite", "Limit state|Tipo de combinação|Combination type|Type|Tipo", opcional=True
)
VETOR = tuple(_coluna(c, f"R{c}" if c.startswith("M") else f"R{c[-1]}|R{c}") for c in COMPONENTES)
ID_ESFORCO = _coluna(
    "Identificação da força",
    "Barra/Nó/Caso|Bar/Node/Case|Member/Node/Case|Barra/Ponto/Caso|Bar/Point/Case|"
    "Barra/Posição/Caso|Bar/Position/Case|Member/Position/Case",
    opcional=True,
)
ID_REACAO = _coluna("Identificação da reação", "Nó/Caso|Node/Case", opcional=True)
NATUREZA = _coluna(
    "Natureza", "Nature|Load nature|Case nature|Natureza do caso|Tipo", opcional=True
)
ESQUEMAS = {
    "Nós": (
        NO,
        _coluna("X"),
        _coluna("Y"),
        _coluna("Z"),
        _coluna("Apoio", "Support", opcional=True),
    ),
    "Barras": (
        BARRA,
        _coluna("Nó inicial", "Start|Start node|Node 1|Nó 1|Início|Node at start"),
        _coluna("Nó final", "End|End node|Node 2|Nó 2|Fim|Node at end"),
        _coluna("Seção", "Section|Secção|Perfil|Cross section|Section name"),
        _coluna("Material", "Material name|Aço"),
        _coluna("Gama", "Gamma|Rotação|Angle", opcional=True),
        _coluna("Eixo forte", "Strong axis|Major axis", opcional=True),
    ),
    "Casos": (CASO, NOME, ANALISE, NATUREZA),
    "Combinações": (
        CASO,
        replace(NOME, obrigatoria=False),
        ANALISE,
        ESTADO,
        NATUREZA,
        _coluna("Definição", "Definition|Expressão|Expression", opcional=True),
        _coluna("Caso base", "Component|Case component|Componente|Simple case", opcional=True),
        _coluna("Fator", "Factor|Coefficient|Coeficiente", opcional=True),
    ),
    "Esforços": (
        ID_ESFORCO,
        BARRA,
        CASO,
        _coluna("Posição", "Position|Point|Ponto|Abscissa|x|x/L|Rel. position"),
        _coluna("Lado", "Side", opcional=True),
        _coluna("Componente", "Component|Case component", opcional=True),
        *VETOR,
    ),
    "Reações": (ID_REACAO, NO, CASO, *VETOR),
}
IDENTIFICACOES = {
    "Esforços": (ID_ESFORCO.nome, {"Barra", "Caso", "Posição"}),
    "Reações": (ID_REACAO.nome, {"Nó", "Caso"}),
}


@dataclass(frozen=True)
class Tabela:
    nome: str
    assinatura: str
    linhas: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True)
class Selecao:
    tabela: Tabela
    cabecalho: int  # número de linha, a partir de 1
    colunas: Mapping[str, int]  # índice, a partir de 0

    def registros(self) -> Iterator[tuple[int, dict[str, Any]]]:
        for numero, linha in enumerate(
            self.tabela.linhas[self.cabecalho :], start=self.cabecalho + 1
        ):
            if not any(_texto(c) for c in linha):
                continue
            if linha == self.tabela.linhas[self.cabecalho - 1]:
                continue
            yield (
                numero,
                {campo: linha[i] if i < len(linha) else None for campo, i in self.colunas.items()},
            )


@dataclass(frozen=True)
class Unidades:
    comprimento: str = "m"
    posicao: str = POSICOES[0]
    forca_esforco: str = "kN"
    momento_esforco: str = "kN·m"
    forca_reacao: str = "kN"
    momento_reacao: str = "kN·m"
    decimal_virgula: bool = True


def _texto(valor: object) -> str:
    return str(valor).strip() if valor is not None else ""


def _chave(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", _texto(valor).casefold())
    return "".join(c for c in texto if c.isascii() and c.isalnum())


def _cabecalho(valor: object) -> str:
    return _chave(re.sub(r"\[[^\]]*\]|\([^)]*\)", "", _texto(valor)))


def _numero(valor: object, unidades: Unidades) -> float:
    if isinstance(valor, bool) or valor is None:
        raise ValueError("valor numérico ausente")
    if isinstance(valor, (int, float)):
        numero = float(valor)
    else:
        texto = _texto(valor).replace("−", "-").replace("\u00a0", "").replace(" ", "")
        decimal = "," if unidades.decimal_virgula else "."
        milhar = "." if unidades.decimal_virgula else ","
        grupo = rf"(?:\d+|\d{{1,3}}(?:{re.escape(milhar)}\d{{3}})+)"
        if not re.fullmatch(
            rf"[+-]?(?:{grupo}(?:{re.escape(decimal)}\d*)?|{re.escape(decimal)}\d+)(?:[eE][+-]?\d+)?",
            texto,
        ):
            raise ValueError(f"número inválido {valor!r} para o separador decimal escolhido")
        numero = float(texto.replace(milhar, "").replace(decimal, "."))
    if not math.isfinite(numero):
        raise ValueError(f"número não finito {valor!r}")
    return numero


def _inteiro(valor: object) -> int:
    texto = _texto(valor)
    if not re.fullmatch(r"\d+(?:[.,]0+)?", texto) or int(re.split(r"[.,]", texto)[0]) <= 0:
        raise ValueError(f"identificador numérico inválido {valor!r}")
    return int(re.split(r"[.,]", texto)[0])


def _caso(valor: object) -> str:
    texto = _texto(valor)
    if isinstance(valor, float) and valor.is_integer():
        texto = str(int(valor))
    achado = re.fullmatch(
        r"(\d+)(?:\s*[/.,]\s*(\d+))?(?:\s*(?:\([^)]*\)|[:\-]\s+.+|\s+.+))?", texto
    )
    if not achado or int(achado[1]) <= 0:
        raise ValueError(f"identificador de caso inválido {valor!r}")
    base = str(int(achado[1]))
    return f"{base}/{int(achado[2])}" if achado[2] and int(achado[2]) else base


def colunas_sugeridas(esquema: str, linha: Sequence[object]) -> dict[str, int]:
    chaves = [_cabecalho(c) for c in linha]
    saida: dict[str, int] = {}
    for coluna in ESQUEMAS[esquema]:
        for alias in (coluna.nome, *coluna.aliases):
            encontrados = [i for i, chave in enumerate(chaves) if chave == _chave(alias)]
            if encontrados:
                if len(encontrados) == 1 and encontrados[0] not in saida.values():
                    saida[coluna.nome] = encontrados[0]
                break
    return saida


def sugerir_cabecalho(esquema: str, tabela: Tabela) -> tuple[int, int]:
    obrigatorias = campos_obrigatorios(esquema)

    def nota(linha: Sequence[object]) -> int:
        mapeadas = colunas_sugeridas(esquema, linha)
        return len(obrigatorias) - len(campos_obrigatorios(esquema, mapeadas) - mapeadas.keys())

    return max(
        ((nota(linha), -i) for i, linha in enumerate(tabela.linhas[:30], 1)),
        default=(0, -1),
    )


def campos_obrigatorios(tipo: str, mapeadas: Mapping[str, int] | None = None) -> set[str]:
    campos = {c.nome for c in ESQUEMAS[tipo] if c.obrigatoria}
    if tipo in IDENTIFICACOES and mapeadas:
        agrupada, separadas = IDENTIFICACOES[tipo]
        if agrupada in mapeadas:
            return campos - separadas
    return campos


def ler_tabelas(nome: str, conteudo: bytes) -> list[Tabela]:
    assinatura = hashlib.sha256(conteudo).hexdigest()
    formato = Path(nome).suffix.casefold()
    if formato == ".xlsx":
        try:
            livro = load_workbook(
                BytesIO(conteudo), read_only=True, data_only=True, keep_links=False
            )
            try:
                return [
                    Tabela(f"{nome} / {aba.title}", assinatura, tuple(aba.values))
                    for aba in livro.worksheets
                ]
            finally:
                livro.close()
        except Exception as erro:
            raise ImportacaoRobotInvalida(f"{nome}: não foi possível ler a pasta XLSX.") from erro
    for codificacao in ("utf-16", "utf-8-sig", "cp1252"):
        if codificacao == "utf-16" and not conteudo.startswith((b"\xff\xfe", b"\xfe\xff")):
            continue
        try:
            texto = conteudo.decode(codificacao)
        except UnicodeError:
            continue
        break
    else:
        raise ImportacaoRobotInvalida(f"{nome}: codificação do texto não reconhecida.")
    if formato in (".htm", ".html", ".rtf", ".xml"):
        try:
            if formato == ".xml":
                if re.search(
                    r"<robot\b(?:[^>]*\bgenerator\s*=\s*['\"]Robot\b|[^>]*>\s*<suite\b)",
                    texto,
                    re.I,
                ):
                    raise ValueError("arquivo de resultados de testes do Robot Framework")
                raise ValueError("envie uma tabela ou nota de cálculo do Autodesk Robot")
            extrair = rd.ler_rtf if formato == ".rtf" else rd.ler_html
            return [
                Tabela(
                    f"{nome} / Tabela {i}" + (f" · {titulo}" if titulo else ""), assinatura, linhas
                )
                for i, (titulo, linhas) in enumerate(extrair(texto), 1)
            ]
        except ValueError as erro:
            raise ImportacaoRobotInvalida(f"{nome}: {erro}.") from erro
    alternativas = []
    for sep in ("\t", ";", ","):
        try:
            linhas = tuple(
                tuple(r) for r in csv.reader(StringIO(texto), delimiter=sep, strict=True)
            )
        except csv.Error:
            continue
        tabela = Tabela(nome, assinatura, linhas)
        aliases = max(sugerir_cabecalho(e, tabela)[0] for e in ESQUEMAS)
        alternativas.append((aliases, max((len(l) for l in linhas[:30]), default=0), tabela))
    if not alternativas:
        raise ImportacaoRobotInvalida(f"{nome}: texto tabular inválido.")
    return [max(alternativas, key=lambda a: a[:2])[2]]


def _unidade_declarada(cabecalho: object, fatores: Mapping[str, float]) -> str | None:
    partes = re.findall(r"\[([^]]+)\]|\(([^)]+)\)", _texto(cabecalho))
    for colchetes, parenteses in partes:
        chave = _chave(colchetes or parenteses)
        for nome in fatores:
            if chave == _chave(nome):
                return nome
        if chave:
            raise ValueError(f"unidade não suportada em {cabecalho!r}")
    return None


def _fatores(
    selecao: Selecao,
    campos: Sequence[str],
    padrao: str,
    unidades: Mapping[str, float],
) -> tuple[float, ...]:
    linha = selecao.tabela.linhas[selecao.cabecalho - 1]
    try:
        return tuple(
            unidades[_unidade_declarada(linha[selecao.colunas[c]], unidades) or padrao]
            for c in campos
        )
    except (ValueError, KeyError) as erro:
        raise ImportacaoRobotInvalida(f"{selecao.tabela.nome}: {erro}") from erro


def _eixo_forte(valor: object) -> str:
    chave = _chave(valor)
    if chave in {"y", "my", "1", "momento1", "localy"}:
        return em.EIXO_M1
    if chave in {"z", "mz", "2", "momento2", "localz"}:
        return em.EIXO_M2
    return ""


def _analise(valor: object) -> str:
    chave = _chave(valor)
    if chave in {
        "linear",
        "linearstatic",
        "staticlinear",
        "estaticalinear",
        "estaticolinear",
        "analiseestaticalinear",
        "estaticalineardeprimeiraordem",
        "combinacaolinear",
        "linearcombination",
        "combinationlinear",
    }:
        return LINEAR
    if chave in {"pdelta", "segundaordem", "estaticadesegundaordem", "secondorderstatic"}:
        return SEGUNDA_ORDEM
    return ""


def _estado(valor: object) -> str:
    alias = {
        "ulsnormal": comb.ELU_NORMAL,
        "slsrare": comb.ELS_RARA,
        "slsfrequent": comb.ELS_FREQUENTE,
        "slsquasipermanent": comb.ELS_QUASE_PERMANENTE,
    }
    chave = _chave(valor)
    return next((e for e in comb.TODOS_OS_ESTADOS if _chave(e) == chave), alias.get(chave, ""))


def ativo(projeto: Mapping[str, Any]) -> bool:
    return projeto.get(CAMPO_ORIGEM) == ROBOT and bool(modelo_do_projeto(projeto))


def assinatura_da_remessa(
    tabelas: Mapping[str, Selecao], unidades: Unidades, modelo: str, revisao: str
) -> str:
    dados = {
        "modelo": modelo,
        "revisao": revisao,
        "unidades": vars(unidades),
        "tabelas": {
            tipo: [s.tabela.nome, s.tabela.assinatura, s.cabecalho, dict(s.colunas)]
            for tipo, s in tabelas.items()
        },
    }
    return hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()


@contextmanager
def _na_linha(tabela: Selecao, numero: int):
    try:
        yield
    except (ArithmeticError, ValueError) as erro:
        raise ImportacaoRobotInvalida(f"{tabela.tabela.nome}, linha {numero}: {erro}.") from erro


def _validar_selecoes(tabelas: Mapping[str, Selecao]) -> None:
    for tipo in ("Nós", "Barras", "Casos", "Esforços", "Reações"):
        if tipo not in tabelas:
            raise ImportacaoRobotInvalida(f"Selecione a tabela de {tipo.lower()}.")
    for tipo, selecao in tabelas.items():
        if not 1 <= selecao.cabecalho <= len(selecao.tabela.linhas):
            raise ImportacaoRobotInvalida(
                f"{selecao.tabela.nome}: número da linha do cabeçalho inválido."
            )
        faltam = sorted(campos_obrigatorios(tipo, selecao.colunas) - selecao.colunas.keys())
        if faltam:
            raise ImportacaoRobotInvalida(f"{selecao.tabela.nome}: mapeie {', '.join(faltam)}.")
        if len(set(selecao.colunas.values())) != len(selecao.colunas):
            raise ImportacaoRobotInvalida(
                f"{selecao.tabela.nome}: uma coluna foi associada a mais de um campo."
            )
        colunas = len(selecao.tabela.linhas[selecao.cabecalho - 1])
        if any(not 0 <= indice < colunas for indice in selecao.colunas.values()):
            raise ImportacaoRobotInvalida(
                f"{selecao.tabela.nome}: índice de coluna fora do cabeçalho."
            )


def _ler_nos(
    tabela: Selecao,
    unidades: Unidades,
) -> tuple[dict[int, tuple[float, float, float]], list[int]]:
    fx, fy, fz = _fatores(tabela, ("X", "Y", "Z"), unidades.comprimento, COMPRIMENTOS)
    nos = {}
    apoios = []
    for numero, linha in tabela.registros():
        with _na_linha(tabela, numero):
            no = _inteiro(linha["Nó"])
            if no in nos:
                raise ValueError(f"nó {no} repetido")
            nos[no] = (
                _numero(linha["X"], unidades) * fx,
                _numero(linha["Y"], unidades) * fy,
                _numero(linha["Z"], unidades) * fz,
            )
            if _chave(linha.get("Apoio")) not in {"", "none", "nenhum", "semapoio"}:
                apoios.append(no)
    if not nos:
        raise ImportacaoRobotInvalida(f"{tabela.tabela.nome}: tabela sem nós.")
    return nos, apoios


def _ler_barras(
    tabela: Selecao,
    unidades: Unidades,
    nos: Mapping[int, tuple[float, float, float]],
) -> tuple[
    dict[str, dict[str, Any]], dict[str, ld.CorpoDoModelo], dict[str, em.ConfiguracaoDoMembro]
]:
    barras = {}
    corpos = {}
    configuracoes = {}
    for numero, linha in tabela.registros():
        with _na_linha(tabela, numero):
            barra = str(_inteiro(linha["Barra"]))
            if barra in barras:
                raise ValueError(f"barra {barra} repetida")
            inicio, fim = (_inteiro(linha[c]) for c in ("Nó inicial", "Nó final"))
            if inicio not in nos or fim not in nos:
                raise ValueError(f"barra {barra} faz referência a um nó ausente ({inicio}, {fim})")
            secao, material = (_texto(linha[c]) for c in ("Seção", "Material"))
            if not secao or not material:
                raise ValueError(f"informe a seção e o material da barra {barra}")
            comprimento = math.dist(nos[inicio], nos[fim])
            if not math.isfinite(comprimento) or comprimento <= 0:
                raise ValueError(f"barra {barra} com comprimento inválido")
            gama = _numero(linha["Gama"], unidades) if _texto(linha.get("Gama")) else None
            perfil_catalogo = lm.perfil_conhecido(secao)
            perfil = perfil_catalogo.nome if perfil_catalogo else ""
            barras[barra] = {
                "nos": [inicio, fim],
                "secao": secao,
                "material": material,
                "gama": gama,
            }
            corpo = ld.CorpoDoModelo(
                barra,
                barra,
                secao,
                nos[inicio],
                nos[fim],
                comprimento,
                forma=ld.FORMA_BARRA,
                perfil_declarado=secao,
            )
            corpos[barra] = corpo
            tipo, _ = ld.tipo_pela_geometria(corpo, "Z")
            configuracoes[barra] = em.ConfiguracaoDoMembro(
                perfil=perfil,
                tipo=tipo if tipo in em.TIPOS_DE_BARRA else "—",
                aco=material,
                eixo_forte=_eixo_forte(linha.get("Eixo forte")),
            )
    if not barras:
        raise ImportacaoRobotInvalida(f"{tabela.tabela.nome}: tabela sem barras.")
    return barras, corpos, configuracoes


def _ler_casos(tabelas: Mapping[str, Selecao], unidades: Unidades) -> dict[str, dict[str, Any]]:
    casos: dict[str, dict[str, Any]] = {}
    for tipo in ("Casos", "Combinações"):
        tabela = tabelas.get(tipo)
        if tabela is None:
            continue
        for numero, linha in tabela.registros():
            with _na_linha(tabela, numero):
                codigo = _caso(linha["Caso"])
                tipo_analise = _chave(linha.get("Análise"))
                combinado = tipo == "Combinações" or tipo_analise.startswith(
                    ("combinacao", "combination", "linearcombination")
                )
                classe = "Combinações" if combinado else "Casos"
                anterior = casos.get(codigo, {})
                if anterior and (not combinado or anterior["tipo"] != classe):
                    raise ValueError(
                        f"identificador de caso {codigo} repetido em classes diferentes ou nos casos simples"
                    )
                nome = _texto(linha.get("Nome")) or _texto(anterior.get("nome"))
                if not nome and not combinado:
                    raise ValueError(f"informe o nome do caso {codigo}")
                caso_base = _texto(linha.get("Caso base"))
                fator = _texto(linha.get("Fator"))
                if bool(caso_base) != bool(fator):
                    raise ValueError(
                        f"a combinação {codigo} precisa do caso base e do fator na mesma linha"
                    )
                componentes = anterior.get("componentes", {})
                if caso_base:
                    chave = _caso(caso_base)
                    if chave not in casos or casos[chave]["tipo"] != "Casos":
                        raise ValueError(
                            f"caso base {chave} da combinação {codigo} ausente dos casos simples"
                        )
                    valor = _numero(linha["Fator"], unidades)
                    if chave in componentes and componentes[chave] != valor:
                        raise ValueError(
                            f"fator conflitante para o caso {chave} da combinação {codigo}"
                        )
                    componentes[chave] = valor
                estado = _estado(linha.get("Estado-limite")) or (_estado(nome) if combinado else "")
                analise = _analise(linha.get("Análise"))
                if estado and anterior.get("estado") not in (None, "", estado):
                    raise ValueError(f"estado-limite conflitante para {codigo}")
                if analise and anterior.get("analise") not in (None, "", analise):
                    raise ValueError(f"tipo de análise conflitante para {codigo}")
                casos[codigo] = {
                    "tipo": classe,
                    "nome": nome,
                    "estado": estado or anterior.get("estado", ""),
                    "analise": analise or anterior.get("analise", ""),
                    "analise_robot": _texto(linha.get("Análise"))
                    or anterior.get("analise_robot", ""),
                    "natureza": _texto(linha.get("Natureza")) or anterior.get("natureza", ""),
                    "codigo_plano": "",
                    "definicao": _texto(linha.get("Definição")) or anterior.get("definicao", ""),
                    "componentes": componentes,
                }
    if not any(c["tipo"] == "Casos" for c in casos.values()):
        raise ImportacaoRobotInvalida("A remessa precisa de pelo menos um caso simples.")
    return casos


def _caso_do_resultado(
    valor: object,
    componente: object,
    casos: dict[str, dict[str, Any]],
) -> str:
    codigo = _caso(valor)
    if _texto(componente) not in ("", "-", "0", "0.0"):
        subcaso = str(_inteiro(componente))
        chave = f"{codigo.split('/')[0]}/{subcaso}"
        if "/" in codigo and codigo != chave:
            raise ValueError(f"componente conflitante para o caso {codigo}")
        codigo = chave
    if codigo not in casos:
        pai = casos.get(codigo.split("/")[0])
        if not pai or pai["tipo"] != "Combinações":
            raise ValueError(f"caso ou combinação {codigo} ausente das tabelas de identificação")
        casos[codigo] = dict(pai)
    return codigo


def _lado(valor: object) -> str:
    chave = _chave(valor)
    texto = _texto(valor)
    if texto in ("", "—"):
        return ""
    if chave in {"left", "l", "esq", "esquerda", "minus", "e", "xminus"} or texto in ("-", "−"):
        return "esquerda"
    if chave in {"right", "r", "dir", "direita", "plus", "d", "xplus"} or texto == "+":
        return "direita"
    raise ValueError(f"lado de corte desconhecido {valor!r}")


def _posicao(valor: object, unidade: str, unidades: Unidades, comprimento: float) -> str:
    numero = _numero(valor, unidades)
    if unidade == "%":
        numero /= 100
    elif unidade in COMPRIMENTOS:
        numero = numero * COMPRIMENTOS[unidade] / comprimento
    if not -1e-6 <= numero <= 1 + 1e-6:
        raise ValueError(f"posição {valor!r} fora da barra na unidade selecionada")
    return f"{min(max(numero, 0.0), 1.0):.9f}".rstrip("0").rstrip(".")


def _unidade_da_posicao(tabela: Selecao, padrao: str) -> str:
    coluna = tabela.colunas.get("Posição", tabela.colunas.get(ID_ESFORCO.nome))
    assert coluna is not None
    cabecalho = _texto(tabela.tabela.linhas[tabela.cabecalho - 1][coluna])
    if "%" in cabecalho:
        return "%"
    if _cabecalho(cabecalho) in {"xl", "relposition"}:
        return POSICOES[0]
    try:
        return _unidade_declarada(cabecalho, {**COMPRIMENTOS, "-": 1.0}) or padrao
    except ValueError as erro:
        raise ImportacaoRobotInvalida(f"{tabela.tabela.nome}: {erro}") from erro


def _separar_identificacao(valor: object, campos: int) -> list[str]:
    texto = _texto(valor)
    # O TXT nativo separa os campos com barra e espaço. A fração interna 2/5
    # de um ponto e o identificador de um componente mantêm a barra sem espaço.
    partes = re.split(r"\s*/\s+", texto, maxsplit=campos - 1)
    if len(partes) != campos:
        partes = texto.split("/", maxsplit=campos - 1)
    if len(partes) != campos or any(not p.strip() for p in partes):
        raise ValueError(f"identificação inválida {valor!r}")
    return partes


def _posicao_na_identificacao(
    ponto: str,
    barra: Mapping[str, Any],
    *,
    por_posicao: bool,
    unidade: str,
    unidades: Unidades,
    comprimento: float,
) -> str:
    if por_posicao:
        return _posicao(ponto, unidade, unidades, comprimento)
    fracao = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", ponto)
    if fracao:
        ordem, divisoes = (int(v) for v in fracao.groups())
        if not 1 < ordem < divisoes:
            raise ValueError(f"ponto de divisão inválido {ponto!r}")
        return _posicao((ordem - 1) / (divisoes - 1), POSICOES[0], unidades, comprimento)
    no = _inteiro(ponto)
    if no not in barra["nos"]:
        raise ValueError(f"nó {no} não é uma extremidade da barra")
    return "0" if no == barra["nos"][0] else "1"


def _ler_esforcos(
    tabela: Selecao,
    unidades: Unidades,
    corpos: Mapping[str, ld.CorpoDoModelo],
    barras: Mapping[str, Mapping[str, Any]],
    casos: dict[str, dict[str, Any]],
) -> dict[str, dict[str, tuple[em.PontoDeEsforco, ...]]]:
    fatores = (
        *_fatores(tabela, COMPONENTES[:3], unidades.forca_esforco, FORCAS),
        *_fatores(tabela, COMPONENTES[3:], unidades.momento_esforco, MOMENTOS),
    )
    unidade_posicao = _unidade_da_posicao(tabela, unidades.posicao)
    agrupada = tabela.colunas.get(ID_ESFORCO.nome)
    por_posicao = agrupada is not None and any(
        termo in _cabecalho(tabela.tabela.linhas[tabela.cabecalho - 1][agrupada])
        for termo in ("posicao", "position")
    )
    pontos: dict[tuple[str, str], dict[tuple[str, str], em.PontoDeEsforco]] = defaultdict(dict)
    for numero, linha in tabela.registros():
        with _na_linha(tabela, numero):
            if agrupada is None:
                id_barra, ponto, id_caso = linha["Barra"], linha["Posição"], linha["Caso"]
            else:
                id_barra, ponto, id_caso = _separar_identificacao(linha[ID_ESFORCO.nome], 3)
            barra = str(_inteiro(id_barra))
            if barra not in corpos:
                raise ValueError(f"barra {barra} ausente da tabela de barras")
            caso = _caso_do_resultado(id_caso, linha.get("Componente"), casos)
            comprimento = corpos[barra].comprimento_m
            posicao = (
                _posicao(linha["Posição"], unidade_posicao, unidades, comprimento)
                if "Posição" in linha
                else _posicao_na_identificacao(
                    ponto,
                    barras[barra],
                    por_posicao=por_posicao,
                    unidade=unidade_posicao,
                    unidades=unidades,
                    comprimento=comprimento,
                )
            )
            lado = _lado(linha.get("Lado"))
            chave = (posicao, lado)
            if chave in pontos[caso, barra]:
                raise ValueError(
                    f"barra {barra}, caso {caso}, x/L {posicao} repetido; confira o lado do corte"
                )
            fx, fy, fz, mx, my, mz = (
                _numero(linha[c], unidades) * f for c, f in zip(COMPONENTES, fatores, strict=True)
            )
            # x local é longitudinal. V1 acompanha MY/MZ conforme o braço local
            # do cortante: FY ↔ MZ e FZ ↔ MY.
            pontos[caso, barra][chave] = em.PontoDeEsforco(posicao, lado, -fx, fy, fz, my, mz, mx)
    if not pontos:
        raise ImportacaoRobotInvalida(f"{tabela.tabela.nome}: tabela sem esforços.")
    por_caso: dict[str, dict[str, tuple[em.PontoDeEsforco, ...]]] = defaultdict(dict)
    for (caso, barra), valores in pontos.items():
        por_caso[caso][barra] = tuple(
            valores[k] for k in sorted(valores, key=lambda k: (float(k[0]), k[1] == "direita"))
        )
    return dict(por_caso)


def _ler_reacoes(
    tabela: Selecao,
    unidades: Unidades,
    nos: Mapping[int, tuple[float, float, float]],
    casos: dict[str, dict[str, Any]],
) -> am.ApoiosDoModelo:
    fatores = (
        *_fatores(tabela, COMPONENTES[:3], unidades.forca_reacao, FORCAS),
        *_fatores(tabela, COMPONENTES[3:], unidades.momento_reacao, MOMENTOS),
    )
    reacoes: dict[str, dict[int, am.ReacaoNoNo]] = defaultdict(dict)
    for numero, linha in tabela.registros():
        with _na_linha(tabela, numero):
            if ID_REACAO.nome in linha:
                identificacao = _texto(linha[ID_REACAO.nome])
                chave = _chave(identificacao)
                if chave.startswith(
                    (
                        "soma",
                        "sum",
                        "total",
                        "verificar",
                        "verification",
                        "precision",
                        "precisao",
                        "residuo",
                        "residuum",
                        "check",
                        "caso",
                        "case",
                    )
                ):
                    continue
                id_no, id_caso = _separar_identificacao(identificacao, 2)
            else:
                id_no, id_caso = linha["Nó"], linha["Caso"]
                if _chave(id_no) in {"soma", "sum", "total"}:
                    continue
            no = _inteiro(id_no)
            if no not in nos:
                raise ValueError(f"nó de apoio {no} ausente da tabela de nós")
            caso = _caso_do_resultado(id_caso, None, casos)
            if no in reacoes[caso]:
                raise ValueError(f"reação repetida para o nó {no} no caso {caso}")
            fx, fy, fz, mx, my, mz = (
                _numero(linha[c], unidades) * f * 1000
                for c, f in zip(COMPONENTES, fatores, strict=True)
            )
            reacoes[caso][no] = am.ReacaoNoNo(no, nos[no], (fx, fy, fz), (mx, my, mz))
    if not reacoes:
        raise ImportacaoRobotInvalida(f"{tabela.tabela.nome}: tabela sem reações.")
    return am.ApoiosDoModelo(
        {
            codigo: am.ApoiosDoCaso(
                codigo, casos[codigo]["nome"], tabela.tabela.nome, tuple(linhas.values())
            )
            for codigo, linhas in reacoes.items()
        }
    )


def modelo_do_projeto(projeto: Mapping[str, Any]) -> Mapping[str, Any]:
    modelo = projeto.get(CAMPO)
    return modelo if isinstance(modelo, Mapping) else {}


def dados_do_modelo(modelo: Mapping[str, Any]) -> em.EsforcosDoModelo:
    dados = em.de_dicionario(modelo.get("esforcos"))
    membros = {
        barra: replace(cfg, eixo_forte="") if barra in modelo.get("eixos_pendentes", ()) else cfg
        for barra, cfg in dados.membros.items()
    }
    return replace(dados, membros=membros)


def com_configuracao(modelo: Mapping[str, Any], dados: em.EsforcosDoModelo) -> dict[str, Any]:
    return {
        **modelo,
        "esforcos": em.para_dicionario(dados, preservar_precisao=True),
        "eixos_pendentes": [b for b, cfg in dados.membros.items() if not cfg.eixo_forte],
    }


def importar(
    tabelas: Mapping[str, Selecao],
    unidades: Unidades,
    nome: str,
    revisao: str,
    *,
    anterior: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    nome, revisao = nome.strip(), revisao.strip()
    if not nome or not revisao:
        raise ImportacaoRobotInvalida("Informe o nome e a revisão do modelo do Robot.")
    _validar_selecoes(tabelas)
    assinatura = assinatura_da_remessa(tabelas, unidades, nome, revisao)
    anterior = anterior or {}
    if anterior.get("assinatura") == assinatura:
        return dict(anterior)
    nos, nos_apoiados = _ler_nos(tabelas["Nós"], unidades)
    barras, corpos, configuracoes = _ler_barras(tabelas["Barras"], unidades, nos)
    casos = _ler_casos(tabelas, unidades)
    esforcos = _ler_esforcos(tabelas["Esforços"], unidades, corpos, barras, casos)
    reacoes = _ler_reacoes(tabelas["Reações"], unidades, nos, casos)
    mesmo_modelo = anterior.get("nome") == nome
    dados_anteriores = dados_do_modelo(anterior) if mesmo_modelo else em.EsforcosDoModelo()
    if mesmo_modelo:
        for barra in configuracoes.keys() & dados_anteriores.membros.keys():
            ficha = barras[barra]
            if ficha != anterior.get("barras", {}).get(barra):
                continue
            if any(list(nos[n]) != anterior.get("nos", {}).get(str(n)) for n in ficha["nos"]):
                continue
            configuracoes[barra] = dados_anteriores.membros[barra]
        for codigo, caso in casos.items():
            previo = anterior.get("casos", {}).get(codigo, {})
            if (caso["nome"], caso["tipo"]) == (previo.get("nome"), previo.get("tipo")):
                caso["codigo_plano"] = previo.get("codigo_plano", "")
                if caso["analise_robot"] == previo.get("analise_robot"):
                    caso["analise"] = caso["analise"] or previo.get("analise", "")
                if caso["definicao"] == previo.get("definicao"):
                    caso["estado"] = caso["estado"] or previo.get("estado", "")
    data = em.agora()
    dados = em.EsforcosDoModelo(
        casos={
            codigo: em.CasoImportado(
                codigo,
                casos[codigo]["nome"],
                tabelas["Esforços"].tabela.nome,
                data,
                tabelas["Esforços"].tabela.assinatura,
                membros,
            )
            for codigo, membros in esforcos.items()
        },
        membros=configuracoes,
        eixo_vertical="Z",
        parametros=dados_anteriores.parametros,
        norma=dados_anteriores.norma,
    )
    origem = anterior.get("origem_combinacoes")
    if origem not in (ROBOT, TOOLKIT):
        origem = ROBOT if any(casos[k]["tipo"] == "Combinações" for k in esforcos) else TOOLKIT
    return com_configuracao(
        {
            "nome": nome,
            "revisao": revisao,
            "assinatura": assinatura,
            "data": data,
            "origem_combinacoes": origem,
            "relatorio": anterior.get("relatorio", {})
            if anterior.get("nome") == nome and anterior.get("revisao") == revisao
            else {},
            "arquivos": {
                tipo: {"tabela": s.tabela.nome, "sha256": s.tabela.assinatura}
                for tipo, s in tabelas.items()
            },
            "unidades": vars(unidades),
            "nos": {str(n): list(p) for n, p in nos.items()},
            "nos_apoiados": nos_apoiados,
            "barras": barras,
            "casos": casos,
            "reacoes": am.para_dicionario(reacoes),
            "geometria": ld.para_dicionario(
                ld.GeometriaDoModelo(
                    tuple(corpos.values()),
                    tabelas["Barras"].tabela.nome,
                    data,
                    nome,
                    revisao,
                )
            ),
        },
        dados,
    )


def contexto(modelo: Mapping[str, Any]) -> dict[str, str]:
    relatorio = modelo.get("relatorio", {})
    origem = {
        "modelo_robot": str(modelo["nome"]),
        "revisao_modelo_robot": str(modelo["revisao"]),
        "assinatura_remessa_robot": str(modelo["assinatura"]),
        "tabelas_robot": ", ".join(a["tabela"] for a in modelo["arquivos"].values()),
        "unidades_robot": "Coordenadas em m, esforços em kN e kN·m, posição em x/L.",
    }
    if relatorio:
        origem["relatorio_robot"] = (
            f"{relatorio['codigo']} · {relatorio['titulo']} · revisão {relatorio['revisao']}"
        )
    return origem


def atualizar_casos(
    modelo: Mapping[str, Any],
    ajustes: Mapping[str, Mapping[str, str]],
    origem: str,
) -> dict[str, Any]:
    if origem not in (ROBOT, TOOLKIT):
        raise ImportacaoRobotInvalida("Escolha a origem das combinações.")
    casos = {}
    for codigo, caso in modelo["casos"].items():
        ajuste = ajustes.get(codigo, {})
        analise = ajuste.get("analise", caso["analise"])
        estado = ajuste.get("estado", caso["estado"]) if caso["tipo"] == "Combinações" else ""
        if analise not in ANALISES or estado not in ("", *comb.TODOS_OS_ESTADOS):
            raise ImportacaoRobotInvalida(
                f"Caso {codigo}: tipo de análise ou estado-limite inválido."
            )
        casos[codigo] = {
            **caso,
            "analise": analise,
            "estado": estado,
            "codigo_plano": ajuste.get("codigo_plano", caso["codigo_plano"])
            if caso["tipo"] == "Casos"
            else "",
        }
    return {**modelo, "origem_combinacoes": origem, "casos": casos}


def _pontos(
    dados: em.EsforcosDoModelo,
    barra: str,
    codigo: str,
) -> dict[tuple[str, str], em.PontoDeEsforco]:
    caso = dados.casos.get(codigo)
    pontos = caso.membros.get(barra, ()) if caso else ()
    if not {"0", "1"} <= {p.elemento for p in pontos}:
        raise ImportacaoRobotInvalida(
            f"Barra {barra}, caso {codigo}: faltam esforços nas extremidades (x/L = 0 e 1)."
        )
    return {p.chave: p for p in pontos}


def _rotulo_ponto(chave: tuple[str, str]) -> str:
    posicao, lado = chave
    return f"x/L = {posicao}" + (f" ({lado})" if lado else "")


def _combinacoes_robot(
    modelo: Mapping[str, Any], dados: em.EsforcosDoModelo, estados: Sequence[str]
):
    casos = modelo["casos"]
    familias = {c.split("/")[0] for c in dados.casos if "/" in c}
    combinacoes = {
        codigo: caso
        for codigo, caso in casos.items()
        if caso["tipo"] == "Combinações" and (codigo not in familias or codigo in dados.casos)
    }
    sem_estado = [codigo for codigo, caso in combinacoes.items() if not caso["estado"]]
    if sem_estado:
        raise ImportacaoRobotInvalida(
            f"Classifique o estado-limite das combinações {', '.join(sem_estado)}."
        )
    escolhidas = {codigo: caso for codigo, caso in combinacoes.items() if caso["estado"] in estados}
    ausentes = [e for e in estados if all(c["estado"] != e for c in escolhidas.values())]
    if ausentes:
        raise ImportacaoRobotInvalida(f"Faltam combinações do Robot para {', '.join(ausentes)}.")
    sem_analise = [codigo for codigo, caso in escolhidas.items() if not caso["analise"]]
    if sem_analise:
        raise ImportacaoRobotInvalida(
            f"Confirme o tipo de análise das combinações {', '.join(sem_analise)}."
        )
    nomes = {
        codigo: f"Robot {codigo}" + (f" · {caso['nome']}" if caso["nome"] else "")
        for codigo, caso in escolhidas.items()
    }
    resultados = {
        barra: tuple(
            (nomes[codigo], _rotulo_ponto(chave), ponto.vetor())
            for codigo in escolhidas
            for chave, ponto in _pontos(dados, barra, codigo).items()
        )
        for barra in modelo["barras"]
    }
    segunda_ordem = frozenset(
        nomes[c] for c, v in escolhidas.items() if v["analise"] == SEGUNDA_ORDEM
    )
    return em.PreparoDasCombinacoes(
        tuple(escolhidas),
        tuple(nomes.values()),
        (),
        (),
        resultados,
        "Combinações calculadas no Robot",
        segunda_ordem,
    )


def _combinacoes_toolkit(
    modelo: Mapping[str, Any],
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    estados: Sequence[str],
) -> em.PreparoDasCombinacoes:
    lista = pc.combinacoes(plano, estados)
    ausentes = [e for e in estados if all(c.estado_limite != e for c in lista)]
    if ausentes or not lista:
        raise ImportacaoRobotInvalida(
            f"O Plano de cargas precisa gerar combinações para {', '.join(ausentes or estados)}."
        )
    exigidos = {codigo for c in lista for codigo, f in c.fatores.items() if f != 0}
    vinculos: dict[str, str] = {}
    for codigo, caso in modelo["casos"].items():
        codigo_plano = caso["codigo_plano"]
        if caso["tipo"] != "Casos" or codigo_plano not in exigidos:
            continue
        if codigo_plano in vinculos:
            raise ImportacaoRobotInvalida(
                f"Há mais de um caso do Robot vinculado a {codigo_plano}."
            )
        if caso["analise"] != LINEAR:
            raise ImportacaoRobotInvalida(
                f"Caso {codigo} ({codigo_plano}): a superposição exige análise linear."
            )
        vinculos[codigo_plano] = codigo
    falta = exigidos - vinculos.keys()
    if falta:
        raise ImportacaoRobotInvalida(
            f"Vincule os casos do Robot a {', '.join(sorted(falta))} no Plano de cargas."
        )

    nomes = tuple(ex.nome_da_combinacao(c, len(lista)) for c in lista)
    resultados = {}
    for barra in modelo["barras"]:
        pontos = {codigo: _pontos(dados, barra, bruto) for codigo, bruto in vinculos.items()}
        valores: list[em.Combinado] = []
        for nome, combinacao in zip(nomes, lista, strict=True):
            participantes = [(codigo, f) for codigo, f in combinacao.fatores.items() if f]
            if not participantes:
                continue
            base = pontos[participantes[0][0]]
            for codigo, _ in participantes:
                if pontos[codigo].keys() != base.keys():
                    raise ImportacaoRobotInvalida(
                        f"Barra {barra}, {nome}: as posições ou lados do corte do caso "
                        f"{vinculos[codigo]} ({codigo}) diferem dos demais casos."
                    )
            for chave in base:
                vetores = [(f, pontos[codigo][chave].vetor()) for codigo, f in participantes]
                valor = tuple(math.fsum(f * v[i] for f, v in vetores) for i in range(6))
                valores.append((nome, _rotulo_ponto(chave), valor))
        resultados[barra] = tuple(valores)
    return em.PreparoDasCombinacoes(
        tuple(k for k in plano.codigos if k in exigidos),
        nomes,
        (),
        (),
        resultados,
        "Combinações do Plano de cargas aplicadas aos casos do Robot",
    )


def preparar_combinacoes(
    modelo: Mapping[str, Any],
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    estados: Sequence[str],
) -> em.PreparoDasCombinacoes:
    if not estados:
        raise ImportacaoRobotInvalida("Selecione pelo menos um estado-limite.")
    if modelo["origem_combinacoes"] == ROBOT:
        return _combinacoes_robot(modelo, dados, estados)
    return _combinacoes_toolkit(modelo, dados, plano, estados)
