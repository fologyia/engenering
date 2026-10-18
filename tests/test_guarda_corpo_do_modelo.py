"""Guarda-corpo pelo esqueleto: bordas livres do piso, viga de cada trecho, acesso da escada, método
pelas vigas, peso no plano, vento e robustez (geometria estragada nunca derruba o cálculo).

Os modelos são montados como a macro do SolidWorks exporta: Y para cima, em metros, chapas com o
contorno da face de cima e vigas U 200 com a linha de centro 0,10 m abaixo da chapa."""

from __future__ import annotations

import math
import random

import pytest

from core import cargas_pelo_modelo as cpm
from core import guarda_corpo_do_modelo as gm
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import vento_estrutura_aberta as va
from core import vento_por_barras as vpb

PISO = 4.0  # cota da face de cima da chapa
LINHA = PISO - 0.107  # linha de centro das vigas U 200 (meia altura + espessura da chapa)
U200 = (203.2, 57.4)


def barra(nome, a, b, secao=U200, alma=(0.0, 1.0, 0.0)) -> ld.CorpoDoModelo:
    return ld.CorpoDoModelo(
        nome=nome,
        item=nome,
        descricao='U 8" x 17,10',
        inicio=tuple(float(v) for v in a),
        fim=tuple(float(v) for v in b),
        comprimento_m=math.dist(a, b),
        forma=ld.FORMA_BARRA,
        secao_mm=secao,
        direcao_secao=alma,
    )


def chapa(nome, contorno, aberturas=()) -> ld.CorpoDoModelo:
    xs = [p[0] for p in contorno]
    zs = [p[2] for p in contorno]
    return ld.CorpoDoModelo(
        nome=nome,
        item="Chapa",
        descricao='Chapa 1/4"',
        inicio=(min(xs), contorno[0][1], min(zs)),
        fim=(max(xs), contorno[0][1], max(zs)),
        comprimento_m=max(max(xs) - min(xs), max(zs) - min(zs)),
        forma=ld.FORMA_CHAPA,
        secao_mm=(1000.0 * (max(zs) - min(zs)), 6.35),
        contorno=tuple(contorno),
        aberturas=tuple(tuple(a) for a in aberturas),
    )


def retangulo(x0, z0, x1, z1, y=PISO):
    return [(x0, y, z0), (x0, y, z1), (x1, y, z1), (x1, y, z0)]


def plataforma(*, com_chapa=True, internas=True) -> list[ld.CorpoDoModelo]:
    """6 × 4 m: vigas de borda em x = 0 e 6 (ao longo de Z) e em z = 0 e 4 (ao longo de X), uma
    interna em x = 3, pilares nos cantos."""
    corpos = [
        barra("Borda x0", (0, LINHA, 0), (0, LINHA, 4)),
        barra("Borda x6", (6, LINHA, 0), (6, LINHA, 4)),
        barra("Borda z0", (0, LINHA, 0), (6, LINHA, 0)),
        barra("Borda z4", (0, LINHA, 4), (6, LINHA, 4)),
    ]
    if internas:
        corpos.append(barra("Interna x3", (3, LINHA, 0), (3, LINHA, 4)))
    for i, (x, z) in enumerate(((0, 0), (6, 0), (0, 4), (6, 4)), start=1):
        corpos.append(barra(f"Pilar {i}", (x, 0, z), (x, LINHA, z), secao=(210, 134)))
    if com_chapa:
        corpos.append(chapa("Piso", retangulo(0, 0, 6, 4)))
    return corpos


def bordas(corpos) -> gm.BordasDoPiso:
    return gm.bordas_do_piso(ld.GeometriaDoModelo(corpos=tuple(corpos)), "Y")


def por_viga(b: gm.BordasDoPiso, situacao=None) -> dict[str, float]:
    soma: dict[str, float] = {}
    for t in b.trechos:
        if situacao is None or t.situacao == situacao:
            soma[t.viga] = soma.get(t.viga, 0.0) + t.comprimento_m
    return soma


# ------------------------------------------------------------------ pelas chapas do piso
def test_plataforma_retangular_tem_guarda_corpo_nas_quatro_bordas():
    b = bordas(plataforma())
    assert b.metodo == gm.METODO_CHAPAS and not b.avisos
    assert por_viga(b, gm.SITUACAO_GUARDA_CORPO) == pytest.approx(
        {"Borda x0": 4.0, "Borda x6": 4.0, "Borda z0": 6.0, "Borda z4": 6.0}
    )
    assert all(t.sugerido for t in b.trechos)
    assert len({t.id for t in b.trechos}) == len({t.chave for t in b.trechos}) == len(b.trechos)


def test_duas_chapas_encostadas_nao_tem_guarda_corpo_na_junta():
    corpos = [c for c in plataforma(com_chapa=False)]
    corpos += [chapa("Piso A", retangulo(0, 0, 3, 4)), chapa("Piso B", retangulo(3.005, 0, 6, 4))]
    b = bordas(corpos)
    assert "Interna x3" not in por_viga(b)
    assert sum(t.comprimento_m for t in b.marcados()) == pytest.approx(20.0, abs=0.05)


def test_chapa_em_balanco_alem_da_viga_ainda_acha_a_viga():
    corpos = [c for c in plataforma(com_chapa=False)]
    corpos.append(chapa("Piso", retangulo(-0.20, 0, 6, 4)))  # 20 cm além da viga em x = 0
    b = bordas(corpos)
    assert por_viga(b, gm.SITUACAO_GUARDA_CORPO)["Borda x0"] == pytest.approx(4.0)


def test_abertura_no_piso_tem_guarda_corpo_em_volta():
    corpos = plataforma(internas=False)[:-1]  # sem a chapa inteira
    corpos += [
        barra("Abertura z1", (1, LINHA, 1), (2, LINHA, 1)),
        barra("Abertura z2", (1, LINHA, 2), (2, LINHA, 2)),
        barra("Abertura x1", (1, LINHA, 1), (1, LINHA, 2)),
        barra("Abertura x2", (2, LINHA, 1), (2, LINHA, 2)),
        chapa("Piso", retangulo(0, 0, 6, 4), aberturas=[retangulo(1, 1, 2, 2)]),
    ]
    b = bordas(corpos)
    em_volta = {k: v for k, v in por_viga(b).items() if k.startswith("Abertura")}
    assert em_volta == pytest.approx({f"Abertura {s}": 1.0 for s in ("z1", "z2", "x1", "x2")})


def _escada(corpos):
    """Lance de 0,8 m de largura saindo da borda z = 4, de x = 1 a 1,8, descendo para +Z."""
    queda, avanco = 2.0, 2.6
    corpos += [
        barra("Longarina A", (1.0, LINHA, 4.0), (1.0, LINHA - queda, 4.0 + avanco)),
        barra("Longarina B", (1.8, LINHA, 4.0), (1.8, LINHA - queda, 4.0 + avanco)),
        chapa(
            "Lance",
            [
                (1.0, PISO, 4.0),
                (1.0, PISO - queda, 4.0 + avanco),
                (1.8, PISO - queda, 4.0 + avanco),
                (1.8, PISO, 4.0),
            ],
        ),
    ]
    return corpos


def test_lance_de_escada_abre_o_acesso_e_leva_guarda_corpo_nas_longarinas():
    b = bordas(_escada(plataforma()))
    gc = por_viga(b, gm.SITUACAO_GUARDA_CORPO)
    assert gc["Borda z4"] == pytest.approx(6.0 - 0.8, abs=0.06)  # sem o trecho do acesso
    escada = por_viga(b, gm.SITUACAO_ESCADA)
    assert set(escada) == {"Longarina A", "Longarina B"}
    assert all(v == pytest.approx(math.hypot(2.0, 2.6), abs=0.06) for v in escada.values())
    pe = [t for t in b.trechos if t.situacao == gm.SITUACAO_ACESSO]
    assert len(pe) == 1 and pe[0].comprimento_m == pytest.approx(0.8, abs=0.06)  # o pé do lance


def test_lance_sem_chapa_o_acesso_sai_das_longarinas():
    corpos = _escada(plataforma())
    corpos = [c for c in corpos if c.nome != "Lance"]
    b = bordas(corpos)
    acesso = [t for t in b.trechos if t.situacao == gm.SITUACAO_ACESSO]
    assert len(acesso) == 1 and acesso[0].viga == "Borda z4"
    assert acesso[0].comprimento_m == pytest.approx(0.8, abs=0.06)
    assert por_viga(b, gm.SITUACAO_GUARDA_CORPO)["Borda z4"] == pytest.approx(5.2, abs=0.06)


def test_mao_francesa_nao_e_escada():
    """Duas mãos-francesas do pilar até a viga de borda (descem para baixo do piso)."""
    corpos = plataforma()
    corpos += [
        barra("MF 1", (0.0, LINHA - 1.0, 4.0), (1.0, LINHA, 4.0), secao=(152, 49)),
        barra("MF 2", (6.0, LINHA - 1.0, 4.0), (5.0, LINHA, 4.0), secao=(152, 49)),
        barra("MF 3", (0.0, LINHA - 1.0, 4.0), (0.0, LINHA, 3.0), secao=(152, 49)),
    ]
    b = bordas([c for c in corpos if c.forma != ld.FORMA_CHAPA])  # sem chapa: pelas longarinas
    assert not [t for t in b.trechos if t.situacao == gm.SITUACAO_ACESSO]
    b2 = bordas(corpos)
    assert not [t for t in b2.trechos if t.situacao == gm.SITUACAO_ACESSO]


def test_borda_sem_viga_vira_aviso_e_nao_entra_marcada():
    corpos = [c for c in plataforma() if c.nome != "Borda x6"]
    b = bordas(corpos)
    sem = [t for t in b.trechos if t.situacao == gm.SITUACAO_SEM_VIGA]
    assert len(sem) == 1 and sem[0].comprimento_m == pytest.approx(4.0, abs=0.06)
    assert not sem[0].sugerido and sem[0] not in b.marcados()
    assert any("sem viga embaixo" in a for a in b.avisos)


def test_cantoneira_de_enrijecimento_perde_para_a_viga():
    corpos = plataforma()
    corpos.append(barra("L enrijecedor", (0.05, PISO - 0.03, 0), (0.05, PISO - 0.03, 4), (64, 64)))
    assert por_viga(bordas(corpos), gm.SITUACAO_GUARDA_CORPO)["Borda x0"] == pytest.approx(4.0)


# ------------------------------------------------------------------ pelas vigas (sem chapas)
def test_sem_chapa_as_bordas_saem_das_vigas():
    b = bordas(plataforma(com_chapa=False))
    assert b.metodo == gm.METODO_VIGAS and any("não tem chapas de piso" in a for a in b.avisos)
    assert por_viga(b, gm.SITUACAO_GUARDA_CORPO) == pytest.approx(
        {"Borda x0": 4.0, "Borda x6": 4.0, "Borda z0": 6.0, "Borda z4": 6.0}, abs=0.05
    )


def test_sem_chapa_e_sem_vizinha_nao_inventa_borda():
    b = bordas([barra("Sozinha", (0, LINHA, 0), (5, LINHA, 0))])
    assert not b.trechos and any("Sozinha" in a for a in b.avisos)


def test_esqueleto_vazio():
    b = gm.bordas_do_piso(ld.GeometriaDoModelo(), "Y")
    assert not b.trechos and b.metodo == gm.METODO_NENHUM


# ------------------------------------------------------------------ robustez
def _corpo_aleatorio(r: random.Random, k: int) -> ld.CorpoDoModelo:
    def ponto():
        valores = [r.uniform(-5, 10) for _ in range(3)]
        if r.random() < 0.05:
            valores[r.randrange(3)] = float("nan")
        return tuple(valores)

    if r.random() < 0.25:
        y = r.choice((PISO, r.uniform(0, 8)))
        n = r.choice((2, 3, 4, 5, 8))
        contorno = [
            (r.uniform(-2, 8), y + r.choice((0.0, r.uniform(-2, 2))), r.uniform(-2, 8))
            for _ in range(n)
        ]
        if r.random() < 0.1:
            contorno = [contorno[0]] * n  # degenerado
        return chapa(f"C{k}", contorno)
    a = ponto()
    b = a if r.random() < 0.05 else ponto()
    secao = r.choice((U200, (64.0, 64.0), (0.0, 0.0), (210.0, 134.0)))
    return ld.CorpoDoModelo(
        nome=f"B{k}",
        item="",
        descricao="",
        inicio=a,
        fim=b,
        comprimento_m=math.dist(a, b) if all(math.isfinite(v) for v in (*a, *b)) else float("nan"),
        forma=r.choice((ld.FORMA_BARRA, ld.FORMA_BARRA, ld.FORMA_BLOCO, "")),
        secao_mm=secao,
        direcao_secao=r.choice((None, (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))),
    )


@pytest.mark.parametrize("semente", range(40))
def test_geometria_estragada_nunca_derruba_e_os_trechos_fazem_sentido(semente):
    r = random.Random(semente)
    corpos = [_corpo_aleatorio(r, k) for k in range(r.randint(0, 30))]
    if r.random() < 0.5:
        corpos += plataforma()
    b = bordas(corpos)
    assert b.metodo in (gm.METODO_CHAPAS, gm.METODO_VIGAS, gm.METODO_NENHUM)
    assert len({t.chave for t in b.trechos}) == len(b.trechos)
    for t in b.trechos:
        assert t.situacao in gm.SITUACOES
        assert t.comprimento_m >= gm.TRECHO_MINIMO_M - 1e-9
        assert all(math.isfinite(v) for v in (*t.inicio, *t.fim))
        assert not t.sugerido or t.viga
    pesos = gm.pesos_nas_vigas(b.marcados(), 0.4)
    assert all(math.isfinite(p.kN_m_na_viga) and p.kN_m_na_viga >= 0 for p in pesos)


# ------------------------------------------------------------------ peso no plano de cargas
def test_peso_vai_para_as_vigas_de_borda_e_fecha_a_conta():
    b = bordas(_escada(plataforma()))
    marcados = b.marcados()
    pesos = gm.pesos_nas_vigas(marcados, 0.40, {"Borda z0": "Viga-3"})
    total = sum(p.total_kN for p in pesos)
    assert total == pytest.approx(0.40 * sum(t.comprimento_m for t in marcados))
    rotulos = {p.rotulo for p in pesos}
    assert "Borda z0 (Viga-3)" in rotulos
    z4 = next(p for p in pesos if p.viga == "Borda z4")
    assert z4.kN_m_na_viga == pytest.approx(0.40 * z4.comprimento_com_guarda_corpo_m / 6.0)


def test_peso_no_pe_mantem_o_piso_e_troca_o_envio_anterior():
    piso = pc.CargaDoModelo("Interna x3", 1.2, "kN/m", cpm.VERTICAL, "piso", comprimento_m=4.0)
    plano = pc.com_acao(
        pc.PlanoDeCargas(), pc.nova_acao("PE", origem=cpm.ORIGEM, resumo="Piso.", cargas=[piso])
    )
    b = bordas(plataforma())
    plano = gm.aplicar_peso_no_plano(plano, gm.pesos_nas_vigas(b.marcados(), 0.40))
    plano = gm.aplicar_peso_no_plano(plano, gm.pesos_nas_vigas(b.marcados(), 0.50))
    pe = plano.acao("PE")
    assert piso in pe.cargas
    do_gc = [c for c in pe.cargas if gm.e_linha_de_guarda_corpo(c)]
    assert len(do_gc) == 4
    assert sum(c.resultante for c in do_gc) == pytest.approx(0.50 * 20.0)
    assert pe.resumo.count(gm.MARCA) == 1 and pe.resumo.startswith("Piso.")
    assert not pc.validar_acao(pe)


def test_reenviar_o_piso_nao_apaga_o_guarda_corpo():
    g = ld.GeometriaDoModelo(corpos=tuple(plataforma()))
    b = gm.bordas_do_piso(g, "Y")
    plano = gm.aplicar_peso_no_plano(pc.PlanoDeCargas(), gm.pesos_nas_vigas(b.marcados(), 0.40))
    distribuicao = cpm.distribuir(g, {"PE": 0.30}, "Y")
    plano = cpm.aplicar_no_plano(distribuicao, plano, {"PE": 0.30})
    pe = plano.acao("PE")
    assert len([c for c in pe.cargas if gm.e_linha_de_guarda_corpo(c)]) == 4
    assert any(not gm.e_linha_de_guarda_corpo(c) for c in pe.cargas)
    assert gm.MARCA in pe.resumo


# ------------------------------------------------------------------ vento
def test_guarda_corpos_viram_elementos_do_vento_na_viga_certa():
    corpos = plataforma()
    g = ld.GeometriaDoModelo(corpos=tuple(corpos))
    b = gm.bordas_do_piso(g, "Y")
    elementos = gm.elementos_ao_vento(b.marcados(), "Y", altura_m=1.1)
    assert {e.barra for e in elementos} == {"Borda x0", "Borda x6", "Borda z0", "Borda z4"}
    r = vpb.calcular(
        vpb.EntradaPorBarras(
            tuple(vpb.barras_do_esqueleto(g, "Y")),
            va.ParametrosVento(v0_m_s=35.0),
            elementos=tuple(elementos),
            direcoes=(0,),
        )
    )
    forcas = {el.elemento: el for el in r.direcao(0).elementos}
    # vento em +X: só os guarda-corpos perpendiculares (ao longo de Z do modelo) carregam
    carregados = {e.barra for e in elementos if forcas[e.nome].forca_kN > 1e-9}
    assert carregados == {"Borda x0", "Borda x6"}


# ------------------------------------------------------------------ o que fica no projeto
def test_escolha_gravada_volta_igual_e_lixo_vira_padrao():
    b = bordas(plataforma())
    primeiro = b.trechos[0]
    escolha = gm.EscolhaDoGuardaCorpo({primeiro.chave: False, "não existe": True}, 0.45, 1.3, 0.35)
    dados = gm.para_dicionario(escolha, b)
    assert dados["trocados"] == {primeiro.chave: False}
    lida = gm.escolha_do_projeto({gm.CHAVE_DO_PROJETO: dados})
    assert lida.trocados == {primeiro.chave: False} and lida.altura_m == 1.3
    assert primeiro not in b.marcados(lida.trocados)
    for lixo in (
        None,
        {},
        {gm.CHAVE_DO_PROJETO: "x"},
        {gm.CHAVE_DO_PROJETO: {"peso_kN_m": "a", "trocados": [1]}},
    ):
        e = gm.escolha_do_projeto(lixo)
        assert e.peso_kN_m == gm.PESO_PADRAO_KN_M and e.trocados == {}


# ------------------------------------------------------------------ opções e trechos à mão
def _soma_marcada(b: gm.BordasDoPiso, viga: str, escolha=None) -> float:
    return sum(t.comprimento_m for t in b.marcados(escolha) if t.viga == viga)


def test_desligar_o_acesso_pelas_longarinas():
    corpos = [c for c in _escada(plataforma()) if c.nome != "Lance"]
    g = ld.GeometriaDoModelo(corpos=tuple(corpos))
    b = gm.bordas_do_piso(g, "Y", acesso_pelas_longarinas=False)
    assert not [t for t in b.trechos if t.situacao == gm.SITUACAO_ACESSO]
    assert _soma_marcada(b, "Borda z4") == pytest.approx(6.0, abs=0.06)


def test_desligar_o_guarda_corpo_dos_lances():
    g = ld.GeometriaDoModelo(corpos=tuple(_escada(plataforma())))
    b = gm.bordas_do_piso(g, "Y", guarda_corpo_nos_lances=False)
    lances = [t for t in b.trechos if t.situacao == gm.SITUACAO_ESCADA]
    assert len(lances) == 2 and all(t.desligado and not t.sugerido for t in lances)
    assert all("desligado" in t.motivo for t in lances)
    assert not set(b.marcados()) & set(lances)
    # o engenheiro ainda pode marcar um lance à mão na tabela
    assert lances[0] in b.marcados({lances[0].chave: True})


def _a_mao(*manuais, corpos=None):
    g = ld.GeometriaDoModelo(corpos=tuple(corpos or plataforma()))
    escolha = gm.EscolhaDoGuardaCorpo(a_mao=tuple(manuais))
    return gm.bordas_do_projeto(g, "Y", escolha)


def test_guarda_corpo_a_mao_numa_viga_que_o_programa_nao_achou():
    b = _a_mao(gm.TrechoAMao("Interna x3"))
    (m,) = [t for t in b.trechos if t.a_mao]
    assert m.id == "M1" and m.situacao == gm.SITUACAO_MAO and m.comprimento_m == pytest.approx(4.0)
    assert m in b.marcados({m.chave: False})  # a tabela à mão manda nele
    pesos = gm.pesos_nas_vigas(b.marcados(), 0.4)
    assert {p.viga for p in pesos} >= {"Interna x3"}


def test_guarda_corpo_a_mao_sobre_o_achado_nao_conta_duas_vezes():
    b = _a_mao(gm.TrechoAMao("Borda z0", 1.0, 3.0))
    assert _soma_marcada(b, "Borda z0") == pytest.approx(6.0, abs=0.01)
    automaticos = [t for t in b.trechos if t.viga == "Borda z0" and not t.a_mao]
    assert sorted(round(t.comprimento_m, 2) for t in automaticos) == [1.0, 3.0]


def test_acesso_a_mao_tira_o_guarda_corpo_e_a_escolha_vale_nos_pedacos():
    b = _a_mao(gm.TrechoAMao("Borda z0", 2.0, 3.0, gm.TIPO_MAO_ACESSO))
    assert _soma_marcada(b, "Borda z0") == pytest.approx(5.0, abs=0.01)
    pedacos = [t for t in b.trechos if t.viga == "Borda z0" and not t.a_mao]
    assert len(pedacos) == 2 and len({t.chave_base for t in pedacos}) == 1
    # desmarcar o trecho achado (pela chave de antes) desmarca os dois pedaços
    assert _soma_marcada(b, "Borda z0", {pedacos[0].chave_base: False}) == 0.0
    acesso = next(t for t in b.trechos if t.situacao == gm.SITUACAO_ACESSO_MAO)
    assert not acesso.sugerido and acesso not in b.marcados()


def test_trecho_a_mao_estragado_vira_aviso_e_o_resto_segue():
    b = _a_mao(
        gm.TrechoAMao("Não existe"),
        gm.TrechoAMao("Borda z0", 3.0, 1.0),  # invertido: vira 1 a 3
        gm.TrechoAMao("Borda x0", -1.0, 9.0),  # passa da viga: corta em 0 a 4
        gm.TrechoAMao("Borda x6", 1.0, 1.02),  # curto demais
        gm.TrechoAMao("Interna x3", tipo="outro"),
        gm.TrechoAMao("Interna x3", float("nan"), 2.0),
    )
    texto = " ".join(b.avisos)
    for pedaco in (
        "não está no esqueleto",
        "invertido",
        "passa da viga",
        "menos de 10 cm",
        "tipo desconhecido",
        "inválido",
    ):
        assert pedaco in texto, pedaco
    mao = {t.viga: t.comprimento_m for t in b.trechos if t.a_mao}
    assert mao == pytest.approx({"Borda z0": 2.0, "Borda x0": 4.0})


@pytest.mark.parametrize("semente", range(25))
def test_trechos_a_mao_aleatorios_nunca_derrubam(semente):
    r = random.Random(semente)
    vigas = ["Borda x0", "Borda x6", "Borda z0", "Borda z4", "Interna x3", "Pilar 1", "?"]
    manuais = [
        gm.TrechoAMao(
            r.choice(vigas),
            r.choice((None, r.uniform(-2, 8))),
            r.choice((None, r.uniform(-2, 8))),
            r.choice((*gm.TIPOS_A_MAO, "x")),
        )
        for _ in range(r.randint(0, 8))
    ]
    b = _a_mao(*manuais)
    for t in b.trechos:
        assert t.comprimento_m >= gm.TRECHO_MINIMO_M - 1e-9
        assert t.situacao in gm.SITUACOES
    for viga in ("Borda x0", "Borda x6", "Borda z0", "Borda z4"):
        comprimento = 4.0 if "x" in viga.split()[1] else 6.0
        assert _soma_marcada(b, viga) <= comprimento + 0.05  # nunca conta duas vezes


def test_opcoes_e_trechos_a_mao_ficam_gravados_no_projeto():
    escolha = gm.EscolhaDoGuardaCorpo(
        acesso_pelas_longarinas=False,
        guarda_corpo_nos_lances=False,
        a_mao=(
            gm.TrechoAMao("Interna x3", None, 2.5),
            gm.TrechoAMao("Borda z0", 1, 2, "acesso / portão"),
        ),
    )
    lida = gm.escolha_do_projeto({gm.CHAVE_DO_PROJETO: gm.para_dicionario(escolha)})
    assert not lida.acesso_pelas_longarinas and not lida.guarda_corpo_nos_lances
    assert lida.a_mao == escolha.a_mao
    lixo = {
        "a_mao": [{"viga": ""}, {"viga": "V", "tipo": "x"}, "texto", {"viga": "V", "de_m": "a"}],
        "acesso_pelas_longarinas": "sim",
    }
    lida = gm.escolha_do_projeto({gm.CHAVE_DO_PROJETO: lixo})
    assert lida.a_mao == (gm.TrechoAMao("V"),) and lida.acesso_pelas_longarinas is True
