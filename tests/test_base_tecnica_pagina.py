"""Base técnica, Plano de cargas e Vento em estruturas abertas, exercitados pela interface (AppTest).

Contratos: todo texto de ajuda é usado e todo campo tem o seu “?”; a base técnica grava no projeto e
as demais páginas começam com os seus valores; o vento vai ao plano de cargas e ao registro; o plano
monta as combinações; o guia e a página inicial conhecem o caminho do projeto.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components import vento_aberto_ui
from components.base_tecnica_help import AJUDA
from core import base_tecnica as bt
from core import contraventamento_plataforma as cp
from core import criterio_anglo as ca
from core import plano_de_cargas as pc
from core import vento_estrutura_aberta as va
from core import vento_nbr6123 as vb
from core.project_store import obter_projeto_ativo, salvar_projeto

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
BASE = "app_pages/base_tecnica.py"
PLANO = "app_pages/plano_cargas.py"
VENTO = "app_pages/vento_estrutura_aberta.py"
USO = re.compile(r'AJUDA\["([A-Za-z_0-9]+)"\]')
TIPOS_COM_AJUDA = (
    "number_input",
    "selectbox",
    "toggle",
    "checkbox",
    "radio",
    "text_input",
    "date_input",
    "button",
    "download_button",
    "metric",
    "subheader",
)
ISENTOS = {("text_input", "Nome do novo projeto")}


def _usadas(*arquivos: str) -> set[str]:
    usadas: set[str] = set()
    for arquivo in arquivos:
        usadas |= set(USO.findall((RAIZ / arquivo).read_text(encoding="utf-8")))
    return usadas


def test_ajuda_da_base_e_do_plano_toda_usada_e_existente():
    usadas = _usadas(
        BASE,
        PLANO,
        "components/base_tecnica_ui.py",
        "app_pages/inicio.py",
        "app_pages/guia_geral.py",
    )
    assert not (usadas - set(AJUDA)), sorted(usadas - set(AJUDA))
    assert not (set(AJUDA) - usadas), sorted(set(AJUDA) - usadas)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave


def test_ajuda_do_vento_aberto_toda_usada():
    usadas = _usadas("components/vento_aberto_ui.py", VENTO)
    assert usadas == set(vento_aberto_ui.AJUDA)


def _ajuda(elemento) -> str | None:
    proto = getattr(elemento, "proto", None)
    for campo in ("help", "tooltip"):
        for origem in (elemento, proto):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return None


def _rotulo(elemento) -> str:
    proto = getattr(elemento, "proto", None)
    for origem in (elemento, proto):
        for campo in ("label", "body"):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return repr(elemento)[:60]


def sem_ajuda(t: AppTest) -> set[tuple[str, str]]:
    return {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - ISENTOS


def abrir(pagina: str, **estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(pagina)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def gravar_no_projeto(**campos) -> dict:
    projeto = obter_projeto_ativo()
    projeto.update(campos)
    return salvar_projeto(projeto, motivo="teste")


def base_anglo() -> dict:
    return bt.para_dicionario(bt.base_do_cliente(bt.CLIENTE_ANGLO))


def metrica(t: AppTest, rotulo: str) -> str:
    return next(m.value for m in t.metric if m.label == rotulo)


# ------------------------------------------------------------------ “?” em todo campo
@pytest.mark.parametrize(
    ("pagina", "estado"),
    [
        pytest.param(BASE, {}, id="base"),
        pytest.param(BASE, {"bt_cliente": bt.CLIENTE_NENHUM}, id="base-sem-cliente"),
        pytest.param(PLANO, {}, id="plano"),
        pytest.param(VENTO, {}, id="vento"),
        pytest.param(VENTO, {"va_direcao": "Y", "ce_n_pisos": 2}, id="vento-y-dois-pisos"),
    ],
)
def test_todo_campo_tem_interrogacao_com_projeto(banco_com_projeto, pagina, estado):
    gravar_no_projeto(
        base_tecnica=base_anglo(),
        plano_de_cargas=pc.para_dicionario(
            pc.com_acao(pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("PP")), pc.nova_acao("W0"))
        ),
    )
    t = abrir(pagina, **estado)
    assert not sem_ajuda(t), sorted(sem_ajuda(t))


@pytest.mark.parametrize("pagina", [BASE, PLANO, VENTO])
def test_sem_projeto_a_pagina_abre_e_explica(banco_isolado, pagina):
    t = abrir(pagina)
    assert not sem_ajuda(t), sorted(sem_ajuda(t))


# ------------------------------------------------------------------ base técnica
def test_salvar_a_base_anglo_grava_no_projeto(banco_com_projeto):
    t = abrir(BASE)
    next(b for b in t.button if b.label == "Salvar a base técnica").click().run()
    assert not t.exception and not t.error
    base = bt.base_do_projeto(obter_projeto_ativo())
    assert base is not None and base.anglo and base.vento.s3 == ca.S3
    assert base.sobrecarga_kN_m2 == 5.0
    t.run()
    assert metrica(t, "Deslocamento do topo sob vento") == "H/400"
    assert any("0,95" in w.value for w in t.warning)


def test_consulta_do_criterio_funciona_sem_projeto(banco_isolado):
    t = abrir(BASE, bt_vib_ne=13.0, bt_vib_nm=10.0)
    assert metrica(t, "Situação") == "atende"
    assert "Critério Anglo — consulta" in [h.value for h in t.header]


# ------------------------------------------------------------------ plano de cargas
def test_plano_inclui_sobrecarga_e_temperatura_e_combina(banco_com_projeto):
    gravar_no_projeto(base_tecnica=base_anglo())
    t = abrir(PLANO)
    t.button(key="pc_incluir_sobrecarga").click().run()
    t.button(key="pc_incluir_temperatura").click().run()
    assert not t.exception
    plano = pc.plano_do_projeto(obter_projeto_ativo())
    assert plano.codigos == ("SC", "T+", "T−")
    assert plano.acao("SC").cargas[0].valor == 5.0
    subtitulos = [s.value for s in t.subheader]
    assert "Combinações" in subtitulos
    assert any("critério Anglo" in s for s in subtitulos)
    t.button(key="pc_remover_T+").click().run()
    assert pc.plano_do_projeto(obter_projeto_ativo()).codigos == ("SC", "T−")


def test_plano_sem_projeto_pede_um_projeto(banco_isolado):
    t = abrir(PLANO)
    assert any("Nenhum projeto ativo" in i.value for i in t.info)


# ------------------------------------------------------------------ vento em estruturas abertas
def _esperado(base: bt.BaseTecnica | None = None) -> va.ResultadoVentoAberto:
    from components.contraventamento_estrutura_ui import PILAR_PADRAO, VIGA_PADRAO
    from core import section_catalog as sc

    pilar, viga = sc.obter_perfil(PILAR_PADRAO), sc.obter_perfil(VIGA_PADRAO)
    e = cp.EntradaContraventamento(
        largura_pilar_m=max(pilar.altura_mm, pilar.largura_mm) / 1e3,
        altura_viga_m=viga.altura_mm / 1e3,
    )
    if base is not None:
        e = replace(
            e,
            vento=va.ParametrosVento(
                v0_m_s=base.vento.v0_m_s,
                s1=base.vento.s1,
                categoria=base.vento.categoria,
                grupo_s3=3,
                s3=base.vento.s3,
            ),
        )
    return va.calcular_vento_aberto(cp.geometria_do_vento(e), e.vento)


def _kN(valor: float) -> str:
    return f"{valor:.1f} kN".replace(".", ",")


def test_vento_aberto_mostra_o_que_o_nucleo_calcula(banco_isolado):
    t = abrir(VENTO)
    r = _esperado()
    assert metrica(t, "Vento em X") == _kN(r.x.total_kN)
    assert metrica(t, "Vento em Y") == _kN(r.y.total_kN)
    assert [tab.label for tab in t.tabs][:3] == ["Desenhos", "Forças por nível", "Forças nos nós"]


def test_vento_aberto_comeca_com_o_vento_da_base_anglo(banco_com_projeto):
    gravar_no_projeto(base_tecnica=base_anglo())
    t = abrir(VENTO)
    r = _esperado(bt.base_do_cliente(bt.CLIENTE_ANGLO))
    assert metrica(t, "Vento em X") == _kN(r.x.total_kN)
    assert any("0,95" in w.value for w in t.warning)
    sem_base = _esperado()
    assert r.x.total_kN == pytest.approx(sem_base.x.total_kN * (0.95 / vb.fator_s3(3)) ** 2)


def test_vento_aberto_vai_ao_plano_e_ao_registro(banco_com_projeto):
    t = abrir(VENTO, ce_tag="PL-3")
    t.button(key="va_para_plano").click().run()
    assert not t.exception
    plano = pc.plano_do_projeto(obter_projeto_ativo())
    assert plano.codigos == ("W0", "W90", "W180", "W270")
    assert plano.acao("W0").cargas and plano.acao("W180").cargas[0].valor < 0
    t.button(key="registrar_vento_estrutura_aberta").click().run()
    assert not t.exception
    achados = [
        r
        for r in obter_projeto_ativo()["registros_tecnicos"]
        if r["modulo_id"] == "vento_estrutura_aberta"
    ]
    assert len(achados) == 1 and achados[0]["entradas"]["tag"] == "PL-3"


# ------------------------------------------------------------------ outras páginas leem a base
def test_ligacao_liga_o_criterio_anglo_pela_base_e_desenha_a_chapa(banco_com_projeto):
    gravar_no_projeto(base_tecnica=base_anglo())
    t = abrir("app_pages/ligacao_contraventamento.py")
    assert t.toggle(key="cv_criterio_anglo").value is True
    assert "Desenho" in [tab.label for tab in t.tabs]
    textos = " ".join(str(d.value) for d in t.dataframe)
    assert "Anglo: espessura mínima da chapa de nó" in textos


def test_vento_nas_estruturas_usa_o_s3_do_cliente(banco_com_projeto):
    gravar_no_projeto(base_tecnica=base_anglo())
    t = abrir("app_pages/vento_nbr6123.py")
    assert t.toggle(key="vt_s3_cliente").value is True
    assert not sem_ajuda(t), sorted(sem_ajuda(t))
    assert any("critério do cliente" in c.value for c in t.caption)


def test_estruturas_de_aco_traz_as_acoes_do_plano(banco_com_projeto):
    plano = pc.PlanoDeCargas()
    for codigo in ("PP", "SC", "W0", "W180"):
        plano = pc.com_acao(plano, pc.nova_acao(codigo))
    gravar_no_projeto(plano_de_cargas=pc.para_dicionario(plano))
    t = abrir("app_pages/estruturas_aco.py", estrutura_aco_modulo="3. Combinações")
    t.button(key="estrutura_trazer_plano").click().run()
    assert not t.exception
    assert t.session_state["estrutura_acoes_versao"] == 1
    linhas = t.session_state["estrutura_acoes_do_plano"]
    assert [linha[0] for linha in linhas] == ["PP", "SC", "W0", "W180"]
    assert any("4 ações do plano de cargas" in c.value for c in t.caption)


# ------------------------------------------------------------------ guia e página inicial
@pytest.mark.parametrize(
    "capitulo", ["Base técnica do projeto", "Plano de cargas", "Vento em estruturas abertas"]
)
def test_guia_tem_os_capitulos_novos(banco_isolado, capitulo):
    t = abrir("app_pages/guia_geral.py", guia_modulo=capitulo)
    assert capitulo in [h.value for h in t.header]
    assert any("Resultado esperado" in c.value for c in t.caption)


def test_exemplo_do_guia_bate_com_o_que_a_pagina_mostra(banco_isolado):
    r = _esperado()
    guia = abrir("app_pages/guia_geral.py", guia_modulo="Vento em estruturas abertas")
    esperado = next(c.value for c in guia.caption if "Resultado esperado" in c.value)
    assert _kN(r.x.total_kN) in esperado and _kN(r.y.total_kN) in esperado
    pagina = abrir(VENTO)
    assert metrica(pagina, "Vento em X") == _kN(r.x.total_kN)


def test_todo_botao_de_ajuda_das_paginas_aponta_para_um_capitulo_do_guia():
    texto_guia = (RAIZ / "app_pages" / "guia_geral.py").read_text(encoding="utf-8")
    opcoes = re.search(r"opcoes = \[(.*?)\]", texto_guia, re.S).group(1)
    capitulos = set(re.findall(r'"([^"]+)"', opcoes))
    for pagina in (RAIZ / "app_pages").glob("*.py"):
        for alvo in re.findall(r'ajuda_modulo="([^"]+)"', pagina.read_text(encoding="utf-8")):
            assert alvo in capitulos, (pagina.name, alvo)


def test_pagina_inicial_mostra_o_caminho_do_projeto(banco_com_projeto):
    t = abrir("app_pages/inicio.py")
    assert "Caminho do projeto" in [s.value for s in t.subheader]
    corpo = " ".join(s.value for s in t.subheader)
    for titulo in ("Base técnica do projeto", "Plano de cargas", "Vento em estruturas abertas"):
        assert titulo in corpo, titulo
    opcoes = t.selectbox[0].options
    assert any("plano de cargas" in o.lower() for o in opcoes)


# ------------------------------------------------------------------ plano: conferência, edição e exportação
def _plano_completo_no_projeto() -> None:
    from tests.test_exportacao_cargas import plano_completo

    gravar_no_projeto(plano_de_cargas=pc.para_dicionario(plano_completo()))


def test_conferencia_do_plano_diz_o_que_falta(banco_com_projeto):
    gravar_no_projeto(
        plano_de_cargas=pc.para_dicionario(pc.com_acao(pc.PlanoDeCargas(), pc.nova_acao("W0")))
    )
    t = abrir(PLANO)
    avisos = " ".join(w.value for w in t.warning)
    assert "Sem PP" in avisos and "Vento incompleto" in avisos


def test_editar_traz_a_acao_gravada_e_gravar_mantem_a_origem(banco_com_projeto):
    _plano_completo_no_projeto()
    t = abrir(PLANO)
    t.button(key="pc_editar_SC").click().run()
    assert t.selectbox(key="pc_codigo").value == "SC"
    nome = next(i for i in t.text_input if i.key and i.key.startswith("pc_nome_SC_"))
    assert nome.value == "Sobrecarga de uso"
    # Num formulário o valor digitado só vale com o clique em gravar, na mesma execução.
    nome.set_value("Sobrecarga das plataformas")
    next(b for b in t.button if b.label == "Gravar a ação").click()
    t.run()
    assert not t.exception and not t.error
    sc = pc.plano_do_projeto(obter_projeto_ativo()).acao("SC")
    assert sc.nome == "Sobrecarga das plataformas" and sc.origem == "Informada"
    assert len(sc.cargas) == 1 and sc.cargas[0].valor == 5.0


def test_exportacao_mostra_as_cargas_nas_unidades_e_eixos_escolhidos(banco_com_projeto):
    from core import exportacao_cargas as ex

    _plano_completo_no_projeto()
    t = abrir(PLANO, pc_unidades=ex.UNIDADES_N_M.nome, pc_eixos=ex.EIXO_Y_PARA_CIMA)
    previa = next(d.value for d in t.dataframe if "Sentido" in d.value.columns)
    sc = previa[previa["Caso"] == "SC"].iloc[0]
    assert sc["Valor"] == 5000.0 and sc["Fy"] == -5000.0 and sc["Unidade"] == "N/m² (Pa)"
    w90 = previa[previa["Caso"] == "W90"].iloc[0]
    assert w90["Fz"] == -3000.0
    chaves = {b.key for b in t.get("download_button")}
    assert {"pc_xlsx", "pc_csv_cargas", "pc_csv_matriz", "pc_csv_lista", "pc_csv_acoes"} <= chaves
    assert "Convenção de eixos e sinais" in [s.value for s in t.subheader]


def test_combinacoes_em_matriz_ou_expressoes(banco_com_projeto):
    _plano_completo_no_projeto()
    t = abrir(PLANO)
    matriz = next(d.value for d in t.dataframe if "Combinação" in getattr(d.value, "columns", []))
    t2 = abrir(PLANO, pc_ver_como="Expressões")
    expressoes = next(
        d.value for d in t2.dataframe if "Expressão" in getattr(d.value, "columns", [])
    )
    assert len(matriz) == len(expressoes) > 0
