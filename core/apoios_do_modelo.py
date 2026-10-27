"""Reações em cada apoio do modelo do SolidWorks, pela macro exportar_casos_de_carga (v12).

A macro grava dois arquivos:

* ``<estudo>-fixacoes.csv``: cada fixação do estudo (nome, código do tipo, entidades e, quando a
  entidade é um vértice, onde ele fica, em m);
* ``<estudo>-<caso>-apoios.csv``: a reação em cada nó apoiado (posição, Fx, Fy, Fz, Mx, My, Mz,
  nos eixos do modelo) e a soma por fixação.

Este módulo junta os dois e monta o **quadro de cargas por apoio** para quem projeta a fundação:

* os nós a menos de 10 cm um do outro formam um apoio (uma fixação numa face tem vários nós); o
  apoio recebe a barra do esqueleto que chega nele (a ponta mais perto, até 15 cm) e a fixação
  (o vértice mais perto, até 5 cm);
* a **ação na fundação** é a reação com o sinal trocado; ``N`` é a componente vertical, compressão
  positiva — sem combinar nem majorar (critério Anglo, item 5.9);
* o **comportamento** sai dos momentos: com momento em algum caso, o apoio trabalha engastado;
  sem, articulado — para conferir com o que o cálculo das bases supõe;
* conferências: a soma dos nós contra a reação total do caso (o arquivo de reações) e contra a soma
  por fixação; unidade das coordenadas pelo esqueleto (m ou mm).

Sem Streamlit.
"""

from __future__ import annotations

import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc

TIPO_APOIOS = "Reações nos apoios"
TIPO_FIXACOES = "Fixações do estudo"
#: Nós a menos disto um do outro formam o mesmo apoio (m).
DISTANCIA_DO_APOIO_M = 0.10
#: A barra do esqueleto cuja ponta fica até esta distância do apoio é a que chega nele (m).
DISTANCIA_DA_BARRA_M = 0.15
#: O vértice de uma fixação até esta distância do apoio é dela (m).
DISTANCIA_DA_FIXACAO_M = 0.05
#: Momento a partir do qual o apoio é engastado (kN·m).
MOMENTO_DE_ENGASTE_KNM = 0.02
TOLERANCIA_RELATIVA = 0.01
TOLERANCIA_ABSOLUTA_KN = 0.01

NOTA = (
    "Ação de cada apoio na fundação (a reação com o sinal trocado), por caso característico — sem "
    "combinar nem majorar (critério Anglo, 5.9): quem projeta a fundação combina. N é a força "
    "vertical, compressão positiva; as outras componentes estão nos eixos do modelo do SolidWorks."
)


class ArquivoDeApoiosInvalido(ValueError):
    """O arquivo não é o que a macro grava, ou está incompleto."""


# ---------------------------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ReacaoNoNo:
    no: int
    ponto: tuple[float, float, float] | None  # m, nos eixos do modelo
    forca_N: tuple[float, float, float]
    momento_Nm: tuple[float, float, float]


@dataclass(frozen=True)
class ApoiosDoCaso:
    caso: str
    estudo: str
    arquivo: str
    nos: tuple[ReacaoNoNo, ...]
    por_fixacao: tuple[tuple[str, tuple[float, ...]], ...] = ()  # nome, (Fx, Fy, Fz, Mx, My, Mz)


@dataclass(frozen=True)
class EntidadeFixada:
    fixacao: str
    tipo: int | None
    entidade: int
    tipo_da_entidade: str
    ponto: tuple[float, float, float] | None


@dataclass(frozen=True)
class FixacoesDoEstudo:
    estudo: str
    arquivo: str
    entidades: tuple[EntidadeFixada, ...]

    @property
    def nomes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(e.fixacao for e in self.entidades))


def tipo_do_arquivo(conteudo: bytes) -> str | None:
    """:data:`TIPO_APOIOS`, :data:`TIPO_FIXACOES` ou ``None`` (outro arquivo)."""
    texto = em._normal(em._decodificar(conteudo[:3000]))
    if "reacoesnosnos" in texto:
        return TIPO_APOIOS
    if "fixacoesdoestudo" in texto:
        return TIPO_FIXACOES
    return None


def _linhas(conteudo: bytes) -> list[str]:
    return [linha.rstrip("\r") for linha in em._decodificar(conteudo).split("\n")]


def _numeros(campos: Sequence[str]) -> list[float | None]:
    return [em.numero(c) for c in campos]


def _estudo(linhas: Sequence[str]) -> str:
    for linha in linhas[:10]:
        if em._normal(linha).startswith("nomedoestudo:"):
            return linha.split(":", 1)[1].strip(" ;")
    return ""


def ler_apoios(conteudo: bytes, nome_arquivo: str = "") -> ApoiosDoCaso:
    linhas = _linhas(conteudo)
    caso = em._caso_de_carga(linhas)
    if not caso:
        raise ArquivoDeApoiosInvalido(
            'Sem o caso de carga no cabeçalho ("Caso de carga: PP"): use o arquivo da macro.'
        )
    nos: list[ReacaoNoNo] = []
    por_fixacao: list[tuple[str, tuple[float, ...]]] = []
    secao = ""
    for linha in linhas:
        normal = em._normal(linha)
        if normal.startswith("reacoesnosnos"):
            secao = "nos"
            continue
        if normal.startswith("reacoesporfixacao"):
            secao = "fixacoes"
            continue
        campos = linha.split(";")
        if secao == "nos" and len(campos) >= 10 and campos[0].strip().lstrip("-").isdigit():
            v = _numeros(campos[1:10])
            if any(x is None for x in v[3:]):
                continue
            ponto = None if any(x is None for x in v[:3]) else (v[0], v[1], v[2])
            nos.append(
                ReacaoNoNo(
                    int(campos[0]),
                    ponto,  # type: ignore[arg-type]
                    (v[3], v[4], v[5]),  # type: ignore[arg-type]
                    (v[6], v[7], v[8]),  # type: ignore[arg-type]
                )
            )
        elif secao == "fixacoes" and len(campos) >= 7 and campos[0].strip():
            if em._normal(campos[0]) == "fixacao":
                continue
            v = _numeros(campos[1:7])
            if all(x is not None for x in v):
                por_fixacao.append((campos[0].strip(), tuple(float(x) for x in v)))  # type: ignore[arg-type]
    if not nos:
        raise ArquivoDeApoiosInvalido(
            f"{caso}: nenhum nó com reação no arquivo — o estudo tem fixações? Rode a macro de novo."
        )
    return ApoiosDoCaso(caso, _estudo(linhas), nome_arquivo, tuple(nos), tuple(por_fixacao))


def ler_fixacoes(conteudo: bytes, nome_arquivo: str = "") -> FixacoesDoEstudo:
    linhas = _linhas(conteudo)
    entidades: list[EntidadeFixada] = []
    dentro = False
    for linha in linhas:
        normal = em._normal(linha)
        if normal.startswith("fixacoesdoestudo"):
            dentro = True
            continue
        campos = linha.split(";")
        if not dentro or len(campos) < 8 or not campos[0].strip():
            continue
        if em._normal(campos[0]) == "fixacao":
            continue
        tipo = em.numero(campos[1])
        indice = em.numero(campos[3])
        x, y, z = (em.numero(c) for c in campos[5:8])
        entidades.append(
            EntidadeFixada(
                campos[0].strip(),
                None if tipo is None else int(tipo),
                0 if indice is None else int(indice),
                campos[4].strip(),
                None if x is None or y is None or z is None else (x, y, z),
            )
        )
    if not entidades:
        raise ArquivoDeApoiosInvalido("Nenhuma fixação no arquivo.")
    return FixacoesDoEstudo(_estudo(linhas), nome_arquivo, tuple(entidades))


# ---------------------------------------------------------------------------------------------
# No projeto
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ApoiosDoModelo:
    casos: Mapping[str, ApoiosDoCaso] = field(default_factory=dict)
    fixacoes: FixacoesDoEstudo | None = None


def com_caso(dados: ApoiosDoModelo, apoios: ApoiosDoCaso, codigo: str = "") -> ApoiosDoModelo:
    codigo = codigo or apoios.caso
    return replace(dados, casos={**dados.casos, codigo: replace(apoios, caso=codigo)})


def trocar_codigos(dados: ApoiosDoModelo, mapa: Mapping[str, str]) -> ApoiosDoModelo:
    """Os casos com os códigos trocados (``{atual: novo}``); os outros ficam."""
    casos = {mapa.get(c, c): replace(a, caso=mapa.get(c, c)) for c, a in dados.casos.items()}
    return replace(dados, casos=casos)


def com_fixacoes(dados: ApoiosDoModelo, fixacoes: FixacoesDoEstudo) -> ApoiosDoModelo:
    return replace(dados, fixacoes=fixacoes)


def para_dicionario(dados: ApoiosDoModelo) -> dict[str, Any]:
    return {
        "casos": {
            codigo: {
                "estudo": c.estudo,
                "arquivo": c.arquivo,
                "nos": [
                    [n.no, *(n.ponto or (None, None, None)), *n.forca_N, *n.momento_Nm]
                    for n in c.nos
                ],
                "por_fixacao": [[nome, *valores] for nome, valores in c.por_fixacao],
            }
            for codigo, c in dados.casos.items()
        },
        "fixacoes": None
        if dados.fixacoes is None
        else {
            "estudo": dados.fixacoes.estudo,
            "arquivo": dados.fixacoes.arquivo,
            "entidades": [
                [
                    e.fixacao,
                    e.tipo,
                    e.entidade,
                    e.tipo_da_entidade,
                    *(e.ponto or (None, None, None)),
                ]
                for e in dados.fixacoes.entidades
            ],
        },
    }


def _f(valor: Any) -> float | None:
    if isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def de_dicionario(dados: Mapping[str, Any] | None) -> ApoiosDoModelo:
    """O que está gravado no projeto; o que não se lê fica de fora (nunca levanta)."""
    if not isinstance(dados, Mapping):
        return ApoiosDoModelo()
    casos: dict[str, ApoiosDoCaso] = {}
    for codigo, c in (
        (dados.get("casos") or {}).items() if isinstance(dados.get("casos"), Mapping) else ()
    ):
        if not isinstance(c, Mapping):
            continue
        nos = []
        for linha in c.get("nos") or []:
            if not isinstance(linha, Sequence) or len(linha) < 10:
                continue
            v = [_f(x) for x in linha[1:10]]
            if any(x is None for x in v[3:]) or _f(linha[0]) is None:
                continue
            ponto = None if any(x is None for x in v[:3]) else (v[0], v[1], v[2])
            nos.append(
                ReacaoNoNo(int(_f(linha[0]) or 0), ponto, (v[3], v[4], v[5]), (v[6], v[7], v[8]))  # type: ignore[arg-type]
            )
        por_fixacao = []
        for linha in c.get("por_fixacao") or []:
            if isinstance(linha, Sequence) and len(linha) >= 7:
                v = [_f(x) for x in linha[1:7]]
                if all(x is not None for x in v):
                    por_fixacao.append((str(linha[0]), tuple(float(x) for x in v)))  # type: ignore[arg-type]
        if nos:
            casos[str(codigo)] = ApoiosDoCaso(
                str(codigo),
                str(c.get("estudo") or ""),
                str(c.get("arquivo") or ""),
                tuple(nos),
                tuple(por_fixacao),
            )
    fixacoes = None
    f = dados.get("fixacoes")
    if isinstance(f, Mapping):
        entidades = []
        for linha in f.get("entidades") or []:
            if not isinstance(linha, Sequence) or len(linha) < 7:
                continue
            p = [_f(x) for x in linha[4:7]]
            tipo = _f(linha[1])
            entidades.append(
                EntidadeFixada(
                    str(linha[0]),
                    None if tipo is None else int(tipo),
                    int(_f(linha[2]) or 0),
                    str(linha[3] or ""),
                    None if any(x is None for x in p) else (p[0], p[1], p[2]),  # type: ignore[arg-type]
                )
            )
        if entidades:
            fixacoes = FixacoesDoEstudo(
                str(f.get("estudo") or ""), str(f.get("arquivo") or ""), tuple(entidades)
            )
    return ApoiosDoModelo(casos, fixacoes)


def do_projeto(projeto: Mapping[str, Any] | None) -> ApoiosDoModelo:
    return de_dicionario((projeto or {}).get("apoios_do_modelo"))


# ---------------------------------------------------------------------------------------------
# Quadro por apoio
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Apoio:
    rotulo: str
    ponto: tuple[float, float, float] | None  # m, eixos do modelo
    nos: tuple[int, ...]
    barra: str = ""
    fixacao: str = ""
    tipo_da_fixacao: int | None = None
    momento_maximo_kNm: float = 0.0

    @property
    def comportamento(self) -> str:
        return "engastado" if self.momento_maximo_kNm > MOMENTO_DE_ENGASTE_KNM else "articulado"


@dataclass(frozen=True)
class CargaNoApoio:
    apoio: str
    caso: str
    forca_kN: tuple[float, float, float]  # ação na fundação (= −reação), eixos do modelo
    momento_kNm: tuple[float, float, float]


@dataclass(frozen=True)
class QuadroPorApoio:
    apoios: tuple[Apoio, ...]
    cargas: tuple[CargaNoApoio, ...]
    casos: tuple[str, ...]
    eixo_vertical: str = "Y"
    escala: float = 1.0  # aplicada às coordenadas dos nós
    conferencia: tuple[pc.ItemDeConferencia, ...] = ()

    def carga(self, apoio: str, caso: str) -> CargaNoApoio | None:
        return next((c for c in self.cargas if c.apoio == apoio and c.caso == caso), None)

    def n_kN(self, carga: CargaNoApoio) -> float:
        """Força vertical na fundação, compressão positiva."""
        indice = 1 if self.eixo_vertical == "Y" else 2
        return -carga.forca_kN[indice]


def _n(valor: float, casas: int = 2) -> str:
    if round(valor, casas) == 0:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def _pontas(geometria: ld.GeometriaDoModelo | None) -> list[tuple[str, tuple[float, float, float]]]:
    if geometria is None:
        return []
    pontas = []
    for corpo in geometria.corpos:
        if corpo.forma == ld.FORMA_CHAPA or not corpo.comprimento_m:
            continue
        pontas.extend([(corpo.nome, tuple(corpo.inicio)), (corpo.nome, tuple(corpo.fim))])
    return pontas  # type: ignore[return-value]


def _escala(pontos: Sequence[tuple[float, float, float]], pontas: Sequence[Any]) -> float:
    """1, 0,001 ou 1000: a que põe mais nós na ponta de alguma barra (coordenadas em m)."""
    if not pontos:
        return 1.0
    if not pontas:
        maior = max(abs(c) for p in pontos for c in p)
        return 0.001 if maior > 200 else 1.0
    melhor, acertos = 1.0, -1
    for escala in (1.0, 0.001, 1000.0):
        n = sum(
            1
            for p in pontos
            if any(math.dist([c * escala for c in p], q) <= DISTANCIA_DA_BARRA_M for _, q in pontas)
        )
        if n > acertos:
            melhor, acertos = escala, n
    return melhor


def montar_quadro(
    dados: ApoiosDoModelo,
    *,
    geometria: ld.GeometriaDoModelo | None = None,
    esforcos: em.EsforcosDoModelo | None = None,
    eixo_vertical: str = "Y",
) -> QuadroPorApoio:
    """O quadro por apoio de todos os casos com o arquivo de apoios."""
    if not dados.casos:
        return QuadroPorApoio((), (), (), eixo_vertical)
    pontas = _pontas(geometria)
    # Posição de cada nó: a do caso importado por último que tenha posições de verdade. Caso
    # com nós diferentes no mesmo ponto (a macro v12 gravou 0, 0, 0 em todos) não dá posição:
    # juntar esses nós faria de todos os pés um apoio só.
    posicoes: dict[int, tuple[float, float, float]] = {}
    sem_posicao: list[str] = []
    for codigo, c in dados.casos.items():
        pontos = {n.no: n.ponto for n in c.nos if n.ponto is not None}
        distintos = {tuple(round(v, 6) for v in q) for q in pontos.values()}
        if len(pontos) > 1 and len(distintos) < len(pontos):
            sem_posicao.append(codigo)
            continue
        posicoes.update(pontos)
    escala = _escala(list(posicoes.values()), pontas)
    posicoes = {no: (p[0] * escala, p[1] * escala, p[2] * escala) for no, p in posicoes.items()}
    # Grupos: nós a menos de 10 cm um do outro (em cadeia).
    grupos: list[list[int]] = []
    for no in sorted({n.no for c in dados.casos.values() for n in c.nos}):
        p = posicoes.get(no)
        alvo = None
        if p is not None:
            for g in grupos:
                if any(
                    q is not None and math.dist(p, q) <= DISTANCIA_DO_APOIO_M
                    for q in (posicoes.get(m) for m in g)
                ):
                    alvo = g
                    break
        if alvo is None:
            grupos.append([no])
        else:
            alvo.append(no)
    grupo_do_no = {no: i for i, g in enumerate(grupos) for no in g}
    pontos_dos_grupos: list[tuple[float, float, float] | None] = []
    for g in grupos:
        ps = [posicoes[n] for n in g if n in posicoes]
        pontos_dos_grupos.append(
            None if not ps else tuple(sum(p[k] for p in ps) / len(ps) for k in range(3))  # type: ignore[arg-type]
        )
    # Ordem: pela posição (X, depois a horizontal que sobra), para os rótulos saírem estáveis.
    horizontal = 2 if eixo_vertical == "Y" else 1
    ordem = sorted(
        range(len(grupos)),
        key=lambda i: (
            (pontos_dos_grupos[i] or (math.inf,) * 3)[0],
            (pontos_dos_grupos[i] or (math.inf,) * 3)[horizontal],
        ),
    )
    rotulo = {i: f"A{k + 1}" for k, i in enumerate(ordem)}
    cargas: list[CargaNoApoio] = []
    momento_maximo = [0.0] * len(grupos)
    conferencia: list[pc.ItemDeConferencia] = []
    for codigo, c in dados.casos.items():
        somas = [[0.0] * 6 for _ in grupos]
        for n in c.nos:
            s = somas[grupo_do_no[n.no]]
            for k in range(3):
                s[k] += n.forca_N[k]
                s[3 + k] += n.momento_Nm[k]
        for i, s in enumerate(somas):
            forca = tuple(-v / 1e3 for v in s[:3])
            momento = tuple(-v / 1e3 for v in s[3:])
            momento_maximo[i] = max(momento_maximo[i], math.hypot(*momento))
            cargas.append(CargaNoApoio(rotulo[i], codigo, forca, momento))  # type: ignore[arg-type]
        total = [sum(n.forca_N[k] for n in c.nos) / 1e3 for k in range(3)]
        caso_esforcos = esforcos.casos.get(codigo) if esforcos else None
        reacoes = caso_esforcos.reacoes if caso_esforcos else None
        if reacoes is not None:
            modelo = list(reacoes.modelo)  # kN
            diferenca = max(abs(a - b) for a, b in zip(total, modelo, strict=True))
            escala_ref = max(max(abs(v) for v in modelo), 1e-9)
            if diferenca <= max(TOLERANCIA_ABSOLUTA_KN, TOLERANCIA_RELATIVA * escala_ref):
                conferencia.append(
                    pc.ItemDeConferencia(
                        "ok", f"{codigo}: a soma dos apoios bate com a reação total do modelo."
                    )
                )
            else:
                conferencia.append(
                    pc.ItemDeConferencia(
                        "atencao",
                        f"{codigo}: a soma dos apoios ({'; '.join(_n(v) for v in total)} kN) não "
                        f"bate com a reação total ({'; '.join(_n(v) for v in modelo)} kN) — o "
                        "arquivo de reações é do mesmo caso e do mesmo estudo?",
                    )
                )
        if c.por_fixacao:
            soma_fix = [sum(v[k] for _, v in c.por_fixacao) / 1e3 for k in range(3)]
            diferenca = max(abs(a - b) for a, b in zip(total, soma_fix, strict=True))
            if diferenca > max(TOLERANCIA_ABSOLUTA_KN, TOLERANCIA_RELATIVA * max(map(abs, total))):
                conferencia.append(
                    pc.ItemDeConferencia(
                        "atencao",
                        f"{codigo}: a soma por fixação ({'; '.join(_n(v) for v in soma_fix)} kN) "
                        "difere da soma dos nós — há nó apoiado fora das fixações listadas.",
                    )
                )
    if sem_posicao:
        conferencia.append(
            pc.ItemDeConferencia(
                "atencao",
                f"{', '.join(sem_posicao)}: nós diferentes no mesmo ponto no arquivo de apoios "
                "(a macro v12 gravava 0, 0, 0) — as posições desses casos ficaram de fora. Rode a "
                "macro v13 e envie os -apoios.csv de novo"
                + ("." if posicoes else ": sem posição, cada nó é um apoio."),
            )
        )
    if esforcos is not None:
        sem_apoios = [c for c in esforcos.casos if c not in dados.casos]
        if sem_apoios:
            conferencia.append(
                pc.ItemDeConferencia(
                    "atencao",
                    "Casos sem o arquivo de apoios: "
                    + ", ".join(sem_apoios)
                    + " (rode a macro v12).",
                )
            )
    apoios: list[Apoio] = []
    vertices = [
        (e.fixacao, e.tipo, e.ponto)
        for e in (dados.fixacoes.entidades if dados.fixacoes else ())
        if e.ponto is not None
    ]
    for i in ordem:
        p = pontos_dos_grupos[i]
        barra = fixacao = ""
        tipo = None
        if p is not None:
            perto = [(math.dist(p, q), nome) for nome, q in pontas]
            perto = [x for x in perto if x[0] <= DISTANCIA_DA_BARRA_M]
            barra = min(perto)[1] if perto else ""
            fix = [(math.dist(p, q), nome, t) for nome, t, q in vertices]
            fix = [x for x in fix if x[0] <= DISTANCIA_DA_FIXACAO_M]
            if fix:
                _, fixacao, tipo = min(fix, key=lambda x: x[0])
        if not fixacao and dados.fixacoes and len(dados.fixacoes.nomes) == 1:
            fixacao = dados.fixacoes.nomes[0]
            tipo = dados.fixacoes.entidades[0].tipo
        apoios.append(
            Apoio(
                rotulo[i],
                p,
                tuple(grupos[i]),
                barra,
                fixacao,
                tipo,
                momento_maximo[i],
            )
        )
    return QuadroPorApoio(
        tuple(apoios),
        tuple(cargas),
        tuple(dados.casos),
        eixo_vertical,
        escala,
        tuple(conferencia),
    )


# ---------------------------------------------------------------------------------------------
# Tabelas e arquivos
# ---------------------------------------------------------------------------------------------
def colunas(eixo_vertical: str = "Y") -> list[str]:
    return [
        "Apoio",
        "Barra",
        "X (m)",
        "Y (m)",
        "Z (m)",
        "Caso",
        "N (kN, compressão +)",
        "Fx (kN)",
        "Fy (kN)",
        "Fz (kN)",
        "Mx (kN·m)",
        "My (kN·m)",
        "Mz (kN·m)",
    ]


def linhas_do_quadro(q: QuadroPorApoio) -> list[list[object]]:
    linhas: list[list[object]] = []
    for a in q.apoios:
        for caso in q.casos:
            c = q.carga(a.rotulo, caso)
            if c is None:
                continue
            p = a.ponto or (None, None, None)
            linhas.append(
                [
                    a.rotulo,
                    a.barra or "—",
                    None if p[0] is None else round(p[0], 3),
                    None if p[1] is None else round(p[1], 3),
                    None if p[2] is None else round(p[2], 3),
                    caso,
                    round(q.n_kN(c), 3),
                    *(round(v, 3) for v in c.forca_kN),
                    *(round(v, 3) for v in c.momento_kNm),
                ]
            )
    return linhas


def linhas_dos_apoios(q: QuadroPorApoio) -> list[dict[str, object]]:
    return [
        {
            "Apoio": a.rotulo,
            "Barra que chega": a.barra or "—",
            "Fixação": a.fixacao or "—",
            "Tipo da fixação (código)": "—"
            if a.tipo_da_fixacao is None
            else str(a.tipo_da_fixacao),
            "Nós": len(a.nos),
            "Maior momento (kN·m)": round(a.momento_maximo_kNm, 3),
            "Trabalha como": a.comportamento,
        }
        for a in q.apoios
    ]


def csv_do_quadro(q: QuadroPorApoio) -> bytes:
    def campo(v: object) -> str:
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.3f}".replace(".", ",")
        return str(v).replace(";", ",")

    texto = [";".join(colunas(q.eixo_vertical))]
    texto.extend(";".join(campo(v) for v in linha) for linha in linhas_do_quadro(q))
    texto.append("")
    texto.append(NOTA)
    return ("﻿" + "\r\n".join(texto) + "\r\n").encode("utf-8")


def xlsx_do_quadro(q: QuadroPorApoio, titulo: str = "") -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    livro = Workbook()
    folha = livro.active
    folha.title = "Apoios"
    folha.append([f"Quadro de cargas por apoio{(' — ' + titulo) if titulo else ''}"])
    folha["A1"].font = Font(bold=True, size=12)
    folha.append([NOTA])
    folha.append([])
    folha.append(colunas(q.eixo_vertical))
    for celula in folha[4]:
        celula.font = Font(bold=True)
    for linha in linhas_do_quadro(q):
        folha.append(linha)
    resumo = livro.create_sheet("Comportamento")
    cabecalho = list(linhas_dos_apoios(q)[0]) if q.apoios else []
    resumo.append(cabecalho)
    for apoio in linhas_dos_apoios(q):
        resumo.append(list(apoio.values()))
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()
