"""O que conferir e corrigir antes de verificar: o painel do início da página Esforços do modelo.

Junta as conferências espalhadas pela página (plano × reações, forças × reações, forças de cada
pilar × reação no pé dele, apoios × reações, rodadas diferentes, arquivos de forças repetidos,
cargas da grade que sobraram no plano, ventos com nomes trocados e os problemas da leitura do
modelo) e diz, para cada problema, **em linguagem simples**: o que está errado, por que importa e o
passo a passo para corrigir — no SolidWorks, no envio dos arquivos ou no próprio programa (alguns
se corrigem com um botão: ``Achado.acao``).

Robustez: cada conferência roda separada — se uma falhar com um dado fora do esperado, as outras
rodam e o painel diz qual não rodou, com a referência da ocorrência (com
``MECANICA_TOOLKIT_ERROS=levantar``, a falha sobe).

De que caso são as forças de um arquivo
---------------------------------------
O erro mais comum é salvar o "Listar forças da viga" sem trocar o caso no gerenciador de casos de
carga (o gráfico não mudou): o arquivo tem o nome de um caso e os números de outro. O programa
confere as forças de cada caso de três jeitos, que não dependem da orientação da seção:

* a soma da compressão nas bases dos pilares contra a reação vertical do caso;
* em cada pilar, a compressão e a cortante na base contra a reação no pé dele (o -apoios.csv da
  macro; com o esqueleto, o pé de cada pilar; sem ele, comparando os conjuntos de valores);
* a cortante das bases contra a reação horizontal (vento): os pilares não podem levar menos.

Quando os números batem com outro caso, o painel diz qual.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core import apoios_do_modelo as am
from core import cargas_pelo_modelo as cpm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf

NIVEL_ERRO = pc.NIVEL_ERRO  # o resultado está errado: corrigir antes de usar
NIVEL_ATENCAO = pc.NIVEL_ATENCAO  # pode estar errado: conferir
NIVEL_INFO = em.NIVEL_INFO  # falta algo, mas o resto vale

ACAO_TROCAR_NOMES = "trocar_nomes"
ACAO_TIRAR_GRADE = "tirar_grade"
#: ``Achado.detalhe["sobre"]`` dos achados do arquivo de forças de um caso (as reações e os apoios
#: do caso podem estar certos).
SOBRE_AS_FORCAS = "forcas"

#: Duas forças "são a mesma" até esta diferença relativa ao maior valor do caso (ou a absoluta).
TOLERANCIA_RELATIVA = 0.03
TOLERANCIA_ABSOLUTA_KN = 0.02

#: Passos que se repetem.
LISTAR_FORCAS = (
    "No SolidWorks, abra o gerenciador de casos de carga › Vista de resultados.",
    "Dê duplo clique no caso {caso} (o gráfico tem de mudar para ele).",
    "Resultados › Listar forças da viga (todas as vigas) › Salvar, com o nome {caso}-forcas.csv.",
    "Envie o arquivo no passo 1 desta página e clique em Gravar no projeto.",
)
#: Passos para os problemas da leitura do modelo (seção 3) que mais aparecem.
PASSOS_DA_LEITURA: Mapping[str, tuple[str, ...]] = {
    "Segunda ordem global (B₂)": (
        "Na página Contraventamento, classifique a estrutura (pequena, média ou grande "
        "deslocabilidade) e leia o B₂ dos pilares.",
        "Informe o B₂ na tabela de parâmetros por tipo (passo 6 desta página).",
    ),
    "Eixo forte trocado": (
        "No passo 4 (Barras do modelo), clique em “Aplicar as sugestões”.",
        "Ou troque a coluna Eixo forte das barras citadas.",
    ),
    "Pontas soltas": (
        "No SolidWorks, Juntas › Calcular de novo (ou estenda e apare as barras até encostar).",
        "Rode os casos de novo e envie os arquivos.",
    ),
    "Eixo vertical trocado": ("Troque “Eixo vertical do modelo” no passo 1 desta página.",),
}
#: A conferência que ficou com o assunto: o achado da leitura com este título não se repete.
_JA_COBERTOS = {"Malha diferente entre os estudos": "Forças de outra rodada"}


@dataclass(frozen=True)
class Achado:
    nivel: str
    titulo: str
    problema: str
    passos: tuple[str, ...] = ()
    acao: str = ""  # ACAO_TROCAR_NOMES, ACAO_TIRAR_GRADE ou vazio
    detalhe: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Diagnostico:
    achados: tuple[Achado, ...]
    certos: tuple[str, ...]  # o que conferiu, em frases curtas
    #: todos os achados da leitura do modelo (os informativos ficam na seção 3 da página)
    leitura: tuple[ld.Achado, ...] = ()

    @property
    def erros(self) -> int:
        return sum(a.nivel == NIVEL_ERRO for a in self.achados)

    @property
    def atencoes(self) -> int:
        return sum(a.nivel == NIVEL_ATENCAO for a in self.achados)

    @property
    def tudo_certo(self) -> bool:
        return not any(a.nivel in (NIVEL_ERRO, NIVEL_ATENCAO) for a in self.achados)


def _n(valor: float, casas: int = 2) -> str:
    if round(valor, casas) == 0:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def _lista(itens: Sequence[str]) -> str:
    itens = list(itens)
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def _tolerancia(*valores: float) -> float:
    escala = max((abs(v) for v in valores), default=0.0)
    return max(TOLERANCIA_RELATIVA * escala, TOLERANCIA_ABSOLUTA_KN)


# ---------------------------------------------------------------------------------------------
# Forças de cada caso: são mesmo do caso?
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _Bases:
    """A base de cada pilar em cada caso: (N compressão +, cortante resultante), kN."""

    por_caso: Mapping[str, Mapping[str, tuple[float, float]]]
    completas: bool  # todos os pilares marcados com a base sabida


def _bases(dados: em.EsforcosDoModelo) -> _Bases:
    quadro = qf.montar_quadro(dados)
    por_caso: dict[str, dict[str, tuple[float, float]]] = {}
    for p in quadro.pilares:
        for c in p.cargas:
            por_caso.setdefault(c.caso, {})[p.pilar] = (c.n, math.hypot(c.v1, c.v2))
    return _Bases(por_caso, bool(quadro.pilares) and not quadro.pendentes)


def _vertical(dados: em.EsforcosDoModelo, codigo: str) -> float | None:
    caso = dados.casos.get(codigo)
    if caso is None or caso.reacoes is None:
        return None
    return em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)[2]


def _horizontal(dados: em.EsforcosDoModelo, codigo: str) -> float | None:
    caso = dados.casos.get(codigo)
    if caso is None or caso.reacoes is None:
        return None
    rx, ry, _ = em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)
    return math.hypot(rx, ry)


@dataclass(frozen=True)
class _PesDosPilares:
    """A reação no pé de cada pilar (ou de cada apoio, sem o esqueleto), por caso."""

    #: caso → apoio → (N compressão +, horizontal resultante), kN
    por_caso: Mapping[str, Mapping[str, tuple[float, float]]]
    #: pilar (nome no Simulation) → apoio que só ele alcança; vazio sem o esqueleto
    pilar_do_apoio: Mapping[str, str]
    #: os pilares em pé (a compressão na base é a reação vertical)
    verticais: frozenset[str]
    #: casos cujos apoios não somam a reação total (de outra rodada): ficam de fora
    de_outra_rodada: frozenset[str]


def _pes_dos_pilares(
    dados: em.EsforcosDoModelo,
    apoios: am.ApoiosDoModelo,
    geometria: ld.GeometriaDoModelo | None,
    leituras: Sequence[ld.LeituraDaBarra] | None,
) -> _PesDosPilares | None:
    if not apoios.casos:
        return None
    quadro = am.montar_quadro(
        apoios, geometria=geometria, esforcos=dados, eixo_vertical=dados.eixo_vertical
    )
    a, b = (0, 2) if dados.eixo_vertical == "Y" else (0, 1)
    por_caso: dict[str, dict[str, tuple[float, float]]] = {}
    for carga in quadro.cargas:
        por_caso.setdefault(carga.caso, {})[carga.apoio] = (
            quadro.n_kN(carga),
            math.hypot(carga.forca_kN[a], carga.forca_kN[b]),
        )
    de_outra_rodada = frozenset(
        c.texto.split(":", 1)[0]
        for c in quadro.conferencia
        if "não bate com a reação total" in c.texto
    )
    pilar_do_apoio: dict[str, str] = {}
    verticais: set[str] = set()
    if geometria is not None and geometria.corpos:
        pontas = am._pontas(geometria)
        corpos = _corpos_das_barras(dados, geometria, leituras)
        apoio_do_corpo: dict[str, str] = {}
        for apoio in quadro.apoios:
            if apoio.ponto is None or not apoio.barra:
                continue
            chegam = {
                nome for nome, q in pontas if math.dist(apoio.ponto, q) <= am.DISTANCIA_DA_BARRA_M
            }
            if chegam == {apoio.barra}:  # só o pilar chega no apoio (sem diagonal na base)
                apoio_do_corpo[apoio.barra] = apoio.rotulo
        for viga, corpo in corpos.items():
            if corpo.nome in apoio_do_corpo:
                pilar_do_apoio[viga] = apoio_do_corpo[corpo.nome]
                eixo = [f - i for i, f in zip(corpo.inicio, corpo.fim, strict=True)]
                comprimento = math.hypot(*eixo)
                indice = 1 if dados.eixo_vertical == "Y" else 2
                if comprimento > 0 and abs(eixo[indice]) >= 0.97 * comprimento:
                    verticais.add(viga)
    return _PesDosPilares(por_caso, pilar_do_apoio, frozenset(verticais), de_outra_rodada)


def _desvio(
    bases: Mapping[str, tuple[float, float]],
    pes: Mapping[str, tuple[float, float]],
    mapa: _PesDosPilares,
) -> tuple[float, float] | None:
    """(maior diferença, tolerância) entre as bases dos pilares de um caso e os pés de outro;
    ``None`` quando não dá para comparar."""
    pares = [p for p, apoio in mapa.pilar_do_apoio.items() if p in bases and apoio in pes]
    if len(pares) >= 2:
        diferencas: list[float] = []
        valores: list[float] = []
        for pilar in pares:
            (n, h), (n_pe, h_pe) = bases[pilar], pes[mapa.pilar_do_apoio[pilar]]
            if pilar in mapa.verticais:
                diferencas += [abs(n - n_pe), abs(h - h_pe)]
            else:  # inclinado: só o tamanho da força (não depende da direção da seção)
                diferencas.append(abs(math.hypot(n, h) - math.hypot(n_pe, h_pe)))
            valores += [n, h, n_pe, h_pe]
        return max(diferencas), _tolerancia(*valores)
    # Sem o esqueleto: o conjunto dos tamanhos das forças, pilar a pilar.
    if mapa.pilar_do_apoio or len(bases) < 2 or len(bases) != len(pes):
        return None
    a = sorted(math.hypot(*v) for v in bases.values())
    b = sorted(math.hypot(*v) for v in pes.values())
    return max(abs(x - y) for x, y in zip(a, b, strict=True)), _tolerancia(*a, *b)


def _assinatura_das_forcas(caso: em.CasoImportado) -> tuple[Any, ...] | None:
    """Os números do arquivo de forças (arredondados); ``None`` se não há força nenhuma."""
    pontos_do_caso = [p for pontos in caso.membros.values() for p in pontos]
    if all(abs(v) < 1e-9 for p in pontos_do_caso for v in p.vetor()):
        return None
    return tuple(
        (membro, p.elemento, p.fim, *(round(v, 5) for v in p.vetor()))
        for membro, pontos in sorted(caso.membros.items())
        for p in pontos
    )


def _corpos_das_barras(
    dados: em.EsforcosDoModelo,
    geometria: ld.GeometriaDoModelo | None,
    leituras: Sequence[ld.LeituraDaBarra] | None,
) -> dict[str, ld.CorpoDoModelo]:
    if geometria is None or not geometria.corpos:
        return {}
    if leituras is not None:
        return {lb.barra: lb.corpo for lb in leituras if lb.corpo is not None}
    return dict(ld.correspondencia(geometria, dados.nomes_dos_membros, dados).corpos)


def _pes_na_planta(
    dados: em.EsforcosDoModelo,
    geometria: ld.GeometriaDoModelo | None,
    leituras: Sequence[ld.LeituraDaBarra] | None,
) -> dict[str, tuple[float, float]]:
    """Onde fica o pé de cada pilar, nos dois eixos horizontais do modelo (m), pelo esqueleto."""
    vertical = 1 if dados.eixo_vertical == "Y" else 2
    a, b = (0, 2) if dados.eixo_vertical == "Y" else (0, 1)
    saida = {}
    for viga, corpo in _corpos_das_barras(dados, geometria, leituras).items():
        if dados.membros.get(viga, em.ConfiguracaoDoMembro()).tipo != "Pilar":
            continue
        pe = min((corpo.inicio, corpo.fim), key=lambda p: p[vertical])
        saida[viga] = (float(pe[a]), float(pe[b]))
    return saida


def _empurrao_pelas_bases(
    bases_do_caso: Mapping[str, tuple[float, float]], pes: Mapping[str, tuple[float, float]]
) -> tuple[float, float] | None:
    """Para onde a carga horizontal empurra, pela compressão nas bases: o lado de sotavento é o
    comprimido. Σ N·(pé − centro dos pés), nos eixos horizontais do modelo; ``None`` sem
    tombamento claro (pilares alinhados com a carga de lado, ou sem os pés)."""
    comuns = [p for p in bases_do_caso if p in pes]
    if len(comuns) < 2:
        return None
    cx = sum(pes[p][0] for p in comuns) / len(comuns)
    cy = sum(pes[p][1] for p in comuns) / len(comuns)
    mx = sum(bases_do_caso[p][0] * (pes[p][0] - cx) for p in comuns)
    my = sum(bases_do_caso[p][0] * (pes[p][1] - cy) for p in comuns)
    escala = sum(
        abs(bases_do_caso[p][0]) * math.hypot(pes[p][0] - cx, pes[p][1] - cy) for p in comuns
    )
    if escala <= 1e-9 or math.hypot(mx, my) <= 0.2 * escala:
        return None
    return (mx, my)


def _empurrao_da_reacao(dados: em.EsforcosDoModelo, codigo: str) -> tuple[float, float] | None:
    """Para onde a carga do caso empurra (a reação com o sinal trocado), nos eixos horizontais."""
    caso = dados.casos.get(codigo)
    if caso is None or caso.reacoes is None:
        return None
    r = caso.reacoes.modelo
    a, b = (0, 2) if dados.eixo_vertical == "Y" else (0, 1)
    if math.hypot(r[a], r[b]) <= TOLERANCIA_ABSOLUTA_KN:
        return None
    return (-r[a], -r[b])


def _horizontal_domina(dados: em.EsforcosDoModelo, codigo: str) -> bool:
    """Caso de carga horizontal (vento): a reação horizontal passa o dobro da vertical."""
    h, v = _horizontal(dados, codigo), _vertical(dados, codigo)
    return h is not None and v is not None and h > 2 * abs(v) + TOLERANCIA_ABSOLUTA_KN


def _sentido(vetor: tuple[float, float], dados: em.EsforcosDoModelo) -> str:
    """ "+X", "−Z"… de um vetor nos eixos horizontais do modelo."""
    # sentido_no_modelo pede a planta do programa: com Y para cima, o +Y da planta é o −Z.
    planta = (vetor[0], -vetor[1]) if dados.eixo_vertical == "Y" else vetor
    return em.sentido_no_modelo(planta, dados.eixo_vertical)


def _mesma_reacao(dados: em.EsforcosDoModelo, a: str, b: str) -> bool:
    """Os dois casos têm a mesma reação total (são o mesmo carregamento com outro nome)."""
    ra, rb = dados.casos.get(a), dados.casos.get(b)
    if ra is None or rb is None or ra.reacoes is None or rb.reacoes is None:
        return False
    va, vb = ra.reacoes.modelo, rb.reacoes.modelo
    return math.dist(va, vb) <= _tolerancia(*va, *vb)


def _espelhos(dados: em.EsforcosDoModelo, codigo: str) -> list[str]:
    """Os casos com a reação do mesmo tamanho (vertical e horizontal) que a deste — um vento e o
    do lado oposto: pelos tamanhos das forças nos pilares, não se distinguem."""
    v, h = _vertical(dados, codigo), _horizontal(dados, codigo)
    if v is None or h is None:
        return []
    saida = []
    for outro in dados.casos:
        vo, ho = _vertical(dados, outro), _horizontal(dados, outro)
        if outro == codigo or vo is None or ho is None:
            continue
        if abs(v - vo) <= _tolerancia(v, vo) and abs(h - ho) <= _tolerancia(h, ho):
            saida.append(outro)
    return saida


def _quem_tem_a_vertical(
    dados: em.EsforcosDoModelo, codigo: str, soma: float
) -> tuple[list[str], bool]:
    """Os outros casos cuja reação vertical é ``soma`` e se a soma é a de todos (estudo base)."""
    verticais = {c: v for c in dados.casos if (v := _vertical(dados, c)) is not None}
    total = sum(verticais.values())
    estudo_base = (
        len(verticais) > 2
        and abs(soma - total) <= _tolerancia(total)
        and abs(total) > _tolerancia(soma)
    )
    outros = [c for c, v in verticais.items() if c != codigo and abs(soma - v) <= _tolerancia(v)]
    return outros, estudo_base


def _forcas_de_cada_caso(
    dados: em.EsforcosDoModelo,
    apoios: am.ApoiosDoModelo,
    geometria: ld.GeometriaDoModelo | None,
    leituras: Sequence[ld.LeituraDaBarra] | None,
) -> tuple[list[Achado], list[str]]:
    """No máximo um achado por caso sobre o arquivo de forças, e o que conferiu."""
    bases = _bases(dados)
    pes = _pes_dos_pilares(dados, apoios, geometria, leituras)
    pes_na_planta = _pes_na_planta(dados, geometria, leituras)
    achados: list[Achado] = []
    certos: list[str] = []
    ja_ditos: set[str] = set()
    nomes_de_vento = set(pc.CODIGOS_DE_VENTO)

    def passos(codigo: str) -> tuple[str, ...]:
        return tuple(p.format(caso=codigo) for p in LISTAR_FORCAS)

    def vertical_bate(codigo: str) -> bool | None:
        vertical = _vertical(dados, codigo)
        if not bases.completas or vertical is None or codigo not in bases.por_caso:
            return None
        soma = sum(n for n, _ in bases.por_caso[codigo].values())
        return abs(soma - vertical) <= max(0.02 * abs(vertical), 0.1)

    def pes_batem(codigo: str, de: str) -> bool | None:
        if pes is None or de in pes.de_outra_rodada or codigo not in bases.por_caso:
            return None
        if de not in pes.por_caso:
            return None
        comparado = _desvio(bases.por_caso[codigo], pes.por_caso[de], pes)
        return None if comparado is None else comparado[0] <= comparado[1]

    apoios_fora_dos_pilares = pes is not None and any(
        len(v) > len(bases.por_caso.get(c, {})) for c, v in pes.por_caso.items()
    )
    # Algum caso com carga vertical fecha nas bases e nenhum deixa de fechar: todos os apoios são
    # pés de pilar (a cortante dos pilares é então toda a reação horizontal).
    gravidade_fecha = any(
        vertical_bate(c) is True and abs(_vertical(dados, c) or 0.0) > 0.1 for c in dados.casos
    ) and not any(vertical_bate(c) is False for c in dados.casos)

    def cortante_fecha(codigo: str) -> bool | None:
        """Os pilares levam pelo menos a reação horizontal? (``None``: não dá para dizer — há
        apoio fora dos pilares, ou a vertical de algum caso não fecha nas bases.)"""
        horizontal = _horizontal(dados, codigo)
        if (
            apoios_fora_dos_pilares
            or not gravidade_fecha
            or horizontal is None
            or codigo not in bases.por_caso
        ):
            return None
        cortantes = sum(h for _, h in bases.por_caso[codigo].values())
        return cortantes >= 0.95 * horizontal - TOLERANCIA_ABSOLUTA_KN

    def direcao_bate(codigo: str) -> bool | None:
        """As forças empurram para onde a reação do caso diz? (pelo lado comprimido; ``None``:
        sem os pés no esqueleto, sem tombamento claro ou caso que não é de carga horizontal)"""
        if codigo not in bases.por_caso or not _horizontal_domina(dados, codigo):
            return None
        empurrao = _empurrao_pelas_bases(bases.por_caso[codigo], pes_na_planta)
        da_reacao = _empurrao_da_reacao(dados, codigo)
        if empurrao is None or da_reacao is None:
            return None
        angulo = em._angulo(empurrao, da_reacao)
        return True if angulo <= 30 else False if angulo >= 60 else None

    # 1. Dois casos com o mesmo arquivo de forças (e reações diferentes).
    assinaturas: dict[tuple[Any, ...], list[str]] = {}
    for codigo, caso in dados.casos.items():
        if (assinatura := _assinatura_das_forcas(caso)) is not None:
            assinaturas.setdefault(assinatura, []).append(codigo)
    for codigos in assinaturas.values():
        if len(codigos) < 2:
            continue
        modelos = [r.modelo for c in codigos if (r := dados.casos[c].reacoes) is not None]
        if len(modelos) == len(codigos) and len(set(modelos)) == 1:
            continue  # reações iguais também: a leitura do modelo diz "têm o mesmo resultado"
        certos_do_par = [
            c
            for c in codigos
            if vertical_bate(c) is not False
            and pes_batem(c, c) is not False
            and cortante_fecha(c) is not False
            and direcao_bate(c) is not False
        ]
        errados = [c for c in codigos if c not in certos_do_par]
        if len(certos_do_par) != 1:
            errados = list(codigos)
        texto = (
            f"Os arquivos de forças de {_lista(codigos)} têm exatamente os mesmos números, mas "
            "as reações dos casos são diferentes: "
            + (
                f"as forças são as do {certos_do_par[0]}, e o de {_lista(errados)} foi salvo sem "
                "trocar o caso no gerenciador (o gráfico não mudou)."
                if len(certos_do_par) == 1
                else "algum deles foi salvo sem trocar o caso no gerenciador (o gráfico não mudou)."
            )
        )
        achados.append(
            Achado(
                NIVEL_ERRO,
                f"{_lista(errados)}: as forças são "
                + (f"as do {certos_do_par[0]}" if len(certos_do_par) == 1 else "de outro caso"),
                texto
                + " A verificação somaria duas vezes o mesmo esforço e deixaria um caso de fora.",
                passos(errados[0] if len(errados) == 1 else "de cada um"),
                detalhe={"casos": errados, "iguais": list(codigos)},
            )
        )
        ja_ditos.update(errados)

    # 2. Caso a caso: vertical, pés dos pilares e cortante.
    for codigo in dados.casos:
        if codigo in ja_ditos or codigo not in bases.por_caso:
            continue
        soma = sum(n for n, _ in bases.por_caso[codigo].values())
        vertical = _vertical(dados, codigo)
        if vertical_bate(codigo) is False and vertical is not None:
            outros, estudo_base = _quem_tem_a_vertical(dados, codigo, soma)
            if estudo_base:
                motivo = (
                    " Esse valor é a soma de todos os casos: o arquivo foi salvo com o estudo "
                    "base (todas as cargas ligadas), não com o caso carregado."
                )
            elif len(outros) == 1:
                motivo = (
                    f" Esse valor é a reação do {outros[0]}: o arquivo foi salvo com o caso "
                    f"{outros[0]} carregado (sem trocar o caso no gerenciador)."
                )
            elif outros and all(c in nomes_de_vento for c in outros):
                motivo = (
                    " A soma zero na vertical é a de um caso de vento: o arquivo foi salvo com um "
                    "vento carregado."
                )
            else:
                motivo = " O arquivo de forças e o de reações não são do mesmo resultado."
            achados.append(
                Achado(
                    NIVEL_ERRO,
                    f"{codigo}: as forças não são do caso {codigo}",
                    f"Os pilares do arquivo de forças de {codigo} levam {_n(soma)} kN à fundação, "
                    f"mas a reação de {codigo} é {_n(vertical)} kN." + motivo,
                    passos(codigo),
                    detalhe={"caso": codigo, "soma": soma, "reacao": vertical, "de": outros},
                )
            )
            continue
        proprio = pes_batem(codigo, codigo)
        # Os casos cujos apoios batem com estas forças (e que não são o mesmo caso com outro nome).
        candidatos: list[str] = []
        if pes is not None and proprio is not True:
            parecidos = [
                c
                for c in pes.por_caso
                if c != codigo
                and pes_batem(codigo, c) is True
                and not _mesma_reacao(dados, codigo, c)
                # Sem o pé de cada pilar, o caso espelhado deste (W0 × W180) tem as mesmas forças
                # em tamanho: bater com ele não prova nada.
                and (pes.pilar_do_apoio or codigo not in _espelhos(dados, c))
            ]
            candidatos = list(parecidos)
            if not pes.pilar_do_apoio:
                # Sem saber o pé de cada pilar, um caso espelhado (W0 × W180) dá as mesmas forças.
                for c in parecidos:
                    candidatos += [
                        d
                        for d in _espelhos(dados, c)
                        if d not in candidatos
                        and d != codigo
                        and not _mesma_reacao(dados, codigo, d)
                    ]
        if candidatos and proprio is not True:
            unico = len(candidatos) == 1
            de_quem = f"do {candidatos[0]}" if unico else f"de {' ou '.join(candidatos)}"
            achados.append(
                Achado(
                    NIVEL_ERRO,
                    f"{codigo}: as forças são as {de_quem}"
                    if unico
                    else f"{codigo}: as forças são de outro caso",
                    f"Em cada pilar, a compressão e a cortante na base do arquivo de forças de "
                    f"{codigo} são a reação no pé dele no caso {de_quem.split(' ', 1)[1]}, não a do "
                    f"{codigo}: o arquivo foi salvo com o caso {de_quem.split(' ', 1)[1]} "
                    "carregado (sem trocar o caso no gerenciador)."
                    + (" As reações e os apoios do caso estão certos." if proprio is False else "")
                    + (
                        ""
                        if unico
                        else " Sem o pé de cada pilar (esqueleto com as posições dos apoios), "
                        "não dá para dizer qual dos casos espelhados é."
                    ),
                    passos(codigo),
                    detalhe={"caso": codigo, "de": candidatos},
                )
            )
            continue
        if proprio is False and pes is not None:
            if pes.pilar_do_apoio:
                achados.append(
                    Achado(
                        NIVEL_ATENCAO,
                        f"{codigo}: as forças não batem com a reação de cada apoio",
                        f"A soma confere, mas em algum pilar a compressão ou a cortante na base "
                        f"do arquivo de forças de {codigo} não é a reação no pé dele (arquivo de "
                        "apoios da macro): os dois arquivos não são do mesmo resultado.",
                        (
                            *passos(codigo),
                            "Rode a macro de novo no mesmo caso para os -apoios.csv saírem da "
                            "mesma rodada.",
                        ),
                        detalhe={"caso": codigo},
                    )
                )
            continue
        horizontal = _horizontal(dados, codigo) or 0.0
        cortantes = sum(h for _, h in bases.por_caso[codigo].values())
        # Para onde as forças empurram (pelo tombamento: o lado comprimido) × a reação do caso.
        empurrao = _empurrao_pelas_bases(bases.por_caso[codigo], pes_na_planta)
        da_reacao = _empurrao_da_reacao(dados, codigo)
        mesma_direcao = direcao_bate(codigo)
        if mesma_direcao is False and empurrao is not None and da_reacao is not None:
            outros = [
                c
                for c in dados.casos
                if c != codigo
                and _horizontal_domina(dados, c)
                and (e := _empurrao_da_reacao(dados, c)) is not None
                and em._angulo(empurrao, e) <= 30
            ]
            achados.append(
                Achado(
                    NIVEL_ERRO,
                    f"{codigo}: as forças empurram para outro lado",
                    f"Pelas compressões dos pilares (o lado comprimido é o de sotavento), as forças "
                    f"do arquivo de {codigo} empurram para {_sentido(empurrao, dados)}, mas a "
                    f"reação de {codigo} mostra a carga empurrando para "
                    f"{_sentido(da_reacao, dados)}"
                    + (f" — essa é a direção do {_lista(outros)}" if outros else "")
                    + ": o arquivo de forças é de outro caso (salvo sem trocar o caso no "
                    "gerenciador).",
                    passos(codigo),
                    detalhe={"caso": codigo, "de": outros},
                )
            )
            continue
        # Os pilares não levam menos cortante que a reação horizontal — a não ser que haja apoio
        # fora deles (travamento na estrutura existente).
        if proprio is None and cortante_fecha(codigo) is False:
            # A pista: o caso cuja reação horizontal é o que os pilares levam.
            mesmos = [
                c
                for c in dados.casos
                if c != codigo
                and (h := _horizontal(dados, c)) is not None
                and h > TOLERANCIA_ABSOLUTA_KN
                and abs(h - cortantes) <= _tolerancia(h)
            ]
            valor_de = (
                f"{_n(cortantes)} kN é o valor "
                + (f"do {mesmos[0]}" if len(mesmos) == 1 else f"de {_lista(mesmos)}")
                if mesmos
                else ""
            )
            if mesma_direcao and empurrao is not None:
                pista = (
                    f" As forças empurram para {_sentido(empurrao, dados)}, a mesma direção da "
                    f"reação do {codigo}, só que com {_n(cortantes)} kN em vez de "
                    f"{_n(horizontal)} kN: o arquivo de forças é de uma rodada anterior, quando a "
                    f"força do {codigo} tinha outro valor" + (f" ({valor_de})." if mesmos else ".")
                )
            elif mesmos:
                pista = (
                    f" {_n(cortantes)} kN é a reação horizontal "
                    + (f"do {mesmos[0]}" if len(mesmos) == 1 else f"de {_lista(mesmos)}")
                    + f": o arquivo parece ser {'dele' if len(mesmos) == 1 else 'de um deles'}."
                )
            else:
                pista = ""
            # Com os apoios da macro, todos os apoios são pés de pilar: não há travamento fora.
            confirmado = pes is not None
            achados.append(
                Achado(
                    NIVEL_ERRO if confirmado else NIVEL_ATENCAO,
                    f"{codigo}: a cortante dos pilares não fecha com a reação horizontal",
                    f"A reação horizontal de {codigo} é {_n(horizontal)} kN, e as cortantes nas "
                    f"bases dos pilares do arquivo de forças somam só {_n(cortantes)} kN. "
                    + (
                        "Os apoios do modelo são só os pés dos pilares (arquivos de apoios da "
                        "macro), e os pilares não podem levar menos que a reação: "
                        if confirmado
                        else "Se todos os apoios são pés de pilar, os pilares não podem levar "
                        "menos que a reação: "
                    )
                    + "o arquivo de forças não é o deste resultado."
                    + pista,
                    passos(codigo)
                    if confirmado
                    else (
                        *passos(codigo),
                        "Se a estrutura é travada fora dos pilares (na estrutura existente), a "
                        "diferença vai para esse travamento e está certo: só confira o valor.",
                    ),
                    detalhe={"caso": codigo, "cortantes": cortantes, "reacao": horizontal},
                )
            )
    if pes is not None:
        conferidos = [
            c for c in dados.casos if c not in pes.de_outra_rodada and pes_batem(c, c) is True
        ]
        if conferidos:
            certos.append(
                f"As forças de cada pilar batem com a reação no pé dele em {_lista(conferidos)} "
                "(arquivos de apoios da macro)."
            )
    return achados, certos


# ---------------------------------------------------------------------------------------------
# Outras conferências
# ---------------------------------------------------------------------------------------------
def _assinatura(caso: em.CasoImportado) -> frozenset[tuple[str, str]]:
    return frozenset(
        (membro, p.elemento) for membro, pontos in caso.membros.items() for p in pontos
    )


def _rodadas(dados: em.EsforcosDoModelo) -> list[Achado]:
    """Casos cujas forças são de outra malha (outra rodada do estudo) que a dos outros."""
    assinaturas = {c: _assinatura(caso) for c, caso in dados.casos.items() if caso.membros}
    if len(assinaturas) < 3:
        return []
    contagem = Counter(assinaturas.values())
    maioria, vezes = contagem.most_common(1)[0]
    if vezes < 2 or vezes == len(assinaturas):
        return []
    fora = [c for c, a in assinaturas.items() if a != maioria]
    if len(fora) > len(assinaturas) / 2:
        return []
    passos = tuple(
        p.format(caso=fora[0] if len(fora) == 1 else "de cada um") for p in LISTAR_FORCAS
    )
    return [
        Achado(
            NIVEL_ATENCAO,
            f"Forças de outra rodada: {_lista(fora)}",
            f"O arquivo de forças de {_lista(fora)} tem outra numeração dos elementos que os "
            "outros casos — é de uma rodada anterior do estudo (antes de refazer a malha ou de "
            "Executar de novo). As combinações juntam os casos elemento a elemento: com malhas "
            "diferentes, o programa combina pela ordem dos elementos, o que é só aproximado.",
            passos,
            detalhe={"casos": fora},
        )
    ]


def _lado_a_lado(texto: str) -> str:
    """O trecho "no seu estudo … No programa …" do resumo dos ventos, sem a conclusão."""
    texto = texto.replace("Ventos — no seu estudo", "No seu estudo")
    for corte in (" Cada caso do estudo", " Não dá para"):
        texto = texto.split(corte)[0]
    return texto.strip()


def _linha_que_explica(dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas, codigo: str) -> str:
    """Se a diferença entre o plano e o modelo é uma linha do plano (um guarda-corpo de uma borda,
    uma carga de uma viga), diz qual — a pista mais provável do que faltou ou sobrou."""
    acao = plano.acao(codigo)
    caso = dados.casos.get(codigo)
    if acao is None or caso is None or caso.reacoes is None:
        return ""
    esperado = em.total_esperado(acao)
    if esperado is None:
        return ""
    recebido = em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)[2]
    diferenca = abs(esperado[2]) - abs(recebido)
    if abs(diferenca) < 0.05:
        return ""
    candidatas = [
        c
        for c in acao.cargas
        if c.resultante and abs(abs(c.resultante) - abs(diferenca)) <= 0.03 * abs(diferenca)
    ]
    if not candidatas or len(candidatas) > 4:
        return ""
    lado = "a mais no plano" if diferenca > 0 else "faltando no plano"
    if len(candidatas) == 1:
        c = candidatas[0]
        return (
            f"A diferença ({_n(abs(diferenca))} kN, {lado}) é exatamente a linha “{c.elemento}” "
            f"({c.observacao or _n(abs(c.resultante or 0.0)) + ' kN'}): confira essa carga no plano "
            "e no modelo."
        )
    nomes = _lista([f"“{c.elemento}”" for c in candidatas])
    return (
        f"A diferença ({_n(abs(diferenca))} kN, {lado}) é o valor de uma destas linhas do plano: "
        f"{nomes} — por exemplo um guarda-corpo numa borda que no modelo não tem (o acesso)."
    )


def _plano_e_reacoes(dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas) -> list[Achado]:
    achados: list[Achado] = []
    da_grade = cpm.cargas_da_grade_no_plano(plano)
    casos_da_grade = sorted({c for c, _ in da_grade})
    if da_grade:
        total = sum(abs(c.resultante or 0.0) for _, c in da_grade)
        achados.append(
            Achado(
                NIVEL_ERRO,
                f"Plano de cargas com cargas de exemplo em {_lista(casos_da_grade)}",
                f"O plano ainda tem {len(da_grade)} linha(s) da grade de eixos da página Cargas do "
                f'esqueleto ({_n(total)} kN em barras "N1 · eixo A…" que o seu modelo não tem). '
                "Elas fazem o plano somar muito mais que o modelo recebeu, e a conferência não fecha.",
                (
                    "Clique no botão abaixo: as linhas da grade saem do plano e o resto fica.",
                    "Se ainda faltar carga, mande o piso e o guarda-corpo pela página Cargas do "
                    "esqueleto › Cargas do piso pelo esqueleto (as chapas do seu modelo).",
                ),
                acao=ACAO_TIRAR_GRADE,
                detalhe={"casos": casos_da_grade},
            )
        )
    ventos = em.resumo_dos_ventos(dados, plano)
    if ventos is not None:
        mapa = em.mapa_de_nomes_dos_ventos(dados, plano)
        if mapa:
            trocas = _lista([f"{a} → {b}" for a, b in mapa.items()])
            achados.append(
                Achado(
                    NIVEL_ERRO,
                    "Ventos com os nomes trocados",
                    f"As forças de vento do seu estudo estão certas, mas com o nome de outro caso: "
                    f"{trocas}. {_lado_a_lado(ventos.texto)}",
                    (
                        "Opção 1 (no programa, agora): clique no botão abaixo — os casos importados "
                        "trocam de nome e passam a bater com o plano.",
                        "Opção 2 (no SolidWorks, para as próximas vezes): renomeie os casos no "
                        "gerenciador. Na vista Superior: W0 vem da esquerda (+X), W180 da direita "
                        "(−X), W90 de baixo para cima (−Z) e W270 de cima para baixo (+Z).",
                    ),
                    acao=ACAO_TROCAR_NOMES,
                    detalhe={"mapa": dict(mapa)},
                )
            )
        else:
            achados.append(
                Achado(
                    NIVEL_ERRO,
                    "Ventos em direção diferente da do plano",
                    _lado_a_lado(ventos.texto)
                    + " Há caso com a direção de um vento e o valor de outro (o valor do vento "
                    "muda com a direção, porque ele vê outra face): só renomear não resolve.",
                    (
                        "Na vista Superior do SolidWorks (X para a direita, Z para baixo): W0 vem da "
                        "esquerda (+X), W180 da direita (−X), W90 de baixo para cima (−Z) e W270 de "
                        "cima para baixo (+Z).",
                        "Vento em X: o valor do W0 e do W180; vento em Z: o do W90 e do W270.",
                        "Acerte a força de cada caso (face, direção e valor), clique em Executar no "
                        "gerenciador, rode a macro e envie os arquivos de novo.",
                    ),
                )
            )
    nomes_de_vento = set(pc.CODIGOS_DE_VENTO)
    for item in em.conferir_reacoes(dados, plano, peso_conferido_no_esqueleto=True):
        codigo = item.texto.split(":", 1)[0]
        if item.nivel == pc.NIVEL_ERRO:
            achados.append(
                Achado(
                    NIVEL_ERRO,
                    f"{codigo}: problema no estudo",
                    item.texto.split(":", 1)[1].strip() if ":" in item.texto else item.texto,
                    ("Corrija no SolidWorks, rode de novo e envie os arquivos.",),
                    detalhe={"estudo": codigo},
                )
            )
        elif (
            item.nivel == pc.NIVEL_ATENCAO
            and "Falta ou sobra carga" in item.texto
            and codigo not in nomes_de_vento
            and codigo not in casos_da_grade
        ):
            pista = _linha_que_explica(dados, plano, codigo)
            achados.append(
                Achado(
                    NIVEL_ATENCAO,
                    f"{codigo}: o modelo não recebeu a carga do plano",
                    item.texto.split(":", 1)[1].strip() + (f" {pista}" if pista else ""),
                    (
                        f"Compare a carga {codigo} do SolidWorks com a do plano (página Plano de "
                        "cargas): valor, área ou comprimento carregado e “Por item” × “Total”.",
                        "Se o plano estiver errado, refaça a ação na página que a gerou (o "
                        "guarda-corpo de cada borda se marca em Cargas do esqueleto › Guarda-corpo "
                        "nas bordas do piso); se for o modelo, corrija, rode e envie os arquivos.",
                    ),
                )
            )
        elif item.nivel == pc.NIVEL_ATENCAO and "falta o arquivo de reações" in item.texto:
            achados.append(
                Achado(
                    NIVEL_ATENCAO,
                    f"{codigo}: falta o arquivo de reações",
                    "Sem a reação do caso, o programa não confere se o modelo recebeu a carga.",
                    (
                        "Rode a macro exportar_casos_de_carga (grava o -reacoes.csv de cada caso) ou, "
                        f"com o caso {codigo} carregado, Listar forças resultantes › Salvar.",
                        "Envie o arquivo no passo 1.",
                    ),
                )
            )
    faltam = [c for c in plano.codigos if c not in dados.casos]
    if dados.casos and faltam:
        achados.append(
            Achado(
                NIVEL_INFO,
                f"Casos do plano sem resultado do modelo: {_lista(faltam)}",
                "As combinações saem só com os casos importados: esses ficam de fora da "
                "verificação.",
                (
                    "Crie esses casos no gerenciador do SolidWorks, Execute e envie os arquivos; "
                    "ou, se não se aplicam (por exemplo a temperatura), tire-os do plano na página "
                    "que os gerou.",
                ),
            )
        )
    return achados


def _apoios(dados: em.EsforcosDoModelo, apoios: am.ApoiosDoModelo) -> list[Achado]:
    if not apoios.casos:
        return []
    achados: list[Achado] = []
    outra_rodada = []
    for codigo, c in apoios.casos.items():
        caso = dados.casos.get(codigo)
        if caso is None or caso.reacoes is None:
            continue
        soma = [sum(n.forca_N[k] for n in c.nos) / 1e3 for k in range(3)]
        modelo = list(caso.reacoes.modelo)
        escala = max(max(abs(v) for v in modelo), 1e-9)
        if max(abs(a - b) for a, b in zip(soma, modelo, strict=True)) > max(0.02 * escala, 0.01):
            outra_rodada.append(codigo)
    sem_posicao = []
    for codigo, c in apoios.casos.items():
        pontos = [n.ponto for n in c.nos if n.ponto is not None]
        distintos = {tuple(round(v, 6) for v in p) for p in pontos}
        if len(pontos) > 1 and len(distintos) < len(pontos):
            sem_posicao.append(codigo)
    if outra_rodada or sem_posicao:
        partes = []
        if outra_rodada:
            partes.append(
                f"a reação nos apoios de {_lista(outra_rodada)} não bate com a reação total do "
                "mesmo caso: os -apoios.csv são de outra rodada"
            )
        if sem_posicao:
            partes.append(
                f"{_lista(sem_posicao)} vieram sem a posição dos nós (a macro v12 gravava 0, 0, 0)"
            )
        achados.append(
            Achado(
                NIVEL_ATENCAO,
                "Reação em cada apoio: arquivos antigos",
                "No quadro por apoio, " + "; ".join(partes) + ".",
                (
                    "Na pasta da peça, os -apoios.csv da última rodada têm a mesma hora dos "
                    "-reacoes.csv (a macro grava os dois juntos).",
                    "Envie todos os -apoios.csv e -reacoes.csv dessa rodada juntos no passo 1 e "
                    "clique em Gravar no projeto.",
                ),
                detalhe={"outra_rodada": outra_rodada, "sem_posicao": sem_posicao},
            )
        )
    return achados


def da_leitura(
    achados_da_leitura: Sequence[ld.Achado], ja_no_painel: Sequence[Achado] = ()
) -> list[Achado]:
    """Os problemas da leitura do modelo (seção 3) no painel: os de corrigir e os de conferir,
    sem repetir o que outra conferência do painel já disse."""
    titulos = [a.titulo for a in ja_no_painel]
    problemas = " ".join(a.problema for a in ja_no_painel).casefold()
    estudos_com_problema = {a.detalhe.get("estudo") for a in ja_no_painel}
    saida: list[Achado] = []
    for a in achados_da_leitura:
        if a.nivel not in (pc.NIVEL_ERRO, pc.NIVEL_ATENCAO):
            continue
        coberto = _JA_COBERTOS.get(a.titulo)
        if coberto and any(t.startswith(coberto) for t in titulos):
            continue
        if a.titulo == "Eixo vertical trocado" and "eixo vertical" in problemas:
            continue
        codigo = a.titulo.split(":", 1)[0] if ":" in a.titulo else ""
        if a.titulo.endswith("estudo sem carga") and codigo in estudos_com_problema:
            continue
        passos = PASSOS_DA_LEITURA.get(a.titulo, ())
        if not passos and a.titulo.endswith("ficou com a gravidade"):
            passos = (
                f"No gerenciador de casos de carga, tire a gravidade do caso {codigo} (ela só vai "
                "no PP).",
                "Execute, rode a macro e envie os arquivos de novo.",
            )
        saida.append(
            Achado(
                a.nivel,
                a.titulo,
                a.texto,
                passos,
                detalhe={"barras": list(a.barras), "origem": "leitura do modelo"},
            )
        )
    return saida


# ---------------------------------------------------------------------------------------------
# O painel
# ---------------------------------------------------------------------------------------------
def _protegido(nome: str, conferencia: Callable[[], list[Achado]]) -> list[Achado]:
    """Uma conferência que falha não derruba as outras: vira um aviso com a referência."""
    try:
        return conferencia()
    except Exception as erro:
        from core import diagnostico as dg

        if dg.levantar_erros():
            raise
        ocorrencia = dg.ocorrencia_de_falha(
            f"Esforços do modelo › Antes de verificar › {nome}", erro
        )
        dg.gravar(ocorrencia)
        return [
            Achado(
                NIVEL_ATENCAO,
                f"Não deu para conferir: {nome}",
                f"Um dado fora do esperado parou esta conferência (ref. {ocorrencia.referencia}); "
                "as outras rodaram normalmente. Enquanto ela não roda, o que ela confere fica sem "
                "conferir.",
                (
                    "Envie de novo os arquivos do SolidWorks, sem editar, e clique em Gravar no "
                    "projeto.",
                    "Se continuar, mande a referência para corrigir o programa.",
                ),
                detalhe={"referencia": ocorrencia.referencia},
            )
        ]


def diagnosticar(
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    apoios: am.ApoiosDoModelo | None = None,
    *,
    geometria: ld.GeometriaDoModelo | None = None,
    leituras: Sequence[ld.LeituraDaBarra] | None = None,
    achados_da_leitura: Sequence[ld.Achado] | None = None,
    ler_o_modelo: bool = False,
    peso_da_estrutura_kN: float | None = None,
) -> Diagnostico:
    """Tudo o que conferir e corrigir, do mais grave ao menos, e o que já confere.

    ``geometria`` (o esqueleto) liga cada pilar ao apoio do pé dele. Os problemas da leitura do
    modelo entram no painel pelos ``achados_da_leitura`` já calculados ou, com ``ler_o_modelo``,
    pela própria :func:`core.leitura_do_modelo.diagnosticar` (protegida como as outras; o
    resultado volta em ``Diagnostico.leitura``).
    """
    if not dados.casos:
        return Diagnostico((), ())
    apoios = apoios or am.ApoiosDoModelo()
    certos: list[str] = []

    com_problema_de_forca: set[str] = set()

    def forcas() -> list[Achado]:
        achados_, certos_ = _forcas_de_cada_caso(dados, apoios, geometria, leituras)
        certos.extend(certos_)
        for a in achados_:  # todos falam do arquivo de forças de algum caso
            com_problema_de_forca.update(a.detalhe.get("casos") or [a.detalhe.get("caso", "?")])
        return [replace(a, detalhe={**a.detalhe, "sobre": SOBRE_AS_FORCAS}) for a in achados_]

    achados = [
        *_protegido("forças de cada caso", forcas),
        *_protegido("plano de cargas e reações", lambda: _plano_e_reacoes(dados, plano)),
        *_protegido("rodadas do estudo", lambda: _rodadas(dados)),
        *_protegido("reação em cada apoio", lambda: _apoios(dados, apoios)),
    ]
    leitura: list[ld.Achado] = list(achados_da_leitura or ())
    if achados_da_leitura is None and ler_o_modelo:

        def ler() -> list[Achado]:
            leitura.extend(
                ld.diagnosticar(
                    dados, plano, geometria, leituras, peso_da_estrutura_kN=peso_da_estrutura_kN
                )
            )
            return []

        achados += _protegido("leitura do modelo", ler)
    if leitura:
        achados += _protegido("leitura do modelo", lambda: da_leitura(leitura, achados))
    ordem = {NIVEL_ERRO: 0, NIVEL_ATENCAO: 1, NIVEL_INFO: 2}
    achados.sort(key=lambda a: ordem.get(a.nivel, 3))

    def equilibrados() -> list[str]:
        return [
            i.texto.split(":", 1)[0]
            for i in em.conferir_reacoes(dados, plano, peso_conferido_no_esqueleto=True)
            if i.nivel == pc.NIVEL_OK and "equilibram" in i.texto
        ]

    try:
        lista = equilibrados()
    except Exception:  # a falha já virou achado em "plano de cargas e reações"
        lista = []
    if lista:
        certos.insert(0, f"O modelo recebeu a carga do plano em {_lista(lista)}.")
    if not any(a.titulo.startswith("Forças de outra rodada") for a in achados):
        certos.append("Os arquivos de forças são todos da mesma rodada (mesma malha).")
    if not com_problema_de_forca and not any(a.titulo.startswith("Não deu") for a in achados):
        certos.append("As forças de cada caso batem com a reação do mesmo caso.")
    return Diagnostico(tuple(achados), tuple(certos), tuple(leitura))


# ---------------------------------------------------------------------------------------------
# Correções pelo programa
# ---------------------------------------------------------------------------------------------
def corrigir_nomes(
    dados: em.EsforcosDoModelo, apoios: am.ApoiosDoModelo, mapa: Mapping[str, str]
) -> tuple[em.EsforcosDoModelo, am.ApoiosDoModelo]:
    """Os casos importados (forças, reações e apoios) com os nomes trocados pelo ``mapa``."""
    return em.trocar_codigos(dados, mapa), am.trocar_codigos(apoios, mapa)


def tirar_grade(plano: pc.PlanoDeCargas) -> pc.PlanoDeCargas:
    return cpm.sem_cargas_da_grade(plano)
