"""Esforços do modelo: leitura dos resultados do SolidWorks Simulation, conferência e envoltória.

O SolidWorks lista, em CSV (clique direito em Resultados):

* **Listar forças da viga** — para cada viga do estudo, as forças nas duas pontas (Fim 1 e Fim 2) de
  **cada elemento da malha**: axial, cisalhamentos 1 e 2, momentos 1 e 2 e torque. Os esforços
  saem, portanto, ao longo de toda a barra, inclusive no meio do vão.
* **Listar forças resultantes** (força de reação) — a soma das reações em X, Y e Z da seleção e do
  modelo inteiro.
* **Listar tensão** — os nós de maior tensão (só informativo aqui).

Convenções da leitura
---------------------
* As forças vêm nas pontas de cada elemento, com sinais opostos nas duas pontas. O esforço
  **interno** (tração positiva) é −F no Fim 1 e +F no Fim 2 — conferido num pilar comprimido do
  modelo do usuário (o axial cresce de cima para baixo com o peso próprio).
* Os números do SolidWorks em português usam ponto de milhar e vírgula decimal (78.611 = 78 611 N);
  os arquivos vêm em codificação do Windows (cp1252). Unidades lidas do cabeçalho (N, kN, lbf; N.m,
  N.mm, kN.m, lbf.in, lbf.ft) e convertidas para kN e kN·m.
* Cada estudo é um caso de carga: o "Nome do estudo" que vem no arquivo sugere o código (PP, SC,
  W0…). As combinações são as do Plano de cargas, aplicadas ponto a ponto (mesmo elemento e mesma
  ponta em todos os casos).

Sem Streamlit.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from core import exportacao_cargas as ex
from core import plano_de_cargas as pc

TIPO_VIGAS = "Forças da viga"
TIPO_REACOES = "Forças de reação"
TIPO_TENSOES = "Tensões"
TIPO_DESCONHECIDO = "Desconhecido"

NIVEL_INFO = "info"

#: Tipos de barra para agrupar (e, depois, verificar com o perfil e o comprimento de cada grupo).
TIPOS_DE_BARRA: tuple[str, ...] = ("—", "Pilar", "Viga", "Diagonal", "Contraventamento", "Outro")
EIXO_M1 = "Momento 1"
EIXO_M2 = "Momento 2"
#: Qual ponta do pilar é a base (para o quadro de cargas das fundações).
BASE_AUTOMATICA = "Automática"
BASE_INICIO = "Início da lista"
BASE_FIM = "Fim da lista"
BASES: tuple[str, ...] = (BASE_AUTOMATICA, BASE_INICIO, BASE_FIM)

_FORCA_PARA_KN = {"n": 1e-3, "kn": 1.0, "lbf": 4.448222e-3, "kgf": 9.80665e-3, "tf": 9.80665}
_MOMENTO_PARA_KNM = {
    "n.m": 1e-3,
    "nm": 1e-3,
    "n.mm": 1e-6,
    "nmm": 1e-6,
    "kn.m": 1.0,
    "knm": 1.0,
    "lbf.in": 1.129848e-4,
    "lbf.ft": 1.355818e-3,
}
_COLUNAS = {
    "nome": ("nomedaviga", "beamname", "nome"),
    "elemento": ("elemento", "element"),
    "fim": ("fim", "end"),
    "axial": ("axial",),
    "v1": ("cisalhamento1", "shear1", "cortante1"),
    "v2": ("cisalhamento2", "shear2", "cortante2"),
    "m1": ("momento1", "moment1"),
    "m2": ("momento2", "moment2"),
    "t": ("torque", "torcao", "torsion"),
}


class ArquivoInvalido(ValueError):
    """Arquivo que o programa não reconhece; a mensagem diz o que exportar."""


# ---------------------------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PontoDeEsforco:
    """Esforço interno numa ponta de um elemento (tração positiva), em kN e kN·m."""

    elemento: str
    fim: str
    n: float
    v1: float
    v2: float
    m1: float
    m2: float
    t: float

    @property
    def chave(self) -> tuple[str, str]:
        return (self.elemento, self.fim)

    def vetor(self) -> tuple[float, float, float, float, float, float]:
        return (self.n, self.v1, self.v2, self.m1, self.m2, self.t)


@dataclass(frozen=True)
class Reacoes:
    """Soma das reações (kN e kN·m) nos eixos do modelo."""

    modelo: tuple[float, float, float]
    selecao: tuple[float, float, float] | None = None
    momento_modelo: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class ArquivoLido:
    tipo: str
    nome_arquivo: str
    estudo: str
    data: str
    assinatura: str  # SHA-256 do conteúdo, para saber se o mesmo arquivo foi enviado de novo
    membros: Mapping[str, tuple[PontoDeEsforco, ...]] = field(default_factory=dict)
    reacoes: Reacoes | None = None
    tensao_maxima_MPa: float | None = None
    avisos: tuple[str, ...] = ()


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _normal(texto: str) -> str:
    return re.sub(r"\s+", "", _sem_acento(texto).casefold())


def _unidade(cabecalho: str) -> str:
    achado = re.search(r"\(([^)]*)\)", cabecalho)
    return _normal(achado.group(1)).replace("·", ".") if achado else ""


def _decodificar(conteudo: bytes) -> str:
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252")


def numero(texto: str, *, decimal_virgula: bool = True) -> float | None:
    """Número do CSV: "78.611" → 78611, "-1.019,1" → −1019,1, "1,4815E+05" → 148150."""
    s = texto.strip().replace(" ", "").replace(" ", "")
    if not s or s in ("-", "—"):
        return None
    s = s.replace(".", "").replace(",", ".") if decimal_virgula else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _separador(linhas: Sequence[str]) -> str:
    for linha in linhas[:3]:
        if linha.strip().lower().startswith("sep="):
            return linha.strip()[4:5] or ";"
    amostra = "\n".join(linhas[:12])
    return ";" if amostra.count(";") >= amostra.count(",") else ","


def _estudo_e_data(linhas: Sequence[str]) -> tuple[str, str]:
    estudo, data = "", ""
    for linha in linhas[:8]:
        texto = linha.strip()
        normal = _normal(texto)
        if normal.startswith(("nomedoestudo", "studyname")):
            estudo = texto.split(":", 1)[1].strip() if ":" in texto else ""
        elif not data and re.search(r"\d{4}", texto) and ";" in texto and ":" in texto[:6]:
            data = texto.replace(";", ",").strip(" ,")
    return estudo, data


def ler_arquivo(conteudo: bytes, nome_arquivo: str = "") -> ArquivoLido:
    """Reconhece e lê um CSV do SolidWorks (forças da viga, reações ou tensões)."""
    texto = _decodificar(conteudo)
    linhas = texto.splitlines()
    if not linhas:
        raise ArquivoInvalido("O arquivo está vazio.")
    assinatura = hashlib.sha256(conteudo).hexdigest()
    sep = _separador(linhas)
    decimal_virgula = sep == ";"
    estudo, data = _estudo_e_data(linhas)
    normal_todo = _normal(texto[:3000])
    for indice, linha in enumerate(linhas[:30]):
        campos = [c.strip() for c in linha.split(sep)]
        if any(_normal(c).startswith("axial") for c in campos):
            membros, avisos = _ler_vigas(linhas[indice:], sep, decimal_virgula)
            return ArquivoLido(
                TIPO_VIGAS, nome_arquivo, estudo, data, assinatura, membros, avisos=avisos
            )
    if ("forcadereacao" in normal_todo or "reactionforce" in normal_todo) and (
        "somax" in normal_todo or "sumx" in normal_todo
    ):
        return ArquivoLido(
            TIPO_REACOES,
            nome_arquivo,
            estudo,
            data,
            assinatura,
            reacoes=_ler_reacoes(linhas, sep, decimal_virgula),
        )
    if "von" in normal_todo:
        return ArquivoLido(
            TIPO_TENSOES,
            nome_arquivo,
            estudo,
            data,
            assinatura,
            tensao_maxima_MPa=_tensao_maxima(linhas, sep, decimal_virgula),
        )
    raise ArquivoInvalido(
        f"{nome_arquivo or 'O arquivo'} não parece um CSV do SolidWorks: exporte por "
        "Resultados › Listar forças da viga (ou Listar forças resultantes) e salve como CSV."
    )


def _ler_vigas(
    linhas: Sequence[str], sep: str, decimal_virgula: bool
) -> tuple[dict[str, tuple[PontoDeEsforco, ...]], tuple[str, ...]]:
    cabecalho = [c.strip() for c in linhas[0].split(sep)]
    posicao: dict[str, int] = {}
    fatores: dict[str, float] = {}
    for i, titulo in enumerate(cabecalho):
        chave = re.sub(r"\(.*?\)", "", _normal(titulo))
        for nome, prefixos in _COLUNAS.items():
            if nome not in posicao and chave.startswith(prefixos):
                posicao[nome] = i
                unidade = _unidade(titulo)
                if nome in ("axial", "v1", "v2"):
                    if unidade not in _FORCA_PARA_KN:
                        raise ArquivoInvalido(f"Unidade de força desconhecida: {titulo!r}.")
                    fatores[nome] = _FORCA_PARA_KN[unidade]
                elif nome in ("m1", "m2", "t"):
                    if unidade not in _MOMENTO_PARA_KNM:
                        raise ArquivoInvalido(f"Unidade de momento desconhecida: {titulo!r}.")
                    fatores[nome] = _MOMENTO_PARA_KNM[unidade]
                break
    faltam = [n for n in ("nome", "fim", "axial", "v1", "v2", "m1", "m2", "t") if n not in posicao]
    if faltam:
        raise ArquivoInvalido(f"Faltam colunas no arquivo de forças da viga: {', '.join(faltam)}.")
    membros: dict[str, list[PontoDeEsforco]] = {}
    avisos: list[str] = []
    atual: str | None = None
    elemento = ""
    contador = 0
    for linha in linhas[1:]:
        campos = [c.strip() for c in linha.split(sep)]
        if len(campos) <= max(posicao.values()):
            continue
        nome = campos[posicao["nome"]]
        if nome and not campos[posicao["fim"]]:
            atual = nome
            membros.setdefault(atual, [])
            continue
        if atual is None:
            continue
        if posicao.get("elemento") is not None and campos[posicao["elemento"]]:
            elemento = campos[posicao["elemento"]]
        fim = campos[posicao["fim"]]
        if not fim:
            continue
        valores = {
            k: numero(campos[posicao[k]], decimal_virgula=decimal_virgula)
            for k in ("axial", "v1", "v2", "m1", "m2", "t")
        }
        if any(v is None for v in valores.values()):
            avisos.append(f"{atual}: linha sem número ignorada ({linha.strip()[:60]}).")
            continue
        contador += 1
        sinal = -1.0 if fim == "1" else 1.0  # força na ponta → esforço interno
        membros[atual].append(
            PontoDeEsforco(
                elemento or str(contador),
                fim,
                *(
                    sinal * float(valores[k] or 0.0) * fatores[k]
                    for k in ("axial", "v1", "v2", "m1", "m2", "t")
                ),
            )
        )
    vazios = [m for m, pontos in membros.items() if not pontos]
    for m in vazios:
        avisos.append(f"{m}: viga sem resultados no arquivo.")
        membros.pop(m)
    if not membros:
        raise ArquivoInvalido("O arquivo de forças da viga não tem nenhuma viga com resultados.")
    return {m: tuple(p) for m, p in membros.items()}, tuple(avisos)


def _ler_reacoes(linhas: Sequence[str], sep: str, decimal_virgula: bool) -> Reacoes:
    secao = ""
    fator = 1e-3
    somas: dict[str, dict[str, list[float | None]]] = {"forca": {}, "momento": {}}
    for linha in linhas:
        normal = _normal(linha)
        if normal.startswith(("forcadereacao", "reactionforce")):
            secao, fator = "forca", _FORCA_PARA_KN.get(_unidade(linha), 1e-3)
            continue
        if normal.startswith(("momentodereacao", "reactionmoment")):
            secao, fator = "momento", _MOMENTO_PARA_KNM.get(_unidade(linha), 1e-3)
            continue
        achado = re.match(r"^(soma|sum)([xyz])", normal)
        if secao and achado:
            campos = [c.strip() for c in linha.split(sep)]
            valores = [numero(c, decimal_virgula=decimal_virgula) for c in campos[1:3]]
            somas[secao][achado.group(2)] = [None if v is None else v * fator for v in valores]

    def vetor(secao_: str, coluna: int) -> tuple[float, float, float] | None:
        try:
            x, y, z = (somas[secao_][eixo][coluna] for eixo in "xyz")
        except (KeyError, IndexError):
            return None
        if x is None or y is None or z is None:
            return None
        return (x, y, z)

    modelo = vetor("forca", 1) or vetor("forca", 0)
    if modelo is None:
        raise ArquivoInvalido("O arquivo de reações não tem as somas X, Y e Z da força de reação.")
    return Reacoes(modelo=modelo, selecao=vetor("forca", 0), momento_modelo=vetor("momento", 1))


def _tensao_maxima(linhas: Sequence[str], sep: str, decimal_virgula: bool) -> float | None:
    fator = 1e-6  # N/m² → MPa
    for linha in linhas[:8]:
        if "n/mm" in _normal(linha):
            fator = 1.0
    valores = []
    for linha in linhas:
        campos = [c.strip() for c in linha.split(sep)]
        if len(campos) >= 5 and campos[0].isdigit():
            v = numero(campos[-1], decimal_virgula=decimal_virgula)
            if v is not None:
                valores.append(v * fator)
    return max(valores) if valores else None


# ---------------------------------------------------------------------------------------------
# Caso sugerido, perfil pelo nome e eixo forte
# ---------------------------------------------------------------------------------------------
def caso_sugerido(estudo: str, codigos: Iterable[str]) -> str | None:
    """O código do plano que aparece no nome do estudo ("W0 vento +X" → W0, "T- frio" → T−)."""
    disponiveis = {c.casefold(): c for c in codigos}

    def achar(pedaco: str) -> str | None:
        for candidato in (pedaco, pedaco.replace("-", "−"), pedaco.rstrip(".")):
            if candidato.casefold() in disponiveis:
                return disponiveis[candidato.casefold()]
        return None

    for pedaco in re.split(r"[\s_()/,:;]+", estudo.strip()):
        if not pedaco:
            continue
        achado = achar(pedaco) or next(
            (achar(parte) for parte in re.split(r"[-–—.]+", pedaco) if parte and achar(parte)),
            None,
        )
        if achado:
            return achado
    return None


def _catalogo() -> dict[str, float]:
    """Perfis do programa → massa (kg/m), para casar nomes americanos com o catálogo."""
    from core import cantoneiras as ct
    from core import section_catalog as sc

    nomes = {nome: perfil.massa_kg_m for nome, perfil in sc.listar_perfis().items()}
    nomes.update({nome: c.massa_kg_m for nome, c in ct.CATALOGO_CANTONEIRAS.items()})
    return nomes


_FRACOES = {0.125: "1/8", 0.1875: "3/16", 0.25: "1/4", 0.3125: "5/16", 0.375: "3/8", 0.5: "1/2"}


def _polegadas(valor: float) -> str:
    inteiro = int(valor)
    resto = round(valor - inteiro, 4)
    if resto == 0:
        return f"{inteiro}"
    fracao = _FRACOES.get(resto) or {0.5: "1/2"}.get(resto)
    return f"{inteiro} {fracao}" if inteiro and fracao else (fracao or f"{valor:g}")


def perfil_do_nome(nome: str) -> str | None:
    """O perfil do catálogo que o nome da viga do SolidWorks indica, se indicar.

    ``Canal c C8X13.75`` → o U 8" mais próximo em massa; ``Ângulo l L2.5X2.5X0.25`` → L 2 1/2" × 1/4";
    ``W8X31`` e ``W 200 x 35.9`` → o W do catálogo com a mesma altura nominal e a massa mais próxima.
    """
    catalogo = _catalogo()
    texto = nome.replace(",", ".")
    m = re.search(r"\bC(\d+)\s*[xX]\s*([\d.]+)", texto)
    if m:
        massa = float(m.group(2)) * 1.48816
        candidatos = {n: k for n, k in catalogo.items() if n.startswith(f'U {m.group(1)}"')}
        return min(candidatos, key=lambda n: abs(candidatos[n] - massa)) if candidatos else None
    m = re.search(r"\bL\s*([\d.]+)\s*[xX]\s*([\d.]+)\s*[xX]\s*([\d.]+)", texto)
    if m:
        aba, espessura = float(m.group(1)), float(m.group(3))
        candidato = f'L {_polegadas(aba)}" × {_polegadas(espessura)}"'
        return candidato if candidato in catalogo else None
    m = re.search(r"\bW\s*(\d+)\s*[xX]\s*([\d.]+)", texto)
    if m:
        altura, massa = float(m.group(1)), float(m.group(2))
        if altura < 50:  # polegadas e lb/ft
            altura, massa = altura * 25.4, massa * 1.48816
        candidatos = {
            n: k
            for n, k in catalogo.items()
            if n.startswith("W ") and abs(float(re.findall(r"\d+", n)[0]) - altura) <= 15
        }
        return min(candidatos, key=lambda n: abs(candidatos[n] - massa)) if candidatos else None
    return None


def eixo_forte_sugerido(pontos: Iterable[PontoDeEsforco]) -> str:
    """O momento que domina é, quase sempre, o do eixo forte."""
    lista = list(pontos)
    m1 = max((abs(p.m1) for p in lista), default=0.0)
    m2 = max((abs(p.m2) for p in lista), default=0.0)
    return EIXO_M2 if m2 >= m1 else EIXO_M1


# ---------------------------------------------------------------------------------------------
# Esforços importados no projeto
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CasoImportado:
    codigo: str
    estudo: str
    arquivo: str
    importado_em: str
    assinatura: str
    membros: Mapping[str, tuple[PontoDeEsforco, ...]]
    reacoes: Reacoes | None = None
    arquivo_reacoes: str = ""

    @property
    def elementos(self) -> int:
        return sum(len({p.elemento for p in pontos}) for pontos in self.membros.values())


@dataclass(frozen=True)
class ConfiguracaoDoMembro:
    """A barra na tabela: perfil, tipo, eixo forte e, se diferente do tipo, aço e comprimentos."""

    perfil: str = ""
    tipo: str = "—"
    eixo_forte: str = EIXO_M2
    aco: str = ""  # vazio = o do tipo
    lx_m: float | None = None  # comprimento de flambagem K·L em torno do eixo forte
    ly_m: float | None = None  # em torno do eixo fraco
    lb_m: float | None = None  # comprimento destravado da mesa comprimida (FLT)
    base: str = BASE_AUTOMATICA  # ponta da base do pilar no arquivo do SolidWorks


ACO_PADRAO = "ASTM A572 Gr 50"
NORMA_PADRAO = "NBR8800_2024"


@dataclass(frozen=True)
class ParametrosDoTipo:
    """O que vale para todas as barras de um tipo, salvo o que a barra informar."""

    aco: str = ACO_PADRAO
    lx_m: float | None = None
    ly_m: float | None = None
    lb_m: float | None = None  # vazio = L_y
    cb: float = 1.0
    b2: float = 1.0  # amplificação da 2ª ordem global (o estudo do SolidWorks é de 1ª ordem)


@dataclass(frozen=True)
class EsforcosDoModelo:
    casos: Mapping[str, CasoImportado] = field(default_factory=dict)
    membros: Mapping[str, ConfiguracaoDoMembro] = field(default_factory=dict)
    eixo_vertical: str = "Y"
    parametros: Mapping[str, ParametrosDoTipo] = field(default_factory=dict)
    norma: str = NORMA_PADRAO

    def parametros_do_tipo(self, tipo: str) -> ParametrosDoTipo:
        return self.parametros.get(tipo, ParametrosDoTipo())

    @property
    def nomes_dos_membros(self) -> list[str]:
        nomes: dict[str, None] = {}
        for caso in self.casos.values():
            nomes.update(dict.fromkeys(caso.membros))
        return list(nomes)


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def caso_do_arquivo(arquivo: ArquivoLido, codigo: str) -> CasoImportado:
    if arquivo.tipo != TIPO_VIGAS:
        raise ArquivoInvalido("Só o arquivo de forças da viga cria um caso.")
    return CasoImportado(
        codigo=codigo,
        estudo=arquivo.estudo,
        arquivo=arquivo.nome_arquivo,
        importado_em=agora(),
        assinatura=arquivo.assinatura,
        membros=dict(arquivo.membros),
    )


def com_caso(dados: EsforcosDoModelo, caso: CasoImportado) -> EsforcosDoModelo:
    """Inclui o caso (substitui o de mesmo código) e sugere perfil e eixo forte dos membros novos."""
    casos = dict(dados.casos)
    anterior = casos.get(caso.codigo)
    if anterior is not None and caso.reacoes is None and anterior.reacoes is not None:
        caso = replace(caso, reacoes=anterior.reacoes, arquivo_reacoes=anterior.arquivo_reacoes)
    casos[caso.codigo] = caso
    membros = dict(dados.membros)
    for nome, pontos in caso.membros.items():
        if nome not in membros:
            membros[nome] = ConfiguracaoDoMembro(
                perfil=perfil_do_nome(nome) or "", eixo_forte=eixo_forte_sugerido(pontos)
            )
    return replace(dados, casos=casos, membros=membros)


def com_reacoes(
    dados: EsforcosDoModelo, codigo: str, reacoes: Reacoes, arquivo: str
) -> EsforcosDoModelo:
    caso = dados.casos.get(codigo)
    if caso is None:
        raise ArquivoInvalido(
            f"Envie primeiro as forças da viga do caso {codigo}: as reações entram no mesmo caso."
        )
    casos = dict(dados.casos)
    casos[codigo] = replace(caso, reacoes=reacoes, arquivo_reacoes=arquivo)
    return replace(dados, casos=casos)


def sem_caso(dados: EsforcosDoModelo, codigo: str) -> EsforcosDoModelo:
    return replace(dados, casos={k: v for k, v in dados.casos.items() if k != codigo})


def com_membros(
    dados: EsforcosDoModelo, membros: Mapping[str, ConfiguracaoDoMembro]
) -> EsforcosDoModelo:
    return replace(dados, membros={**dados.membros, **membros})


def com_parametros(
    dados: EsforcosDoModelo, parametros: Mapping[str, ParametrosDoTipo], norma: str | None = None
) -> EsforcosDoModelo:
    return replace(dados, parametros={**dados.parametros, **parametros}, norma=norma or dados.norma)


def _r(valor: float) -> float:
    return float(f"{valor:.6g}")


def para_dicionario(dados: EsforcosDoModelo) -> dict[str, Any]:
    """Compacto: cada ponto é uma lista [elemento, fim, N, V1, V2, M1, M2, T]."""
    return {
        "eixo_vertical": dados.eixo_vertical,
        "casos": {
            codigo: {
                "estudo": c.estudo,
                "arquivo": c.arquivo,
                "importado_em": c.importado_em,
                "assinatura": c.assinatura,
                "arquivo_reacoes": c.arquivo_reacoes,
                "reacoes": None
                if c.reacoes is None
                else {
                    "modelo": list(c.reacoes.modelo),
                    "selecao": None if c.reacoes.selecao is None else list(c.reacoes.selecao),
                    "momento_modelo": None
                    if c.reacoes.momento_modelo is None
                    else list(c.reacoes.momento_modelo),
                },
                "membros": {
                    nome: [[p.elemento, p.fim, *(_r(v) for v in p.vetor())] for p in pontos]
                    for nome, pontos in c.membros.items()
                },
            }
            for codigo, c in dados.casos.items()
        },
        "membros": {
            nome: {
                "perfil": m.perfil,
                "tipo": m.tipo,
                "eixo_forte": m.eixo_forte,
                "aco": m.aco,
                "lx_m": m.lx_m,
                "ly_m": m.ly_m,
                "lb_m": m.lb_m,
                "base": m.base,
            }
            for nome, m in dados.membros.items()
        },
        "parametros": {
            tipo: {
                "aco": t.aco,
                "lx_m": t.lx_m,
                "ly_m": t.ly_m,
                "lb_m": t.lb_m,
                "cb": t.cb,
                "b2": t.b2,
            }
            for tipo, t in dados.parametros.items()
        },
        "norma": dados.norma,
    }


def _tripla(valor: Any) -> tuple[float, float, float] | None:
    if not isinstance(valor, Sequence) or len(valor) != 3:
        return None
    return (float(valor[0]), float(valor[1]), float(valor[2]))


def _comprimento(valor: Any) -> float | None:
    try:
        numero_ = float(valor)
    except (TypeError, ValueError):
        return None
    return numero_ if math.isfinite(numero_) and numero_ > 0 else None


def de_dicionario(dados: Mapping[str, Any] | None) -> EsforcosDoModelo:
    if not isinstance(dados, Mapping):
        return EsforcosDoModelo()
    casos: dict[str, CasoImportado] = {}
    for codigo, c in (dados.get("casos") or {}).items():
        if not isinstance(c, Mapping):
            continue
        r = c.get("reacoes")
        reacoes = None
        if isinstance(r, Mapping) and _tripla(r.get("modelo")) is not None:
            reacoes = Reacoes(
                modelo=_tripla(r["modelo"]),  # type: ignore[arg-type]
                selecao=_tripla(r.get("selecao")),
                momento_modelo=_tripla(r.get("momento_modelo")),
            )
        membros = {
            str(nome): tuple(
                PontoDeEsforco(str(p[0]), str(p[1]), *(float(v) for v in p[2:8]))
                for p in pontos
                if isinstance(p, Sequence) and len(p) >= 8
            )
            for nome, pontos in (c.get("membros") or {}).items()
        }
        casos[str(codigo)] = CasoImportado(
            codigo=str(codigo),
            estudo=str(c.get("estudo") or ""),
            arquivo=str(c.get("arquivo") or ""),
            importado_em=str(c.get("importado_em") or ""),
            assinatura=str(c.get("assinatura") or ""),
            membros=membros,
            reacoes=reacoes,
            arquivo_reacoes=str(c.get("arquivo_reacoes") or ""),
        )
    membros_cfg = {
        str(nome): ConfiguracaoDoMembro(
            perfil=str(m.get("perfil") or ""),
            tipo=str(m.get("tipo") or "—") if str(m.get("tipo") or "—") in TIPOS_DE_BARRA else "—",
            eixo_forte=str(m.get("eixo_forte") or EIXO_M2)
            if str(m.get("eixo_forte") or EIXO_M2) in (EIXO_M1, EIXO_M2)
            else EIXO_M2,
            aco=str(m.get("aco") or ""),
            lx_m=_comprimento(m.get("lx_m")),
            ly_m=_comprimento(m.get("ly_m")),
            lb_m=_comprimento(m.get("lb_m")),
            base=str(m.get("base") or BASE_AUTOMATICA)
            if str(m.get("base") or BASE_AUTOMATICA) in BASES
            else BASE_AUTOMATICA,
        )
        for nome, m in (dados.get("membros") or {}).items()
        if isinstance(m, Mapping)
    }
    parametros = {
        str(tipo): ParametrosDoTipo(
            aco=str(t.get("aco") or ACO_PADRAO),
            lx_m=_comprimento(t.get("lx_m")),
            ly_m=_comprimento(t.get("ly_m")),
            lb_m=_comprimento(t.get("lb_m")),
            cb=_comprimento(t.get("cb")) or 1.0,
            b2=_comprimento(t.get("b2")) or 1.0,
        )
        for tipo, t in (dados.get("parametros") or {}).items()
        if isinstance(t, Mapping)
    }
    return EsforcosDoModelo(
        casos,
        membros_cfg,
        str(dados.get("eixo_vertical") or "Y"),
        parametros,
        str(dados.get("norma") or NORMA_PADRAO),
    )


def esforcos_do_projeto(projeto: Mapping[str, Any] | None) -> EsforcosDoModelo:
    if not isinstance(projeto, Mapping):
        return EsforcosDoModelo()
    return de_dicionario(projeto.get("esforcos_do_modelo"))


# ---------------------------------------------------------------------------------------------
# Conferência das reações
# ---------------------------------------------------------------------------------------------
def para_o_plano(
    vetor: tuple[float, float, float], eixo_vertical: str
) -> tuple[float, float, float]:
    """Vetor nos eixos do modelo → eixos do plano (Z para cima). Inverso de ``para_os_eixos``."""
    x, y, z = vetor
    if eixo_vertical == "Y":
        return (x + 0.0, -z + 0.0, y + 0.0)
    return (x + 0.0, y + 0.0, z + 0.0)


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _so_vertical(acao: pc.Acao) -> bool:
    if acao.grupo == pc.GRUPO_VENTO or acao.categoria == pc.CATEGORIA_TEMPERATURA:
        return False
    return all(ex.eixo_da_direcao(c.direcao) == "Z" for c in acao.cargas)


def total_esperado(acao: pc.Acao) -> tuple[float, float, float] | None:
    """Soma das forças concentradas (kN) da ação, nos eixos do plano; ``None`` se não houver."""
    soma = [0.0, 0.0, 0.0]
    achou = False
    for c in acao.cargas:
        if c.unidade != "kN":
            continue
        vetor = ex.componentes_no_programa(c)
        if vetor is None:
            continue
        achou = True
        for i in range(3):
            soma[i] += vetor[i] * c.quantidade
    return (soma[0], soma[1], soma[2]) if achou else None


def conferir_reacoes(
    dados: EsforcosDoModelo, plano: pc.PlanoDeCargas
) -> list[pc.ItemDeConferencia]:
    """O modelo recebeu a carga do plano? Compara a soma das reações com as cargas, caso a caso."""
    itens: list[pc.ItemDeConferencia] = []
    for codigo, caso in dados.casos.items():
        if caso.reacoes is None:
            itens.append(
                pc.ItemDeConferencia(
                    pc.NIVEL_ATENCAO,
                    f"{codigo}: falta o arquivo de reações (Listar forças resultantes) para "
                    "conferir o equilíbrio.",
                )
            )
            continue
        rx, ry, rz = para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)
        horizontal = math.hypot(rx, ry)
        acao = plano.acao(codigo)
        if acao is None:
            itens.append(
                pc.ItemDeConferencia(
                    pc.NIVEL_ATENCAO,
                    f"{codigo}: o caso não está no plano de cargas — não entra nas combinações.",
                )
            )
            continue
        if _so_vertical(acao):
            if rz < 0:
                itens.append(
                    pc.ItemDeConferencia(
                        pc.NIVEL_ERRO,
                        f"{codigo}: a reação vertical soma {_n(rz)} kN, para baixo — a carga ou "
                        "a gravidade está no sentido trocado.",
                    )
                )
            limite = max(0.005 * abs(rz), 0.05)
            if horizontal > limite:
                itens.append(
                    pc.ItemDeConferencia(
                        pc.NIVEL_ATENCAO,
                        f"{codigo}: o plano só tem carga vertical, mas as reações horizontais somam "
                        f"{_n(horizontal)} kN ({_n(100 * horizontal / abs(rz) if rz else 0, 1)} % da "
                        f"vertical, {_n(rz)} kN). Confira cargas em faces inclinadas (pressão sai "
                        "normal à face), a direção de referência das forças e a direção da gravidade.",
                    )
                )
            else:
                itens.append(
                    pc.ItemDeConferencia(
                        pc.NIVEL_OK,
                        f"{codigo}: reação vertical de {_n(rz)} kN e horizontal desprezável "
                        f"({_n(horizontal)} kN).",
                    )
                )
        esperado = total_esperado(acao)
        if esperado is not None:
            residuo = math.dist((rx, ry, rz), tuple(-v for v in esperado))
            referencia = max(math.hypot(*esperado), 1e-9)
            if residuo <= max(0.02 * referencia, 0.1):
                itens.append(
                    pc.ItemDeConferencia(
                        pc.NIVEL_OK,
                        f"{codigo}: as reações equilibram as forças do plano ({_n(referencia)} kN).",
                    )
                )
            else:
                itens.append(
                    pc.ItemDeConferencia(
                        pc.NIVEL_ATENCAO,
                        f"{codigo}: o plano soma ({_n(esperado[0])}; {_n(esperado[1])}; "
                        f"{_n(esperado[2])}) kN em X, Y e Z, e as reações ({_n(rx)}; {_n(ry)}; "
                        f"{_n(rz)}) kN — diferença de {_n(residuo)} kN. Falta ou sobra carga no "
                        "modelo.",
                    )
                )
        por_area = [c for c in acao.cargas if c.unidade == "kN/m²" and c.valor > 0]
        if por_area and rz > 0:
            q = max(c.valor for c in por_area)
            itens.append(
                pc.ItemDeConferencia(
                    NIVEL_INFO,
                    f"{codigo}: {_n(rz)} kN de reação ÷ {_n(q)} kN/m² = {_n(rz / q, 1)} m² de "
                    "área carregada — confira com a área do piso.",
                )
            )
        if codigo == "PP" and not acao.cargas and rz > 0:
            itens.append(
                pc.ItemDeConferencia(
                    NIVEL_INFO, f"PP: peso do modelo = {_n(rz)} kN ({_n(rz / 9.81 * 1000, 0)} kg)."
                )
            )
    faltam = [c for c in plano.codigos if c not in dados.casos]
    if dados.casos and faltam:
        itens.append(
            pc.ItemDeConferencia(
                pc.NIVEL_ATENCAO,
                f"Do plano de cargas, ainda sem esforços do modelo: {', '.join(faltam)}. As "
                "combinações saem só com os casos importados.",
            )
        )
    return itens


# ---------------------------------------------------------------------------------------------
# Combinações e envoltória
# ---------------------------------------------------------------------------------------------
COMPONENTES = ("N", "V1", "V2", "M1", "M2", "T")


@dataclass(frozen=True)
class Extremo:
    valor: float
    combinacao: str
    ponto: str
    n: float
    m1: float
    m2: float


@dataclass(frozen=True)
class EnvoltoriaDoMembro:
    membro: str
    compressao: Extremo | None
    tracao: Extremo | None
    m1: Extremo
    m2: Extremo
    v: Extremo
    t: Extremo
    metodo: str  # "ponto a ponto", "pela ordem dos elementos" ou "soma dos máximos (conservador)"


@dataclass(frozen=True)
class ResultadoDaEnvoltoria:
    membros: tuple[EnvoltoriaDoMembro, ...]
    combinacoes: int
    casos: tuple[str, ...]
    avisos: tuple[str, ...] = ()


def _pontos_alinhados(
    membro: str, casos: Sequence[CasoImportado]
) -> tuple[list[list[tuple[float, ...]]], list[str], str] | None:
    """Os vetores de cada caso ponto a ponto: pela chave (elemento, fim) ou pela ordem."""
    listas = [caso.membros.get(membro, ()) for caso in casos]
    if any(not lista for lista in listas):
        return None
    chaves = [lista and [p.chave for p in lista] for lista in listas]
    if all(c == chaves[0] for c in chaves):
        rotulos = [f"elemento {p.elemento}, fim {p.fim}" for p in listas[0]]
        return [[p.vetor() for p in lista] for lista in listas], rotulos, "ponto a ponto"
    if all(len(lista) == len(listas[0]) for lista in listas):
        rotulos = [f"ponto {i + 1} de {len(listas[0])}" for i in range(len(listas[0]))]
        return [[p.vetor() for p in lista] for lista in listas], rotulos, "pela ordem dos elementos"
    return None


#: (combinação, ponto, (N, V1, V2, M1, M2, T)) — esforços de cálculo de uma barra.
Combinado = tuple[str, str, tuple[float, ...]]


@dataclass(frozen=True)
class PreparoDasCombinacoes:
    importados: tuple[str, ...]
    nomes: tuple[str, ...]
    fatores: tuple[tuple[float, ...], ...]
    casos: tuple[CasoImportado, ...]


def preparar_combinacoes(
    dados: EsforcosDoModelo, plano: pc.PlanoDeCargas, estados: Sequence[str]
) -> PreparoDasCombinacoes | None:
    """As combinações do plano só com os casos importados (``None`` se nenhum foi importado)."""
    importados = tuple(c for c in plano.codigos if c in dados.casos)
    if not importados:
        return None
    plano_filtrado = pc.PlanoDeCargas(tuple(a for a in plano.acoes if a.codigo in importados))
    lista = pc.combinacoes(plano_filtrado, estados)
    return PreparoDasCombinacoes(
        importados,
        tuple(ex.nome_da_combinacao(c, len(lista)) for c in lista),
        tuple(tuple(float(c.fatores.get(k, 0.0)) for k in importados) for c in lista),
        tuple(dados.casos[k] for k in importados),
    )


def combinados_do_membro(
    membro: str, preparo: PreparoDasCombinacoes
) -> tuple[list[Combinado], str, str | None]:
    """Os esforços de cálculo da barra em cada combinação e ponto, o método e o aviso (se houver)."""
    nomes, fatores, casos = preparo.nomes, preparo.fatores, preparo.casos
    alinhados = _pontos_alinhados(membro, casos)
    if alinhados is not None:
        vetores, rotulos, metodo = alinhados
        aviso = (
            None
            if metodo == "ponto a ponto"
            else f"{membro}: a numeração dos elementos muda entre os estudos; combinei pela "
            "ordem. Use a mesma malha em todos os estudos (duplique o estudo)."
        )
        combinados = [
            (
                nomes[i],
                rotulos[j],
                tuple(
                    sum(f * vetores[k][j][comp] for k, f in enumerate(fatores[i]))
                    for comp in range(6)
                ),
            )
            for i in range(len(nomes))
            for j in range(len(rotulos))
        ]
        return combinados, metodo, aviso
    combinados = []
    for i in range(len(nomes)):
        for sentido in (-1.0, 1.0):
            vetor = []
            for comp in range(6):
                total = 0.0
                for k, f in enumerate(fatores[i]):
                    valores = [p.vetor()[comp] for p in casos[k].membros.get(membro, ())] or [0.0]
                    escolhido = max(valores) if f * sentido >= 0 else min(valores)
                    total += f * escolhido
                vetor.append(total)
            combinados.append((nomes[i], "envoltória dos pontos", tuple(vetor)))
    return (
        combinados,
        "soma dos máximos (conservador)",
        f"{membro}: não está em todos os casos com os mesmos elementos — usei a soma dos máximos "
        "de cada caso (a favor da segurança).",
    )


def envoltoria(
    dados: EsforcosDoModelo, plano: pc.PlanoDeCargas, estados: Sequence[str]
) -> ResultadoDaEnvoltoria:
    """Combina os casos importados com os fatores do plano e acha o pior de cada barra."""
    preparo = preparar_combinacoes(dados, plano, estados)
    if preparo is None:
        return ResultadoDaEnvoltoria((), 0, (), ("Nenhum caso do plano de cargas foi importado.",))
    avisos: list[str] = []
    membros: list[EnvoltoriaDoMembro] = []
    for membro in dados.nomes_dos_membros:
        combinados, metodo, aviso = combinados_do_membro(membro, preparo)
        if aviso:
            avisos.append(aviso)

        def extremo(chave: Any, combinados_: Sequence[Combinado]) -> Extremo:
            nome, ponto, v = max(combinados_, key=chave)
            return Extremo(chave((nome, ponto, v)), nome, ponto, v[0], v[3], v[4])

        menor_n = min(combinados, key=lambda x: x[2][0])
        maior_n = max(combinados, key=lambda x: x[2][0])
        compressao = (
            Extremo(
                menor_n[2][0], menor_n[0], menor_n[1], menor_n[2][0], menor_n[2][3], menor_n[2][4]
            )
            if menor_n[2][0] < 0
            else None
        )
        tracao = (
            Extremo(
                maior_n[2][0], maior_n[0], maior_n[1], maior_n[2][0], maior_n[2][3], maior_n[2][4]
            )
            if maior_n[2][0] > 0
            else None
        )
        membros.append(
            EnvoltoriaDoMembro(
                membro,
                compressao,
                tracao,
                extremo(lambda x: abs(x[2][3]), combinados),
                extremo(lambda x: abs(x[2][4]), combinados),
                extremo(lambda x: math.hypot(x[2][1], x[2][2]), combinados),
                extremo(lambda x: abs(x[2][5]), combinados),
                metodo,
            )
        )
    sobram = [c for c in dados.casos if c not in plano.codigos]
    if sobram:
        avisos.append(
            f"Casos importados fora do plano de cargas (não combinados): {', '.join(sobram)}."
        )
    return ResultadoDaEnvoltoria(
        tuple(membros), len(preparo.nomes), preparo.importados, tuple(avisos)
    )


def momento_forte_e_fraco(e: EnvoltoriaDoMembro, eixo_forte: str) -> tuple[Extremo, Extremo]:
    return (e.m2, e.m1) if eixo_forte == EIXO_M2 else (e.m1, e.m2)


COLUNAS_ENVOLTORIA = (
    "Barra",
    "Tipo",
    "Perfil",
    "Compressão máx. (kN)",
    "Combinação (compressão)",
    "Tração máx. (kN)",
    "Combinação (tração)",
    "M forte máx. (kN·m)",
    "Combinação (M forte)",
    "N junto (kN)",
    "M fraco máx. (kN·m)",
    "Cortante máx. (kN)",
    "Torque máx. (kN·m)",
    "Ponto do M forte",
    "Como combinou",
)


def linhas_da_envoltoria(
    dados: EsforcosDoModelo, resultado: ResultadoDaEnvoltoria
) -> list[list[object]]:
    linhas: list[list[object]] = []
    for e in resultado.membros:
        cfg = dados.membros.get(e.membro, ConfiguracaoDoMembro())
        forte, fraco = momento_forte_e_fraco(e, cfg.eixo_forte)
        linhas.append(
            [
                e.membro,
                cfg.tipo,
                cfg.perfil or "—",
                "" if e.compressao is None else e.compressao.valor,
                "" if e.compressao is None else e.compressao.combinacao,
                "" if e.tracao is None else e.tracao.valor,
                "" if e.tracao is None else e.tracao.combinacao,
                forte.valor,
                forte.combinacao,
                forte.n,
                fraco.valor,
                e.v.valor,
                e.t.valor,
                forte.ponto,
                e.metodo,
            ]
        )
    return linhas


def csv_da_envoltoria(dados: EsforcosDoModelo, resultado: ResultadoDaEnvoltoria) -> bytes:
    return pc._csv(COLUNAS_ENVOLTORIA, linhas_da_envoltoria(dados, resultado))
