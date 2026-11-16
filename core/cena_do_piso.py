"""O esqueleto em 3D como o programa o entendeu para as cargas do piso (página Cargas do
esqueleto): o que é cada peça, a área da chapa que cada viga recebe e a carga de um caso.

O desenho é o núcleo :mod:`core.cena_3d`; as barras com o perfil vêm de
:mod:`core.cena_do_modelo`. Sem Streamlit.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from core import cargas_pelo_modelo as cpm
from core import cena_3d as c3
from core import cena_do_modelo as cm
from core import leitura_do_modelo as ld
from core import piso_do_modelo as pm

COR_POR_PAPEL = "O que é cada peça"
COR_POR_INFLUENCIA = "Área que cada viga recebe"
COR_POR_CARGA = "Carga do caso (kN/m)"
CORES = (COR_POR_PAPEL, COR_POR_INFLUENCIA, COR_POR_CARGA)

COR_DO_PAPEL: dict[str, str] = {
    ld.TIPO_PILAR: "#3f6fb5",
    "Viga com piso": "#d4760a",
    ld.TIPO_VIGA: "#8a929c",
    ld.TIPO_CONTRAVENTAMENTO: "#7b5ea7",
    pm.PAPEL_LONGARINA: "#2e7d32",
    pm.PAPEL_PECA_CURTA: "#a1887f",
}
COR_DA_CHAPA: dict[str, str] = {
    pm.TIPO_PISO: "#f8b46a",
    pm.TIPO_PATAMAR: "#9ccc65",
    pm.TIPO_ESCADA: "#66bb6a",
    pm.TIPO_SEM_CARGA: "#cfd5dc",
}
COR_SEM_CARGA = "#cfd5dc"
#: Cores bem separadas, para a faixa da chapa e a viga que a recebe.
PALETA_DAS_VIGAS: tuple[str, ...] = (
    "#3f6fb5",
    "#d4760a",
    "#2e7d32",
    "#b23a48",
    "#7b5ea7",
    "#00897b",
    "#c0a000",
    "#5d4037",
    "#0277bd",
    "#e65100",
    "#558b2f",
    "#ad1457",
)


def _contorno(chapa: cpm.ChapaDoPiso, eixo_vertical: str) -> tuple[c3.Ponto, ...]:
    return tuple(cm._planta(p, eixo_vertical) for p in pm._contorno_no_espaco(chapa))


def _centro(pontos: tuple[c3.Ponto, ...], subir: float = 0.0) -> c3.Ponto:
    n = max(len(pontos), 1)
    return (
        sum(p[0] for p in pontos) / n,
        sum(p[1] for p in pontos) / n,
        sum(p[2] for p in pontos) / n + subir,
    )


def cena_do_piso(
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    leitura: pm.LeituraDoPiso,
    escolha: pm.EscolhaDoPiso,
    distribuicao: cpm.DistribuicaoDoPiso,
    *,
    cor_por: str = COR_POR_PAPEL,
    caso: str = "",
    rotulos_das_vigas: Mapping[str, str] | None = None,
) -> c3.Cena:
    """A cena para conferir a leitura do modelo.

    * ``COR_POR_PAPEL``: pilares, vigas que recebem piso, vigas sem piso, diagonais, longarinas;
      cada chapa na cor do tipo dela (piso, patamar, escada, sem carga);
    * ``COR_POR_INFLUENCIA``: cada chapa cortada em faixas com a cor da viga que as recebe;
    * ``COR_POR_CARGA``: as vigas na escala de kN/m do caso, com o pente da carga (só no trecho,
      quando a carga é parcial).
    """
    papeis = leitura.papel
    carregadas = {c.viga for c in distribuicao.cargas}
    barras, _, _ = cm.barras_da_cena(g, eixo_vertical, cor_por=cm.COR_UNICA)
    paineis: list[c3.PainelCena] = []
    textos: list[c3.TextoCena] = []
    distribuidas: list[c3.CargaDistribuidaCena] = []
    legenda: list[tuple[str, str]] = []
    escala = None
    rotulos = dict(rotulos_das_vigas or {})

    for chapa in leitura.chapas:
        pontos = _contorno(chapa.chapa, eixo_vertical)
        if len(pontos) >= 3:
            tipo = escolha.da_chapa(chapa.nome).tipo
            textos.append(c3.TextoCena(_centro(pontos, 0.05), f"{chapa.codigo} · {tipo.lower()}"))

    if cor_por == COR_POR_INFLUENCIA:
        cor_da_viga: dict[str, str] = {}
        for chapa in leitura.chapas:
            da_chapa = escolha.da_chapa(chapa.nome)
            pontos = _contorno(chapa.chapa, eixo_vertical)
            if da_chapa.tipo == pm.TIPO_SEM_CARGA or not chapa.vigas:
                if len(pontos) >= 3:
                    paineis.append(c3.PainelCena(chapa.nome, pontos, COR_SEM_CARGA, 0.35, "chapa"))
                continue
            for faixa in cpm.mapa_de_influencia(g, chapa.chapa, da_chapa.sentido):
                if faixa.viga not in cor_da_viga:
                    cor_da_viga[faixa.viga] = PALETA_DAS_VIGAS[
                        len(cor_da_viga) % len(PALETA_DAS_VIGAS)
                    ]
                paineis.append(
                    c3.PainelCena(
                        f"{chapa.nome} → {faixa.viga}",
                        tuple(cm._planta(p, eixo_vertical) for p in faixa.pontos),
                        cor_da_viga[faixa.viga],
                        0.62,
                        "influência",
                        sombra=False,
                    )
                )
        barras = [replace(b, cor=cor_da_viga.get(b.nome, COR_SEM_CARGA)) for b in barras]
        legenda = [
            ("#d4760a", "cada cor: uma viga e a área da chapa que vai para ela"),
            (COR_SEM_CARGA, "barra que não recebe piso"),
        ]
    else:
        for chapa in leitura.chapas:
            pontos = _contorno(chapa.chapa, eixo_vertical)
            if len(pontos) < 3:
                continue
            tipo = escolha.da_chapa(chapa.nome).tipo
            opacidade = 0.42 if cor_por == COR_POR_PAPEL else 0.22
            paineis.append(
                c3.PainelCena(chapa.nome, pontos, COR_DA_CHAPA[tipo], opacidade, "chapa")
            )
        if cor_por == COR_POR_CARGA and caso:
            cargas = {c.viga: c for c in distribuicao.do_caso(caso)}
            maximo = max((c.kN_m for c in cargas.values()), default=0.0) or 1.0
            escala = c3.EscalaDeCor(0.0, maximo, "kN/m", f"Carga do {caso} nas vigas")
            corpos = {c.nome: c for c in g.corpos}
            novas = []
            for b in barras:
                carga = cargas.get(b.nome)
                cor = (
                    c3.cor_da_escala(0.08 + 0.92 * carga.kN_m / maximo)
                    if carga is not None
                    else COR_SEM_CARGA
                )
                novas.append(replace(b, cor=cor))
                corpo = corpos.get(b.nome)
                if carga is None or corpo is None or corpo.comprimento_m <= 0:
                    continue
                a = cm._planta(corpo.inicio, eixo_vertical)
                fim = cm._planta(corpo.fim, eixo_vertical)
                t0, t1 = 0.0, 1.0
                if carga.parcial:
                    t0 = carga.de_m / corpo.comprimento_m
                    t1 = carga.ate_m / corpo.comprimento_m
                inicio_do_trecho = tuple(a[k] + t0 * (fim[k] - a[k]) for k in range(3))
                fim_do_trecho = tuple(a[k] + t1 * (fim[k] - a[k]) for k in range(3))
                distribuidas.append(
                    c3.CargaDistribuidaCena(
                        inicio_do_trecho,  # type: ignore[arg-type]
                        fim_do_trecho,  # type: ignore[arg-type]
                        (0.0, 0.0, -carga.kN_m),
                        "",
                        cm.COR_DA_CARGA,
                        caso,
                    )
                )
            barras = novas
            maiores = sorted(range(len(distribuidas)), key=lambda i: -cargas_valor(distribuidas[i]))
            for indice in maiores[:6]:
                d = distribuidas[indice]
                distribuidas[indice] = replace(
                    d, rotulo=f"{cargas_valor(d):.2f} kN/m".replace(".", ",")
                )
        else:
            novas = []
            vistos: dict[str, str] = {}
            for b in barras:
                papel = papeis.get(b.nome, ld.TIPO_VIGA)
                if b.nome in carregadas and papel == ld.TIPO_VIGA:
                    papel = "Viga com piso"
                cor = COR_DO_PAPEL.get(papel, cm.COR_DE_OUTRO_TIPO)
                vistos[papel] = cor
                novas.append(replace(b, cor=cor, grupo=papel))
            barras = novas
            nomes = {
                ld.TIPO_VIGA: "viga sem piso em cima",
                ld.TIPO_CONTRAVENTAMENTO: "diagonal ou contraventamento",
            }
            legenda = [(cor, nomes.get(papel, papel.lower())) for papel, cor in vistos.items()]
            tipos_vistos = dict.fromkeys(escolha.da_chapa(c.nome).tipo for c in leitura.chapas)
            legenda += [(COR_DA_CHAPA[t], f"chapa: {t.lower()}") for t in tipos_vistos]
    if rotulos:
        barras = [replace(b, rotulo=rotulos.get(b.nome, b.rotulo)) for b in barras]
    return c3.Cena(
        barras=tuple(barras),
        paineis=tuple(paineis),
        distribuidas=tuple(distribuidas),
        textos=tuple(textos),
        titulo={
            COR_POR_PAPEL: "O que o programa entendeu do modelo",
            COR_POR_INFLUENCIA: "A área da chapa que cada viga recebe",
            COR_POR_CARGA: f"Carga do {caso} nas vigas" if caso else "Carga nas vigas",
        }.get(cor_por, ""),
        subtitulo=(
            f"{g.arquivo or 'esqueleto do modelo'} · {len(barras)} barras · "
            f"{len(leitura.chapas)} chapas de piso"
        ),
        legenda=tuple(legenda),
        escala=escala,
        eixo_vertical_do_modelo=eixo_vertical,
    )


def cargas_valor(carga: c3.CargaDistribuidaCena) -> float:
    return c3._norma(carga.vetor_por_metro)
