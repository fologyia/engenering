"""Perfil soldado em todo o contorno (W/HP/I, U e cantoneira): contas conferidas à mão."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core import ligacao_contorno as lc
from core import ligacoes as lg
from core import soldas as sd

BASE = lc.EntradaPerfilNoContorno()
CANTONEIRA = lc.perfis_da_forma(lc.FORMA_L)[18]  # L 2" × 1/4"


def _so(e: lc.EntradaPerfilNoContorno, **esforcos: float) -> lc.EntradaPerfilNoContorno:
    zeros = dict(
        n_sd_kN=0.0, vx_sd_kN=0.0, vy_sd_kN=0.0, mx_sd_kNm=0.0, my_sd_kNm=0.0, t_sd_kNm=0.0
    )
    return replace(e, **{**zeros, **esforcos})


def _linha(r, inicio: str):
    return next(v for v in r.verificacoes if v.nome.startswith(inicio))


def test_contorno_do_w_a_mao():
    s = lc.secao(BASE)  # W 250 x 32,7: d 258, b_f 146, t_w 6,1, t_f 9,1 (raio = t_f)
    d, bf, tw, tf = 258.0, 146.0, 6.1, 9.1
    esperado = 2 * bf + 4 * tf + 4 * (bf / 2 - tw / 2 - tf) + 2 * (d - 2 * tf - 2 * tf)
    assert sum(t.comprimento for t in s.trechos) == pytest.approx(esperado)
    assert len(s.trechos) == 12
    g = lc.propriedades(s.trechos)
    assert g.x_c == pytest.approx(0.0, abs=1e-9) and g.y_c == pytest.approx(0.0, abs=1e-9)
    assert g.i_xy == pytest.approx(0.0, abs=1e-6)
    # I_x das linhas: mesas por fora (y = d/2) e por dentro (y = d/2 − t_f), pontas e alma
    meio = d / 2 - 2 * tf
    i_x = (
        2 * bf * (d / 2) ** 2
        + 4 * (bf / 2 - tw / 2 - tf) * (d / 2 - tf) ** 2
        + 4 * tf * ((d / 2) ** 2 + (d / 2) * (d / 2 - tf) + (d / 2 - tf) ** 2) / 3
        + 2 * (2 * meio) ** 3 / 12
    )
    assert g.i_x == pytest.approx(i_x)


def test_so_tracao_e_uniforme():
    r = lc.calcular(_so(BASE, n_sd_kN=100.0))
    assert r.grandezas["f_r_kN_mm"] == pytest.approx(100.0 / r.grandezas["comprimento_total_mm"])


def test_so_momento_no_w_a_mao():
    e = _so(BASE, mx_sd_kNm=20.0)
    r = lc.calcular(e)
    g = lc.propriedades(lc.secao(e).trechos)
    assert r.grandezas["f_r_kN_mm"] == pytest.approx(20e6 * 129.0 / g.i_x / 1000)
    assert abs(r.grandezas["y_critico_mm"]) == pytest.approx(129.0)


def test_compressao_por_contato_nao_vai_a_solda():
    comprimida = _so(BASE, n_sd_kN=-300.0)
    assert lc.calcular(comprimida).grandezas["f_r_kN_mm"] > 0
    com_contato = lc.calcular(replace(comprimida, contato=True))
    assert com_contato.grandezas["f_r_kN_mm"] == pytest.approx(0.0, abs=1e-12)
    assert "J1.4" in _linha(com_contato, "Solda: filete").formula


@pytest.mark.parametrize(
    ("forma", "perfil"),
    [(lc.FORMA_I, "W 250 x 32,7"), (lc.FORMA_U, 'U 6" x 12,20'), (lc.FORMA_L, CANTONEIRA)],
)
def test_as_forcas_nos_filetes_devolvem_os_esforcos(forma, perfil):
    """∫f ds sobre o contorno = N, V_x, V_y, M_x, M_y e T aplicados no centro da seção."""
    e = replace(
        BASE, forma=forma, perfil=perfil, n_sd_kN=12.0, vx_sd_kN=-3.0, vy_sd_kN=5.0,
        mx_sd_kNm=0.4, my_sd_kNm=-0.25, t_sd_kNm=0.15,
    )  # fmt: skip
    s = lc.secao(e)
    g = lc.propriedades(s.trechos)
    f = lc.esforcos_no_grupo(e, g)
    soma = dict.fromkeys(("n", "vx", "vy", "mx", "my", "t"), 0.0)
    det = g.i_x * g.i_y - g.i_xy**2
    a = (f.my * g.i_x - f.mx * g.i_xy) / det
    b = (f.mx * g.i_y - f.my * g.i_xy) / det
    for t in s.trechos:
        n = 400
        for k in range(n):
            u = (k + 0.5) / n
            x, y = t.x1 + (t.x2 - t.x1) * u, t.y1 + (t.y2 - t.y1) * u
            ds = t.comprimento / n
            f_n = f.n / g.comprimento + a * (x - g.x_c) + b * (y - g.y_c)  # com sinal
            p = lc.forca_no_ponto(g, f, x, y, t, contato=False)
            soma["n"] += f_n * ds
            soma["mx"] += f_n * y * ds
            soma["my"] += f_n * x * ds
            soma["vx"] += p.f_vx * ds
            soma["vy"] += p.f_vy * ds
            soma["t"] += (x * p.f_vy - y * p.f_vx) * ds
    assert soma["n"] / 1e3 == pytest.approx(12.0, abs=1e-6)
    assert soma["vx"] / 1e3 == pytest.approx(-3.0, rel=1e-6)
    assert soma["vy"] / 1e3 == pytest.approx(5.0, rel=1e-6)
    assert soma["mx"] / 1e6 == pytest.approx(0.4, rel=1e-4)
    assert soma["my"] / 1e6 == pytest.approx(-0.25, rel=1e-4)
    assert soma["t"] / 1e6 == pytest.approx(0.15, rel=1e-4)


def test_u_e_cantoneira_tem_centro_do_grupo_fora_do_centro_da_secao():
    u = lc.propriedades(lc.secao(replace(BASE, forma=lc.FORMA_U, perfil='U 6" x 12,20')).trechos)
    assert abs(u.x_c) > 0.1 and u.y_c == pytest.approx(0.0, abs=1e-9)
    l_ = lc.propriedades(lc.secao(replace(BASE, forma=lc.FORMA_L, perfil=CANTONEIRA)).trechos)
    assert l_.x_c == pytest.approx(l_.y_c) and l_.i_xy < 0  # simétrica pela diagonal


def test_perna_automatica_e_a_menor_comercial_que_passa():
    r = lc.calcular(replace(BASE, mx_sd_kNm=40.0))
    perna = r.grandezas["perna_mm"]
    c = sd.coeficientes(BASE.combinacao)
    r_mm = sd.resistencia_filete_por_mm(perna, 485.0, c.w2)
    assert r.grandezas["f_r_kN_mm"] <= r_mm
    anterior = max(p for p in lc.PERNAS_COMERCIAIS if p < perna)
    assert r.grandezas["f_r_kN_mm"] > sd.resistencia_filete_por_mm(anterior, 485.0, c.w2)
    assert r.adotada.perna_mm == perna
    assert _linha(r, "Solda: filete").status == "OK"


def test_perna_informada_e_limites():
    r = lc.calcular(replace(BASE, perna_mm=10.0))  # t_f = 9,1 → máximo 7,6 mm na ponta
    maxima = _linha(r, "Solda: perna máxima na ponta da mesa")
    assert maxima.status == "NÃO OK" and maxima.resistente == pytest.approx(9.1 - 1.5)
    minima = _linha(r, "Solda: perna mínima")
    assert minima.solicitante == sd.perna_minima(6.1)
    r08 = lc.calcular(replace(BASE, perna_mm=3.0, norma=sd.NBR_2008))
    assert "2008" in _linha(r08, "Solda: filete").referencia


def test_metal_base_do_perfil_a_mao():
    e = _so(BASE, n_sd_kN=200.0, perna_mm=6.0)
    r = lc.calcular(e)
    f_n = 200e3 / r.grandezas["comprimento_total_mm"]
    c = sd.coeficientes(BASE.combinacao)
    # a parede mais fina (alma, 6,1 mm) com A572 Gr 50: f_y = 345 MPa
    esperado = 2 * f_n / (345.0 * 6.1 / c.a1)
    assert _linha(r, "Perfil: metal-base").solicitante == pytest.approx(esperado)


def test_entradas_impossiveis():
    with pytest.raises(lg.LigacaoInvalida):
        lc.calcular(replace(BASE, perfil="W 999 x 1"))
    with pytest.raises(lg.LigacaoInvalida):
        lc.calcular(replace(BASE, forma=lc.FORMA_U))  # um W não é U
    with pytest.raises(lg.LigacaoInvalida):
        lc.calcular(replace(BASE, perna_mm=-1.0))


def test_pelo_modulo_de_ligacoes_figura_registro_e_memorial():
    r = lg.calcular(replace(BASE, forma=lc.FORMA_L, perfil=CANTONEIRA, mx_sd_kNm=0.2))
    assert r.tipo == lg.PERFIL_NO_CONTORNO
    assert lg.figura(r).png
    registro = lg.registro_ligacao(r)
    assert registro["metodo"] == lc.METODO
    assert registro["entradas"]["forma"] == lc.FORMAS[lc.FORMA_L]
    assert registro["entradas"]["perna_mm"] == "automática"
    assert any(nome == "Filete em todo o contorno" for nome, _ in lg.detalhamento_adotado(r))
    grupos = dict(lg.verificacoes_por_grupo(r))
    assert lg.GRUPO_SOLDA in grupos and lg.GRUPO_METAL_BASE in grupos
    assert lg.memorial_da_ligacao(r)[:2] == b"PK"  # Word
    assert lg.memorial_da_ligacao(r, formato="pdf")[:4] == b"%PDF"


def test_sem_esforco_passa_e_nao_quebra():
    r = lc.calcular(_so(BASE))
    assert r.status == "OK" and math.isclose(r.grandezas["f_r_kN_mm"], 0.0, abs_tol=1e-12)
