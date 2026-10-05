"""Barras comprimidas e flexo-comprimidas: verificação completa pela NBR 8800 e pelo AISC 360-16.

Uma única rodada calcula, para a mesma barra:

* **todos os modos de flambagem elástica** — flexão em x, flexão em y, torção, flexo-torção
  monossimétrica e, para seção assimétrica, a menor raiz da equação cúbica — e adota o menor
  ``N_e`` (NBR 5.3.5; AISC E3/E4);
* **flambagem local** pelo fator ``Q = Q_s·Q_a`` (NBR 8800:2008, Anexo F) ou pela área efetiva
  ``A_ef`` (Projeto NBR 8800:2024 e AISC 360-16, Tabelas 4 e 5) e a resistência
  ``N_c,Rd = χ·Q·A_g·f_y/γ_a1`` (ou ``χ·A_ef·f_y·φ``);
* **flexão** em x e em y — FLT, FLM e FLA, com o limite ``1,5·W·f_y`` — e os momentos
  amplificados por ``B_1`` com o comprimento real da barra no plano de flexão (K = 1);
* a **interação N + M_x + M_y numa única equação** (NBR 5.5.1.2; AISC H1-1);
* o **critério Anglo** AA-BR-DPST-DR-0001: esbeltez limite (8.3) e espessuras mínimas (8.8).

As fórmulas estão em :mod:`core.column_design` (porte do módulo de referência, validado contra o
AISC Design Guide 29 e o exemplo do programa). Este módulo as encadeia, monta a tabela de
verificações de oito colunas (:mod:`core.verificacao`) e **não conserta entradas em silêncio**:
tubo circular com D/t > 0,45·E/f_y, alma esbelta ou tubo não compacto na flexão, ``N_Sd ≥ N_e``
no ``B_1``, seção sem ``Z`` ou sem rotina de ``M_Rd`` viram linhas NÃO OK que bloqueiam o resultado.

Unidades: comprimentos em mm, tensões em MPa, forças em kN e momentos em kN·m.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from core import column_design as cd
from core.column_design import Secao
from core.steel_sections import (
    PerfilAco,
    centro_de_cisalhamento_do_perfil,
    centroide_do_perfil,
    constante_de_empenamento_estimada,
    e_tubo_circular,
    e_tubo_retangular,
    familia_do_perfil,
)
from core.technical_records import criar_registro_tecnico
from core.verificacao import (
    STATUS_REGISTRO,
    Verificacao,
    formatar_percentual,
    linhas_para_registro,
    status_geral,
)

NORMAS = cd.NORMAS
NORMAS_ROTULOS = {
    "NBR8800_2008": "ABNT NBR 8800:2008",
    "NBR8800_2024": "Projeto NBR 8800:2024",
    "AISC360_16_LRFD": "AISC 360-16 (LRFD)",
}
GAMMA_A1 = 1.10  # escoamento, flambagem e instabilidade (NBR 8800 Tabela 3)
ESBELTEZ_MAXIMA = 200.0  # Anglo 8.3 (obrigatório); NBR 5.3.4.1 / Projeto 5.3.7 (recomendação)
ESBELTEZ_MAXIMA_TRACAO = 300.0


# Coeficientes de ponderação das ações (Tabela 1, combinações normais):
# permanente de pequena variabilidade (estrutura metálica) 1,25; permanente
# de grande variabilidade ou variável em geral 1,40; equipamentos e
# sobrecargas 1,50. O padrão 1,40/1,40 é o par usual de pré-projeto.
GAMMA_G_PADRAO = 1.40
GAMMA_Q_PADRAO = 1.40
COEFICIENTES_PERMANENTE: dict[str, float] = {
    "Peso próprio de estrutura metálica (γ_g = 1,25)": 1.25,
    "Peso próprio de estrutura pré-moldada (γ_g = 1,30)": 1.30,
    "Elementos industrializados com adições in loco (γ_g = 1,40)": 1.40,
    "Elementos construtivos em geral e equipamentos (γ_g = 1,50)": 1.50,
}
COEFICIENTES_VARIAVEL: dict[str, float] = {
    "Vento (γ_q = 1,40)": 1.40,
    "Ações variáveis em geral / sobrecarga (γ_q = 1,50)": 1.50,
    "Ações truncadas / recalques (γ_q = 1,20)": 1.20,
}

# Coeficiente de Poisson do aço (NBR 8800 4.5.2.9: E = 200 000 MPa,
# G = 77 000 MPa → ν = 0,3).
POISSON_ACO = 0.3


# Fator de comprimento de flambagem K por condição de apoio idealizada
# (Tabela E.1 da NBR 8800, valores teóricos).
CONDICOES_APOIO: dict[str, float] = {
    "Biapoiada (pino-pino)": 1.0,
    "Engastada-livre (em balanço)": 2.0,
    "Engastada-pino": 0.70,
    "Biengastada": 0.50,
    "Biengastada com translação (deslocável)": 1.0,
    "Engastada-pino com translação (deslocável)": 2.0,
}

# Valores recomendados para projeto (Tabela E.1): ligações reais nunca são o
# engaste perfeito, então K sobe.
CONDICOES_APOIO_RECOMENDADAS: dict[str, float] = {
    "Biapoiada (pino-pino)": 1.0,
    "Engastada-livre (em balanço)": 2.1,
    "Engastada-pino": 0.80,
    "Biengastada": 0.65,
    "Biengastada com translação (deslocável)": 1.2,
    "Engastada-pino com translação (deslocável)": 2.0,
}

# Faixa física de K: 0,5 é o mínimo teórico (biengastada) e acima de 3 só
# em pórtico muito deslocável; fora disso quase sempre é erro de digitação.
K_MINIMO, K_MAXIMO = 0.5, 3.0


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número finito maior que zero.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} não pode ser negativo.")
    return valor


# ---------------------------------------------------------------------------
# Ações de cálculo
# ---------------------------------------------------------------------------


def forca_de_calculo(
    permanente_N: float,
    variavel_N: float = 0.0,
    *,
    gamma_g: float = GAMMA_G_PADRAO,
    gamma_q: float = GAMMA_Q_PADRAO,
) -> float:
    """``N_Sd = γ_g·N_g + γ_q·N_q`` (combinação normal, 4.7.7)."""
    ng = _nao_negativo("permanente_N", permanente_N)
    nq = _nao_negativo("variavel_N", variavel_N)
    gg = _positivo("gamma_g", gamma_g)
    gq = _positivo("gamma_q", gamma_q)
    return gg * ng + gq * nq


# ---------------------------------------------------------------------------
# Mão-francesa: força inclinada chegando na coluna
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EsforcosMaoFrancesa:
    """Componentes e momento que a mão-francesa descarrega na coluna.

    ``forca_N`` é a força de cálculo na barra da mão-francesa; ``theta`` é o
    ângulo entre a barra e o eixo da coluna. A componente horizontal ``H``
    flete a coluna com braço ``a`` (altura do nó em relação à base); a
    vertical ``V`` soma à compressão e, se chega fora do eixo, gera ``V·e``.
    """

    forca_N: float
    angulo_graus: float
    componente_vertical_N: float
    componente_horizontal_N: float
    altura_no_mm: float
    comprimento_mm: float
    vinculo: str
    excentricidade_mm: float
    momento_horizontal_Nmm: float
    momento_excentricidade_Nmm: float
    momento_Nmm: float
    expressao: str


# Momento máximo na coluna por uma força horizontal H aplicada a ``a`` da
# base, para os vínculos usuais da coluna no plano da mão-francesa.
VINCULOS_MAO_FRANCESA: tuple[str, ...] = (
    "Engastada na base, topo livre (balanço)",
    "Biapoiada (pino na base, topo travado)",
    "Engastada na base, topo apoiado",
)


def _momento_forca_horizontal(h: float, a: float, l: float, vinculo: str) -> tuple[float, str]:
    if vinculo == VINCULOS_MAO_FRANCESA[0]:
        return h * a, "M = H·a (engaste na base)"
    if vinculo == VINCULOS_MAO_FRANCESA[1]:
        return h * a * (l - a) / l, "M = H·a·(L − a)/L (sob o nó)"
    if vinculo == VINCULOS_MAO_FRANCESA[2]:
        b = l - a
        m_base = h * a * b * (l + b) / (2.0 * l**2)
        m_no = h * a**2 * b * (3.0 * l - a) / (2.0 * l**3)
        if m_base >= m_no:
            return m_base, "M = H·a·b·(L + b)/(2L²) (engaste na base)"
        return m_no, "M = H·a²·b·(3L − a)/(2L³) (sob o nó)"
    raise ValueError(f"Vínculo desconhecido: {vinculo!r}. Use um de {VINCULOS_MAO_FRANCESA}.")


def esforcos_mao_francesa(
    forca_N: float,
    angulo_graus: float,
    altura_no_mm: float,
    comprimento_mm: float,
    vinculo: str = VINCULOS_MAO_FRANCESA[0],
    excentricidade_mm: float = 0.0,
) -> EsforcosMaoFrancesa:
    """Decompõe a força da mão-francesa e obtém o momento que ela impõe à coluna.

    ``V = F·cos θ`` e ``H = F·sin θ`` (θ entre a barra e a coluna; 45° é o
    usual). O momento da componente horizontal depende do vínculo da coluna
    (:data:`VINCULOS_MAO_FRANCESA`); o da excentricidade, ``V·e``, é somado
    integralmente — conservador, já que só no engaste de base ele chega
    inteiro à seção crítica.
    """
    f = _nao_negativo("forca_N", forca_N)
    theta = float(angulo_graus)
    if not math.isfinite(theta) or not 0.0 < theta < 90.0:
        raise ValueError("angulo_graus deve ficar entre 0 e 90 (exclusive).")
    a = _positivo("altura_no_mm", altura_no_mm)
    l = _positivo("comprimento_mm", comprimento_mm)
    if a > l:
        raise ValueError("altura_no_mm não pode passar do comprimento da coluna.")
    e = _nao_negativo("excentricidade_mm", excentricidade_mm)
    rad = math.radians(theta)
    v, h = f * math.cos(rad), f * math.sin(rad)
    m_h, expressao = _momento_forca_horizontal(h, a, l, vinculo)
    m_e = v * e
    return EsforcosMaoFrancesa(
        forca_N=f,
        angulo_graus=theta,
        componente_vertical_N=v,
        componente_horizontal_N=h,
        altura_no_mm=a,
        comprimento_mm=l,
        vinculo=vinculo,
        excentricidade_mm=e,
        momento_horizontal_Nmm=m_h,
        momento_excentricidade_Nmm=m_e,
        momento_Nmm=m_h + m_e,
        expressao=expressao + (" + V·e" if m_e > 0 else ""),
    )


def _avisos_de_entrada(
    kx: float, ky: float, modulo_elasticidade_MPa: float, escoamento_MPa: float
) -> list[str]:
    avisos: list[str] = []
    for nome, k in (("Kx", kx), ("Ky", ky)):
        if not K_MINIMO <= k <= K_MAXIMO:
            avisos.append(
                f"{nome} = {k:g} está fora da faixa física usual ({K_MINIMO:g} a "
                f"{K_MAXIMO:g}): 0,5 é o mínimo teórico (biengastada) e acima de 3 "
                "só em pórtico muito deslocável. Confira o valor."
            )
    e_gpa = modulo_elasticidade_MPa / 1_000.0
    if not 0.5 <= e_gpa <= 1_000.0:
        avisos.append(
            f"E = {e_gpa:.4g} GPa está fora da faixa de qualquer material de "
            "engenharia (0,5 a 1 000 GPa). Este módulo espera E em MPa "
            "(aço ≈ 200 000)."
        )
    if escoamento_MPa > 0.05 * modulo_elasticidade_MPa:
        avisos.append(
            f"f_y/E = {escoamento_MPa / modulo_elasticidade_MPa:.3g} corresponde a "
            "deformação de escoamento acima de 5 %, que nenhum material estrutural "
            "tem. Confira as unidades: f_y e E em MPa."
        )
    return avisos


# ---------------------------------------------------------------------------
# Textos de apresentação (a interface e o registro usam os mesmos)
# ---------------------------------------------------------------------------

NOMES_GRUPO = {
    1: "parede de tubo retangular",
    2: "alma",
    3: "aba de cantoneira",
    4: "mesa de perfil laminado",
    5: "mesa de perfil soldado",
    6: "talão de T",
}

#: O que esta verificação deliberadamente não cobre.
FORA_DO_ESCOPO = (
    "Cantoneira simples, com regras próprias de esbeltez e excentricidade (NBR 5.3.5.4).",
    "Barras compostas (NBR 5.3.6, N_e,m).",
    "Cisalhamento na barra (NBR 5.4.3): só é avisado quando há mão-francesa ou força transversal.",
    "Efeitos globais de segunda ordem (B₂), deslocabilidade do pórtico e cargas nocionais — "
    "pertencem à análise da estrutura.",
    "Barra tracionada (λ ≤ 300, Anglo 8.3): verifique em Estruturas de aço (NBR 5.2).",
    "Fadiga, cargas dinâmicas e de impacto.",
    "Perfis formados a frio (NBR 14762).",
)

#: Valores da NBR 8800:2008 que o módulo de referência trouxe de memória (a norma vigente não
#: estava disponível). Confirmar na norma antes de liberar a versão.
CONFERIR_NBR8800_2008 = (
    "Q_s e Q_a do Anexo F.",
    "Tabela E.1 de K.",
    "λ_p de tubos na flexão.",
    "Forma da FLT de 2008, com C_b multiplicando a interpolação.",
)

REGRAS_B1 = (
    "N_e é calculado com o comprimento real da barra no plano de flexão (K = 1).",
    "C_m = 0,60 − 0,40·M₁/M₂, com M₁/M₂ positivo em curvatura reversa.",
    "C_m = 1,0 com forças transversais entre os apoios — e também quando M₁/M₂ não é informado "
    "(conservador).",
    "B₁ ≥ 1,0; em tração, B₁ = 1.",
    "N_Sd,1 ≥ N_e: a barra é instável no plano de flexão e o cálculo é bloqueado.",
    "B₂ (efeitos globais) continua na análise da estrutura.",
)

EXPLICACAO_FLT = {
    "NBR8800_2008": (
        "FLT na NBR 8800:2008: C_b multiplica a interpolação (λ_p < λ ≤ λ_r) e o M_cr; λ_r não "
        "depende de C_b. Item marcado CONFERIR."
    ),
    "NBR8800_2024": (
        "FLT no Projeto 2024: C_b entra em λ_r e no M_cr; a interpolação não é multiplicada por C_b."
    ),
    "AISC360_16_LRFD": (
        "FLT no AISC 360-16 (F2): C_b multiplica a interpolação e o M_cr, como na NBR 2008; este "
        "módulo usa a mesma forma de L_p e L_r da NBR (não o r_ts do AISC)."
    ),
}

REFERENCIAS_NORMA = {
    "NBR8800_2008": (
        "ABNT NBR 8800:2008 — 4.7 (ações), 5.3 (compressão), 5.4.2 e Anexo G (flexão), 5.5.1.2 "
        "(interação) e Anexos D (B₁), E (K, N_e) e F (flambagem local)."
    ),
    "NBR8800_2024": (
        "Projeto de revisão ABNT NBR 8800 (maio/2024, Rev6): 5.3.2–5.3.7, Tabelas 4 e 5, 5.4.2, "
        "Anexo C (C.2.2, B₁), Anexo D (Tabela D.1, D.2.8) e 5.5.1.2."
    ),
    "AISC360_16_LRFD": "ANSI/AISC 360-16 — Capítulos E, F e H (LRFD) e AISC Design Guide 29.",
}

ROTULOS_ESPESSURA_ANGLO = {
    "perfil_soldado": "perfil soldado",
    "perfil_laminado_H_W": "perfil laminado H/W",
    "perfil_laminado_L_U": "perfil laminado L/U",
    "chapa_ligacao_enrijecedor": "chapa de ligação ou enrijecedor",
    "cantoneira": "cantoneira",
    "placa_base": "placa de base",
}


# ---------------------------------------------------------------------------
# Seções: do perfil de catálogo, de dimensões e de propriedades informadas
# ---------------------------------------------------------------------------

_FAMILIAS_I = frozenset({"i", "w", "hp", "hea", "heb", "hem", "ipe", "ipn"})
_FAMILIAS_U = frozenset({"u", "upn"})


def _kc(h: float, tw: float) -> float:
    """``k_c = 4/√(h/t_w)``, entre 0,35 e 0,76 (mesa de perfil soldado)."""
    return min(0.76, max(0.35, 4.0 / math.sqrt(h / tw)))


def secao_de_perfil(perfil: PerfilAco, *, soldado: bool = False) -> Secao:
    """Converte um perfil do catálogo na seção do módulo de normas, com **as propriedades dele**.

    Usa A, I, J, C_w, W e Z do catálogo — e não a geometria idealizada, que erra I_y, J e C_w
    de perfis laminados (mesas inclinadas e raios de concordância). Onde o catálogo não traz o
    valor (C_w do U, centro de cisalhamento), usa as fórmulas de parede fina do próprio
    :mod:`core.steel_sections`. Famílias sem rotina de norma viram seção genérica, sem paredes —
    e a verificação sinaliza isso em vez de assumir Q = 1 em silêncio.
    """
    familia = familia_do_perfil(perfil)
    texto = str(perfil.familia).casefold()
    d, bf = perfil.altura_mm, perfil.largura_mm
    tw, tf = perfil.espessura_alma_mm, perfil.espessura_mesa_mm
    area, ix, iy, j = perfil.area_mm2, perfil.ix_mm4, perfil.iy_mm4, perfil.j_mm4
    zx = perfil.zx_mm3 if perfil.zx_mm3 > 0 else None
    zy = perfil.zy_mm3 if perfil.zy_mm3 > 0 else None

    if e_tubo_circular(perfil):
        return Secao(
            perfil.nome,
            area,
            ix,
            iy,
            J=j,
            Wx=ix / (d / 2),
            Wy=iy / (d / 2),
            Zx=zx,
            Zy=zy,
            tipo="tubo_circ",
            torcao_relevante=False,
            D_t=d / tw,
            dims=dict(D=d, t=tw),
        )
    if e_tubo_retangular(perfil):
        t = min(tw, tf)
        bp, hp = bf - 3 * t, d - 3 * t  # largura plana = lado − 3t (AISC B4.1b)
        paredes: list[dict[str, Any]] = [
            dict(tipo="AA", grupo=1, b=bp, t=t, n=2, tubo_ret=True),
            dict(tipo="AA", grupo=1, b=hp, t=t, n=2, tubo_ret=True),
        ]
        return Secao(
            perfil.nome,
            area,
            ix,
            iy,
            J=j,
            Wx=ix / (d / 2),
            Wy=iy / (bf / 2),
            Zx=zx,
            Zy=zy,
            tipo="tubo_ret",
            elementos=paredes,
            torcao_relevante=False,
            dims=dict(B=bf, H=d, t=t, b=bp, h=hp),
        )
    if "barra" in texto:
        if "circ" in texto:
            return Secao(
                perfil.nome,
                area,
                ix,
                iy,
                J=j,
                Wx=ix / (d / 2),
                Wy=iy / (d / 2),
                Zx=zx,
                Zy=zy,
                tipo="circ_macica",
                torcao_relevante=False,
                dims=dict(d=d),
            )
        return Secao(
            perfil.nome,
            area,
            ix,
            iy,
            J=j,
            Wx=ix / (d / 2),
            Wy=iy / (bf / 2),
            Zx=zx,
            Zy=zy,
            tipo="ret_macica",
            torcao_relevante=False,
            dims=dict(b=bf, h=d),
        )
    if familia in _FAMILIAS_I:
        hw = d - 2 * tf
        cw = perfil.cw_mm6 if perfil.cw_mm6 > 0 else iy * (d - tf) ** 2 / 4
        kc = _kc(hw, tw)
        mesas_e_alma: list[dict[str, Any]] = [
            dict(tipo="AL", grupo=5 if soldado else 4, b=bf / 2, t=tf, n=4, kc=kc),
            dict(tipo="AA", grupo=2, b=hw, t=tw, n=1),
        ]
        return Secao(
            perfil.nome,
            area,
            ix,
            iy,
            J=j,
            Cw=cw,
            Wx=ix / (d / 2),
            Wy=iy / (bf / 2),
            Zx=zx,
            Zy=zy,
            tipo="I",
            elementos=mesas_e_alma,
            dims=dict(d=d, bf=bf, tf=tf, tw=tw, h=hw, soldado=soldado, kc=kc),
        )
    if familia in _FAMILIAS_U:
        hw = d - 2 * tf
        x0 = abs(centro_de_cisalhamento_do_perfil(perfil)[0])
        xb = centroide_do_perfil(perfil)[0]
        kc = _kc(hw, tw)
        mesas_e_alma = [
            dict(tipo="AL", grupo=5 if soldado else 4, b=bf, t=tf, n=2, kc=kc),
            dict(tipo="AA", grupo=2, b=hw, t=tw, n=1),
        ]
        return Secao(
            perfil.nome,
            area,
            ix,
            iy,
            J=j,
            Cw=constante_de_empenamento_estimada(perfil),
            x0=x0,
            Wx=ix / (d / 2),
            Wy=iy / max(xb, bf - xb),
            Zx=zx,
            Zy=zy,
            tipo="U",
            elementos=mesas_e_alma,
            dims=dict(d=d, bf=bf, tf=tf, tw=tw, h=hw, xb=xb, soldado=soldado, kc=kc),
        )
    if familia == "t":
        # Mesa em cima e talão para baixo; centro de cisalhamento no encontro mesa-talão.
        y_bar = centroide_do_perfil(perfil)[1]
        paredes_t: list[dict[str, Any]] = [
            dict(tipo="AL", grupo=4, b=bf / 2, t=tf, n=2),
            dict(tipo="AL", grupo=6, b=d, t=tw, n=1),
        ]
        return Secao(
            perfil.nome,
            area,
            ix,
            iy,
            J=j,
            y0=abs(centro_de_cisalhamento_do_perfil(perfil)[1]),
            Wx=ix / max(y_bar, d - y_bar),
            Wy=iy / (bf / 2),
            Zx=zx,
            Zy=zy,
            tipo="generica",
            elementos=paredes_t,
        )
    if any(palavra in texto for palavra in ("enrijecido", "dobrada", "formado a frio")):
        aviso = "perfil formado a frio: a NBR 14762 (fora do escopo desta verificação) é que vale"
    else:
        aviso = (
            f"família «{perfil.familia}» sem classificação nas tabelas da norma: assumida seção "
            "de dupla simetria, sem flambagem local e sem rotina de M_Rd"
        )
    x0, y0 = centro_de_cisalhamento_do_perfil(perfil)
    return Secao(
        perfil.nome,
        area,
        ix,
        iy,
        J=j,
        Cw=constante_de_empenamento_estimada(perfil),
        x0=abs(x0),
        y0=abs(y0),
        Wx=ix / (d / 2),
        Wy=iy / (bf / 2),
        Zx=zx,
        Zy=zy,
        tipo="generica",
        dims={"aviso": aviso},
    )


def secao_direta(
    area_mm2: float,
    raio_giracao_x_mm: float,
    raio_giracao_y_mm: float | None = None,
    *,
    distancia_fibra_x_mm: float = 0.0,
    distancia_fibra_y_mm: float = 0.0,
) -> Secao:
    """Seção informada só por A e r: sem paredes, sem torção, sem rotina de ``M_Rd``.

    Serve para a flambagem por flexão. A verificação marca ALERTA (nunca OK) enquanto o usuário
    não confirmar que a seção é compacta e que a torção não governa.
    """
    area = _positivo("area_mm2", area_mm2)
    rx = _positivo("raio_giracao_x_mm", raio_giracao_x_mm)
    ry = _positivo("raio_giracao_y_mm", raio_giracao_y_mm) if raio_giracao_y_mm else rx
    ix, iy = area * rx**2, area * ry**2
    cx = _nao_negativo("distancia_fibra_x_mm", distancia_fibra_x_mm)
    cy = _nao_negativo("distancia_fibra_y_mm", distancia_fibra_y_mm)
    return cd.secao_generica(
        "Área e raio de giração informados",
        area,
        ix,
        iy,
        Wx=ix / cx if cx > 0 else None,
        Wy=iy / cy if cy > 0 else None,
        torcao_relevante=False,
    )


TIPOS_SECAO_POR_DIMENSOES = (
    "circular_macica",
    "retangular_macica",
    "tubo_circular",
    "tubo_retangular",
    "I",
    "U",
)


def secao_por_dimensoes(tipo: str, *, soldado: bool = False, **dimensoes: float) -> Secao:
    """Seção a partir das dimensões, recusando geometria impossível (parede maior que o lado…).

    ``tipo``: um de :data:`TIPOS_SECAO_POR_DIMENSOES`. Dimensões em mm: ``d`` (circular maciça),
    ``b`` e ``h`` (retangular maciça), ``D`` e ``t`` (tubo circular), ``B``, ``H`` e ``t`` (tubo
    retangular), ``d``, ``bf``, ``tf`` e ``tw`` (I e U).
    """
    esperadas = {
        "circular_macica": ("d",),
        "retangular_macica": ("b", "h"),
        "tubo_circular": ("D", "t"),
        "tubo_retangular": ("B", "H", "t"),
        "I": ("d", "bf", "tf", "tw"),
        "U": ("d", "bf", "tf", "tw"),
    }
    if tipo not in esperadas:
        raise ValueError(f"Tipo de seção desconhecido: {tipo!r}. Use um de {list(esperadas)}.")
    faltam = [nome for nome in esperadas[tipo] if nome not in dimensoes]
    if faltam:
        raise ValueError(f"Faltam as dimensões {faltam} para a seção {tipo!r}.")
    v = {nome: _positivo(nome, dimensoes[nome]) for nome in esperadas[tipo]}
    if tipo == "circular_macica":
        return cd.secao_circular_macica(v["d"])
    if tipo == "retangular_macica":
        return cd.secao_retangular_macica(v["b"], v["h"])
    if tipo == "tubo_circular":
        if v["t"] >= v["D"] / 2:
            raise ValueError("A espessura do tubo (t) deve ser menor que metade do diâmetro.")
        return cd.secao_tubo_circular(v["D"], v["t"])
    if tipo == "tubo_retangular":
        if v["t"] >= min(v["B"], v["H"]) / 2:
            raise ValueError("A espessura do tubo (t) deve ser menor que metade do menor lado.")
        return cd.secao_tubo_retangular(v["B"], v["H"], v["t"])
    if 2 * v["tf"] >= v["d"]:
        raise ValueError("As duas mesas (2·t_f) devem somar menos que a altura total.")
    if v["tw"] >= v["bf"]:
        raise ValueError("A espessura da alma (t_w) deve ser menor que a largura da mesa.")
    construtor = cd.secao_I if tipo == "I" else cd.secao_U
    return construtor(v["d"], v["bf"], v["tf"], v["tw"], soldado=soldado)


def secao_informada(
    nome: str,
    area_mm2: float,
    inercia_x_mm4: float,
    inercia_y_mm4: float,
    *,
    J_mm4: float = 0.0,
    Cw_mm6: float = 0.0,
    x0_mm: float = 0.0,
    y0_mm: float = 0.0,
    Wx_mm3: float = 0.0,
    Wy_mm3: float = 0.0,
    Zx_mm3: float = 0.0,
    Zy_mm3: float = 0.0,
    elementos: Sequence[Mapping[str, Any]] = (),
    torcao_relevante: bool = True,
) -> Secao:
    """Seção genérica com as propriedades do usuário; ``0`` em W e Z quer dizer “não informado”.

    Sem W/Z a seção não tem rotina de M_Rd (a verificação pede ``M_Rd`` informado ou bloqueia).
    Sem elementos de parede não há flambagem local — e a verificação não aceita isso em silêncio.
    """
    area = _positivo("área", area_mm2)
    ix = _positivo("I_x", inercia_x_mm4)
    iy = _positivo("I_y", inercia_y_mm4)
    for rotulo, valor in (
        ("J", J_mm4),
        ("C_w", Cw_mm6),
        ("W_x", Wx_mm3),
        ("W_y", Wy_mm3),
        ("Z_x", Zx_mm3),
        ("Z_y", Zy_mm3),
    ):
        _nao_negativo(rotulo, valor)
    if not (math.isfinite(x0_mm) and math.isfinite(y0_mm)):
        raise ValueError("As coordenadas do centro de cisalhamento devem ser números finitos.")
    return cd.secao_generica(
        nome.strip() or "Seção genérica",
        area,
        ix,
        iy,
        J=float(J_mm4),
        Cw=float(Cw_mm6),
        x0=float(x0_mm),
        y0=float(y0_mm),
        Wx=Wx_mm3 or None,
        Wy=Wy_mm3 or None,
        Zx=Zx_mm3 or None,
        Zy=Zy_mm3 or None,
        elementos=elementos_manuais(elementos) if elementos else [],
        torcao_relevante=torcao_relevante,
    )


def elementos_manuais(linhas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Elementos de parede informados na tela (``tipo``, ``grupo``, ``b``, ``t``, ``n``, ``kc``).

    Valida a combinação tipo × grupo da Tabela 4: AL = grupos 3, 4, 5 e 6; AA = grupos 1 e 2.
    O grupo 5 exige ``k_c`` (0,35 a 0,76).
    """
    elementos: list[dict[str, Any]] = []
    for indice, linha in enumerate(linhas, start=1):
        tipo = str(linha.get("tipo", "")).strip().upper()
        try:
            grupo = int(linha.get("grupo", 0))
            b = float(linha.get("b", 0.0))
            t = float(linha.get("t", 0.0))
            n = int(linha.get("n", 1))
        except (TypeError, ValueError) as erro:
            raise ValueError(f"Elemento {indice}: valores numéricos inválidos.") from erro
        if tipo not in {"AL", "AA"}:
            raise ValueError(f"Elemento {indice}: o tipo deve ser AL (livre) ou AA (apoiado).")
        grupos_validos = {3, 4, 5, 6} if tipo == "AL" else {1, 2}
        if grupo not in grupos_validos:
            raise ValueError(
                f"Elemento {indice}: o grupo {grupo} não existe para {tipo} "
                f"(use {sorted(grupos_validos)})."
            )
        if not (math.isfinite(b) and math.isfinite(t) and b > 0 and t > 0 and n >= 1):
            raise ValueError(f"Elemento {indice}: b, t e a quantidade devem ser positivos.")
        elemento: dict[str, Any] = dict(tipo=tipo, grupo=grupo, b=b, t=t, n=n)
        if grupo == 5:
            kc = float(linha.get("kc") or 0.0)
            if not 0.35 <= kc <= 0.76:
                raise ValueError(f"Elemento {indice}: k_c do grupo 5 deve ficar entre 0,35 e 0,76.")
            elemento["kc"] = kc
        if grupo == 1:
            elemento["tubo_ret"] = True
        elementos.append(elemento)
    return elementos


def categoria_espessura_anglo(
    secao: Secao, soldado: bool = False
) -> tuple[str | None, float | None]:
    """Categoria do item 8.8 da Anglo e a menor espessura de parede da seção.

    ``(None, None)`` para tubos, barras maciças e seções genéricas: a tabela da Anglo não os cobre.
    """
    if secao.tipo in {"I", "U"}:
        t = min(secao.dims["tf"], secao.dims["tw"])
        if soldado or secao.dims.get("soldado"):
            return "perfil_soldado", t
        return ("perfil_laminado_H_W" if secao.tipo == "I" else "perfil_laminado_L_U"), t
    return None, None


# ---------------------------------------------------------------------------
# Entrada e resultado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntradaColuna:
    """Tudo o que a verificação precisa. Forças em kN, momentos em kN·m, comprimentos em mm.

    Os esforços são **de cálculo** (já majorados) e de primeira ordem. ``Lx`` é o comprimento
    destravado para a flexão em torno de x (flambagem no plano y-z) e ``Ly`` o de y. ``kz`` e
    ``Lz`` definem o comprimento de flambagem por torção; sem eles vale o maior de K_x·L_x e
    K_y·L_y.
    """

    secao: Secao
    fy_MPa: float
    norma: str = "NBR8800_2008"
    E_MPa: float = cd.E_ACO
    G_MPa: float = cd.G_ACO
    gama_a1: float = GAMMA_A1
    Lx_mm: float = 3000.0
    Ly_mm: float = 3000.0
    kx: float = 1.0
    ky: float = 1.0
    Lz_mm: float | None = None
    kz: float | None = None
    N_Sd_kN: float = 0.0
    Mx_kNm: float = 0.0
    My_kNm: float = 0.0
    ex_mm: float = 0.0
    ey_mm: float = 0.0
    Mx_mao_francesa_kNm: float = 0.0
    My_mao_francesa_kNm: float = 0.0
    razao_m1_m2_x: float | None = None
    razao_m1_m2_y: float | None = None
    forcas_transversais_x: bool = False
    forcas_transversais_y: bool = False
    Lb_mm: float | None = None
    Cb: float = 1.0
    momentos_cb_kNm: tuple[float, float, float, float] | None = None
    MRd_x_informado_kNm: float | None = None
    MRd_y_informado_kNm: float | None = None
    secao_compacta_confirmada: bool = False
    espessuras_anglo: Mapping[str, float] | None = None
    com_mao_francesa: bool = False


@dataclass(frozen=True)
class ResultadoColuna:
    entrada: EntradaColuna
    compressao: dict[str, Any] | None
    flexao_x: dict[str, Any] | None
    flexao_y: dict[str, Any] | None
    momento_x_primeira_ordem_kNm: float
    momento_y_primeira_ordem_kNm: float
    cm_x: float
    cm_y: float
    b1_x: float
    b1_y: float
    momento_x_amplificado_kNm: float
    momento_y_amplificado_kNm: float
    indice_interacao: float | None
    verificacoes: tuple[Verificacao, ...]
    status_geral: str
    aproveitamento_max: float | None
    governante: str
    bloqueios: tuple[str, ...]
    avisos: tuple[str, ...]
    cb_usado: float
    lb_usado_mm: float

    @property
    def reprovadas(self) -> tuple[Verificacao, ...]:
        return tuple(v for v in self.verificacoes if v.status == "NÃO OK")

    @property
    def atende(self) -> bool:
        return self.status_geral in ("OK", "ALERTA")


# ---------------------------------------------------------------------------
# Verificação
# ---------------------------------------------------------------------------


def _validar(e: EntradaColuna) -> None:
    if e.norma not in NORMAS:
        raise ValueError(f"Norma inválida: {e.norma}. Use uma de {NORMAS}.")
    for nome, valor in (
        ("fy_MPa", e.fy_MPa),
        ("E_MPa", e.E_MPa),
        ("G_MPa", e.G_MPa),
        ("gama_a1", e.gama_a1),
        ("Lx_mm", e.Lx_mm),
        ("Ly_mm", e.Ly_mm),
        ("kx", e.kx),
        ("ky", e.ky),
        ("Cb", e.Cb),
    ):
        _positivo(nome, valor)
    if e.Cb < 1.0:
        raise ValueError("C_b não pode ser menor que 1,0 (1,0 = momento constante, conservador).")
    for nome_opc, valor_opc in (("Lz_mm", e.Lz_mm), ("kz", e.kz), ("Lb_mm", e.Lb_mm)):
        if valor_opc is not None:
            _positivo(nome_opc, valor_opc)
    for nome_esf, valor_esf in (
        ("N_Sd_kN", e.N_Sd_kN),
        ("Mx_kNm", e.Mx_kNm),
        ("My_kNm", e.My_kNm),
        ("ex_mm", e.ex_mm),
        ("ey_mm", e.ey_mm),
        ("Mx_mao_francesa_kNm", e.Mx_mao_francesa_kNm),
        ("My_mao_francesa_kNm", e.My_mao_francesa_kNm),
    ):
        _nao_negativo(nome_esf, valor_esf)
    for nome_mrd, valor_mrd in (
        ("MRd_x_informado_kNm", e.MRd_x_informado_kNm),
        ("MRd_y_informado_kNm", e.MRd_y_informado_kNm),
    ):
        if valor_mrd is not None:
            _positivo(nome_mrd, valor_mrd)
    for nome, razao in (("razao_m1_m2_x", e.razao_m1_m2_x), ("razao_m1_m2_y", e.razao_m1_m2_y)):
        if razao is not None and not (math.isfinite(razao) and -1.0 <= razao <= 1.0):
            raise ValueError(f"{nome} deve ficar entre −1 e +1 (M₁/M₂, com |M₁| ≤ |M₂|).")
    if e.momentos_cb_kNm is not None and not e.momentos_cb_kNm[0] > 0:
        raise ValueError("M_max do diagrama (para C_b) deve ser maior que zero.")
    for categoria, espessura in (e.espessuras_anglo or {}).items():
        if categoria not in cd.ESPESSURA_MIN_ANGLO:
            raise ValueError(f"Categoria de espessura desconhecida: {categoria}.")
        _positivo(f"espessura {categoria}", espessura)


def _f(valor: float, casas: int = 2) -> str:
    return "∞" if math.isinf(valor) else f"{valor:.{casas}f}"


def _linha_info(
    nome: str,
    solicitante: float | None,
    resistente: float | None,
    unidade: str,
    referencia: str,
    formula: str = "",
) -> Verificacao:
    return Verificacao(
        nome,
        solicitante,
        resistente,
        unidade,
        referencia,
        formula,
        status="INFO",
        tipo="informativo",
    )


def _linha_alerta(nome: str, referencia: str, texto: str) -> Verificacao:
    return Verificacao(nome, None, None, "—", referencia, texto, status="ALERTA", tipo="limite")


def _linha_bloqueio(nome: str, referencia: str, texto: str) -> Verificacao:
    return Verificacao(nome, None, None, "—", referencia, texto, status="NÃO OK", tipo="limite")


def verificar_coluna(entrada: EntradaColuna) -> ResultadoColuna:
    """Verifica a barra inteira — todos os eixos, todos os modos e os dois momentos juntos."""
    _validar(entrada)
    sec, norma = entrada.secao, entrada.norma
    fy, e_mod, g_mod, gama = entrada.fy_MPa, entrada.E_MPa, entrada.G_MPa, entrada.gama_a1
    lx, ly = entrada.Lx_mm, entrada.Ly_mm
    kxlx, kyly = entrada.kx * lx, entrada.ky * ly
    kzlz: float | None = None
    if entrada.kz is not None or entrada.Lz_mm is not None:
        kzlz = (entrada.kz or 1.0) * (entrada.Lz_mm or max(lx, ly))
    n_sd = entrada.N_Sd_kN
    fator = cd.fator_resistencia(norma, gama)
    aisc = norma == "AISC360_16_LRFD"

    linhas: list[Verificacao] = []
    avisos: list[str] = _avisos_de_entrada(entrada.kx, entrada.ky, e_mod, fy)
    bloqueios: list[str] = []
    ref_norma = {
        "NBR8800_2008": "NBR 8800:2008",
        "NBR8800_2024": "Projeto NBR 8800:2024",
        "AISC360_16_LRFD": "AISC 360-16",
    }[norma]

    def bloquear(nome: str, referencia: str, motivo: str) -> None:
        bloqueios.append(f"{nome}: {motivo}")
        linhas.append(_linha_bloqueio(nome, referencia, motivo))

    # ------------------------------------------------------------------ compressão
    comp: dict[str, Any] | None = None
    try:
        comp = cd.resist_compressao(sec, fy, kxlx, kyly, kzlz, norma, e_mod, g_mod, gama)
    except ValueError as erro:
        bloquear("Compressão — flambagem local", f"{ref_norma} (flambagem local)", str(erro))

    lam_x, lam_y = kxlx / sec.rx, kyly / sec.ry
    linhas.append(
        _linha_info(
            "Esbeltez em x: λx = Kx·Lx/rx",
            lam_x,
            None,
            "—",
            "NBR 5.3 / AISC E2",
            f"{entrada.kx:g}·{lx:.0f}/{sec.rx:.1f} = {lam_x:.1f}",
        )
    )
    linhas.append(
        _linha_info(
            "Esbeltez em y: λy = Ky·Ly/ry",
            lam_y,
            None,
            "—",
            "NBR 5.3 / AISC E2",
            f"{entrada.ky:g}·{ly:.0f}/{sec.ry:.1f} = {lam_y:.1f}",
        )
    )

    def linhas_de_limites() -> list[Verificacao]:
        """Critério Anglo (esbeltez e espessuras) e o aviso sobre K nas normas mais novas."""
        ref_esbeltez = {
            "NBR8800_2008": "Anglo 8.3; NBR 8800:2008 5.3.4.1",
            "NBR8800_2024": "Anglo 8.3; Projeto NBR 5.3.7 (recomendação)",
            "AISC360_16_LRFD": "Anglo 8.3; AISC E2 (recomendação)",
        }[norma]
        anglo = cd.criterio_anglo(
            max(lam_x, lam_y),
            True,
            dict(entrada.espessuras_anglo) if entrada.espessuras_anglo else None,
        )
        anglo[0].referencia = ref_esbeltez
        for categoria, linha in zip(entrada.espessuras_anglo or {}, anglo[1:], strict=True):
            rotulo = ROTULOS_ESPESSURA_ANGLO.get(categoria, categoria)
            linha.nome = f"Espessura mínima — {rotulo}"
        if norma != "NBR8800_2008" and (entrada.kx != 1.0 or entrada.ky != 1.0):
            texto_k = (
                "Com o método da análise direta o comprimento efetivo é o real (K = 1). Mantenha "
                "K da Tabela E.1 só se a estrutura for verificada pelo método do comprimento "
                "efetivo."
            )
            anglo.append(
                _linha_info(
                    "K diferente de 1,0 nesta norma",
                    None,
                    None,
                    "—",
                    f"{ref_norma} (método da análise direta)",
                    texto_k,
                )
            )
            avisos.append(f"K ≠ 1,0 no {ref_norma}: {texto_k}")
        return anglo

    if comp is None:
        # Sem N_c,Rd não há como seguir; mostra ao menos a flambagem elástica.
        elastico = cd.forca_flambagem_elastica(sec, kxlx, kyly, kzlz, e_mod, g_mod)
        linhas.append(
            _linha_info("N_ex — flexão em x", None, elastico["Nex"], "kN", "NBR Anexo E / AISC E3")
        )
        linhas.append(
            _linha_info("N_ey — flexão em y", None, elastico["Ney"], "kN", "NBR Anexo E / AISC E3")
        )
        linhas.extend(linhas_de_limites())
        return _fechar(
            entrada, None, None, None, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, None,
            linhas, bloqueios, avisos, entrada.Cb, entrada.Lb_mm or ly,
        )  # fmt: skip

    ne_modos: dict[str, float] = comp["modos"]
    ref_e = "NBR 5.3.5 e Anexo E / AISC E3–E4"
    linhas.append(
        _linha_info(
            "N_ex — flambagem elástica por flexão em x",
            None,
            comp["Nex"],
            "kN",
            ref_e,
            f"π²·E·Ix/(Kx·Lx)² = π²·{e_mod:.0f}·{sec.Ix:.4g}/{kxlx:.0f}²",
        )
    )
    linhas.append(
        _linha_info(
            "N_ey — flambagem elástica por flexão em y",
            None,
            comp["Ney"],
            "kN",
            ref_e,
            f"π²·E·Iy/(Ky·Ly)² = π²·{e_mod:.0f}·{sec.Iy:.4g}/{kyly:.0f}²",
        )
    )
    if math.isfinite(comp["Nez"]):
        kzlz_usado = kzlz if kzlz else max(kxlx, kyly)
        linhas.append(
            _linha_info(
                "N_ez — flambagem elástica por torção",
                None,
                comp["Nez"],
                "kN",
                ref_e,
                f"[π²·E·Cw/(Kz·Lz)² + G·J]/r0² com Kz·Lz = {kzlz_usado:.0f} mm, r0 = {sec.r0:.1f} mm",
            )
        )
    for nome_modo, valor in ne_modos.items():
        if nome_modo.startswith("flexo-torção"):
            linhas.append(
                _linha_info(
                    f"N_e {nome_modo} (acoplado)",
                    None,
                    valor,
                    "kN",
                    ref_e,
                    f"x0 = {sec.x0:.1f} mm, y0 = {sec.y0:.1f} mm: a flexão no plano de simetria "
                    "se acopla à torção",
                )
            )
    linhas.append(
        _linha_info(
            "N_e adotado (menor modo)",
            None,
            comp["Ne"],
            "kN",
            ref_e,
            f"modo que governa: {comp['modo']}",
        )
    )

    # ------------------------------------------------------------------ flambagem local e χ
    if norma == "NBR8800_2008":
        linhas.append(
            _linha_info(
                "Flambagem local: fator Q = Q_s·Q_a",
                None,
                comp["Q"],
                "—",
                "NBR 8800:2008 Anexo F",
                f"Q_s = {comp['Qs']:.3f}; Q_a = {comp['Qa']:.3f}; A_ef = Q·A_g = {comp['A_ef']:.0f} mm²",
            )
        )
    else:
        linhas.append(
            _linha_info(
                "Flambagem local: área efetiva A_ef",
                None,
                comp["A_ef"],
                "mm²",
                f"{ref_norma} (Tabelas 4 e 5 / AISC E7)",
                f"A_ef/A_g = {comp['Q']:.3f} (c1 e c2 da Tabela 5; sem fator Q)",
            )
        )
    formula_lambda0 = "λ₀ = √(Q·A_g·f_y/N_e)" if norma == "NBR8800_2008" else "λ₀ = √(A_g·f_y/N_e)"
    linhas.append(
        _linha_info(
            "Esbeltez reduzida λ₀",
            comp["lambda0"],
            None,
            "—",
            "NBR 5.3.3 / AISC E3",
            f"{formula_lambda0} = {comp['lambda0']:.3f}",
        )
    )
    linhas.append(
        _linha_info(
            "Fator de redução χ",
            None,
            comp["chi"],
            "—",
            "NBR 5.3.3 / AISC E3",
            ("χ = 0,658^(λ₀²)" if comp["lambda0"] <= 1.5 else "χ = 0,877/λ₀²")
            + f" = {comp['chi']:.3f}",
        )
    )
    n_rd = comp["Nc_Rd"]
    nome_fator = "φ" if aisc else "1/γ_a1"
    valor_fator = f"{fator:.2f}" if aisc else f"1/{gama:.2f}"
    formula_n = (
        f"N_c,Rd = χ·Q·A_g·f_y/γ_a1 = {comp['chi']:.3f}·{comp['Q']:.3f}·{sec.A:.0f}·{fy:.0f}/{gama:.2f}"
        if norma == "NBR8800_2008"
        else f"N_c,Rd = χ·A_ef·f_y·{nome_fator} = {comp['chi']:.3f}·{comp['A_ef']:.0f}·{fy:.0f}·{valor_fator}"
    ) + f" = {n_rd:.2f} kN (modo {comp['modo']})"
    linhas.append(
        Verificacao(
            "Compressão axial N_c,Rd (todos os modos)",
            n_sd,
            n_rd,
            "kN",
            "NBR 5.3.2 / AISC E3",
            formula_n,
        )
    )

    alertas_secao: list[Verificacao] = []
    # ------------------------------------------------------------------ seção genérica: o que não foi verificado
    if sec.tipo == "generica":
        if entrada.secao_compacta_confirmada:
            alertas_secao.append(
                _linha_info(
                    "Seção compacta e torção não governa — confirmado",
                    None,
                    None,
                    "—",
                    "Confirmação do usuário",
                    "Flambagem local e torção não foram calculadas: a responsabilidade é de quem confirmou.",
                )
            )
        else:
            if not sec.elementos:
                alertas_secao.append(
                    _linha_alerta(
                        "Flambagem local não verificada",
                        f"{ref_norma} (Anexo F / Tabela 4)",
                        "Seção sem os b/t dos elementos: informe-os ou confirme que a seção é "
                        "compacta. Enquanto isso o resultado nunca é OK.",
                    )
                )
            if not math.isfinite(comp["Nez"]):
                alertas_secao.append(
                    _linha_alerta(
                        "Torção e flexo-torção não verificadas",
                        "NBR 5.3.5 e Anexo E / AISC E4",
                        "Sem J e C_w a torção não entra em N_e: informe-os ou confirme que a torção "
                        "não governa. Enquanto isso o resultado nunca é OK.",
                    )
                )
    aviso_secao = sec.dims.get("aviso")
    if aviso_secao:
        alertas_secao.append(
            _linha_alerta("Seção fora do escopo", "NBR 14762", str(aviso_secao).capitalize())
        )

    if comp["Q"] < 1.0:
        paredes = "; ".join(
            f"{item['nome']} b/t = {item['b/t']:.1f} > {item['(b/t) lim']:.1f}"
            for item in tabela_elementos(sec, fy, norma, comp, e_mod)
            if item["Esbelto"] == "sim"
        )
        avisos.append(
            f"Flambagem local reduz a capacidade: {'Q' if norma == 'NBR8800_2008' else 'A_ef/A_g'} = "
            f"{comp['Q']:.3f}" + (f" — {paredes}." if paredes else ".")
        )
    if comp["modo"] not in {"flexão x", "flexão y"}:
        avisos.append(
            f"O modo de flambagem elástica que governa é «{comp['modo']}» (N_e = {comp['Ne']:.1f} kN), "
            "não a flexão pura: a verificação por Euler nos eixos x e y superestimaria a resistência."
        )

    # ------------------------------------------------------------------ momentos de 1ª ordem e B1
    mx1 = entrada.Mx_kNm + n_sd * entrada.ex_mm / 1000.0 + entrada.Mx_mao_francesa_kNm
    my1 = entrada.My_kNm + n_sd * entrada.ey_mm / 1000.0 + entrada.My_mao_francesa_kNm

    def cm_do_plano(razao: float | None, transversais: bool) -> float:
        if transversais or razao is None:
            return 1.0
        return cd.coef_Cm(razao, 1.0, False)

    cm_x = cm_do_plano(entrada.razao_m1_m2_x, entrada.forcas_transversais_x)
    cm_y = cm_do_plano(entrada.razao_m1_m2_y, entrada.forcas_transversais_y)

    # C_b e L_b (FLT) — só no eixo x
    lb = entrada.Lb_mm or ly
    cb = entrada.Cb
    if entrada.momentos_cb_kNm is not None:
        cb = min(3.0, cd.fator_Cb(*entrada.momentos_cb_kNm))
    if sec.tipo == "U" and norma == "NBR8800_2008" and cb != 1.0 and mx1 > 0:
        avisos.append(
            "Seção U: C_b tomado igual a 1,0 na FLT, conforme o Anexo G da NBR 8800:2008."
        )
        cb = 1.0

    momentos: dict[str, dict[str, Any]] = {}
    for eixo, m1, comprimento, cm, inercia in (
        ("x", mx1, lx, cm_x, sec.Ix),
        ("y", my1, ly, cm_y, sec.Iy),
    ):
        dados: dict[str, Any] = dict(
            m1=m1, b1=1.0, amplificado=0.0, mrd=None, flexao=None, completo=m1 <= 0
        )
        momentos[eixo] = dados
        if m1 <= 0:
            continue
        # B1 com o comprimento real no plano de flexão
        n_e_real = math.pi**2 * e_mod * inercia / comprimento**2 / 1000.0
        try:
            dados["b1"] = cd.coef_B1(n_sd, inercia, comprimento, cm, e_mod)
        except ValueError as erro:
            bloquear(
                f"Amplificação B₁ em {eixo}",
                "NBR Anexo D (D.2.2) / Projeto C.2.2",
                f"{erro} N_Sd = {n_sd:.1f} kN, N_e{eixo} (K = 1) = {n_e_real:.1f} kN.",
            )
            continue
        dados["amplificado"] = m1 * dados["b1"]
        linhas.append(
            _linha_info(
                f"B₁{eixo} — amplificação do momento em torno de {eixo}",
                dados["b1"],
                None,
                "—",
                "NBR Anexo D (D.2.2) / Projeto C.2.2",
                f"C_m/(1 − N_Sd/N_e{eixo}) = {cm:.2f}/(1 − {n_sd:.1f}/{n_e_real:.1f}); "
                f"M{eixo},Sd = B₁·M₁ = {dados['b1']:.3f}·{m1:.3f} = {dados['amplificado']:.3f} kN·m",
            )
        )
        # M_Rd
        usar_lb = lb if eixo == "x" else 0.0
        usar_cb = cb if eixo == "x" else 1.0
        informado = entrada.MRd_x_informado_kNm if eixo == "x" else entrada.MRd_y_informado_kNm
        try:
            flexao = cd.momento_resistente(sec, fy, eixo, usar_lb, usar_cb, norma, e_mod, gama)
            dados["flexao"] = flexao
            dados["mrd"] = flexao["MRd"]
        except (NotImplementedError, ValueError) as erro:
            if informado is not None:
                dados["mrd"] = informado
                linhas.append(
                    _linha_info(
                        f"M{eixo},Rd informado pelo usuário",
                        None,
                        informado,
                        "kN·m",
                        "Informado",
                        f"A rotina de norma não cobre esta seção ({erro}). Valor informado sem verificação.",
                    )
                )
            else:
                bloquear(
                    f"Flexão em {eixo} não calculada",
                    "NBR 5.4.2 e Anexo G / Projeto Anexo D / AISC F",
                    f"{erro} Informe M{eixo},Rd da seção, se o conhecer.",
                )
                continue
        flexao = dados["flexao"]
        if flexao is not None:
            w = sec.Wx if eixo == "x" else sec.Wy
            for estado, valor in flexao["estados"].items():
                formula = ""
                if estado == "FLT" and "lambda_FLT" in flexao["aux"]:
                    aux = flexao["aux"]
                    formula = (
                        f"λ = Lb/ry = {aux['lambda_FLT']:.1f}; λp = {aux['lp_FLT']:.1f}; "
                        f"λr = {aux['lr_FLT']:.1f}; Lb = {usar_lb:.0f} mm; Cb = {usar_cb:.2f}"
                    )
                linhas.append(
                    _linha_info(
                        f"M{eixo},Rd — {estado}",
                        None,
                        valor,
                        "kN·m",
                        "NBR 5.4.2 e Anexo G / Projeto Tab. D.1 / AISC F",
                        formula,
                    )
                )
            if w:
                linhas.append(
                    _linha_info(
                        f"M{eixo},Rd — limite 1,5·W·f_y",
                        None,
                        1.5 * w * fy * fator / 1e6,
                        "kN·m",
                        "NBR 5.4.2.2",
                        f"1,5·{w:.4g}·{fy:.0f}·{valor_fator} = {1.5 * w * fy * fator / 1e6:.2f} kN·m",
                    )
                )
        linhas.append(
            Verificacao(
                f"Flexão em torno de {eixo}: M{eixo},Sd amplificado ≤ M{eixo},Rd",
                dados["amplificado"],
                dados["mrd"],
                "kN·m",
                "NBR 5.4.2 / AISC F",
                f"estado-limite que governa: {flexao['governa']}" if flexao else "M_Rd informado",
            )
        )
        dados["completo"] = True

    # ------------------------------------------------------------------ interação (uma equação, dois eixos)
    indice: float | None = None
    presentes = [eixo for eixo, d in momentos.items() if d["m1"] > 0]
    if presentes and all(
        momentos[eixo]["completo"] and momentos[eixo]["mrd"] for eixo in presentes
    ):
        indice = cd.interacao_NM(
            n_sd,
            n_rd,
            momentos["x"]["amplificado"],
            momentos["x"]["mrd"] or math.inf,
            momentos["y"]["amplificado"],
            momentos["y"]["mrd"] or math.inf,
        )
        razao_n = n_sd / n_rd
        termo_m = momentos["x"]["amplificado"] / (momentos["x"]["mrd"] or math.inf) + momentos["y"][
            "amplificado"
        ] / (momentos["y"]["mrd"] or math.inf)
        formula_i = (
            f"N/N_Rd + 8/9·(Mx/Mx,Rd + My/My,Rd) = {razao_n:.3f} + 8/9·{termo_m:.3f}"
            if razao_n >= 0.2
            else f"N/(2·N_Rd) + Mx/Mx,Rd + My/My,Rd = {razao_n / 2:.3f} + {termo_m:.3f}"
        )
        linhas.append(
            Verificacao(
                "Interação N + Mx + My (uma única equação)",
                indice,
                1.0,
                "—",
                "NBR 5.5.1.2 / AISC H1-1",
                f"{formula_i} = {indice:.3f}",
            )
        )

    # ------------------------------------------------------------------ limites, alertas e cisalhamento
    linhas.extend(linhas_de_limites())
    linhas.extend(alertas_secao)
    if entrada.com_mao_francesa or entrada.forcas_transversais_x or entrada.forcas_transversais_y:
        linhas.append(
            _linha_alerta(
                "Cisalhamento na barra não verificado",
                "NBR 5.4.3 / AISC G",
                "A mão-francesa ou a força transversal introduz cortante na barra, e o cisalhamento "
                "(5.4.3) está fora do escopo desta verificação.",
            )
        )

    return _fechar(
        entrada, comp, momentos["x"]["flexao"], momentos["y"]["flexao"], mx1, my1, cm_x, cm_y,
        momentos["x"]["b1"], momentos["y"]["b1"], momentos["x"]["amplificado"],
        momentos["y"]["amplificado"], indice, linhas, bloqueios, avisos, cb, lb,
    )  # fmt: skip


def _fechar(
    entrada: EntradaColuna,
    comp: dict[str, Any] | None,
    flexao_x: dict[str, Any] | None,
    flexao_y: dict[str, Any] | None,
    mx1: float,
    my1: float,
    cm_x: float,
    cm_y: float,
    b1_x: float,
    b1_y: float,
    mx_amp: float,
    my_amp: float,
    indice: float | None,
    linhas: list[Verificacao],
    bloqueios: list[str],
    avisos: list[str],
    cb_usado: float,
    lb_usado: float,
) -> ResultadoColuna:
    resistencia = [v for v in linhas if v.tipo == "resistencia" and v.aproveitamento is not None]
    if resistencia:
        pior = max(resistencia, key=lambda v: v.aproveitamento or 0.0)
        aproveitamento: float | None = pior.aproveitamento
        governante = pior.nome
    else:
        aproveitamento, governante = None, "—"
    return ResultadoColuna(
        entrada=entrada,
        compressao=comp,
        flexao_x=flexao_x,
        flexao_y=flexao_y,
        momento_x_primeira_ordem_kNm=mx1,
        momento_y_primeira_ordem_kNm=my1,
        cm_x=cm_x,
        cm_y=cm_y,
        b1_x=b1_x,
        b1_y=b1_y,
        momento_x_amplificado_kNm=mx_amp,
        momento_y_amplificado_kNm=my_amp,
        indice_interacao=indice,
        verificacoes=tuple(linhas),
        status_geral=status_geral(linhas),
        aproveitamento_max=aproveitamento,
        governante=governante,
        bloqueios=tuple(bloqueios),
        avisos=tuple(dict.fromkeys(avisos)),
        cb_usado=cb_usado,
        lb_usado_mm=lb_usado,
    )


# ---------------------------------------------------------------------------
# Tabelas auxiliares, comparação entre normas e registro técnico
# ---------------------------------------------------------------------------


def tabela_elementos(
    secao: Secao, fy: float, norma: str, compressao: dict[str, Any], e_mod: float = cd.E_ACO
) -> list[dict[str, Any]]:
    """Cada parede da seção com b/t, o limite da Tabela 4, se é esbelta e o que sobra dela.

    2008: ``Q_s`` dos elementos livres (AL) e ``b_ef`` dos apoiados (AA); 2024 e AISC: ``b_ef`` de
    todos. A tensão das larguras efetivas é a de ``χ`` calculado sem flambagem local.
    """
    chi_sem_q = cd.fator_chi(math.sqrt(secao.A * fy / (compressao["Ne"] * 1000.0)))
    tabela: list[dict[str, Any]] = []
    for el in secao.elementos:
        bt = el["b"] / el["t"]
        limite = cd.bt_lim(el, fy, e_mod)
        grupo = int(el["grupo"])
        nome = el.get("nome") or NOMES_GRUPO.get(grupo, f"grupo {grupo}")
        if norma == "NBR8800_2008":
            esbelto = bt > (limite if el["tipo"] == "AL" else limite * math.sqrt(1.0 / chi_sem_q))
            q_s = cd.Qs_elemento_2008(el, fy, e_mod) if el["tipo"] == "AL" else None
            b_ef = cd.bef_AA_2008(el, fy, chi_sem_q * fy, e_mod) if el["tipo"] == "AA" else None
        else:
            esbelto = bt > limite / math.sqrt(chi_sem_q)
            q_s = None
            b_ef = cd.bef_2024(el, fy, chi_sem_q, e_mod)
        tabela.append(
            {
                "nome": nome,
                "Elemento": nome,
                "Tipo": el["tipo"],
                "Grupo (Tabela 4)": grupo,
                "b (mm)": el["b"],
                "t (mm)": el["t"],
                "b/t": bt,
                "(b/t) lim": limite,
                "Esbelto": "sim" if esbelto else "não",
                "Q_s": q_s,
                "b_ef (mm)": b_ef,
            }
        )
    return tabela


def comparar_normas(entrada: EntradaColuna) -> list[dict[str, Any]]:
    """A mesma barra nas três normas. Quem bloqueia mostra o motivo em vez de sumir."""
    saida: list[dict[str, Any]] = []
    for norma in NORMAS:
        linha: dict[str, Any] = {"norma": norma, "rotulo": NORMAS_ROTULOS[norma]}
        try:
            resultado = verificar_coluna(replace(entrada, norma=norma))
        except ValueError as erro:
            linha.update(status="NÃO OK", erro=str(erro))
            saida.append(linha)
            continue
        comp = resultado.compressao
        linha.update(
            status=resultado.status_geral,
            aproveitamento_max=resultado.aproveitamento_max,
            governante=resultado.governante,
            Nc_Rd_kN=None if comp is None else comp["Nc_Rd"],
            fator_Q=None if comp is None else comp["Q"],
            chi=None if comp is None else comp["chi"],
            MRd_x_kNm=None if resultado.flexao_x is None else resultado.flexao_x["MRd"],
            MRd_y_kNm=None if resultado.flexao_y is None else resultado.flexao_y["MRd"],
            indice_interacao=resultado.indice_interacao,
            erro="; ".join(resultado.bloqueios),
        )
        saida.append(linha)
    return saida


def registro_coluna(
    entrada: EntradaColuna,
    resultado: ResultadoColuna,
    *,
    contexto: Mapping[str, Any] | None = None,
    materiais_ids: Sequence[str] = (),
    equacoes_de_carga: Sequence[str] = (),
) -> dict[str, Any]:
    """Registro técnico de Flambagem de colunas: a barra inteira, com a tabela de verificações.

    Mantém as chaves que o gráfico da curva de flambagem e a sensibilidade já liam
    (``esbeltez_governante``, ``chi``, ``fator_q``, ``resistencia_kN``…) e acrescenta as novas.
    ``contexto`` leva o que só a interface sabe (condição de apoio, ações características,
    mão-francesa).
    """
    sec, norma = entrada.secao, entrada.norma
    comp = resultado.compressao
    fator = cd.fator_resistencia(norma, entrada.gama_a1)
    lam_x = entrada.kx * entrada.Lx_mm / sec.rx
    lam_y = entrada.ky * entrada.Ly_mm / sec.ry
    eixo_governante = "x" if lam_x >= lam_y else "y"
    aprov = resultado.aproveitamento_max
    aprov_finito = aprov if aprov is not None and math.isfinite(aprov) else None

    entradas: dict[str, Any] = {
        "norma": norma,
        "secao": sec.nome,
        "tipo_secao": sec.tipo,
        "area_mm2": sec.A,
        "inercia_x_mm4": sec.Ix,
        "inercia_y_mm4": sec.Iy,
        "raio_giracao_x_mm": sec.rx,
        "raio_giracao_y_mm": sec.ry,
        "J_mm4": sec.J,
        "Cw_mm6": sec.Cw,
        "x0_mm": sec.x0,
        "y0_mm": sec.y0,
        "modulo_elasticidade_MPa": entrada.E_MPa,
        "modulo_cisalhamento_MPa": entrada.G_MPa,
        "escoamento_MPa": entrada.fy_MPa,
        "gamma_a1": entrada.gama_a1,
        "fator_resistencia": fator,
        "comprimento_x_mm": entrada.Lx_mm,
        "comprimento_y_mm": entrada.Ly_mm,
        "comprimento_z_mm": entrada.Lz_mm,
        "kx": entrada.kx,
        "ky": entrada.ky,
        "kz": entrada.kz,
        "forca_solicitante_kN": entrada.N_Sd_kN,
        "momento_x_kNm": entrada.Mx_kNm,
        "momento_y_kNm": entrada.My_kNm,
        "excentricidade_x_mm": entrada.ex_mm,
        "excentricidade_y_mm": entrada.ey_mm,
        "momento_mao_francesa_x_kNm": entrada.Mx_mao_francesa_kNm,
        "momento_mao_francesa_y_kNm": entrada.My_mao_francesa_kNm,
        "razao_M1_M2_x": entrada.razao_m1_m2_x,
        "razao_M1_M2_y": entrada.razao_m1_m2_y,
        "forcas_transversais_x": entrada.forcas_transversais_x,
        "forcas_transversais_y": entrada.forcas_transversais_y,
        "comprimento_destravado_FLT_mm": resultado.lb_usado_mm,
        "cb": resultado.cb_usado,
        "secao_compacta_confirmada": entrada.secao_compacta_confirmada,
        "espessuras_anglo_mm": dict(entrada.espessuras_anglo or {}),
        **dict(contexto or {}),
    }
    entradas = {chave: valor for chave, valor in entradas.items() if valor is not None}

    resultados: dict[str, Any] = {
        "status_geral": resultado.status_geral,
        "modo_governante": resultado.governante,
        "eixo_governante": eixo_governante,
        "esbeltez_x": lam_x,
        "esbeltez_y": lam_y,
        "esbeltez_governante": max(lam_x, lam_y),
        "utilizacao": aprov_finito,
        "indice_interacao": resultado.indice_interacao
        if resultado.indice_interacao is not None and math.isfinite(resultado.indice_interacao)
        else None,
        "b1_x": resultado.b1_x if resultado.momento_x_primeira_ordem_kNm > 0 else None,
        "b1_y": resultado.b1_y if resultado.momento_y_primeira_ordem_kNm > 0 else None,
        "momento_x_amplificado_kNm": resultado.momento_x_amplificado_kNm or None,
        "momento_y_amplificado_kNm": resultado.momento_y_amplificado_kNm or None,
        "momento_resistente_x_kNm": None
        if resultado.flexao_x is None
        else resultado.flexao_x["MRd"],
        "momento_resistente_y_kNm": None
        if resultado.flexao_y is None
        else resultado.flexao_y["MRd"],
        "atende": resultado.atende,
        "bloqueios": list(resultado.bloqueios) or None,
        "verificações": linhas_para_registro(resultado.verificacoes),
    }
    if comp is not None:
        resultados.update(
            {
                "ne_x_kN": comp["Nex"],
                "ne_y_kN": comp["Ney"],
                "ne_z_kN": comp["Nez"] if math.isfinite(comp["Nez"]) else None,
                "ne_kN": comp["Ne"],
                "modo_flambagem": comp["modo"],
                "fator_q": comp["Q"],
                "area_efetiva_mm2": comp["A_ef"],
                "lambda_0": comp["lambda0"],
                "chi": comp["chi"],
                "resistencia_kN": comp["Nc_Rd"],
                "utilizacao_axial": entrada.N_Sd_kN / comp["Nc_Rd"],
            }
        )
        resultados["esbeltez_paredes"] = [
            {
                "elemento": item["Elemento"],
                "tipo": item["Tipo"],
                "razao": item["b/t"],
                "limite_r": item["(b/t) lim"],
                "grupo": item["Grupo (Tabela 4)"],
                "esbelto": item["Esbelto"],
            }
            for item in tabela_elementos(sec, entrada.fy_MPa, norma, comp, entrada.E_MPa)
        ]
    if aprov_finito is not None:
        # A Central de validação lê esta chave: acima de 1,0 bloqueia a emissão.
        resultados["utilizacao_maxima"] = aprov_finito
    resultados = {chave: valor for chave, valor in resultados.items() if valor is not None}

    alertas = [
        f"{v.nome}: {v.formula}" for v in resultado.verificacoes if v.status in ("NÃO OK", "ALERTA")
    ] + list(resultado.avisos)
    if norma == "NBR8800_2008":
        alertas.append(
            "Conferir na NBR 8800:2008 antes de emitir: " + " ".join(CONFERIR_NBR8800_2008)
        )

    conclusao = (
        f"Status geral {resultado.status_geral}; aproveitamento máximo "
        f"{formatar_percentual(aprov)} em «{resultado.governante}»"
        + (f"; N_c,Rd = {comp['Nc_Rd']:.2f} kN" if comp is not None else "")
        + "."
    )
    modos_txt = "" if comp is None else f" Modo de flambagem que governa: {comp['modo']}."
    texto_resistencia = (
        "Resistência minorada por φ = 0,90 (AISC 360-16)."
        if norma == "AISC360_16_LRFD"
        else f"Resistência minorada por γ_a1 = {entrada.gama_a1:.2f} (NBR 8800, Tabela 3)."
    )
    return criar_registro_tecnico(
        modulo="Flambagem de colunas",
        modulo_id="flambagem_colunas",
        titulo=f"Flambagem de coluna — {sec.nome} ({NORMAS_ROTULOS[norma]})",
        status=STATUS_REGISTRO[resultado.status_geral],
        resumo=(
            f"Verificação da barra inteira pela {NORMAS_ROTULOS[norma]}: todos os modos de "
            "flambagem elástica, flambagem local, flexão em x e y, interação N + Mx + My numa só "
            f"equação e critério Anglo.{modos_txt}"
        ),
        entradas=entradas,
        resultados=resultados,
        metodo=(
            f"{NORMAS_ROTULOS[norma]} — N_c,Rd com N_e do menor modo entre flexão em x, flexão em y, "
            "torção e flexo-torção (acoplada nas seções monossimétricas e cúbica nas assimétricas); "
            + (
                "Q = Q_s·Q_a (Anexo F)"
                if norma == "NBR8800_2008"
                else "A_ef com c₁ e c₂ (Tabelas 4 e 5)"
            )
            + "; momentos amplificados por B₁ com K = 1 no plano de flexão; M_Rd pelo menor entre FLT, "
            "FLM e FLA, limitado a 1,5·W·f_y; interação 5.5.1.2 com M_x e M_y na mesma equação."
        ),
        premissas=[
            "Barra prismática isolada, com efeitos de 2ª ordem locais (B₁); B₂ e a deslocabilidade do "
            "pórtico ficam na análise global.",
            (
                "Esforços de cálculo informados (ações já majoradas)."
                if not equacoes_de_carga
                else "N_Sd obtido por majoração das ações características (NBR 8681 / NBR 8800 4.7)."
            ),
            texto_resistencia,
            "Cisalhamento (5.4.3), cantoneira simples, barras compostas e perfis formados a frio "
            "estão fora do escopo.",
        ],
        equacoes=[
            *equacoes_de_carga,
            *(v.formula for v in resultado.verificacoes if v.tipo == "resistencia" and v.formula),
        ],
        criterios=[
            "Esbeltez λ = máx(K·L/r) ≤ 200 na compressão (Anglo 8.3).",
            "Espessuras mínimas das partes (Anglo 8.8).",
            "Aproveitamento = solicitante ÷ resistente ≤ 1,0 nas verificações de resistência.",
        ],
        alertas=alertas,
        referencias=[
            REFERENCIAS_NORMA[norma],
            "Anglo American — Critério de Projeto Estruturas Metálicas AA-BR-DPST-DR-0001, itens 5.9, 8.3 e 8.8.",
        ],
        conclusao=conclusao,
        materiais_ids=list(materiais_ids),
    )
