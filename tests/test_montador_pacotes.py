"""Montador: entradas ruins, origem dos valores, conjuntos, registro no projeto e referências."""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest import mock

import pytest
import sympy as sp
from streamlit.testing.v1 import AppTest

from core import montador as mt
from core import montador_blocos as mb
from core import montador_conjuntos as mc
from core import montador_eixo as me
from core import montador_grandezas as g
from core import montador_modelos as mm
from core import montador_registro as rg
from core.montador_funcoes import TABELADAS
from core.montador_grandezas import Unidades, unidades_padrao

APP = str(Path(__file__).resolve().parents[1] / "app.py")
U = unidades_padrao(g.SISTEMA_SOLIDOS)
BASE = {"b": 50.0, "M_x": 2e6, "V_y": 1e4, "S_y": 250.0, "n": 1.5}


def montar(*itens, zeros=frozenset()) -> mt.Montagem:
    dados = _dados(*itens)
    return mt.montar(mt.grafo_de_dados(dados), zeros)


def _dados(*itens) -> dict:
    nos = []
    for i, item in enumerate(itens):
        tipo, opcoes = item if isinstance(item, tuple) else (item, {})
        nos.append({"id": f"n{i}", "tipo": tipo, "opcoes": opcoes, "x": 0, "y": 0})
    fios = []
    for a, b in zip(nos, nos[1:], strict=False):
        saida = mb.POR_CHAVE[a["tipo"]].saidas[0]
        entrada = mb.POR_CHAVE[b["tipo"]].entradas[0]
        fios.append(
            {"de": a["id"], "saida": saida.chave, "para": b["id"], "entrada": entrada.chave}
        )
    return {"nos": nos, "fios": fios}


RET = ("retangular", "flexao", "cortante", "von_mises", mb.RESULTADO)


# ---------------------------------------------------------------------------
# Entradas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("chave", "valor", "trecho"),
    [
        ("n", -1.5, "maior que zero"),
        ("n", 0.0, "maior que zero"),
        ("b", -50.0, "maior que zero"),
        ("S_y", 0.0, "maior que zero"),
        ("M_x", -2e6, "sem o sinal"),
    ],
)
def test_valor_invalido_explica_e_nao_da_resposta(chave, valor, trecho):
    r = mt.isolar(montar(*RET), "h", {**BASE, chave: valor})
    assert r.valor is None
    assert any(trecho in texto for texto in r.invalidos)


def test_relacao_do_tubo_acima_de_1_explica():
    m = montar("tubo_relacao", "flexao", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d", {"k": 1.2, "M_x": 1e6, "S_y": 250.0, "n": 1.5})
    assert any("abaixo de 1" in texto for texto in r.invalidos)


def test_cortante_zero_nao_gera_aviso_falso():
    r = mt.isolar(montar(*RET), "h", {**BASE, "V_y": 0.0})
    assert r.valor == pytest.approx(math.sqrt(6 * 2e6 * 1.5 / (50 * 250)))
    assert not r.alertas
    assert len(r.isoladas) == 1


def test_momento_zero_no_eixo_nao_vira_zero_sobre_zero():
    m = montar("circular", "flexao", "cortante", "von_mises", mb.RESULTADO)
    r = mt.isolar(m, "d", {"M_x": 0.0, "V_y": 1e4, "S_y": 250.0, "n": 1.5})
    area = 4 * math.sqrt(3) * 1e4 * 1.5 / (3 * 250)
    assert r.valor == pytest.approx(math.sqrt(4 * area / math.pi))
    assert not r.alertas


def test_todos_os_esforcos_em_zero_diz_o_que_falta():
    with pytest.raises(mt.ErroDeMontagem, match="Preencha ao menos um esforço"):
        mt.isolar(montar(*RET), "h", {**BASE, "M_x": 0.0, "V_y": 0.0})


def test_fadiga_aceita_zero_sem_remendo():
    m = montar("circular", "goodman", mb.RESULTADO)
    valores = {
        "M_a": 1.4e5,
        "M_m": 0.0,
        "T_a": 0.0,
        "T_m": 1.2e5,
        "S_e": 195.0,
        "S_ut": 735.0,
        "K_f": 1.0,
        "K_fs": 1.0,
        "n": 1.5,
    }
    d3 = 16 * 1.5 / math.pi * (2 * 1.4e5 / 195 + math.sqrt(3) * 1.2e5 / 735)
    assert mt.isolar(m, "d", valores).valor == pytest.approx(d3 ** (1 / 3), rel=1e-6)


# ---------------------------------------------------------------------------
# Valor adotado
# ---------------------------------------------------------------------------


def test_valor_adotado_mostra_o_uso_de_cada_condicao():
    r = mt.isolar(montar(*RET), "h", BASE, adotado=40.0)
    assert r.valor == pytest.approx(37.947, rel=1e-3)
    fibra = next(i for i in r.conferencia_adotada if "fibra" in i.nome)
    assert fibra.uso == pytest.approx((37.947 / 40.0) ** 2, rel=1e-3)


def test_adotado_abaixo_do_minimo_passa_de_100():
    r = mt.isolar(montar(*RET), "h", BASE, adotado=30.0)
    assert max(i.uso for i in r.conferencia_adotada) > 1.0


def test_adotado_sem_todos_os_valores_nao_inventa_uso():
    r = mt.isolar(montar(*RET), "h", {"b": 50.0}, adotado=40.0)
    assert r.conferencia_adotada == ()


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------


def _material(nome: str) -> mt.Montagem:
    dados = _dados("circular", "flexao", "flecha", mb.RESULTADO)
    dados["nos"].append({"id": "m", "tipo": "material", "opcoes": {"material": nome}})
    dados["nos"].append({"id": "v", "tipo": "balanco_ponta", "opcoes": {}})
    dados["fios"] += [
        {"de": "m", "saida": "saida", "para": "n2", "entrada": "material"},
        {"de": "v", "saida": "flecha", "para": "n2", "entrada": "flecha"},
    ]
    return mt.montar(mt.grafo_de_dados(dados))


def _aluminio() -> str:
    from core import material_catalog as cat

    return next(m.nome for m in cat.listar_cadastrados().values() if m.categoria == "aluminio")


def test_aluminio_nao_fica_com_o_modulo_do_aco():
    m = _material(_aluminio())
    padroes = dict(m.padroes)
    assert padroes["E"] == pytest.approx(71000.0)
    assert "típico" in dict(m.origens)["E"]


def test_fio_de_material_leva_tudo_de_uma_vez():
    dados = _dados("circular", "flexao", "von_mises", mb.RESULTADO)
    dados["nos"].append({"id": "m", "tipo": "material", "opcoes": {}})
    dados["fios"].append({"de": "m", "saida": "saida", "para": "n2", "entrada": "material"})
    m = mt.montar(mt.grafo_de_dados(dados))
    assert "S_y" in {item.chave for item in m.grandezas}
    assert not m.erros


def test_dois_materiais_tem_letras_proprias():
    dados = _dados("circular", "flexao", "von_mises", mb.RESULTADO)
    dados["nos"] += [
        {"id": "m1", "tipo": "material", "opcoes": {}},
        {"id": "m2", "tipo": "material", "opcoes": {}},
    ]
    dados["fios"].append({"de": "m2", "saida": "saida", "para": "n2", "entrada": "material"})
    m = mt.montar(mt.grafo_de_dados(dados))
    assert "S_y_2" in {item.chave for item in m.grandezas}


# ---------------------------------------------------------------------------
# Fadiga com os esforços da fila
# ---------------------------------------------------------------------------


def test_eixo_girando_usa_os_mesmos_esforcos_da_estatica():
    modelo = mm.PARTE_SOLIDOS.por_nome["Eixo: estática e fadiga"]
    m = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    assert not {"M_a", "M_m", "T_a", "T_m"} & {item.chave for item in m.grandezas}
    r = mt.isolar(m, "d", modelo.valores)
    mr = math.hypot(5e5, 3e5)
    d3 = 16 * 2.0 / math.pi * (2 * mr / 180 + math.sqrt(3) * 2e5 / 655)
    assert r.valor == pytest.approx(d3 ** (1 / 3), rel=1e-6)
    assert "Fadiga" in r.manda.condicao.nome


def test_criterios_de_aceite_do_prototipo():
    m = montar("circular", "flexao", "flexao_y", "torcao", "von_mises", mb.RESULTADO)
    base = {"M_y": 3e5, "T": 2e5, "S_y": 350.0, "n": 2.0}
    assert mt.isolar(m, "d", {**base, "M_x": 5e5}).valor == pytest.approx(32.84, abs=0.01)
    assert mt.isolar(m, "d", {**base, "M_x": 1e6}).valor == pytest.approx(39.49, abs=0.01)
    r = mt.isolar(m, "d", {**base, "M_x": 5e5}, adotado=35.0)
    assert max(i.uso for i in r.conferencia_adotada) == pytest.approx(0.826, abs=0.001)


def test_eixo_girando_em_secao_retangular_explica():
    m = montar("retangular", "flexao", ("goodman", {"esforcos": mb.EIXO_GIRANDO}), mb.RESULTADO)
    assert any("seção redonda" in erro for _, erro in m.erros)


def test_eixo_girando_sem_esforco_explica():
    m = montar("circular", ("goodman", {"esforcos": mb.EIXO_GIRANDO}), mb.RESULTADO)
    assert any("Ponha flexão" in erro for _, erro in m.erros)


# ---------------------------------------------------------------------------
# Unidades coerentes
# ---------------------------------------------------------------------------


def _escala(item: g.Grandeza, f: float, l_: float, t: float, k: float = 1.0) -> float:
    if item.chave == g.MANNING.chave:
        return t * l_ ** (-1.0 / 3.0)  # n de Manning não é adimensional: s/m^(1/3)
    a, b, c, d = g.EXPOENTES[item.dimensao]
    return f**a * l_**b * t**c * k**d


@pytest.mark.parametrize(
    "modelo",
    [*mm.MODELOS, *mm.MODELOS_FLUIDOS],
    ids=lambda m: m.nome,
)
def test_toda_condicao_tem_os_dois_lados_na_mesma_unidade(modelo):
    """Mudar a escala de força, comprimento e tempo não pode mudar quem passa: 5·uso = 5·uso."""
    m = mt.montar(mt.grafo_de_dados(modelo.grafo()))
    tipos = {no.id: no.tipo for no in m.grafo.nos}
    base = {item.chave: 1.3 + 0.41 * i for i, item in enumerate(m.grandezas)}
    base.update({"k": 0.5, "t_f": 0.3, "t_w": 0.2, "b_f": 4.0, "h": 9.0})
    for condicao in m.condicoes:
        trocas = {item.simbolo: sp.Float(base[item.chave]) for item in m.grandezas}
        escalados = {
            item.simbolo: sp.Float(base[item.chave] * _escala(item, 7.0, 3.0, 2.0))
            for item in m.grandezas
        }
        if condicao.esquerda.has(sp.Function):
            continue  # f(Re, ε/D) é adimensional: a parte com atrito se confere nos testes de fluidos
        if condicao.direita.has(*TABELADAS):
            continue  # valor de tabela, como a interferência da NBR 6158, não muda com a escala
        if tipos[condicao.no] == me.TIPO:
            continue  # o eixo com trechos tem as posições na tabela, em mm: a escala não chega nelas
        antes = complex((condicao.esquerda / condicao.direita).subs(trocas).evalf())
        depois = complex((condicao.esquerda / condicao.direita).subs(escalados).evalf())
        assert depois.real == pytest.approx(antes.real, rel=1e-6), condicao.nome


def test_reynolds_e_adimensional():
    m = montar("fluido", "trecho", "carga", mb.RESULTADO)
    trecho = m.saidas["n1"]["saida"].trechos[0]
    letras = {"rho": 3.0, "mu": 2.0, "Q": 5.0, "D": 7.0}
    escala = {"rho": 7.0 / 3.0**4 * 2.0**2, "mu": 7.0 / 3.0**2 * 2.0, "Q": 3.0**3 / 2.0, "D": 3.0}

    def valor(fator: bool) -> float:
        trocas = {
            sp.Symbol(k, positive=True): sp.Float(v * (escala[k] if fator else 1.0))
            for k, v in letras.items()
        }
        return float(trecho.reynolds.subs(trocas))

    assert valor(True) == pytest.approx(valor(False))


# ---------------------------------------------------------------------------
# Conjuntos
# ---------------------------------------------------------------------------


def _modelo_conjunto() -> dict:
    return mm.PARTE_SOLIDOS.por_nome["Eixo: estática e fadiga"].grafo()


def test_conjunto_fica_com_cinco_blocos_e_seis_fios():
    dados = _modelo_conjunto()
    assert len(dados["nos"]) == 5
    assert len(dados["fios"]) == 6
    conjunto = next(n for n in dados["nos"] if n["tipo"] == mt.CONJUNTO)
    assert conjunto["nome"] == "Eixo solicitado"
    assert len(conjunto["grafo"]["nos"]) == 4


def test_abrir_o_conjunto_da_a_mesma_conta_que_sem_ele():
    modelo = mm.PARTE_SOLIDOS.por_nome["Eixo: estática e fadiga"]
    com = mt.isolar(mt.montar(mt.grafo_de_dados(modelo.grafo())), "d", modelo.valores)
    direto = mc.desagrupar(_modelo_conjunto(), "c1")
    sem = mt.isolar(mt.montar(mt.grafo_de_dados(direto)), "d", modelo.valores)
    assert com.valor == pytest.approx(sem.valor)
    assert all(n["tipo"] != mt.CONJUNTO for n in direto["nos"])


def test_ids_de_dentro_levam_o_conjunto_na_frente():
    grafo = mt.grafo_de_dados(_modelo_conjunto())
    assert any(no.id.startswith("c1/") for no in grafo.nos)


def test_agrupar_exige_dois_blocos():
    with pytest.raises(mc.ErroDeConjunto, match="dois blocos"):
        mc.agrupar(_dados("circular", "flexao"), ["n0"])


def test_resultado_nao_entra_no_conjunto():
    dados = _dados("circular", "flexao", "von_mises", mb.RESULTADO)
    with pytest.raises(mc.ErroDeConjunto, match="fora do conjunto"):
        mc.agrupar(dados, ["n2", "n3"])


def test_agrupar_cria_porta_para_fio_que_cruza_a_borda():
    dados = _dados("circular", "flexao", "torcao", "von_mises", mb.RESULTADO)
    novo = mc.agrupar(dados, ["n1", "n2"], "Esforços")
    conjunto = next(n for n in novo["nos"] if n["tipo"] == mt.CONJUNTO)
    assert [p["porta"] for p in conjunto["portas"]["entradas"]] == ["entrada"]
    assert [p["porta"] for p in conjunto["portas"]["saidas"]] == ["saida"]
    m = mt.montar(mt.grafo_de_dados(novo))
    assert not m.erros
    assert {"M_x", "T"} <= {item.chave for item in m.grandezas}


def test_conjunto_dentro_de_conjunto():
    dados = _dados("circular", "flexao", "torcao", "von_mises", mb.RESULTADO)
    um = mc.agrupar(dados, ["n1", "n2"], "Interno")
    dois = mc.agrupar(um, ["n0", "c1"], "Externo")
    grafo = mt.grafo_de_dados(dois)
    assert any(no.id == "c2/c1/n1" for no in grafo.nos)
    r = mt.isolar(mt.montar(grafo), "d", {"M_x": 5e5, "T": 3e5, "S_y": 350.0, "n": 2.0})
    direto = mt.isolar(
        mt.montar(mt.grafo_de_dados(dados)), "d", {"M_x": 5e5, "T": 3e5, "S_y": 350.0, "n": 2.0}
    )
    assert r.valor == pytest.approx(direto.valor)


def test_tirar_porta_publica_retira_o_fio_de_fora():
    novo = mc.agrupar(_dados("circular", "flexao", "von_mises", mb.RESULTADO), ["n0", "n1"])
    menos = mc.definir_portas(novo, "c1", [], [])
    assert all(f["de"] != "c1" for f in menos["fios"])


def test_acrescentar_porta_publica():
    novo = mc.agrupar(_dados("circular", "flexao", "von_mises", mb.RESULTADO), ["n0", "n1"])
    conjunto = next(n for n in novo["nos"] if n["id"] == "c1")
    entradas, saidas = mc.candidatas(conjunto)
    assert any(c["porta"] == "valor" for c in entradas)
    com = mc.definir_portas(novo, "c1", [("n1", "valor")], [("n1", "saida")])
    conjunto = next(n for n in com["nos"] if n["id"] == "c1")
    assert conjunto["portas"]["entradas"][0]["tipo"] == mb.VALOR


def test_apagar_bloco_de_dentro_tira_a_porta_morta():
    novo = mc.agrupar(_dados("circular", "flexao", "von_mises", mb.RESULTADO), ["n0", "n1"])
    conjunto = next(n for n in novo["nos"] if n["id"] == "c1")
    conjunto["grafo"]["nos"] = [n for n in conjunto["grafo"]["nos"] if n["id"] != "n1"]
    conjunto["grafo"]["fios"] = []
    limpo = mc.tirar_portas_mortas(novo)
    conjunto = next(n for n in limpo["nos"] if n["id"] == "c1")
    assert conjunto["portas"]["saidas"] == []
    assert all(f["de"] != "c1" for f in limpo["fios"])


def test_biblioteca_guarda_e_devolve(tmp_path):
    with mock.patch.object(mc, "ARQUIVO_USUARIO", tmp_path / "c.json"):
        novo = mc.agrupar(_dados("circular", "flexao", "von_mises", mb.RESULTADO), ["n0", "n1"])
        conjunto = next(n for n in novo["nos"] if n["id"] == "c1")
        mc.salvar("Eixo meu", mb.SOLIDOS, conjunto)
        catalogo = mc.catalogo_de_conjuntos(mb.SOLIDOS)
        assert [c["nome"] for c in catalogo] == ["Eixo meu"]
        assert catalogo[0]["chave"] == "conjunto:Eixo meu"
        assert mc.catalogo_de_conjuntos(mb.FLUIDOS) == []
        mc.remover("Eixo meu", mb.SOLIDOS)
        assert mc.catalogo_de_conjuntos(mb.SOLIDOS) == []


def test_conjunto_sem_nome_nao_salva(tmp_path):
    with mock.patch.object(mc, "ARQUIVO_USUARIO", tmp_path / "c.json"):
        with pytest.raises(mc.ErroDeConjunto, match="nome"):
            mc.salvar("  ", mb.SOLIDOS, {"grafo": {}, "portas": {}})


def test_biblioteca_corrompida_nao_quebra_a_lista(tmp_path):
    arquivo = tmp_path / "c.json"
    arquivo.write_text("{quebrado", encoding="utf-8")
    with mock.patch.object(mc, "ARQUIVO_USUARIO", arquivo):
        assert mc.listar(mb.SOLIDOS) == []


# ---------------------------------------------------------------------------
# Salvar e abrir
# ---------------------------------------------------------------------------


def _resposta(modelo_nome: str = "Base conhecida: achar a altura"):
    modelo = mm.PARTE_SOLIDOS.por_nome[modelo_nome]
    dados = modelo.grafo()
    m = mt.montar(mt.grafo_de_dados(dados))
    r = mt.isolar(m, modelo.alvo, modelo.valores)
    doc = rg.documento(mb.SOLIDOS, dados, modelo.valores, {}, modelo.alvo, None, U.escolhas)
    return m, r, doc


def test_arquivo_vai_e_volta():
    _, _, doc = _resposta()
    lido = rg.ler_documento(rg.em_json(doc), mb.SOLIDOS, g.SISTEMA_SOLIDOS)
    assert lido["alvo"] == "h"
    assert lido["valores"]["b"] == 50.0
    assert len(lido["grafo"]["nos"]) == 5


@pytest.mark.parametrize(
    ("conteudo", "trecho"),
    [
        (b"{quebrado", "JSON"),
        (b'{"formato": "outro"}', "não é uma montagem"),
    ],
)
def test_arquivo_ruim_explica(conteudo, trecho):
    with pytest.raises(rg.ErroDeArquivo, match=trecho):
        rg.ler_documento(conteudo, mb.SOLIDOS, g.SISTEMA_SOLIDOS)


def test_arquivo_da_outra_parte_explica():
    _, _, doc = _resposta()
    with pytest.raises(rg.ErroDeArquivo, match="outra parte"):
        rg.ler_documento(rg.em_json(doc), mb.FLUIDOS, g.SISTEMA_FLUIDOS)


def test_arquivo_com_valor_que_nao_e_numero_fica_sem_ele():
    _, _, doc = _resposta()
    bruto = json.loads(rg.em_json(doc))
    bruto["valores"]["b"] = "cinquenta"
    lido = rg.ler_documento(json.dumps(bruto), mb.SOLIDOS, g.SISTEMA_SOLIDOS)
    assert "b" not in lido["valores"]


def test_bloco_desconhecido_no_arquivo_nao_quebra():
    _, _, doc = _resposta()
    doc["grafo"]["nos"].append({"id": "x", "tipo": "nao_existe", "x": 0, "y": 0})
    lido = rg.ler_documento(rg.em_json(doc), mb.SOLIDOS, g.SISTEMA_SOLIDOS)
    assert all(no.tipo != "nao_existe" for no in mt.grafo_de_dados(lido["grafo"]).nos)


def test_assinatura_ignora_a_posicao_dos_blocos():
    _, _, doc = _resposta()
    outro = json.loads(json.dumps(doc))
    outro["grafo"]["nos"][0]["x"] = 999
    assert rg.assinatura(doc) == rg.assinatura(outro)
    outro["valores"]["b"] = 60.0
    assert rg.assinatura(doc) != rg.assinatura(outro)


def test_registro_tem_o_que_o_memorial_precisa():
    m, r, doc = _resposta()
    registro = rg.registro_tecnico(
        modulo="Montador de fórmulas",
        modulo_id="montador_formulas",
        dominio=mb.SOLIDOS,
        titulo="Viga do mezanino",
        resposta=r,
        montagem=m,
        doc=doc,
        u=U,
    )
    assert registro["modulo_id"] == "montador_formulas"
    assert registro["resultados"]["h (mm)"] == pytest.approx(37.947, rel=1e-3)
    assert registro["entradas"]["M_x (kN·m)"] == pytest.approx(2.0)
    assert registro["resultados"]["utilizacao"] == pytest.approx(1.0)
    assert "h ≥ 37,95 mm" in registro["conclusao"]
    assert registro["montagem"]["alvo"] == "h"
    assert registro["hash_calculo"]


def test_montagens_do_projeto_sem_as_superadas():
    m, r, doc = _resposta()
    registro = rg.registro_tecnico(
        modulo="Montador de fórmulas",
        modulo_id="montador_formulas",
        dominio=mb.SOLIDOS,
        titulo="A",
        resposta=r,
        montagem=m,
        doc=doc,
        u=U,
    )
    projeto = {"registros_tecnicos": [registro, {**registro, "id": "x", "status": "Superado"}]}
    assert [i["id"] for i in rg.montagens_do_projeto(projeto, "montador_formulas")] == [
        registro["id"]
    ]
    assert rg.montagens_do_projeto(None, "montador_formulas") == []


# ---------------------------------------------------------------------------
# Referências
# ---------------------------------------------------------------------------


def _projeto() -> dict:
    m, r, doc = _resposta()
    registro = rg.registro_tecnico(
        modulo="Montador de fórmulas",
        modulo_id="montador_formulas",
        dominio=mb.SOLIDOS,
        titulo="Viga",
        resposta=r,
        montagem=m,
        doc=doc,
        u=U,
    )
    outro = {
        "id": "mohr1",
        "modulo": "Círculo de Mohr",
        "titulo": "Estado plano",
        "status": "Calculado",
        "hash_calculo": "abc",
        "resultados": {"sigma_1_MPa": 120.0, "texto": "nada", "ok": True},
    }
    return {"registros_tecnicos": [registro, outro]}


def _dados_com_referencia(opcoes: dict) -> dict:
    dados = _dados("circular", "flexao", "von_mises", mb.RESULTADO)
    dados["nos"].append({"id": "r", "tipo": mb.REFERENCIA, "opcoes": opcoes})
    dados["fios"].append({"de": "r", "saida": "saida", "para": "n1", "entrada": "valor"})
    return dados


def test_fontes_tem_a_resposta_e_os_numeros_dos_outros_registros():
    fontes = rg.fontes_do_projeto(_projeto(), mb.SOLIDOS, U)
    chaves = {(f.campo, f.dimensao) for f in fontes}
    assert ("h", g.MEDIDA) in chaves
    assert ("sigma_1_MPa", g.TENSAO) in chaves
    assert not any(f.campo in ("texto", "ok") for f in fontes)


def test_referencia_traz_o_valor_e_troca_a_letra():
    projeto = _projeto()
    fonte = next(f for f in rg.fontes_do_projeto(projeto, mb.SOLIDOS, U) if f.campo == "M_x")
    m = mt.montar(mt.grafo_de_dados(_dados_com_referencia(rg.opcoes_da_fonte(fonte))))
    assert not m.erros
    assert "M_x" not in {item.chave for item in m.grandezas}
    r = mt.isolar(m, "d", {"S_y": 250.0, "n": 1.5})
    assert r.valor == pytest.approx((32 * 1.5 * 2e6 / (math.pi * 250)) ** (1 / 3))


def test_referencia_de_outra_grandeza_nao_liga():
    projeto = _projeto()
    fonte = next(f for f in rg.fontes_do_projeto(projeto, mb.SOLIDOS, U) if f.campo == "h")
    grafo = mt.grafo_de_dados(_dados_com_referencia(rg.opcoes_da_fonte(fonte)))
    assert not any(f.de == "r" for f in grafo.fios)


def test_referencia_sem_escolha_diz_o_que_falta():
    m = mt.montar(mt.grafo_de_dados(_dados_com_referencia({"dimensao": g.MOMENTO})))
    assert any("Escolha o cálculo" in erro for _, erro in m.erros)


def _diagnostico(projeto: dict, opcoes: dict) -> rg.Diagnostico:
    grafo = mt.grafo_de_dados(_dados_com_referencia(opcoes))
    return rg.conferir_referencias(grafo, projeto, mb.SOLIDOS, U)[0]


def _opcoes_de_mx(projeto: dict) -> dict:
    fonte = next(f for f in rg.fontes_do_projeto(projeto, mb.SOLIDOS, U) if f.campo == "M_x")
    return rg.opcoes_da_fonte(fonte)


def test_referencia_em_dia():
    projeto = _projeto()
    assert _diagnostico(projeto, _opcoes_de_mx(projeto)).situacao == rg.EM_DIA


def test_registro_apagado_e_referencia_ausente():
    projeto = _projeto()
    opcoes = _opcoes_de_mx(projeto)
    d = _diagnostico({"registros_tecnicos": []}, opcoes)
    assert d.situacao == rg.AUSENTE


def test_projeto_fechado_e_referencia_ausente():
    projeto = _projeto()
    assert _diagnostico(None, _opcoes_de_mx(projeto)).situacao == rg.AUSENTE


def test_registro_mudou_e_referencia_desatualizada():
    projeto = _projeto()
    opcoes = _opcoes_de_mx(projeto)
    registro = projeto["registros_tecnicos"][0]
    registro["hash_calculo"] = "outro"
    saida = next(s for s in registro["saidas_publicas"] if s["chave"] == "M_x")
    saida["valor"] = 3e6
    d = _diagnostico(projeto, opcoes)
    assert d.situacao == rg.DESATUALIZADA
    assert d.fonte.valor == pytest.approx(3e6)
    assert "Atualize" in d.mensagem


def test_campo_que_sumiu_e_incompativel():
    projeto = _projeto()
    opcoes = _opcoes_de_mx(projeto)
    projeto["registros_tecnicos"][0]["saidas_publicas"] = [
        s for s in projeto["registros_tecnicos"][0]["saidas_publicas"] if s["chave"] != "M_x"
    ]
    assert _diagnostico(projeto, opcoes).situacao == rg.INCOMPATIVEL


def test_registro_superado_avisa():
    projeto = _projeto()
    opcoes = _opcoes_de_mx(projeto)
    projeto["registros_tecnicos"][0]["status"] = "Superado"
    assert _diagnostico(projeto, opcoes).situacao == rg.DESATUALIZADA


def test_registro_guarda_a_dependencia_para_a_central_de_validacao():
    projeto = _projeto()
    opcoes = _opcoes_de_mx(projeto)
    dados = _dados_com_referencia(opcoes)
    m = mt.montar(mt.grafo_de_dados(dados))
    valores = {"S_y": 250.0, "n": 1.5}
    r = mt.isolar(m, "d", valores)
    doc = rg.documento(mb.SOLIDOS, dados, valores, {}, "d", None, U.escolhas)
    registro = rg.registro_tecnico(
        modulo="Montador de fórmulas",
        modulo_id="montador_formulas",
        dominio=mb.SOLIDOS,
        titulo="Eixo",
        resposta=r,
        montagem=m,
        doc=doc,
        u=U,
    )
    assert registro["dependencias_ids"] == [opcoes["registro"]]


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


def abrir(pagina: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.switch_page(pagina).run()
    assert not at.exception
    return at


def _tela(at: AppTest) -> str:
    return " ".join(e.proto.body for e in at.get("html"))


def test_pagina_de_fluidos_abre_e_responde():
    at = abrir("app_pages/montador_fluidos.py")
    assert any(s.value.startswith("**Q ≤") for s in at.success)


def test_todo_modelo_de_fluidos_abre_na_tela():
    at = abrir("app_pages/montador_fluidos.py")
    for modelo in mm.MODELOS_FLUIDOS:
        at.selectbox(key="mfl_modelo").set_value(modelo.nome).run()
        assert not at.exception, modelo.nome
        assert at.success, modelo.nome


def test_unidades_de_fluidos_convertem():
    at = abrir("app_pages/montador_fluidos.py")
    at.selectbox(key="mfl_u_vazao").set_value("L/s").run()
    assert not at.exception
    assert any("L/s" in s.value for s in at.success)


def test_as_duas_partes_nao_se_misturam():
    at = abrir("app_pages/montador_formulas.py")
    at.switch_page("app_pages/montador_fluidos.py").run()
    assert not at.exception
    assert "mf_grafo" in at.session_state
    assert "mfl_grafo" in at.session_state
    tipos = {n["tipo"] for n in at.session_state["mfl_grafo"]["nos"]}
    assert "trecho" in tipos


def test_trocar_de_modelo_deixa_voltar_com_os_valores():
    at = abrir("app_pages/montador_formulas.py")
    at.session_state["mf_valores"]["b"] = 77.0
    at.selectbox(key="mf_modelo").set_value("Eixo com flexão e torção").run()
    assert at.session_state["mf_valores"].get("b") is None
    at.button(key="mf_voltar").click().run()
    assert not at.exception
    assert at.session_state["mf_valores"]["b"] == 77.0


def test_limpar_deixa_voltar():
    at = abrir("app_pages/montador_formulas.py")
    at.button(key="mf_limpar").click().run()
    assert at.session_state["mf_grafo"]["nos"] == []
    at.button(key="mf_voltar").click().run()
    assert not at.exception
    assert len(at.session_state["mf_grafo"]["nos"]) == 5


def test_valor_adotado_na_tela():
    at = abrir("app_pages/montador_formulas.py")
    campo = next(n for n in at.number_input if n.label.startswith("Valor adotado"))
    campo.set_value(40.0).run()
    assert not at.exception
    assert any("maior uso é 90" in c.value for c in at.caption)


def test_adotado_abaixo_do_minimo_avisa_na_tela():
    at = abrir("app_pages/montador_formulas.py")
    campo = next(n for n in at.number_input if n.label.startswith("Valor adotado"))
    campo.set_value(30.0).run()
    assert any("não passa" in e.value for e in at.error)


def test_mudanca_mostra_antes_e_depois():
    at = abrir("app_pages/montador_formulas.py")
    campo = next(n for n in at.number_input if n.label.startswith("M_x"))
    campo.set_value(4.0).run()
    assert not at.exception
    assert any("→" in c.value and "M_x foi de 2 kN·m para 4 kN·m" in c.value for c in at.caption)


def test_selecionar_bloco_mostra_o_inspetor_dele():
    at = abrir("app_pages/montador_formulas.py")
    at.session_state["mf_selecao"] = {"tipo": "no", "id": "n2"}
    at.run()
    assert not at.exception
    assert any(n.label.startswith("M_x") for n in at.number_input)
    assert not any(n.label.startswith("b:") for n in at.number_input)


def test_selecionar_fio_mostra_as_tensoes_por_ponto():
    at = abrir("app_pages/montador_formulas.py")
    at.session_state["mf_selecao"] = {
        "tipo": "fio",
        "caminho": [],
        "de": "n3",
        "saida": "saida",
        "para": "n4",
        "entrada": "entrada",
    }
    at.run()
    assert not at.exception
    texto = _tela(at)
    assert "EstadoTensao" in texto
    assert "σ (MPa)" in texto
    assert "<td>166,7</td>" in texto
    assert "M_x" in texto  # o que a fila já somou


def test_selecionar_conjunto_mostra_os_valores_de_dentro():
    at = abrir("app_pages/montador_formulas.py")
    at.selectbox(key="mf_modelo").set_value("Eixo: estática e fadiga").run()
    at.session_state["mf_selecao"] = {"tipo": "no", "id": "c1"}
    at.run()
    assert not at.exception
    rotulos = {n.label.split(":")[0] for n in at.number_input}
    assert {"M_x", "M_y", "T"} <= rotulos


def test_valor_padrao_aparece_como_padrao():
    at = abrir("app_pages/montador_formulas.py")
    at.selectbox(key="mf_modelo").set_value("Coluna em compressão").run()
    assert not at.exception
    assert any("padrão do programa" in c.value for c in at.caption)


def test_seta_o_fluido_e_muda_a_resposta():
    at = abrir("app_pages/montador_fluidos.py")
    antes = next(s.value for s in at.success)
    at.selectbox(key=f"mfl_op_n1_fluido_r{at.session_state['mfl_revisao']}").set_value(
        "Água a 80 °C"
    ).run()
    assert not at.exception
    assert next(s.value for s in at.success) != antes


def test_unidades_nao_quebram_com_o_sistema_certo():
    assert isinstance(unidades_padrao(g.SISTEMA_FLUIDOS), Unidades)
    assert unidades_padrao(g.SISTEMA_FLUIDOS).rotulo(g.VAZAO) == "m³/h"
    assert U.rotulo(g.DISTRIBUIDA) == "kN/m"


# ---------------------------------------------------------------------------
# A ligação no inspetor
# ---------------------------------------------------------------------------

FIO_DA_FILA = {"de": "n3", "saida": "saida", "para": "n4", "entrada": "entrada"}


def _selecionar_fio(at: AppTest) -> AppTest:
    at.session_state["mf_selecao"] = {"tipo": "fio", "caminho": [], **FIO_DA_FILA}
    at.run()
    assert not at.exception
    return at


def test_so_cabe_no_fio_quem_recebe_e_devolve_o_que_passa():
    dados = _dados(*RET)
    fio = dados["fios"][1]
    chaves = mc.compativeis(dados, fio, mb.SOLIDOS)
    assert "cortante" in chaves
    assert "von_mises" not in chaves  # o critério não devolve a fila
    assert mb.RESULTADO not in chaves
    assert "fluido" not in chaves


def test_inserir_no_fio_cria_um_bloco_e_dois_fios():
    dados = _dados(*RET)
    fio = dados["fios"][1]
    nos, fios = len(dados["nos"]), len(dados["fios"])
    novo, id_ = mc.inserir_no_fio(dados, fio, "cortante")
    assert len(novo["nos"]) == nos + 1
    assert len(novo["fios"]) == fios + 1
    assert fio not in novo["fios"]
    assert any(f["de"] == fio["de"] and f["para"] == id_ for f in novo["fios"])
    assert any(f["de"] == id_ and f["para"] == fio["para"] for f in novo["fios"])
    assert len(dados["nos"]) == nos  # o desenho de entrada não muda


def test_inserir_bloco_que_nao_cabe_e_recusado():
    dados = _dados(*RET)
    with pytest.raises(mc.ErroDeConjunto):
        mc.inserir_no_fio(dados, dados["fios"][1], "von_mises")


def test_tirar_fio_deixa_os_blocos():
    dados = _dados(*RET)
    novo = mc.tirar_fio(dados, dados["fios"][0])
    assert len(novo["fios"]) == len(dados["fios"]) - 1
    assert len(novo["nos"]) == len(dados["nos"])


def test_ligacao_conferida_de_verdade():
    dados = _dados(*RET)
    assert all(certo for _, certo in mc.conferir_fio(dados, dados["fios"][0]))
    errado = {"de": "n1", "saida": "saida", "para": "n0", "entrada": "entrada"}
    dados["nos"][0]["tipo"] = "flexao"
    dados["fios"].append(errado)
    resultado = dict(mc.conferir_fio(dados, errado))
    assert resultado["Sem laço na montagem"] is False


def test_tela_insere_bloco_na_ligacao():
    at = _selecionar_fio(abrir("app_pages/montador_formulas.py"))
    grafo = at.session_state["mf_grafo"]
    nos, fios = len(grafo["nos"]), len(grafo["fios"])
    at.selectbox(key="mf_inserir_bloco").set_value("concentracao").run()
    at.button(key="mf_inserir").click().run()
    assert not at.exception
    grafo = at.session_state["mf_grafo"]
    assert len(grafo["nos"]) == nos + 1
    assert len(grafo["fios"]) == fios + 1
    selecao = at.session_state["mf_selecao"]
    assert selecao["tipo"] == "no"  # o bloco novo já vem selecionado
    assert any(n["id"] == selecao["id"] and n["tipo"] == "concentracao" for n in grafo["nos"])
    assert "Concentração" in _tela(at)


def test_tela_desfaz_a_ligacao():
    at = _selecionar_fio(abrir("app_pages/montador_formulas.py"))
    fios = len(at.session_state["mf_grafo"]["fios"])
    at.button(key="mf_tirar_fio").click().run()
    assert not at.exception
    assert len(at.session_state["mf_grafo"]["fios"]) == fios - 1
    assert at.session_state["mf_selecao"] is None


def test_bloco_leva_para_a_ligacao_de_saida():
    at = abrir("app_pages/montador_formulas.py")
    at.session_state["mf_selecao"] = {"tipo": "no", "id": "n3"}
    at.run()
    at.button(key="mf_ver_saida_n3").click().run()
    assert not at.exception
    selecao = at.session_state["mf_selecao"]
    assert selecao["tipo"] == "fio"
    assert selecao["de"] == "n3"
    assert "Dados transportados" in _tela(at)


def test_rastrear_explica_quem_manda():
    at = abrir("app_pages/montador_formulas.py")
    at.button(key="mf_rastrear").click().run()
    assert not at.exception
    assert at.session_state["mf_selecao"]["tipo"] == "no"
    texto = _tela(at)
    assert "Quem manda" in texto
    assert "é quem decide" in texto
    assert "Pré-dimensionamento" in texto


def test_cartoes_mostram_valores_e_resposta():
    at = abrir("app_pages/montador_formulas.py")
    grafo = mt.grafo_de_dados(at.session_state["mf_grafo"])
    base = mt.montar(grafo)
    alvo = at.session_state["mf_alvo"]
    valores = at.session_state["mf_valores"]
    resposta = mt.isolar(base, alvo, valores, None)
    from components.montador_ui import _faces

    faces, luzes = _faces(grafo, at.session_state["mf_grafo"], base, resposta, valores, alvo, U)
    resultado = next(n.id for n in grafo.nos if n.tipo == mb.RESULTADO)
    assert faces[resultado]["b"] == rg.texto_da_resposta(resposta, U)
    assert "manda" in faces[resultado]["a"]
    assert luzes[resultado] == "ok"
    assert any("Utilização = " in f.get("a", "") for f in faces.values())
    assert any(" = ?" in f.get("a", "") for f in faces.values())  # a letra pedida


def test_conjunto_soma_o_cartao_de_dentro():
    at = abrir("app_pages/montador_formulas.py")
    at.selectbox(key="mf_modelo").set_value("Eixo: estática e fadiga").run()
    dados = at.session_state["mf_grafo"]
    grafo = mt.grafo_de_dados(dados)
    base = mt.montar(grafo)
    alvo = at.session_state["mf_alvo"]
    valores = at.session_state["mf_valores"]
    from components.montador_ui import _faces

    faces, luzes = _faces(grafo, dados, base, None, valores, alvo, U)
    assert "M_x = " in faces["c1"]["a"]
    assert luzes["c1"] in ("ok", "falta")


def test_numero_grande_nao_vai_em_notacao_cientifica():
    from components.montador_ui import _numero

    assert _numero(200000.0) == "200.000"
    assert _numero(32.84) == "32,84"
    assert "e+" not in _numero(1.5e7)


def test_uma_condicao_no_singular():
    from components.montador_ui import _situacao

    grafo = mt.grafo_de_dados(_dados(*RET[:2], "von_mises", mb.RESULTADO))
    base = mt.montar(grafo)
    resposta = mt.isolar(base, "h", {"b": 50.0, "M_x": 2e6, "S_y": 250.0, "n": 1.5})
    texto = _situacao(grafo, base, resposta, "", (), (), False)["detalhe"]
    assert len(base.condicoes) > 0
    assert ("condição" in texto) == (len(base.condicoes) == 1)


def test_conjunto_novo_nao_cai_em_cima_de_outro_bloco():
    # Fila quebrada em linhas: o menor x e o menor y juntos dão a casa de um bloco de fora.
    dados = _dados(*RET)
    casas = [(30, 30), (246, 30), (30, 170), (246, 170), (30, 310)]
    for no, (x, y) in zip(dados["nos"], casas, strict=True):
        no["x"], no["y"] = x, y
    novo = mc.agrupar(dados, ["n1", "n2"], "")
    conjunto = next(n for n in novo["nos"] if n["tipo"] == mt.CONJUNTO)
    fora = [(n["x"], n["y"]) for n in novo["nos"] if n is not conjunto]
    assert (conjunto["x"], conjunto["y"]) == (246, 30)
    assert (conjunto["x"], conjunto["y"]) not in fora


def test_selecao_de_fio_apagado_nao_derruba_o_inspetor():
    at = _selecionar_fio(abrir("app_pages/montador_formulas.py"))
    dados = at.session_state["mf_grafo"]
    assert mc.fio_existe(dados, FIO_DA_FILA)
    at.session_state["mf_grafo"] = mc.tirar_fio(dados, FIO_DA_FILA)
    at.run()
    assert not at.exception
    assert "Valores da montagem" in _tela(at)
    assert not mc.fio_existe(at.session_state["mf_grafo"], FIO_DA_FILA)
    assert not mc.fio_existe(dados, FIO_DA_FILA, ["c9"])


def test_biblioteca_comeca_pelo_que_abre_a_montagem():
    def grupos(dominio: str) -> list[str]:
        return list(dict.fromkeys(b["grupo"] for b in mb.catalogo_para_tela(dominio)))

    assert grupos(mb.FLUIDOS)[0] == mb.GRUPO_FLUIDO
    assert grupos(mb.SOLIDOS)[0] == mb.GRUPO_SECAO
    assert all(b["categoria"] for b in mb.catalogo_para_tela(mb.SOLIDOS))
    assert all(b["categoria"] for b in mb.catalogo_para_tela(mb.FLUIDOS))


def test_campo_nao_mostra_o_ruido_da_conversao():
    from components.montador_ui import _para_o_campo

    assert _para_o_campo(4.5e-5, 1e-3) == 0.045
    assert _para_o_campo(None, 1e-3) is None
