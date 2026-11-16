"""O piso lido do esqueleto do modelo: tipo de cada chapa, carga por chapa, apoio em um sentido,
carga só no trecho, envio ao plano e a cena 3D de conferência."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core import cargas_pelo_modelo as cpm
from core import cena_3d as c3
from core import cena_do_piso as cp
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import piso_do_modelo as pm
from core import plano_de_cargas as pc
from core import section_catalog as sc
from tests.test_cargas_pelo_modelo import ALTURA, barra, chapa, piso_6x3

Y = -ALTURA / 2


def painel_4_lados() -> ld.GeometriaDoModelo:
    """Chapa de 4 × 2 m com viga nos quatro lados (as longas em X, as curtas em Z)."""
    return ld.GeometriaDoModelo(
        corpos=(
            barra("Longa z0", (0, Y, 0), (4, Y, 0)),
            barra("Longa z2", (0, Y, 2), (4, Y, 2)),
            barra("Curta x0", (0, Y, 0), (0, Y, 2)),
            barra("Curta x4", (4, Y, 0), (4, Y, 2)),
            chapa("Piso", [(0, 0, 0), (4, 0, 0), (4, 0, 2), (0, 0, 2)]),
        )
    )


def com_escada() -> ld.GeometriaDoModelo:
    """Piso de 6 × 3 m a 3 m do chão, um lance inclinado, um patamar pequeno e outro lance."""
    piso = piso_6x3().corpos
    subir = [replace(c, inicio=_sobe(c.inicio), fim=_sobe(c.fim)) for c in piso[:3]]
    chapa_do_piso = chapa("Piso", [(0, 3, 0), (6, 3, 0), (6, 3, 3), (0, 3, 3)])
    lance_1 = chapa("Lance 1", [(6, 3, 0), (8, 1.5, 0), (8, 1.5, 1), (6, 3, 1)])
    patamar = chapa("Patamar", [(8, 1.5, 0), (9, 1.5, 0), (9, 1.5, 1), (8, 1.5, 1)])
    lance_2 = chapa("Lance 2", [(9, 1.5, 0), (11, 0, 0), (11, 0, 1), (9, 1.5, 1)])
    longarinas = [
        barra("Longarina 1a", (6, 3 + Y, 0), (8, 1.5 + Y, 0)),
        barra("Longarina 1b", (6, 3 + Y, 1), (8, 1.5 + Y, 1)),
        barra("Longarina 2a", (9, 1.5 + Y, 0), (11, Y, 0)),
        barra("Longarina 2b", (9, 1.5 + Y, 1), (11, Y, 1)),
        barra("Patamar a", (8, 1.5 + Y, 0), (9, 1.5 + Y, 0)),
        barra("Patamar b", (8, 1.5 + Y, 1), (9, 1.5 + Y, 1)),
    ]
    pilar = barra("Pilar", (0, 0, 0), (0, 3 + Y, 0))
    return ld.GeometriaDoModelo(
        corpos=(*subir, chapa_do_piso, lance_1, patamar, lance_2, *longarinas, pilar)
    )


def _sobe(p):
    return (p[0], p[1] + 3, p[2])


def escolha_de(leitura, **mudancas) -> pm.EscolhaDoPiso:
    return replace(pm.escolha_inicial(leitura, None, sc_do_piso=5.0, sc_da_escada=3.0), **mudancas)


def kn(d: cpm.DistribuicaoDoPiso, caso: str) -> dict[str, float]:
    return {c.viga: c.total_kN for c in d.do_caso(caso)}


# ------------------------------------------------------------------ o que o programa entendeu
def test_le_piso_patamar_e_lances_com_os_niveis_e_as_longarinas():
    g = com_escada()
    leitura = pm.ler(g, "Y")
    tipos = {c.nome: c.tipo for c in leitura.chapas}
    assert tipos == {
        "Piso": pm.TIPO_PISO,
        "Lance 1": pm.TIPO_ESCADA,
        "Patamar": pm.TIPO_PATAMAR,
        "Lance 2": pm.TIPO_ESCADA,
    }
    assert [c.codigo for c in leitura.chapas] == ["C1", "C2", "C3", "C4"]
    assert leitura.niveis == pytest.approx((1.65, 3.15))  # o chão é o pé da longarina
    assert {c.nome: c.nivel for c in leitura.chapas} == {
        "Piso": 2,
        "Lance 1": 0,
        "Patamar": 1,
        "Lance 2": 0,
    }
    barras = dict(leitura.barras)
    assert barras[pm.PAPEL_LONGARINA] == 4 and barras[ld.TIPO_PILAR] == 1
    assert barras[ld.TIPO_VIGA] == 5
    assert leitura.altura_m == pytest.approx(3.15)
    assert not leitura.avisos


def test_patamar_com_um_lance_so_e_piso_grande_continua_piso():
    g = com_escada()
    sem_o_lance_2 = ld.GeometriaDoModelo(corpos=tuple(c for c in g.corpos if c.nome != "Lance 2"))
    tipos = {c.nome: c.tipo for c in pm.ler(sem_o_lance_2, "Y").chapas}
    assert tipos["Patamar"] == pm.TIPO_PATAMAR  # pequeno, na ponta de um lance
    assert tipos["Piso"] == pm.TIPO_PISO  # o lance encosta, mas é o piso maior


def test_avisa_nivel_de_vigas_sem_chapa_e_chapa_sem_viga():
    g = piso_6x3()
    outro_nivel = [
        barra(f"N2 {i}", (0, 3 + Y, z), (6, 3 + Y, z)) for i, z in enumerate((0, 1, 2, 3))
    ]
    solta = chapa("Solta", [(20, 0, 0), (22, 0, 0), (22, 0, 2), (20, 0, 2)])
    leitura = pm.ler(ld.GeometriaDoModelo(corpos=(*g.corpos, *outro_nivel, solta)), "Y")
    assert any("4 vigas em nível na cota +3,00 m sem chapa" in a for a in leitura.avisos)
    assert any(a.startswith("C2 (Solta): nenhuma viga") for a in leitura.avisos)


def test_peso_pelo_volume_da_chapa():
    g = piso_6x3()
    com_volume = tuple(
        replace(c, volume_m3=18.0 * 0.00635) if c.forma == ld.FORMA_CHAPA else c for c in g.corpos
    )
    leitura = pm.ler(ld.GeometriaDoModelo(corpos=com_volume), "Y")
    esperado = 18.0 * 0.00635 * lm.DENSIDADE_ACO * lm.G / 1e3
    assert leitura.chapas[0].peso_kN == pytest.approx(esperado)
    assert leitura.chapas[0].peso_kN_m2 == pytest.approx(esperado / 18.0)
    assert leitura.chapas[0].espessura_mm == pytest.approx(6.35)
    d = pm.distribuir(ld.GeometriaDoModelo(corpos=com_volume), leitura, escolha_de(leitura))
    assert d.total("PE") == pytest.approx(esperado) and d.total("SC") == pytest.approx(90.0)
    no_pp = pm.distribuir(
        ld.GeometriaDoModelo(corpos=com_volume), leitura, escolha_de(leitura, peso=pm.PESO_NO_PP)
    )
    assert no_pp.casos == ("SC",)


def test_sem_o_volume_o_peso_pelo_volume_avisa():
    leitura = pm.ler(piso_6x3(), "Y")
    d = pm.distribuir(piso_6x3(), leitura, escolha_de(leitura))
    assert d.casos == ("SC",) and any("sem o volume da chapa" in a for a in d.avisos)


# ------------------------------------------------------------------ carga por chapa
def test_cada_chapa_com_a_sua_sobrecarga_e_o_total_fecha():
    g = com_escada()
    leitura = pm.ler(g, "Y")
    escolha = escolha_de(leitura, peso=pm.PESO_INFORMADO)
    assert {n: c.sc_kN_m2 for n, c in escolha.chapas.items()} == {
        "Piso": 5.0,
        "Lance 1": 3.0,
        "Patamar": 3.0,
        "Lance 2": 3.0,
    }
    d = pm.distribuir(g, leitura, escolha)
    # 18 m² de piso a 5 + (2 + 1 + 2) m² de projeção de escada e patamar a 3 kN/m²
    assert d.total("SC") == pytest.approx(18 * 5 + 5 * 3, rel=1e-6)
    assert {linha["Confere"] for linha in pm.conferencia(leitura, escolha, d)} == {"sim"}
    # Cada lance vai para as duas longarinas dele, metade para cada uma.
    cargas = kn(d, "SC")
    assert cargas["Longarina 1a"] == pytest.approx(3.0, rel=0.03)
    assert cargas["Longarina 1b"] == pytest.approx(3.0, rel=0.03)


def test_chapa_sem_carga_e_outros_casos_por_area():
    g = com_escada()
    leitura = pm.ler(g, "Y")
    escolha = escolha_de(leitura, outros=(("SCm", 2.0),))
    chapas = dict(escolha.chapas)
    chapas["Lance 2"] = replace(chapas["Lance 2"], tipo=pm.TIPO_SEM_CARGA)
    d = pm.distribuir(g, leitura, replace(escolha, chapas=chapas))
    assert "Longarina 2a" not in kn(d, "SC")
    assert d.total("SCm") == pytest.approx((18 + 2 + 1) * 2.0, rel=1e-6)
    assert d.casos == ("SC", "SCm")


def test_sobrecarga_da_escada_vem_do_criterio_do_projeto():
    assert pm.sobrecarga_da_escada(True, 5.0) == 3.0  # Tabela 2 do critério Anglo
    assert pm.sobrecarga_da_escada(False, 4.0) == 4.0


# ------------------------------------------------------------------ apoio em um sentido
def test_um_sentido_leva_tudo_as_vigas_de_apoio():
    g = painel_4_lados()
    leitura = pm.ler(g, "Y")

    def com(sentido):
        chapas = {"Piso": pm.EscolhaDaChapa(pm.TIPO_PISO, 5.0, 0.0, sentido)}
        return kn(pm.distribuir(g, leitura, escolha_de(leitura, chapas=chapas)), "SC")

    dois = com(cpm.SENTIDO_DOIS)
    assert set(dois) == {"Longa z0", "Longa z2", "Curta x0", "Curta x4"}
    assert sum(dois.values()) == pytest.approx(40.0)
    # Charneiras a 45°: cada viga curta leva um triângulo de 1 m² (5 kN).
    assert dois["Curta x0"] == pytest.approx(5.0, rel=0.05)
    um = com(cpm.SENTIDO_UM)  # as vigas longas apoiam: metade para cada uma
    assert um == pytest.approx({"Longa z0": 20.0, "Longa z2": 20.0}, rel=0.01)
    outro = com(cpm.SENTIDO_UM_OUTRO)
    assert outro == pytest.approx({"Curta x0": 20.0, "Curta x4": 20.0}, rel=0.01)


def test_um_sentido_com_viga_intermediaria_e_balanco():
    """Vigas em z = 0; 1,5; 3 e a chapa até z = 3,6: faixas de 0,75 / 1,5 / 0,75 + 0,6 m."""
    vigas = piso_6x3().corpos[:3]
    g = ld.GeometriaDoModelo(
        corpos=(*vigas, chapa("Piso", [(0, 0, 0), (6, 0, 0), (6, 0, 3.6), (0, 0, 3.6)]))
    )
    leitura = pm.ler(g, "Y")
    chapas = {"Piso": pm.EscolhaDaChapa(pm.TIPO_PISO, 1.0, 0.0, cpm.SENTIDO_UM)}
    cargas = kn(pm.distribuir(g, leitura, escolha_de(leitura, chapas=chapas)), "SC")
    # A fileira de amostras bem no meio do vão cai inteira num dos lados: ± uma fileira.
    assert cargas == pytest.approx({"V0": 4.5, "V1": 9.0, "V2": 8.1}, abs=0.2)
    assert sum(cargas.values()) == pytest.approx(21.6)


def test_direcoes_das_vigas_agrupa_e_ordena_pelo_comprimento():
    g = painel_4_lados()
    chapa_do_piso = cpm.chapas_do_piso(g, "Y")[0][0]
    grupos = cpm.direcoes_das_vigas(cpm.vigas_que_apoiam(g, chapa_do_piso))
    assert [round(soma, 6) for _, soma, _ in grupos] == [8.0, 4.0]
    assert [len(vigas) for _, _, vigas in grupos] == [2, 2]


# ------------------------------------------------------------------ carga só no trecho
def viga_coberta_em_parte() -> ld.GeometriaDoModelo:
    """Vigas de 6 m; a chapa cobre só de x = 0 a 2 m."""
    vigas = piso_6x3().corpos[:3]
    return ld.GeometriaDoModelo(
        corpos=(*vigas, chapa("Piso", [(0, 0, 0), (2, 0, 0), (2, 0, 3), (0, 0, 3)]))
    )


def test_carga_so_no_trecho_sob_a_chapa():
    g = viga_coberta_em_parte()
    leitura = pm.ler(g, "Y")
    inteira = pm.distribuir(g, leitura, escolha_de(leitura))
    assert any("Carga só em parte da viga" in a for a in inteira.avisos)
    v1 = next(c for c in inteira.do_caso("SC") if c.viga == "V1")
    assert not v1.parcial and v1.kN_m == pytest.approx(15.0 / 6.0, rel=0.01)
    no_trecho = pm.distribuir(g, leitura, escolha_de(leitura, so_no_trecho=True))
    assert not any("Carga só em parte" in a for a in no_trecho.avisos)
    v1 = next(c for c in no_trecho.do_caso("SC") if c.viga == "V1")
    assert v1.parcial and (v1.de_m, v1.ate_m) == pytest.approx((0.0, 2.0), abs=0.03)
    assert v1.kN_m == pytest.approx(15.0 / 2.0, rel=0.02)
    assert v1.total_kN == pytest.approx(15.0)
    linha = next(c for c in pm.linhas_do_caso(no_trecho, "SC") if c.elemento == "V1")
    assert linha.comprimento_m == pytest.approx(2.0, abs=0.03) and linha.inicio_m == 0.0
    assert linha.resultante == pytest.approx(15.0, rel=1e-3)
    assert "só no trecho de 0,00 a 2,00 m" in linha.observacao
    texto = pm.csv_das_cargas(no_trecho).decode("utf-8-sig")
    assert "SC;V1;;7,500;trecho;0,000;2,000;15,000" in texto


def test_trecho_gravado_volta_do_plano_e_o_3d_desenha_so_nele():
    from core import cena_do_modelo as cm

    g = viga_coberta_em_parte()
    leitura = pm.ler(g, "Y")
    escolha = escolha_de(leitura, so_no_trecho=True)
    d = pm.distribuir(g, leitura, escolha)
    plano = pm.aplicar_no_plano(pc.PlanoDeCargas(), leitura, escolha, d)
    lido = pc.de_dicionario(pc.para_dicionario(plano))
    assert lido.acao("SC").cargas == plano.acao("SC").cargas
    cargas = cm.cargas_do_caso(lido, "SC", g, "Y", cm.Nomes({}))
    assert -cargas.total_kN[2] == pytest.approx(30.0, rel=1e-3)
    assert all(
        math.dist(c.inicio, c.fim) == pytest.approx(2.0, abs=0.03) for c in cargas.distribuidas
    )


# ------------------------------------------------------------------ plano de cargas
def test_envio_troca_so_as_linhas_do_piso_e_mostra_o_que_muda():
    g = piso_6x3()
    leitura = pm.ler(g, "Y")
    escolha = escolha_de(leitura, temperatura=True)
    d = pm.distribuir(g, leitura, escolha)
    a_mao = pc.CargaDoModelo("V1", 2.0, "kN", "Z (vertical)", "talha")
    por_area = pc.CargaDoModelo("Todos os pisos", 5.0, "kN/m²", "Z (vertical)")
    grade = pc.CargaDoModelo("N1 · eixo A · 1–2", 1.0, "kN/m", "Z (vertical)", "", 2, 6.0)
    antiga = pc.CargaDoModelo(
        "V0", 9.0, "kN/m", "Z (vertical)", "54,00 kN de Piso; trecho carregado 6,00 de 6,00 m"
    )
    guarda_corpo = pc.CargaDoModelo(
        "V0", 0.4, "kN/m", "Z (vertical)", f"{cpm.MARCA_GUARDA_CORPO}: 0,400 kN/m", 1, 6.0
    )
    antes = pc.PlanoDeCargas()
    antes = pc.com_acao(antes, pc.nova_acao("SC", cargas=[por_area, a_mao, antiga]))
    antes = pc.com_acao(
        antes,
        pc.nova_acao(
            "PE", cargas=[grade, guarda_corpo], resumo=f"{cpm.MARCA_GUARDA_CORPO}: 2,40 kN"
        ),
    )
    depois = pm.aplicar_no_plano(antes, leitura, escolha, d, {"V0": "Viga-1(V0)"})
    sc = depois.acao("SC")
    assert a_mao in sc.cargas and por_area not in sc.cargas and antiga not in sc.cargas
    assert sum(1 for c in sc.cargas if pm.e_linha_do_piso(c)) == 3
    assert sc.cargas[0].elemento == "V0 (Viga-1(V0))" and sc.origem == pm.ORIGEM
    assert sc.resumo.startswith("Piso do modelo (SC): 90,00 kN")
    assert depois.acao("PE").cargas == (guarda_corpo,)
    assert depois.acao("PE").resumo == f"{cpm.MARCA_GUARDA_CORPO}: 2,40 kN"
    assert depois.fator_peso_proprio == pytest.approx(1.07) and "PP" in depois.codigos
    assert depois.acao("T+").cargas[0].valor == 10.0 and depois.acao("T−").cargas[0].valor == -10.0
    assert not [erro for acao in depois.acoes for erro in pc.validar_acao(acao)]
    muda = {linha["Caso"]: linha for linha in pm.comparar(antes, depois)}
    assert set(muda) == {"PP", "SC", "PE", "T+", "T−"}
    assert "gravidade × 1,00 → × 1,07" in muda["PP"]["O que muda"]
    assert "sai a carga por área" in muda["SC"]["O que muda"]
    assert "piso: 1 → 3 viga(s)" in muda["SC"]["O que muda"]
    assert "saem 1 linha(s) da grade de eixos" in muda["PE"]["O que muda"]
    assert muda["PE"]["Antes (kN)"] == pytest.approx(14.4) and muda["T+"]["Antes (kN)"] is None
    # Enviar de novo não muda nada; sem a temperatura, só ela sai.
    assert (
        pm.comparar(depois, pm.aplicar_no_plano(depois, leitura, escolha, d, {"V0": "Viga-1(V0)"}))
        == []
    )
    sem = pm.aplicar_no_plano(depois, leitura, replace(escolha, temperatura=False), d)
    assert {linha["Caso"] for linha in pm.comparar(depois, sem)} >= {"T+", "T−"}
    # A grade fica quando o usuário desliga a limpeza.
    fica = pm.aplicar_no_plano(antes, leitura, replace(escolha, tirar_a_grade=False), d)
    assert grade in fica.acao("PE").cargas


def test_temperatura_informada_a_mao_nao_e_trocada_nem_tirada():
    leitura = pm.ler(piso_6x3(), "Y")
    d = pm.distribuir(piso_6x3(), leitura, escolha_de(leitura))
    a_mao = pc.nova_acao("T+", cargas=[pc.CargaDoModelo("Tudo", 25.0, "°C", "—")])
    plano = pc.com_acao(pc.PlanoDeCargas(), a_mao)
    for ligada in (True, False):
        novo = pm.aplicar_no_plano(plano, leitura, escolha_de(leitura, temperatura=ligada), d)
        assert novo.acao("T+").cargas[0].valor == 25.0


def test_chapa_que_deixa_de_ter_carga_sai_do_plano():
    g = piso_6x3()
    leitura = pm.ler(g, "Y")
    escolha = escolha_de(leitura)
    plano = pm.aplicar_no_plano(
        pc.PlanoDeCargas(), leitura, escolha, pm.distribuir(g, leitura, escolha)
    )
    sem = replace(escolha, chapas={"Piso": pm.EscolhaDaChapa(pm.TIPO_SEM_CARGA)})
    novo = pm.aplicar_no_plano(plano, leitura, sem, pm.distribuir(g, leitura, sem))
    assert novo.acao("SC").cargas == ()


def test_escolha_vai_e_volta_e_o_gravado_ruim_cai_na_sugestao():
    leitura = pm.ler(com_escada(), "Y")
    escolha = escolha_de(
        leitura, peso=pm.PESO_INFORMADO, so_no_trecho=True, outros=(("EQ", 1.5),), temperatura=True
    )
    volta = pm.escolha_inicial(
        leitura, pm.para_dicionario(escolha), sc_do_piso=9.0, sc_da_escada=9.0
    )
    assert volta == escolha
    ruim = {
        "chapas": {"Piso": {"tipo": "Telhado", "sc_kN_m2": "x", "sentido": 3}, "Outra": 5},
        "peso": "?",
        "outros": [["SC", 2], ["EQ", -1], "x"],
        "acrescimo_ligacoes_pct": 900,
    }
    lida = pm.escolha_inicial(leitura, ruim, sc_do_piso=5.0, sc_da_escada=3.0)
    assert lida.chapas["Piso"] == pm.EscolhaDaChapa(pm.TIPO_PISO, 5.0)
    assert lida.peso == pm.PESO_PELO_VOLUME and lida.outros == ()
    assert lida.acrescimo_ligacoes_pct == 7.0 and not pm.validar(lida)
    assert pm.validar(replace(lida, acrescimo_ligacoes_pct=45.0))


# ------------------------------------------------------------------ PP do estudo
def test_pp_conta_as_chapas_pela_reacao_do_peso_proprio(monkeypatch):
    g = piso_6x3()
    corpos = tuple(
        replace(c, volume_m3=0.2 if c.forma == ld.FORMA_CHAPA else 0.05) for c in g.corpos
    )
    g = ld.GeometriaDoModelo(corpos=corpos)
    peso = lm.DENSIDADE_ACO * lm.G / 1e3  # kN por m³

    class Caso:
        reacoes = object()

    class Dados:
        casos = {"PP": Caso()}

    plano = pc.PlanoDeCargas()
    for vertical, esperado in (
        (0.35 * peso, True),  # barras + chapas
        (-0.15 * peso, False),  # só as barras (o sinal não importa)
        (0.25 * peso, None),  # nem um nem outro
    ):
        monkeypatch.setattr(ld, "_vertical", lambda dados, caso, v=vertical: v)
        assert pm.pp_conta_as_chapas(g, Dados(), plano) is esperado
    assert pm.pp_conta_as_chapas(g, None, plano) is None


# ------------------------------------------------------------------ cena 3D
def test_cena_de_conferencia_nos_tres_modos():
    g = com_escada()
    leitura = pm.ler(g, "Y")
    escolha = escolha_de(leitura, so_no_trecho=True)
    d = pm.distribuir(g, leitura, escolha)
    papel = cp.cena_do_piso(g, "Y", leitura, escolha, d)
    cores = {b.nome: b.cor for b in papel.barras}
    assert cores["Pilar"] == cp.COR_DO_PAPEL[ld.TIPO_PILAR]
    assert cores["V1"] == cp.COR_DO_PAPEL["Viga com piso"]
    assert cores["Longarina 1a"] == cp.COR_DO_PAPEL[pm.PAPEL_LONGARINA]
    assert {p.cor for p in papel.paineis} == {
        cp.COR_DA_CHAPA[t] for t in (pm.TIPO_PISO, pm.TIPO_PATAMAR, pm.TIPO_ESCADA)
    }
    assert [t.texto for t in papel.textos] == [
        "C1 · piso",
        "C2 · escada",
        "C3 · patamar",
        "C4 · escada",
    ]
    assert any("viga com piso" in texto for _, texto in papel.legenda)

    influencia = cp.cena_do_piso(g, "Y", leitura, escolha, d, cor_por=cp.COR_POR_INFLUENCIA)
    cor_da_viga = {b.nome: b.cor for b in influencia.barras}
    faixas = [p for p in influencia.paineis if p.grupo == "influência"]
    assert faixas and all(not p.sombra for p in faixas)
    for faixa in faixas:  # a faixa tem a cor da viga que a recebe
        assert faixa.cor == cor_da_viga[faixa.nome.split(" → ")[1]]
    assert cor_da_viga["Pilar"] == cp.COR_SEM_CARGA

    carga = cp.cena_do_piso(g, "Y", leitura, escolha, d, cor_por=cp.COR_POR_CARGA, caso="SC")
    assert carga.escala is not None and carga.escala.unidade == "kN/m"
    assert len(carga.distribuidas) == len(d.do_caso("SC"))
    assert sum(1 for c in carga.distribuidas if c.rotulo) == min(6, len(carga.distribuidas))
    for cena in (papel, influencia, carga):
        with sc.catalogo_estavel():
            desenho = c3.projetar(cena, azimute=-125.0, elevacao=27.0, perfil_real=True)
        assert desenho.itens and hash(cena) is not None


def test_mapa_de_influencia_cobre_a_chapa_e_segue_o_sentido():
    g = painel_4_lados()
    chapa_do_piso = cpm.chapas_do_piso(g, "Y")[0][0]

    def area(faixas):
        soma: dict[str, float] = {}
        for f in faixas:
            a, b, c, _ = f.pontos
            soma[f.viga] = soma.get(f.viga, 0.0) + math.dist(a, b) * math.dist(b, c)
        return soma

    dois = area(cpm.mapa_de_influencia(g, chapa_do_piso))
    assert sum(dois.values()) == pytest.approx(8.0, rel=0.02) and len(dois) == 4
    um = area(cpm.mapa_de_influencia(g, chapa_do_piso, cpm.SENTIDO_UM))
    assert set(um) == {"Longa z0", "Longa z2"}
    assert um["Longa z0"] == pytest.approx(4.0, rel=0.03)


# ------------------------------------------------------------------ catálogo estável
def test_catalogo_estavel_e_uma_foto_e_gravar_volta_ao_disco(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "ARQUIVO_USUARIO", tmp_path / "perfis_usuario.json")
    antes = sc.listar_perfis()
    chamadas = []
    original = sc._carregar_com_versao
    monkeypatch.setattr(
        sc, "_carregar_com_versao", lambda *a, **k: chamadas.append(1) or original(*a, **k)
    )
    with sc.catalogo_estavel():
        for _ in range(50):
            assert sc.listar_perfis() == antes
        dentro = len(chamadas)
        with sc.catalogo_estavel():  # aninhado: a mesma foto
            sc.listar_cadastrados()
        assert len(chamadas) == dentro
    assert dentro == len(sc.catalogos_de_referencia()) + 1  # uma leitura por arquivo
    sc.listar_perfis()
    assert len(chamadas) > dentro  # fora do bloco, volta a conferir o disco
