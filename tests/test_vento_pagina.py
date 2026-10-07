"""A página Vento nas estruturas, exercitada pela interface (AppTest), e os seus “?”.

Três contratos: (1) todo texto de ``components/wind_help.py`` é usado por algum campo e todo campo
usa um texto que existe; (2) todo campo da página — em cada estado que muda os campos — tem o seu
“?”; (3) a tela mostra o que o núcleo calcula (V_k, q, zonas, pórtico) e o registro leva a tabela
inteira para o projeto.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from components.wind_help import AJUDA
from core import vento_edificio as ve
from core import vento_nbr6123 as v6123
from core.project_store import obter_projeto_ativo

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
PAGINA = "app_pages/vento_nbr6123.py"
ARQUIVOS_COM_AJUDA = [
    RAIZ / "components" / "wind_ui.py",
    RAIZ / "app_pages" / "vento_nbr6123.py",
]
USO = re.compile(r'AJUDA\["([A-Za-z_0-9]+)"\]')


def _chaves_usadas() -> set[str]:
    usadas: set[str] = set()
    for arquivo in ARQUIVOS_COM_AJUDA:
        usadas |= set(USO.findall(arquivo.read_text(encoding="utf-8")))
    return usadas


def test_todo_campo_usa_um_texto_que_existe():
    inexistentes = _chaves_usadas() - set(AJUDA)
    assert not inexistentes, f"chaves sem texto em AJUDA: {sorted(inexistentes)}"


def test_nenhum_texto_de_ajuda_fica_sem_uso():
    orfaos = set(AJUDA) - _chaves_usadas()
    assert not orfaos, f"textos de ajuda que nenhum campo usa: {sorted(orfaos)}"


def test_textos_de_ajuda_sao_curtos_e_sem_marcas_de_rascunho():
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and len(texto) > 15, chave
        assert len(texto) <= 1300, f"{chave}: dica longa demais ({len(texto)} caracteres)"
        assert "TODO" not in texto and "XXX" not in texto, chave


@pytest.mark.parametrize(
    ("chave", "deve_citar"),
    [
        ("v0", ("isopletas", "3 segundos", "50 anos")),
        ("categoria", ("I", "II", "III", "IV", "V", "mar", "centro de grande cidade")),
        ("grupo", ("1,11", "1,06", "1,00", "0,95", "0,83")),
        ("classe", ("20 m", "50 m", "Anexo A")),
        ("permeabilidade", ("−0,3", "+0,2", "0")),
        ("h", ("beiral", "cumeeira")),
        ("a", ("cumeeira", "maior")),
        ("periodo", ("1 s", "dinâmico", "0,29")),
        ("alta_turb", ("2/3", "não aplica")),
        ("res_zonas", ("positiva empurra", "negativa puxa")),
        ("res_portico", ("normais", "sucção")),
        ("res_p_reacoes", ("segurando",)),
    ],
)
def test_dicas_para_quem_nao_conhece_o_termo_explicam_o_termo(chave, deve_citar):
    for trecho in deve_citar:
        assert trecho in AJUDA[chave], (chave, trecho)


FRASES_PROIBIDAS = ("sem valor normativo", "não tem valor normativo", "nao tem valor normativo")


def test_textos_do_vento_nao_falam_em_valor_normativo():
    for texto in (*AJUDA.values(), v6123.__doc__ or ""):
        for frase in FRASES_PROIBIDAS:
            assert frase not in texto.lower(), texto


# ------------------------------------------------------------------ a página na tela
TIPOS_COM_AJUDA = (
    "number_input",
    "selectbox",
    "toggle",
    "checkbox",
    "radio",
    "text_input",
    "button_group",
    "button",
    "download_button",
    "metric",
    "subheader",
)
ISENTOS_DE_AJUDA = {
    ("text_input", "Nome do novo projeto"),
}


def _ajuda_de(elemento) -> str | None:
    proto = getattr(elemento, "proto", None)
    for campo in ("help", "tooltip"):
        for origem in (elemento, proto):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return None


def _rotulo_de(elemento) -> str:
    proto = getattr(elemento, "proto", None)
    for origem in (elemento, proto):
        for campo in ("label", "body"):
            texto = getattr(origem, campo, None)
            if texto:
                return str(texto)
    return repr(elemento)[:60]


def sem_ajuda(teste: AppTest) -> set[tuple[str, str]]:
    faltam = set()
    for tipo in TIPOS_COM_AJUDA:
        for elemento in teste.get(tipo):
            if not _ajuda_de(elemento):
                faltam.add((tipo, _rotulo_de(elemento)))
    return faltam - ISENTOS_DE_AJUDA


def abrir(banco_isolado, **estado) -> AppTest:
    teste = AppTest.from_file(APP, default_timeout=180)
    teste.run()
    teste.switch_page(PAGINA)
    for chave, valor in estado.items():
        teste.session_state[chave] = valor
    teste.run()
    assert not teste.exception, [str(e.value) for e in teste.exception]
    return teste


def metrica(teste: AppTest, rotulo: str) -> str:
    return next(m.value for m in teste.metric if m.label == rotulo)


def tem_metrica(teste: AppTest, rotulo: str) -> bool:
    return any(m.label == rotulo for m in teste.metric)


def numero(texto: str) -> float:
    return float(texto.split()[0])


def tabela(teste: AppTest, coluna: str) -> pd.DataFrame:
    achadas = [d.value for d in teste.dataframe if coluna in d.value.columns]
    assert achadas, f"nenhuma tabela com a coluna {coluna!r}"
    return achadas[0]


ESTADOS = [
    pytest.param({}, id="padrao-duas-aguas"),
    pytest.param({"vt_cobertura": ve.COBERTURA_PLANA}, id="plana"),
    pytest.param({"vt_cobertura": ve.COBERTURA_UMA_AGUA, "vt_theta": 12.0}, id="uma-agua"),
    pytest.param(
        {"vt_relevo": "talude", "vt_theta_t": 12.0, "vt_z_t": 4.0, "vt_d_t": 30.0}, id="talude"
    ),
    pytest.param({"vt_s3_estat": True, "vt_pm": 0.5, "vt_ma": 25.0}, id="s3-anexo-b"),
    pytest.param({"vt_permeabilidade": "informado", "vt_cpis": "-0,3; 0,2"}, id="cpi-informado"),
    pytest.param({"vt_permeabilidade": "duas_faces_longas"}, id="duas-faces-permeaveis"),
    pytest.param({"vt_vizinhanca": True, "vt_s_viz": 8.0}, id="vizinhanca"),
    pytest.param(
        {"vt_alta_turb": True, "vt_h_viz": 12.0, "vt_ext_viz": 800.0}, id="alta-turbulencia"
    ),
    pytest.param({"vt_ad_posicao": "paralela"}, id="abertura-dominante-paralela"),
    pytest.param({"vt_p_bases": "Rotuladas"}, id="portico-rotulado"),
    pytest.param({"vt_a": 150.0}, id="comprimento-acima-de-a-b-4"),
]


@pytest.mark.parametrize("estado", ESTADOS)
def test_todo_campo_tem_interrogacao(banco_isolado, estado):
    t = abrir(banco_isolado, **estado)
    faltam = sem_ajuda(t)
    assert not faltam, f"campos sem “?”: {sorted(faltam)}"


def test_colunas_da_tabela_de_verificacoes_explicam_o_que_mostram(banco_isolado):
    import json

    from components.verification_table import AJUDA_COLUNAS

    t = abrir(banco_isolado)
    achada = next(d for d in t.dataframe if "Verificação" in d.value.columns)
    colunas = json.loads(achada.proto.columns)
    for coluna, texto in AJUDA_COLUNAS.items():
        assert colunas[coluna]["help"] == texto, coluna


# ------------------------------------------------------------------ o que a tela mostra
def _padrao() -> ve.ResultadoEdificio:
    """O que a página calcula com os valores padrão dos campos."""
    return ve.calcular_edificacao(
        ve.EntradaEdificio(
            v0_m_s=35.0,
            comprimento_a_m=60.0,
            largura_b_m=30.0,
            altura_h_m=8.0,
            cobertura=ve.COBERTURA_DUAS_AGUAS,
            theta_graus=10.0,
            categoria="III",
            grupo_s3=3,
            espacamento_porticos_m=6.0,
        )
    )


def test_resumo_da_tela_bate_com_o_nucleo(banco_isolado):
    esperado = _padrao()
    t = abrir(banco_isolado)
    for alpha in (0, 90):
        classe = esperado.classe_por_alpha[alpha]
        assert metrica(t, f"V_k a {alpha}° (classe {classe})") == (
            f"{esperado.vento_por_alpha[alpha].vk_m_s:.2f} m/s"
        )
        assert metrica(t, f"q a {alpha}°") == f"{esperado.vento_por_alpha[alpha].q_kN_m2:.3f} kN/m²"
    assert metrica(t, "q das vedações") == f"{esperado.vento_vedacoes.q_kN_m2:.3f} kN/m²"


def test_tabela_de_zonas_traz_as_zonas_do_telhado_e_das_paredes(banco_isolado):
    t = abrir(banco_isolado)
    zonas = tabela(t, "Zona")
    assert {"A1 e B1", "C (barlavento)", "E e G", "I e J"} <= set(zonas["Zona"])
    assert "Δp = q·(C_e − c_pi) (kN/m²)" in zonas.columns


def test_trocar_o_caso_de_vento_troca_a_tabela(banco_isolado):
    t = abrir(banco_isolado)
    casos = [c.nome for c in _padrao().casos]
    assert len(casos) == 4
    t.selectbox(key="vt_res_caso").select(casos[2]).run()
    assert not t.exception
    zonas = tabela(t, "Zona")
    assert "E, F e I (barlavento)" in set(zonas["Zona"])  # vento a 90°


def test_desenho_da_planta_aparece(banco_isolado):
    t = abrir(banco_isolado)
    assert len(t.get("image")) == 1  # a planta com as zonas, em SVG


def test_tela_avisa_quando_a_geometria_sai_do_campo_da_norma(banco_isolado):
    t = abrir(banco_isolado, vt_a=150.0)
    assert any(
        "1 ≤ a/b ≤ 4" in str(d.value["Verificação"].tolist())
        for d in t.dataframe
        if "Verificação" in d.value.columns
    )
    assert any(
        d.value["Status"].eq("ALERTA").any() for d in t.dataframe if "Status" in d.value.columns
    )


def test_comprimento_menor_que_a_largura_vira_erro_claro(banco_isolado):
    t = abrir(banco_isolado, vt_a=20.0, vt_b=30.0)
    assert any("maior ou igual à largura" in e.value for e in t.error)
    assert not tem_metrica(t, "q a 0°")


def test_cpis_informados_geram_um_caso_por_valor(banco_isolado):
    t = abrir(banco_isolado, vt_permeabilidade="informado", vt_cpis="0,2; -0,4; 0")
    casos = [o for o in t.selectbox(key="vt_res_caso").options]
    assert len([c for c in casos if c.startswith("Vento a 0°")]) == 3 and len(casos) == 6
    t2 = abrir(banco_isolado, vt_permeabilidade="informado", vt_cpis="abc")
    assert any("c_pi inválido" in e.value for e in t2.error)


def test_assistente_de_abertura_dominante_copia_o_cpi(banco_isolado):
    t = abrir(banco_isolado, vt_ad_posicao="barlavento", vt_ad_razao=2.0)
    t.button(key="vt_ad_usar").click().run()
    assert not t.exception
    assert t.selectbox(key="vt_permeabilidade").value == "informado"
    assert t.text_input(key="vt_cpis").value == "0,50"


def test_s3_do_anexo_b_nunca_fica_abaixo_do_grupo(banco_isolado):
    t = abrir(banco_isolado, vt_s3_estat=True, vt_pm=0.5, vt_ma=25.0)
    assert any("abaixo do mínimo do grupo" in w.value for w in t.warning)
    com_folga = abrir(banco_isolado, vt_s3_estat=True, vt_pm=0.1, vt_ma=100.0)
    assert not any("abaixo do mínimo" in w.value for w in com_folga.warning)
    # S3 maior → q maior que o do grupo 3 puro.
    base = abrir(banco_isolado)
    assert numero(metrica(com_folga, "q a 0°")) > numero(metrica(base, "q a 0°"))


def test_portico_mostra_reacoes_e_equilibra_com_as_cargas(banco_isolado):
    t = abrir(banco_isolado)
    reacoes = tabela(t, "Rh (kN)")
    assert len(reacoes) == 2
    assert tem_metrica(t, "Deslocamento horizontal máximo")
    assert tem_metrica(t, "Deslocamento vertical máximo")
    cargas = tabela(t, "Pilar esq. (kN/m)")
    assert len(cargas) == 8  # a 0° em 3 faixas e a 90°, cada um com dois c_pi
    assert {"Água esq. (kN/m)", "Água dir. (kN/m)", "Pilar dir. (kN/m)"} <= set(cargas.columns)


def test_portico_aceita_perfil_do_catalogo(banco_isolado):
    from core import section_catalog as catalogo

    nome = next(n for n in sorted(catalogo.listar_perfis()) if n.startswith("W "))
    t = abrir(banco_isolado, vt_p_perfil_pilar=nome, vt_p_perfil_rafter=nome)
    assert any(nome in c.value for c in t.caption)
    assert not sem_ajuda(t)


def test_baixar_csv_tem_ajuda(banco_isolado):
    t = abrir(banco_isolado)
    botoes = [b for b in t.get("download_button") if b.proto.label.startswith("Baixar")]
    assert len(botoes) >= 4 and all(b.proto.help for b in botoes)


# ------------------------------------------------------------------ registro no projeto
def test_registrar_grava_o_calculo_com_a_tabela_e_as_tabelas_do_memorial(banco_com_projeto):
    t = abrir(banco_com_projeto)
    t.button(key="registrar_vento_nbr6123").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    registros = [
        r for r in obter_projeto_ativo()["registros_tecnicos"] if r["modulo_id"] == "vento_nbr6123"
    ]
    assert len(registros) == 1
    registro = registros[0]
    assert registro["entradas"]["v0_m_s"] == 35.0
    assert registro["resultados"]["status_geral"] == "OK"
    assert len(registro["resultados"]["verificações"]) >= 15
    assert len(registro["resultados"]["tabelas_memorial"]) >= 3
    assert "q = " in registro["resultados"]["destaque_memorial"]
    assert registro["status"] == "Calculado"
    assert any("V_k" in str(eq) for eq in registro["equacoes"])


# ------------------------------------------------------------------ o guia
def test_guia_tem_o_capitulo_do_vento_com_exemplo_calculado_pelo_nucleo(banco_isolado):
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page("app_pages/guia_geral.py")
    t.session_state["guia_modulo"] = "Vento nas estruturas"
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    assert any(h.value == "Vento nas estruturas" for h in t.header)
    # O guia usa V₀ = 40 m/s (a página, 35): o exemplo é conferido pelo próprio núcleo.
    exemplo = ve.calcular_edificacao(
        ve.EntradaEdificio(
            v0_m_s=40.0,
            comprimento_a_m=60.0,
            largura_b_m=30.0,
            altura_h_m=8.0,
            cobertura=ve.COBERTURA_DUAS_AGUAS,
            theta_graus=10.0,
            categoria="III",
            grupo_s3=3,
            espacamento_porticos_m=6.0,
        )
    )
    q0 = f"{exemplo.vento_por_alpha[0].q_kN_m2:.3f}".replace(".", ",")
    textos = " ".join(m.value for m in t.markdown) + " ".join(c.value for c in t.caption)
    assert f"q = {q0} kN/m²" in textos
