"""Guarda-corpo nas bordas do piso pela interface: Cargas do esqueleto e o vento barra a barra."""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from components import vento_aberto_ui
from components.guarda_corpo_help import AJUDA
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core.project_store import obter_projeto_ativo, salvar_projeto
from tests.test_esforcos_modelo_pagina import TIPOS_COM_AJUDA, _ajuda, _rotulo
from tests.test_guarda_corpo_do_modelo import plataforma

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")


def test_todo_texto_de_ajuda_e_usado():
    usadas = set(
        re.findall(
            r'AJUDA\["([A-Za-z_0-9]+)"\]',
            (RAIZ / "components/guarda_corpo_ui.py").read_text(encoding="utf-8"),
        )
    )
    assert usadas == set(AJUDA)
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and 15 < len(texto) <= 900, chave


def _com_esqueleto(**extra) -> None:
    projeto = obter_projeto_ativo()
    projeto["geometria_do_modelo"] = ld.para_dicionario(
        ld.GeometriaDoModelo(corpos=tuple(plataforma()), arquivo="plataforma_esqueleto.csv")
    )
    projeto.update(extra)
    salvar_projeto(projeto, motivo="teste")


def abrir(pagina: str, **estado) -> AppTest:
    t = AppTest.from_file(APP, default_timeout=180)
    t.run()
    t.switch_page(pagina)
    for chave, valor in estado.items():
        t.session_state[chave] = valor
    t.run()
    assert not t.exception, [str(e.value) for e in t.exception]
    return t


def test_bloco_mostra_as_bordas_com_ajuda_e_poe_o_peso_no_pe(banco_com_projeto):
    _com_esqueleto()
    t = abrir("app_pages/cargas_esqueleto.py")
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    metricas = {m.label: m.value for m in t.metric}
    assert metricas["Com guarda-corpo"] == "20,00 m"
    assert metricas["Bordas"] == "pelas chapas do piso"
    assert "Guarda-corpo nas bordas do piso" in [s.value for s in t.subheader]
    t.button(key="gc_enviar").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    salvo = obter_projeto_ativo()
    pe = pc.plano_do_projeto(salvo).acao("PE")
    linhas = [c for c in pe.cargas if gm.e_linha_de_guarda_corpo(c)]
    assert len(linhas) == 4
    assert sum(c.resultante for c in linhas) == gm.PESO_PADRAO_KN_M * 20.0
    assert gm.CHAVE_DO_PROJETO in salvo


def test_trecho_desmarcado_fica_fora_da_conta_e_do_vento(banco_com_projeto):
    b = gm.bordas_do_piso(ld.GeometriaDoModelo(corpos=tuple(plataforma())), "Y")
    z0 = next(t for t in b.trechos if t.viga == "Borda z0")
    escolha = gm.EscolhaDoGuardaCorpo({z0.chave: False}, altura_m=1.3)
    _com_esqueleto(**{gm.CHAVE_DO_PROJETO: gm.para_dicionario(escolha, b)})
    t = abrir("app_pages/cargas_esqueleto.py")
    assert {m.label: m.value for m in t.metric}["Com guarda-corpo"] == "14,00 m"
    v = abrir(
        "app_pages/vento_estrutura_aberta.py",
        va_metodo=vento_aberto_ui.METODO_BARRAS,
    )
    assert any("3 guarda-corpos nas bordas" in c.value for c in v.caption)
    elementos = next(d.value for d in v.dataframe if "Vai para" in d.value.columns)
    assert sorted(elementos["Elemento"]) == sorted(
        f"GC {t.id}" for t in b.trechos if t.viga != "Borda z0"
    )


def test_ajustes_a_mao_e_chaves_da_escada_pela_pagina(banco_com_projeto):
    escolha = gm.EscolhaDoGuardaCorpo(
        acesso_pelas_longarinas=False, a_mao=(gm.TrechoAMao("Interna x3"),)
    )
    _com_esqueleto(**{gm.CHAVE_DO_PROJETO: gm.para_dicionario(escolha)})
    t = abrir("app_pages/cargas_esqueleto.py")
    sem_ajuda = {
        (tipo, _rotulo(e)) for tipo in TIPOS_COM_AJUDA for e in t.get(tipo) if not _ajuda(e)
    } - {("text_input", "Nome do novo projeto")}
    assert not sem_ajuda, sorted(sem_ajuda)
    assert {m.label: m.value for m in t.metric}["Com guarda-corpo"] == "24,00 m"
    assert any("trechos M" in c.value for c in t.caption)
    chave = next(tg for tg in t.toggle if tg.label.startswith("Achar o acesso"))
    assert chave.value is False
    t.button(key="gc_enviar").click().run()
    assert not t.exception, [str(e.value) for e in t.exception]
    salvo = gm.escolha_do_projeto(obter_projeto_ativo())
    assert salvo.a_mao == escolha.a_mao and not salvo.acesso_pelas_longarinas
    pe = pc.plano_do_projeto(obter_projeto_ativo()).acao("PE")
    assert any("Interna x3" in c.elemento for c in pe.cargas if gm.e_linha_de_guarda_corpo(c))
