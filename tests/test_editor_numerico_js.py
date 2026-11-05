"""A lógica das pranchetas em JS, rodada no Node: o que se digita e a geometria das chapas."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EDITOR = RAIZ / "components" / "editor_numerico.js"
GEOMETRIA = RAIZ / "components" / "prancheta" / "geometria.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="Node não instalado")


def _rodar(fonte: Path, expressao: str):
    programa = fonte.read_text(encoding="utf-8") + f"\nconsole.log(JSON.stringify({expressao}));\n"
    saida = subprocess.run(
        [NODE, "-"],
        input=programa,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    return json.loads(saida.stdout)


def _prancheta(expressao: str):
    """Geometria com a leitura da caixinha, como a prancheta recebe as duas."""
    programa = EDITOR.read_text(encoding="utf-8") + GEOMETRIA.read_text(encoding="utf-8")
    programa += f"\nconsole.log(JSON.stringify({expressao}));\n"
    saida = subprocess.run(
        [NODE, "-"],
        input=programa,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    return json.loads(saida.stdout)


def _ler(texto: str, atual: float = 100.0, unidade: str = "mm"):
    argumentos = json.dumps([texto, atual, unidade], ensure_ascii=False)
    return _rodar(EDITOR, f"lerValorDigitado(...{argumentos})")


# ---------------------------------------------------------------------------
# Valores comerciais em volta do número
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (7.0, [5.0, 6.3, 8.0, 9.5]),
        (8.0, [5.0, 6.3, 8.0, 9.5, 12.5]),
        (1.0, [3.0, 4.75]),
        (100.0, [16.0, 25.0]),
        (3.0, [3.0, 4.75, 5.0]),
    ],
)
def test_vizinhos_da_serie(valor, esperado):
    serie = [3.0, 4.75, 5.0, 6.3, 8.0, 9.5, 12.5, 16.0, 25.0]
    assert _rodar(EDITOR, f"enVizinhos({json.dumps(serie)}, {valor})") == esperado


# ---------------------------------------------------------------------------
# O que se digita
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("150", 150.0),
        ("1,5", 1.5),
        ("1.5", 1.5),
        ("1.200,5", 1200.5),
        ("300/2", 150.0),
        ("2*150+10", 310.0),
        ("(100+50)/3", 50.0),
        ("2x150", 300.0),
        ("-20", -20.0),
    ],
)
def test_numero_e_conta(texto, esperado):
    assert _ler(texto)["valor"] == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("texto", "unidade", "esperado"),
    [
        ("1,5 m", "mm", 1500.0),
        ("2 pol", "mm", 50.8),
        ('2"', "mm", 50.8),
        ("10 cm", "mm", 100.0),
        ("3000 mm", "m", 3.0),
        ("5 kN", "N", 5000.0),
        ("500 N", "kN", 0.5),
        ("100 kgf", "kN", 0.980665),
        ("2 tf", "kN", 19.6133),
        ("10 bar", "MPa", 1.0),
        ("1500 N·mm", "N·m", 1.5),
        ("2 kN.m", "N·m", 2000.0),
        ("300/2 mm", "mm", 150.0),
        ("2 cm²", "mm²", 200.0),
    ],
)
def test_unidade_digitada_converte_para_a_do_campo(texto, unidade, esperado):
    assert _ler(texto, unidade=unidade)["valor"] == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("+10", 110.0), ("*1,5", 150.0), ("/4", 25.0), ("+5 cm", 150.0)],
)
def test_valor_relativo_parte_do_atual(texto, esperado):
    assert _ler(texto, 100.0)["valor"] == pytest.approx(esperado)


@pytest.mark.parametrize(
    ("texto", "unidade", "trecho"),
    [
        ("", "mm", "Digite"),
        ("abc", "mm", "não combina"),
        ("5 kN", "mm", "não combina"),
        ("5 mm", "", "não tem unidade"),
        ("3+", "mm", "Não entendi"),
        ("(2", "mm", "Não entendi"),
        ("1/0", "mm", "Não entendi"),
        ("/0", "mm", "dividir por zero"),
    ],
)
def test_digitacao_ruim_vira_motivo_e_nao_numero(texto, unidade, trecho):
    lido = _ler(texto, unidade=unidade)
    assert "valor" not in lido
    assert trecho in lido["erro"]


def test_texto_do_usuario_nao_e_executado():
    lido = _ler("process.exit(1)")
    assert "erro" in lido


@pytest.mark.parametrize(
    ("valor", "passo", "esperado"),
    [(150.0, 5.0, 5.0), (150.0, None, 10.0), (3.5, None, 0.1), (0.0, None, 0.1)],
)
def test_passo_das_setas(valor, passo, esperado):
    argumentos = json.dumps([valor, passo])
    assert _rodar(EDITOR, f"passoDoValor(...{argumentos})") == pytest.approx(esperado)


# ---------------------------------------------------------------------------
# Geometria da seção
# ---------------------------------------------------------------------------


def _ret(x, y, b, h, **extra):
    return {"forma": "ret", "x": x, "y": y, "b": b, "h": h, "giro": 0, "furo": False, **extra}


def _i():
    """Mesa de baixo, alma e mesa de cima: 300 × 150, mesas de 20 e alma de 10."""
    return [_ret(75, 10, 150, 20), _ret(75, 150, 10, 260), _ret(75, 290, 150, 20)]


def _chamar(partes, funcao, *argumentos):
    dados = json.dumps(partes, ensure_ascii=False)
    resto = ", ".join(json.dumps(a, ensure_ascii=False) for a in argumentos)
    return _rodar(GEOMETRIA, f"(() => {{const p = {dados}; {funcao}(p, {resto}); return p}})()")


def _bordas(p):
    return p["x"] - p["b"] / 2, p["y"] - p["h"] / 2, p["x"] + p["b"] / 2, p["y"] + p["h"] / 2


def test_alma_mais_alta_empurra_a_mesa_de_cima_e_nada_solta():
    base, alma, topo = _chamar(_i(), "dimensionarParte", 1, "h", 300)
    assert alma["h"] == 300
    assert _bordas(alma)[1] == pytest.approx(_bordas(base)[3])
    assert _bordas(topo)[1] == pytest.approx(_bordas(alma)[3])
    assert _bordas(topo)[3] == pytest.approx(340)


def test_mesa_de_baixo_mais_grossa_sobe_o_resto():
    base, alma, topo = _chamar(_i(), "dimensionarParte", 0, "h", 30)
    assert _bordas(base)[:2] == pytest.approx((0, 0))
    assert _bordas(alma)[1] == pytest.approx(30)
    assert _bordas(topo)[3] == pytest.approx(310)


def test_mesa_de_cima_mais_grossa_nao_invade_a_alma():
    """Era o limite antigo: crescer do centro fazia a mesa entrar na alma."""
    _, alma, topo = _chamar(_i(), "dimensionarParte", 2, "h", 30)
    assert _bordas(topo)[1] == pytest.approx(_bordas(alma)[3])
    assert _bordas(topo)[3] == pytest.approx(310)


def test_mesa_mais_larga_fica_centrada_e_nao_mexe_na_outra():
    base, alma, topo = _chamar(_i(), "dimensionarParte", 2, "b", 200)
    assert topo["b"] == 200
    assert topo["x"] == pytest.approx(alma["x"])
    assert base["b"] == 150  # dá para ter mesas diferentes


def test_alma_mais_grossa_continua_centrada():
    _, alma, _ = _chamar(_i(), "dimensionarParte", 1, "b", 16)
    assert alma["x"] == pytest.approx(75)
    assert alma["b"] == 16


def test_duas_almas_de_caixao_crescem_juntas():
    partes = [
        _ret(100, 5, 200, 10),
        _ret(5, 110, 10, 200),
        _ret(195, 110, 10, 200),
        _ret(100, 215, 200, 10),
    ]
    _, a, b, topo = _chamar(partes, "dimensionarParte", 1, "h", 240)
    assert a["h"] == b["h"] == 240
    assert _bordas(b)[3] == pytest.approx(_bordas(topo)[1])


def test_chapas_lado_a_lado_empurram_para_os_dois_lados():
    partes = [_ret(50, 50, 100, 100), _ret(150, 50, 100, 100), _ret(250, 50, 100, 100)]
    a, b, c = _chamar(partes, "dimensionarParte", 1, "b", 120)
    assert _bordas(a)[2] == pytest.approx(_bordas(b)[0])
    assert _bordas(c)[0] == pytest.approx(_bordas(b)[2])


def test_furo_acompanha_a_chapa_que_andou():
    partes = [
        _ret(50, 50, 100, 100),
        _ret(50, 150, 100, 100),
        {"forma": "circ", "x": 50, "y": 150, "b": 20, "h": 20, "giro": 0, "furo": True},
    ]
    _, chapa, furo = _chamar(partes, "dimensionarParte", 0, "h", 130)
    assert chapa["y"] == pytest.approx(180)
    assert furo["y"] == pytest.approx(180)


def test_circulo_muda_os_dois_lados():
    partes = [{"forma": "circ", "x": 0, "y": 0, "b": 50, "h": 50, "giro": 0, "furo": False}]
    circulo = _chamar(partes, "dimensionarParte", 0, "b", 80)[0]
    assert (circulo["b"], circulo["h"]) == (80, 80)


def test_medida_invalida_nao_mexe_em_nada():
    assert _chamar(_i(), "dimensionarParte", 1, "h", -5) == _i()
    assert _chamar(_i(), "dimensionarParte", 1, "h", 0) == _i()


def test_altura_total_estica_a_alma_e_mantem_as_mesas():
    base, alma, topo = _chamar(_i(), "esticarConjunto", "h", 400)
    assert (base["h"], topo["h"]) == (20, 20)
    assert alma["h"] == 360
    assert _bordas(alma)[1] == pytest.approx(_bordas(base)[3])
    assert _bordas(topo)[1] == pytest.approx(_bordas(alma)[3])
    assert _bordas(topo)[3] - _bordas(base)[1] == pytest.approx(400)


def test_largura_total_alarga_as_mesas_e_nao_a_alma():
    base, alma, topo = _chamar(_i(), "esticarConjunto", "b", 200)
    assert (base["b"], topo["b"]) == (200, 200)
    assert alma["b"] == 10
    assert alma["x"] == pytest.approx(base["x"])


def test_largura_total_do_u_mantem_a_alma_na_borda():
    partes = [_ret(50, 10, 100, 20), _ret(5, 100, 10, 160), _ret(50, 190, 100, 20)]
    mesa, alma, _ = _chamar(partes, "esticarConjunto", "b", 140)
    assert mesa["b"] == 140
    assert _bordas(alma)[0] == pytest.approx(_bordas(mesa)[0])


def test_tubo_redondo_muda_de_escala():
    partes = [
        {"forma": "circ", "x": 0, "y": 0, "b": 100, "h": 100, "giro": 0, "furo": False},
        {"forma": "circ", "x": 0, "y": 0, "b": 80, "h": 80, "giro": 0, "furo": True},
    ]
    fora, furo = _chamar(partes, "esticarConjunto", "b", 150)
    assert fora["b"] == pytest.approx(150)
    assert furo["b"] == pytest.approx(120)


# ---------------------------------------------------------------------------
# Polígono: mudar um lado sem entortar o perfil
# ---------------------------------------------------------------------------

L = [[0, 0], [100, 0], [100, 10], [10, 10], [10, 80], [0, 80]]
T = [[-5, 0], [5, 0], [5, 90], [50, 90], [50, 100], [-50, 100], [-50, 90], [-5, 90]]
U = [[0, 0], [100, 0], [100, 100], [90, 100], [90, 10], [10, 10], [10, 100], [0, 100]]
RETANGULO = [[0, 0], [100, 0], [100, 50], [0, 50]]


def _poligono(pontos):
    return {
        "forma": "poli",
        "x": 0,
        "y": 0,
        "b": 0,
        "h": 0,
        "giro": 0,
        "pontos": pontos,
        "grupo": 0,
    }


def _mudar_lado(pontos, k, novo, trocar=False):
    partes = json.dumps([_poligono(pontos)])
    troca = "true" if trocar else "false"
    return _prancheta(
        f"""(() => {{
          const partes = {partes}
          const erro = ajustarCota(partes, cotaDoLado(partes, 0, {k}, {troca}), {novo})
          return {{ erro, pontos: partes[0].pontos }}
        }})()"""
    )


def test_lado_do_l_leva_o_que_esta_alem_e_mantem_os_angulos():
    saida = _mudar_lado(L, 0, 120)
    assert saida["erro"] == ""
    assert saida["pontos"] == [[0, 0], [120, 0], [120, 10], [10, 10], [10, 80], [0, 80]]


def test_encurtar_usa_o_mesmo_lado_e_nao_o_sinal_do_movimento():
    saida = _mudar_lado(L, 0, 60)
    assert saida["pontos"] == [[0, 0], [60, 0], [60, 10], [10, 10], [10, 80], [0, 80]]


def test_subir_a_alma_do_t_leva_a_mesa_inteira():
    """Mover só o ponto afinaria a mesa: ela precisa continuar com 10 mm."""
    saida = _mudar_lado(T, 1, 110)
    assert saida["pontos"] == [
        [-5, 0],
        [5, 0],
        [5, 110],
        [50, 110],
        [50, 120],
        [-50, 120],
        [-50, 110],
        [-5, 110],
    ]


def test_subir_uma_aba_do_u_nao_leva_a_outra():
    saida = _mudar_lado(U, 1, 120)
    assert saida["pontos"] == [
        [0, 0],
        [100, 0],
        [100, 120],
        [90, 120],
        [90, 10],
        [10, 10],
        [10, 100],
        [0, 100],
    ]


def test_retangulo_continua_retangulo():
    saida = _mudar_lado(RETANGULO, 1, 70)
    assert saida["pontos"] == [[0, 0], [100, 0], [100, 70], [0, 70]]


def test_a_outra_ponta_pode_ser_a_que_anda():
    saida = _mudar_lado(RETANGULO, 0, 120, trocar=True)
    assert saida["erro"] == ""
    assert saida["pontos"] == [[-20, 0], [100, 0], [100, 50], [-20, 50]]


def test_lado_inclinado_anda_na_propria_direcao():
    saida = _mudar_lado([[0, 0], [30, 40], [0, 80]], 0, 100)
    assert saida["erro"] == ""
    assert saida["pontos"][1] == pytest.approx([60, 80])


def test_encurtar_o_l_alem_da_alma_ainda_e_uma_forma_valida():
    saida = _mudar_lado(L, 0, 5)
    assert saida["erro"] == ""
    assert saida["pontos"][2] == [5, 10]


def test_lado_que_fica_sobre_outro_e_recusado_e_o_erro_vem_escrito():
    """Encurtar a base do U põe a aba em cima da outra: não cruza em X, mas estraga a seção."""
    assert _mudar_lado(U, 0, 5)["erro"] == "O contorno cruzaria a si mesmo."


def test_medida_zero_e_recusada():
    assert _mudar_lado(L, 0, 0)["erro"] == "A medida precisa ser maior que zero."


@pytest.mark.parametrize(
    ("pontos", "esperado"),
    [
        ([[0, 0], [10, 0]], "O polígono precisa de ao menos 3 pontos."),
        ([[0, 0], [10, 0], [20, 0]], "O polígono ficaria sem área."),
        ([[0, 0], [0, 0], [20, 5]], "Dois pontos ficariam no mesmo lugar."),
        ([[0, 0], [10, 10], [10, 0], [0, 20]], "O contorno cruzaria a si mesmo."),
        ([[0, 0], [10, 0], [10, 10], [5, 0], [0, 10]], "O contorno cruzaria a si mesmo."),
        (L, ""),
    ],
)
def test_problema_do_poligono(pontos, esperado):
    assert _prancheta(f"problemaDoPoligono({json.dumps(pontos)})") == esperado


def test_area_com_sinal_segue_o_sentido():
    assert _prancheta(f"areaComSinal({json.dumps(RETANGULO)})") == 5000
    assert _prancheta(f"areaComSinal({json.dumps(RETANGULO[::-1])})") == -5000


# ---------------------------------------------------------------------------
# Cotas de um ponto a outro
# ---------------------------------------------------------------------------

CHAPA = {"forma": "ret", "x": 50, "y": 25, "b": 100, "h": 50, "giro": 0, "pontos": [], "grupo": 0}
FURO = {"forma": "circ", "x": 30, "y": 25, "b": 20, "h": 20, "giro": 0, "pontos": [], "grupo": 0}


def _cota(partes, cota, novo):
    return _prancheta(
        f"""(() => {{
          const partes = {json.dumps(partes)}
          const erro = ajustarCota(partes, {json.dumps(cota)}, {novo})
          return {{ erro, partes }}
        }})()"""
    )


@pytest.mark.parametrize(
    ("mouse", "modo"),
    [([50, 120], "h"), ([50, -30], "h"), ([160, 40], "v"), ([-20, 40], "v"), ([160, 120], "a")],
)
def test_lugar_da_cota_escolhe_o_tipo(mouse, modo):
    assert _prancheta(f"modoDaCota([0, 0], [100, 80], {json.dumps(mouse)})") == modo


def test_pontos_alinhados_so_tem_uma_medida():
    assert _prancheta("modoDaCota([0, 0], [100, 0], [50, -40])") == "h"
    assert _prancheta("modoDaCota([0, 0], [0, 80], [50, 40])") == "v"


@pytest.mark.parametrize(("modo", "medida"), [("h", 30), ("v", 40), ("a", 50)])
def test_medida_de_cada_tipo(modo, medida):
    assert _prancheta(f'medidaEntre([0, 0], [30, 40], "{modo}")') == medida


@pytest.mark.parametrize(
    ("modo", "mouse", "linha"),
    [
        ("h", [15, 70], [[0, 70], [30, 70]]),
        ("v", [90, 20], [[90, 0], [90, 40]]),
    ],
)
def test_linha_passa_pelo_lugar_escolhido(modo, mouse, linha):
    expressao = f"""(() => {{
      const f = folgaDaCota([0, 0], [30, 40], "{modo}", {json.dumps(mouse)})
      return linhaDaCota([0, 0], [30, 40], "{modo}", f)
    }})()"""
    assert _prancheta(expressao) == linha


def test_cota_direta_fica_paralela_e_na_distancia_do_mouse():
    expressao = """(() => {
      const f = folgaDaCota([0, 0], [100, 0], "a", [50, 30])
      return linhaDaCota([0, 0], [100, 0], "a", f)
    })()"""
    assert _prancheta(expressao) == [[0, 30], [100, 30]]


def test_ancoras_do_poligono_sao_pontos_e_meios():
    ancoras = _prancheta(f"ancorasDaParte({json.dumps(_poligono(RETANGULO))}, 3)")
    assert len(ancoras) == 8
    assert {"i": 3, "t": "m", "k": 0, "x": 50, "y": 0} in ancoras


def test_ancoras_da_chapa_trazem_o_centro_e_as_do_circulo_tambem():
    assert {"i": 0, "t": "c", "k": 0, "x": 50, "y": 25} in _prancheta(
        f"ancorasDaParte({json.dumps(CHAPA)}, 0)"
    )
    circulo = _prancheta(f"ancorasDaParte({json.dumps(FURO)}, 1)")
    assert len(circulo) == 5
    assert {"i": 1, "t": "v", "k": 0, "x": 40, "y": 25} in circulo


def test_furo_anda_pela_cota_a_partir_da_chapa():
    """Distância do furo à borda: o primeiro ponto fica e a peça do segundo anda."""
    cota = {"a": {"i": 0, "t": "v", "k": 0}, "b": {"i": 1, "t": "c", "k": 0}, "modo": "h"}
    saida = _cota([CHAPA, FURO], cota, 45)
    assert saida["erro"] == ""
    assert saida["partes"][1]["x"] == 45
    assert saida["partes"][1]["y"] == 25
    assert saida["partes"][0]["x"] == 50


def test_cota_leva_o_grupo_inteiro_da_peca_que_anda():
    outra = {**FURO, "grupo": 2}
    irma = {**CHAPA, "x": 300, "grupo": 2}
    cota = {"a": {"i": 0, "t": "v", "k": 0}, "b": {"i": 1, "t": "c", "k": 0}, "modo": "h"}
    saida = _cota([CHAPA, outra, irma], cota, 40)
    assert saida["partes"][1]["x"] == 40
    assert saida["partes"][2]["x"] == 310


def test_pontos_do_mesmo_perfil_mandam_mudar_pela_chapa():
    a = {**CHAPA, "grupo": 1}
    b = {**CHAPA, "y": 80, "grupo": 1}
    cota = {"a": {"i": 0, "t": "v", "k": 0}, "b": {"i": 1, "t": "v", "k": 0}, "modo": "v"}
    assert "mesmo perfil" in _cota([a, b], cota, 90)["erro"]


def test_chapa_cresce_a_partir_do_primeiro_ponto():
    cota = {"a": {"i": 0, "t": "v", "k": 1}, "b": {"i": 0, "t": "v", "k": 0}, "modo": "h"}
    saida = _cota([CHAPA], cota, 150)
    assert saida["erro"] == ""
    chapa = saida["partes"][0]
    assert (chapa["b"], chapa["x"]) == (150, 25)


def test_chapa_recusa_diagonal():
    cota = {"a": {"i": 0, "t": "v", "k": 0}, "b": {"i": 0, "t": "v", "k": 2}, "modo": "a"}
    assert "lados opostos" in _cota([CHAPA], cota, 150)["erro"]


def test_raio_do_circulo():
    cota = {"a": {"i": 0, "t": "c", "k": 0}, "b": {"i": 0, "t": "v", "k": 0}, "modo": "a"}
    saida = _cota([FURO], cota, 25)
    assert saida["partes"][0]["b"] == 50
    assert saida["partes"][0]["h"] == 50


def test_cota_horizontal_no_poligono_leva_o_lado_todo():
    """Da ponta da aba até a ponta da mesa: anda em x, e o resto do L fica."""
    cota = {"a": {"i": 0, "t": "v", "k": 5}, "b": {"i": 0, "t": "v", "k": 2}, "modo": "h"}
    saida = _cota([_poligono(L)], cota, 130)
    assert saida["erro"] == ""
    assert saida["partes"][0]["pontos"] == [
        [0, 0],
        [130, 0],
        [130, 10],
        [10, 10],
        [10, 80],
        [0, 80],
    ]


def test_cota_que_perdeu_o_ponto_avisa():
    cota = {"a": {"i": 0, "t": "v", "k": 0}, "b": {"i": 7, "t": "v", "k": 0}, "modo": "h"}
    assert "perdeu" in _cota([CHAPA], cota, 10)["erro"]


def test_cotas_validas_tira_quem_perdeu_o_ponto():
    boa = {"a": {"i": 0, "t": "v", "k": 0}, "b": {"i": 0, "t": "v", "k": 1}, "modo": "h"}
    ruim = {"a": {"i": 0, "t": "v", "k": 0}, "b": {"i": 0, "t": "v", "k": 9}, "modo": "h"}
    expressao = f"cotasValidas({json.dumps([CHAPA])}, {json.dumps([boa, ruim])})"
    assert _prancheta(expressao) == [boa]


# ---------------------------------------------------------------------------
# Pontos novos e pontos apagados
# ---------------------------------------------------------------------------


def _cotas_em(*ks):
    return [
        {"a": {"i": 0, "t": "v", "k": k}, "b": {"i": 0, "t": "v", "k": 0}, "modo": "a"} for k in ks
    ]


def test_inserir_ponto_mantem_a_cota_no_mesmo_lugar():
    partes = json.dumps([_poligono(RETANGULO)])
    cotas = json.dumps(_cotas_em(1, 2))
    saida = _prancheta(
        f"""(() => {{
          const partes = {partes}
          const cotas = inserirVertice(partes, {cotas}, 0, 1, [100, 25])
          return {{ cotas, pontos: partes[0].pontos, antes: pontoDaAncora(partes, cotas[1].a) }}
        }})()"""
    )
    assert saida["pontos"] == [[0, 0], [100, 0], [100, 25], [100, 50], [0, 50]]
    assert [c["a"]["k"] for c in saida["cotas"]] == [1, 3]
    assert saida["antes"] == [100, 50]


def test_apagar_ponto_leva_a_cota_presa_a_ele_e_corrige_as_outras():
    partes = json.dumps([_poligono([[0, 0], [100, 0], [100, 25], [100, 50], [0, 50]])])
    cotas = json.dumps(_cotas_em(2, 3))
    saida = _prancheta(
        f"""(() => {{
          const partes = {partes}
          const cotas = apagarVertice(partes, {cotas}, 0, 2)
          return {{ cotas, pontos: partes[0].pontos, ponto: pontoDaAncora(partes, cotas[0].a) }}
        }})()"""
    )
    assert saida["pontos"] == RETANGULO
    assert [c["a"]["k"] for c in saida["cotas"]] == [2]
    assert saida["ponto"] == [100, 50]


def test_apagar_parte_renumera_as_cotas_das_outras():
    cotas = [
        {"a": {"i": 0, "t": "c", "k": 0}, "b": {"i": 1, "t": "c", "k": 0}, "modo": "h"},
        {"a": {"i": 1, "t": "c", "k": 0}, "b": {"i": 2, "t": "c", "k": 0}, "modo": "h"},
    ]
    saida = _prancheta(f"cotasSemPartes({json.dumps(cotas)}, new Set([0]))")
    assert len(saida) == 1
    assert (saida[0]["a"]["i"], saida[0]["b"]["i"]) == (0, 1)


# ---------------------------------------------------------------------------
# O próximo ponto digitado
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("100", [110, 20]),
        ("10 cm", [110, 20]),
        ("100<0", [110, 20]),
        ("100<90", [10, 120]),
        ("100<180", [-90, 20]),
        ("100<90°", [10, 120]),
        ("@50;20", [60, 40]),
        ("@50,20", [60, 40]),
        ("@-5,5;2,5", [4.5, 22.5]),
        ("@ 50 ; -20", [60, 0]),
    ],
)
def test_proximo_ponto(texto, esperado):
    argumentos = json.dumps([texto, [10, 20], [500, 20]], ensure_ascii=False)
    saida = _prancheta(f"lerProximoPonto(...{argumentos})")
    assert saida["valor"] == pytest.approx(esperado, abs=1e-9)


@pytest.mark.parametrize("texto", ["@50", "@a;b", "abc<45", "100<xx", "", "abc"])
def test_proximo_ponto_recusa_o_que_nao_entende(texto):
    argumentos = json.dumps([texto, [10, 20], [500, 20]], ensure_ascii=False)
    assert _prancheta(f"lerProximoPonto(...{argumentos})")["erro"]


def test_proximo_ponto_precisa_de_direcao():
    assert "Mova o mouse" in _prancheta("lerProximoPonto('100', [10, 20], [10, 20])")["erro"]


@pytest.mark.parametrize(
    ("alvo", "esperado"),
    [
        ([100, 3], [100, 0]),
        ([3, 100], [0, 100]),
        ([70, 72], [70.711, 70.711]),
        ([-100, 4], [-100, 0]),
    ],
)
def test_travar_angulo(alvo, esperado):
    saida = _prancheta(f"travarAngulo([0, 0], {json.dumps(alvo)})")
    assert saida == pytest.approx(esperado, abs=0.3)


def test_angulo_do_lado():
    assert _prancheta("anguloEntre([0, 0], [10, 0])") == 0
    assert _prancheta("anguloEntre([0, 0], [0, 10])") == 90
    assert _prancheta("anguloEntre([0, 0], [-10, 0])") == 180
    assert _prancheta("anguloEntre([0, 0], [0, -10])") == 270


def test_girar_lado_mantem_o_comprimento():
    partes = json.dumps([_poligono(RETANGULO)])
    saida = _prancheta(
        f"""(() => {{
          const partes = {partes}
          const cota = cotaDoLado(partes, 0, 0)
          const erro = girarLado(partes, cota, 20)
          return {{ erro, ponto: partes[0].pontos[1] }}
        }})()"""
    )
    assert saida["erro"] == ""
    assert saida["ponto"] == pytest.approx([93.9693, 34.202], abs=1e-3)


def test_girar_lado_ate_encostar_em_outro_e_recusado():
    """A 30°, a ponta de 100 mm cai em cima do lado de 50 mm de altura."""
    partes = json.dumps([_poligono(RETANGULO)])
    saida = _prancheta(
        f"""(() => {{
          const partes = {partes}
          return girarLado(partes, cotaDoLado(partes, 0, 0), 30)
        }})()"""
    )
    assert saida == "O contorno cruzaria a si mesmo."


def test_grau_e_unidade_que_a_caixinha_aceita():
    assert _ler("45°", 0.0, "°") == {"valor": 45}
