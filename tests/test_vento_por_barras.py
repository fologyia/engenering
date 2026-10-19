"""Vento barra a barra (NBR 6123:2023, 8.3 a 8.5): área de sombra, reticulados, proteção, elementos,
plano de cargas e registro. As contas de conferência usam as mesmas Figuras 12 e 14 (testadas em
``test_vento_estrutura_aberta``) e o q da norma."""

from __future__ import annotations

import math

import pytest

from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import vento_estrutura_aberta as va
from core import vento_nbr6123 as vb
from core import vento_por_barras as vpb
from core import vento_por_barras_registro as vbr

VENTO = va.ParametrosVento(v0_m_s=35.0, categoria="III")
ALMA_X = (1.0, 0.0, 0.0)
ALMA_Z = (0.0, 0.0, 1.0)


def pilar(nome: str, x: float, y: float, h: float = 4.0, *, b: float = 0.25) -> vpb.BarraAoVento:
    return vpb.BarraAoVento(nome, (x, y, 0.0), (x, y, h), b, b, ALMA_X)


def viga(nome: str, a, c, *, d: float = 0.30, bf: float = 0.15) -> vpb.BarraAoVento:
    return vpb.BarraAoVento(nome, a, c, d, bf, ALMA_Z)


def q_kN(z: float, classe: str) -> float:
    return (
        vb.calcular_vento_no_local(
            VENTO.v0_m_s,
            s1=VENTO.s1,
            categoria=VENTO.categoria,
            classe=classe,
            altura_m=z,
            grupo_s3=VENTO.grupo_s3,
        ).q_N_m2
        / 1e3
    )


# ------------------------------------------------------------------ área de sombra
def test_largura_vista_pela_alma():
    """Alma em X: o vento em X vê a mesa (b_f); em Y vê a alma (d); a 45° vê as duas projeções."""
    b = vpb.BarraAoVento("P", (0, 0, 0), (0, 0, 4), 0.20, 0.15, ALMA_X)
    assert vpb.largura_vista(b, 0) == pytest.approx((1.0, 0.15))
    assert vpb.largura_vista(b, 90) == pytest.approx((1.0, 0.20))
    s = math.sqrt(0.5)
    assert vpb.largura_vista(b, 45) == pytest.approx((1.0, 0.20 * s + 0.15 * s))
    sem_direcao = vpb.BarraAoVento("P", (0, 0, 0), (0, 0, 4), 0.20, 0.15)
    assert vpb.largura_vista(sem_direcao, 0)[1] == pytest.approx(0.20)  # a favor da segurança


def test_viga_ao_longo_do_vento_nao_carrega_e_a_perpendicular_mostra_a_alma():
    ao_longo = viga("V", (0, 0, 4), (6, 0, 4))
    assert vpb.area_de_sombra(ao_longo, 0) == pytest.approx(0.0)
    assert vpb.area_de_sombra(ao_longo, 90) == pytest.approx(6 * 0.30)
    assert vpb.area_de_sombra(ao_longo, 45) == pytest.approx(6 * math.sqrt(0.5) * 0.30)


def test_diagonal_inclinada_usa_o_seno_do_angulo_com_o_vento():
    d = vpb.BarraAoVento("D", (0, 0, 0), (3, 0, 4), 0.064, 0.064)
    sen = 4 / 5  # o vento em X faz cos θ = 3/5 com o eixo
    assert vpb.area_de_sombra(d, 0) == pytest.approx(5 * sen * 0.064)


# ------------------------------------------------------------------ uma coluna isolada
def test_coluna_isolada_bate_com_a_conta_a_mao():
    r = vpb.calcular(vpb.EntradaPorBarras((pilar("P1", 0, 0, b=0.15),), VENTO, direcoes=(0,)))
    f = r.direcao(0).barras[0]
    contorno = 0.15 * (4.0 + 0.15)  # a barra e meia largura de cada lado
    phi = 0.15 * 4.0 / contorno
    ca = va.ca_reticulado_plano(phi)
    assert f.plano == "R1" and f.ca == pytest.approx(ca) and f.eta == 1.0
    assert f.forca_kN == pytest.approx(ca * q_kN(4.0, r.classe) * 0.15 * 4.0)
    assert f.fx_kN_m == pytest.approx(f.forca_kN / 4.0) and f.fy_kN_m == pytest.approx(0.0)


# ------------------------------------------------------------------ grade regular = método dos pórticos
def _grade() -> list[vpb.BarraAoVento]:
    barras = []
    for i, x in enumerate((0.0, 6.0, 12.0)):
        for j, y in enumerate((0.0, 6.0)):
            barras.append(pilar(f"P{i}{j}", x, y))
        barras.append(viga(f"VY{i}", (x, 0.0, 4.0), (x, 6.0, 4.0)))
    for j, y in enumerate((0.0, 6.0)):
        barras.append(viga(f"VX{j}a", (0.0, y, 4.0), (6.0, y, 4.0)))
        barras.append(viga(f"VX{j}b", (6.0, y, 4.0), (12.0, y, 4.0)))
    return barras


def test_grade_regular_da_o_mesmo_que_os_porticos():
    """Três pórticos iguais: barra a barra e por pórticos dão a mesma força (o contorno de cada
    plano difere pela meia largura das barras: φ e η mudam um pouco)."""
    g = va.GeometriaAberta(
        comprimento_x_m=12.0,
        largura_y_m=6.0,
        cotas_m=(4.0,),
        vaos_x=2,
        vaos_y=1,
        largura_pilar_m=0.25,
        altura_viga_m=0.30,
        largura_diagonal_x_m=1e-6,
        largura_diagonal_y_m=1e-6,
        guarda_corpo=False,
    )
    porticos = va.calcular_vento_aberto(g, VENTO)
    r = vpb.calcular(vpb.EntradaPorBarras(tuple(_grade()), VENTO, direcoes=(0, 90)))
    assert r.direcao(0).total_kN == pytest.approx(porticos.x.total_kN, rel=0.05)
    assert r.direcao(90).total_kN == pytest.approx(porticos.y.total_kN, rel=0.05)
    planos = r.direcao(0).planos
    assert [p.nome for p in planos] == ["R1", "R2", "R3"]
    assert planos[0].eta == 1.0 and all(p.eta < 1.0 for p in planos[1:])
    # a viga ao longo do vento não carrega (8.5)
    assert r.direcao(0).da_barra("VX0a").forca_kN == pytest.approx(0.0)


def test_protecao_desligada_carrega_mais():
    com = vpb.calcular(vpb.EntradaPorBarras(tuple(_grade()), VENTO, direcoes=(0,)))
    sem = vpb.calcular(vpb.EntradaPorBarras(tuple(_grade()), VENTO, direcoes=(0,), protecao=False))
    assert sem.direcao(0).total_kN > com.direcao(0).total_kN
    assert all(f.eta == 1.0 for f in sem.direcao(0).barras)


def test_so_a_parte_atras_do_plano_da_frente_e_protegida():
    """Pilar de trás mais alto que o da frente: só o trecho atrás do contorno ganha η."""
    frente = pilar("A", 0.0, 0.0, h=2.0)
    tras = pilar("B", 1.0, 0.0, h=4.0)
    r = vpb.calcular(vpb.EntradaPorBarras((frente, tras), VENTO, direcoes=(0,)))
    f = r.direcao(0).da_barra("B")
    assert 0.4 < f.fracao_protegida < 0.6  # metade de baixo
    eta_plano = r.direcao(0).planos[1].eta
    assert f.eta == pytest.approx(1 - f.fracao_protegida * (1 - eta_plano))


def test_diagonal_sem_protecao_e_com_ca_2():
    r = vpb.calcular(vpb.EntradaPorBarras(tuple(_grade()), VENTO, direcoes=(45,)))
    d = r.direcao(45)
    assert not d.planos and not d.perpendicular
    assert all(f.ca == 2.0 and f.eta == 1.0 for f in d.barras)
    assert d.fx_kN == pytest.approx(d.fy_kN)


def test_duas_colunas_com_balanco_e_assimetria_dao_torcao():
    """Duas colunas numa linha e a plataforma em balanço para um lado só: o vento perpendicular
    à linha das colunas tem resultante fora do centro (torção ≠ 0)."""
    barras = [
        pilar("P1", 0.0, 0.0),
        pilar("P2", 0.0, 1.8),
        viga("V1", (0.0, 0.0, 4.0), (3.0, 0.0, 4.0)),
        viga("V2", (0.0, 1.8, 4.0), (3.0, 1.8, 4.0)),
        viga("V3", (3.0, 0.0, 4.0), (3.0, 1.8, 4.0)),
    ]
    r = vpb.calcular(vpb.EntradaPorBarras(tuple(barras), VENTO, direcoes=(0, 90)))
    assert abs(r.direcao(90).torcao_kNm) > 0.05
    assert r.direcao(0).da_barra("P2").forca_kN > 0  # as duas colunas de frente para o vento X


# ------------------------------------------------------------------ elementos
def test_guarda_corpo_vai_para_a_viga_de_baixo():
    barras = (pilar("P1", 0, 0), pilar("P2", 6, 0), viga("V", (0.0, 0.0, 4.0), (6.0, 0.0, 4.0)))
    gc = vpb.ElementoAoVento("GC", vpb.TIPO_GUARDA_CORPO, (0.0, 0.0, 4.0), (6.0, 0.0, 4.0))
    r = vpb.calcular(vpb.EntradaPorBarras(barras, VENTO, elementos=(gc,), direcoes=(90, 0)))
    el = r.direcao(90).elementos[0]
    esperado = va.ca_reticulado_plano(0.30) * q_kN(5.1, r.classe) * 0.30 * 1.1 * 6.0
    assert el.forca_kN == pytest.approx(esperado)
    (parcela,) = el.parcelas
    assert parcela.barra == "V" and parcela.unidade == "kN/m"
    assert parcela.fy == pytest.approx(esperado / 6.0) and parcela.fx == pytest.approx(0.0)
    assert r.direcao(0).elementos[0].forca_kN == pytest.approx(0.0)  # paralelo ao vento (8.5)


def test_cilindro_igual_ao_do_metodo_dos_porticos():
    barras = (pilar("P1", 0, 0), viga("V", (0.0, 0.0, 4.0), (6.0, 0.0, 4.0)))
    vaso = vpb.ElementoAoVento(
        "Vaso", vpb.TIPO_CILINDRO, (2.0, 0.0, 4.0), altura_m=1.5, largura_x_m=0.8
    )
    r = vpb.calcular(vpb.EntradaPorBarras(barras, VENTO, elementos=(vaso,), direcoes=(0,)))
    el = r.direcao(0).elementos[0]
    eq = va.Equipamento("Vaso", 1, va.FORMA_CILINDRO, dimensao_x_m=0.8, altura_m=1.5)
    forca, _ = va._forca_equipamento(eq, 4.0, "X", VENTO, r.classe)
    assert el.forca_kN == pytest.approx(forca)
    assert el.parcelas[0].barra == "V" and el.parcelas[0].unidade == "kN"


def test_elemento_sem_viga_embaixo_vai_para_a_mais_proxima_com_aviso():
    barras = (pilar("P1", 0, 0),)
    painel = vpb.ElementoAoVento("Painel", vpb.TIPO_PAINEL, (5.0, 0.0, 1.0), (5.0, 2.0, 1.0))
    r = vpb.calcular(vpb.EntradaPorBarras(barras, VENTO, elementos=(painel,), direcoes=(0,)))
    assert r.direcao(0).elementos[0].parcelas[0].barra == "P1"
    assert any("Painel" in a for a in r.avisos)


# ------------------------------------------------------------------ plano de cargas
def test_plano_recebe_um_caso_por_direcao_com_a_soma_certa():
    r = vpb.calcular(
        vpb.EntradaPorBarras(tuple(_grade()), VENTO, direcoes=vpb.DIRECOES_COM_DIAGONAIS)
    )
    acoes = vpb.acoes_para_o_plano(r)
    assert [a.codigo for a in acoes] == list(pc.CODIGOS_DE_VENTO)
    for acao, d in zip(acoes, r.direcoes, strict=True):
        assert acao.grupo == pc.GRUPO_VENTO and acao.origem == vpb.ORIGEM
        fx = sum(c.valor * c.comprimento_m for c in acao.cargas if c.direcao.endswith("X"))
        fy = sum(c.valor * c.comprimento_m for c in acao.cargas if c.direcao.endswith("Y"))
        assert fx == pytest.approx(d.fx_kN, abs=1e-3) and fy == pytest.approx(d.fy_kN, abs=1e-3)
        assert not pc.validar_acao(acao)


def test_barra_com_o_vento_dela_e_o_do_guarda_corpo_vira_uma_linha_so():
    """A viga de borda recebe o vento dela e o do guarda-corpo: uma linha só no plano (uma carga
    no SolidWorks), com a soma — sem o aviso de "aparece duas vezes" na conferência."""
    gc = vpb.ElementoAoVento(
        "GC", vpb.TIPO_GUARDA_CORPO, (0.0, 0.0, 4.0), (6.0, 0.0, 4.0), barra="VX0a"
    )
    r = vpb.calcular(vpb.EntradaPorBarras(tuple(_grade()), VENTO, elementos=(gc,)))
    d = r.direcao(90)
    linhas = [c for c in vpb.cargas_da_direcao(d) if c.elemento == "VX0a"]
    assert len(linhas) == 1 and linhas[0].direcao == "+Y"
    propria = d.da_barra("VX0a")
    assert propria is not None
    parcela = d.elementos[0].parcelas[0]
    assert linhas[0].valor == pytest.approx(propria.fy_kN_m + parcela.fy, abs=1e-5)
    assert linhas[0].observacao.startswith("soma de ") and "GC" in linhas[0].observacao
    plano = vpb.plano_com_o_vento(pc.PlanoDeCargas(), r)
    assert not any("aparece duas vezes" in i.texto for i in pc.conferir_plano(plano))


def test_enviar_so_as_perpendiculares_tira_os_diagonais_antigos():
    todas = vpb.calcular(
        vpb.EntradaPorBarras(tuple(_grade()), VENTO, direcoes=vpb.DIRECOES_COM_DIAGONAIS)
    )
    plano = vpb.plano_com_o_vento(pc.PlanoDeCargas(), todas)
    assert set(pc.CODIGOS_DE_VENTO) <= set(plano.codigos)
    quatro = vpb.calcular(vpb.EntradaPorBarras(tuple(_grade()), VENTO))
    plano = vpb.plano_com_o_vento(plano, quatro)
    ventos = [c for c in plano.codigos if c in pc.CODIGOS_DE_VENTO]
    assert ventos == list(pc.CODIGOS_DE_VENTO_PERPENDICULARES)


def test_csv_tem_uma_linha_por_barra_e_direcao():
    r = vpb.calcular(vpb.EntradaPorBarras(tuple(_grade()), VENTO))
    texto = vpb.csv_das_cargas(r).decode("utf-8-sig")
    assert len(texto.strip().splitlines()) == 1 + len(_grade()) * 4


# ------------------------------------------------------------------ esqueleto do SolidWorks
def test_esqueleto_com_y_para_cima_vira_a_planta():
    corpo = ld.CorpoDoModelo(
        nome="Pilar-1",
        item="W200",
        descricao="W 200 x 35,9",
        inicio=(1.0, 0.0, 2.0),
        fim=(1.0, 4.0, 2.0),
        comprimento_m=4.0,
        forma=ld.FORMA_BARRA,
        secao_mm=(201.0, 165.0),
        direcao_secao=(0.0, 0.0, 1.0),
    )
    chapa = ld.CorpoDoModelo("Piso", "", "", (0, 0, 0), (1, 0, 1), 1.0, forma=ld.FORMA_CHAPA)
    g = ld.GeometriaDoModelo(corpos=(corpo, chapa))
    (b,) = vpb.barras_do_esqueleto(g, "Y", {"Pilar-1": "Viga-7"})
    assert b.inicio == pytest.approx((1.0, -2.0, 0.0)) and b.fim == pytest.approx((1.0, -2.0, 4.0))
    assert b.direcao_maior == pytest.approx((0.0, -1.0, 0.0))  # o Z do modelo é o −Y da planta
    assert b.maior_m == pytest.approx(0.201) and b.rotulo == "Pilar-1 (Viga-7)"
    assert vpb.do_modelo(vpb.para_a_planta((1.0, 2.0, 3.0), "Y"), "Y") == pytest.approx(
        (1.0, 2.0, 3.0)
    )


def test_entrada_errada_vira_mensagem():
    sem_barras = vpb.EntradaPorBarras(())
    assert vpb.validar_entrada(sem_barras)
    torta = vpb.EntradaPorBarras((pilar("P", 0, 0),), direcoes=(30,))
    assert any("30°" in e for e in vpb.validar_entrada(torta))
    repetida = vpb.EntradaPorBarras((pilar("P", 0, 0), pilar("P", 1, 0)))
    assert any("repetidos" in e for e in vpb.validar_entrada(repetida))
    with pytest.raises(vpb.VentoPorBarrasInvalido):
        vpb.calcular(vpb.EntradaPorBarras((pilar("P", 0, 0),), cota_do_terreno_m=10.0))


# ------------------------------------------------------------------ registro (memorial)
def test_registro_traz_o_resumo_os_reticulados_e_a_carga_de_cada_barra():
    r = vpb.calcular(
        vpb.EntradaPorBarras(tuple(_grade()), VENTO, direcoes=vpb.DIRECOES_COM_DIAGONAIS)
    )
    registro = vbr.registro_vento_por_barras(r, origem_das_barras="digitadas")
    tabelas = registro["resultados"]["tabelas_memorial"]
    assert len(tabelas) == 4
    assert tabelas[1]["legenda"].startswith("Força do vento em cada nível")
    assert len(tabelas[1]["linhas"]) == len(pc.CODIGOS_DE_VENTO) * 2  # o nível e a base
    assert tabelas[3]["cabecalhos"][3:] == list(pc.CODIGOS_DE_VENTO)
    assert len(tabelas[3]["linhas"]) == len(_grade())
    for tabela in tabelas:
        assert sum(tabela["larguras"]) == 9360
        assert all(len(linha) == len(tabela["cabecalhos"]) for linha in tabela["linhas"])
    assert registro["modulo_id"] == "vento_estrutura_aberta"
    assert "barra a barra" in registro["resultados"]["destaque_memorial"]
