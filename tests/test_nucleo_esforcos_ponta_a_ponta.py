"""O núcleo dos Esforços do modelo de ponta a ponta, com o teste01 do usuário resolvido como
pórtico espacial (tests/portico_3d_teste01.py).

Os arquivos saem no formato do SolidWorks e da macro, passam pela leitura, pela gravação no
projeto, pelo quadro das fundações, pelo quadro por apoio, pela envoltória e pelo painel "Antes de
verificar". Primeiro tudo certo; depois cada erro que o usuário cometeu (ou pode cometer) ao
salvar os arquivos, e o painel tem de apontar o problema certo, com o caso certo.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from core import apoios_do_modelo as am
from core import diagnostico as dg
from core import diagnostico_do_modelo as dm
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf
from tests import portico_3d_teste01 as t


def montar(
    *,
    forcas: dict[str, str] | None = None,
    reacoes: dict[str, str] | None = None,
    apoios_de: dict[str, str] | None = None,
    casos: tuple[str, ...] = t.CASOS,
    com_apoios: bool = True,
    com_esqueleto: bool = True,
    b2: float = 1.10,
) -> tuple[em.EsforcosDoModelo, am.ApoiosDoModelo, ld.GeometriaDoModelo | None]:
    """O que fica gravado no projeto depois de enviar os arquivos de cada caso.

    ``forcas``/``reacoes``/``apoios_de``: caso → de que resultado saem os números daquele arquivo
    (o erro de salvar com outro caso carregado; "PP+W0" = estudo com as duas cargas).
    """
    forcas, reacoes, apoios_de = forcas or {}, reacoes or {}, apoios_de or {}
    dados = em.EsforcosDoModelo()
    apoios = am.ApoiosDoModelo()
    for caso in casos:
        lido = em.ler_arquivo(t.csv_forcas(caso, de=forcas.get(caso)), f"{caso}-forcas.csv")
        assert em.caso_do_arquivo_sugerido(lido, t.CASOS) == caso
        dados = em.com_caso(dados, em.caso_do_arquivo(lido, caso))
        r = em.ler_arquivo(t.csv_reacoes(caso, de=reacoes.get(caso)), f"{caso}-reacoes.csv")
        assert r.tipo == em.TIPO_REACOES and r.reacoes is not None
        dados = em.com_reacoes(dados, caso, r.reacoes, r.nome_arquivo)
        if com_apoios:
            lidos = am.ler_apoios(t.csv_apoios(caso, de=apoios_de.get(caso)), f"{caso}-apoios.csv")
            apoios = am.com_caso(apoios, lidos)
    if com_apoios:
        apoios = am.com_fixacoes(apoios, am.ler_fixacoes(t.csv_fixacoes(), "fixacoes.csv"))
    geometria = (
        ld.ler_esqueleto(t.csv_esqueleto(), "teste01_esqueleto.csv") if com_esqueleto else None
    )
    dados = em.com_membros(
        dados,
        {
            b.viga: em.ConfiguracaoDoMembro(
                perfil=b.perfil,
                tipo="Pilar" if b.perfil == t.PILAR else "Viga",
                eixo_forte=dados.membros[b.viga].eixo_forte,
            )
            for b in t.BARRAS
        },
    )
    dados = em.com_parametros(dados, {"Pilar": em.ParametrosDoTipo(b2=b2)})
    # O que fica gravado é o que a página lê de volta: passa pelo dicionário do projeto.
    dados = em.de_dicionario(json.loads(json.dumps(em.para_dicionario(dados))))
    apoios = am.de_dicionario(json.loads(json.dumps(am.para_dicionario(apoios))))
    return dados, apoios, geometria


def diagnostico(
    dados: em.EsforcosDoModelo,
    apoios: am.ApoiosDoModelo,
    geometria: ld.GeometriaDoModelo | None,
    plano: pc.PlanoDeCargas | None = None,
) -> dm.Diagnostico:
    plano = plano or t.plano()
    leituras = ld.ler_barras(dados, geometria, plano)
    return dm.diagnosticar(
        dados,
        plano,
        apoios,
        geometria=geometria,
        leituras=leituras,
        achados_da_leitura=ld.diagnosticar(dados, plano, geometria, leituras),
    )


def _titulos(d: dm.Diagnostico) -> list[str]:
    return [a.titulo for a in d.achados]


def _achado(d: dm.Diagnostico, titulo: str) -> dm.Achado:
    achado = next((a for a in d.achados if a.titulo == titulo), None)
    assert achado is not None, _titulos(d)
    return achado


# ------------------------------------------------------------------ o pórtico de teste
def test_o_portico_de_teste_esta_em_equilibrio():
    for caso in t.CASOS:
        r = t.resolver(caso)
        assert t.reacao_total_N(caso) == pytest.approx(-r.cargas_totais_N, abs=1e-6)
    assert t.reacao_total_N("PP")[1] == pytest.approx(1993.0, abs=1.0)  # ~190 kg × 10,5
    assert t.reacao_total_N("SC")[1] == pytest.approx(7500.0)
    # O vento empurra +X: os pilares de barlavento (x = 0) são tracionados.
    w0 = t.resolver("W0").reacoes
    assert all(w0[p][0][1] < 0 for p in t.PES if p[0] == 0.0)
    assert all(w0[p][0][1] > 0 for p in t.PES if p[0] == 1.5)


# ------------------------------------------------------------------ tudo certo
def test_tudo_certo_de_ponta_a_ponta():
    dados, apoios, geometria = montar()
    d = diagnostico(dados, apoios, geometria)
    assert d.tudo_certo, [(a.titulo, a.problema) for a in d.achados]
    assert d.certos[0] == "O modelo recebeu a carga do plano em SC, W0, W90, W180 e W270."
    assert any(
        "batem com a reação no pé dele em PP, SC, W0, W90, W180 e W270" in c for c in d.certos
    )
    assert "As forças de cada caso batem com a reação do mesmo caso." in d.certos


def test_quadro_das_fundacoes_e_o_do_portico():
    """A compressão e a cortante na base de cada pilar são a reação no pé dele, caso a caso."""
    dados, apoios, geometria = montar()
    quadro = qf.montar_quadro(dados)
    assert not quadro.pendentes and len(quadro.pilares) == 4
    assert {p.pilar: p.base for p in quadro.pilares} == {
        "Viga-1(Pilar[1])": qf.BASE_INICIO,
        "Viga-2(Pilar[2])": qf.BASE_INICIO,
        "Viga-3(Pilar[3])": qf.BASE_FIM,
        "Viga-4(Pilar[4])": qf.BASE_FIM,
    }
    for pilar, pe in zip(quadro.pilares, t.PES, strict=True):
        for carga in pilar.cargas:
            forca, _ = t.resolver(carga.caso).reacoes[pe]
            assert carga.n == pytest.approx(forca[1] / 1e3, abs=1e-4)  # 6 algarismos no projeto
            assert math.hypot(carga.v1, carga.v2) == pytest.approx(
                math.hypot(forca[0], forca[2]) / 1e3, abs=1e-4
            )
    assert all(i.nivel == pc.NIVEL_OK for i in quadro.conferencia)
    por_apoio = am.montar_quadro(apoios, geometria=geometria, esforcos=dados)
    assert [a.barra for a in por_apoio.apoios] == [f"Pilar[{k}]" for k in (1, 2, 3, 4)]
    assert all(a.comportamento == "engastado" for a in por_apoio.apoios)
    for apoio, pe in zip(por_apoio.apoios, t.PES, strict=True):
        for caso in t.CASOS:
            forca, momento = t.resolver(caso).reacoes[pe]
            carga = por_apoio.carga(apoio.rotulo, caso)
            assert carga is not None
            assert carga.forca_kN == pytest.approx(tuple(-forca / 1e3), abs=1e-6)
            assert carga.momento_kNm == pytest.approx(tuple(-momento / 1e3), abs=1e-6)
    assert all(i.nivel == pc.NIVEL_OK for i in por_apoio.conferencia)


def test_envoltoria_combina_ponto_a_ponto_como_a_mao():
    """A maior compressão na base de cada pilar no ELU é Σ γ·N de cada caso, como à mão."""
    dados, _, _ = montar()
    plano = t.plano()
    resultado = em.envoltoria(dados, plano, [comb.ELU_NORMAL])
    preparo = em.preparar_combinacoes(dados, plano, [comb.ELU_NORMAL])
    assert preparo is not None and resultado.combinacoes == len(preparo.nomes) > 0
    assert set(resultado.casos) == set(t.CASOS)
    for e in resultado.membros:
        assert e.metodo == "ponto a ponto"
    pilares = {e.membro: e for e in resultado.membros if "Pilar" in e.membro}
    for k, pe in enumerate(t.PES, start=1):
        bases = [-t.resolver(c).reacoes[pe][0][1] / 1e3 for c in preparo.importados]  # tração +
        na_mao = min(
            sum(f * n for f, n in zip(fatores, bases, strict=True)) for fatores in preparo.fatores
        )
        compressao = pilares[f"Viga-{k}(Pilar[{k}])"].compressao
        assert compressao is not None
        # O pior ponto da barra pode estar acima da base? Não: o peso faz a base a mais comprimida.
        assert compressao.valor == pytest.approx(na_mao, abs=1e-4)


# ------------------------------------------------------------------ os erros de envio
def test_forcas_do_w0_salvas_com_o_w90_carregado():
    dados, apoios, geometria = montar(forcas={"W0": "W90"})
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "W0: as forças são as do W90")
    assert achado.nivel == dm.NIVEL_ERRO and achado.detalhe["casos"] == ["W0"]
    assert "Dê duplo clique no caso W0" in achado.passos[1]
    assert not any(a.titulo.startswith("W90") for a in d.achados)


def test_forcas_do_w180_com_os_numeros_do_w0_so_o_esqueleto_separa():
    """W0 e W180 são espelhados: o tamanho das forças é o mesmo, só o sinal da compressão em
    cada pé muda — com o esqueleto (cada pilar no seu apoio), o programa diz qual está errado."""
    dados, apoios, geometria = montar(forcas={"W180": "W0"})
    d = diagnostico(dados, apoios, geometria)
    assert _achado(d, "W180: as forças são as do W0").detalhe["casos"] == ["W180"]
    # Sem o esqueleto não dá para saber qual dos dois: o painel diz que é um deles.
    dados, apoios, _ = montar(forcas={"W180": "W0"}, com_esqueleto=False)
    d = diagnostico(dados, apoios, None)
    achado = _achado(d, "W0 e W180: as forças são de outro caso")
    assert "algum deles" in achado.problema


def test_forcas_do_vento_de_outro_caso_sem_o_outro_caso_importado():
    """O W90 não foi importado, mas os apoios dele vieram da macro: o painel reconhece que as
    forças salvas como W0 são as do W90 pela reação no pé de cada pilar."""
    dados, apoios, geometria = montar(forcas={"W0": "W90"})
    dados = em.sem_caso(dados, "W90")
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "W0: as forças são as do W90")
    assert "reação no pé dele no caso W90" in achado.problema


def test_o_w270_do_usuario_com_as_forcas_de_um_vento_em_x():
    """O teste01 real (26/10): o arquivo de forças do W270 leva 1,82 kN de cortante — o vento em
    X — e os apoios do W270 são de outra rodada. As forças vêm de outra rodada (números quase
    iguais aos do W0, não idênticos)."""
    dados, apoios, _ = montar(
        forcas={"W270": "1.001*W0"}, apoios_de={"W270": "W90"}, com_esqueleto=False
    )
    d = diagnostico(dados, apoios, None)
    achado = _achado(d, "W270: as forças são de outro caso")
    assert achado.detalhe["de"] == ["W0", "W180"] and "W0 ou W180" in achado.problema
    assert "não dá para dizer qual dos casos espelhados" in achado.problema
    # Com o esqueleto, o pé de cada pilar separa o W0 do W180.
    dados, apoios, geometria = montar(forcas={"W270": "1.001*W0"}, apoios_de={"W270": "W90"})
    d = diagnostico(dados, apoios, geometria)
    assert _achado(d, "W270: as forças são as do W0").nivel == dm.NIVEL_ERRO
    # Sem os apoios da macro, o esqueleto mostra o lado comprimido: empurra em X.
    dados, apoios, geometria = montar(forcas={"W270": "1.001*W0"}, com_apoios=False)
    d = diagnostico(dados, apoios, geometria)
    assert _achado(d, "W270: as forças empurram para outro lado").detalhe["de"] == ["W0"]
    # Sem os apoios e sem o esqueleto, a pista é a reação horizontal.
    dados, apoios, _ = montar(forcas={"W270": "1.001*W0"}, com_apoios=False, com_esqueleto=False)
    d = diagnostico(dados, apoios, None)
    achado = _achado(d, "W270: a cortante dos pilares não fecha com a reação horizontal")
    assert achado.nivel == dm.NIVEL_ATENCAO
    assert "1,82 kN é a reação horizontal de W0 e W180: o arquivo parece ser de um deles" in (
        achado.problema
    )


def test_forcas_do_vento_com_a_direcao_de_outro_caso_pelo_tombamento():
    """Sem os apoios da macro, o esqueleto diz onde fica o pé de cada pilar: o lado comprimido
    mostra para onde as forças do arquivo empurram."""
    dados, apoios, geometria = montar(forcas={"W90": "1.001*W0"}, com_apoios=False)
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "W90: as forças empurram para outro lado")
    assert "empurram para +X" in achado.problema and "empurrando para −Z" in achado.problema
    assert achado.detalhe["de"] == ["W0"] and "essa é a direção do W0" in achado.problema
    # O espelho: W180 com os números (quase) do W0 — o lado comprimido é o outro.
    dados, apoios, geometria = montar(forcas={"W180": "1.001*W0"}, com_apoios=False)
    assert _achado(
        diagnostico(dados, apoios, geometria), "W180: as forças empurram para outro lado"
    )


def test_o_w270_do_usuario_com_o_valor_do_vento_em_x_na_mesma_direcao():
    """O que o arquivo real do usuário tinha (26/10): o W270-forcas é um vento em Z, na direção
    da reação do W270, mas com 1,82 kN (o valor do vento em X) em vez de 2,18 kN — de uma rodada
    anterior, antes de acertar o valor. Os apoios do W270 também são de outra rodada."""
    dados, apoios, geometria = montar(
        forcas={"W270": f"{1.82 / 2.18}*W270"}, apoios_de={"W270": "W90"}
    )
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "W270: a cortante dos pilares não fecha com a reação horizontal")
    assert achado.nivel == dm.NIVEL_ERRO  # os apoios da macro mostram que só os pilares apoiam
    assert "As forças empurram para +Z, a mesma direção da reação do W270" in achado.problema
    assert "só que com 1,82 kN em vez de 2,18 kN" in achado.problema
    assert "rodada anterior" in achado.problema and "o valor de W0 e W180" in achado.problema
    # O painel não pode dizer, logo abaixo, que as forças de todos os casos batem.
    assert "As forças de cada caso batem com a reação do mesmo caso." not in d.certos


def test_vento_espelhado_com_os_apoios_de_outra_rodada_nao_e_acusado():
    """O falso alarme da rodada no banco real: o W180 certo, com os apoios dele de outra rodada,
    bate em tamanho com os apoios do W0 (o espelho dele) — sem o esqueleto, isso não prova nada."""
    dados, apoios, _ = montar(apoios_de={"W180": "W90"}, com_esqueleto=False)
    d = diagnostico(dados, apoios, None)
    assert not any("forças" in a.titulo for a in d.achados), _titulos(d)
    assert "Reação em cada apoio: arquivos antigos" in _titulos(d)


def test_vento_espelhado_sem_o_esqueleto():
    dados, apoios, _ = montar(forcas={"W90": "1.001*W0"}, com_esqueleto=False)
    d = diagnostico(dados, apoios, None)
    achado = _achado(d, "W90: as forças são de outro caso")
    assert achado.detalhe["de"] == ["W0", "W180"]
    assert "As reações e os apoios do caso estão certos." in achado.problema


def test_forcas_que_nao_batem_com_nenhum_apoio():
    dados, apoios, geometria = montar(forcas={"W0": "0.5*W0+0.5*W90"})
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "W0: as forças não batem com a reação de cada apoio")
    assert achado.nivel == dm.NIVEL_ATENCAO


def test_forcas_da_sobrecarga_com_os_numeros_do_peso_proprio():
    dados, apoios, geometria = montar(forcas={"SC": "PP"})
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "SC: as forças são as do PP")
    assert "as forças são as do PP" in achado.problema and "SC" in achado.detalhe["casos"]


def test_forcas_do_pp_salvas_com_o_estudo_base():
    todos = "+".join(t.CASOS)
    dados, apoios, geometria = montar(forcas={"PP": todos})
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "PP: as forças não são do caso PP")
    assert "estudo base" in achado.problema


def test_forcas_da_sobrecarga_de_outro_caso_pela_vertical():
    """Sem os apoios da macro: a soma das bases do arquivo da SC é a reação do PP."""
    dados, apoios, geometria = montar(
        forcas={"SC": "PP"}, casos=("SC", "W0", "W180"), com_apoios=False
    )
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "SC: as forças não são do caso SC")
    assert "levam 1,99 kN" in achado.problema


def test_cortante_das_bases_menor_que_a_reacao_do_vento():
    """Sem apoios: a vertical do vento é zero e não diz nada, mas os pilares não podem levar
    menos cortante que a reação horizontal."""
    dados, apoios, geometria = montar(forcas={"W0": "0.2*W0"}, com_apoios=False)
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "W0: a cortante dos pilares não fecha com a reação horizontal")
    assert achado.nivel == dm.NIVEL_ATENCAO and "somam só 0,36 kN" in achado.problema
    assert "travada fora dos pilares" in achado.passos[-1]


def test_gravidade_esquecida_no_caso_de_vento():
    dados, apoios, geometria = montar(
        forcas={"W0": "PP+W0"}, reacoes={"W0": "PP+W0"}, apoios_de={"W0": "PP+W0"}
    )
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "W0: ficou com a gravidade")
    assert achado.nivel == dm.NIVEL_ERRO and "tire a gravidade do caso W0" in achado.passos[0]


def test_sobrecarga_majorada_no_solidworks():
    dados, apoios, geometria = montar(
        forcas={"SC": "1.4*SC"}, reacoes={"SC": "1.4*SC"}, apoios_de={"SC": "1.4*SC"}
    )
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "SC: problema no estudo")
    assert "majorado" in achado.problema
    assert not any("forças" in a.titulo for a in d.achados)  # os arquivos são do mesmo caso


def test_ventos_com_os_nomes_trocados_e_o_botao():
    trocar = {"W90": "W270", "W270": "W90"}
    dados, apoios, geometria = montar(forcas=trocar, reacoes=trocar, apoios_de=trocar)
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "Ventos com os nomes trocados")
    assert achado.acao == dm.ACAO_TROCAR_NOMES and achado.detalhe["mapa"] == trocar
    novos, apoios_novos = dm.corrigir_nomes(dados, apoios, achado.detalhe["mapa"])
    assert diagnostico(novos, apoios_novos, geometria).tudo_certo


def test_apoios_de_outra_rodada_nao_acusam_as_forcas():
    dados, apoios, geometria = montar(apoios_de={"W0": "W90"})
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "Reação em cada apoio: arquivos antigos")
    assert achado.detalhe["outra_rodada"] == ["W0"]
    assert not any("forças" in a.titulo for a in d.achados)


def test_eixo_vertical_trocado_aparece_uma_vez():
    dados, apoios, geometria = montar()
    from dataclasses import replace

    dados = replace(dados, eixo_vertical="Z")
    d = diagnostico(dados, apoios, geometria)
    sobre_o_eixo = [a for a in d.achados if "eixo vertical" in (a.titulo + a.problema).casefold()]
    assert sobre_o_eixo and sobre_o_eixo[0].nivel == dm.NIVEL_ERRO
    assert "Eixo vertical trocado" not in _titulos(d)  # já dito pela conferência das reações


def test_segunda_ordem_entra_no_painel_com_o_passo_a_passo():
    dados, apoios, geometria = montar(b2=1.0)
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "Segunda ordem global (B₂)")
    assert achado.nivel == dm.NIVEL_ATENCAO and "Contraventamento" in achado.passos[0]


# ------------------------------------------------------------------ robustez
def test_uma_conferencia_que_falha_nao_derruba_as_outras(banco_isolado, monkeypatch):
    monkeypatch.delenv(dg.VARIAVEL_MODO, raising=False)
    dados, apoios, geometria = montar(apoios_de={"W0": "W90"})

    def quebra(*_args, **_kwargs):
        raise ZeroDivisionError("teste")

    monkeypatch.setattr(dm.qf, "montar_quadro", quebra)
    d = diagnostico(dados, apoios, geometria)
    achado = _achado(d, "Não deu para conferir: forças de cada caso")
    assert achado.nivel == dm.NIVEL_ATENCAO and not d.tudo_certo
    assert "ref. " in achado.problema
    assert "Reação em cada apoio: arquivos antigos" in _titulos(d)  # as outras rodaram
    assert "As forças de cada caso batem com a reação do mesmo caso." not in d.certos
    gravadas = dg.ler()
    assert any(o["referencia"] == achado.detalhe["referencia"] for o in gravadas)


def test_com_o_modo_levantar_a_falha_sobe(monkeypatch):
    dados, apoios, geometria = montar()

    def quebra(*_args, **_kwargs):
        raise ZeroDivisionError("teste")

    monkeypatch.setattr(dm.qf, "montar_quadro", quebra)
    with pytest.raises(ZeroDivisionError):
        diagnostico(dados, apoios, geometria)


@pytest.mark.parametrize("semente", range(40))
def test_dados_estragados_nunca_quebram_o_painel(semente):
    """Casos com números aleatórios, sem reações, sem barras, apoios sem posição e com nós
    repetidos: o painel sempre sai (o modo levantar está ligado, então nada pode falhar)."""
    gerador = np.random.default_rng(semente)
    dados, apoios, geometria = montar()
    casos = {}
    for codigo, caso in dados.casos.items():
        sorteio = gerador.integers(0, 5)
        if sorteio == 0:
            caso = em.CasoImportado(codigo, "", "", "", "", {}, caso.reacoes)
        elif sorteio == 1:
            caso = em.CasoImportado(codigo, "", "", "", "", caso.membros, None)
        elif sorteio == 2:
            membros = {
                m: tuple(
                    em.PontoDeEsforco(p.elemento, p.fim, *gerador.normal(0, 10, 6)) for p in pontos
                )
                for m, pontos in caso.membros.items()
            }
            caso = em.CasoImportado(
                codigo, "", "", "", "", membros, em.Reacoes(tuple(gerador.normal(0, 5, 3)))
            )
        elif sorteio == 3:
            membros = {
                m: pontos[: gerador.integers(0, len(pontos) + 1)]
                for m, pontos in caso.membros.items()
            }
            caso = em.CasoImportado(codigo, "", "", "", "", membros, caso.reacoes)
        casos[codigo] = caso
    from dataclasses import replace

    dados = replace(dados, casos=casos)
    apoios_casos = {}
    for codigo, a in apoios.casos.items():
        nos = a.nos
        if gerador.integers(0, 3) == 0:
            nos = tuple(am.ReacaoNoNo(n.no, None, n.forca_N, n.momento_Nm) for n in nos)
        elif gerador.integers(0, 3) == 0:
            nos = tuple(am.ReacaoNoNo(n.no, (0.0, 0.0, 0.0), n.forca_N, n.momento_Nm) for n in nos)
        apoios_casos[codigo] = replace(a, nos=nos)
    apoios = replace(apoios, casos=apoios_casos)
    plano = t.plano()
    if gerador.integers(0, 2):
        plano = pc.com_acao(plano, pc.nova_acao("T+", categoria=pc.CATEGORIA_TEMPERATURA))
    d = diagnostico(dados, apoios, geometria if gerador.integers(0, 2) else None, plano)
    assert all(a.titulo and a.problema for a in d.achados)
    assert d.erros + d.atencoes <= len(d.achados)
