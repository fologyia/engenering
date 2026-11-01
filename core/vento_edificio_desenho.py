"""Desenhos da ação do vento na edificação fechada (NBR 6123:2023, seção 6): as zonas de pressão em
3D, as faixas de altas sucções das vedações e o pórtico transversal com as cargas do vento.

Tudo sai da mesma geometria do cálculo (:mod:`core.vento_edificio`):

* cada zona vira os polígonos em que ela está nas paredes e no telhado, e a soma das áreas desses
  polígonos é a área da zona usada nas forças — o desenho mostra exatamente o que foi calculado;
* a cena 3D vai para a página (SVG) e para o memorial (PNG) pelo núcleo :mod:`core.cena_3d`;
* as faixas de ``c_pe`` médio seguem as figuras das Tabelas 6, 7 e 8 (larguras ``y`` e ``x`` e,
  nas paredes, ``mín(0,2·b; h)`` junto a cada canto);
* o pórtico transversal com as cargas normais aos elementos vira um modelo do núcleo de pórtico
  plano (:mod:`core.portico_plano`), que dá as figuras no estilo do Ftool (cargas, reações, N, V, M
  e deformada) na página e no memorial.

Eixos como no cálculo: x ao longo de ``a``, y ao longo de ``b``, z para cima; na cobertura de uma
água o lado alto fica em y = 0. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core import cena_3d as c3
from core import portico_plano as pp
from core import vento_portico as vp
from core.vento_edificio import (
    COBERTURA_UMA_AGUA,
    CasoDeVento,
    GeometriaEdificio,
    ResultadoEdificio,
)
from core.vento_nbr6123 import numero_ptbr

Ponto = tuple[float, float, float]

#: Escala de C_e: azul (sucção) até −2, branco em 0, vermelho (sobrepressão) até +1. As cores são
#: as de :func:`cor_do_ce` nos quatro valores inteiros, e a interpolação linear entre elas é a
#: mesma conta: a escala da cena e o mapa da planta mostram a mesma cor para o mesmo C_e.
CE_MINIMO_DA_ESCALA = -2.0
CE_MAXIMO_DA_ESCALA = 1.0
PALETA_CE: tuple[str, ...] = ("#5087ff", "#a7c3ff", "#ffffff", "#ff6969")
COR_DO_VENTO = "#d4760a"

#: Vista padrão: de barlavento e de um lado, de cima (vê a parede de barlavento, uma lateral e o
#: telhado). O vento a −90° (uma água) é visto do outro lado.
ELEVACAO_DA_VISTA = 26.0
AZIMUTE_DA_VISTA: dict[int, float] = {0: -125.0, 90: -125.0, -90: 125.0, 45: -125.0, -45: 125.0}


def cor_do_ce(ce: float) -> str:
    """Azul para sucção (C_e < 0) e vermelho para sobrepressão, em tons claros que deixam o texto
    legível; satura em −2 e em +1."""
    if ce >= 0:
        t = min(ce / 1.0, 1.0)
        return f"#ff{round(255 - 150 * t):02x}{round(255 - 150 * t):02x}"
    t = min(-ce / 2.0, 1.0)
    return f"#{round(255 - 175 * t):02x}{round(255 - 120 * t):02x}ff"


def _n(valor: float, casas: int = 2) -> str:
    return numero_ptbr(valor, casas).replace("-", "−")


def _graus(alpha: int) -> str:
    return f"{alpha}°".replace("-", "−")


def _sinal(valor: float, casas: int = 1) -> str:
    return ("+" if valor > 0 else "") + _n(valor, casas)


# ---------------------------------------------------------------------------------------------
# Polígonos de cada zona
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FaceDaZona:
    """Um pedaço plano de uma zona: o polígono em 3D e a normal externa."""

    zona: str  # o id da zona (Zona.id)
    superficie: str  # "parede" | "telhado"
    rotulo: str  # o nome da parte nesta face ("A1", "C2", "E"…)
    pontos: tuple[Ponto, ...]
    normal: Ponto

    @property
    def area_m2(self) -> float:
        """Área do polígono plano (fórmula de Newell)."""
        nx = ny = nz = 0.0
        for i, p in enumerate(self.pontos):
            q = self.pontos[(i + 1) % len(self.pontos)]
            nx += (p[1] - q[1]) * (p[2] + q[2])
            ny += (p[2] - q[2]) * (p[0] + q[0])
            nz += (p[0] - q[0]) * (p[1] + q[1])
        return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)

    @property
    def centro(self) -> Ponto:
        n = len(self.pontos)
        return (
            sum(p[0] for p in self.pontos) / n,
            sum(p[1] for p in self.pontos) / n,
            sum(p[2] for p in self.pontos) / n,
        )


def altura_do_telhado(g: GeometriaEdificio, y: float) -> float:
    """Cota do telhado (ou do topo da parede curta) na posição y ao longo de b."""
    return g.altura_da_parede_curta_m(min(max(y, 0.0), g.b_m))


def _quebras(g: GeometriaEdificio, y0: float, y1: float) -> list[float]:
    """y0, a cumeeira (se estiver entre eles, na duas águas) e y1."""
    pontos = [y0, y1]
    if g.cobertura != COBERTURA_UMA_AGUA and y0 < g.b_m / 2.0 < y1:
        pontos.insert(1, g.b_m / 2.0)
    return pontos


def _empena(g: GeometriaEdificio, x: float, y0: float, y1: float) -> tuple[Ponto, ...]:
    """Pedaço da parede curta em x (0 ou a), entre y0 e y1, do chão até a linha do telhado."""
    topo = [(x, y, altura_do_telhado(g, y)) for y in _quebras(g, y0, y1)]
    return ((x, y0, 0.0), (x, y1, 0.0), *reversed(topo))


def _parede_longa(g: GeometriaEdificio, y: float, x0: float, x1: float) -> tuple[Ponto, ...]:
    h = g.h_parede_y0_m if y <= 0.0 else g.h_parede_yb_m
    return ((x0, y, 0.0), (x1, y, 0.0), (x1, y, h), (x0, y, h))


def _telhado(g: GeometriaEdificio, x0: float, x1: float, y0: float, y1: float) -> tuple[Ponto, ...]:
    """Pedaço plano do telhado entre x0–x1 e y0–y1 (sem passar pela cumeeira)."""
    z0, z1 = altura_do_telhado(g, y0), altura_do_telhado(g, y1)
    return ((x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1))


def faces_das_zonas(g: GeometriaEdificio, alpha: int) -> list[FaceDaZona]:
    """Os polígonos de todas as zonas do vento a ``alpha`` (0, 90 ou −90), com a mesma divisão de
    :func:`core.vento_edificio.zonas_das_paredes` e :func:`~core.vento_edificio.zonas_do_telhado`."""
    a, b, x1 = g.a_m, g.b_m, g.x_m
    uma_agua = g.cobertura == COBERTURA_UMA_AGUA
    sen, cos = g.sin_theta, g.cos_theta
    faces: list[FaceDaZona] = []

    def face(zona: str, superficie: str, rotulo: str, pontos: tuple[Ponto, ...], n: Ponto) -> None:
        nova = FaceDaZona(zona, superficie, rotulo, pontos, n)
        if nova.area_m2 > 1e-9:
            faces.append(nova)

    x_menos, x_mais = (-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)
    y_menos, y_mais = (0.0, -1.0, 0.0), (0.0, 1.0, 0.0)
    if uma_agua:
        n_y0 = n_yb = (0.0, sen, cos)
    else:
        n_y0, n_yb = (0.0, -sen, cos), (0.0, sen, cos)
    if alpha == 0:
        face("C", "parede", "C", _empena(g, 0.0, 0.0, b), x_menos)
        face("D", "parede", "D", _empena(g, a, 0.0, b), x_mais)
        for zona, (s0, s1), sufixo in (
            ("A1B1", (0.0, x1), "1"),
            ("A2B2", (x1, a / 2.0), "2"),
            ("A3B3", (a / 2.0, a), "3"),
        ):
            face(zona, "parede", "A" + sufixo, _parede_longa(g, 0.0, s0, s1), y_menos)
            face(zona, "parede", "B" + sufixo, _parede_longa(g, b, s0, s1), y_mais)
        if uma_agua:
            for zona, (s0, s1), rotulo in (
                ("HL_ate_b2", (0.0, b / 2.0), "H e L"),
                ("HL_de_b2", (b / 2.0, a / 2.0), "H e L"),
                ("IJ", (a / 2.0, a), "I e J"),
            ):
                face(zona, "telhado", rotulo, _telhado(g, s0, s1, 0.0, b), n_y0)
        else:
            for zona, (s0, s1), (r0, rb) in (
                ("EG", (0.0, x1), ("E", "G")),
                ("FH", (x1, a / 2.0), ("F", "H")),
                ("IJ", (a / 2.0, a), ("I", "J")),
            ):
                face(zona, "telhado", r0, _telhado(g, s0, s1, 0.0, b / 2.0), n_y0)
                face(zona, "telhado", rb, _telhado(g, s0, s1, b / 2.0, b), n_yb)
        return faces
    if alpha not in (90, -90):
        raise ValueError("Zonas: vento a 0°, 90° ou −90°.")
    c1 = g.c1_m
    if alpha == 90:  # sopra de y = 0 para y = b
        face("A", "parede", "A", _parede_longa(g, 0.0, 0.0, a), y_menos)
        face("B", "parede", "B", _parede_longa(g, b, 0.0, a), y_mais)
        trechos = (("C1D1", (0.0, c1), "1"), ("C2D2", (c1, b), "2"))
    else:  # −90: sopra de y = b para y = 0
        face("A", "parede", "A", _parede_longa(g, b, 0.0, a), y_mais)
        face("B", "parede", "B", _parede_longa(g, 0.0, 0.0, a), y_menos)
        trechos = (("C1D1", (b - c1, b), "1"), ("C2D2", (0.0, b - c1), "2"))
    for zona, (s0, s1), sufixo in trechos:
        face(zona, "parede", "C" + sufixo, _empena(g, 0.0, s0, s1), x_menos)
        face(zona, "parede", "D" + sufixo, _empena(g, a, s0, s1), x_mais)
    if uma_agua:
        face("HI", "telhado", "H e I", _telhado(g, 0.0, a, 0.0, b / 2.0), n_y0)
        face("LJ", "telhado", "L e J", _telhado(g, 0.0, a, b / 2.0, b), n_yb)
    else:
        face("EFI", "telhado", "E, F e I", _telhado(g, 0.0, a, 0.0, b / 2.0), n_y0)
        face("GHJ", "telhado", "G, H e J", _telhado(g, 0.0, a, b / 2.0, b), n_yb)
    return faces


# ---------------------------------------------------------------------------------------------
# A cena 3D das zonas
# ---------------------------------------------------------------------------------------------
def _olho(azimute: float, elevacao: float) -> Ponto:
    a, e = math.radians(azimute), math.radians(elevacao)
    return (math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))


def vista_do_caso(alpha: int) -> tuple[float, float]:
    """(azimute, elevação) que mostra a parede de barlavento, uma lateral e o telhado."""
    return AZIMUTE_DA_VISTA.get(alpha, -125.0), ELEVACAO_DA_VISTA


def cena_das_zonas(resultado: ResultadoEdificio, caso: CasoDeVento) -> c3.Cena:
    """As zonas do caso pintadas pelo C_e nas faces que se veem da vista do caso, com o C_e e a
    pressão líquida de cada uma e a seta do vento."""
    g = resultado.geometria
    alpha = caso.alpha
    olho = _olho(*vista_do_caso(alpha))
    por_id = {p.zona.id: p for p in caso.pressoes}
    paineis: list[c3.PainelCena] = []
    textos: list[c3.TextoCena] = []
    rotulados: set[tuple[str, str]] = set()
    faces = faces_das_zonas(g, alpha)
    # Só as faces de frente para quem olha: num sólido convexo elas não se cobrem.
    visiveis = [f for f in faces if sum(n * o for n, o in zip(f.normal, olho, strict=True)) > 0.02]
    for f in visiveis:
        pressao = por_id.get(f.zona)
        if pressao is None:
            continue
        ce = pressao.zona.ce
        paineis.append(
            c3.PainelCena(
                f"{f.zona}:{f.rotulo}", f.pontos, cor_do_ce(ce), 0.96, f.superficie, sombra=False
            )  # fmt: skip
        )
    # Um rótulo por parte visível (a maior face dela), no centro.
    for f in sorted(visiveis, key=lambda f: -f.area_m2):
        pressao = por_id.get(f.zona)
        if pressao is None or (f.zona, f.rotulo) in rotulados:
            continue
        rotulados.add((f.zona, f.rotulo))
        texto = (
            f"{f.rotulo}: C_e {_sinal(pressao.zona.ce)} · Δp {_sinal(pressao.pressao_liquida_kN_m2, 2)}"
            " kN/m²"
        )
        textos.append(c3.TextoCena(f.centro, texto, "#1f2328"))
    # Seta do vento: chega à parede de barlavento, baixa e fora do centro (onde fica o rótulo).
    a, b = g.a_m, g.b_m
    altura = 0.3 * g.h_m
    if alpha == 0:
        alvo, sentido = (0.0, 0.25 * b, altura), (1.0, 0.0, 0.0)
    elif alpha == 90:
        alvo, sentido = (0.82 * a, 0.0, altura), (0.0, 1.0, 0.0)
    else:
        alvo, sentido = (0.82 * a, b, altura), (0.0, -1.0, 0.0)
    seta = c3.SetaCena(
        alvo,
        sentido,
        f"Vento a {_graus(alpha)}",
        COR_DO_VENTO,
        larga=True,
        comprimento_relativo=0.32,
    )
    q = caso.vento.q_kN_m2
    return c3.Cena(
        paineis=tuple(paineis),
        setas=(seta,),
        textos=tuple(textos),
        titulo=f"Zonas do vento a {_graus(alpha)} — C_e e pressão líquida",
        subtitulo=(
            f"q = {_n(q, 3)} kN/m² (classe {caso.classe}) · {caso.cpi.rotulo} · "
            "Δp = q·(f_v·C_e − c_pi): + empurra para dentro, − puxa para fora"
        ),
        escala=c3.EscalaDeCor(
            CE_MINIMO_DA_ESCALA,
            CE_MAXIMO_DA_ESCALA,
            "",
            "C_e (azul: sucção; vermelho: pressão)",
            PALETA_CE,
        ),  # fmt: skip
        eixo_vertical_do_modelo="",
    )


def figura_das_zonas_para_o_registro(
    resultado: ResultadoEdificio, caso: CasoDeVento
) -> dict[str, object]:
    """A cena gravada no registro (o memorial a desenha de novo em PNG)."""
    azimute, elevacao = vista_do_caso(caso.alpha)
    return {
        "cena": c3.cena_para_dicionario(cena_das_zonas(resultado, caso)),
        "legenda": (
            f"Zonas do vento a {_graus(caso.alpha)}, {caso.cpi.rotulo}: C_e de cada zona (NBR 6123:2023, "
            "Tabelas 6 a 8) e a pressão líquida Δp em kN/m²."
        ),
        "azimute": azimute,
        "elevacao": elevacao,
        "perfil_real": True,
    }


# ---------------------------------------------------------------------------------------------
# Faixas de altas sucções (c_pe médio) para as vedações
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FaixaDeVedacao:
    """Uma linha da tabela das vedações e onde ela fica: retângulos em planta (x0, x1, y0, y1) no
    telhado, ou trechos ``(parede, s0, s1)`` ao longo das paredes ("y0", "yb", "x0", "xa")."""

    id: str
    rotulo: str
    cpe: float
    pior_kN_m2: float
    retangulos: tuple[tuple[float, float, float, float], ...] = ()
    trechos_de_parede: tuple[tuple[str, float, float], ...] = ()


def _pior(resultado: ResultadoEdificio, id_: str) -> tuple[float, float] | None:
    for linha in resultado.vedacoes:
        if linha.id == id_:
            return linha.cpe, linha.mais_desfavoravel_kN_m2
    return None


def faixas_de_vedacao(resultado: ResultadoEdificio) -> list[FaixaDeVedacao]:
    """Onde ficam as zonas de ``c_pe`` médio (figuras das Tabelas 6, 7 e 8), com o valor e a pior
    pressão líquida de cada uma. Zona que a norma não dá para a inclinação não aparece."""
    g = resultado.geometria
    a, b, x, y = g.a_m, g.b_m, g.x_m, g.y_telhado_m
    faixas: list[FaixaDeVedacao] = []

    def nova(id_: str, rotulo: str, **onde: object) -> None:
        valor = _pior(resultado, id_)
        if valor is not None:
            faixas.append(FaixaDeVedacao(id_, rotulo, valor[0], valor[1], **onde))  # type: ignore[arg-type]

    # Paredes (Tabela 6, Nota 4): junto à aresta de barlavento das paredes paralelas ao vento,
    # numa distância mín(0,2·b; h); o vento vem dos dois sentidos: os quatro cantos de cada parede.
    f = g.faixa_cpe_medio_parede_m
    trechos: list[tuple[str, float, float]] = []
    for parede, comprimento in (("y0", a), ("yb", a), ("x0", b), ("xa", b)):
        trechos.append((parede, 0.0, min(f, comprimento / 2.0)))
        trechos.append((parede, max(comprimento - f, comprimento / 2.0), comprimento))
    nova("parede-cpe-medio", "Paredes", trechos_de_parede=tuple(trechos))
    if g.cobertura == COBERTURA_UMA_AGUA:
        # Tabela 8: H do lado alto (y = 0), L do lado baixo; extremos He/Le de largura y em cada
        # empena; ao longo dos beirais, H1/L1 até b da empena e H2/L2 no meio.
        meio = b / 2.0
        canto = min(b, a / 2.0)
        for lado, (y0, y1) in (("h", (0.0, y)), ("l", (b - y, b))):
            maiusculo = lado.upper()
            nova(f"telhado-{lado}1", f"{maiusculo}1",
                 retangulos=((y, canto, y0, y1), (a - canto, a - y, y0, y1)))  # fmt: skip
            if a - canto > canto:
                nova(f"telhado-{lado}2", f"{maiusculo}2", retangulos=((canto, a - canto, y0, y1),))
        nova("telhado-he", "He", retangulos=((0.0, y, 0.0, meio), (a - y, a, 0.0, meio)))
        nova("telhado-le", "Le", retangulos=((0.0, y, meio, b), (a - y, a, meio, b)))
        return faixas
    # Tabela 7 (e telhado plano): faixas de largura y nas empenas; cantos de x ao longo dos
    # beirais; o beiral entre os cantos; y de cada lado da cumeeira, entre as faixas das empenas.
    nova("telhado-empena", "Empenas", retangulos=((0.0, y, 0.0, b), (a - y, a, 0.0, b)))
    xc = min(x, a / 2.0)
    nova(
        "telhado-canto",
        "Cantos",
        retangulos=tuple(
            (x0, x1, y0, y1)
            for x0, x1 in ((y, xc), (a - xc, a - y))
            for y0, y1 in ((0.0, y), (b - y, b))
            if x1 > x0
        ),
    )
    if a - xc > xc:
        nova("telhado-beiral", "Beiral", retangulos=((xc, a - xc, 0.0, y), (xc, a - xc, b - y, b)))
    nova("telhado-cumeeira", "Cumeeira", retangulos=((y, a - y, b / 2.0 - y, b / 2.0 + y),))
    return faixas


# ---------------------------------------------------------------------------------------------
# O pórtico transversal no núcleo de pórtico plano (figuras do Ftool)
# ---------------------------------------------------------------------------------------------
NOS_DO_PORTICO = ("1", "2", "3", "4", "5")


def secao_do_portico(nome: str, secao: vp.SecaoDoElemento) -> pp.Secao:
    """A seção do solver rápido (mm, MPa) no núcleo de pórtico plano (m, kN)."""
    return pp.Secao(
        nome=nome,
        area_m2=secao.area_mm2 * 1e-6,
        inercia_m4=secao.inercia_mm4 * 1e-12,
        e_kN_m2=secao.modulo_elasticidade_MPa * 1e3,
    )


def _carga_local(membro: vp.Membro, carga_kN_m: float) -> float:
    """Carga normal (positiva para dentro) na direção local y do núcleo (barra girada de +90°)."""
    dx = membro.p_j[0] - membro.p_i[0]
    dz = membro.p_j[1] - membro.p_i[1]
    comprimento = math.hypot(dx, dz)
    local_y = (-dz / comprimento, dx / comprimento)
    para_dentro = (-membro.normal_externa[0], -membro.normal_externa[1])
    return carga_kN_m * (para_dentro[0] * local_y[0] + para_dentro[1] * local_y[1])


def modelo_do_portico(
    geometria: vp.GeometriaPortico,
    caso: vp.CasoPortico,
    *,
    pilar: pp.Secao,
    rafter: pp.Secao,
    bases_engastadas: bool = True,
) -> pp.Portico:
    """O pórtico transversal do galpão com as cargas do vento do ``caso`` (normais aos elementos,
    em kN/m), para o núcleo de pórtico plano. Os nós são os do solver rápido (1 a 5)."""
    nos = tuple(
        pp.No(nome, y, z) for nome, (y, z) in zip(NOS_DO_PORTICO, geometria.nos, strict=True)
    )
    barras = []
    cargas = []
    for membro in geometria.membros:
        nome = vp.ROTULOS_CURTOS_MEMBROS[membro.id]
        secao = pilar if membro.id in (vp.PILAR_ESQUERDO, vp.PILAR_DIREITO) else rafter
        barras.append(pp.Barra(nome, str(membro.no_i), str(membro.no_j), secao))
        carga = caso.carga(membro.id)
        if abs(carga.carga_kN_m) > 1e-12:
            cargas.append(
                pp.CargaDistribuida(
                    nome,
                    _carga_local(membro, carga.carga_kN_m),
                    direcao=pp.LOCAL_Y,
                    nome=carga.zona.split(" (")[0],
                )
            )
    apoio = pp.engaste if bases_engastadas else pp.pino
    return pp.Portico(
        nos=nos,
        barras=tuple(barras),
        apoios=(apoio("1"), apoio("5")),
        cargas_distribuidas=tuple(cargas),
    )


def rotulo_do_caso_do_portico(caso: vp.CasoPortico) -> str:
    faixa = (
        ""
        if caso.faixa_x_m is None
        else f", de {_n(caso.faixa_x_m[0], 1)} a {_n(caso.faixa_x_m[1], 1)} m da empena"
    )
    return f"{caso.nome}{faixa}"


def pior_caso_do_portico(casos: Sequence[vp.CasoPortico]) -> vp.CasoPortico:
    """O caso de maior carga total (soma de |kN/m| nos quatro elementos), para o memorial."""
    return max(casos, key=lambda c: sum(abs(item.carga_kN_m) for item in c.cargas))
