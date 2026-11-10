"""O tratamento automático da leitura do modelo (core/tratamento_do_modelo.py).

Com o pórtico espacial de teste (tests/portico_3d_teste01.py): cada erro de leitura que tem prova
nos próprios arquivos é consertado sozinho, o que está gravado não muda, e o que o tratamento não
alcança continua no painel "Antes de verificar".
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from core import apoios_do_modelo as am
from core import diagnostico as dg
from core import diagnostico_do_modelo as dm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import quadro_fundacoes as qf
from core import tratamento_do_modelo as tm
from tests import portico_3d_teste01 as t
from tests.test_nucleo_esforcos_ponta_a_ponta import dados_estragados, diagnostico, montar


def tratar(dados, apoios, geometria) -> tm.ModeloTratado:
    return tm.tratar(dados, apoios, t.plano(), geometria)


def _titulos(tratado: tm.ModeloTratado) -> list[str]:
    return [x.titulo for x in tratado.tratamentos]


def _painel(tratado: tm.ModeloTratado) -> dm.Diagnostico:
    return diagnostico(tratado.dados, tratado.apoios, tratado.geometria)


def _mesmos_numeros(a: em.CasoImportado, b: em.CasoImportado, tolerancia: float = 2e-3) -> None:
    assert set(a.membros) == set(b.membros)
    for barra, pontos in a.membros.items():
        for p, q in zip(pontos, b.membros[barra], strict=True):
            assert p.chave == q.chave
            assert p.vetor() == pytest.approx(q.vetor(), abs=tolerancia), (barra, p.chave)
    assert a.reacoes is not None and b.reacoes is not None
    assert a.reacoes.modelo == pytest.approx(b.reacoes.modelo, abs=tolerancia)


# ------------------------------------------------------------------ nada a tratar
def test_modelo_certo_passa_sem_mudar_nada():
    dados, apoios, geometria = montar()
    tratado = tratar(dados, apoios, geometria)
    assert tratado.tratamentos == () and tratado.falhas == ()
    assert tratado.dados is dados and tratado.apoios is apoios  # nem cópia
    assert tratado.para_gravar(tratado.dados) is dados and tratado.apoios_para_gravar is None
    assert tm.achados(tratado) == [] and tm.resumo(tratado) == ""


def test_sem_casos_importados_nao_ha_o_que_tratar():
    vazio = tm.tratar(em.EsforcosDoModelo())
    assert vazio.tratamentos == () and vazio.dados.casos == {}
    assert tm.do_projeto(None).tratamentos == () and tm.do_projeto({}).dados.casos == {}


# ------------------------------------------------------------------ 0. escala das reações
def _com_a_reacao_vezes(dados: em.EsforcosDoModelo, caso: str, fator: float):
    r = dados.casos[caso].reacoes
    errada = em.Reacoes(
        tuple(v * fator for v in r.modelo),
        tuple(v * fator for v in r.selecao) if r.selecao else None,
        tuple(v * fator for v in r.momento_modelo) if r.momento_modelo else None,
    )
    return em.com_reacoes(dados, caso, errada, dados.casos[caso].arquivo_reacoes)


@pytest.mark.parametrize("fator", [0.001, 1000.0])
@pytest.mark.parametrize("caso", ["SC", "W0"])
def test_reacao_mil_vezes_fora_e_corrigida_pelos_apoios(caso, fator):
    dados, apoios, geometria = montar()
    tratado = tratar(_com_a_reacao_vezes(dados, caso, fator), apoios, geometria)
    assert [x.codigo for x in tratado.tratamentos] == [tm.T_ESCALA]
    assert tratado.tratamentos[0].onde == (caso,)
    assert tratado.dados.casos[caso].reacoes.modelo == pytest.approx(
        dados.casos[caso].reacoes.modelo, abs=1e-9
    )
    assert _painel(tratado).tudo_certo


def test_sem_os_apoios_a_escala_sai_das_bases_dos_pilares():
    dados, apoios, geometria = montar(com_apoios=False)
    tratado = tratar(_com_a_reacao_vezes(dados, "SC", 0.001), apoios, geometria)
    assert [x.codigo for x in tratado.tratamentos] == [tm.T_ESCALA]
    assert "bases dos pilares" in tratado.tratamentos[0].texto
    assert tratado.dados.casos["SC"].reacoes.modelo == pytest.approx(
        dados.casos["SC"].reacoes.modelo, abs=1e-9
    )
    # No vento a vertical é zero: pelas bases não há prova, e a reação fica como veio.
    vento = tratar(_com_a_reacao_vezes(dados, "W0", 0.001), apoios, geometria)
    assert not vento.tratou(tm.T_ESCALA)


def test_reacao_diferente_que_nao_e_fator_de_mil_fica_para_o_painel():
    dados, apoios, geometria = montar()
    tratado = tratar(_com_a_reacao_vezes(dados, "SC", 1.4), apoios, geometria)
    assert not tratado.tratou(tm.T_ESCALA)
    assert not _painel(tratado).tudo_certo


# ------------------------------------------------------------------ 1. reação pelos apoios
def test_reacao_que_falta_e_a_soma_dos_apoios_da_macro():
    dados, apoios, geometria = montar()
    sem = replace(
        dados,
        casos={
            k: replace(c, reacoes=None, arquivo_reacoes="") if k in ("PP", "W0") else c
            for k, c in dados.casos.items()
        },
    )
    tratado = tratar(sem, apoios, geometria)
    assert tratado.tratou(tm.T_REACOES) and tratado.tratamentos[0].onde == ("PP", "W0")
    for codigo in ("PP", "W0"):
        caso = tratado.dados.casos[codigo]
        assert caso.arquivo_reacoes == tm.ARQUIVO_PELOS_APOIOS
        assert caso.reacoes.modelo == pytest.approx(dados.casos[codigo].reacoes.modelo, abs=1e-5)
    assert _painel(tratado).tudo_certo
    # Sem os apoios da macro não há de onde tirar: o caso fica sem a reação.
    sem_macro = tm.tratar(sem, None, t.plano(), geometria)
    assert not sem_macro.tratou(tm.T_REACOES) and sem_macro.dados.casos["PP"].reacoes is None


# ------------------------------------------------------------------ 2. eixo vertical
def test_eixo_vertical_trocado_e_achado_pelo_peso_do_pp():
    dados, apoios, geometria = montar()
    tratado = tratar(replace(dados, eixo_vertical="Z"), apoios, geometria)
    assert _titulos(tratado) == ["Eixo vertical do modelo"]
    assert tratado.dados.eixo_vertical == "Y" and tratado.bruto.eixo_vertical == "Z"
    assert tratado.tratamentos[0].confianca == tm.CERTO
    assert _painel(tratado).tudo_certo
    assert tm.eixo_vertical_provado(dados, t.plano()) == "Y"
    # Sem o PP (ou sem a reação dele) não há prova: o eixo gravado fica.
    sem_pp = replace(dados, eixo_vertical="Z", casos={"W0": dados.casos["W0"]})
    assert tm.tratar(sem_pp, None, t.plano(), geometria).dados.eixo_vertical == "Z"


def test_eixo_vertical_sem_o_arquivo_de_reacoes_sai_dos_apoios():
    dados, apoios, geometria = montar()
    sem = replace(
        dados,
        eixo_vertical="Z",
        casos={k: replace(c, reacoes=None, arquivo_reacoes="") for k, c in dados.casos.items()},
    )
    tratado = tratar(sem, apoios, geometria)
    assert tratado.tratou(tm.T_REACOES) and tratado.tratou(tm.T_EIXO)
    assert tratado.dados.eixo_vertical == "Y" and _painel(tratado).tudo_certo


# ------------------------------------------------------------------ 3. nomes dos ventos
def test_ventos_com_os_nomes_trocados_vao_para_o_caso_certo():
    trocar = {"W90": "W270", "W270": "W90"}
    dados, apoios, geometria = montar(forcas=trocar, reacoes=trocar, apoios_de=trocar)
    assert not diagnostico(dados, apoios, geometria).tudo_certo
    tratado = tratar(dados, apoios, geometria)
    assert tratado.renomeados == trocar and tratado.tratou(tm.T_VENTOS)
    # O que foi enviado como W90 é o W270 de verdade.
    assert tratado.dados.casos["W270"].arquivo == "W90-forcas.csv"
    assert tratado.apoios.casos["W270"].arquivo == "W90-apoios.csv"
    certo, _, _ = montar()
    _mesmos_numeros(tratado.dados.casos["W270"], certo.casos["W270"], 1e-9)
    assert _painel(tratado).tudo_certo
    # Ao gravar, esforços e apoios vão juntos com os nomes certos.
    assert tratado.para_gravar(tratado.dados) is tratado.dados
    a_gravar = tratado.apoios_para_gravar
    assert a_gravar is not None and a_gravar.casos["W270"].arquivo == "W90-apoios.csv"
    # Gravado assim, não há mais o que tratar.
    assert tratar(tratado.dados, a_gravar, geometria).tratamentos == ()


# ------------------------------------------------------------------ 4. gravidade junto
@pytest.mark.parametrize("caso", ["W0", "SC"])
def test_gravidade_junto_e_descontada_ponto_a_ponto(caso):
    junto = {caso: f"PP+{caso}"}
    dados, apoios, geometria = montar(forcas=junto, reacoes=junto, apoios_de=junto)
    assert f"{caso}: ficou com a gravidade" in [
        a.titulo for a in diagnostico(dados, apoios, geometria).achados
    ]
    assert tm.casos_com_a_gravidade_junto(dados, t.plano()) == [caso]
    tratado = tratar(dados, apoios, geometria)
    assert tratado.recalculados == {caso} and tratado.tratou(tm.T_GRAVIDADE)
    certo, apoios_certos, _ = montar()
    _mesmos_numeros(tratado.dados.casos[caso], certo.casos[caso])
    for no, esperado in zip(
        tratado.apoios.casos[caso].nos, apoios_certos.casos[caso].nos, strict=True
    ):
        assert no.forca_N == pytest.approx(esperado.forca_N, abs=0.01)
        assert no.momento_Nm == pytest.approx(esperado.momento_Nm, abs=0.01)
    # Muda números: vai para o painel como item para conferir, não como erro.
    (a_conferir,) = tm.achados(tratado)
    assert a_conferir.nivel == dm.NIVEL_ATENCAO and "descontada" in a_conferir.titulo
    painel = _painel(tratado)
    assert painel.erros == 0, [a.titulo for a in painel.achados]
    # O que se grava são os números do arquivo, não os descontados.
    a_gravar = tratado.para_gravar(tratado.dados)
    assert a_gravar.casos[caso].membros is dados.casos[caso].membros
    assert a_gravar.casos[caso].reacoes is dados.casos[caso].reacoes
    assert a_gravar.casos["PP"] is dados.casos["PP"]


def test_gravidade_descontada_e_arquivo_novo_ao_gravar():
    junto = {"W0": "PP+W0"}
    dados, apoios, geometria = montar(forcas=junto, reacoes=junto, apoios_de=junto)
    tratado = tratar(dados, apoios, geometria)
    # A página trocou o arquivo de forças do caso: vale o novo, não o gravado antes.
    novo = em.caso_do_arquivo(em.ler_arquivo(t.csv_forcas("W0"), "W0-forcas.csv"), "W0")
    editado = em.com_caso(tratado.dados, novo)
    assert tratado.para_gravar(editado).casos["W0"].membros is editado.casos["W0"].membros
    # Só as reações novas: as forças voltam a ser as do arquivo, as reações ficam as novas.
    lidas = em.ler_arquivo(t.csv_reacoes("W0"), "W0-reacoes.csv").reacoes
    com_reacoes = em.com_reacoes(tratado.dados, "W0", lidas, "W0-reacoes.csv")
    gravado = tratado.para_gravar(com_reacoes).casos["W0"]
    assert gravado.membros is dados.casos["W0"].membros and gravado.reacoes is lidas


def test_so_a_reacao_a_mais_sem_o_peso_nos_pilares_nao_e_gravidade():
    # A reação do W0 tem o peso do PP a mais, mas as forças são as do W0 puro: sem a segunda
    # prova (a normal variando dentro dos pilares como no PP) o programa não desconta nada.
    dados, apoios, geometria = montar(reacoes={"W0": "PP+W0"}, com_apoios=False)
    assert tm.casos_com_a_gravidade_junto(dados, t.plano()) == []
    assert not tratar(dados, apoios, geometria).tratou(tm.T_GRAVIDADE)


def test_caso_majorado_nao_e_tratado():
    vezes = {"SC": "1.4*SC"}
    dados, apoios, geometria = montar(forcas=vezes, reacoes=vezes, apoios_de=vezes)
    tratado = tratar(dados, apoios, geometria)
    assert tratado.tratamentos == ()
    assert "SC: problema no estudo" in [a.titulo for a in _painel(tratado).achados]


def test_gravidade_com_apoios_de_nos_diferentes_sai_pelos_pilares():
    junto = {"W0": "PP+W0"}
    dados, apoios, geometria = montar(forcas=junto, reacoes=junto, apoios_de=junto)
    outros_nos = replace(
        apoios.casos["W0"],
        nos=tuple(replace(no, no=no.no + 1000) for no in apoios.casos["W0"].nos),
    )
    tratado = tratar(dados, am.com_caso(apoios, outros_nos), geometria)
    assert "W0" not in tratado.apoios.casos and "W0" in tratado.apoios_brutos.casos
    assert "ficaram de fora" in tratado.a_conferir[0].texto


# ------------------------------------------------------------------ 5. tabela das barras
def test_barras_sem_tipo_ganham_o_da_posicao_no_modelo():
    dados, apoios, geometria = montar()
    sem_tipo = em.com_membros(dados, {b: replace(c, tipo="—") for b, c in dados.membros.items()})
    assert not qf.montar_quadro(sem_tipo).pilares
    tratado = tratar(sem_tipo, apoios, geometria)
    assert "Tipo das barras" in _titulos(tratado)
    assert {b: c.tipo for b, c in tratado.dados.membros.items()} == {
        b.viga: "Pilar" if b.perfil == t.PILAR else "Viga" for b in t.BARRAS
    }
    assert len(qf.montar_quadro(tratado.dados).pilares) == 4
    # Os comprimentos de flambagem não entram: continuam vazios (valem os do tipo).
    assert all(
        c.lx_m is None and c.ly_m is None and c.lb_m is None for c in tratado.dados.membros.values()
    )
    # Sem o esqueleto, o tipo sai da leitura dos esforços no peso próprio.
    pelos_esforcos = tm.tratar(sem_tipo, apoios, t.plano(), None)
    assert sum(c.tipo == "Pilar" for c in pelos_esforcos.dados.membros.values()) == 4
    assert "leitura dos esforços" in pelos_esforcos.tratamentos[-1].texto


def test_tipo_escolhido_pelo_usuario_nao_e_trocado():
    dados, apoios, geometria = montar()
    pilar = t.BARRAS[0].viga
    escolhido = em.com_membros(dados, {pilar: replace(dados.membros[pilar], tipo="Outro")})
    tratado = tratar(escolhido, apoios, geometria)
    assert tratado.dados.membros[pilar].tipo == "Outro" and "Tipo das barras" not in _titulos(
        tratado
    )


def test_eixo_forte_contra_a_secao_e_perfil_vazio_sao_corrigidos():
    dados, apoios, geometria = montar()
    leituras = {lb.barra: lb for lb in ld.ler_barras(dados, geometria, t.plano())}
    certos = [b for b, lb in leituras.items() if lb.origem_do_eixo in ld.EIXOS_CERTOS]
    assert certos, "o esqueleto do pórtico de teste dá o eixo forte pela seção"
    barra = certos[0]
    outro = em.EIXO_M1 if dados.membros[barra].eixo_forte == em.EIXO_M2 else em.EIXO_M2
    errado = em.com_membros(
        dados, {barra: replace(dados.membros[barra], eixo_forte=outro, perfil="")}
    )
    tratado = tratar(errado, apoios, geometria)
    assert {"Eixo forte das barras", "Perfil das barras"} <= set(_titulos(tratado))
    assert tratado.dados.membros[barra].eixo_forte == dados.membros[barra].eixo_forte
    assert tratado.dados.membros[barra].perfil == dados.membros[barra].perfil
    assert "Eixo forte trocado" not in [a.titulo for a in _painel(tratado).achados]


# ------------------------------------------------------------------ 6. base do pilar
def test_base_escolhida_na_ponta_de_cima_volta_para_a_automatica():
    dados, apoios, geometria = montar()
    pilar = t.BARRAS[0].viga  # listado do pé para o topo: Fim da lista é a ponta de cima
    errado = em.com_membros(dados, {pilar: replace(dados.membros[pilar], base=em.BASE_FIM)})
    assert qf.montar_quadro(errado).de_ponta_cabeca
    tratado = tratar(errado, apoios, geometria)
    assert _titulos(tratado) == ["Base do pilar escolhida na ponta de cima"]
    assert tratado.dados.membros[pilar].base == em.BASE_AUTOMATICA
    quadro = qf.montar_quadro(tratado.dados)
    assert not quadro.de_ponta_cabeca and not quadro.pendentes
    assert _painel(tratado).tudo_certo
    # A base escolhida na ponta certa fica como o usuário pôs.
    certo = em.com_membros(dados, {pilar: replace(dados.membros[pilar], base=em.BASE_INICIO)})
    assert tratar(certo, apoios, geometria).tratamentos == ()


# ------------------------------------------------------------------ vários de uma vez
def test_varios_erros_juntos_saem_tratados_na_ordem():
    trocar = {"W90": "W270", "W270": "W90"}
    dados, apoios, geometria = montar(forcas=trocar, reacoes=trocar, apoios_de=trocar)
    pilar = t.BARRAS[0].viga
    dados = replace(
        em.com_membros(
            dados,
            {
                **{b: replace(c, tipo="—") for b, c in dados.membros.items()},
                pilar: replace(dados.membros[pilar], tipo="—", base=em.BASE_FIM),
            },
        ),
        eixo_vertical="Z",
        casos={
            k: replace(c, reacoes=None, arquivo_reacoes="") if k == "SC" else c
            for k, c in dados.casos.items()
        },
    )
    tratado = tratar(dados, apoios, geometria)
    assert [x.codigo for x in tratado.tratamentos] == [
        tm.T_REACOES,
        tm.T_EIXO,
        tm.T_VENTOS,
        tm.T_TABELA,
        tm.T_BASE,
    ]
    assert all(x.confianca == tm.CERTO for x in tratado.tratamentos)
    assert _painel(tratado).tudo_certo and tm.achados(tratado) == []
    assert "tratou sozinho 5 ponto(s)" in tm.resumo(tratado)
    # Tratar o que já foi tratado não muda mais nada.
    de_novo = tratar(tratado.dados, tratado.apoios_para_gravar, geometria)
    assert de_novo.tratamentos == ()


# ------------------------------------------------------------------ robustez
def test_tratamento_que_falha_nao_derruba_os_outros(banco_isolado, monkeypatch):
    monkeypatch.delenv(dg.VARIAVEL_MODO, raising=False)
    dados, apoios, geometria = montar()
    pilar = t.BARRAS[0].viga
    dados = replace(
        em.com_membros(dados, {pilar: replace(dados.membros[pilar], base=em.BASE_FIM)}),
        eixo_vertical="Z",
    )

    def quebra(*_args, **_kwargs):
        raise ZeroDivisionError("teste")

    monkeypatch.setattr(tm.em, "mapa_de_nomes_dos_ventos", quebra)
    tratado = tratar(dados, apoios, geometria)
    assert [x.codigo for x in tratado.tratamentos] == [tm.T_EIXO, tm.T_BASE]  # os outros rodaram
    (falha,) = tratado.falhas
    assert falha.startswith("nomes dos ventos (ref. ")
    (achado,) = tm.achados(tratado)
    assert achado.nivel == dm.NIVEL_ATENCAO and "Não deu para tratar sozinho" in achado.titulo
    assert any(o["referencia"] in falha for o in dg.ler())


def test_com_o_modo_levantar_a_falha_do_tratamento_sobe(monkeypatch):
    dados, apoios, geometria = montar()

    def quebra(*_args, **_kwargs):
        raise ZeroDivisionError("teste")

    monkeypatch.setattr(tm.qf, "montar_quadro", quebra)
    with pytest.raises(ZeroDivisionError):
        tratar(dados, apoios, geometria)


@pytest.mark.parametrize("semente", range(40))
def test_dados_estragados_nunca_quebram_o_tratamento(semente):
    """Casos com números aleatórios, sem reações, sem barras ou cortados: o tratamento sempre
    sai (o modo levantar está ligado, então nada pode falhar), o gravado não muda e o painel roda
    com o resultado."""
    dados, apoios, geometria, plano = dados_estragados(semente)
    tratado = tm.tratar(dados, apoios, plano, geometria)
    assert tratado.bruto is dados and tratado.apoios_brutos is apoios and tratado.falhas == ()
    assert set(tratado.dados.casos) == set(dados.casos)
    assert all(x.titulo and x.texto for x in tratado.tratamentos)
    gravavel = tratado.para_gravar(tratado.dados)
    assert set(gravavel.casos) == set(dados.casos)
    diagnostico(tratado.dados, tratado.apoios, geometria, plano)


def test_vento_salvo_com_o_nome_do_pp_nao_vira_o_eixo_do_modelo():
    # O erro clássico de salvar sem trocar o caso: o "PP" tem os números do W90, com a reação em
    # Z e para cima. Sem o peso ao longo das barras, e com a SC em Y, não é prova de eixo.
    errado = {"PP": "W90"}
    dados, apoios, geometria = montar(forcas=errado, reacoes=errado, apoios_de=errado)
    assert tm.eixo_vertical_provado(dados, t.plano()) is None
    tratado = tratar(dados, apoios, geometria)
    assert not tratado.tratou(tm.T_EIXO) and tratado.dados.eixo_vertical == "Y"
    # E o painel continua acusando o arquivo do PP.
    assert _painel(tratado).erros >= 1


# ------------------------------------------------------------------ nas páginas
def _gravar(dados, apoios, geometria) -> None:
    from core import plano_de_cargas as pc
    from core.project_store import obter_projeto_ativo, salvar_projeto

    projeto = obter_projeto_ativo()
    projeto["plano_de_cargas"] = pc.para_dicionario(t.plano())
    projeto["esforcos_do_modelo"] = em.para_dicionario(dados)
    projeto["apoios_do_modelo"] = am.para_dicionario(apoios)
    projeto["geometria_do_modelo"] = ld.para_dicionario(geometria)
    salvar_projeto(projeto, motivo="teste")


def _projeto_com_varios_erros():
    trocar = {"W90": "W270", "W270": "W90"}
    dados, apoios, geometria = montar(forcas=trocar, reacoes=trocar, apoios_de=trocar)
    pilar = t.BARRAS[0].viga
    dados = replace(
        em.com_membros(
            dados,
            {
                **{b: replace(c, tipo="—") for b, c in dados.membros.items()},
                pilar: replace(dados.membros[pilar], tipo="—", base=em.BASE_FIM),
            },
        ),
        eixo_vertical="Z",
    )
    return dados, apoios, geometria


def test_pagina_trata_sozinha_e_grava_o_valor_certo(banco_com_projeto):
    from core.project_store import obter_projeto_ativo
    from tests.test_esforcos_modelo_pagina import abrir, sem_ajuda

    dados, apoios, geometria = _projeto_com_varios_erros()
    _gravar(dados, apoios, geometria)
    pagina = abrir()
    assert not sem_ajuda(pagina), sorted(sem_ajuda(pagina))
    # Tudo tratado: o painel não tem o que corrigir nem o que conferir.
    assert any("Tudo confere" in s.value for s in pagina.success)
    assert "Para corrigir" not in {m.label for m in pagina.metric}
    textos = " ".join(m.value for m in pagina.markdown)
    for titulo in (
        "Eixo vertical do modelo",
        "Casos de vento com o nome trocado",
        "Tipo das barras",
        "Base do pilar escolhida na ponta de cima",
    ):
        assert f"**{titulo}.**" in textos, titulo
    eixo = pagina.radio(key="em_eixo")
    assert eixo.value == "Y" and eixo.disabled
    assert any("O eixo vertical saiu do peso próprio" in c.value for c in pagina.caption)
    # A leitura não gravou nada: o projeto continua como chegou.
    gravado = em.esforcos_do_projeto(obter_projeto_ativo())
    assert gravado.eixo_vertical == "Z" and gravado.membros[t.BARRAS[0].viga].tipo == "—"
    # Ao gravar a tabela das barras, o valor certo fica gravado — esforços e apoios juntos.
    pagina.button(key="em_gravar_barras").click().run()
    assert not pagina.exception, [str(e.value) for e in pagina.exception]
    projeto = obter_projeto_ativo()
    gravado = em.esforcos_do_projeto(projeto)
    assert gravado.eixo_vertical == "Y"
    assert gravado.membros[t.BARRAS[0].viga].tipo == "Pilar"
    assert gravado.membros[t.BARRAS[0].viga].base == em.BASE_AUTOMATICA
    assert gravado.casos["W270"].arquivo == "W90-forcas.csv"
    assert am.do_projeto(projeto).casos["W270"].arquivo == "W90-apoios.csv"
    assert tm.do_projeto(projeto).tratamentos == ()


def test_pagina_com_a_gravidade_descontada_nao_grava_os_numeros_descontados(banco_com_projeto):
    from core.project_store import obter_projeto_ativo
    from tests.test_esforcos_modelo_pagina import abrir

    junto = {"W0": "PP+W0"}
    dados, apoios, geometria = montar(forcas=junto, reacoes=junto, apoios_de=junto)
    _gravar(dados, apoios, geometria)
    pagina = abrir()
    metricas = {m.label: m.value for m in pagina.metric}
    assert metricas["Para corrigir"] == "0" and metricas["Para conferir"] == "1"
    assert any("descontou o PP ponto a ponto" in m.value for m in pagina.markdown)
    antes = em.esforcos_do_projeto(obter_projeto_ativo()).casos["W0"]
    pagina.button(key="em_gravar_barras").click().run()
    assert not pagina.exception, [str(e.value) for e in pagina.exception]
    depois = em.esforcos_do_projeto(obter_projeto_ativo()).casos["W0"]
    assert depois.membros == antes.membros and depois.reacoes == antes.reacoes
    assert tm.do_projeto(obter_projeto_ativo()).recalculados == {"W0"}  # continua tratando


def test_reacoes_nas_bases_usam_o_modelo_tratado(banco_com_projeto):
    from core import reacoes_nas_bases as rb
    from core.project_store import obter_projeto_ativo
    from tests.test_reacoes_nas_bases import _confere_com_o_portico
    from tests.test_reacoes_nas_bases import abrir as abrir_reacoes

    dados, apoios, geometria = _projeto_com_varios_erros()
    _gravar(dados, apoios, geometria)
    # O que vai para o engenheiro civil é o do cálculo, com cada vento no caso certo.
    _confere_com_o_portico(rb.do_projeto(obter_projeto_ativo()), tolerancia=1e-6)
    pagina = abrir_reacoes()
    metricas = {m.label: m.value for m in pagina.metric}
    assert metricas["Pés"] == "4" and metricas["Pela macro"] == "24"
    assert any("Nada pendente" in s.value for s in pagina.success)
    assert any("O programa tratou sozinho" in c.value for c in pagina.caption)
