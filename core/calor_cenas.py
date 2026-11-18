"""Cenas, figuras e registro das contas de calor no tempo (parede/cilindro/esfera e seção).

As contas estão em :mod:`core.calor_no_tempo` e :mod:`core.calor_na_secao`; aqui elas viram a cena
do tocador (:mod:`core.animacao`), as figuras do memorial (:mod:`core.figuras_no_tempo`) e o
registro no projeto.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from core import calor_na_secao as cs
from core import calor_no_tempo as ct
from core import figuras_no_tempo as fnt
from core import secao_desenhada as sd
from core.animacao import (
    CALOR,
    Cena,
    reamostrar,
    tempo_em_texto,
    tempos_dos_quadros,
    unidade_de_tempo,
)
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    linhas_para_registro,
    numero_json,
    status_geral,
)

MODULO_ID = "calor_no_tempo"
MODULO_TITULO = "Calor no tempo"
_FAIXAS = 40  # faixas (ou anéis) coloridas no desenho da peça
_REFERENCIAS = [
    "Incropera, F. P. et al. Fundamentos de Transferência de Calor e de Massa, 6ª ed. LTC, 2008 "
    "(cap. 5: condução transiente; Tab. A.1 e A.3).",
    "Çengel, Y. A.; Ghajar, A. J. Transferência de Calor e Massa, 4ª ed. McGraw-Hill, 2012 (cap. 4).",
]
_N = ct._n


def _faixa_de_temperatura(*valores: Any) -> tuple[float, float]:
    tudo = np.concatenate([np.ravel(np.asarray(v, dtype=float)) for v in valores if v is not None])
    tudo = tudo[np.isfinite(tudo)]
    return float(tudo.min()), float(tudo.max())


def _minuscula(texto: str) -> str:
    return texto[:1].lower() + texto[1:]


def _maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _temperaturas_das_faces(p: ct.Peca) -> list[float]:
    saida = []
    for face in (p.face_a, p.face_b):
        if face.tipo == ct.CONVECCAO:
            saida.append(face.t_fluido)
        elif face.tipo == ct.TEMPERATURA:
            saida.append(face.t_fixa)
    return saida


def _texto_da_face(face: ct.Face) -> str:
    if face.tipo == ct.CONVECCAO:
        return f"fluido a {_N(face.t_fluido, 1)} °C · h = {_N(face.h, 0)} W/m²K"
    if face.tipo == ct.TEMPERATURA:
        return f"face a {_N(face.t_fixa, 1)} °C"
    if face.tipo == ct.FLUXO:
        return f"q = {_N(face.fluxo, 0)} W/m² entrando"
    return "isolada"


# ---------------------------------------------------------------------------------------------
# Parede, cilindro, esfera
# ---------------------------------------------------------------------------------------------
#: Cor das setas de calor e cores dos três pontos (as mesmas das curvas, na ordem fixa).
COR_CALOR = "#de5524"
CORES_DOS_PONTOS = ("#2a78d6", "#eb6834", "#1baf7a")
NOTA_DAS_SETAS = (
    "Setas laranja: o calor, entrando ou saindo pela face (o tamanho acompanha a intensidade). "
    "Bolinhas: os pontos das curvas."
)


def marcos_do_calor(m: ct.Marcos, tempo_do_alvo: float | None) -> list[tuple[str, float | None]]:
    return [
        ("equaliza", m.equaliza),
        ("estabiliza", m.estabiliza),
        ("chega ao alvo", tempo_do_alvo),
    ]


def _caminho_ate_o_regime(r: ct.ResultadoDoCalor, energia: np.ndarray) -> np.ndarray | None:
    final = r.energia_final()
    if final is None or abs(final) < 1e-9:
        return None
    return np.clip(energia / final * 100.0, -999.0, 999.0)


def cena_da_peca(
    r: ct.ResultadoDoCalor, alvo: float | None = None, ponto_do_alvo: ct.Ponto | None = None
) -> dict[str, Any]:
    p = r.peca
    tempos = tempos_dos_quadros(r.duracao)
    nos = reamostrar(r.tempos, r.temperaturas, tempos)  # quadros × nós
    energia = reamostrar(r.tempos, r.energia(), tempos)
    q_a, q_b = ct.fluxos_nas_faces(r)
    q_a = np.interp(tempos, r.tempos, q_a) / 1000.0  # kW/m²
    q_b = np.interp(tempos, r.tempos, q_b) / 1000.0
    referencia = max(float(np.max(np.abs(q_a))), float(np.max(np.abs(q_b))), 1e-9)
    lo, hi = _faixa_de_temperatura(nos, _temperaturas_das_faces(p), r.permanente)
    cena = Cena(tempos, id=f"peca-{hash((p, round(r.duracao, 6))) & 0xFFFFFFFF:x}", altura=330)
    esc = cena.escala("Temperatura", "°C", lo, hi, cores=CALOR, casas=1)
    canais_nos = cena.canais(nos)
    k_qa, k_qb = cena.canal(q_a), cena.canal(q_b)
    pos = r.posicoes_mm
    bordas = np.linspace(pos[0], pos[-1], _FAIXAS + 1)
    meios = (bordas[:-1] + bordas[1:]) / 2.0
    faixas = np.stack([np.interp(meios, pos, nos[q]) for q in range(len(tempos))])
    canais_faixas = cena.canais(faixas)
    caminho = _caminho_ate_o_regime(r, energia)
    if p.forma == ct.PAREDE:
        _desenhar_parede(cena, r, esc, canais_faixas, bordas, k_qa, k_qb, referencia)
    else:
        _desenhar_redondo(cena, r, esc, canais_faixas, bordas, k_qa, k_qb, referencia)
    if caminho is not None:
        x0, y0, x1, y1 = cena.vista or (0, 0, 1, 1)
        cena.texto(
            (x0 + x1) / 2,
            y0,
            "caminho até o regime permanente: {} %",
            canal=cena.canal(caminho),
            casas=0,
            base="bottom",
            tamanho=11,
            dy=-2,
        )
    # gráficos
    m = ct.marcos(r)
    tempo_do_alvo = (
        r.tempo_para(ponto_do_alvo, alvo)
        if (alvo is not None and ponto_do_alvo is not None)
        else None
    )
    series = [(ponto.nome, canais_nos[ponto.indice]) for ponto in r.pontos]
    limites = [("alvo", alvo)] if alvo is not None else []
    cena.grafico_no_tempo(
        "Temperatura nos pontos",
        "°C",
        series,
        limites=limites,
        marcos=marcos_do_calor(m, tempo_do_alvo),
    )
    rotulo = "posição na espessura (mm)" if p.forma == ct.PAREDE else "raio (mm)"
    fixas = [("No começo", np.full(len(pos), p.t_inicial))]
    if r.permanente is not None:
        fixas.append(("Regime permanente", r.permanente))
    cena.grafico_de_perfil(
        "Temperatura ao longo da espessura",
        "°C",
        pos,
        canais_nos,
        rotulo_x=rotulo,
        rotulo_curto="posição (mm)" if p.forma == ct.PAREDE else "r (mm)",
        fixas=fixas,
        faixa=(lo - 0.04 * (hi - lo), hi + 0.04 * (hi - lo)),
    )
    diferenca = nos.max(axis=1) - nos.min(axis=1)
    cena.grafico_no_tempo(
        "Diferença dentro da peça (mais quente − mais fria)",
        "°C",
        [("Diferença", cena.canal(diferenca))],
        marcos=[("maior", m.quando_maior), ("equaliza", m.equaliza)],
    )
    unidade = {"J/m²": "kJ/m²", "J/m": "kJ/m", "J": "kJ"}[p.unidade_de_calor]
    k_energia = cena.canal(energia / 1000.0)
    cena.grafico_no_tempo(
        "Calor guardado na peça desde o começo",
        unidade,
        [("Calor guardado", k_energia)],
        casas=1,
        marcos=[("estabiliza", m.estabiliza)],
    )
    cena.nota = NOTA_DAS_SETAS + " Clique num gráfico no tempo para ir àquele instante."
    return cena.como_dados()


def _setas_de_calor(
    cena: Cena,
    face: ct.Face,
    canal: int,
    referencia: float,
    pontos: list[tuple[float, float, float, float]],
    comprimento: float,
) -> None:
    """Setas na face (x, y, normal para fora): o calor que entra chega na face, o que sai parte
    dela. Só a do meio leva o rótulo."""
    if face.tipo == ct.ISOLADA:
        return
    meio = len(pontos) // 2
    for k, (x, y, nx, ny) in enumerate(pontos):
        cena.seta(
            x, y, nx, ny, comprimento=comprimento, canal=canal, ref=referencia, chega=True, cor=COR_CALOR,
            rotulo="{} kW/m²" if k == meio else "", casas=2,
        )  # fmt: skip


def _marcar_pontos(
    cena: Cena, r: ct.ResultadoDoCalor, posicoes: list[tuple[float, float]], abaixo: float
) -> None:
    """Bolinhas nos três pontos das curvas, na cor de cada curva, com o nome embaixo: o primeiro
    para a esquerda, o do meio um pouco mais baixo e o último para a direita."""
    for k, (ponto, (x, y)) in enumerate(zip(r.pontos, posicoes, strict=True)):
        cena.circulo(
            x,
            y,
            raio_px=5,
            cor=CORES_DOS_PONTOS[k],
            contorno="#ffffff",
            espessura=1.5,
            nome=ponto.nome,
        )
    nomes = [ponto.nome for ponto in r.pontos]
    (xa, _), (xm, _), (xb, _) = posicoes
    cena.texto(
        xa, abaixo, nomes[0], ancora="end", base="top", tamanho=10, cor=CORES_DOS_PONTOS[0], dx=4
    )
    cena.texto(xm, abaixo, nomes[1], base="top", tamanho=10, cor=CORES_DOS_PONTOS[1], dy=13)
    cena.texto(
        xb, abaixo, nomes[2], ancora="start", base="top", tamanho=10, cor=CORES_DOS_PONTOS[2], dx=-4
    )


def _desenhar_parede(
    cena: Cena,
    r: ct.ResultadoDoCalor,
    esc: int,
    faixas: list[int],
    bordas: np.ndarray,
    k_qa: int,
    k_qb: int,
    referencia: float,
) -> None:
    p = r.peca
    e = p.espessura_mm
    altura = 1.15 * e
    lateral = 0.6 * e
    for face, x0, x1 in ((p.face_a, -lateral, 0.0), (p.face_b, e, e + lateral)):
        if face.tipo == ct.CONVECCAO:
            cena.retangulo(
                x0, 0, x1, altura, escala=esc, canal=cena.canal(face.t_fluido), nome="Fluido"
            )
    for k in range(_FAIXAS):
        fim = bordas[k + 1] + (0.004 * e if k < _FAIXAS - 1 else 0.0)
        cena.retangulo(bordas[k], 0, fim, altura, escala=esc, canal=faixas[k], nome="Parede")
    cena.retangulo(0, 0, e, altura, vazio=True, contorno="texto", espessura=1.6)
    for face, borda, normal, ancora, x_texto in (
        (p.face_a, 0.0, -1.0, "end", -0.04 * e),
        (p.face_b, e, 1.0, "start", e + 0.04 * e),
    ):
        if face.tipo == ct.ISOLADA:
            largura = 0.1 * e
            a, b = (borda - largura, borda) if normal < 0 else (borda, borda + largura)
            cena.retangulo(
                a, 0, b, altura, cor="#e2e8f0", hachura=True, contorno="texto", espessura=1.0
            )
        elif face.tipo == ct.TEMPERATURA:
            largura = 0.06 * e
            a, b = (borda - largura, borda) if normal < 0 else (borda, borda + largura)
            cena.retangulo(a, 0, b, altura, escala=esc, canal=cena.canal(face.t_fixa), nome="Face")
        cena.texto(
            x_texto, altura * 1.03, _texto_da_face(face), ancora=ancora, base="bottom", tamanho=11
        )
        canal = k_qa if normal < 0 else k_qb
        pontos = [(borda, altura * f, normal, 0.0) for f in (0.22, 0.5, 0.78)]
        _setas_de_calor(cena, face, canal, referencia, pontos, 0.5 * lateral)
    _marcar_pontos(
        cena, r, [(0.0, altura * 0.5), (e / 2, altura * 0.5), (e, altura * 0.5)], -0.05 * e
    )
    cena.cota((0, -0.3 * e), (e, -0.3 * e), f"e = {_N(e, 1)} mm")
    cena.vista = (-lateral - 0.05 * e, -0.52 * e, e + lateral + 0.05 * e, altura + 0.2 * e)


def _desenhar_redondo(
    cena: Cena,
    r: ct.ResultadoDoCalor,
    esc: int,
    faixas: list[int],
    bordas: np.ndarray,
    k_qa: int,
    k_qb: int,
    referencia: float,
) -> None:
    p = r.peca
    raio = p.diametro_mm / 2.0
    raio_i = p.diametro_interno_mm / 2.0
    anel = 0.34 * raio
    if p.face_b.tipo == ct.CONVECCAO:
        cena.poligono(
            _anel(raio + anel, 0.0),
            escala=esc,
            canal=cena.canal(p.face_b.t_fluido),
            nome="Fluido de fora",
        )
    elif p.face_b.tipo == ct.TEMPERATURA:
        cena.poligono(
            _anel(raio * 1.05, 0.0), escala=esc, canal=cena.canal(p.face_b.t_fixa), nome="Face"
        )
    elif p.face_b.tipo == ct.ISOLADA:
        cena.poligono(_anel(raio * 1.12, raio), cor="#e2e8f0", hachura=True)
    for k in reversed(range(_FAIXAS)):
        cena.poligono(_anel(bordas[k + 1], 0.0), escala=esc, canal=faixas[k], nome="Peça")
    if raio_i > 0:
        if p.face_a.tipo == ct.CONVECCAO:
            cena.poligono(
                _anel(raio_i, 0.0),
                escala=esc,
                canal=cena.canal(p.face_a.t_fluido),
                nome="Fluido de dentro",
            )
        elif p.face_a.tipo == ct.ISOLADA:
            cena.poligono(_anel(raio_i, 0.0), cor="#e2e8f0", hachura=True)
        else:
            cena.poligono(_anel(raio_i, 0.0), cor="fundo")
        cena.poligono(_anel(raio_i, 0.0), vazio=True, contorno="texto", espessura=1.4)
    cena.poligono(_anel(raio, 0.0), vazio=True, contorno="texto", espessura=1.6)
    angulos = np.radians([30, 90, 150, 210, 270, 330])
    fora = [(raio * math.cos(a), raio * math.sin(a), math.cos(a), math.sin(a)) for a in angulos]
    # a do meio da lista leva o rótulo: a de 210°, embaixo à esquerda, longe do texto de cima
    _setas_de_calor(cena, p.face_b, k_qb, referencia, fora, 0.3 * raio)
    if raio_i > 0:
        dentro = [
            (raio_i * math.cos(a), raio_i * math.sin(a), -math.cos(a), -math.sin(a))
            for a in np.radians([45, 135, 225, 315])
        ]
        _setas_de_calor(cena, p.face_a, k_qa, referencia, dentro, 0.7 * raio_i)
    # o raio onde ficam os três pontos
    cena.linha([(raio_i, 0.0), (raio, 0.0)], largura=1.2, cor="#475569", tracejado=True)
    posicoes = [(float(r.r[pt.indice] * 1000.0), 0.0) for pt in r.pontos]
    _marcar_pontos(cena, r, posicoes, -0.06 * raio)
    extensao = raio + anel + 0.25 * raio
    cena.texto(
        0.0,
        raio + anel + 0.08 * raio,
        f"de fora: {_texto_da_face(p.face_b)}",
        base="bottom",
        tamanho=11,
    )
    if raio_i > 0:
        cena.texto(0.0, -raio_i * 0.35, f"de dentro: {_texto_da_face(p.face_a)}", tamanho=10)
    cota_y = -raio - anel - 0.12 * raio
    diametro = f"Ø {_N(p.diametro_mm, 1)} mm" + (
        f" × Ø {_N(p.diametro_interno_mm, 1)} mm" if raio_i > 0 else ""
    )
    cena.cota(
        (-raio, cota_y),
        (raio, cota_y),
        diametro + (" (esfera: corte pelo centro)" if p.forma == ct.ESFERA else ""),
    )
    cena.vista = (-extensao, -extensao - 0.22 * raio, extensao, extensao + 0.05 * raio)


def _anel(r_fora: float, r_dentro: float, lados: int = 96) -> list[tuple[float, float]]:
    angulo = np.linspace(0.0, 2.0 * math.pi, lados, endpoint=False)
    fora = [(r_fora * math.cos(a), r_fora * math.sin(a)) for a in angulo]
    if r_dentro <= 0:
        return fora
    dentro = [(r_dentro * math.cos(a), r_dentro * math.sin(a)) for a in angulo[::-1]]
    return [*fora, fora[0], dentro[-1], *dentro]


def instantes_do_memorial(duracao: float) -> list[float]:
    return [0.0, duracao * 0.1, duracao * 0.3, duracao]


def figuras_da_peca(r: ct.ResultadoDoCalor, alvo: float | None = None) -> list[dict[str, Any]]:
    """Dados das figuras do memorial: as temperaturas no tempo e o perfil em alguns instantes."""
    u = unidade_de_tempo(r.duracao)
    amostra = np.linspace(0.0, r.duracao, 121)
    series = [
        fnt.Serie(
            ponto.nome,
            tuple(amostra / u.fator),
            tuple(np.interp(amostra, r.tempos, r.serie(ponto))),
        )
        for ponto in r.pontos
    ]
    limites = [("alvo", float(alvo))] if alvo is not None else []
    rotulo = "posição na espessura (mm)" if r.peca.forma == ct.PAREDE else "raio (mm)"
    perfis = []
    for t in instantes_do_memorial(r.duracao):
        i = int(round(t / r.duracao * (len(r.tempos) - 1)))
        perfis.append(
            fnt.Serie(f"t = {tempo_em_texto(t, u)}", tuple(r.posicoes_mm), tuple(r.temperaturas[i]))
        )
    if r.permanente is not None:
        perfis.append(
            fnt.Serie(
                "regime permanente", tuple(r.posicoes_mm), tuple(r.permanente), tracejada=True
            )
        )
    m = ct.marcos(r)
    marcos = [(nome, None if t is None else t / u.fator) for nome, t in marcos_do_calor(m, None)]
    diferenca = r.temperaturas.max(axis=1) - r.temperaturas.min(axis=1)
    return [
        fnt.linhas_para_o_registro(
            "Temperatura nos pontos da peça",
            "Temperatura no tempo nos pontos da peça, com os instantes em que ela equaliza e "
            "estabiliza.",
            f"tempo ({u.rotulo})",
            "°C",
            series,
            limites,
            marcos,
        ),
        fnt.linhas_para_o_registro(
            "Diferença dentro da peça",
            "Diferença entre o ponto mais quente e o mais frio da peça no tempo.",
            f"tempo ({u.rotulo})",
            "°C",
            [
                fnt.Serie(
                    "Diferença",
                    tuple(amostra / u.fator),
                    tuple(np.interp(amostra, r.tempos, diferenca)),
                )
            ],
            marcos=[("maior", m.quando_maior / u.fator)],
        ),
        fnt.linhas_para_o_registro(
            "Temperatura ao longo da espessura",
            "Perfil de temperatura na espessura em alguns instantes.",
            rotulo,
            "°C",
            perfis,
        ),
    ]


def descricao_da_peca(p: ct.Peca) -> str:
    if p.forma == ct.PAREDE:
        return f"parede plana de {_N(p.espessura_mm, 1)} mm"
    nome = "cilindro" if p.forma == ct.CILINDRO else "esfera"
    if p.macica:
        return (
            f"{nome} maciço de diâmetro {_N(p.diametro_mm, 1)} mm"
            if nome == "cilindro"
            else f"esfera maciça de diâmetro {_N(p.diametro_mm, 1)} mm"
        )
    oco = "tubo" if nome == "cilindro" else "esfera oca"
    return f"{oco} de diâmetro {_N(p.diametro_mm, 1)} × {_N(p.diametro_interno_mm, 1)} mm"


def verificacoes_da_peca(
    r: ct.ResultadoDoCalor, alvo: float | None, ponto: ct.Ponto | None, prazo: float | None
) -> list[Verificacao]:
    """O ponto chega à temperatura pedida dentro do prazo (se houver prazo)."""
    if alvo is None or ponto is None:
        return []
    t = r.tempo_para(ponto, alvo)
    u = unidade_de_tempo(r.duracao)
    if prazo is not None and prazo > 0:
        return [
            Verificacao(
                f"{ponto.nome} chega a {_N(alvo, 1)} °C",
                None if t is None else t / u.fator,
                prazo / u.fator,
                u.rotulo,
                "Tempo para o ponto chegar à temperatura pedida, dentro do prazo",
                "não chega na duração calculada" if t is None else f"t = {tempo_em_texto(t, u)}",
                status="OK" if t is not None and t <= prazo else "NÃO OK",
                tipo="limite",
            )
        ]
    return []


def registro_da_peca(
    r: ct.ResultadoDoCalor,
    *,
    alvo: float | None = None,
    ponto: ct.Ponto | None = None,
    prazo: float | None = None,
    responsavel: str = "",
) -> dict[str, Any]:
    p = r.peca
    u = unidade_de_tempo(r.duracao)
    verificacoes = verificacoes_da_peca(r, alvo, ponto, prazo)
    geral = status_geral(verificacoes) if verificacoes else "OK"
    final = r.temperaturas[-1]
    partes = [
        f"{_maiuscula(descricao_da_peca(p))} em {_minuscula(p.material.nome)}, de {_N(p.t_inicial, 1)} °C,",
        f"em {tempo_em_texto(r.duracao, u)}:",
        ", ".join(f"{pt.nome.lower()} a {_N(final[pt.indice], 1)} °C" for pt in r.pontos) + ".",
    ]
    if alvo is not None and ponto is not None:
        t = r.tempo_para(ponto, alvo)
        partes.append(
            f"{ponto.nome} chega a {_N(alvo, 1)} °C em {tempo_em_texto(t, u)}."
            if t is not None
            else f"{ponto.nome} não chega a {_N(alvo, 1)} °C no tempo calculado."
        )
    destaque = " ".join(partes)
    tabela = [
        [
            tempo_em_texto(float(r.tempos[i]), u),
            *[_N(float(r.temperaturas[i, pt.indice]), 1) for pt in r.pontos],
        ]
        for i in np.linspace(0, len(r.tempos) - 1, 11).round().astype(int)
    ]
    entradas = {
        "forma": p.forma,
        "espessura_mm": numero_json(p.espessura_mm, 4),
        "diametro_mm": numero_json(p.diametro_mm, 4),
        "diametro_interno_mm": numero_json(p.diametro_interno_mm, 4),
        "material": p.material.nome,
        "condutividade_W_mK": numero_json(p.material.condutividade, 5),
        "massa_especifica_kg_m3": numero_json(p.material.massa_especifica, 4),
        "calor_especifico_J_kgK": numero_json(p.material.calor_especifico, 4),
        "temperatura_inicial_C": numero_json(p.t_inicial, 3),
        "face_a": p.face_a.descricao(),
        "face_b": p.face_b.descricao(),
        "duracao_s": numero_json(r.duracao, 3),
    }
    resultados: dict[str, Any] = {
        "status_geral": geral,
        "destaque_memorial": destaque,
        "constante_de_tempo_s": None if r.tau is None else numero_json(r.tau, 3),
        "numero_de_biot": None if r.biot is None else numero_json(r.biot, 4),
        "tabelas_memorial": [
            {
                "legenda": "Temperatura nos pontos da peça ao longo do tempo (°C).",
                "cabecalhos": ["Instante", *[pt.nome for pt in r.pontos]],
                "linhas": tabela,
                "fonte": 8.0,
            }
        ],
        fnt.CHAVE: figuras_da_peca(r, alvo),
    }
    if verificacoes:
        resultados["verificações"] = linhas_para_registro(verificacoes)
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Calor no tempo — {descricao_da_peca(p)}",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas=entradas,
        resultados=resultados,
        metodo=(
            "Condução transiente em uma dimensão (espessura), por volumes finitos com "
            f"{len(r.r)} nós e Crank–Nicolson no tempo, com partida implícita. Conferido com a "
            "solução exata em série nos casos clássicos (parede, cilindro e esfera com convecção)."
        ),
        premissas=ct.hipoteses(r),
        referencias=_REFERENCIAS,
        conclusao=destaque,
        responsavel=responsavel,
    )


# ---------------------------------------------------------------------------------------------
# Seção desenhada
# ---------------------------------------------------------------------------------------------
def _contornos(partes: list[sd.Parte]) -> list[tuple[list[tuple[float, float]], bool]]:
    saida = []
    for parte in partes:
        if parte.forma == sd.CIRC:
            raio = parte.b / 2.0
            angulo = np.linspace(0.0, 2.0 * math.pi, 96, endpoint=False)
            pontos = [(parte.x + raio * math.cos(a), parte.y + raio * math.sin(a)) for a in angulo]
        else:
            pontos = [(float(x), float(y)) for x, y in parte.cantos]
        saida.append((pontos, parte.furo))
    return saida


def _bordas_de_fora(g: cs.GradeDaSecao) -> list[tuple[float, float, float, float]]:
    """Onde o contorno de fora corta as duas retas pelo centro da caixa: a face de fora da última
    célula com material em cada sentido (x, y, normal para fora)."""
    xc = 0.5 * (g.xs[0] + g.xs[-1])
    yc = 0.5 * (g.ys[0] + g.ys[-1])
    i0 = int(np.clip(np.searchsorted(g.xs, xc) - 1, 0, len(g.xs) - 2))
    j0 = int(np.clip(np.searchsorted(g.ys, yc) - 1, 0, len(g.ys) - 2))
    saida: list[tuple[float, float, float, float]] = []
    coluna = np.nonzero(g.ativa[:, j0])[0]
    if len(coluna):
        saida += [
            (float(g.xs[coluna[-1] + 1]), yc, 1.0, 0.0),
            (float(g.xs[coluna[0]]), yc, -1.0, 0.0),
        ]
    linha = np.nonzero(g.ativa[i0, :])[0]
    if len(linha):
        saida += [
            (xc, float(g.ys[linha[-1] + 1]), 0.0, 1.0),
            (xc, float(g.ys[linha[0]]), 0.0, -1.0),
        ]
    return saida


def _bordas_dos_furos(partes: list[sd.Parte]) -> list[tuple[float, float, float, float]]:
    """Pontos no contorno de cada furo, com a normal apontando para o meio do furo."""
    saida: list[tuple[float, float, float, float]] = []
    for parte in partes:
        if not parte.furo:
            continue
        x0, y0, x1, y1 = parte.caixa()
        xc, yc = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        meia_x, meia_y = 0.5 * (x1 - x0), 0.5 * (y1 - y0)
        for a in (45.0, 135.0, 225.0, 315.0):
            c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
            if parte.forma == sd.CIRC:
                x, y = xc + meia_x * c, yc + meia_y * s
            else:
                fator = min(meia_x / max(abs(c), 1e-9), meia_y / max(abs(s), 1e-9))
                x, y = xc + fator * c, yc + fator * s
            saida.append((x, y, -c, -s))
    return saida


def cena_da_secao(
    r: cs.ResultadoDaSecao,
    partes: list[sd.Parte],
    alvo: float | None = None,
    *,
    identificador: str = "",
) -> dict[str, Any]:
    g = r.grade
    tempos = r.tempos_dos_quadros
    faces = [r.t_inicial]
    for face in (r.fora, r.furos):
        if face.tipo == ct.CONVECCAO:
            faces.append(face.t_fluido)
        elif face.tipo == ct.TEMPERATURA:
            faces.append(face.t_fixa)
    lo, hi = _faixa_de_temperatura(r.quadros, faces)
    cena = Cena(
        tempos, id=identificador or f"secao-{len(g.xs)}x{len(g.ys)}-{r.duracao:.6g}", altura=380
    )
    esc = cena.escala("Temperatura", "°C", lo, hi, cores=CALOR, casas=1)
    x0, x1 = float(g.xs[0]), float(g.xs[-1])
    y0, y1 = float(g.ys[0]), float(g.ys[-1])
    tamanho = max(x1 - x0, y1 - y0)
    folga = 0.22 * tamanho
    vista = (x0 - folga, y0 - folga, x1 + folga, y1 + folga)
    # o fluido em volta e o dos furos, atrás da grade
    if r.fora.tipo == ct.CONVECCAO:
        cena.retangulo(
            vista[0],
            vista[1],
            vista[2],
            vista[3],
            escala=esc,
            canal=cena.canal(r.fora.t_fluido),
            nome="Fluido de fora",
            atras=True,
        )
    contornos = _contornos(partes)
    if r.furos.tipo == ct.CONVECCAO and g.tem_furo:
        k_furo = cena.canal(r.furos.t_fluido)
        for pontos, furo in contornos:
            if furo:
                cena.poligono(pontos, escala=esc, canal=k_furo, nome="Fluido do furo", atras=True)
    cena.grade(g.xs, g.ys, g.indices_ativos, r.quadros, esc, nome="Temperatura")
    for pontos, furo in contornos:
        cena.poligono(pontos, vazio=True, contorno="texto", espessura=1.0 if furo else 1.4)
    # setas do calor que entra ou sai em média pelos contornos
    q_fora = np.interp(
        tempos, r.tempos, r.calor_fora if r.calor_fora is not None else np.zeros(len(r.tempos))
    )
    q_furos = np.interp(
        tempos, r.tempos, r.calor_furos if r.calor_furos is not None else np.zeros(len(r.tempos))
    )
    q_fora = q_fora / max(g.contorno_fora_mm / 1000.0, 1e-12) / 1000.0  # kW/m²
    q_furos = (
        q_furos / max(g.contorno_furos_mm / 1000.0, 1e-12) / 1000.0
        if g.tem_furo
        else np.zeros(len(tempos))
    )
    # cada contorno com a sua escala: o de fora troca bem menos que o furo com líquido, e a seta
    # dele sumiria; o valor escrito na seta diz o tamanho de cada um
    _setas_de_calor(
        cena,
        r.fora,
        cena.canal(q_fora),
        max(float(np.max(np.abs(q_fora))), 1e-9),
        _bordas_de_fora(g),
        0.16 * tamanho,
    )
    if g.tem_furo:
        _setas_de_calor(
            cena,
            r.furos,
            cena.canal(q_furos),
            max(float(np.max(np.abs(q_furos))), 1e-9),
            _bordas_dos_furos(partes),
            0.07 * tamanho,
        )
    cena.texto(
        vista[0] + 0.02 * tamanho,
        vista[3] - 0.02 * tamanho,
        f"de fora: {_texto_da_face(r.fora)}",
        ancora="start",
        base="top",
        tamanho=11,
    )
    if g.tem_furo:
        cena.texto(
            vista[0] + 0.02 * tamanho,
            vista[3] - 0.02 * tamanho,
            f"nos furos: {_texto_da_face(r.furos)}",
            ancora="start",
            base="top",
            tamanho=11,
            dy=16,
        )
    cena.cota((x0, y0 - 0.08 * tamanho), (x1, y0 - 0.08 * tamanho), f"{_N(x1 - x0, 1)} mm")
    cena.cota((x1 + 0.08 * tamanho, y0), (x1 + 0.08 * tamanho, y1), f"{_N(y1 - y0, 1)} mm")
    cena.vista = vista
    m = cs.marcos(r)
    tempo_do_alvo = None
    if alvo is not None:
        tempo_do_alvo = r.tempo_para("max" if r.t_inicial > alvo else "min", alvo)
    k_max = cena.canal(np.interp(tempos, r.tempos, r.maxima))
    k_med = cena.canal(np.interp(tempos, r.tempos, r.media))
    k_min = cena.canal(np.interp(tempos, r.tempos, r.minima))
    limites = [("alvo", alvo)] if alvo is not None else []
    cena.grafico_no_tempo(
        "Temperatura na seção",
        "°C",
        [("Ponto mais quente", k_max), ("Média", k_med), ("Ponto mais frio", k_min)],
        limites=limites,
        marcos=[
            ("equaliza", m.equaliza),
            ("estabiliza", m.estabiliza),
            ("seção inteira no alvo", tempo_do_alvo),
        ],
    )
    cena.grafico_no_tempo(
        "Diferença dentro da seção (mais quente − mais fria)",
        "°C",
        [("Diferença", cena.canal(np.interp(tempos, r.tempos, r.maxima - r.minima)))],
        marcos=[("maior", m.quando_maior), ("equaliza", m.equaliza)],
    )
    calores = [("Contorno de fora", cena.canal(q_fora))]
    if g.tem_furo:
        calores.append(("Furos", cena.canal(q_furos)))
    cena.grafico_no_tempo("Calor que entra pelo contorno (média)", "kW/m²", calores, casas=2)
    cena.nota = (
        NOTA_DAS_SETAS.split(" Bolinhas")[0] + " Passe o mouse na seção para ler a temperatura."
    )
    return cena.como_dados()


def figuras_da_secao(r: cs.ResultadoDaSecao, alvo: float | None = None) -> list[dict[str, Any]]:
    u = unidade_de_tempo(r.duracao)
    amostra = np.linspace(0.0, r.duracao, 121)
    x = tuple(amostra / u.fator)
    series = [
        fnt.Serie("Ponto mais quente", x, tuple(np.interp(amostra, r.tempos, r.maxima))),
        fnt.Serie("Média", x, tuple(np.interp(amostra, r.tempos, r.media))),
        fnt.Serie("Ponto mais frio", x, tuple(np.interp(amostra, r.tempos, r.minima))),
    ]
    limites = [("alvo", float(alvo))] if alvo is not None else []
    g = r.grade
    quadros = []
    for t in instantes_do_memorial(r.duracao):
        k = int(round(t / r.duracao * (len(r.tempos_dos_quadros) - 1)))
        quadros.append((f"t = {tempo_em_texto(float(r.tempos_dos_quadros[k]), u)}", r.quadros[k]))
    lo, hi = _faixa_de_temperatura(r.quadros)
    m = cs.marcos(r)
    marcos = [(nome, None if t is None else t / u.fator) for nome, t in marcos_do_calor(m, None)]
    return [
        fnt.linhas_para_o_registro(
            "Temperatura na seção",
            "Temperatura no tempo: ponto mais quente, média e ponto mais frio da seção, com os "
            "instantes em que ela equaliza e estabiliza.",
            f"tempo ({u.rotulo})",
            "°C",
            series,
            limites,
            marcos,
        ),
        fnt.mapas_para_o_registro(
            "Temperatura na seção em alguns instantes",
            "Distribuição de temperatura na seção em alguns instantes.",
            g.xs,
            g.ys,
            g.indices_ativos,
            quadros,
            lo,
            hi,
            "°C",
        ),
    ]


def registro_da_secao(
    r: cs.ResultadoDaSecao,
    nome_da_secao: str,
    *,
    alvo: float | None = None,
    responsavel: str = "",
) -> dict[str, Any]:
    u = unidade_de_tempo(r.duracao)
    g = r.grade
    destaque = (
        f"Seção {nome_da_secao} em {_minuscula(r.material.nome)}, de {_N(r.t_inicial, 1)} °C, em "
        f"{tempo_em_texto(r.duracao, u)}: ponto mais quente a {_N(float(r.maxima[-1]), 1)} °C, "
        f"média a {_N(float(r.media[-1]), 1)} °C e ponto mais frio a {_N(float(r.minima[-1]), 1)} °C."
    )
    if alvo is not None:
        quente = r.t_inicial > alvo
        qual = "max" if quente else "min"
        t = r.tempo_para(qual, alvo)
        nome = "o ponto mais quente" if quente else "o ponto mais frio"
        destaque += (
            f" A seção inteira passa de {_N(alvo, 1)} °C ({nome} chega lá) em {tempo_em_texto(t, u)}."
            if t is not None
            else f" A seção inteira não chega a {_N(alvo, 1)} °C no tempo calculado."
        )
    tabela = [
        [
            tempo_em_texto(float(r.tempos[i]), u),
            _N(float(r.maxima[i]), 1),
            _N(float(r.media[i]), 1),
            _N(float(r.minima[i]), 1),
        ]
        for i in np.linspace(0, len(r.tempos) - 1, 11).round().astype(int)
    ]
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Calor no tempo — seção {nome_da_secao}",
        status=STATUS_REGISTRO.get("OK", "Pendente"),
        resumo=destaque,
        entradas={
            "secao": nome_da_secao,
            "area_mm2": numero_json(g.area_mm2, 3),
            "material": r.material.nome,
            "condutividade_W_mK": numero_json(r.material.condutividade, 5),
            "massa_especifica_kg_m3": numero_json(r.material.massa_especifica, 4),
            "calor_especifico_J_kgK": numero_json(r.material.calor_especifico, 4),
            "temperatura_inicial_C": numero_json(r.t_inicial, 3),
            "contorno_de_fora": r.fora.descricao(),
            "contorno_dos_furos": r.furos.descricao() if g.tem_furo else "sem furo",
            "duracao_s": numero_json(r.duracao, 3),
        },
        resultados={
            "status_geral": "OK",
            "destaque_memorial": destaque,
            "constante_de_tempo_s": None if r.tau is None else numero_json(r.tau, 3),
            "tabelas_memorial": [
                {
                    "legenda": "Temperatura na seção ao longo do tempo (°C).",
                    "cabecalhos": ["Instante", "Mais quente", "Média", "Mais fria"],
                    "linhas": tabela,
                    "fonte": 8.0,
                }
            ],
            fnt.CHAVE: figuras_da_secao(r, alvo),
        },
        metodo=(
            "Condução transiente em duas dimensões na seção, por volumes finitos numa grade de "
            f"{int(g.ativa.sum())} células, com o contorno curvo corrigido para o comprimento de "
            "verdade, e Crank–Nicolson no tempo com partida implícita."
        ),
        premissas=cs.hipoteses(r),
        referencias=_REFERENCIAS,
        conclusao=destaque,
        responsavel=responsavel,
    )
