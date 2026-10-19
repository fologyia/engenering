"""Monta a cena 3D (:mod:`core.cena_3d`) com o que o projeto tem: o esqueleto do SolidWorks (cada
barra com o perfil do catálogo e a alma lida pela macro; as chapas de piso), os guarda-corpos das
bordas, as cargas de um caso do plano de cargas (setas e pentes), as reações nas bases dos pilares
e os apoios, e a cor de cada barra por tipo, perfil ou por um resultado (vento, esforço normal,
aproveitamento). Sem Streamlit.

Viabilidade das setas (o que dá para mostrar com o que o programa lê):

* **Cargas** — as linhas do plano de cargas cujo elemento é uma barra do esqueleto (pelo nome do
  corpo ou da viga do Simulation): kN/m vira um pente ao longo da barra, kN uma seta no meio dela
  (no SolidWorks é a força "por item"). Carga por área, por nó ou por texto livre ("Pórtico P1…")
  não tem lugar certo e fica listada como não localizada.
* **Reações** — o quadro das fundações dá, em cada pilar marcado como Pilar, o N na base (vertical,
  compressão positiva): vira uma seta para cima no pé do pilar. As forças horizontais V₁ e V₂ estão
  nos eixos da seção do Simulation: com a direção 1 da seção (macro v6) e o sentido tirado de um
  caso com carga no pilar (:mod:`core.direcoes_da_secao`), viram a seta horizontal H; sem isso,
  ficam no rótulo (H = √(V₁² + V₂²)) e o motivo vai nos avisos.
* **Apoios** — no pé de cada pilar (a ponta mais baixa): **engastado** quando a base tem momento
  num caso importado, **articulado** quando nunca tem; sem esforços importados, o pé dos pilares que
  chegam no chão, sem o tipo.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from core import cantoneiras
from core import cargas_pelo_modelo as cpm
from core import cena_3d as c3
from core import cena_escada as cesc
from core import direcoes_da_secao as ds
from core import esforcos_modelo as em
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf
from core import section_catalog as sc
from core import vento_por_barras as vpb

COR_POR_TIPO = "Tipo de barra"
COR_POR_PERFIL = "Perfil"
COR_POR_VENTO = "Carga do vento"
COR_POR_NORMAL = "Esforço normal (caso importado)"
COR_POR_APROVEITAMENTO = "Aproveitamento (verificação ELU)"
COR_UNICA = "Cor única"

CORES_POR_TIPO: dict[str, str] = {
    ld.TIPO_PILAR: "#3f6fb5",
    ld.TIPO_VIGA: "#8a929c",
    ld.TIPO_CONTRAVENTAMENTO: "#d4760a",
}
COR_DE_OUTRO_TIPO = "#a1887f"
COR_DO_GUARDA_CORPO = "#a9bcd6"
COR_DA_CARGA = "#d4760a"
COR_DA_REACAO = "#2e7d32"
TOLERANCIA_DO_CHAO_M = 0.20  # pé de pilar e de escada no chão, com placa e graute
MOMENTO_DE_ENGASTE_KNM = 0.05  # base com mais que isso num caso: engastada
REACAO_MINIMA_KN = 0.05  # menos que isso não vira seta
#: A seta horizontal da reação só nos pilares em pé (até 15° do prumo).
COS_PILAR_EM_PE = math.cos(math.radians(15.0))


def _n(valor: float, casas: int = 2) -> str:
    if round(valor, casas) == 0:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


# ---------------------------------------------------------------------------------------------
# Seções
# ---------------------------------------------------------------------------------------------
def secao_do_perfil(perfil: str, secao_mm: Sequence[float] | None = None) -> c3.Secao:
    """A seção para desenhar: pelo catálogo (W, HP, I, U, C, T, tubos, barras), pelas cantoneiras
    ou, sem o perfil, pelas medidas que a macro leu (retângulo; Ø no nome = circular)."""
    nome = (perfil or "").strip()
    if nome:
        try:
            p = sc.obter_perfil(nome)
        except (KeyError, ValueError):
            p = None
        if p is not None:
            familia = p.familia.lower()
            d, b = p.altura_mm / 1e3, p.largura_mm / 1e3
            tw, tf = p.espessura_alma_mm / 1e3, p.espessura_mesa_mm / 1e3
            if familia.startswith(("w ", "w(", "hp", "i ")) or familia.startswith("w"):
                forma = c3.FORMA_I
            elif familia.startswith(("u", "c ")):
                forma = c3.FORMA_U
            elif familia.startswith("t "):
                forma = c3.FORMA_T
            elif "tubo retangular" in familia:
                forma = c3.FORMA_TUBO_RETANGULAR
            elif "circular" in familia:
                forma = c3.FORMA_TUBO_CIRCULAR
            else:
                forma = c3.FORMA_CHEIA
            if c3.finito(d, b, tw, tf) and d > 0 and b > 0:
                return c3.Secao(forma, d, b, tw, tf)
        if nome.upper().startswith("L"):
            try:
                cant = cantoneiras.obter_cantoneira(nome)
            except (KeyError, ValueError):
                cant = None
            if cant is not None:
                return c3.Secao(
                    c3.FORMA_L, cant.b_mm / 1e3, cant.b_mm / 1e3, cant.t_mm / 1e3, cant.t_mm / 1e3
                )
    if secao_mm and len(secao_mm) >= 2 and c3.finito(*secao_mm) and min(secao_mm) > 0:
        maior, menor = max(secao_mm) / 1e3, min(secao_mm) / 1e3
        if "Ø" in nome or "TC" in nome.upper():
            return c3.Secao(c3.FORMA_TUBO_CIRCULAR, maior, maior)
        return c3.Secao(c3.FORMA_CHEIA, maior, menor)
    return c3.Secao(c3.FORMA_CHEIA, 0.1, 0.1)


# ---------------------------------------------------------------------------------------------
# Nomes: corpo do esqueleto × viga do Simulation × elemento do plano de cargas
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Nomes:
    """Os nomes de cada corpo: no Simulation ("Viga-12(…)") e o que o plano usa ("corpo (Viga-12)")."""

    do_simulation: Mapping[str, str]  # corpo → viga do Simulation

    def corpo_do_elemento(self, elemento: str, corpos: Mapping[str, ld.CorpoDoModelo]) -> str:
        texto = (elemento or "").strip()
        if texto in corpos:
            return texto
        inverso = {v: k for k, v in self.do_simulation.items()}
        if texto in inverso:
            return inverso[texto]
        if texto.endswith(")") and " (" in texto:
            base = texto[: texto.rindex(" (")]
            if base in corpos:
                return base
        candidato = ld.nome_do_corpo(texto)
        return candidato if candidato in corpos else ""

    @classmethod
    def do_projeto(cls, g: ld.GeometriaDoModelo, dados: em.EsforcosDoModelo | None) -> Nomes:
        if dados is None or not dados.casos:
            return cls({})
        return cls(
            {
                corpo.nome: barra
                for barra, corpo in ld.correspondencia(
                    g, dados.nomes_dos_membros, dados
                ).corpos.items()
            }
        )


def _corpos(g: ld.GeometriaDoModelo) -> dict[str, ld.CorpoDoModelo]:
    """As barras e os blocos (pedaços curtos) do esqueleto, com coordenadas válidas."""
    return {
        c.nome: c
        for c in g.corpos
        if c.forma != ld.FORMA_CHAPA and c.comprimento_m > 0 and c3.finito(*c.inicio, *c.fim)
    }


def _planta(p: Sequence[float], eixo_vertical: str) -> c3.Ponto:
    return vpb.para_a_planta(p, eixo_vertical)


def _tipo(corpo: ld.CorpoDoModelo, eixo_vertical: str, tipos: Mapping[str, str]) -> str:
    tipo = tipos.get(corpo.nome, "")
    if tipo and tipo != "—":
        return tipo
    return ld.tipo_pela_geometria(corpo, eixo_vertical)[0]


# ---------------------------------------------------------------------------------------------
# Barras, chapas e guarda-corpos
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ValoresPorBarra:
    """Um resultado por corpo, para a cor: kN/m do vento, N (tração +), aproveitamento…"""

    valores: Mapping[str, float]
    unidade: str
    titulo: str
    paleta: tuple[str, ...] = c3.PALETA_CARGA
    com_sinal: bool = False  # escala de −máx a +máx (tração e compressão)
    maximo_fixo: float | None = None  # aproveitamento: 0 a 1


def barras_da_cena(
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    *,
    cor_por: str = COR_POR_TIPO,
    valores: ValoresPorBarra | None = None,
    tipos: Mapping[str, str] | None = None,
    ocultos: Iterable[str] = (),
    destaque: str = "",
    rotulos: Mapping[str, str] | None = None,
) -> tuple[list[c3.BarraCena], list[tuple[str, str]], c3.EscalaDeCor | None]:
    """As barras com a seção do perfil e a cor; mais a legenda e a escala de cor."""
    tipos = tipos or {}
    rotulos = rotulos or {}
    perfis = ld.perfis_do_esqueleto(g)
    ocultos_set = set(ocultos)
    corpos = _corpos(g)
    paleta_de_perfis: dict[str, str] = {}
    escala = None
    if cor_por in (COR_POR_VENTO, COR_POR_NORMAL, COR_POR_APROVEITAMENTO) and valores is not None:
        numeros = [v for v in valores.valores.values() if c3.finito(v)]
        maximo = valores.maximo_fixo or max((abs(v) for v in numeros), default=0.0) or 1.0
        minimo = -maximo if valores.com_sinal else 0.0
        escala = c3.EscalaDeCor(minimo, maximo, valores.unidade, valores.titulo, valores.paleta)
    barras = []
    tipos_vistos: dict[str, str] = {}
    for corpo in corpos.values():
        tipo = _tipo(corpo, eixo_vertical, tipos)
        if tipo in ocultos_set:
            continue
        perfil = perfis.get(corpo.nome, ("", ""))[0]
        if cor_por == COR_POR_PERFIL:
            chave = perfil or corpo.descricao or "?"
            if chave not in paleta_de_perfis:
                paleta_de_perfis[chave] = c3.PALETA_CATEGORIAS[
                    len(paleta_de_perfis) % len(c3.PALETA_CATEGORIAS)
                ]
            cor = paleta_de_perfis[chave]
        elif escala is not None and valores is not None:
            valor = valores.valores.get(corpo.nome)
            if valor is None or not c3.finito(valor):
                cor = "#cfd5dc"
            elif valores.com_sinal:
                cor = c3.cor_da_escala((valor - escala.minimo) / (escala.maximo - escala.minimo),
                                       valores.paleta)  # fmt: skip
            else:
                cor = c3.cor_da_escala(0.08 + 0.92 * abs(valor) / escala.maximo, valores.paleta)
        elif cor_por == COR_UNICA:
            cor = "#8a929c"
        else:
            cor = CORES_POR_TIPO.get(tipo, COR_DE_OUTRO_TIPO)
            tipos_vistos[tipo] = cor
        barras.append(
            c3.BarraCena(
                nome=corpo.nome,
                inicio=_planta(corpo.inicio, eixo_vertical),
                fim=_planta(corpo.fim, eixo_vertical),
                secao=secao_do_perfil(perfil, corpo.secao_mm),
                alma=_planta(corpo.direcao_secao, eixo_vertical) if corpo.direcao_secao else None,
                cor=cor,
                rotulo=rotulos.get(corpo.nome, ""),
                destaque=corpo.nome == destaque,
                grupo=tipo,
            )
        )
    if cor_por == COR_POR_PERFIL:
        legenda = [(cor, nome) for nome, cor in list(paleta_de_perfis.items())[:8]]
    elif escala is None and cor_por != COR_UNICA:
        legenda = [(cor, tipo.lower()) for tipo, cor in tipos_vistos.items()]
    else:
        legenda = []
    return barras, legenda, escala


ESPELHO_DE_REFERENCIA_M = 0.18  # para desenhar os degraus de um lance que veio como chapa


def _degraus_do_lance(nome: str, pontos: Sequence[c3.Ponto]) -> list[c3.BarraCena]:
    """Os degraus de um lance que o esqueleto traz como chapa inclinada: espelhos de ~18 cm na
    altura do lance, cada degrau uma grade de 35 mm na largura da chapa."""
    normal = c3.normal_da_face(pontos)
    if normal is None:
        return []
    descida = c3._unitario(c3._sub((0.0, 0.0, -1.0), c3._escala(normal, -normal[2])))
    if descida is None:
        return []
    lado = c3._unitario(c3._cross(normal, descida))
    if lado is None:
        return []
    centro = tuple(sum(p[k] for p in pontos) / len(pontos) for k in range(3))
    s = [c3._dot(c3._sub(p, centro), descida) for p in pontos]
    t = [c3._dot(c3._sub(p, centro), lado) for p in pontos]
    s0, s1, t0, t1 = min(s), max(s), min(t), max(t)
    queda = (s1 - s0) * abs(descida[2])
    corrida = (s1 - s0) * math.hypot(descida[0], descida[1])
    espelhos = max(2, round(queda / ESPELHO_DE_REFERENCIA_M))
    piso = corrida / espelhos
    degraus = []
    for j in range(1, espelhos):
        sj = s1 - (s1 - s0) * j / espelhos

        def ponto(tt: float, sj: float = sj) -> c3.Ponto:
            return (
                centro[0] + sj * descida[0] + tt * lado[0],
                centro[1] + sj * descida[1] + tt * lado[1],
                centro[2] + sj * descida[2] + tt * lado[2] - cesc.ESPESSURA_DO_DEGRAU_M / 2,
            )

        degraus.append(
            c3.BarraCena(
                f"{nome} degrau {j}",
                ponto(t0 + 0.02),
                ponto(t1 - 0.02),
                c3.Secao(c3.FORMA_CHEIA, cesc.ESPESSURA_DO_DEGRAU_M, 0.96 * piso),
                (0.0, 0.0, 1.0),
                cesc.COR_DEGRAU,
                grupo="degrau",
            )
        )
    return degraus


def chapas_da_cena(
    g: ld.GeometriaDoModelo, eixo_vertical: str, modo: str = cesc.MODO_DETALHADO
) -> tuple[list[c3.BarraCena], list[c3.PainelCena]]:
    """As chapas de piso como painéis; os lances (chapa inclinada) com os degraus (escada
    detalhada) ou como tampa translúcida (casca)."""
    try:
        chapas, _ = cpm.chapas_do_piso(g, eixo_vertical)
    except (ArithmeticError, ValueError, IndexError):
        return [], []
    barras: list[c3.BarraCena] = []
    paineis: list[c3.PainelCena] = []
    for ch in chapas:
        pontos = tuple(_planta(gm._no_espaco(ch, q), eixo_vertical) for q in ch.poligono)
        if len(pontos) < 3:
            continue
        lance = ch.inclinacao_graus > gm.INCLINACAO_DE_ESCADA_GRAUS
        if lance and modo == cesc.MODO_DETALHADO:
            degraus = _degraus_do_lance(ch.nome, pontos)
            if degraus:
                barras += degraus
                continue
        cor, opacidade = ("#7c9cc4", 0.30) if lance else ("#c9d6e6", 0.30)
        paineis.append(
            c3.PainelCena(ch.nome, pontos, cor, opacidade, "lance" if lance else "chapa")
        )
    return barras, paineis


TUBO_DO_GUARDA_CORPO = c3.Secao(c3.FORMA_TUBO_CIRCULAR, 0.042, 0.042)
RODAPE_M = 0.10
VAO_DE_MONTANTE_M = 1.5


def guarda_corpos_da_cena(
    trechos: Iterable[gm.TrechoDeBorda],
    eixo_vertical: str,
    altura_m: float,
    modo: str = cesc.MODO_DETALHADO,
) -> tuple[list[c3.BarraCena], list[c3.PainelCena]]:
    """Cada trecho como guarda-corpo de verdade (corrimão e travessa intermediária em tubo de
    42 mm, montantes a cada ~1,5 m e o rodapé translúcido) ou, na casca, um painel translúcido."""
    barras: list[c3.BarraCena] = []
    paineis: list[c3.PainelCena] = []
    if not (c3.finito(altura_m) and altura_m > 0):
        return barras, paineis
    if modo == cesc.MODO_CASCA:
        for t in trechos:
            a, b = _planta(t.inicio, eixo_vertical), _planta(t.fim, eixo_vertical)
            if c3.finito(*a, *b) and math.dist(a, b) > 1e-3:
                paineis.append(
                    c3.PainelCena(
                        f"GC {t.id}",
                        (a, b, (b[0], b[1], b[2] + altura_m), (a[0], a[1], a[2] + altura_m)),
                        cesc.COR_CASCA,
                        0.22,
                        "gc",
                    )  # fmt: skip
                )
        return barras, paineis
    for t in trechos:
        a, b = _planta(t.inicio, eixo_vertical), _planta(t.fim, eixo_vertical)
        if not (c3.finito(*a, *b)):
            continue
        comprimento = math.dist(a, b)
        if comprimento < 1e-3:
            continue

        def em_cima(p: c3.Ponto, h: float) -> c3.Ponto:
            return (p[0], p[1], p[2] + h)

        for k, h in enumerate((altura_m, altura_m / 2)):
            barras.append(
                c3.BarraCena(
                    f"GC {t.id} travessa {k}",
                    em_cima(a, h),
                    em_cima(b, h),
                    TUBO_DO_GUARDA_CORPO,
                    None,
                    COR_DO_GUARDA_CORPO,
                    grupo="gc",
                )  # fmt: skip
            )
        montantes = max(1, round(comprimento / VAO_DE_MONTANTE_M))
        for k in range(montantes + 1):
            s = k / montantes
            p: c3.Ponto = (
                a[0] + s * (b[0] - a[0]),
                a[1] + s * (b[1] - a[1]),
                a[2] + s * (b[2] - a[2]),
            )
            barras.append(
                c3.BarraCena(
                    f"GC {t.id} montante {k}",
                    p,
                    em_cima(p, altura_m),
                    TUBO_DO_GUARDA_CORPO,
                    None,
                    COR_DO_GUARDA_CORPO,
                    grupo="gc",
                )  # fmt: skip
            )
        paineis.append(
            c3.PainelCena(
                f"GC {t.id} rodapé",
                (a, b, em_cima(b, RODAPE_M), em_cima(a, RODAPE_M)),
                COR_DO_GUARDA_CORPO,
                0.45,
                "gc",
            )  # fmt: skip
        )
    return barras, paineis


# ---------------------------------------------------------------------------------------------
# Cargas de um caso do plano
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CargasNaCena:
    distribuidas: tuple[c3.CargaDistribuidaCena, ...]
    setas: tuple[c3.SetaCena, ...]
    nao_localizadas: tuple[str, ...]  # elementos do plano que não são barras do esqueleto
    total_kN: tuple[float, float, float]  # resultante do que foi desenhado (planta)


def _vetor_da_carga(c: pc.CargaDoModelo) -> c3.Ponto | None:
    """Na planta: X e Y com o sinal do valor; "Z (vertical)" positivo para baixo."""
    direcao = c.direcao.replace("−", "-").strip()
    if not c3.finito(c.valor):
        return None
    if direcao.startswith("Z"):
        return (0.0, 0.0, -c.valor)
    eixo = direcao.lstrip("+-")
    if eixo == "X":
        return (c.valor, 0.0, 0.0)
    if eixo == "Y":
        return (0.0, c.valor, 0.0)
    return None


def cargas_do_caso(
    plano: pc.PlanoDeCargas,
    caso: str,
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    nomes: Nomes,
    *,
    rotulos_maximos: int = 6,
) -> CargasNaCena:
    acao = plano.acao(caso)
    if acao is None:
        return CargasNaCena((), (), (), (0.0, 0.0, 0.0))
    corpos = _corpos(g)
    distribuidas: list[c3.CargaDistribuidaCena] = []
    setas: list[c3.SetaCena] = []
    fora: list[str] = []
    total = [0.0, 0.0, 0.0]
    magnitudes: list[tuple[float, int, str]] = []  # para rotular só as maiores
    for carga in acao.cargas:
        nome = nomes.corpo_do_elemento(carga.elemento, corpos)
        vetor = _vetor_da_carga(carga)
        if not nome or vetor is None or carga.unidade not in ("kN/m", "kN"):
            fora.append(f"{carga.elemento} ({_n(carga.valor)} {carga.unidade})")
            continue
        corpo = corpos[nome]
        a, b = _planta(corpo.inicio, eixo_vertical), _planta(corpo.fim, eixo_vertical)
        if carga.unidade == "kN/m":
            distribuidas.append(c3.CargaDistribuidaCena(a, b, vetor, "", COR_DA_CARGA, caso))
            magnitudes.append((abs(carga.valor), len(distribuidas) - 1, "d"))
            resultante = [v * corpo.comprimento_m * carga.quantidade for v in vetor]
        else:
            meio = tuple((a[k] + b[k]) / 2 for k in range(3))
            setas.append(c3.SetaCena(meio, vetor, "", COR_DA_CARGA, False, caso))  # type: ignore[arg-type]
            magnitudes.append((abs(carga.valor), len(setas) - 1, "s"))
            resultante = [v * carga.quantidade for v in vetor]
        total = [total[k] + resultante[k] for k in range(3)]
    for _, indice, tipo in sorted(magnitudes, reverse=True)[:rotulos_maximos]:
        if tipo == "d":
            c = distribuidas[indice]
            rotulo = f"{_n(c3._norma(c.vetor_por_metro), 2)} kN/m"
            distribuidas[indice] = c3.CargaDistribuidaCena(
                c.inicio, c.fim, c.vetor_por_metro, rotulo, c.cor, c.grupo
            )
        else:
            s = setas[indice]
            setas[indice] = c3.SetaCena(s.ponto, s.vetor, f"{_n(c3._norma(s.vetor), 2)} kN",
                                        s.cor, s.reacao, s.grupo)  # fmt: skip
    return CargasNaCena(tuple(distribuidas), tuple(setas), tuple(fora), tuple(total))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------------------------
# Apoios e reações
# ---------------------------------------------------------------------------------------------
def cargas_distribuidas_por_corpo(
    plano: pc.PlanoDeCargas,
    casos: Iterable[str],
    g: ld.GeometriaDoModelo,
    nomes: Nomes,
) -> dict[str, dict[str, c3.Ponto]]:
    """Caso → corpo → a carga distribuída total que o plano manda na barra (kN, planta): o que
    o Simulation tem de mostrar dentro dos elementos dela."""
    corpos = _corpos(g)
    resultado: dict[str, dict[str, c3.Ponto]] = {}
    for caso in casos:
        acao = plano.acao(caso)
        if acao is None:
            continue
        por_corpo: dict[str, list[float]] = {}
        for carga in acao.cargas:
            if carga.unidade != "kN/m":
                continue
            nome = nomes.corpo_do_elemento(carga.elemento, corpos)
            vetor = _vetor_da_carga(carga)
            if not nome or vetor is None:
                continue
            fator = corpos[nome].comprimento_m * carga.quantidade
            soma = por_corpo.setdefault(nome, [0.0, 0.0, 0.0])
            for k in range(3):
                soma[k] += vetor[k] * fator
        resultado[caso] = {nome: (v[0], v[1], v[2]) for nome, v in por_corpo.items()}
    return resultado


@dataclass(frozen=True)
class ApoiosNaCena:
    apoios: tuple[c3.ApoioCena, ...]
    reacoes: tuple[c3.SetaCena, ...]
    avisos: tuple[str, ...]
    soma_vertical_kN: float = 0.0
    #: Soma das reações horizontais desenhadas (planta, kN) e quantos pilares as têm.
    soma_horizontal_kN: tuple[float, float] = (0.0, 0.0)
    horizontais: int = 0
    direcoes: ds.DirecoesDosPilares | None = None
    conferencia: str = ""  # as horizontais contra o arquivo de reações


def _pe(corpo: ld.CorpoDoModelo, eixo_vertical: str) -> c3.Ponto:
    a, b = _planta(corpo.inicio, eixo_vertical), _planta(corpo.fim, eixo_vertical)
    return a if a[2] <= b[2] else b


def _direcoes(
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    dados: em.EsforcosDoModelo,
    nomes: Nomes,
    quadro: qf.QuadroDeFundacoes,
    plano: pc.PlanoDeCargas | None,
) -> ds.DirecoesDosPilares:
    corpos = _corpos(g)
    inverso = {v: k for k, v in nomes.do_simulation.items()}
    das_vigas = {
        p.pilar: corpo
        for p in quadro.pilares
        if (corpo := corpos.get(inverso.get(p.pilar, ld.nome_do_corpo(p.pilar)))) is not None
    }
    aplicadas = (
        cargas_distribuidas_por_corpo(plano, dados.casos, g, nomes) if plano is not None else {}
    )
    perfis = ld.perfis_do_esqueleto(ld.GeometriaDoModelo(corpos=tuple(das_vigas.values())))
    secoes = {
        c.nome: secao_do_perfil(perfis.get(c.nome, ("", ""))[0], c.secao_mm)
        for c in das_vigas.values()
    }
    return ds.direcoes_dos_pilares(quadro, dados, das_vigas, eixo_vertical, aplicadas, secoes)


def apoios_e_reacoes(
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    dados: em.EsforcosDoModelo | None,
    nomes: Nomes,
    caso: str = "",
    *,
    plano: pc.PlanoDeCargas | None = None,
) -> ApoiosNaCena:
    """Os apoios no pé dos pilares e, com um caso importado, a reação em cada um: a vertical
    sempre; a horizontal quando a direção da seção do pilar é sabida (:mod:`core.direcoes_da_secao`,
    com o ``plano`` de cargas para tirar o sentido)."""
    corpos = _corpos(g)
    avisos: list[str] = []
    if dados is not None and dados.casos:
        try:
            quadro = qf.montar_quadro(dados)
        except (ArithmeticError, ValueError, KeyError) as erro:
            quadro = None
            avisos.append(f"O quadro das fundações não foi montado ({erro}).")
    else:
        quadro = None
    inverso = {v: k for k, v in nomes.do_simulation.items()}
    apoios: list[c3.ApoioCena] = []
    reacoes: list[c3.SetaCena] = []
    soma = 0.0
    soma_h = [0.0, 0.0]
    horizontais = 0
    direcoes: ds.DirecoesDosPilares | None = None
    conferencia = ""
    if quadro is not None and quadro.pilares and dados is not None and caso in dados.casos:
        try:
            direcoes = _direcoes(g, eixo_vertical, dados, nomes, quadro, plano)
        except (ArithmeticError, ValueError, KeyError) as erro:
            avisos.append(f"As direções das seções dos pilares não foram lidas ({erro}).")
        else:
            avisos.extend(direcoes.avisos)
    if quadro is not None and quadro.pilares:
        for pilar in quadro.pilares:
            corpo = corpos.get(inverso.get(pilar.pilar, ld.nome_do_corpo(pilar.pilar)))
            if corpo is None:
                avisos.append(
                    f"{pilar.pilar}: o pilar não está no esqueleto (o apoio não aparece)."
                )
                continue
            momentos = [max(abs(c.m1), abs(c.m2)) for c in pilar.cargas]
            tipo = (
                c3.APOIO_ENGASTE
                if any(m > MOMENTO_DE_ENGASTE_KNM for m in momentos)
                else c3.APOIO_ARTICULADO
            )
            pe = _pe(corpo, eixo_vertical)
            chao = min(_pe(c, eixo_vertical)[2] for c in corpos.values())
            if pe[2] - chao > 0.5:
                avisos.append(
                    f"{pilar.pilar} está como Pilar, mas o pé dele fica {_n(pe[2] - chao, 2)} m "
                    "acima do chão do modelo: confira o tipo da barra em Esforços do modelo."
                )
            apoios.append(c3.ApoioCena(pe, tipo, "", "apoio"))
            carga = next((c for c in pilar.cargas if c.caso == caso), None)
            if carga is not None and c3.finito(carga.n):
                d = direcoes.pilares.get(pilar.pilar) if direcoes is not None else None
                vetor_h = (
                    d.horizontal(carga)
                    if d is not None and abs(d.axial[2]) >= COS_PILAR_EM_PE
                    else None
                )
                h = math.hypot(carga.v1, carga.v2)
                if vetor_h is not None and c3.finito(*vetor_h):
                    rotulo = f"N {_n(carga.n, 1)} kN"
                    horizontais += 1
                    soma_h = [soma_h[0] + vetor_h[0], soma_h[1] + vetor_h[1]]
                    h = math.hypot(vetor_h[0], vetor_h[1])
                    if h >= REACAO_MINIMA_KN:
                        reacoes.append(
                            c3.SetaCena(pe, (vetor_h[0], vetor_h[1], 0.0), f"H {_n(h, 1)} kN",
                                        COR_DA_REACAO, True, "reacao")
                        )  # fmt: skip
                else:
                    rotulo = f"N {_n(carga.n, 1)} kN" + (f" · H {_n(h, 1)} kN" if h >= 0.05 else "")
                if abs(carga.n) >= REACAO_MINIMA_KN:
                    reacoes.append(
                        c3.SetaCena(pe, (0.0, 0.0, carga.n), rotulo, COR_DA_REACAO, True, "reacao")
                    )
                soma += carga.n
        if direcoes is not None and dados is not None and caso in dados.casos:
            reacoes_do_arquivo = dados.casos[caso].reacoes
            if reacoes_do_arquivo is not None:
                conferencia = ds.conferir_horizontais(
                    direcoes,
                    quadro,
                    caso,
                    vpb.para_a_planta(reacoes_do_arquivo.modelo, eixo_vertical),
                )
        if caso and not reacoes and caso not in dados.casos:  # type: ignore[union-attr]
            avisos.append(f"O caso {caso} não foi importado em Esforços do modelo: sem reações.")
    # O pé de cada barra em pé que chega no chão e não está no quadro (sem o tipo).
    if not corpos:
        return ApoiosNaCena(tuple(apoios), tuple(reacoes), tuple(avisos), soma, (soma_h[0], soma_h[1]),
                            horizontais, direcoes, conferencia)  # fmt: skip
    chao = min(_pe(c, eixo_vertical)[2] for c in corpos.values())
    sem_tipo = 0
    for corpo in corpos.values():
        pe = _pe(corpo, eixo_vertical)
        if pe[2] - chao > TOLERANCIA_DO_CHAO_M:
            continue  # o pé dos pilares e das longarinas que chegam no chão
        if any(math.dist(pe, a.ponto) < 0.10 for a in apoios):
            continue
        apoios.append(c3.ApoioCena(pe, c3.APOIO_DESCONHECIDO, "", "apoio"))
        sem_tipo += 1
    if sem_tipo:
        avisos.append(
            f"{sem_tipo} apoio(s) no chão sem o tipo: importe os esforços e marque a "
            "barra como Pilar (Esforços do modelo) para o programa dizer engastado ou articulado e "
            "mostrar a reação."
        )
    return ApoiosNaCena(tuple(apoios), tuple(reacoes), tuple(avisos), soma, (soma_h[0], soma_h[1]),
                        horizontais, direcoes, conferencia)  # fmt: skip


# ---------------------------------------------------------------------------------------------
# Registro da vista (memorial)
# ---------------------------------------------------------------------------------------------
MODULO_ID = "modelo_3d"
MODULO_TITULO = "Modelo em 3D"


def registro_da_vista(
    cena: c3.Cena,
    *,
    azimute: float,
    elevacao: float,
    perfil_real: bool,
    descricao: str,
    contexto: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """A vista do modelo para o memorial: a cena gravada (o memorial a desenha de novo em PNG)."""
    from core.technical_records import criar_registro_tecnico

    destaque = f"Vista do modelo em 3D: {descricao}."
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Modelo em 3D — {cena.titulo or 'vista'}",
        status="Calculado",
        resumo=destaque,
        entradas={"vista": descricao, **dict(contexto or {})},
        resultados={
            "destaque_memorial": destaque,
            "figura_3d": {
                "cena": c3.cena_para_dicionario(cena),
                "azimute": azimute,
                "elevacao": elevacao,
                "perfil_real": perfil_real,
                "legenda": f"Modelo em 3D: {descricao}.",
            },
        },
        metodo=(
            "Cada barra do esqueleto do SolidWorks desenhada com a seção do perfil (catálogo) ao "
            "longo da linha de centro, na posição da alma lida pela macro; vista paralela."
        ),
        conclusao=destaque,
    )


# ---------------------------------------------------------------------------------------------
# Resultados como cor
# ---------------------------------------------------------------------------------------------
def valores_do_vento(
    g: ld.GeometriaDoModelo, eixo_vertical: str, parametros: object, angulo: int
) -> ValoresPorBarra:
    barras = vpb.barras_do_esqueleto(g, eixo_vertical)
    r = vpb.calcular(vpb.EntradaPorBarras(tuple(barras), parametros, direcoes=(angulo,)))  # type: ignore[arg-type]
    d = r.direcao(angulo)
    return ValoresPorBarra(
        {f.barra: f.kN_m for f in d.barras},
        "kN/m",
        f"carga do vento a {angulo}° ({vpb.SENTIDOS[angulo]})",
    )


def valores_do_normal(dados: em.EsforcosDoModelo, caso: str, nomes: Nomes) -> ValoresPorBarra:
    """N de cada barra no caso (o de maior módulo entre as pontas; tração positiva)."""
    importado = dados.casos.get(caso)
    inverso = {v: k for k, v in nomes.do_simulation.items()}
    valores: dict[str, float] = {}
    if importado is not None:
        for membro, pontos in importado.membros.items():
            corpo = inverso.get(membro, ld.nome_do_corpo(membro))
            ns = [p.n for p in pontos if c3.finito(p.n)]
            if corpo and ns:
                valores[corpo] = max(ns, key=abs)
    return ValoresPorBarra(
        valores, "kN", f"esforço normal no caso {caso} (tração +)", c3.PALETA_SINAL, com_sinal=True
    )


def valores_do_aproveitamento(
    dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas, nomes: Nomes
) -> tuple[ValoresPorBarra, list[str]]:
    from core import verificacao_barras as vb

    try:
        resultados, avisos = vb.verificar_barras(dados, plano)
    except (ArithmeticError, ValueError, KeyError) as erro:
        return ValoresPorBarra({}, "", "aproveitamento"), [f"A verificação não rodou ({erro})."]
    inverso = {v: k for k, v in nomes.do_simulation.items()}
    valores = {
        inverso.get(r.membro, ld.nome_do_corpo(r.membro)): float(r.aproveitamento)
        for r in resultados
        if r.aproveitamento is not None and c3.finito(r.aproveitamento)
    }
    return (
        ValoresPorBarra(
            valores, "", "aproveitamento (0 a 100 %)", c3.PALETA_APROVEITAMENTO, maximo_fixo=1.0
        ),
        list(avisos),
    )
