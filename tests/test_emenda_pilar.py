"""Emenda de pilar com talas parafusadas: caso de validação (±0,5 %), testes extras, o exemplo do
SCI P207 5.4 (só o modelo mecânico) e a página."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components.emenda_pilar_help import AJUDA
from core import emenda_pilar as ep
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/emenda_pilar.py"
P = ep.EntradaEmenda()
TOL = 0.005


def perto(valor: float, esperado: float) -> bool:
    return valor == pytest.approx(esperado, rel=TOL)


@pytest.fixture(scope="module")
def r() -> ep.ResultadoEmenda:
    return ep.calcular(P)


def sd(r, n):
    return ep.verificacao(r, n).solicitante


def rd(r, n):
    return ep.verificacao(r, n).resistente


# ------------------------------------------------------------------ caso de validação (seção 6)
def test_propriedades_e_nc_rd(r):
    assert perto(r.propriedades["Fv_Rd"], 78.86)
    assert perto(r.lambda0, 1.550) and perto(r.chi, 0.365)
    assert perto(r.Nc_Rd, 671.0) and not r.estimativa_invalida
    assert perto(r.propriedades["alfa_f"], 0.381) and r.propriedades["z"] == 192.0


def test_caso_minimo_adota_b(r):
    m = r.minimo
    assert m.adotado == "b"
    assert perto(m.Mb, 12.88) and perto(m.Vb, 10.74)
    assert perto(m.Ffa, 127.9) and perto(m.Ffb, 67.1)
    assert r.casos[-1].origem.endswith("(b)")


def test_esforcos_por_caso(r):
    c1, c2 = r.casos[0], r.casos[1]
    assert perto(c1.Fft, -98.4) and perto(c2.Fft, 160.7)
    assert perto(r.envoltoria["T"], 160.7) and perto(r.envoltoria["Cc"], 358.8)
    assert perto(c2.Rw, 14.21) and perto(c2.Rh, 10.17) and perto(c2.Rv, 9.92)


@pytest.mark.parametrize(
    ("n", "sd_esp", "rd_esp"),
    [
        ("1", 160.7, 315.4),
        ("2", None, 602.5),
        ("3", None, 596.5),
        ("5", None, 568.2),
        ("6", None, 573.0),
        ("7", None, 568.9),
        ("8", None, 643.0),
        ("10", None, 614.6),
        ("11", None, 578.3),
        ("12", 358.8, 1027.2),
        ("14", None, 157.7),
        ("15", None, 85.5),
        ("16", None, 154.6),
        ("17", None, 327.3),
        ("18", None, 297.9),
        ("19", None, 10.46),
    ],
)
def test_verificacoes_do_caso_de_validacao(r, n, sd_esp, rd_esp):
    assert perto(rd(r, n), rd_esp)
    if sd_esp is not None:
        assert perto(sd(r, n), sd_esp)
    assert ep.verificacao(r, n).status == "OK"


def test_governa_o_corte_da_mesa_e_geometria(r):
    assert r.governante.nome.startswith("1.") and perto(r.utilizacao_maxima, 0.51)
    assert perto(r.propriedades["W_net_w"], 46003)
    assert r.propriedades["Lp"] == 310 and r.propriedades["Lw"] == 310
    assert r.total_de_parafusos == 24


def test_nao_aplicaveis_no_padrao(r):
    for n in ("1b", "4", "9", "13", "22"):
        assert ep.verificacao(r, n).status == "N/A", n


def test_continuidade_e_situacao_geral(r):
    area = ep.disposicao(r, "Continuidade: área")
    ext = ep.disposicao(r, "Continuidade: extensão")
    assert area.status == "OK" and area.solicitante == 2500
    assert "2233" in area.formula
    assert ext.status == "ALERTA" and ext.solicitante == 155
    assert [v.nome for v in r.itens_a_verificar] == [ext.nome]
    assert r.situacao == "ATENDE"
    assert r.resumo_da_situacao == "resistência ATENDE; disposições: 1 item(ns) a VERIFICAR"
    assert ep.AVISO_MOMENTO_SEM_ATRITO in r.avisos
    assert r.notas_de_desenho == ep.NOTAS_DE_DESENHO_CONTATO


def test_com_tres_fileiras_a_continuidade_passa():
    r3 = ep.calcular(ep.com(P, nr=3))
    assert ep.disposicao(r3, "Continuidade: extensão").solicitante == 230
    assert not r3.itens_a_verificar


# ------------------------------------------------------------------ testes extras
def test_deslizamento_nao_atende():
    v = ep.verificacao(ep.calcular(ep.com(P, verificar_deslizamento=True)), "13")
    assert perto(v.solicitante, 112.5) and perto(v.resistente, 80.0) and v.status == "NÃO OK"


def test_sem_contato_com_gap_6():
    r6 = ep.calcular(ep.com(P, contato=False, gap=6.0))
    v1 = ep.verificacao(r6, "1")
    assert perto(v1.solicitante, 358.8) and perto(v1.resistente, 315.4)
    assert perto(v1.aproveitamento, 1.14) and v1.status == "NÃO OK"
    assert perto(rd(r6, "9"), 568.2) and perto(rd(r6, "4"), 670.6)
    assert ep.verificacao(r6, "12").status == "N/A"
    assert r6.situacao == "NÃO ATENDE"


def test_enchimento():
    r59 = ep.calcular(ep.com(P, perfil_inferior="W 200 x 59,0 (H)"))
    assert r59.propriedades["tsf"] == pytest.approx(3.5) and r59.propriedades["beta_f"] == 1.0
    assert ep.fator_enchimento(10.0) == pytest.approx(0.943, abs=5e-4)
    with pytest.raises(ValueError, match="6.5.7.2-b"):
        ep.fator_enchimento(20.0)


def test_criterios_do_minimo():
    assert ep.calcular(ep.com(P, criterio_minimo=ep.MINIMO_SO_A)).casos[-1].N == pytest.approx(
        -0.5 * 671.03, rel=TOL
    )
    assert len(ep.calcular(ep.com(P, criterio_minimo=ep.MINIMO_NENHUM)).casos) == 2


def test_nc_informado_e_metade_nas_mesas():
    r = ep.calcular(ep.com(P, Nc_Rd_informado=1000.0, distribuicao=ep.DISTRIBUICAO_METADE))
    assert r.Nc_Rd == 1000.0
    assert r.casos[1].Fft == pytest.approx(25e3 / 192 + 40.0)
    assert r.casos[1].Nw == 0.0


def test_flexao_em_y_ativa_1b_e_aumenta_o_parafuso():
    casos = (ep.CasoEsforco("y", -80.0, 25.0, 20.0, 10.0),)
    r = ep.calcular(ep.com(P, casos=casos, criterio_minimo=ep.MINIMO_NENHUM))
    c = r.casos[0]
    assert c.Mf == 5.0 and c.Ffr > c.Tf / 4
    # dispensada: tala 200 × 12,5 tem mais área e mais módulo que a mesa 203 × 11
    assert ep.verificacao(r, "1b").formula.startswith("dispensada")
    fina = ep.calcular(ep.com(P, casos=casos, criterio_minimo=ep.MINIMO_NENHUM, tp=8.0))
    assert ep.verificacao(fina, "1b").aproveitamento is not None


def test_erros_de_entrada():
    assert ep.validar(ep.com(P, a=7000.0))
    assert ep.validar(ep.com(P, casos=()))
    with pytest.raises(ValueError):
        ep.calcular(ep.com(P, bp=100.0))


T1 = """
W 200 x 15,0       200  100  4.3   5.2   190  170  19.4   1305    87
W 200 x 19,3       203  102  5.8   6.5   190  170  25.1   1686   116
W 200 x 22,5       206  102  6.2   8.0   190  170  29.0   2029   142
W 200 x 26,6       207  133  5.8   8.4   190  170  34.2   2611   330
W 200 x 31,3       210  134  6.4  10.2   190  170  40.3   3168   410
W 200 x 35,9 (H)   201  165  6.2  10.2   181  161  45.7   3437   764
W 200 x 41,7 (H)   205  166  7.2  11.8   181  157  53.5   4114   901
W 200 x 46,1 (H)   203  203  7.2  11.0   181  161  58.6   4543  1535
W 200 x 52,0 (H)   206  204  7.9  12.6   181  157  66.9   5298  1784
HP 200 x 53,0 (H)  204  207 11.3  11.3   181  161  68.1   4977  1673
W 200 x 59,0 (H)   210  205  9.1  14.2   182  158  76.0   6140  2041
W 200 x 71,0 (H)   216  206 10.2  17.4   181  161  91.0   7660  2537
W 200 x 86,0 (H)   222  209 13.0  20.6   181  157 110.9   9498  3139
"""


def _norm(nome: str) -> str:
    return re.sub(r"\s*\(H\)|\*", "", nome).strip()


def test_catalogo_reproduz_a_tabela_t1_do_pedido():
    for linha in T1.strip().splitlines():
        partes = linha.split()
        nome = " ".join(partes[:-9])
        d, bf, tw, tf, h, dl, A, Ix, Iy = map(float, partes[-9:])
        # o catálogo grava alguns nomes com outra grafia ("71,0(H)", "*"): compara normalizado
        p = next(x for x in ep.PERFIS.values() if _norm(x.nome) == _norm(nome))
        assert (p.d, p.bf, p.tw, p.tf, p.h, p.d_linha) == (d, bf, tw, tf, h, dl), nome
        assert p.A == pytest.approx(A * 100, rel=2e-3), nome
        assert p.Ix == pytest.approx(Ix * 1e4, rel=2e-3) and p.Iy == pytest.approx(
            Iy * 1e4, rel=2e-3
        )


def test_familias_w_hp_e_u_do_catalogo():
    w = [p for p in ep.PERFIS.values() if p.familia == ep.FAMILIA_W]
    u = [p for p in ep.PERFIS.values() if p.familia == ep.FAMILIA_U]
    assert len(w) == 106 and len(u) == 12
    assert all(p.d_linha < p.h for p in w)  # d' de core/perfis_gerdau_k.py
    assert ep.PERFIS['U 12" x 37,00'].h == pytest.approx(305.0 - 2 * 12.7)
    assert set(ep.perfis_da_familia(ep.FAMILIA_U)) == {p.nome for p in u}


def test_exportacoes(r):
    texto = ep.csv_completo(r).decode("utf-8-sig")
    assert "Esforços por caso" in texto and "Disposições" in texto
    assert ep.xlsx_completo(r)[:2] == b"PK"


# ------------------------------------------------------------------ talas internas (corte duplo)
@pytest.fixture(scope="module")
def ri() -> ep.ResultadoEmenda:
    return ep.calcular(ep.com(P, talas_internas=True, bi=80.0, ti=12.5))


def test_talas_internas_dobram_o_corte_e_dividem_a_forca(ri):
    p = ri.propriedades
    assert p["n_int"] == 2 and p["fracao_externa"] == pytest.approx(2500 / 4500)
    assert perto(rd(ri, "1"), 2 * 315.4) and perto(sd(ri, "1"), 160.7)
    # a tala externa leva 2500/4500 de T; as internas, o resto
    assert sd(ri, "5") == pytest.approx(160.69 * 2500 / 4500, rel=TOL)
    assert sd(ri, "5i") == pytest.approx(160.69 * 2000 / 4500, rel=TOL)
    assert rd(ri, "5i") == pytest.approx(2 * 80 * 12.5 * 250 / 1.1 / 1000)
    dhn = 20.6375 + 2
    assert rd(ri, "6i") == pytest.approx(
        min(2 * (80 - dhn) * 12.5, 0.85 * 2000) * 400 / 1.35 / 1000
    )
    # contato nas internas: a mesma conta da externa, com t_i (as duas talas somam n_l linhas)
    assert rd(ri, "2i") == pytest.approx(rd(ri, "2"))
    # rasgamento até as bordas de cada interna: e_2 externa = e_2c, interna = b_i − e_2c
    e2c, e2i = 46.5, 80 - 46.5
    L = 40 + 75
    Agv = 2 * 2 * L * 12.5
    Anv = Agv - 2 * 2 * 1.5 * dhn * 12.5
    Ant = 2 * (e2c + e2i - dhn) * 12.5
    duas_bordas = min(0.6 * 400 * Anv + 400 * Ant, 0.6 * 250 * Agv + 400 * Ant) / 1.35 / 1000
    # bloco em L (um plano, tração até a borda mais próxima, e_2i = 33,5 mm), em cada tala
    Agv1 = L * 12.5
    Anv1 = Agv1 - 1.5 * dhn * 12.5
    Ant1 = (e2i - 0.5 * dhn) * 12.5
    em_l = min(0.6 * 400 * Anv1 + 400 * Ant1, 0.6 * 250 * Agv1 + 400 * Ant1) / 1.35 / 1000
    assert rd(ri, "7i") == pytest.approx(2 * min(duas_bordas / 2, em_l))
    assert rd(ri, "7i") == pytest.approx(2 * em_l)
    assert ep.verificacao(ri, "8i").status == "N/A"  # uma linha por tala interna
    assert ri.situacao == "ATENDE"


def test_talas_internas_deslizamento_com_dois_planos():
    r = ep.calcular(ep.com(P, talas_internas=True, verificar_deslizamento=True))
    assert perto(rd(r, "13"), 160.0)


def test_talas_internas_disposicoes():
    r = ep.calcular(ep.com(P, talas_internas=True, bi=95.0, ti=6.3))
    assert ep.disposicao(r, "Largura das talas internas").status == "ALERTA"  # > 87,9 mm
    assert ep.disposicao(r, "Espessura das talas internas").status == "ALERTA"
    assert ep.validar(ep.com(P, talas_internas=True, nl=3))  # W precisa de n_l par


def test_sem_talas_internas_as_linhas_i_ficam_n_a(r):
    for n in ("2i", "4i", "5i", "6i", "7i", "8i", "9i"):
        assert ep.verificacao(r, n).status == "N/A", n


# ------------------------------------------------------------------ perfil U
U = ep.com(
    P,
    perfil_superior='U 12" x 37,00',
    perfil_inferior='U 12" x 37,00',
    bp=77.0,
    tp=9.5,
    nl=1,
    nr=2,
    x1_u=45.0,
    raio_u=12.0,
    Nc_Rd_informado=400.0,
    casos=(
        ep.CasoEsforco("Caso 1", 200.0, 10.0, 10.0),
        ep.CasoEsforco("Caso 2", -40.0, 10.0, 10.0),
    ),
)


def test_u_geometria_e_bloco_da_mesa():
    r = ep.calcular(U)
    p = r.propriedades
    assert p["e2c"] == pytest.approx(77 - 45)
    assert p["e2_lado_alma"] == 45 and p["folga"] == pytest.approx(45 - 9.8 - 12)
    dhn = 20.6375 + 2
    tf = 12.7
    # U: um plano de cisalhamento (linha junto à alma) e tração até a borda livre
    Agv = (40 + 75) * tf
    Anv = Agv - 1.5 * dhn * tf
    Ant = (32 - 0.5 * dhn) * tf
    esperado = min(0.6 * 450 * Anv + 450 * Ant, 0.6 * 345 * Agv + 450 * Ant) / 1.35 / 1000
    assert rd(r, "10") == pytest.approx(esperado)
    assert any("flexo-torção" in a for a in r.avisos)


def test_u_sem_raio_pede_para_verificar():
    r = ep.calcular(ep.com(U, raio_u=0.0))
    assert ep.disposicao(r, "Raio de concordância do U").status == "ALERTA"


def test_u_enchimento_da_alma_e_inteiro():
    r = ep.calcular(ep.com(U, perfil_inferior='U 12" x 29,76'))
    assert r.propriedades["tsw"] == pytest.approx(9.8 - 9.63)


def test_u_com_tala_interna():
    r = ep.calcular(ep.com(U, talas_internas=True, bi=45.0, ti=9.5))
    assert r.propriedades["n_int"] == 1
    assert ep.verificacao(r, "5i").resistente == pytest.approx(45 * 9.5 * 250 / 1.1 / 1000)


def test_familias_nao_se_misturam():
    assert ep.validar(ep.com(P, perfil_inferior='U 12" x 37,00'))


# ------------------------------------------------------------------ SCI P207, 5.4 (pág. 79–81)
def test_p207_forcas_nas_mesas_metade():
    z = 453.6 - 12.7
    Fft, Ffc = ep.forcas_nas_mesas(-150.0, 200.0, z, 0.5)
    assert Fft == pytest.approx(529, rel=TOL) and Ffc == pytest.approx(379, rel=TOL)


def test_p207_grupo_da_alma():
    g = ep.grupo_da_alma(150.0, 0.0, m=1, nc=3, sv=0.0, sh=100.0, e=50.0)
    assert g.soma_r2 == pytest.approx(20000)
    assert g.componente_1 == pytest.approx(50.0) and g.componente_2 == pytest.approx(37.5)
    assert g.resultante == pytest.approx(62.5)


def test_p207_modulo_liquido_das_talas_da_alma():
    I, W = ep.modulo_liquido(300.0, 10.0, 22.0, [-100.0, 0.0, 100.0], n_talas=2)
    assert I == pytest.approx(18.07e6, rel=TOL) and W == pytest.approx(241e3, rel=TOL)


# ------------------------------------------------------------------ página
def abrir(**estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(PAGINA)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def test_todo_texto_de_ajuda_e_usado_e_termina_com_ponto():
    texto_das_telas = "".join(
        (RAIZ / f).read_text(encoding="utf-8")
        for f in (PAGINA, "components/emendas_do_modelo_ui.py")
    )
    usadas = set(re.findall(r'"([a-zA-Z_0-9]+)"', texto_das_telas))
    assert set(AJUDA) <= usadas, set(AJUDA) - usadas
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and texto[-1] in ".!:", chave


def test_pagina_mostra_os_numeros_do_nucleo(banco_isolado):
    t = abrir(emp_desliz=True, emp_usar_nc=True)
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    t = abrir()
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Situação geral"] == "ATENDE"
    assert metricas["Utilização máxima"] == "51 %"
    assert str(metricas["Total de parafusos"]) == "24"
    assert metricas["Situação mínima"] == "b"
    assert any("1 item(ns) a VERIFICAR" in w.value for w in t.warning)
    assert len(t.get("image")) == 2


def test_pagina_com_u_e_talas_internas(banco_isolado):
    t = abrir(emp_familia=ep.FAMILIA_U, emp_internas=True)
    assert any(m.label == "Situação geral" for m in t.metric)
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)


# ------------------------------------------------------------------ registro, memorial e guia
def _textos_svg(desenho) -> str:
    from components.cena_3d_svg import svg_da_cena

    return " ".join(re.findall(r">([^<>]+)</text>", svg_da_cena(desenho)))


def test_cota_x1_so_no_u():
    from core import desenho_emenda_pilar as de

    assert "x1 =" not in _textos_svg(de.vista_da_mesa(ep.calcular(ep.com(P, talas_internas=True))))
    assert "x1 = 45" in _textos_svg(de.vista_da_mesa(ep.calcular(U)))


def test_registro_leva_so_as_linhas_que_se_aplicam_e_os_desenhos(r):
    import json

    from core import desenho_emenda_pilar as de
    from core.record_charts import imagens_do_registro

    registro = json.loads(json.dumps(ep.registro(r, figuras=de.figuras_para_o_registro(r))))
    assert registro["modulo_id"] == ep.MODULO_ID and registro["status"] == "Atenção"
    nomes = [v["verificação"] for v in registro["resultados"]["verificações"]]
    assert not [v for v in registro["resultados"]["verificações"] if v["status"] == "N/A"]
    assert nomes[0].startswith("1. Corte") and "Continuidade: extensão de cada lado" in nomes
    assert len(registro["resultados"]["combinacoes"]) == 3  # 2 casos + o mínimo b
    imagens, aviso = imagens_do_registro(registro, {})
    assert aviso == "" and len(imagens) == 2
    assert any("SCI P207" in x for x in registro["referencias"])
    assert registro["entradas"]["total_de_parafusos"] == 24


def test_memorial_word_e_pdf():
    import io

    import docx

    from core import desenho_emenda_pilar as de

    r = ep.calcular(ep.com(P, talas_internas=True))
    w = ep.memorial_da_emenda(r, figuras=de.figuras_para_o_registro(r))
    d = docx.Document(io.BytesIO(w))
    titulos = [p.text for p in d.paragraphs if p.style.name.startswith("Heading")]
    assert titulos[0] == "Emenda de pilar — W 200 x 46,1 (H) (talas internas)"
    assert "Esforços de cálculo" in titulos and "Conclusão" in titulos
    texto = " ".join(p.text for p in d.paragraphs).lower()
    assert "não avaliad" not in texto and "página" not in texto
    assert "valor normativo" not in texto
    pdf = ep.memorial_da_emenda(r, figuras=de.figuras_para_o_registro(r), formato="pdf")
    assert pdf[:4] == b"%PDF"


def test_entra_no_capitulo_das_ligacoes_do_memorial_do_projeto():
    from core import memorial_do_projeto as mp
    from core import memorial_verificacoes as mv

    registro = {"modulo_id": ep.MODULO_ID, "titulo": "Emenda de pilar — W 200 x 46,1 (H)"}
    assert mp.ETAPAS[mp.indice_da_etapa(registro)].nome == "Ligações"
    entradas = ep.registro(ep.calcular(P))["entradas"]
    curadas = {c for c, *_ in mv.ENTRADAS_CURADAS[ep.MODULO_ID]}
    assert set(entradas) <= curadas, set(entradas) - curadas


def test_pagina_registra_no_projeto(banco_com_projeto):
    from core.project_store import obter_projeto_ativo

    t = abrir()
    assert {b.label for b in t.get("download_button")} >= {
        "Baixar o memorial (Word)",
        "Baixar o memorial (PDF)",
    }
    t.button(key="registrar_emenda_pilar").click().run()
    assert not t.exception
    registros = [
        x for x in obter_projeto_ativo()["registros_tecnicos"] if x["modulo_id"] == ep.MODULO_ID
    ]
    assert len(registros) == 1 and registros[0]["status"] == "Atenção"


def test_guia_tem_o_capitulo_com_o_exemplo(banco_isolado):
    r = ep.calcular(P)
    t = abrir()
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Emenda de pilar"
    t.run()
    assert "Emenda de pilar" in [h.value for h in t.header]
    esperado = next(c.value for c in t.caption if "Resultado esperado" in c.value)
    assert f"{100 * r.utilizacao_maxima:.0f} %" in esperado and "24 parafusos" in esperado
