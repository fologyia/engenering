"""Figuras de apoio às contas da base de pilar, para o memorial.

Cada figura mostra uma conta do memorial, ao lado dela:

* :func:`figura_das_pressoes` — o corte pelo plano do momento: a pressão de contato sob a placa
  (o bloco uniforme da 6.7 ou o trapézio da distribuição elástica), a resultante de compressão e
  as forças nos chumbadores tracionados, com N e M de cálculo;
* :func:`figura_da_tracao_a_45` — a planta da tração na placa: o balanço m de cada chumbador até a
  face da mesa e a largura b_eff aberta a 45° (limitada pela borda e pela metade do espaçamento);
* :func:`figura_do_cone` — a planta do bloco com a área projetada A_Nc do cone de concreto do grupo
  tracionado (o quadrado de lado 3·h_ef de cada chumbador, cortado pelas bordas e pela
  sobreposição) e as distâncias às bordas.

Desenhos em tons de cinza, legíveis impressos em preto e branco; as medidas saem das mesmas
funções do cálculo (:func:`core.base_de_pilar.aberturas_a_45_graus`,
:func:`core.base_de_pilar.area_do_cone`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from PIL import Image, ImageDraw

from core import base_de_pilar as bp
from core import desenho_girado as dg
from core.beam_charts import ImagemDiagrama, _fonte, figura_final
from core.graficos_memorial import fonte_em_negrito

ESC = dg.ESC
_FUNDO = "#ffffff"
_TRACO = "#111827"
_COTA = "#374151"
_PLACA = "#e5e7eb"
_PILAR = "#9ca3af"
_CONCRETO = "#f3f4f6"
_HACHURA = "#6b7280"
_LARGURA_PX, _ALTURA_PX = 900, 560
Ponto = tuple[float, float]


def _n(valor: float, casas: int = 0) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _hachurar(
    imagem: Image.Image, pontos: Sequence[Ponto], *, passo: float = 9 * ESC, angulo: float = 45.0
) -> None:
    """Linhas paralelas dentro do polígono (px): a área sem depender de cor."""
    if len(pontos) < 3:
        return
    mascara = Image.new("L", imagem.size, 0)
    ImageDraw.Draw(mascara).polygon(list(pontos), fill=255)
    camada = Image.new("RGB", imagem.size, _HACHURA)
    linhas = Image.new("L", imagem.size, 0)
    d = ImageDraw.Draw(linhas)
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    altura = y1 - y0
    tg = math.tan(math.radians(angulo))
    inicio = x0 - altura / tg if tg else x0
    x = inicio
    while x <= x1:
        d.line([(x, y1), (x + altura / tg, y0)] if tg else [(x, y0), (x, y1)], fill=255, width=ESC)
        x += passo
    from PIL import ImageChops

    imagem.paste(camada, (0, 0), ImageChops.multiply(mascara, linhas))


def _seta(d: ImageDraw.ImageDraw, a: Ponto, b: Ponto, *, largura: int = 3 * ESC) -> None:
    dg.seta(d, a, b, _TRACO, largura=largura, ponta_px=11 * ESC)


def _texto(
    d: ImageDraw.ImageDraw, ponto: Ponto, texto: str, ancora: str = "mm", *, negrito: bool = False
) -> None:
    fonte = fonte_em_negrito(12 * ESC) if negrito else _fonte(12 * ESC)
    caixa = d.textbbox(ponto, texto, font=fonte, anchor=ancora)
    d.rectangle([caixa[0] - 3 * ESC, caixa[1] - 2 * ESC, caixa[2] + 3 * ESC, caixa[3] + 2 * ESC], fill=_FUNDO)  # fmt: skip
    d.text(ponto, texto, fill=_TRACO, font=fonte, anchor=ancora)


def _cota(
    d: ImageDraw.ImageDraw, a: Ponto, b: Ponto, lado: Ponto, texto: str, afasta: float
) -> None:
    dg.cota_alinhada(d, a, b, lado, texto, afasta, cor=_COTA, fundo=True)


def _retangulo(tela: dg.Tela, x0: float, y0: float, x1: float, y1: float) -> list[Ponto]:
    """Retângulo em mm (y para cima) como polígono em px."""
    return [tela(x0, -y0), tela(x1, -y0), tela(x1, -y1), tela(x0, -y1)]


def _perfil(d: ImageDraw.ImageDraw, tela: dg.Tela, g: bp.Geometria) -> None:
    """O perfil do pilar em planta (I com as mesas paralelas a y, ou U)."""
    d.polygon([tela(x, -y) for x, y in bp.contorno_do_perfil(g)], fill=_PILAR, outline=_TRACO)


def _chumbador(
    d: ImageDraw.ImageDraw, tela: dg.Tela, x: float, y: float, raio_mm: float, cheio: bool
) -> None:
    cx, cy = tela(x, -y)
    raio = max(raio_mm * tela.esc, 4 * ESC)
    d.ellipse(
        [cx - raio, cy - raio, cx + raio, cy + raio],
        fill=_TRACO if cheio else _FUNDO,
        outline=_TRACO,
        width=2 * ESC,
    )


# ============================================================================================
# Pressão sob a placa e forças nos chumbadores (corte)
# ============================================================================================
def _pressao_no_corte(r: bp.ResultadoBase) -> tuple[Any, float, str]:
    """(σ(x) em MPa, σ máxima, como ela se distribui) no corte pelo plano do momento."""
    corte = bp.corte_de_pressao(r)
    if corte is None:
        return (lambda x: 0.0), 0.0, "sem contato"
    a, b, qa, qb, y = corte

    def pressao(x):
        if x < a or x > b or a == b:
            return 0.0
        return qa + (qb - qa) * (x - a) / (b - a)

    tipo = (
        "linear elástica"
        if r.entrada.distribuicao == bp.DISTRIBUICAO_ELASTICA
        else "bloco uniforme"
    )
    return pressao, max(qa, qb), f"{tipo}, corte y = {_n(y, 2)} mm"


def figura_das_pressoes(r: bp.ResultadoBase, combinacao: str = "") -> ImagemDiagrama | None:
    """O corte da base com a pressão de contato e as forças nos chumbadores (ver o módulo)."""
    e, g = r.entrada, r.geometria
    sigma, sigma_max, onde = _pressao_no_corte(r)
    forcas_por_x: dict[float, float] = {}
    for (x, _), f in zip(g.posicoes, r.forcas_nos_chumbadores, strict=True):
        chave = round(x, 6)
        forcas_por_x[chave] = max(forcas_por_x.get(chave, 0.0), f)
    if sigma_max <= 0 and not any(f > 0 for f in forcas_por_x.values()):
        return None
    lx = g.lx
    t_desenho = max(e.t_placa_mm, 0.035 * lx)
    profundidade = 0.22 * lx
    altura_pilar = 0.30 * lx
    pontos = [
        (-lx / 2 - 0.30 * lx, -altura_pilar - 0.12 * lx),
        (lx / 2 + 0.30 * lx, t_desenho + 0.42 * lx),
    ]
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), _FUNDO)
    d = ImageDraw.Draw(imagem)
    tela = dg.Tela(pontos, (30, 20, _LARGURA_PX - 30, _ALTURA_PX - 20))

    # concreto, placa e pilar
    d.line([tela(-lx / 2 - 0.25 * lx, t_desenho), tela(lx / 2 + 0.25 * lx, t_desenho)], fill=_COTA, width=2 * ESC)  # fmt: skip
    d.rectangle(
        [tela(-lx / 2, 0), tela(lx / 2, t_desenho)], fill=_PLACA, outline=_TRACO, width=2 * ESC
    )
    d.rectangle(
        [tela(-g.d / 2, -altura_pilar), tela(g.d / 2, 0)],
        fill=_FUNDO,
        outline=_TRACO,
        width=2 * ESC,
    )
    for x0, x1 in ((-g.d / 2, -g.d / 2 + g.t_f), (g.d / 2 - g.t_f, g.d / 2)):
        d.rectangle([tela(x0, -altura_pilar), tela(x1, 0)], fill=_PILAR, outline=_TRACO)

    # pressão de contato
    if sigma_max > 0:
        amostras = [(-lx / 2 + lx * k / 200) for k in range(201)]
        corte = bp.corte_de_pressao(r)
        assert corte is not None
        amostras = sorted(set(amostras + list(corte[:2])))
        valores = [sigma(x) for x in amostras]
        borda = [
            tela(x, t_desenho + profundidade * v / sigma_max)
            for x, v in zip(amostras, valores, strict=True)
        ]
        poligono = [tela(amostras[0], t_desenho), *borda, tela(amostras[-1], t_desenho)]
        d.polygon(poligono, fill=_CONCRETO)
        _hachurar(imagem, poligono, angulo=90.0, passo=7 * ESC)
        d.line(borda, fill=_TRACO, width=2 * ESC)
        com_pressao = [x for x, v in zip(amostras, valores, strict=True) if v > 1e-9]
        if com_pressao:  # σ no meio do trecho (uniforme) ou na borda mais comprimida (linear)
            inicio, fim = min(com_pressao), max(com_pressao)
            uniforme = abs(sigma(inicio) - sigma(fim)) <= 1e-6 * sigma_max
            x_rotulo = (inicio + fim) / 2 if uniforme else max(amostras, key=sigma)
            fundo_do_diagrama = t_desenho + profundidade * sigma(x_rotulo) / sigma_max
            _texto(d, dg.mais(tela(x_rotulo, fundo_do_diagrama), (0, 1), 14 * ESC), f"σ = {_n(sigma_max, 2)} MPa", "mt", negrito=True)  # fmt: skip
        if com_pressao:
            inicio, fim = min(com_pressao), max(com_pressao)
            y_cota = t_desenho + profundidade + 0.10 * lx
            _cota(d, tela(inicio, y_cota), tela(fim, y_cota), (0, 1), f"trecho comprimido {_n(fim - inicio, 0)} mm", 0)  # fmt: skip
        # a resultante de compressão: C = N + ΣF
        compressao = e.n_sd_kN * 1e3 + sum(r.forcas_nos_chumbadores)
        if compressao > 0 and r.centro_pressao is not None:
            x_c = r.centro_pressao[0]
            ponta = tela(x_c, t_desenho)
            base = tela(x_c, t_desenho + profundidade * 0.95)
            _seta(d, base, ponta)
            meio = ((base[0] + ponta[0]) / 2, (base[1] + ponta[1]) / 2)
            _texto(d, dg.mais(meio, (1, 0), 8 * ESC), f"C = {_n(compressao / 1e3, 1)} kN", "lm")

    # chumbadores e as forças de tração
    for x, f in sorted(forcas_por_x.items()):
        d.line([tela(x, -0.06 * lx), tela(x, t_desenho + 0.34 * lx)], fill=_TRACO, width=3 * ESC)
        d.rectangle(
            [tela(x - 0.025 * lx, -0.06 * lx), tela(x + 0.025 * lx, -0.02 * lx)], fill=_TRACO
        )
        if f > 0:
            a = tela(x, t_desenho + 0.06 * lx)
            b = tela(x, t_desenho + 0.26 * lx)
            _seta(d, a, b)
            lado = -1 if x < 0 else 1
            _texto(d, dg.mais(b, (lado, 0), 10 * ESC), f"F_t = {_n(f / 1e3, 2)} kN", "lm" if lado > 0 else "rm", negrito=True)  # fmt: skip

    # N e M no topo do pilar
    topo = tela(0, -altura_pilar)
    n_kn = e.n_sd_kN
    if abs(n_kn) > 1e-9:
        a, b = dg.mais(topo, (0, -1), 60 * ESC), dg.mais(topo, (0, -1), 6 * ESC)
        if n_kn > 0:
            _seta(d, a, b)  # compressão: N empurra o pilar
        else:
            _seta(d, b, a)
    esforcos = f"N = {_n(n_kn, 1)} kN" + (f";  M = {_n(e.m_sd_kNm, 1)} kN·m" if e.m_sd_kNm else "")
    if e.m_sd_y_kNm:
        esforcos += f";  M_y = {_n(e.m_sd_y_kNm, 1)} kN·m"
    _texto(d, dg.mais(topo, (1, -1), 40 * ESC), esforcos, "lm")

    titulo = "Pressão sob a placa e forças nos chumbadores" + (
        f" — {combinacao}" if combinacao else ""
    )
    legenda = (
        f"Pressão de contato ({onde}, caso {r.caso}). A seta C representa a resultante da área "
        "inteira, projetada no corte. F_t indica a maior tração na fila de chumbadores."
    )
    return figura_final(imagem, titulo, legenda)


# ============================================================================================
# Tração na placa: balanço m e largura b_eff a 45° (planta)
# ============================================================================================
def figura_da_tracao_a_45(r: bp.ResultadoBase, combinacao: str = "") -> ImagemDiagrama | None:
    """A planta com a largura efetiva a 45° de cada chumbador externo tracionado."""
    g = r.geometria
    aberturas = bp.aberturas_a_45_graus(g, r.forcas_nos_chumbadores)
    if not aberturas:
        return None
    fy = bp.ACOS[r.entrada.aco_placa][0]
    governa = max(aberturas, key=lambda a: a.f * a.m / a.b_eff)
    margem = 0.18 * max(g.lx, g.ly)
    pontos = [(-g.lx / 2 - margem, -g.ly / 2 - margem), (g.lx / 2 + margem, g.ly / 2 + margem)]
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), _FUNDO)
    d = ImageDraw.Draw(imagem)
    tela = dg.Tela(pontos, (30, 20, _LARGURA_PX - 30, _ALTURA_PX - 20))
    d.polygon(
        _retangulo(tela, -g.lx / 2, -g.ly / 2, g.lx / 2, g.ly / 2), fill=_PLACA, outline=_TRACO
    )
    _perfil(d, tela, g)
    for a in aberturas:
        s = 1.0 if a.x > 0 else -1.0
        face = s * g.d / 2
        poligono = [
            tela(a.x, -a.y),
            tela(a.x - s * a.lado_mais, -(a.y + a.lado_mais)),
            tela(face, -(a.y + a.lado_mais)),
            tela(face, -(a.y - a.lado_menos)),
            tela(a.x - s * a.lado_menos, -(a.y - a.lado_menos)),
        ]
        d.polygon(poligono, fill=_FUNDO)
        _hachurar(imagem, poligono, passo=8 * ESC)
        d.polygon(poligono, outline=_TRACO, width=(3 if a is governa else 1) * ESC)
    raio = r.linha.d_b / 2
    tracionados = {(round(a.x, 6), round(a.y, 6)) for a in aberturas}
    for x, y in g.posicoes:
        _chumbador(d, tela, x, y, raio, (round(x, 6), round(y, 6)) in tracionados)
    # cotas do que governa
    s = 1.0 if governa.x > 0 else -1.0
    face = s * g.d / 2
    raio_px = max(r.linha.d_b / 2 * tela.esc, 4 * ESC)
    _cota(  # abaixo do chumbador, para o texto não cobrir o círculo
        d,
        tela(governa.x, -governa.y),
        tela(face, -governa.y),
        (0, 1),
        f"m = {_n(governa.m, 1)} mm",
        raio_px + 10 * ESC,
    )
    _cota(  # do lado do chumbador, fora da mesa
        d,
        tela(face, -(governa.y - governa.lado_menos)),
        tela(face, -(governa.y + governa.lado_mais)),
        (s, 0),
        f"b_eff = {_n(governa.b_eff, 1)} mm",
        8 * ESC,
    )
    t = math.sqrt(
        4
        * governa.f
        * governa.m
        / (governa.b_eff * fy / bp.sd.coeficientes(r.entrada.combinacao).a1)
    )
    titulo = "Tração na placa: balanço até a face da mesa e largura a 45°" + (
        f" — {combinacao}" if combinacao else ""
    )
    legenda = (
        "Planta: cada chumbador tracionado (em preto) carrega a faixa da placa aberta a 45° até a "
        "face da mesa, limitada pela borda da placa e pela metade do espaçamento; a faixa em traço "
        f"grosso é a que governa: F_t = {_n(governa.f / 1e3, 2)} kN, m = {_n(governa.m, 1)} mm, "
        f"b_eff = {_n(governa.b_eff, 1)} mm → t = {_n(t, 1)} mm."
    )
    return figura_final(imagem, titulo, legenda)


# ============================================================================================
# Cone de concreto (planta do bloco)
# ============================================================================================
def figura_do_cone(r: bp.ResultadoBase, combinacao: str = "") -> ImagemDiagrama | None:
    """A planta do bloco com a área projetada A_Nc do cone do grupo tracionado."""
    e, g = r.entrada, r.geometria
    area = bp.area_do_cone(e, g, r.linha, r.forcas_nos_chumbadores)
    if area is None:
        return None
    bx, by, h = area.bx, area.by, area.h_ef
    margem = 0.16 * max(bx, by)
    xmin, xmax, ymin, ymax = bp.limites_bloco(e, bx, by)
    pontos = [(xmin - margem, -ymax - margem), (xmax + margem, -ymin + margem)]
    imagem = Image.new("RGB", (_LARGURA_PX * ESC, _ALTURA_PX * ESC), _FUNDO)
    d = ImageDraw.Draw(imagem)
    tela = dg.Tela(pontos, (30, 20, _LARGURA_PX - 30, _ALTURA_PX - 20))
    d.polygon(_retangulo(tela,xmin,ymin,xmax,ymax), fill=_CONCRETO, outline=_TRACO, width=2 * ESC)  # fmt: skip
    x0, x1, y0, y1 = area.retangulo
    for x, y, _ in area.tracionados:  # o quadrado 3·h_ef de cada um, cortado pelo bloco
        canto = (
            max(x - 1.5 * h, xmin), max(y - 1.5 * h, ymin),
            min(x + 1.5 * h, xmax), min(y + 1.5 * h, ymax),
        )  # fmt: skip
        quadrado = _retangulo(tela, *canto)
        _hachurar(imagem, quadrado, passo=9 * ESC)
        for k in range(4):
            dg.tracejado(d, quadrado[k], quadrado[(k + 1) % 4], _COTA, largura=ESC)
    d.polygon(_retangulo(tela, -g.lx / 2, -g.ly / 2, g.lx / 2, g.ly / 2), outline=_COTA, width=ESC)
    tracionados = {(round(x, 6), round(y, 6)) for x, y, _ in area.tracionados}
    for x, y in g.posicoes:
        _chumbador(d, tela, x, y, r.linha.d_b / 2, (round(x, 6), round(y, 6)) in tracionados)
    # distâncias às bordas, dos chumbadores tracionados extremos
    xs = [x for x, _, _ in area.tracionados]
    ys = [y for _, y, _ in area.tracionados]
    c_menos_x, c_mais_x, c_menos_y, c_mais_y = area.bordas
    y_meio = (min(ys) + max(ys)) / 2
    x_meio = (min(xs) + max(xs)) / 2
    _cota(d, tela(xmin, -y_meio), tela(min(xs), -y_meio), (0, -1), f"c = {_n(c_menos_x, 0)}", 0)
    _cota(d, tela(max(xs), -y_meio), tela(xmax, -y_meio), (0, -1), f"c = {_n(c_mais_x, 0)}", 0)
    _cota(d, tela(x_meio, -ymin), tela(x_meio, -min(ys)), (1, 0), f"c = {_n(c_menos_y, 0)}", 0)
    _cota(d, tela(x_meio, -max(ys)), tela(x_meio, -ymax), (1, 0), f"c = {_n(c_mais_y, 0)}", 0)
    _texto(
        d,
        tela(x1, -y1),
        f"A_Nc = {_n(area.a_nc / 100, 0)} cm²",
        "rb",
        negrito=True,
    )
    reducao = (
        f"; h_ef útil {_n(h, 0)} mm, reduzido de {_n(area.h_ef_informado, 0)} mm pela ACI 17.6.2.1.2"
        if area.reduzido
        else f"; h_ef = {_n(h, 0)} mm"
    )
    titulo = "Cone de concreto: área projetada A_Nc no bloco" + (
        f" — {combinacao}" if combinacao else ""
    )
    legenda = (
        f"Planta do bloco {_n(bx, 0)} × {_n(by, 0)} mm: em tracejado, o quadrado de lado 3·h_ef de "
        f"cada chumbador tracionado (em preto); hachurada, a área A_Nc do grupo, cortada pelas "
        f"bordas e sem contar a sobreposição; A_Nco = 9·h_ef² = {_n(area.a_nco / 100, 0)} cm²"
        f"{reducao}; c, a distância de cada borda."
    )
    return figura_final(imagem, titulo, legenda)


# ============================================================================================
# As figuras de cada verificação (para o memorial separado)
# ============================================================================================
def figuras_das_contas(r: bp.ResultadoBase) -> dict[str, list[ImagemDiagrama]]:
    """As figuras de apoio, pelo nome da verificação ao lado da qual entram.

    Numa envoltória, cada figura é a da combinação que governa a verificação dela (o nome entre
    colchetes no começo da fórmula), e o título diz qual.
    """
    from core.memorial_trecho import separar_combinacao

    por_nome = {v.nome: v for v in r.verificacoes}
    casos = {item.caso.nome: item.resultado for item in r.casos}

    def resultado_de(nome: str) -> tuple[bp.ResultadoBase, str]:
        v = por_nome.get(nome)
        combinacao = separar_combinacao(v.formula)[0] if v is not None else ""
        if combinacao in casos:
            return casos[combinacao], combinacao
        return r, r.combinacao_governante

    saida: dict[str, list[ImagemDiagrama]] = {}

    def anexar(nome: str, figura: ImagemDiagrama | None) -> None:
        if figura is not None and figura.png:
            saida.setdefault(nome, []).append(figura)

    nomes_da_pressao = (
        "Concreto: pressão de contato σ_c,Sd ≤ σ_c,Rd",
        "Concreto: pressão de contato",
        "Placa de base: espessura t_p ≥ t_p,min",
    )
    nome = next((n for n in nomes_da_pressao if n in por_nome), "")
    if nome and resultado_de(nome)[0].equilibrio_valido:
        anexar(nome, figura_das_pressoes(*resultado_de(nome)))
    placa = "Placa de base: espessura t_p ≥ t_p,min"
    if placa in por_nome:
        resultado, combinacao = resultado_de(placa)
        if not bp.aberturas_a_45_graus(resultado.geometria, resultado.forcas_nos_chumbadores):
            # a placa governada pela compressão: a figura a 45° vem da combinação mais tracionada
            if r.casos:
                item = max(r.casos, key=lambda i: i.resultado.f_t_sd)
                resultado, combinacao = item.resultado, item.caso.nome
        if resultado.equilibrio_valido:
            anexar(placa, figura_da_tracao_a_45(resultado, combinacao))
    for nome_cone in (bp.LINHA_DO_CONE, "Cone de concreto: armadura de ancoragem no bloco"):
        if (
            nome_cone in por_nome
            and resultado_de(nome_cone)[0].equilibrio_valido
            and por_nome[nome_cone].status != "ALERTA"
        ):
            anexar(nome_cone, figura_do_cone(*resultado_de(nome_cone)))
    return saida
