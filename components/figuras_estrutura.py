"""Desenhos (SVG) do vento em estruturas abertas, do contraventamento e da chapa de nó.

Sem dependências: cada função devolve texto SVG, que a página mostra com ``st.image``. Os desenhos
são esquemáticos mas em escala (o que importa é a proporção entre as peças), com as forças do
cálculo escritas sobre eles. Cores: azul = tração, vermelho = compressão, cinza = peça sem esforço
ou desprezada, laranja = vento.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from xml.sax.saxutils import escape

from core import contraventamento_ligacao as lig
from core import contraventamento_plataforma as cp
from core import contraventamento_ufm as ufm
from core import vento_estrutura_aberta as va

COR_TEXTO = "#1f2328"
COR_FUNDO = "#fbfbfd"
COR_ESTRUTURA = "#5b6470"
COR_CONTRAVENTADO = "#1f4e8c"
COR_TRACAO = "#1f6feb"
COR_COMPRESSAO = "#cf222e"
COR_DESPREZADA = "#9aa1a9"
COR_VENTO = "#d4760a"
COR_CHAPA = "#f2d17a"
COR_PARAFUSO = "#3b3b3b"
FONTE = "sans-serif"


def _n(valor: float, casas: int = 1) -> str:
    if not math.isfinite(valor):
        return "∞"
    return f"{valor:.{casas}f}".replace(".", ",")


def _texto(
    x: float,
    y: float,
    conteudo: str,
    *,
    tamanho: float = 12.0,
    ancora: str = "middle",
    cor: str = COR_TEXTO,
    peso: str = "normal",
    giro: float = 0.0,
) -> str:
    transforma = f' transform="rotate({giro:.1f} {x:.1f} {y:.1f})"' if giro else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{tamanho}" text-anchor="{ancora}" '
        f'dominant-baseline="middle" font-family="{FONTE}" font-weight="{peso}" fill="{cor}"'
        f"{transforma}>{escape(conteudo)}</text>"
    )


def _linha(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    cor: str = COR_ESTRUTURA,
    largura: float = 2.0,
    tracejado: str = "",
) -> str:
    traco = f' stroke-dasharray="{tracejado}"' if tracejado else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{cor}" '
        f'stroke-width="{largura}" stroke-linecap="round"{traco}/>'
    )


def _seta(
    x1: float, y1: float, x2: float, y2: float, *, cor: str = COR_VENTO, largura: float = 2.5
) -> str:
    comprimento = max(math.hypot(x2 - x1, y2 - y1), 1e-9)
    ux, uy = (x2 - x1) / comprimento, (y2 - y1) / comprimento
    bx, by = x2 - 10 * ux, y2 - 10 * uy
    px, py = -uy, ux
    ponta = f"{x2:.1f},{y2:.1f} {bx + 4.5 * px:.1f},{by + 4.5 * py:.1f} {bx - 4.5 * px:.1f},{by - 4.5 * py:.1f}"
    return _linha(x1, y1, bx, by, cor=cor, largura=largura) + (
        f'<polygon points="{ponta}" fill="{cor}"/>'
    )


def _svg(largura: float, altura: float, corpo: Sequence[str], titulo: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura:.0f} {altura:.0f}" '
        f'width="{largura:.0f}" height="{altura:.0f}" role="img">'
        f"<title>{escape(titulo)}</title>"
        f'<rect x="0" y="0" width="{largura:.0f}" height="{altura:.0f}" fill="{COR_FUNDO}"/>'
        + "".join(corpo)
        + "</svg>"
    )


def _legenda(x: float, y: float, itens: Sequence[tuple[str, str, str]]) -> list[str]:
    """Itens (cor, tracejado, texto) numa linha a partir de (x, y)."""
    partes = []
    for cor, tracejado, texto in itens:
        partes.append(_linha(x, y, x + 22, y, cor=cor, largura=3, tracejado=tracejado))
        partes.append(_texto(x + 28, y, texto, tamanho=11, ancora="start"))
        x += 34 + 6.2 * len(texto)
    return partes


# ---------------------------------------------------------------------------------------------
# Vento em estrutura aberta — elevação na direção do vento
# ---------------------------------------------------------------------------------------------
def svg_vento_elevacao(g: va.GeometriaAberta, r: va.VentoNaDirecao) -> str:
    """Os pórticos vistos de lado, o vento chegando pela esquerda e a força em cada nível."""
    largura, altura = 780.0, 430.0
    comprimento = max(p.coordenada_m for p in r.planos) or 1.0
    h_total = g.altura_total_m
    esquerda, direita, topo, base = 210.0, 40.0, 40.0, 70.0
    escala = min((largura - esquerda - direita) / comprimento, (altura - topo - base) / h_total)
    x0, y0 = esquerda, altura - base

    def px(x_m: float) -> float:
        return x0 + x_m * escala

    def py(z_m: float) -> float:
        return y0 - z_m * escala

    corpo: list[str] = [_linha(x0 - 30, y0, px(comprimento) + 30, y0, cor="#444", largura=2)]
    # pórticos
    for plano in sorted(r.planos, key=lambda p: p.coordenada_m):
        cor = COR_CONTRAVENTADO if plano.contraventado else COR_ESTRUTURA
        x = px(plano.coordenada_m)
        corpo.append(
            _linha(x, y0, x, py(g.altura_m), cor=cor, largura=4 if plano.contraventado else 2.5)
        )
        corpo.append(_texto(x, y0 + 16, f"P{plano.posicao}", tamanho=12, peso="bold"))
        corpo.append(_texto(x, y0 + 32, f"η {_n(plano.eta, 2)}", tamanho=11))
    # pisos e guarda-corpos
    for nivel in r.niveis:
        y = py(nivel.cota_m)
        corpo.append(_linha(px(0), y, px(comprimento), y, cor=COR_ESTRUTURA, largura=3))
        if g.guarda_corpo:
            yg = py(nivel.cota_m + g.altura_guarda_corpo_m)
            corpo.append(
                _linha(
                    px(0), yg, px(comprimento), yg, cor=COR_ESTRUTURA, largura=1.2, tracejado="5 4"
                )
            )
            corpo.append(
                _linha(px(0), y, px(0), yg, cor=COR_ESTRUTURA, largura=1.2, tracejado="5 4")
            )
            corpo.append(
                _linha(
                    px(comprimento),
                    y,
                    px(comprimento),
                    yg,
                    cor=COR_ESTRUTURA,
                    largura=1.2,
                    tracejado="5 4",
                )
            )
        # cota
        corpo.append(
            _texto(px(comprimento) + 6, y, f"{_n(nivel.cota_m, 2)} m", tamanho=11, ancora="start")
        )
    # setas do vento por nível
    maior = max((n.total_kN for n in r.niveis), default=1.0) or 1.0
    for nivel in r.niveis:
        y = py(nivel.cota_m)
        comprimento_seta = 60 + 80 * nivel.total_kN / maior
        corpo.append(_seta(x0 - 12 - comprimento_seta, y, x0 - 12, y))
        corpo.append(
            _texto(
                x0 - 12 - comprimento_seta / 2,
                y - 12,
                f"F{nivel.nivel} = {_n(nivel.total_kN)} kN",
                tamanho=12,
                peso="bold",
                cor=COR_VENTO,
            )
        )
    if r.forca_na_base_kN > 0:
        yb = py(r.niveis[0].faixa_m[0] / 2) if r.niveis else y0
        corpo.append(_seta(x0 - 70, yb, x0 - 12, yb, largura=1.5))
        corpo.append(
            _texto(x0 - 41, yb - 11, f"base {_n(r.forca_na_base_kN)} kN", tamanho=10, cor=COR_VENTO)
        )
    corpo.append(
        _texto(
            20,
            22,
            f"Vento em {r.direcao} — elevação dos pórticos",
            tamanho=14,
            ancora="start",
            peso="bold",
        )
    )
    corpo.extend(
        _legenda(
            20,
            altura - 14,
            (
                (COR_CONTRAVENTADO, "", "pórtico contraventado"),
                (COR_ESTRUTURA, "", "pórtico sem diagonais"),
                (COR_ESTRUTURA, "5 4", "guarda-corpo"),
                (COR_VENTO, "", "força do vento (característica)"),
            ),
        )
    )
    return _svg(largura, altura, corpo, f"Vento em {r.direcao}")


# ---------------------------------------------------------------------------------------------
# Contraventamento — planta
# ---------------------------------------------------------------------------------------------
def _linhas_contraventadas(n_linhas_de_pilares: int, contraventadas: int) -> list[int]:
    ordem = sorted(
        range(n_linhas_de_pilares), key=lambda k: (min(k, n_linhas_de_pilares - 1 - k), k)
    )
    return sorted(ordem[:contraventadas])


def svg_planta(e: cp.EntradaContraventamento) -> str:
    """Planta com os pilares, as linhas contraventadas (com o X nos painéis) e o vento."""
    largura, altura = 780.0, 470.0
    margem_esq, margem_dir, margem_topo, margem_base = 110.0, 60.0, 60.0, 90.0
    escala = min(
        (largura - margem_esq - margem_dir) / e.comprimento_x_m,
        (altura - margem_topo - margem_base) / e.largura_y_m,
    )
    x0, y0 = margem_esq, altura - margem_base

    def px(x_m: float) -> float:
        return x0 + x_m * escala

    def py(y_m: float) -> float:
        return y0 - y_m * escala

    ax = e.comprimento_x_m / e.vaos_x
    ay = e.largura_y_m / e.vaos_y
    corpo: list[str] = []
    # vigas (grade)
    for j in range(e.vaos_y + 1):
        corpo.append(
            _linha(px(0), py(j * ay), px(e.comprimento_x_m), py(j * ay), cor="#c3c8ce", largura=2)
        )
    for i in range(e.vaos_x + 1):
        corpo.append(
            _linha(px(i * ax), py(0), px(i * ax), py(e.largura_y_m), cor="#c3c8ce", largura=2)
        )
    # linhas contraventadas
    sx, sy = e.contraventamento_x, e.contraventamento_y
    for j in _linhas_contraventadas(e.vaos_y + 1, sx.linhas):
        y = py(j * ay)
        corpo.append(_linha(px(0), y, px(e.comprimento_x_m), y, cor=COR_CONTRAVENTADO, largura=4))
        for painel in range(min(sx.paineis_por_linha, e.vaos_x)):
            xa, xb = px(painel * ax), px((painel + 1) * ax)
            corpo.append(_marca_painel(xa, xb, y, horizontal=True, tipo=sx.tipo))
    for i in _linhas_contraventadas(e.vaos_x + 1, sy.linhas):
        x = px(i * ax)
        corpo.append(_linha(x, py(0), x, py(e.largura_y_m), cor=COR_CONTRAVENTADO, largura=4))
        for painel in range(min(sy.paineis_por_linha, e.vaos_y)):
            ya, yb = py(painel * ay), py((painel + 1) * ay)
            corpo.append(_marca_painel(ya, yb, x, horizontal=False, tipo=sy.tipo))
    # pilares
    lado = 10.0
    for i in range(e.vaos_x + 1):
        for j in range(e.vaos_y + 1):
            corpo.append(
                f'<rect x="{px(i * ax) - lado / 2:.1f}" y="{py(j * ay) - lado / 2:.1f}" width="{lado}" '
                f'height="{lado}" fill="{COR_ESTRUTURA}"/>'
            )
    # cotas
    corpo.append(
        _texto(
            (px(0) + px(e.comprimento_x_m)) / 2,
            y0 + 26,
            f"L_x = {_n(e.comprimento_x_m, 2)} m ({e.vaos_x} vão(s))",
            tamanho=12,
        )
    )
    corpo.append(
        _texto(
            px(e.comprimento_x_m) + 22,
            (py(0) + py(e.largura_y_m)) / 2,
            f"L_y = {_n(e.largura_y_m, 2)} m",
            tamanho=12,
            giro=-90,
        )
    )
    # vento
    ym = (py(0) + py(e.largura_y_m)) / 2
    corpo.append(_seta(20, ym, x0 - 22, ym))
    corpo.append(_texto(46, ym - 14, "vento X", tamanho=12, cor=COR_VENTO, peso="bold"))
    xm = (px(0) + px(e.comprimento_x_m)) / 2 - 140
    corpo.append(_seta(xm, altura - 18, xm, y0 + 10))
    corpo.append(
        _texto(
            xm + 10, altura - 30, "vento Y", tamanho=12, cor=COR_VENTO, peso="bold", ancora="start"
        )
    )
    corpo.append(
        _texto(20, 24, "Planta — linhas contraventadas", tamanho=14, ancora="start", peso="bold")
    )
    corpo.append(
        _texto(
            20,
            42,
            "Painéis marcados na ponta da linha só para ilustrar: a posição é a do seu desenho.",
            tamanho=10,
            ancora="start",
            cor="#666",
        )
    )
    return _svg(largura, altura, corpo, "Planta do contraventamento")


def _marca_painel(a: float, b: float, c: float, *, horizontal: bool, tipo: str) -> str:
    """Símbolo do contraventamento sobre o painel (em planta: um X ou uma barra)."""
    meio = (a + b) / 2
    meia = abs(b - a) * 0.18
    if horizontal:
        p1, p2 = (meio - meia, c - 9), (meio + meia, c + 9)
        q1, q2 = (meio - meia, c + 9), (meio + meia, c - 9)
    else:
        p1, p2 = (c - 9, meio - meia), (c + 9, meio + meia)
        q1, q2 = (c + 9, meio - meia), (c - 9, meio + meia)
    partes = [_linha(*p1, *p2, cor=COR_TRACAO, largura=2.5)]
    if tipo != cp.TIPO_DIAGONAL_SIMPLES:
        partes.append(_linha(*q1, *q2, cor=COR_TRACAO, largura=2.5))
    return "".join(partes)


# ---------------------------------------------------------------------------------------------
# Contraventamento — elevação de uma linha
# ---------------------------------------------------------------------------------------------
def svg_elevacao_linha(
    e: cp.EntradaContraventamento, andares: Sequence[cp.AndarNaDirecao], direcao: str
) -> str:
    """A linha contraventada mais carregada vista de frente, com a força em cada diagonal."""
    s = e.sistema(direcao)
    comprimento = e.comprimento_x_m if direcao == "X" else e.largura_y_m
    vaos = e.vaos_x if direcao == "X" else e.vaos_y
    painel = comprimento / vaos
    largura, altura = 780.0, 470.0
    esquerda, direita, topo, base = 70.0, 190.0, 50.0, 80.0
    h_total = e.cotas_m[-1]
    escala = min((largura - esquerda - direita) / comprimento, (altura - topo - base) / h_total)
    x0, y0 = esquerda, altura - base

    def px(x_m: float) -> float:
        return x0 + x_m * escala

    def py(z_m: float) -> float:
        return y0 - z_m * escala

    corpo: list[str] = [_linha(x0 - 25, y0, px(comprimento) + 25, y0, cor="#444", largura=2)]
    for k in range(vaos + 1):
        x = px(k * painel)
        corpo.append(_linha(x, y0, x, py(h_total), cor=COR_ESTRUTURA, largura=3))
        corpo.append(
            f'<polygon points="{x - 7:.1f},{y0 + 9:.1f} {x + 7:.1f},{y0 + 9:.1f} {x:.1f},{y0:.1f}" fill="{COR_ESTRUTURA}"/>'
        )
    cotas = (0.0, *e.cotas_m)
    for z in e.cotas_m:
        corpo.append(_linha(px(0), py(z), px(comprimento), py(z), cor=COR_ESTRUTURA, largura=3))
        corpo.append(_texto(x0 - 8, py(z), f"{_n(z, 2)} m", tamanho=11, ancora="end"))
    por_andar = {a.andar: a for a in andares}
    for i in range(1, len(cotas)):
        andar = por_andar.get(i)
        if andar is None:
            continue
        zb, zt = cotas[i - 1], cotas[i]
        for p in range(min(s.paineis_por_linha, vaos)):
            xa, xb = px(p * painel), px((p + 1) * painel)
            yb_, yt = py(zb), py(zt)
            n_t = _n(andar.tracao_kN)
            n_c = _n(andar.compressao_kN)
            if s.tipo == cp.TIPO_V_INVERTIDO:
                xm = (xa + xb) / 2
                corpo.append(_linha(xa, yb_, xm, yt, cor=COR_TRACAO, largura=3))
                corpo.append(_linha(xb, yb_, xm, yt, cor=COR_COMPRESSAO, largura=3))
                corpo.append(
                    _texto(
                        (xa + xm) / 2 - 8,
                        (yb_ + yt) / 2,
                        f"+{n_t}",
                        tamanho=11,
                        cor=COR_TRACAO,
                        ancora="end",
                    )
                )
                corpo.append(
                    _texto(
                        (xb + xm) / 2 + 8,
                        (yb_ + yt) / 2,
                        f"−{n_c}",
                        tamanho=11,
                        cor=COR_COMPRESSAO,
                        ancora="start",
                    )
                )
            elif s.tipo == cp.TIPO_DIAGONAL_SIMPLES:
                corpo.append(_linha(xa, yb_, xb, yt, cor="#7b3fb5", largura=3))
                corpo.append(
                    _texto(
                        (xa + xb) / 2,
                        (yb_ + yt) / 2 - 12,
                        f"±{n_t}",
                        tamanho=11,
                        cor="#7b3fb5",
                        peso="bold",
                    )
                )
            else:
                corpo.append(_linha(xa, yb_, xb, yt, cor=COR_TRACAO, largura=3))
                if s.tipo == cp.TIPO_X_TRACAO:
                    corpo.append(
                        _linha(xa, yt, xb, yb_, cor=COR_DESPREZADA, largura=2, tracejado="6 5")
                    )
                    rotulo_c = "0 (desprezada)"
                else:
                    corpo.append(_linha(xa, yt, xb, yb_, cor=COR_COMPRESSAO, largura=3))
                    rotulo_c = f"−{n_c}"
                xm, ym = (xa + xb) / 2, (yb_ + yt) / 2
                corpo.append(
                    _texto(xm, ym - 16, f"+{n_t}", tamanho=11, cor=COR_TRACAO, peso="bold")
                )
                corpo.append(
                    _texto(
                        xm,
                        ym + 16,
                        rotulo_c,
                        tamanho=11,
                        cor=COR_COMPRESSAO if s.tipo != cp.TIPO_X_TRACAO else COR_DESPREZADA,
                    )
                )
        # cortante do andar à direita
        ym = py((zb + zt) / 2)
        corpo.append(
            _seta(px(comprimento) + 110, ym, px(comprimento) + 30, ym, cor=COR_VENTO, largura=2)
        )
        corpo.append(
            _texto(
                px(comprimento) + 36,
                ym - 14,
                f"V{i} = {_n(andar.forca_na_linha_kN)} kN",
                tamanho=11,
                ancora="start",
                cor=COR_VENTO,
            )
        )
    corpo.append(
        _texto(
            20,
            22,
            f"Elevação da linha mais carregada — direção {direcao} ({cp.TIPOS[s.tipo].split(' (')[0]})",
            tamanho=14,
            ancora="start",
            peso="bold",
        )
    )
    corpo.extend(
        _legenda(
            20,
            altura - 18,
            (
                (COR_TRACAO, "", "tração (kN)"),
                (COR_COMPRESSAO, "", "compressão (kN)"),
                (COR_DESPREZADA, "6 5", "desprezada"),
                (COR_VENTO, "", "cortante na linha (ELU, com B₂)"),
            ),
        )
    )
    return _svg(largura, altura, corpo, f"Elevação da linha contraventada em {direcao}")


# ---------------------------------------------------------------------------------------------
# Ligação de contraventamento — chapa de nó no canto viga–coluna
# ---------------------------------------------------------------------------------------------
def svg_ligacao(r: lig.ResultadoLigacao) -> str:
    """Coluna à esquerda, viga em cima, chapa no canto, a diagonal descendo a θ da vertical.

    Em escala: perfis, chapa (l_h, l_v, cortes), grupo de parafusos ao longo do eixo, seção de
    Whitmore (30° a partir da fileira mais afastada até a mais próxima do canto) e as forças de
    cálculo em cada interface pelo UFM. A posição do grupo ao longo do eixo é ilustrativa (60 mm
    de folga das faces da viga e da coluna).
    """
    e = r.entrada
    f = r.forcas
    caso_3 = e.caso == ufm.CASO_3
    dc = e.perfil_coluna.d_mm if e.ligacao_na_mesa_da_coluna else e.perfil_coluna.tw_mm
    db = e.perfil_viga.d_mm
    theta = math.radians(e.theta_graus)
    direcao = (math.sin(theta), -math.cos(theta))  # para baixo e para a direita
    perp = (math.cos(theta), math.sin(theta))  # para o lado da viga
    wp = (-e.perfil_coluna.d_mm / 2.0 if e.ligacao_na_mesa_da_coluna else 0.0, db / 2.0)
    arr = r.arranjo
    meia_grupo = arr.largura_do_grupo_mm / 2.0
    folga = 60.0
    t_inicio = 0.0
    for passo in range(0, 50000, 5):
        x = wp[0] + passo * direcao[0]
        y = wp[1] + passo * direcao[1]
        if x - meia_grupo * perp[0] >= folga and y + meia_grupo * perp[1] <= -folga:
            t_inicio = float(passo)
            break
    t_fim = t_inicio + arr.comprimento_do_grupo_mm

    def no_eixo(t: float, deslocamento: float = 0.0) -> tuple[float, float]:
        return (
            wp[0] + t * direcao[0] + deslocamento * perp[0],
            wp[1] + t * direcao[1] + deslocamento * perp[1],
        )

    lh, lv = e.lh_mm, (0.0 if caso_3 else e.lv_mm)
    borda = meia_grupo + arr.extremidade_mm
    t_borda = t_fim + arr.extremidade_mm + 30.0
    canto_a = no_eixo(t_borda, borda)
    canto_b = no_eixo(t_borda, -borda)
    pontos_chapa = [(e.corte_h_mm, 0.0), (max(lh, e.corte_h_mm + 1), 0.0), canto_a, canto_b]
    if caso_3:
        pontos_chapa.append((e.corte_h_mm, canto_b[1]))
    else:
        pontos_chapa += [(0.0, -lv), (0.0, -e.corte_v_mm)]
    fim_barra = t_fim + max(700.0, 0.6 * arr.comprimento_do_grupo_mm)
    ponta = no_eixo(fim_barra)
    xs = [x for x, _ in pontos_chapa] + [ponta[0], -dc]
    ys = [y for _, y in pontos_chapa] + [ponta[1], db]
    xmin, xmax = min(xs) - 90, max(xs) + 40
    ymin, ymax = min(ys) - 80, max(ys) + 50
    largura, altura = 780.0, 560.0
    esquerda, direita, topo, base = 40.0, 250.0, 46.0, 40.0
    escala = min(
        (largura - esquerda - direita) / (xmax - xmin), (altura - topo - base) / (ymax - ymin)
    )

    def px(x: float) -> float:
        return esquerda + (x - xmin) * escala

    def py(y: float) -> float:
        return topo + (ymax - y) * escala

    def ponto(x: float, y: float) -> str:
        return f"{px(x):.1f},{py(y):.1f}"

    corpo: list[str] = []
    corpo.append(
        f'<rect x="{px(-dc):.1f}" y="{py(ymax):.1f}" width="{dc * escala:.1f}" '
        f'height="{(ymax - ymin) * escala:.1f}" fill="#dfe3e8" stroke="{COR_ESTRUTURA}" stroke-width="2"/>'
    )
    corpo.append(
        f'<rect x="{px(0):.1f}" y="{py(db):.1f}" width="{(xmax - 0) * escala:.1f}" '
        f'height="{db * escala:.1f}" fill="#dfe3e8" stroke="{COR_ESTRUTURA}" stroke-width="2"/>'
    )
    corpo.append(
        _texto(px(xmax) - 8, py(db) + 14, f"viga {e.perfil_viga.nome}", tamanho=11, ancora="end")
    )
    corpo.append(
        _texto(
            px(-dc / 2),
            py(ymin) - 14,
            f"coluna {e.perfil_coluna.nome}",
            tamanho=11,
            giro=-90,
            ancora="start",
        )
    )
    eixo = dict(cor="#8a9099", largura=1.0, tracejado="12 4 3 4")
    corpo.append(_linha(px(xmin), py(db / 2), px(xmax), py(db / 2), **eixo))
    if e.ligacao_na_mesa_da_coluna:
        corpo.append(_linha(px(-dc / 2), py(ymin), px(-dc / 2), py(ymax), **eixo))
    corpo.append(
        f'<polygon points="{" ".join(ponto(x, y) for x, y in pontos_chapa)}" fill="{COR_CHAPA}" '
        f'stroke="#8a6d1a" stroke-width="2"/>'
    )
    # barra do contraventamento (contorno) e o eixo até o ponto de trabalho
    meia_barra = meia_grupo + 0.6 * arr.extremidade_mm + 15
    inicio_barra = t_inicio - arr.extremidade_mm
    for lado in (-1.0, 1.0):
        a = no_eixo(inicio_barra, lado * meia_barra)
        b = no_eixo(fim_barra, lado * meia_barra)
        corpo.append(_linha(px(a[0]), py(a[1]), px(b[0]), py(b[1]), cor=COR_TRACAO, largura=2.5))
    a, b = no_eixo(inicio_barra, -meia_barra), no_eixo(inicio_barra, meia_barra)
    corpo.append(_linha(px(a[0]), py(a[1]), px(b[0]), py(b[1]), cor=COR_TRACAO, largura=2.5))
    corpo.append(_linha(px(wp[0]), py(wp[1]), px(ponta[0]), py(ponta[1]), **eixo))
    corpo.append(
        f'<circle cx="{px(wp[0]):.1f}" cy="{py(wp[1]):.1f}" r="5" fill="{COR_COMPRESSAO}"/>'
    )
    corpo.append(
        _texto(px(wp[0]) + 8, py(wp[1]) - 12, "ponto de trabalho", tamanho=10, ancora="start")
    )
    # Whitmore: da fileira mais afastada (por onde a força entra) até a mais próxima do canto
    meia_w = r.largura_de_whitmore_mm / 2.0
    verde = "#2da44e"
    for lado in (-1.0, 1.0):
        a = no_eixo(t_fim, lado * meia_grupo)
        b = no_eixo(t_inicio, lado * meia_w)
        corpo.append(
            _linha(px(a[0]), py(a[1]), px(b[0]), py(b[1]), cor=verde, largura=1.5, tracejado="5 4")
        )
    w1, w2 = no_eixo(t_inicio, -meia_w), no_eixo(t_inicio, meia_w)
    corpo.append(_linha(px(w1[0]), py(w1[1]), px(w2[0]), py(w2[1]), cor=verde, largura=2.5))
    # parafusos
    raio = max(2.5, 0.5 * 22.0 * escala)
    for i in range(arr.por_fileira):
        for jf in range(arr.fileiras):
            x, y = no_eixo(
                t_inicio + i * arr.passo_mm, (jf - (arr.fileiras - 1) / 2) * arr.gabarito_mm
            )
            corpo.append(
                f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="{raio:.1f}" fill="{COR_PARAFUSO}"/>'
            )
    # cotas l_h (abaixo de tudo) e l_v (à esquerda da coluna)
    y_cota = min(ys) - 45
    corpo.append(_linha(px(0), py(y_cota), px(lh), py(y_cota), cor="#555", largura=1))
    for x in (0.0, lh):
        corpo.append(_linha(px(x), py(y_cota) - 6, px(x), py(y_cota) + 6, cor="#555", largura=1))
    corpo.append(_texto(px(lh / 2), py(y_cota) + 13, f"l_h = {_n(lh, 0)} mm", tamanho=11))
    if not caso_3:
        x_cota = -dc - 45
        corpo.append(_linha(px(x_cota), py(0), px(x_cota), py(-lv), cor="#555", largura=1))
        for y in (0.0, -lv):
            corpo.append(
                _linha(px(x_cota) - 6, py(y), px(x_cota) + 6, py(y), cor="#555", largura=1)
            )
        corpo.append(
            _texto(px(x_cota) - 12, py(-lv / 2), f"l_v = {_n(lv, 0)} mm", tamanho=11, giro=-90)
        )
    # forças nas interfaces, desenhadas do lado do perfil (fora da chapa)
    vermelho = COR_COMPRESSAO
    xa = px(r.alfa_real_mm)
    corpo.append(_seta(xa - 55, py(0) - 16, xa, py(0) - 16, cor=vermelho, largura=2))
    corpo.append(
        _texto(xa - 60, py(0) - 16, "H_b", tamanho=11, ancora="end", cor=vermelho, peso="bold")
    )
    corpo.append(_seta(xa + 16, py(0) - 62, xa + 16, py(0) - 4, cor=vermelho, largura=2))
    corpo.append(
        _texto(xa + 24, py(0) - 52, "V_b", tamanho=11, ancora="start", cor=vermelho, peso="bold")
    )
    if not caso_3:
        yb = py(-r.beta_real_mm)
        corpo.append(_seta(px(0) - 62, yb + 14, px(0) - 4, yb + 14, cor=vermelho, largura=2))
        corpo.append(_texto(px(0) - 50, yb + 28, "H_c", tamanho=11, cor=vermelho, peso="bold"))
        corpo.append(_seta(px(0) - 18, yb + 50, px(0) - 18, yb - 6, cor=vermelho, largura=2))
        corpo.append(
            _texto(px(0) - 26, yb - 16, "V_c", tamanho=11, ancora="end", cor=vermelho, peso="bold")
        )
    # quadro de valores
    xq = largura - direita + 18
    linhas_quadro: list[tuple[str, bool]] = [
        ("Forças de cálculo (UFM)", True),
        (
            f"P = {_n(max(e.P_tracao_kN, e.P_compressao_kN), 0)} kN a {_n(e.theta_graus, 1)}° da vertical",
            False,
        ),
        ("Chapa–viga", True),
        (f"  H_b = {_n(f.viga_cisalhamento_kN, 0)} kN   V_b = {_n(f.viga_normal_kN, 0)} kN", False),
    ]
    if not caso_3:
        linhas_quadro += [
            ("Chapa–coluna", True),
            (
                f"  V_c = {_n(f.coluna_cisalhamento_kN, 0)} kN   H_c = {_n(f.coluna_normal_kN, 0)} kN",
                False,
            ),
        ]
    linhas_quadro += [
        ("Viga–coluna", True),
        (f"  V = {_n(f.vc_cisalhamento_kN, 0)} kN   N = {_n(f.vc_axial_kN, 0)} kN", False),
        ("Geometria", True),
        (f"  α̅ = {_n(f.alfa_ideal_mm, 0)} mm   α = {_n(r.alfa_real_mm, 0)} mm", False),
    ]
    if not caso_3:
        linhas_quadro.append(
            (f"  β̅ = {_n(f.beta_ideal_mm, 0)} mm   β = {_n(r.beta_real_mm, 0)} mm", False)
        )
    linhas_quadro += [
        (f"  chapa t = {_n(e.t_chapa_mm, 1)} mm", False),
        (
            f"  {arr.fileiras} × {arr.por_fileira} parafusos {e.designacao_do_parafuso} {e.grau_do_parafuso}",
            False,
        ),
        (f"  Whitmore {_n(r.largura_de_whitmore_mm, 0)} mm", False),
        (
            f"  solda {_n(e.perna_na_viga_mm, 0)} mm na viga"
            + ("" if caso_3 else f", {_n(e.perna_na_coluna_mm, 0)} mm na coluna"),
            False,
        ),
    ]
    y = topo + 4
    for texto, negrito in linhas_quadro:
        corpo.append(
            _texto(xq, y, texto, tamanho=11, ancora="start", peso="bold" if negrito else "normal")
        )
        y += 18
    corpo.extend(
        _legenda(
            xq,
            y + 12,
            ((verde, "5 4", "seção de Whitmore"),),
        )
    )
    corpo.append(
        _texto(
            16,
            20,
            "Chapa de nó — viga em cima, coluna à esquerda (em escala)",
            tamanho=14,
            ancora="start",
            peso="bold",
        )
    )
    corpo.append(
        _texto(
            16,
            altura - 14,
            "Posição do grupo ao longo do eixo e recortes ilustrativos: confira no desenho de fabricação.",
            tamanho=10,
            ancora="start",
            cor="#666",
        )
    )
    return _svg(largura, altura, corpo, "Chapa de nó do contraventamento")


# ---------------------------------------------------------------------------------------------
# Convenção de eixos do plano de cargas e limite de deslocamento da base técnica
# ---------------------------------------------------------------------------------------------
def svg_convencao_de_eixos(eixos: str) -> str:
    """Planta com as direções do vento e elevação com o eixo vertical e a gravidade."""
    from core import exportacao_cargas as ex

    vertical = ex.eixo_vertical(eixos)
    corpo: list[str] = [
        _texto(175, 20, "Planta — direções do vento", tamanho=13, peso="bold"),
        _texto(490, 20, "Elevação — vertical e gravidade", tamanho=13, peso="bold"),
        f'<rect x="110" y="100" width="130" height="80" fill="#eef1f5" stroke="{COR_ESTRUTURA}" '
        'stroke-width="1.5"/>',
        _texto(175, 140, "estrutura", tamanho=11, cor=COR_ESTRUTURA),
        _seta(40, 140, 100, 140),
        _texto(62, 126, "W0 → +X", tamanho=11, cor=COR_VENTO, peso="bold"),
        _seta(310, 140, 250, 140),
        _texto(290, 126, "W180 → −X", tamanho=11, cor=COR_VENTO, peso="bold"),
        _seta(175, 250, 175, 190),
        _texto(185, 238, "W90 → +Y", tamanho=11, ancora="start", cor=COR_VENTO, peso="bold"),
        _seta(175, 40, 175, 92),
        _texto(185, 56, "W270 → −Y", tamanho=11, ancora="start", cor=COR_VENTO, peso="bold"),
        _seta(30, 262, 72, 262, cor=COR_TEXTO, largura=1.8),
        _texto(80, 262, "X", tamanho=12, ancora="start", peso="bold"),
        _seta(30, 262, 30, 220, cor=COR_TEXTO, largura=1.8),
        _texto(
            22, 210, "Y" if vertical == "Z" else "Y → −Z", tamanho=12, ancora="start", peso="bold"
        ),
        _linha(420, 235, 620, 235, cor=COR_ESTRUTURA, largura=1.5),
        _linha(450, 235, 450, 110, cor=COR_ESTRUTURA, largura=3),
        _linha(590, 235, 590, 110, cor=COR_ESTRUTURA, largura=3),
        _linha(450, 110, 590, 110, cor=COR_ESTRUTURA, largura=3),
        _seta(520, 135, 520, 200, cor=COR_COMPRESSAO, largura=2.2),
        _texto(530, 168, "g", tamanho=13, ancora="start", cor=COR_COMPRESSAO, peso="bold"),
        _seta(380, 262, 380, 205, cor=COR_TEXTO, largura=1.8),
        _texto(380, 195, vertical, tamanho=12, peso="bold"),
        _seta(380, 262, 420, 262, cor=COR_TEXTO, largura=1.8),
        _texto(428, 262, "X", tamanho=12, ancora="start", peso="bold"),
        _texto(
            320,
            288,
            "No plano: Z (vertical) com valor positivo = para baixo; X e Y levam o sinal no valor.",
            tamanho=11,
        ),
    ]
    altura = 310.0
    if vertical == "Y":
        corpo.append(
            _texto(
                320,
                305,
                "No SolidWorks (Y para cima): X → X · Y da planta → −Z · Z (vertical) → Y",
                tamanho=11,
                peso="bold",
            )
        )
        altura = 322.0
    return _svg(640, altura, corpo, "Convenção de eixos e direções do vento")


def svg_limite_de_deslocamento(divisor: float, maximo_mm: float | None, altura_m: float) -> str:
    """Pórtico deslocado pelo vento com o limite δ ≤ H/divisor escrito."""
    limite = altura_m * 1000.0 / divisor
    if maximo_mm:
        limite = min(limite, maximo_mm)
    corpo = [
        _linha(90, 220, 330, 220, cor=COR_ESTRUTURA, largura=1.5),
        _linha(130, 220, 130, 70, cor=COR_ESTRUTURA, largura=3),
        _linha(290, 220, 290, 70, cor=COR_ESTRUTURA, largura=3),
        _linha(130, 70, 290, 70, cor=COR_ESTRUTURA, largura=3),
        _linha(130, 220, 162, 70, cor=COR_TRACAO, largura=2, tracejado="6 4"),
        _linha(290, 220, 322, 70, cor=COR_TRACAO, largura=2, tracejado="6 4"),
        _linha(162, 70, 322, 70, cor=COR_TRACAO, largura=2, tracejado="6 4"),
        _seta(30, 55, 122, 55),
        _texto(60, 42, "vento", tamanho=11, cor=COR_VENTO, peso="bold"),
        _linha(290, 50, 322, 50, cor=COR_TEXTO, largura=1.2),
        _linha(290, 44, 290, 56, cor=COR_TEXTO, largura=1.2),
        _linha(322, 44, 322, 56, cor=COR_TEXTO, largura=1.2),
        _texto(306, 36, "δ", tamanho=14, peso="bold"),
        _linha(100, 220, 100, 70, cor=COR_TEXTO, largura=1.2),
        _linha(94, 220, 106, 220, cor=COR_TEXTO, largura=1.2),
        _linha(94, 70, 106, 70, cor=COR_TEXTO, largura=1.2),
        _texto(92, 145, f"H = {_n(altura_m, 2)} m", tamanho=11, ancora="end"),
        _texto(
            210,
            245,
            f"δ ≤ H/{divisor:g}"
            + (f" (máx. {maximo_mm:g} mm)" if maximo_mm else "")
            + f" = {_n(limite, 1)} mm",
            tamanho=13,
            peso="bold",
        ),
    ]
    return _svg(360, 262, corpo, "Limite do deslocamento horizontal do topo")


def svg_viga_de_piso(
    vao_m: float, q_kN_m: float, p_kN: float, flecha_mm: float, reacao_kN: float
) -> str:
    """Viga biapoiada com a carga distribuída, a concentrada no meio, a deformada e as reações."""
    x0, x1, y = 90.0, 550.0, 130.0
    meio = (x0 + x1) / 2
    corpo: list[str] = [
        f'<polygon points="{x0:.0f},{y + 2:.0f} {x0 - 12:.0f},{y + 22:.0f} {x0 + 12:.0f},{y + 22:.0f}" '
        f'fill="none" stroke="{COR_ESTRUTURA}" stroke-width="1.6"/>',
        f'<polygon points="{x1:.0f},{y + 2:.0f} {x1 - 12:.0f},{y + 18:.0f} {x1 + 12:.0f},{y + 18:.0f}" '
        f'fill="none" stroke="{COR_ESTRUTURA}" stroke-width="1.6"/>',
        f'<circle cx="{x1:.0f}" cy="{y + 22:.0f}" r="3.5" fill="none" stroke="{COR_ESTRUTURA}"/>',
        _linha(x0 - 20, y + 26, x0 + 20, y + 26, cor=COR_ESTRUTURA, largura=1.2),
        _linha(x1 - 20, y + 26, x1 + 20, y + 26, cor=COR_ESTRUTURA, largura=1.2),
        f'<path d="M{x0:.0f},{y:.0f} Q{meio:.0f},{y + 48:.0f} {x1:.0f},{y:.0f}" fill="none" '
        f'stroke="{COR_TRACAO}" stroke-width="1.8" stroke-dasharray="6 4"/>',
        _linha(x0, y, x1, y, cor=COR_ESTRUTURA, largura=5),
        _linha(x0, 78, x1, 78, cor=COR_COMPRESSAO, largura=1.2),
        _texto(
            x0,
            64,
            f"q = {_n(q_kN_m, 2)} kN/m (total)",
            tamanho=11,
            ancora="start",
            cor=COR_COMPRESSAO,
        ),
    ]
    passo = (x1 - x0) / 10
    for i in range(11):
        if p_kN > 0 and i == 5:
            continue  # o meio do vão fica para a carga concentrada
        x = x0 + i * passo
        corpo.append(_seta(x, 78, x, y - 4, cor=COR_COMPRESSAO, largura=1.3))
    if p_kN > 0:
        corpo.append(_seta(meio, 30, meio, y - 4, cor=COR_VENTO, largura=2.6))
        corpo.append(
            _texto(
                meio + 10,
                38,
                f"P = {_n(p_kN, 1)} kN",
                tamanho=12,
                ancora="start",
                cor=COR_VENTO,
                peso="bold",
            )
        )
    esbeltez = vao_m * 1000 / flecha_mm if flecha_mm > 0 else math.inf
    corpo += [
        _texto(
            meio,
            y + 40,
            f"δ = {_n(flecha_mm, 1)} mm (L/{esbeltez:.0f})",
            tamanho=11,
            cor=COR_TRACAO,
            peso="bold",
        ),
        _seta(x0, y + 72, x0, y + 32, cor=COR_ESTRUTURA, largura=1.8),
        _seta(x1, y + 72, x1, y + 32, cor=COR_ESTRUTURA, largura=1.8),
        _texto(x0 + 8, y + 64, f"R = {_n(reacao_kN, 1)} kN", tamanho=11, ancora="start"),
        _texto(x1 - 8, y + 64, f"R = {_n(reacao_kN, 1)} kN", tamanho=11, ancora="end"),
        _linha(x0, y + 92, x1, y + 92, cor=COR_TEXTO, largura=1),
        _linha(x0, y + 86, x0, y + 98, cor=COR_TEXTO, largura=1),
        _linha(x1, y + 86, x1, y + 98, cor=COR_TEXTO, largura=1),
        _texto(meio, y + 106, f"L = {_n(vao_m, 2)} m", tamanho=12, peso="bold"),
    ]
    return _svg(640, y + 118, corpo, "Viga de piso biapoiada")


def svg_placa_de_base(
    *,
    comprimento_mm: float,
    largura_mm: float,
    altura_perfil_mm: float,
    largura_mesa_mm: float,
    espessura_mesa_mm: float,
    espessura_alma_mm: float,
    chumbadores: int,
    distancia_mm: float,
    furo_mm: float,
    arruela_mm: float,
) -> str:
    """Planta da placa de base: o pilar (seção I), os chumbadores em duas linhas a ±f, furos e arruelas."""
    escala = 300.0 / max(comprimento_mm, largura_mm)
    cx, cy = 180.0, 190.0
    meio_n, meio_b = comprimento_mm * escala / 2, largura_mm * escala / 2
    corpo: list[str] = [
        f'<rect x="{cx - meio_n:.1f}" y="{cy - meio_b:.1f}" width="{2 * meio_n:.1f}" '
        f'height="{2 * meio_b:.1f}" fill="#e9edf2" stroke="{COR_ESTRUTURA}" stroke-width="1.6"/>',
    ]
    # Pilar: a alma na direção de N (a do momento), as mesas perpendiculares.
    d, bf = altura_perfil_mm * escala, largura_mesa_mm * escala
    tf, tw = max(espessura_mesa_mm * escala, 2.0), max(espessura_alma_mm * escala, 1.5)
    for lado in (-1, 1):
        x = cx + lado * (d / 2 - tf / 2)
        corpo.append(
            f'<rect x="{x - tf / 2:.1f}" y="{cy - bf / 2:.1f}" width="{tf:.1f}" height="{bf:.1f}" '
            f'fill="{COR_CONTRAVENTADO}"/>'
        )
    corpo.append(
        f'<rect x="{cx - d / 2:.1f}" y="{cy - tw / 2:.1f}" width="{d:.1f}" height="{tw:.1f}" '
        f'fill="{COR_CONTRAVENTADO}"/>'
    )
    # Chumbadores: metade em cada linha (a do lado tracionado e a oposta).
    por_linha = [chumbadores - chumbadores // 2, chumbadores // 2]
    borda = max(furo_mm, arruela_mm) * escala / 2 + 6
    for lado, quantidade in zip((1, -1), por_linha, strict=True):
        x = cx + lado * distancia_mm * escala
        if quantidade == 1:
            posicoes = [cy]
        else:
            passo = (2 * meio_b - 2 * borda) / (quantidade - 1)
            posicoes = [cy - meio_b + borda + i * passo for i in range(quantidade)]
        for y in posicoes:
            a = arruela_mm * escala
            corpo += [
                f'<rect x="{x - a / 2:.1f}" y="{y - a / 2:.1f}" width="{a:.1f}" height="{a:.1f}" '
                f'fill="none" stroke="{COR_PARAFUSO}" stroke-width="1" stroke-dasharray="3 2"/>',
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{furo_mm * escala / 2:.1f}" fill="#ffffff" '
                f'stroke="{COR_PARAFUSO}" stroke-width="1.2"/>',
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{max(furo_mm * escala / 4, 2):.1f}" '
                f'fill="{COR_PARAFUSO}"/>',
            ]
    topo, base = cy - meio_b, cy + meio_b
    esquerda, direita = cx - meio_n, cx + meio_n
    corpo += [
        # N embaixo, B à direita, f em cima.
        _linha(esquerda, base + 22, direita, base + 22, cor=COR_TEXTO, largura=1),
        _linha(esquerda, base + 16, esquerda, base + 28, cor=COR_TEXTO, largura=1),
        _linha(direita, base + 16, direita, base + 28, cor=COR_TEXTO, largura=1),
        _texto(cx, base + 38, f"N = {_n(comprimento_mm, 0)} mm", tamanho=12, peso="bold"),
        _linha(direita + 22, topo, direita + 22, base, cor=COR_TEXTO, largura=1),
        _linha(direita + 16, topo, direita + 28, topo, cor=COR_TEXTO, largura=1),
        _linha(direita + 16, base, direita + 28, base, cor=COR_TEXTO, largura=1),
        _texto(
            direita + 36, cy, f"B = {_n(largura_mm, 0)} mm", tamanho=12, ancora="start", peso="bold"
        ),
        _linha(cx, topo - 18, cx + distancia_mm * escala, topo - 18, cor=COR_TRACAO, largura=1),
        _linha(cx, topo - 24, cx, topo - 12, cor=COR_TRACAO, largura=1),
        _linha(
            cx + distancia_mm * escala,
            topo - 24,
            cx + distancia_mm * escala,
            topo - 12,
            cor=COR_TRACAO,
            largura=1,
        ),
        _texto(
            cx + distancia_mm * escala / 2,
            topo - 30,
            f"f = {_n(distancia_mm, 0)} mm",
            tamanho=11,
            cor=COR_TRACAO,
        ),
        _texto(
            esquerda,
            topo - 52,
            f"Furo {_n(furo_mm, 0)} mm · arruela {_n(arruela_mm, 0)} mm (tracejada)",
            tamanho=11,
            ancora="start",
        ),
        _linha(cx, topo - 6, cx, base + 6, cor=COR_COMPRESSAO, largura=1, tracejado="8 3 2 3"),
        _texto(cx + 6, base - 10, "eixo forte", tamanho=10, ancora="start", cor=COR_COMPRESSAO),
    ]
    return _svg(470, base + 56, corpo, "Placa de base do pilar em planta")
