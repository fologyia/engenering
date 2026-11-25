"""Pontos da auditoria de 24/11/2026 (U 6" × 12,20, rotulada em x, 2 × 3/4", químico)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from core import base_de_pilar as bp

U6 = bp.EntradaBase(
    perfil='U 6" x 12,20', tipo=bp.TIPO_ROTULADA_X, n_chumbadores=2, chumbador='3/4"',
    t_placa_mm=12.7, ancoragem=bp.ANCORAGEM_QUIMICO, h_ef_mm=200, e_n_mm=50,
    n_rd_fabricante_kN=106, perna_pilar_mm=5, cortante=bp.CORTANTE_DIRETOS,
    n_sd_kN=3.99, m_sd_kNm=0.59, m_sd_y_kNm=0.46, v_sd_kN=4.65,
)  # fmt: skip


def _nomes(r: bp.ResultadoBase) -> dict[str, bp.Verificacao]:
    return {v.nome: v for v in r.verificacoes}


@pytest.mark.parametrize("m_y", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0])
def test_equilibrio_elastico_vale_pelos_residuos(m_y):
    """Antes, M_y = 3, 5 e 8 saíam "sem equilíbrio" com o equilíbrio satisfeito (parada do Newton
    por arredondamento). Agora vale o resíduo: ∫σ − ΣF = N, ∫σx − ΣFx = M, ∫σy − ΣFy = M_y."""
    e = replace(U6, m_sd_y_kNm=m_y)
    g = bp.geometria(e)
    a_se = bp.area_resistente(e, bp.disposicoes(e))
    d = bp.distribuicao_elastica(g, 3990.0, 0.59e6, m_y * 1e6, 25.0, a_se)
    assert d.equilibrio
    w0, ax, ay = d.plano
    a, sx, sy, ixx, ixy, iyy = bp._momentos_do_poligono(list(d.zona))
    f = d.forcas
    pos = g.posicoes
    assert w0 * a + ax * sx + ay * sy - sum(f) == pytest.approx(3990.0, rel=1e-6)
    assert w0 * sx + ax * ixx + ay * ixy - sum(
        fi * x for fi, (x, _) in zip(f, pos, strict=True)
    ) == pytest.approx(0.59e6, rel=1e-6)
    assert w0 * sy + ax * ixy + ay * iyy - sum(
        fi * y for fi, (_, y) in zip(f, pos, strict=True)
    ) == pytest.approx(m_y * 1e6, rel=1e-6)
    r = bp.calcular(replace(e, distribuicao=bp.DISTRIBUICAO_ELASTICA))
    assert _nomes(r)["Equilíbrio elástico da placa"].status == "OK"


def test_sem_equilibrio_nao_mostra_espessura_nem_forcas():
    """Bloco uniforme sem solução (M_y = 10 kN·m): antes a espessura saía "OK" com t_p,min = 0."""
    r = bp.calcular(replace(U6, m_sd_y_kNm=10.0))
    nomes = _nomes(r)
    assert nomes["Equilíbrio possível com a placa (flexão oblíqua)"].status == "NÃO OK"
    placa = nomes["Placa de base: espessura t_p ≥ t_p,min"]
    assert placa.status == "NÃO OK" and placa.solicitante is None
    assert placa.formula.startswith(bp.SEM_EQUILIBRIO)
    assert nomes["Ancoragem no concreto"].status == "NÃO OK"
    # o que só usa N, V ou a geometria continua valendo
    assert nomes["Chumbador: aço à cortante (ACI 318-19)"].solicitante == pytest.approx(4.65)
    assert any("Sem equilíbrio" in a for a in r.avisos)


def test_com_equilibrio_nada_e_invalidado():
    r = bp.calcular(U6)
    assert not any(v.formula.startswith(bp.SEM_EQUILIBRIO) for v in r.verificacoes)


@pytest.mark.parametrize(("n_b", "engatados"), [(2, 1), (4, 2), (6, 2), (8, 2)])
def test_direto_no_furo_conta_metade_dos_chumbadores(n_b, engatados):
    assert bp.engatados_sem_arruela(n_b) == engatados


def test_base_de_dois_chumbadores_direto_no_furo_um_leva_a_cortante():
    linha = _nomes(bp.calcular(U6))["Chumbador: aço à cortante (ACI 318-19)"]
    assert linha.solicitante == pytest.approx(4.65)  # V_Sd inteiro, não V/2
    assert "só 1 de 2" in linha.formula


def test_trecho_interno_curto_da_solda_nao_cria_reprovacao_separada():
    e = replace(U6, solda_mesas_por_dentro=True)
    r, so_externa = bp.calcular(e), bp.calcular(replace(e, solda_mesas_por_dentro=False))
    nomes = _nomes(r)
    assert "Solda do pilar na placa: comprimento dos trechos internos da mesa" not in nomes
    # O trecho curto não entra na resistência; a solda restante continua verificada no grupo.
    nome_filete = "Solda do pilar na placa: filete no ponto mais solicitado"
    assert nomes[nome_filete].solicitante == pytest.approx(
        _nomes(so_externa)[nome_filete].solicitante
    )


def test_espessura_mostra_a_razao_em_t_e_em_t_ao_quadrado():
    r = bp.calcular(U6)
    linha = _nomes(r)["Placa de base: espessura t_p ≥ t_p,min"]
    razao = r.t_p_min / 12.7
    assert f"{100 * razao:.0f} %" in linha.formula
    assert f"{100 * razao**2:.0f} %" in linha.formula


def test_cortante_divergente_e_equilibrio_parcial_ficam_explicitos():
    r = bp.calcular(replace(U6, vx_kN=3.0, vy_kN=4.0, v_sd_kN=7.0))
    linhas = _nomes(r)
    assert linhas["Resultante de cortante divergente"].status == "ALERTA"
    assert linhas["Equilíbrio do cortante nos chumbadores"].status == "ALERTA"
    assert "5,0000" in linhas["Componentes simultâneas do cortante"].formula


def test_u_espelhado_identifica_eixos_internos():
    r = bp.calcular(replace(U6, m_sd_y_kNm=-0.46))
    texto = _nomes(r)["Pilar U: método da 6.7 estendido"].formula
    assert "−y" in texto and "espelhados" in texto


def test_graute_aplica_reducao_sem_flexao_separada():
    r = bp.calcular(replace(U6, cortante=bp.CORTANTE_ARRUELAS))
    linhas = _nomes(r)
    assert bp.LINHA_FLEXAO_NA_ARGAMASSA not in linhas
    assert "0,80" in linhas["Chumbador: aço à cortante (ACI 318-19)"].formula
    assert "excepcionalmente" in linhas["Graute: hipótese para o cortante dos chumbadores"].formula


def test_tracao_sem_contato_equilibra_forcas_e_momentos():
    g = bp.geometria(U6)
    area = bp.area_resistente(U6, bp.disposicoes(U6))
    d = bp.distribuicao_elastica(g, -100000, 1e6, 0, 25, area)
    assert d.equilibrio and not d.zona and d.compressao == 0
    assert sum(d.forcas) == pytest.approx(100000, abs=1e-7)
    assert -sum(f * x for f, (x, _) in zip(d.forcas, g.posicoes, strict=True)) == pytest.approx(
        1e6, abs=1e-5
    )


def test_faixa_critica_fora_do_aco_mostra_sensibilidade_sem_afrouxar():
    """Terceira auditoria: a faixa de 21 mm caía fora das mesas do U. O adotado continua o da linha
    inteira (a favor da segurança); o texto traz o valor com apoio a 45° só como sensibilidade."""
    e = replace(U6, chumbador="5/8\"", por_formula=True, ancoragem=bp.ANCORAGEM_PORCA,
                lx_mm=260, ly_mm=94, a1_mm=26.8, h_ef_mm=0, n_rd_fabricante_kN=0,
                n_sd_kN=2.942, m_sd_kNm=1.064, m_sd_y_kNm=-0.6762, v_sd_kN=7.5593)  # fmt: skip
    placa = _nomes(bp.calcular(e))["Placa de base: espessura t_p ≥ t_p,min"]
    assert placa.solicitante > 20.0
    assert "Sensibilidade, não adotada" in " ".join(map(str, placa.equacoes))


def test_historico_da_busca_distingue_alerta_erro_e_aprovacao(monkeypatch):
    from types import SimpleNamespace

    entrada = replace(U6, por_formula=True, chumbador=bp.CHUMBADOR_LIVRE)
    monkeypatch.setattr(bp, "ESPESSURAS_COMERCIAIS", (6.3, 8.0, 10.0, 12.7))

    def calcular_falso(e):
        if e.t_placa_mm == 6.3:
            raise bp.BaseInvalida("geometria incompatível")
        if e.t_placa_mm == 8.0:
            return SimpleNamespace(
                status="ALERTA",
                aproveitamento_maximo=0.8,
                verificacoes=(SimpleNamespace(status="ALERTA", nome="Modelo pendente"),),
            )
        return SimpleNamespace(
            status="OK", aproveitamento_maximo=0.7, verificacoes=(), massa_da_placa_kg=2.0
        )

    monkeypatch.setattr(bp, "calcular", calcular_falso)
    melhor, historico = bp.buscar_base_mais_leve(entrada)
    assert melhor is not None
    assert [c.status for c in historico] == ["Entrada inválida", "ALERTA", "OK"]
    assert historico[0].motivos == ("geometria incompatível",)
    assert historico[1].motivos == ("ALERTA: Modelo pendente",)
    assert historico[-1].espessura_mm == 10.0  # 12,7 mm não foi avaliada


def test_envoltoria_identifica_origem_de_textos_informativos_distintos():
    casos = (
        bp.CasoDeCarga("C01", 5, 0, 0, 0, vx_kN=3, vy_kN=4),
        bp.CasoDeCarga("C02", 5, 0, 0, 0, vx_kN=6, vy_kN=8),
    )
    r = bp.calcular(replace(U6, casos=casos))
    linha = _nomes(r)["Componentes simultâneas do cortante"]
    assert linha.formula.startswith("[C01]") or linha.formula.startswith("[C02]")


def test_distribuicao_cortante_equilibra_forcas_e_torcao_com_centro_deslocado():
    pos = ((10.0, 20.0), (110.0, 20.0), (10.0, 120.0))
    vx, vy, mz = 3000.0, -4000.0, 750000.0
    reacoes = bp.distribuir_cortante_elastico(pos, vx, vy, mz)
    assert sum(x for x, _ in reacoes) == pytest.approx(vx)
    assert sum(y for _, y in reacoes) == pytest.approx(vy)
    assert sum(
        x * fy - y * fx for (x, y), (fx, fy) in zip(pos, reacoes, strict=True)
    ) == pytest.approx(mz)


def test_distribuicao_nao_inventa_reacao_para_torcao_em_um_chumbador():
    with pytest.raises(bp.BaseInvalida):
        bp.distribuir_cortante_elastico(((0.0, 0.0),), 0.0, 0.0, 1000.0)


def test_transicao_do_contato_com_momentos_em_dois_eixos():
    from tests.test_base_de_pilar_revisao import BASE

    g = bp.geometria(BASE)
    area = bp.area_resistente(BASE, bp.disposicoes(BASE))
    normal = -100_000.0
    sx2 = sum(x * x for x, _ in g.posicoes)
    sy2 = sum(y * y for _, y in g.posicoes)
    limite = (-normal / len(g.posicoes)) / (g.lx / (2 * sx2) + 0.4 * g.ly / (2 * sy2))
    for fator in (0.999, 1.001):
        mx, my = limite * fator, 0.4 * limite * fator
        d = bp.distribuicao_elastica(g, normal, mx, my, 25.0, area)
        assert d.equilibrio
        if fator < 1:
            assert d.compressao == 0 and not d.zona
            for f, (x, y) in zip(d.forcas, g.posicoes, strict=True):
                esperado = -normal / len(g.posicoes) - mx * x / sx2 - my * y / sy2
                assert f == pytest.approx(esperado, abs=1e-7)
        else:
            assert d.compressao > 0 and d.zona
        w0, ax, ay = d.plano
        if d.zona:
            a, sx, sy, ixx, ixy, iyy = bp._momentos_do_poligono(list(d.zona))
            c = w0 * a + ax * sx + ay * sy
            cx = w0 * sx + ax * ixx + ay * ixy
            cy = w0 * sy + ax * ixy + ay * iyy
        else:
            c = cx = cy = 0.0
        assert c - sum(d.forcas) == pytest.approx(normal, abs=0.1)
        assert cx - sum(
            f * x for f, (x, _) in zip(d.forcas, g.posicoes, strict=True)
        ) == pytest.approx(mx, abs=20)
        assert cy - sum(
            f * y for f, (_, y) in zip(d.forcas, g.posicoes, strict=True)
        ) == pytest.approx(my, abs=20)


def test_arruelas_soldadas_exigem_escolha_e_sao_verificadas():
    direto = _nomes(bp.calcular(U6))
    soldado = _nomes(bp.calcular(replace(U6, cortante=bp.CORTANTE_ARRUELAS)))
    chave = "Chumbador: aço à cortante (ACI 318-19)"
    assert direto[chave].solicitante == pytest.approx(4.65)
    assert soldado[chave].solicitante == pytest.approx(4.65 / 2)
    assert any(nome.startswith("Solda das arruelas na placa") for nome in soldado)
    assert not any(nome.startswith("Solda das arruelas na placa") for nome in direto)
