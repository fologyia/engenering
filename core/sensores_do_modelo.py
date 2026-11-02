"""Sensores do SolidWorks: o quadro da Vista de resultados do gerenciador de casos de carga, lido,
conferido contra o plano de cargas e verificado para o memorial.

A macro ``exportar_casos_de_carga`` grava ``<estudo>-gerenciador-resultados.csv``: uma coluna por
sensor (as colunas da Vista de resultados), uma linha por caso primário e por combinação, com o
valor como a API do SOLIDWORKS devolve — na unidade do sensor, que o arquivo não diz. Aqui:

* o quadro é lido (``sep=;``, vírgula decimal, cp1252 ou UTF-8; célula vazia = a API não
  respondeu) e cada sensor ganha a grandeza (tensão, deslocamento, fator de segurança, força…) e
  a unidade sugeridas pelo nome, que o usuário confirma. O produto ``σ·FS`` dá o f_y do aço no
  ponto do FS mínimo e confere a unidade da tensão;
* cada combinação ``C07-ELU`` é ligada à do plano de cargas pelo nome que o programa exportou, e o
  quadro é conferido: casos do plano que o estudo não tem, combinações que não vieram, linhas com
  o mesmo resultado em todos os sensores (as que diferem só em casos fora do estudo são
  explicadas; as outras não são resultado e ficam fora da verificação) e a superposição — o
  máximo de uma combinação não passa de ``Σ|γ|·v`` dos casos, e o FS não fica abaixo de
  ``1/Σ(|γ|/FS)`` (vale ponto a ponto, mesmo com dois aços);
* nas ELU, o escoamento: ``σ ≤ f_y/γ_a1`` e ``FS ≥ γ_a1``; nas ELS, o deslocamento contra o limite
  escolhido para o sensor (critério Anglo, Tabelas 3 e 4, ou informado);
* o registro do memorial leva as tabelas e o gráfico de cada sensor, combinação a combinação.

Um sensor é o máximo (ou o mínimo) do modelo inteiro, ou de onde ele foi posto. A tensão elástica do
modelo não verifica flambagem, flambagem lateral com torção nem a interação N + M da NBR 8800: isso
é a verificação barra a barra (Esforços do modelo).

Sem Streamlit.
"""

from __future__ import annotations

import csv
import io
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from core import criterio_anglo as ca
from core import esforcos_modelo as em
from core import exportacao_cargas as ex
from core import gerenciador_solidworks as gs
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "sensores_do_modelo"
MODULO_TITULO = "Sensores do modelo"
CAMPO_DO_PROJETO = "sensores_do_modelo"
GAMA_A1 = 1.10
REFERENCIA_GAMA = "ABNT NBR 8800:2025 — γ_a1 = 1,10 (Tabela 3)"
REFERENCIA_CONFERENCIA = "Plano de cargas × gerenciador de casos de carga do SolidWorks"

NIVEL_ERRO = pc.NIVEL_ERRO
NIVEL_ATENCAO = pc.NIVEL_ATENCAO
NIVEL_OK = pc.NIVEL_OK
NIVEL_INFO = em.NIVEL_INFO

# ---------------------------------------------------------------------------------------------
# O que cada sensor mede e em que unidade
# ---------------------------------------------------------------------------------------------
TENSAO = "tensão"
COMPONENTE = "componente de tensão"
DESLOCAMENTO = "deslocamento"
FATOR_DE_SEGURANCA = "fator de segurança"
FORCA = "força"
MOMENTO = "momento"
OUTRA = "outra"
GRANDEZAS = (TENSAO, COMPONENTE, DESLOCAMENTO, FATOR_DE_SEGURANCA, FORCA, MOMENTO, OUTRA)
ROTULOS_GRANDEZA = {
    TENSAO: "Tensão (von Mises ou limite superior)",
    COMPONENTE: "Componente de tensão (axial, flexão, cisalhamento)",
    DESLOCAMENTO: "Deslocamento",
    FATOR_DE_SEGURANCA: "Fator de segurança",
    FORCA: "Força",
    MOMENTO: "Momento",
    OUTRA: "Outra grandeza",
}
GRANDEZA_DO_ROTULO = {rotulo: g for g, rotulo in ROTULOS_GRANDEZA.items()}

MPA = "MPa (N/mm²)"
_TENSOES = {MPA: 1.0, "kPa": 1e-3, "Pa (N/m²)": 1e-6, "psi": 6.894757293168361e-3, "ksi": 6.894757}
#: Unidade do arquivo → fator para a unidade de cálculo (MPa, mm, kN, kN·m).
UNIDADES: dict[str, dict[str, float]] = {
    TENSAO: dict(_TENSOES),
    COMPONENTE: dict(_TENSOES),
    DESLOCAMENTO: {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4},
    FATOR_DE_SEGURANCA: {"—": 1.0},
    FORCA: {"kN": 1.0, "N": 1e-3, "kgf": 9.80665e-3, "tf": 9.80665, "lbf": 4.4482216152605e-3},
    MOMENTO: {
        "kN·m": 1.0,
        "N·m": 1e-3,
        "N·mm": 1e-6,
        "kgf·m": 9.80665e-3,
        "lbf·in": 1.129848290276167e-4,
    },
    OUTRA: {"—": 1.0},
}
UNIDADE_DE_CALCULO = {
    TENSAO: "MPa",
    COMPONENTE: "MPa",
    DESLOCAMENTO: "mm",
    FATOR_DE_SEGURANCA: "",
    FORCA: "kN",
    MOMENTO: "kN·m",
    OUTRA: "",
}
TODAS_AS_UNIDADES = tuple(dict.fromkeys(u for g in GRANDEZAS for u in UNIDADES[g]))
CASAS = {
    TENSAO: 2,
    COMPONENTE: 2,
    DESLOCAMENTO: 3,
    FATOR_DE_SEGURANCA: 2,
    FORCA: 3,
    MOMENTO: 3,
    OUTRA: 4,
}

#: Pedaços do nome (sem acento, sem espaço, minúsculo) → grandeza, na ordem em que se testa.
_PISTAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (FATOR_DE_SEGURANCA, ("seguranca", "fatorminimo", "factorofsafety", "fos")),
    (DESLOCAMENTO, ("desloc", "displac", "flecha", "deflect")),
    (FORCA, ("forca", "force", "reac")),
    (MOMENTO, ("moment",)),
    (
        COMPONENTE,
        ("axial", "flex", "bending", "torc", "torsion", "cisalh", "shear", "dir1", "dir2"),
    ),
    (TENSAO, ("tens", "mises", "stress", "limitesuperior", "upperbound")),
)
_UNIDADE_DO_TEXTO = {
    "mpa": MPA,
    "n/mm^2": MPA,
    "n/mm2": MPA,
    "n/mm²": MPA,
    "kpa": "kPa",
    "pa": "Pa (N/m²)",
    "n/m^2": "Pa (N/m²)",
    "n/m2": "Pa (N/m²)",
    "n/m²": "Pa (N/m²)",
    "psi": "psi",
    "ksi": "ksi",
    "mm": "mm",
    "cm": "cm",
    "m": "m",
    "in": "in",
    "kn": "kN",
    "n": "N",
    "kgf": "kgf",
    "tf": "tf",
    "lbf": "lbf",
    "kn.m": "kN·m",
    "kn·m": "kN·m",
    "n.m": "N·m",
    "n·m": "N·m",
    "n.mm": "N·mm",
    "n·mm": "N·mm",
    "kgf.m": "kgf·m",
    "lbf.in": "lbf·in",
}


def grandeza_sugerida(nome: str) -> str:
    """Pelo nome do sensor: "Tensão vigas" → tensão, "Deslocamento1" → deslocamento…"""
    n = em._normal(nome)
    if re.fullmatch(r"fs\d*", n):
        return FATOR_DE_SEGURANCA
    if re.fullmatch(r"u(x|y|z|res)\d*", n):
        return DESLOCAMENTO
    for grandeza, pistas in _PISTAS:
        if any(p in n for p in pistas):
            return grandeza
    return OUTRA


def unidade_padrao(grandeza: str) -> str:
    return next(iter(UNIDADES.get(grandeza, UNIDADES[OUTRA])))


def unidade_do_texto(texto: str, grandeza: str) -> str | None:
    """A unidade escrita no arquivo (``N/mm^2``, ``mm``…), se for uma desta grandeza."""
    unidade = _UNIDADE_DO_TEXTO.get(em._normal(texto).replace("·", "."))
    if unidade is None:
        unidade = _UNIDADE_DO_TEXTO.get(em._normal(texto))
    return unidade if unidade in UNIDADES.get(grandeza, {}) else None


# ---------------------------------------------------------------------------------------------
# Limite do deslocamento
# ---------------------------------------------------------------------------------------------
SEM_LIMITE = "Sem limite (só informar o valor)"
L_SOBRE_X = "Informar L/x"
EM_MM = "Informar o limite em mm"


def _rotulo_do_limite(limite: ca.LimiteDeDeslocamento) -> str:
    return f"{limite.descricao} — {limite.texto} (Anglo, {limite.tabela})"


LIMITES_ANGLO: dict[str, ca.LimiteDeDeslocamento] = {
    _rotulo_do_limite(lim): lim
    for lim in (*ca.DESLOCAMENTOS_VERTICAIS, *ca.DESLOCAMENTOS_HORIZONTAIS)
}
OPCOES_DE_LIMITE = (SEM_LIMITE, *LIMITES_ANGLO, L_SOBRE_X, EM_MM)


@dataclass(frozen=True)
class LimiteDoDeslocamento:
    """O limite de um sensor de deslocamento: um item do critério Anglo (com o vão ou a altura),
    um ``L/x`` informado ou um valor em mm."""

    opcao: str = SEM_LIMITE
    comprimento_m: float | None = None
    divisor: float | None = None
    maximo_mm: float | None = None

    @property
    def anglo(self) -> ca.LimiteDeDeslocamento | None:
        return LIMITES_ANGLO.get(self.opcao)

    @property
    def base(self) -> str:
        anglo = self.anglo
        return anglo.base if anglo is not None else "L"

    def limite_mm(self) -> float | None:
        anglo = self.anglo
        comprimento = _positivo(self.comprimento_m)
        if anglo is not None:
            if comprimento is None:
                return anglo.maximo_mm if anglo.divisor is None else None
            valor = anglo.limite_mm(comprimento * 1000.0)
            return valor if math.isfinite(valor) else None
        if self.opcao == L_SOBRE_X:
            divisor = _positivo(self.divisor)
            if comprimento is None or divisor is None:
                return None
            return comprimento * 1000.0 / divisor
        if self.opcao == EM_MM:
            return _positivo(self.maximo_mm)
        return None

    def falta(self) -> str:
        """O que falta preencher para haver limite ("" se nada)."""
        if self.opcao == SEM_LIMITE:
            return ""
        if self.limite_mm() is not None:
            return ""
        if self.opcao == EM_MM:
            return "o limite em mm"
        if self.opcao == L_SOBRE_X and _positivo(self.divisor) is None:
            return "o x de L/x"
        return f"o comprimento {self.base}"

    def texto(self) -> str:
        """Ex.: "L/350 com L = 6,00 m = 17,14 mm (Vigas de piso principais, Anglo Tabela 3)"."""
        limite = self.limite_mm()
        if limite is None:
            return "sem limite"
        anglo = self.anglo
        comprimento = _positivo(self.comprimento_m)
        if anglo is not None:
            partes = []
            if anglo.divisor and comprimento is not None:
                partes.append(
                    f"{anglo.base}/{anglo.divisor:g} com {anglo.base} = {_n(comprimento)} m"
                )
            if anglo.maximo_mm:
                partes.append(f"máx. {anglo.maximo_mm:g} mm")
            return (
                f"{'; '.join(partes)} → {_n(limite)} mm ({anglo.descricao}, Anglo {anglo.tabela})"
            )
        if self.opcao == L_SOBRE_X and comprimento is not None:
            return f"L/{self.divisor:g} com L = {_n(comprimento)} m → {_n(limite)} mm (informado)"
        return f"{_n(limite)} mm (informado)"

    def referencia(self) -> str:
        anglo = self.anglo
        if anglo is not None:
            return f"{ca.REFERENCIA}, {anglo.tabela}"
        return "Limite informado pelo projetista"


# ---------------------------------------------------------------------------------------------
# O quadro
# ---------------------------------------------------------------------------------------------
class QuadroInvalido(ValueError):
    """O arquivo não é o quadro dos sensores, ou não tem o que ler."""


@dataclass(frozen=True)
class Sensor:
    nome: str
    grandeza: str = OUTRA
    unidade: str = "—"
    limite: LimiteDoDeslocamento = field(default_factory=LimiteDoDeslocamento)

    @property
    def fator(self) -> float:
        return UNIDADES.get(self.grandeza, UNIDADES[OUTRA]).get(self.unidade, 1.0)

    @property
    def unidade_de_calculo(self) -> str:
        return UNIDADE_DE_CALCULO.get(self.grandeza, "")

    @property
    def rotulo(self) -> str:
        unidade = self.unidade_de_calculo
        return f"{self.nome} ({unidade})" if unidade else self.nome


@dataclass(frozen=True)
class LinhaDoQuadro:
    """Um caso primário ou uma combinação: o valor de cada sensor como veio no arquivo."""

    nome: str
    primario: bool
    valores: tuple[float | None, ...]


@dataclass(frozen=True)
class QuadroDeSensores:
    arquivo: str = ""
    estudo: str = ""
    lido_em: str = ""
    sensores: tuple[Sensor, ...] = ()
    linhas: tuple[LinhaDoQuadro, ...] = ()
    fy_MPa: float | None = None  # None: o do σ·FS (ou 250 MPa)
    avisos: tuple[str, ...] = ()

    @property
    def vazio(self) -> bool:
        return not self.sensores or not self.linhas

    @property
    def casos(self) -> tuple[LinhaDoQuadro, ...]:
        return tuple(linha for linha in self.linhas if linha.primario)

    @property
    def combinacoes(self) -> tuple[LinhaDoQuadro, ...]:
        return tuple(linha for linha in self.linhas if not linha.primario)

    def valor(self, linha: LinhaDoQuadro, k: int) -> float | None:
        """O valor do sensor ``k`` na unidade de cálculo (MPa, mm, kN, kN·m)."""
        bruto = linha.valores[k] if k < len(linha.valores) else None
        return None if bruto is None else bruto * self.sensores[k].fator


def _numero(texto: str) -> float | None:
    s = texto.strip().replace(" ", "").replace(" ", "")
    if not s or s in ("-", "—"):
        return None
    try:
        valor = float(s.replace(",", "."))
    except ValueError:
        return None
    return valor if math.isfinite(valor) else None


e_quadro = gs.e_quadro_dos_sensores


def agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def ler_quadro(conteudo: bytes, nome_arquivo: str = "") -> QuadroDeSensores:
    """O ``<estudo>-gerenciador-resultados.csv`` da macro, ou o mesmo quadro salvo à mão."""
    texto = em._decodificar(conteudo)
    linhas = [linha for linha in texto.splitlines()]
    sep = ";"
    if linhas and linhas[0].strip().lower().startswith("sep="):
        sep = linhas[0].strip()[4:5] or ";"
    estudo = ""
    titulos: list[str] | None = None
    inicio = 0
    for i, linha in enumerate(linhas):
        celulas = linha.split(sep)
        primeira = em._normal(celulas[0]) if celulas else ""
        if primeira.startswith("nomedoestudo"):
            estudo = linha.split(":", 1)[1].strip() if ":" in linha else ""
        elif primeira in ("caso", "casodecarga", "loadcase") and len(celulas) >= 3:
            titulos = [c.strip() for c in celulas]
            inicio = i + 1
            break
    if titulos is None:
        raise QuadroInvalido(
            "não achei a linha de títulos do quadro (Caso;Tipo;sensor 1;sensor 2…). Este arquivo é "
            "o <estudo>-gerenciador-resultados.csv da macro exportar_casos_de_carga?"
        )
    nomes = titulos[2:]
    while nomes and not nomes[-1]:
        nomes.pop()
    if not nomes:
        raise QuadroInvalido("o quadro não tem nenhum sensor (nenhuma coluna depois de Caso;Tipo).")
    vistos: dict[str, int] = {}
    sensores: list[Sensor] = []
    for k, nome in enumerate(nomes):
        nome = nome or f"Sensor {k + 1}"
        vistos[nome] = vistos.get(nome, 0) + 1
        if vistos[nome] > 1:
            nome = f"{nome} ({vistos[nome]})"
        grandeza = grandeza_sugerida(nome)
        sensores.append(Sensor(nome, grandeza, unidade_padrao(grandeza)))
    avisos: list[str] = []
    lidas: list[LinhaDoQuadro] = []
    nomes_vistos: set[str] = set()
    for linha in linhas[inicio:]:
        celulas = [c.strip() for c in linha.split(sep)]
        if not celulas or not celulas[0]:
            continue
        primeira = em._normal(celulas[0])
        if primeira in ("unidade", "unidades", "unit", "units"):
            for k, s in enumerate(sensores):
                escrita = celulas[k + 2] if k + 2 < len(celulas) else ""
                unidade = unidade_do_texto(escrita, s.grandeza) if escrita else None
                if unidade:
                    sensores[k] = replace(s, unidade=unidade)
            continue
        nome = celulas[0]
        if nome in nomes_vistos:
            avisos.append(f"{nome} aparece duas vezes no quadro: ficou a primeira linha.")
            continue
        tipo = em._normal(celulas[1]) if len(celulas) > 1 else ""
        if tipo.startswith("caso") or tipo.startswith("primar"):
            primario = True
        elif tipo.startswith("comb") or tipo.startswith("secund"):
            primario = False
        else:
            primario = re.match(r"^C\d+-", nome) is None
        valores = tuple(
            _numero(celulas[k + 2]) if k + 2 < len(celulas) else None for k in range(len(sensores))
        )
        nomes_vistos.add(nome)
        lidas.append(LinhaDoQuadro(nome, primario, valores))
    if not lidas:
        raise QuadroInvalido("o quadro não tem nenhuma linha de caso ou de combinação.")
    vazias = [linha.nome for linha in lidas if all(v is None for v in linha.valores)]
    if vazias:
        avisos.append(
            f"Sem nenhum valor (a API do SolidWorks não respondeu): {lista_curta(vazias)}. Rode o "
            "gerenciador (Executar) antes da macro."
        )
    return QuadroDeSensores(
        arquivo=nome_arquivo,
        estudo=estudo,
        lido_em=agora(),
        sensores=tuple(sensores),
        linhas=tuple(lidas),
        avisos=tuple(avisos),
    )


def com_ajustes(
    quadro: QuadroDeSensores,
    sensores: Sequence[Sensor] | None = None,
    *,
    fy_MPa: float | None = None,
) -> QuadroDeSensores:
    """O quadro com a grandeza, a unidade e o limite que o usuário confirmou, e o f_y."""
    novos = quadro.sensores
    if sensores is not None:
        por_nome = {s.nome: s for s in sensores}
        novos = tuple(_sensor_valido(por_nome.get(s.nome, s)) for s in quadro.sensores)
    return replace(quadro, sensores=novos, fy_MPa=_positivo(fy_MPa))


def manter_ajustes(novo: QuadroDeSensores, antigo: QuadroDeSensores) -> QuadroDeSensores:
    """Ao trocar o arquivo, os sensores de mesmo nome ficam como o usuário tinha deixado; o mesmo
    arquivo de novo (mesmos sensores e valores) é o quadro já gravado."""
    if antigo.vazio:
        return novo
    if [s.nome for s in novo.sensores] == [s.nome for s in antigo.sensores] and (
        novo.linhas == antigo.linhas
    ):
        return antigo
    return com_ajustes(novo, antigo.sensores, fy_MPa=antigo.fy_MPa)


def _sensor_valido(s: Sensor) -> Sensor:
    grandeza = s.grandeza if s.grandeza in GRANDEZAS else OUTRA
    unidade = s.unidade if s.unidade in UNIDADES[grandeza] else unidade_padrao(grandeza)
    limite = s.limite if grandeza == DESLOCAMENTO else LimiteDoDeslocamento()
    if limite.opcao not in OPCOES_DE_LIMITE:
        limite = LimiteDoDeslocamento()
    return Sensor(s.nome, grandeza, unidade, limite)


# ---------------------------------------------------------------------------------------------
# Gravar no projeto
# ---------------------------------------------------------------------------------------------
def para_dicionario(quadro: QuadroDeSensores) -> dict[str, Any]:
    return {
        "versao": 1,
        "arquivo": quadro.arquivo,
        "estudo": quadro.estudo,
        "lido_em": quadro.lido_em,
        "fy_MPa": quadro.fy_MPa,
        "avisos": list(quadro.avisos),
        "sensores": [
            {
                "nome": s.nome,
                "grandeza": s.grandeza,
                "unidade": s.unidade,
                "limite": {
                    "opcao": s.limite.opcao,
                    "comprimento_m": s.limite.comprimento_m,
                    "divisor": s.limite.divisor,
                    "maximo_mm": s.limite.maximo_mm,
                },
            }
            for s in quadro.sensores
        ],
        "linhas": [
            {"nome": linha.nome, "primario": linha.primario, "valores": list(linha.valores)}
            for linha in quadro.linhas
        ],
    }


def _positivo(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        return None
    try:
        numero = float(valor)
    except ValueError:
        return None
    return numero if math.isfinite(numero) and numero > 0 else None


def _finito(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    numero = float(valor)
    return numero if math.isfinite(numero) else None


def _texto(valor: Any) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def de_dicionario(dados: Any) -> QuadroDeSensores:
    """O quadro gravado; o que estiver fora do formato é ignorado (o quadro nunca derruba a página)."""
    if not isinstance(dados, Mapping):
        return QuadroDeSensores()
    sensores: list[Sensor] = []
    brutos = dados.get("sensores")
    for item in brutos if isinstance(brutos, list) else []:
        if not isinstance(item, Mapping) or not _texto(item.get("nome")):
            continue
        limite_bruto = item.get("limite")
        if not isinstance(limite_bruto, Mapping):
            limite_bruto = {}
        limite = LimiteDoDeslocamento(
            _texto(limite_bruto.get("opcao")) or SEM_LIMITE,
            _positivo(limite_bruto.get("comprimento_m")),
            _positivo(limite_bruto.get("divisor")),
            _positivo(limite_bruto.get("maximo_mm")),
        )
        sensores.append(
            _sensor_valido(
                Sensor(
                    _texto(item.get("nome")),
                    _texto(item.get("grandeza")) or OUTRA,
                    _texto(item.get("unidade")),
                    limite,
                )
            )
        )
    linhas: list[LinhaDoQuadro] = []
    brutas = dados.get("linhas")
    for item in brutas if isinstance(brutas, list) else []:
        if not isinstance(item, Mapping) or not _texto(item.get("nome")):
            continue
        valores = item.get("valores")
        lista = valores if isinstance(valores, list) else []
        linhas.append(
            LinhaDoQuadro(
                _texto(item.get("nome")),
                bool(item.get("primario")),
                tuple(_finito(lista[k]) if k < len(lista) else None for k in range(len(sensores))),
            )
        )
    avisos = dados.get("avisos")
    return QuadroDeSensores(
        arquivo=_texto(dados.get("arquivo")),
        estudo=_texto(dados.get("estudo")),
        lido_em=_texto(dados.get("lido_em")),
        sensores=tuple(sensores),
        linhas=tuple(linhas),
        fy_MPa=_positivo(dados.get("fy_MPa")),
        avisos=tuple(a for a in avisos if isinstance(a, str)) if isinstance(avisos, list) else (),
    )


def quadro_do_projeto(projeto: Mapping[str, Any] | None) -> QuadroDeSensores:
    if not isinstance(projeto, Mapping):
        return QuadroDeSensores()
    return de_dicionario(projeto.get(CAMPO_DO_PROJETO))


# ---------------------------------------------------------------------------------------------
# Ligação com o plano de cargas
# ---------------------------------------------------------------------------------------------
SIGLA_DO_ESTADO = dict(ex.SIGLAS)
ESTADO_DA_SIGLA = {sigla: estado for estado, sigla in ex.SIGLAS.items()}
_ORDEM_DOS_ESTADOS = (*comb.COMBINACOES_ULTIMAS, *comb.COMBINACOES_DE_SERVICO)
_NOME_DA_COMBINACAO = re.compile(r"^C(\d+)-([A-Z]+)$")


def estado_pela_sigla(nome: str) -> str:
    """``C07-ELU`` → "ELU normal"; "" se o nome não tem a sigla do programa."""
    achado = _NOME_DA_COMBINACAO.match(nome.strip())
    return ESTADO_DA_SIGLA.get(achado.group(2), "") if achado else ""


def tipo_do_estado(estado: str) -> str:
    if estado in comb.COMBINACOES_ULTIMAS:
        return "ELU"
    if estado in comb.COMBINACOES_DE_SERVICO:
        return "ELS"
    return ""


@dataclass(frozen=True)
class CombinacaoDoPlano:
    nome: str
    estado: str
    fatores: Mapping[str, float]  # código como no SolidWorks → γ
    expressao: str


@dataclass(frozen=True)
class LigacaoAoPlano:
    combinacoes: Mapping[str, CombinacaoDoPlano] = field(default_factory=dict)
    faltam: tuple[str, ...] = ()  # no plano, com caso no estudo, e não vieram
    sobram: tuple[str, ...] = ()  # vieram e não estão no plano
    codigos: tuple[str, ...] = ()  # os casos do plano, como no SolidWorks


def _permutacoes(estados: Sequence[str]) -> list[tuple[str, ...]]:
    from itertools import permutations

    if len(estados) > 4:
        return [tuple(estados)]
    return [tuple(p) for p in permutations(estados)]


def ligar_ao_plano(plano: pc.PlanoDeCargas | None, quadro: QuadroDeSensores) -> LigacaoAoPlano:
    """Cada combinação do quadro com a do plano de mesmo nome (o que o programa exportou).

    A numeração depende dos estados-limites exportados e da ordem deles: tenta os estados que as
    siglas do quadro indicam (e o padrão do programa) e fica com o que liga mais nomes.
    """
    if plano is None or not plano.acoes:
        return LigacaoAoPlano()
    nomes = [linha.nome for linha in quadro.combinacoes]
    siglas = {achado.group(2) for n in nomes if (achado := _NOME_DA_COMBINACAO.match(n))}
    indicados = [e for e in _ORDEM_DOS_ESTADOS if SIGLA_DO_ESTADO.get(e) in siglas]
    candidatos: list[tuple[str, ...]] = []
    if indicados:
        candidatos.extend(_permutacoes(indicados))
    padrao = list(comb.ESTADOS_PADRAO)
    candidatos.append(tuple(padrao))
    candidatos.append(tuple(dict.fromkeys([*padrao, *indicados])))
    presentes = {em._normal(linha.nome) for linha in quadro.casos}
    melhor: tuple[int, list[CombinacaoDoPlano]] = (-1, [])
    vistos: set[tuple[str, ...]] = set()
    for estados in candidatos:
        if estados in vistos:
            continue
        vistos.add(estados)
        try:
            lista = pc.combinacoes(plano, estados)
        except (ValueError, KeyError, ArithmeticError):
            continue
        geradas = [
            CombinacaoDoPlano(
                ex.nome_da_combinacao(c, len(lista)),
                c.estado_limite,
                {
                    ex.nome_no_solidworks(codigo): float(fator)
                    for codigo, fator in c.fatores.items()
                    if abs(float(fator)) > 1e-12
                },
                c.expressao,
            )
            for c in lista
        ]
        ligadas = sum(1 for g in geradas if g.nome in nomes)
        if ligadas > melhor[0]:
            melhor = (ligadas, geradas)
    ligadas_por_nome = {g.nome: g for g in melhor[1] if g.nome in nomes}
    faltam = tuple(
        g.nome
        for g in melhor[1]
        if g.nome not in nomes and any(em._normal(c) in presentes for c in g.fatores)
    )
    sobram = tuple(n for n in nomes if n not in ligadas_por_nome)
    codigos = tuple(ex.nome_no_solidworks(c) for c in plano.codigos)
    return LigacaoAoPlano(ligadas_por_nome, faltam, sobram, codigos)


# ---------------------------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Achado:
    nivel: str
    titulo: str
    texto: str


@dataclass(frozen=True)
class Extremo:
    """O valor que governa um sensor num grupo de linhas (ELU, ELS ou casos)."""

    sensor: int
    grupo: str
    valor: float
    linha: str
    contadas: int


@dataclass(frozen=True)
class FyAparente:
    """O que ``σ·FS`` diz do aço: o f_y no ponto do FS mínimo, quando é o ponto da tensão máxima."""

    valor_MPa: float
    linhas: int
    total: int
    maiores: tuple[tuple[str, float], ...] = ()  # linhas em que σ·FS deu mais


@dataclass(frozen=True)
class AnaliseDosSensores:
    quadro: QuadroDeSensores
    ligacao: LigacaoAoPlano
    tipos: Mapping[str, str]  # nome da linha → "Caso", "ELU", "ELS" ou ""
    fora: frozenset[str]
    observacoes: Mapping[str, str]
    achados: tuple[Achado, ...]
    extremos: tuple[Extremo, ...]
    fy_MPa: float
    fy_origem: str
    fy_aparente: FyAparente | None
    verificacoes: tuple[Verificacao, ...]

    @property
    def status(self) -> str:
        return status_geral(self.verificacoes)

    @property
    def aproveitamento_maximo(self) -> float | None:
        valores = [
            v.aproveitamento
            for v in self.verificacoes
            if v.tipo == "resistencia" and v.aproveitamento is not None
        ]
        return max(valores) if valores else None

    def extremo(self, k: int, grupo: str) -> Extremo | None:
        return next((e for e in self.extremos if e.sensor == k and e.grupo == grupo), None)

    def linha(self, nome: str) -> LinhaDoQuadro | None:
        return next((linha for linha in self.quadro.linhas if linha.nome == nome), None)


GRUPO_ELU = "ELU"
GRUPO_ELS = "ELS"
GRUPO_CASOS = "Caso"
#: Folga da superposição: os valores vêm com 4 algarismos e o máximo é do modelo inteiro.
TOLERANCIA_SUPERPOSICAO = 0.01
#: Aços que o σ·FS costuma revelar (MPa) e o nome mais comum.
ACOS_CONHECIDOS = {250.0: "ASTM A36", 345.0: "ASTM A572 Gr 50", 350.0: "AR350", 355.0: "S355"}


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def formatar(valor: float | None, grandeza: str) -> str:
    if valor is None:
        return "—"
    if grandeza == OUTRA:
        return f"{valor:.4g}".replace(".", ",")
    return _n(valor, CASAS.get(grandeza, 3))


def lista_curta(nomes: Iterable[str], maximo: int = 8) -> str:
    """``C52-ELSR … C72-ELSR`` em faixas: "C01-ELU, C52-ELSR a C72-ELSR"."""
    nomes = list(nomes)
    partes: list[str] = []
    i = 0
    while i < len(nomes):
        atual = _NOME_DA_COMBINACAO.match(nomes[i])
        j = i
        if atual:
            while j + 1 < len(nomes):
                proximo = _NOME_DA_COMBINACAO.match(nomes[j + 1])
                anterior = _NOME_DA_COMBINACAO.match(nomes[j])
                if not (proximo and anterior and proximo.group(2) == anterior.group(2)):
                    break
                if int(proximo.group(1)) != int(anterior.group(1)) + 1:
                    break
                j += 1
        if j - i >= 2:
            partes.append(f"{nomes[i]} a {nomes[j]}")
        else:
            partes.extend(nomes[i : j + 1])
        i = j + 1
    if len(partes) > maximo:
        return ", ".join(partes[:maximo]) + f" e mais {len(partes) - maximo}"
    return ", ".join(partes)


def _chave(valores: Sequence[float | None]) -> tuple[float | None, ...] | None:
    if all(v is None for v in valores):
        return None
    return tuple(None if v is None else float(f"{v:.6g}") for v in valores)


def _fatores_no_estudo(c: CombinacaoDoPlano, presentes: set[str]) -> frozenset[tuple[str, float]]:
    return frozenset(
        (em._normal(codigo), round(fator, 9))
        for codigo, fator in c.fatores.items()
        if em._normal(codigo) in presentes
    )


def _grupos_iguais(quadro: QuadroDeSensores) -> list[list[LinhaDoQuadro]]:
    grupos: dict[tuple[bool, tuple[float | None, ...]], list[LinhaDoQuadro]] = {}
    for linha in quadro.linhas:
        chave = _chave(linha.valores)
        if chave is not None:
            grupos.setdefault((linha.primario, chave), []).append(linha)
    return [g for g in grupos.values() if len(g) >= 2]


def _cluster_minimo(produtos: Sequence[tuple[str, float]]) -> FyAparente | None:
    if not produtos:
        return None
    valores = sorted(p for _, p in produtos)
    # grupos de valores a menos de 1,5 % do anterior; o menor grupo com pelo menos 2 linhas (ou o
    # único) é o f_y no ponto da tensão máxima — σ·FS só pode dar mais que isso.
    grupos: list[list[float]] = [[valores[0]]]
    for v in valores[1:]:
        if v <= grupos[-1][-1] * 1.015:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    escolhido = next((g for g in grupos if len(g) >= 2), grupos[0])
    mediana = escolhido[len(escolhido) // 2]
    for conhecido in ACOS_CONHECIDOS:
        if abs(mediana - conhecido) <= 0.01 * conhecido:
            mediana = conhecido
            break
    teto = escolhido[-1]
    maiores = tuple((nome, p) for nome, p in produtos if p > teto * 1.0001)
    return FyAparente(round(mediana, 1), len(escolhido), len(produtos), maiores)


def _extremo(
    quadro: QuadroDeSensores, k: int, linhas: Sequence[LinhaDoQuadro], grupo: str
) -> Extremo | None:
    valores = [(linha.nome, quadro.valor(linha, k)) for linha in linhas]
    validos = [(nome, v) for nome, v in valores if v is not None]
    if not validos:
        return None
    if quadro.sensores[k].grandeza == FATOR_DE_SEGURANCA:
        nome, valor = min(validos, key=lambda par: par[1])
    else:
        nome, valor = max(validos, key=lambda par: abs(par[1]))
    return Extremo(k, grupo, valor, nome, len(validos))


def _texto_do_aco(fy: float) -> str:
    nome = ACOS_CONHECIDOS.get(fy)
    return f"{_n(fy, 0)} MPa" + (f" ({nome}?)" if nome else "")


def analisar(quadro: QuadroDeSensores, plano: pc.PlanoDeCargas | None = None) -> AnaliseDosSensores:
    ligacao = ligar_ao_plano(plano, quadro)
    achados: list[Achado] = [Achado(NIVEL_ATENCAO, "Ao ler o arquivo", a) for a in quadro.avisos]
    presentes = {em._normal(linha.nome) for linha in quadro.casos}

    # ------------------------------------------------ tipo de cada linha
    tipos: dict[str, str] = {}
    for linha in quadro.linhas:
        if linha.primario:
            tipos[linha.nome] = GRUPO_CASOS
            continue
        ligada = ligacao.combinacoes.get(linha.nome)
        estado = ligada.estado if ligada else estado_pela_sigla(linha.nome)
        tipos[linha.nome] = tipo_do_estado(estado)
    sem_tipo = [n for n, t in tipos.items() if not t]
    if sem_tipo:
        achados.append(
            Achado(
                NIVEL_ATENCAO,
                "Combinações sem estado-limite",
                f"{lista_curta(sem_tipo)}: o nome não diz se é ELU ou ELS (o programa exporta "
                "C07-ELU, C49-ELSR…) e elas não estão no plano — ficam fora da verificação. "
                "Monte o gerenciador pelo Plano de cargas.",
            )
        )

    # ------------------------------------------------ casos e combinações do plano × estudo
    if plano is not None and plano.acoes:
        fora_do_estudo = [c for c in ligacao.codigos if em._normal(c) not in presentes]
        if fora_do_estudo:
            achados.append(
                Achado(
                    NIVEL_ATENCAO,
                    "Casos do plano que não estão no estudo",
                    f"{', '.join(fora_do_estudo)} estão no plano de cargas, mas o estudo do "
                    "SolidWorks não tem esses casos: as combinações saíram sem eles. Se eles têm "
                    "carga, crie-os no estudo; se não se aplicam ao projeto, tire-os do plano.",
                )
            )
        codigos_do_plano = {em._normal(c) for c in ligacao.codigos}
        extras = [
            linha.nome for linha in quadro.casos if em._normal(linha.nome) not in codigos_do_plano
        ]
        if extras:
            achados.append(
                Achado(
                    NIVEL_INFO,
                    "Casos do estudo que não estão no plano",
                    f"{', '.join(extras)}: o plano de cargas não tem esse código (mostrados, mas "
                    "não entram em nenhuma combinação do plano).",
                )
            )
        if ligacao.faltam:
            achados.append(
                Achado(
                    NIVEL_ATENCAO,
                    "Combinações do plano que não vieram do SolidWorks",
                    f"{lista_curta(ligacao.faltam)}: no plano de cargas, mas fora do quadro — o "
                    "gerenciador do SolidWorks não tem ou não calculou. Monte o gerenciador de novo "
                    "pelo Plano de cargas e rode (Executar).",
                )
            )
        if ligacao.sobram:
            achados.append(
                Achado(
                    NIVEL_INFO,
                    "Combinações que não estão no plano",
                    f"{lista_curta(ligacao.sobram)}: não têm combinação de mesmo nome no plano (o "
                    "plano mudou depois de exportar?). Entram pela sigla do nome, sem conferência "
                    "dos coeficientes.",
                )
            )
    elif quadro.combinacoes:
        achados.append(
            Achado(
                NIVEL_INFO,
                "Sem plano de cargas",
                "O projeto não tem plano de cargas: as combinações entram pela sigla do nome "
                "(C07-ELU, C49-ELSR…), sem conferir os coeficientes nem as que faltam.",
            )
        )

    # ------------------------------------------------ linhas com o mesmo resultado
    fora: set[str] = set()
    observacoes: dict[str, str] = {}
    explicadas: list[str] = []
    for grupo in _grupos_iguais(quadro):
        nomes = [linha.nome for linha in grupo]
        if grupo[0].primario:
            achados.append(
                Achado(
                    NIVEL_ATENCAO,
                    "Casos com o mesmo resultado",
                    f"{', '.join(nomes)} dão exatamente os mesmos números em todos os sensores: "
                    "confira se não é o mesmo caso calculado duas vezes (cargas copiadas sem "
                    "trocar a direção, por exemplo).",
                )
            )
            continue
        ligadas = [ligacao.combinacoes.get(n) for n in nomes]
        if any(c is None for c in ligadas):
            achados.append(
                Achado(
                    NIVEL_INFO,
                    "Combinações com o mesmo resultado",
                    f"{lista_curta(nomes)} dão os mesmos números em todos os sensores. Sem o plano "
                    "não dá para saber se é certo (diferem só em casos fora do estudo, ou por "
                    "simetria) — confira os coeficientes no gerenciador.",
                )
            )
            continue
        no_estudo = {_fatores_no_estudo(c, presentes) for c in ligadas if c is not None}
        if len(no_estudo) == 1:
            diferentes = sorted(
                {
                    codigo
                    for c in ligadas
                    if c is not None
                    for codigo in c.fatores
                    if em._normal(codigo) not in presentes
                }
            )
            for n in nomes[1:]:
                observacoes[n] = f"igual a {nomes[0]}"
            explicadas.append(
                f"{' = '.join(nomes)}"
                + (f" (diferem só em {', '.join(diferentes)})" if diferentes else "")
            )
            continue
        fora.update(nomes)
        for n in nomes:
            observacoes[n] = "repetido: fora da verificação"
        achados.append(
            Achado(
                NIVEL_ERRO,
                "Resultados repetidos com coeficientes diferentes",
                f"{lista_curta(nomes)} ({len(nomes)} combinações) dão exatamente os mesmos números "
                "em todos os sensores, mas têm coeficientes diferentes nos casos do estudo — não "
                "podem dar igual. Não são resultados (o SolidWorks repetiu o valor de uma "
                "combinação só ou não as calculou): ficam fora da verificação. No SolidWorks, abra "
                "o gerenciador, confira essas combinações e rode (Executar) antes da macro.",
            )
        )
    if explicadas:
        achados.append(
            Achado(
                NIVEL_INFO,
                "Combinações iguais (explicado)",
                "Dão o mesmo resultado porque diferem só em casos que o estudo não tem: "
                + "; ".join(explicadas[:6])
                + (f" e mais {len(explicadas) - 6}" if len(explicadas) > 6 else "")
                + ".",
            )
        )

    # ------------------------------------------------ superposição
    casos_por_nome = {em._normal(linha.nome): linha for linha in quadro.casos}
    nao_fecham: list[str] = []
    for linha in quadro.combinacoes:
        c = ligacao.combinacoes.get(linha.nome)
        if c is None or linha.nome in fora:
            continue
        termos = [
            (casos_por_nome[em._normal(codigo)], fator)
            for codigo, fator in c.fatores.items()
            if em._normal(codigo) in casos_por_nome
        ]
        if not termos:
            continue
        for k, s in enumerate(quadro.sensores):
            if s.grandeza not in (TENSAO, DESLOCAMENTO, FATOR_DE_SEGURANCA):
                continue
            v = quadro.valor(linha, k)
            dos_casos = [quadro.valor(caso, k) for caso, _ in termos]
            if v is None or any(x is None or x < 0 for x in dos_casos) or v < 0:
                continue
            valores = [float(x) for x in dos_casos if x is not None]
            if s.grandeza == FATOR_DE_SEGURANCA:
                if any(x <= 0 for x in valores):
                    continue
                piso = 1.0 / sum(abs(f) / x for (_, f), x in zip(termos, valores, strict=True))
                if v < piso * (1 - TOLERANCIA_SUPERPOSICAO):
                    nao_fecham.append(
                        f"{linha.nome} ({s.nome}: {formatar(v, s.grandeza)} < "
                        f"1/Σ(γ/FS) = {formatar(piso, s.grandeza)})"
                    )
                    observacoes.setdefault(linha.nome, "não fecha com o plano")
                continue
            teto = sum(abs(f) * x for (_, f), x in zip(termos, valores, strict=True))
            if v > teto * (1 + TOLERANCIA_SUPERPOSICAO) + 1e-9:
                nao_fecham.append(
                    f"{linha.nome} ({s.nome}: {formatar(v, s.grandeza)} > Σ|γ|·v = "
                    f"{formatar(teto, s.grandeza)} {s.unidade_de_calculo})".replace(" )", ")")
                )
                observacoes.setdefault(linha.nome, "não fecha com o plano")
    if nao_fecham:
        achados.append(
            Achado(
                NIVEL_ATENCAO,
                "Combinações que não fecham com os coeficientes do plano",
                "O máximo de uma combinação não pode passar da soma dos máximos dos casos com os "
                "coeficientes do plano (nem o FS ficar abaixo de 1/Σ(γ/FS)): "
                + "; ".join(nao_fecham[:5])
                + (f" e mais {len(nao_fecham) - 5}" if len(nao_fecham) > 5 else "")
                + ". O gerenciador tem coeficientes diferentes dos do plano (ou o plano mudou "
                "depois de exportar): monte-o de novo pelo Plano de cargas.",
            )
        )

    # ------------------------------------------------ σ·FS → f_y
    k_tensao = next((k for k, s in enumerate(quadro.sensores) if s.grandeza == TENSAO), None)
    k_fs = next(
        (k for k, s in enumerate(quadro.sensores) if s.grandeza == FATOR_DE_SEGURANCA), None
    )
    fy_aparente: FyAparente | None = None
    if k_tensao is not None and k_fs is not None:
        produtos = []
        for linha in quadro.linhas:
            if linha.nome in fora:
                continue
            sigma, fs = quadro.valor(linha, k_tensao), quadro.valor(linha, k_fs)
            if sigma is not None and fs is not None and sigma > 0 and fs > 0:
                produtos.append((linha.nome, sigma * fs))
        fy_aparente = _cluster_minimo(produtos)
        if fy_aparente is not None:
            tensao = quadro.sensores[k_tensao]
            if not 150.0 <= fy_aparente.valor_MPa <= 1000.0:
                achados.append(
                    Achado(
                        NIVEL_ERRO,
                        "A unidade da tensão não confere com o fator de segurança",
                        f"σ·FS dá {fy_aparente.valor_MPa:.4g} MPa com a tensão “{tensao.nome}” em "
                        f"{tensao.unidade} — nenhum aço tem esse f_y. Escolha a unidade em que o "
                        "sensor foi criado no SolidWorks (quase sempre N/mm² = MPa).",
                    )
                )
            else:
                texto = (
                    f"σ·FS = {_texto_do_aco(fy_aparente.valor_MPa)} em {fy_aparente.linhas} das "
                    f"{fy_aparente.total} linhas: o FS mínimo está no ponto da tensão máxima, num "
                    f"aço de f_y = {_n(fy_aparente.valor_MPa, 0)} MPa — a unidade da tensão confere."
                )
                if fy_aparente.maiores:
                    faixa = [p for _, p in fy_aparente.maiores]
                    texto += (
                        f" Em {lista_curta([n for n, _ in fy_aparente.maiores], 6)}, σ·FS dá mais "
                        f"({_n(min(faixa), 0)} a {_n(max(faixa), 0)} MPa): ali o FS mínimo está em "
                        "outro ponto que a tensão máxima — de outro aço (o modelo pode ter um aço "
                        "mais resistente) ou com tensão menor. O FS de cada ponto já usa o aço "
                        "dele; a verificação da tensão máxima usa o f_y menor, a favor da segurança."
                    )
                achados.append(Achado(NIVEL_INFO, "O aço que o fator de segurança mostra", texto))

    if quadro.fy_MPa is not None:
        fy, fy_origem = quadro.fy_MPa, "informado"
    elif fy_aparente is not None and 150.0 <= fy_aparente.valor_MPa <= 1000.0:
        fy, fy_origem = fy_aparente.valor_MPa, "pelo σ·FS do SolidWorks"
    else:
        fy, fy_origem = 250.0, "adotado (ASTM A36) — confirme"
        if k_tensao is not None:
            achados.append(
                Achado(
                    NIVEL_ATENCAO,
                    "f_y adotado",
                    "Sem sensor de fator de segurança para mostrar o aço, o escoamento da tensão "
                    "usa f_y = 250 MPa. Informe o f_y do aço da estrutura.",
                )
            )

    # ------------------------------------------------ extremos
    grupos = {
        GRUPO_ELU: [
            x for x in quadro.combinacoes if tipos.get(x.nome) == "ELU" and x.nome not in fora
        ],
        GRUPO_ELS: [
            x for x in quadro.combinacoes if tipos.get(x.nome) == "ELS" and x.nome not in fora
        ],
        GRUPO_CASOS: list(quadro.casos),
    }
    extremos = tuple(
        e
        for k in range(len(quadro.sensores))
        for grupo, linhas in grupos.items()
        if (e := _extremo(quadro, k, linhas, grupo)) is not None
    )

    # ------------------------------------------------ verificações
    verificacoes: list[Verificacao] = []

    def extremo(k: int, grupo: str) -> Extremo | None:
        return next((e for e in extremos if e.sensor == k and e.grupo == grupo), None)

    limite_tensao = fy / GAMA_A1
    for k, s in enumerate(quadro.sensores):
        if s.grandeza == TENSAO:
            e = extremo(k, GRUPO_ELU)
            if e is None:
                verificacoes.append(_sem_linhas(f"Escoamento — {s.nome}", "ELU", "MPa"))
                continue
            verificacoes.append(
                Verificacao(
                    f"Escoamento — {s.nome} (pior ELU: {e.linha})",
                    abs(e.valor),
                    limite_tensao,
                    "MPa",
                    REFERENCIA_GAMA,
                    f"σ = {_n(abs(e.valor))} MPa ({e.linha}) ≤ f_y/γ_a1 = {_n(fy, 0)}/1,10 = "
                    f"{_n(limite_tensao)} MPa (f_y {fy_origem})",
                )
            )
        elif s.grandeza == FATOR_DE_SEGURANCA:
            e = extremo(k, GRUPO_ELU)
            if e is None:
                verificacoes.append(_sem_linhas(f"Fator de segurança — {s.nome}", "ELU", "—"))
                continue
            verificacoes.append(
                Verificacao(
                    f"Fator de segurança mínimo — {s.nome} (pior ELU: {e.linha})",
                    GAMA_A1,
                    e.valor,
                    "—",
                    REFERENCIA_GAMA,
                    f"FS = {_n(e.valor)} ({e.linha}) ≥ γ_a1 = 1,10 — o FS do SolidWorks é f_y/σ "
                    "de cada ponto, com o aço do ponto",
                )
            )
        elif s.grandeza == DESLOCAMENTO:
            e = extremo(k, GRUPO_ELS)
            if e is None:
                verificacoes.append(_sem_linhas(f"Deslocamento — {s.nome}", "ELS", "mm"))
                continue
            limite = s.limite.limite_mm()
            nome = f"Deslocamento — {s.nome} (pior ELS: {e.linha})"
            if limite is None:
                falta = s.limite.falta()
                verificacoes.append(
                    Verificacao(
                        nome,
                        abs(e.valor),
                        None,
                        "mm",
                        "—",
                        f"δ = {_n(abs(e.valor), 3)} mm ({e.linha}); "
                        + (f"falta {falta} para verificar" if falta else "sem limite escolhido"),
                        status="ALERTA" if falta else "INFO",
                        tipo="informativo",
                    )
                )
                continue
            verificacoes.append(
                Verificacao(
                    nome,
                    abs(e.valor),
                    limite,
                    "mm",
                    s.limite.referencia(),
                    f"δ = {_n(abs(e.valor), 3)} mm ({e.linha}) ≤ {s.limite.texto()}",
                )
            )

    # ------------------------------------------------ o que deixa o quadro incompleto
    if fora or ligacao.faltam:
        partes = []
        if fora:
            partes.append(f"com resultado repetido (fora): {lista_curta(sorted(fora, key=_ordem))}")
        if ligacao.faltam:
            partes.append(f"sem resultado no quadro: {lista_curta(ligacao.faltam)}")
        verificacoes.append(
            Verificacao(
                "Combinações do plano sem resultado confiável do SolidWorks",
                None,
                None,
                "",
                REFERENCIA_CONFERENCIA,
                "; ".join(partes) + " — a verificação acima não as inclui",
                status="ALERTA",
                tipo="limite",
            )
        )
    if plano is not None and plano.acoes:
        fora_do_estudo = [c for c in ligacao.codigos if em._normal(c) not in presentes]
        if fora_do_estudo:
            verificacoes.append(
                Verificacao(
                    "Casos do plano que não estão no estudo",
                    None,
                    None,
                    "",
                    REFERENCIA_CONFERENCIA,
                    f"{', '.join(fora_do_estudo)}: as combinações do SolidWorks saíram sem eles",
                    status="ALERTA",
                    tipo="limite",
                )
            )
    if nao_fecham:
        verificacoes.append(
            Verificacao(
                "Combinações que não fecham com os coeficientes do plano",
                None,
                None,
                "",
                REFERENCIA_CONFERENCIA,
                f"{len(nao_fecham)} caso(s) — ver a conferência do quadro",
                status="ALERTA",
                tipo="limite",
            )
        )

    return AnaliseDosSensores(
        quadro=quadro,
        ligacao=ligacao,
        tipos=tipos,
        fora=frozenset(fora),
        observacoes=observacoes,
        achados=tuple(achados),
        extremos=extremos,
        fy_MPa=fy,
        fy_origem=fy_origem,
        fy_aparente=fy_aparente,
        verificacoes=tuple(verificacoes),
    )


def _ordem(nome: str) -> tuple[int, str]:
    achado = _NOME_DA_COMBINACAO.match(nome)
    return (int(achado.group(1)), nome) if achado else (10**9, nome)


def _sem_linhas(nome: str, grupo: str, unidade: str) -> Verificacao:
    return Verificacao(
        nome,
        None,
        None,
        unidade,
        REFERENCIA_CONFERENCIA,
        f"o quadro não tem combinação {grupo} com resultado: exporte as combinações {grupo} do "
        "Plano de cargas para o gerenciador",
        status="ALERTA",
        tipo="limite",
    )


# ---------------------------------------------------------------------------------------------
# Tabelas (página, CSV e memorial)
# ---------------------------------------------------------------------------------------------
def _valor_do_extremo(a: AnaliseDosSensores, k: int, grupo: str) -> str:
    e = a.extremo(k, grupo)
    if e is None:
        return "—"
    return f"{formatar(e.valor, a.quadro.sensores[k].grandeza)} ({e.linha})"


COLUNAS_RESUMO = ("Sensor", "Mede", "Unidade", "Pior nas ELU", "Pior nas ELS", "Pior nos casos")


def linhas_do_resumo(a: AnaliseDosSensores) -> list[list[str]]:
    """Um sensor por linha: o pior valor nas ELU, nas ELS e nos casos (mínimo, no FS)."""
    return [
        [
            s.nome,
            ROTULOS_GRANDEZA.get(s.grandeza, s.grandeza),
            s.unidade_de_calculo or "—",
            _valor_do_extremo(a, k, GRUPO_ELU),
            _valor_do_extremo(a, k, GRUPO_ELS),
            _valor_do_extremo(a, k, GRUPO_CASOS),
        ]
        for k, s in enumerate(a.quadro.sensores)
    ]


def colunas_do_quadro(a: AnaliseDosSensores, sensores: Sequence[int] | None = None) -> list[str]:
    indices = range(len(a.quadro.sensores)) if sensores is None else sensores
    return [
        "Caso / combinação",
        "Estado",
        *(a.quadro.sensores[k].rotulo for k in indices),
        "Observação",
    ]


def _rotulo_do_tipo(a: AnaliseDosSensores, linha: LinhaDoQuadro) -> str:
    if linha.primario:
        return "caso"
    ligada = a.ligacao.combinacoes.get(linha.nome)
    estado = ligada.estado if ligada else estado_pela_sigla(linha.nome)
    return estado or "—"


def linhas_do_quadro(
    a: AnaliseDosSensores, sensores: Sequence[int] | None = None
) -> list[list[str]]:
    """O quadro inteiro na unidade de cálculo, com a observação de cada linha."""
    indices = list(range(len(a.quadro.sensores)) if sensores is None else sensores)
    return [
        [
            linha.nome,
            _rotulo_do_tipo(a, linha),
            *(formatar(a.quadro.valor(linha, k), a.quadro.sensores[k].grandeza) for k in indices),
            a.observacoes.get(linha.nome, ""),
        ]
        for linha in a.quadro.linhas
    ]


def csv_do_quadro(a: AnaliseDosSensores) -> bytes:
    """O quadro organizado para o Excel (``;`` e vírgula decimal)."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow([f"Estudo: {a.quadro.estudo}", f"Arquivo: {a.quadro.arquivo}"])
    escritor.writerow(colunas_do_quadro(a))
    escritor.writerows(linhas_do_quadro(a))
    return ("﻿" + saida.getvalue()).encode("utf-8")


def combinacoes_que_governam(a: AnaliseDosSensores) -> list[list[str]]:
    """As combinações que governam alguma verificação, com a expressão no modelo."""
    presentes = {em._normal(linha.nome) for linha in a.quadro.casos}
    ordem = {codigo: i for i, codigo in enumerate(a.ligacao.codigos)}
    nomes: list[str] = []
    for e in a.extremos:
        if e.grupo in (GRUPO_ELU, GRUPO_ELS) and e.linha not in nomes:
            nomes.append(e.linha)
    linhas = []
    for nome in sorted(nomes, key=_ordem):
        c = a.ligacao.combinacoes.get(nome)
        if c is None:
            linhas.append([nome, estado_pela_sigla(nome) or "—", "— (não está no plano)"])
            continue
        termos = [
            f"{_n(f, 2).rstrip('0').rstrip(',')}·{codigo}"
            for codigo, f in sorted(c.fatores.items(), key=lambda par: ordem.get(par[0], 99))
            if em._normal(codigo) in presentes
        ]
        linhas.append([nome, c.estado, " + ".join(termos).replace("+ -", "− ") or "—"])
    return linhas


def _larguras(pesos: Sequence[float]) -> list[int]:
    total = sum(pesos)
    larguras = [round(9360 * p / total) for p in pesos]
    larguras[-1] += 9360 - sum(larguras)
    return larguras


def tabelas_para_memorial(a: AnaliseDosSensores) -> list[dict[str, Any]]:
    tabelas: list[dict[str, Any]] = [
        {
            "legenda": (
                "Sensores do estudo e o pior valor de cada um (máximo; no fator de segurança, o "
                "mínimo) nas combinações últimas (ELU), nas de serviço (ELS) e nos casos "
                "característicos, com a linha em que ocorre."
            ),
            "cabecalhos": list(COLUNAS_RESUMO),
            "linhas": linhas_do_resumo(a),
            "larguras": _larguras([18, 22, 9, 17, 17, 17]),
            "fonte": 7.2,
        }
    ]
    governam = combinacoes_que_governam(a)
    if governam:
        tabelas.append(
            {
                "legenda": "Combinações que governam, como foram calculadas no modelo.",
                "cabecalhos": ["Combinação", "Estado-limite", "Expressão no modelo"],
                "linhas": governam,
                "larguras": _larguras([14, 18, 68]),
                "fonte": 7.2,
            }
        )
    total = len(a.quadro.sensores)
    por_tabela = 5
    for inicio in range(0, total, por_tabela):
        indices = list(range(inicio, min(total, inicio + por_tabela)))
        parte = f" (sensores {inicio + 1} a {indices[-1] + 1})" if total > por_tabela else ""
        tabelas.append(
            {
                "subtitulo": "Quadro dos sensores" if inicio == 0 else "",
                "legenda": (
                    f"Resultado de cada sensor em cada caso e combinação{parte} — estudo "
                    f"“{a.quadro.estudo or a.quadro.arquivo}”, gerenciador de casos de carga do "
                    "SolidWorks Simulation."
                ),
                "cabecalhos": colunas_do_quadro(a, indices),
                "linhas": linhas_do_quadro(a, indices),
                "larguras": _larguras([14, 13, *([12] * len(indices)), 18]),
                "fonte": 6.8,
            }
        )
    return tabelas


# ---------------------------------------------------------------------------------------------
# Registro (memorial)
# ---------------------------------------------------------------------------------------------
def _inicial_minuscula(texto: str) -> str:
    return texto[:1].lower() + texto[1:]


def destaque(a: AnaliseDosSensores) -> str:
    partes = []
    for v in a.verificacoes:
        if v.tipo == "resistencia" and v.aproveitamento is not None:
            partes.append(f"{v.nome}: {100 * v.aproveitamento:.0f} %")
    casos, combinacoes = len(a.quadro.casos), len(a.quadro.combinacoes)
    texto = (
        f"Estudo “{a.quadro.estudo or a.quadro.arquivo}”: {len(a.quadro.sensores)} sensores em "
        f"{casos} casos e {combinacoes} combinações."
    )
    if partes:
        texto += " " + "; ".join(partes) + "."
    if a.fora:
        texto += f" {len(a.fora)} combinações com resultado repetido ficaram fora."
    return texto


def registro_sensores(
    a: AnaliseDosSensores, *, contexto: Mapping[str, Any] | None = None, responsavel: str = ""
) -> dict[str, Any]:
    from core import desenho_dos_sensores as dds

    texto = destaque(a)
    geral = a.status
    q = a.quadro
    entradas: dict[str, Any] = {
        "estudo": q.estudo or None,
        "arquivo": q.arquivo or None,
        "lido_em": q.lido_em or None,
        "sensores": ", ".join(
            f"{s.nome} ({_inicial_minuscula(ROTULOS_GRANDEZA.get(s.grandeza, s.grandeza))}"
            + (f", {s.unidade}" if s.unidade != "—" else "")
            + ")"
            for s in q.sensores
        ),
        "fy_MPa": numero_json(a.fy_MPa, 1),
        "origem_do_fy": a.fy_origem,
        "gama_a1": "1,10 (ABNT NBR 8800:2025, Tabela 3)",
    }
    for s in q.sensores:
        if s.grandeza == DESLOCAMENTO:
            entradas[f"limite — {s.nome}"] = s.limite.texto()
    entradas.update(contexto or {})
    entradas = {k: v for k, v in entradas.items() if v is not None}
    resultados: dict[str, Any] = {
        "status_geral": geral,
        "verificações": linhas_para_registro(list(a.verificacoes)),
        "utilizacao_maxima": numero_json(a.aproveitamento_maximo, 4),
        "destaque_memorial": texto,
        "tabelas_memorial": tabelas_para_memorial(a),
        "conferencia_do_quadro": [
            {"nivel": achado.nivel, "titulo": achado.titulo, "texto": achado.texto}
            for achado in a.achados
        ],
    }
    paineis = dds.paineis_da_analise(a)
    if paineis:
        resultados["figura_sensores"] = dds.paineis_para_o_registro(paineis)
    alertas = [
        f"{achado.titulo}: {achado.texto}"
        for achado in a.achados
        if achado.nivel in (NIVEL_ERRO, NIVEL_ATENCAO)
    ]
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Sensores do modelo — {q.estudo or q.arquivo or 'estudo do SolidWorks'}",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=texto,
        entradas=entradas,
        resultados=resultados,
        metodo=(
            "Resultados dos sensores do gerenciador de casos de carga do SolidWorks Simulation "
            "(análise estática linear), lidos do quadro da Vista de resultados: cada caso "
            "característico e cada combinação do plano de cargas. Nas combinações últimas, o "
            "escoamento pela tensão elástica do modelo (σ ≤ f_y/γ_a1) e pelo fator de segurança "
            "(FS ≥ γ_a1); nas de serviço, o deslocamento contra o limite de cada sensor. O quadro é "
            "conferido contra o plano: casos e combinações que faltam, resultados repetidos e a "
            "superposição dos casos."
        ),
        premissas=[
            "Cada sensor dá o máximo (no fator de segurança, o mínimo) do modelo inteiro ou da "
            "região em que foi posto no SolidWorks.",
            "A tensão elástica do modelo não verifica flambagem, flambagem lateral com torção nem "
            "a interação N + M da NBR 8800: essas ficam na verificação barra a barra.",
            "O deslocamento do sensor é absoluto (inclui o movimento dos apoios da barra): para a "
            "flecha relativa de uma viga, ele fica a favor da segurança.",
            "Combinações com resultado repetido e coeficientes diferentes não são resultado e "
            "ficam fora da verificação.",
        ],
        alertas=alertas,
        referencias=[
            "ABNT NBR 8800:2025 — combinações de ações e γ_a1 = 1,10.",
            f"{ca.REFERENCIA} — Tabelas 3 e 4 (deslocamentos).",
            "SOLIDWORKS Simulation — gerenciador de casos de carga (sensores da Vista de "
            "resultados).",
        ],
        conclusao=texto,
        responsavel=responsavel,
    )
