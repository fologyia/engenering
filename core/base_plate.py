"""Placa de base e chumbadores — AISC Design Guide 1 (2ª ed.), em unidades SI.

A base de uma coluna em balanço (o caso da plataforma com dois pilares
engastados) recebe compressão **e** momento, e a NBR 8800 não traz um
roteiro fechado para isso; a prática brasileira usa o Design Guide 1 da
AISC, que é o que está aqui, com os fatores de resistência explícitos e
editáveis:

* pressão de contato no concreto ``f_p,max = φ_c·0,85·f_c·√(A₂/A₁)`` com
  ``√(A₂/A₁) ≤ 2`` (AISC J8 / ACI 318), ``φ_c = 0,65``;
* flexão da placa em regime plástico, ``φ_b = 0,90``, cantiléveres
  ``m = (N − 0,95d)/2``, ``n = (B − 0,8b_f)/2`` e ``λn' = λ√(d·b_f)/4``;
* compressão pura (DG1 3.1), momento pequeno com ``e ≤ e_crit`` (DG1 3.3),
  momento grande com tração nos chumbadores (DG1 3.4, ``Y`` pela equação
  do 2º grau) e arrancamento (tração na base, DG1 3.2);
* chumbadores à tração ``φ_t·0,75·F_u·A_b`` e ao cisalhamento
  ``φ_v·0,45·F_u·A_b`` (rosca no plano de corte), com a interação de AISC
  J3.7, ``φ = 0,75``.

O que fica de fora, e o resultado avisa: ancoragem no concreto (arrancamento
do cone, fendilhamento — ACI 318 cap. 17 / NBR 6118), rigidez da base para
o modelo (a placa "engastada" só é engastada se a fundação e os chumbadores
a fizerem assim) e o dimensionamento do bloco ou sapata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

FATOR_CONTATO_CONCRETO = 0.65  # φ_c, AISC J8
FATOR_FLEXAO_PLACA = 0.90  # φ_b
FATOR_CHUMBADOR = 0.75  # φ para tração e cisalhamento (AISC J3)
LIMITE_CONFINAMENTO = 2.0  # √(A₂/A₁) ≤ 2
FRACAO_TRACAO_NOMINAL = 0.75  # F_nt = 0,75·F_u
FRACAO_CISALHAMENTO_NOMINAL = 0.45  # F_nv = 0,45·F_u, rosca no plano de corte


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número positivo.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} deve ser um número maior ou igual a zero.")
    return valor


@dataclass(frozen=True, slots=True)
class ResultadoPlacaBase:
    caso: str
    pressao_maxima_MPa: float
    pressao_atuante_MPa: float
    excentricidade_mm: float
    excentricidade_critica_mm: float | None
    comprimento_contato_mm: float
    m_mm: float
    n_mm: float
    lambda_n_linha_mm: float | None
    tracao_chumbadores_N: float
    braco_tracao_mm: float | None
    espessura_requerida_apoio_mm: float
    espessura_requerida_tracao_mm: float
    espessura_requerida_mm: float
    espessura_adotada_mm: float
    utilizacao_contato: float
    utilizacao_placa: float
    tracao_por_chumbador_N: float
    resistencia_tracao_chumbador_N: float
    utilizacao_tracao_chumbador: float
    cisalhamento_por_chumbador_N: float
    resistencia_cisalhamento_chumbador_N: float
    utilizacao_cisalhamento_chumbador: float
    utilizacao_interacao_chumbador: float
    utilizacao_governante: float
    modo_governante: str
    atende: bool
    avisos: tuple[str, ...] = field(default=())
    memoria: tuple[str, ...] = field(default=())


def verificar_placa_base(
    *,
    profundidade_coluna_mm: float,
    largura_mesa_mm: float,
    espessura_mesa_mm: float,
    comprimento_placa_mm: float,
    largura_placa_mm: float,
    espessura_placa_mm: float,
    fy_placa_MPa: float,
    fck_MPa: float,
    razao_areas_a2_a1: float = 1.0,
    forca_axial_N: float,
    momento_Nmm: float = 0.0,
    cortante_N: float = 0.0,
    numero_chumbadores: int = 4,
    chumbadores_lado_tracionado: int = 2,
    diametro_chumbador_mm: float = 19.05,
    fu_chumbador_MPa: float = 400.0,
    distancia_chumbador_mm: float | None = None,
    fator_contato: float = FATOR_CONTATO_CONCRETO,
    fator_flexao: float = FATOR_FLEXAO_PLACA,
    fator_chumbador: float = FATOR_CHUMBADOR,
) -> ResultadoPlacaBase:
    """Verifica placa e chumbadores para ``P`` (+ compressão, − tração), ``M`` e ``V``.

    ``comprimento_placa_mm`` (N) é a dimensão na direção do momento, paralela
    à alma; ``largura_placa_mm`` (B) a outra. ``distancia_chumbador_mm`` (f) é
    a distância do centro da placa à linha dos chumbadores tracionados; se
    omitida, adota-se ``N/2 − 50 mm``. ``razao_areas_a2_a1`` é ``A₂/A₁`` do
    pedestal (1,0 quando a placa cobre o pedestal inteiro).
    """
    d = _positivo("profundidade da coluna", profundidade_coluna_mm)
    bf = _positivo("largura da mesa", largura_mesa_mm)
    tf = _positivo("espessura da mesa", espessura_mesa_mm)
    comprimento = _positivo("comprimento da placa N", comprimento_placa_mm)
    largura = _positivo("largura da placa B", largura_placa_mm)
    tp = _positivo("espessura da placa", espessura_placa_mm)
    fy = _positivo("f_y da placa", fy_placa_MPa)
    fc = _positivo("f_ck", fck_MPa)
    razao = _positivo("A₂/A₁", razao_areas_a2_a1)
    phi_c = _positivo("φ_c", fator_contato)
    phi_b = _positivo("φ_b", fator_flexao)
    phi_t = _positivo("φ do chumbador", fator_chumbador)
    p = float(forca_axial_N)
    m_u = abs(float(momento_Nmm))
    v_u = abs(float(cortante_N))
    if not all(math.isfinite(valor) for valor in (p, m_u, v_u)):
        raise ValueError("Esforços devem ser números finitos.")
    n_ch = int(numero_chumbadores)
    n_lado = int(chumbadores_lado_tracionado)
    if n_ch <= 0 or n_lado <= 0 or n_lado > n_ch:
        raise ValueError("Número de chumbadores inválido (total ≥ lado tracionado ≥ 1).")
    d_ch = _positivo("diâmetro do chumbador", diametro_chumbador_mm)
    fu_ch = _positivo("f_u do chumbador", fu_chumbador_MPa)
    if comprimento <= d or largura < bf:
        raise ValueError("A placa precisa ser maior que a seção da coluna (N > d e B ≥ b_f).")
    f = (
        comprimento / 2.0 - 50.0
        if distancia_chumbador_mm is None
        else _positivo("distância f dos chumbadores", distancia_chumbador_mm)
    )
    if f >= comprimento / 2.0:
        raise ValueError("Os chumbadores precisam ficar dentro da placa (f < N/2).")

    avisos: list[str] = []
    memoria: list[str] = []
    area_placa = comprimento * largura
    confinamento = min(math.sqrt(razao), LIMITE_CONFINAMENTO)
    f_p_max = phi_c * 0.85 * fc * confinamento
    q_max = f_p_max * largura
    m = (comprimento - 0.95 * d) / 2.0
    n = (largura - 0.8 * bf) / 2.0
    memoria.append(
        f"f_p,max = φ_c·0,85·f_ck·√(A₂/A₁) = {phi_c:.2f} × 0,85 × {fc:.1f} × {confinamento:.3f} "
        f"= {f_p_max:.3f} MPa; q_max = f_p,max·B = {q_max / 1e3:.3f} kN/mm"
    )
    memoria.append(
        f"m = (N − 0,95d)/2 = {m:.1f} mm; n = (B − 0,8b_f)/2 = {n:.1f} mm; "
        f"A₁ = N·B = {area_placa:.0f} mm²"
    )
    if m < 0 or n < 0:
        avisos.append(
            "A placa é menor que o retângulo 0,95d × 0,8b_f: o modelo de cantiléver não se "
            "aplica — aumente N ou B."
        )

    def espessura_apoio(pressao: float, y: float) -> float:
        """Placa fletida pela pressão de contato no cantiléver ``m`` (DG1 3.3.3/3.4.4).

        Com ``Y ≥ m`` a pressão cobre o cantiléver inteiro (``M = f_p·m²/2``);
        com ``Y < m`` só a faixa de comprimento ``Y`` está carregada
        (``M = f_p·Y·(m − Y/2)``). ``t = √(4M/(φ_b·f_y))`` é a placa em regime
        plástico — os 1,5 e 2,11 do Design Guide já com ``φ_b = 0,90``.
        """
        if m <= 0:
            return 0.0
        if y >= m:
            momento_unitario = pressao * m**2 / 2.0
        else:
            momento_unitario = pressao * y * (m - y / 2.0)
        return math.sqrt(4.0 * momento_unitario / (phi_b * fy))

    tracao_total = 0.0
    braco_tracao: float | None = None
    t_apoio = 0.0
    t_tracao = 0.0
    lambda_n_linha: float | None = None
    e_crit: float | None = None
    pressao = 0.0
    y = comprimento
    e = m_u / p if p > 0 else math.inf if m_u > 0 else 0.0

    if p > 0 and m_u == 0.0:
        caso = "compressão centrada (DG1 3.1)"
        pressao = p / area_placa
        x = (4.0 * d * bf / (d + bf) ** 2) * (p / (f_p_max * area_placa))
        if x >= 1.0:
            lam = 1.0
        else:
            lam = min(1.0, 2.0 * math.sqrt(x) / (1.0 + math.sqrt(1.0 - x)))
        lambda_n_linha = lam * math.sqrt(d * bf) / 4.0
        braco = max(m, n, lambda_n_linha)
        t_apoio = braco * math.sqrt(2.0 * p / (phi_b * fy * area_placa))
        memoria.append(
            f"f_pu = P/A₁ = {pressao:.3f} MPa ≤ f_p,max; X = {x:.3f}, λ = {lam:.3f}, "
            f"λn' = {lambda_n_linha:.1f} mm; l = max(m, n, λn') = {braco:.1f} mm"
        )
        memoria.append(
            f"t_req = l·√(2P/(φ_b·f_y·B·N)) = {braco:.1f} × √(2 × {p / 1e3:.1f} kN / "
            f"({phi_b:.2f} × {fy:.0f} × {area_placa:.0f})) = {t_apoio:.2f} mm"
        )
    elif p > 0:
        e_crit = comprimento / 2.0 - p / (2.0 * q_max)
        memoria.append(f"e = M/P = {e:.1f} mm; e_crit = N/2 − P/(2·q_max) = {e_crit:.1f} mm")
        if e <= e_crit:
            caso = "momento pequeno, sem tração nos chumbadores (DG1 3.3)"
            y = comprimento - 2.0 * e
            pressao = p / (y * largura)
            t_apoio = espessura_apoio(pressao, y)
            memoria.append(
                f"Y = N − 2e = {y:.1f} mm; f_p = P/(Y·B) = {pressao:.3f} MPa ≤ f_p,max = {f_p_max:.3f} MPa"
            )
            memoria.append(f"t_req (apoio) = {t_apoio:.2f} mm")
        else:
            caso = "momento grande, com tração nos chumbadores (DG1 3.4)"
            soma = f + comprimento / 2.0
            discriminante = soma**2 - 2.0 * p * (e + f) / q_max
            if discriminante < 0:
                raise ValueError(
                    "Placa insuficiente para o momento: (f + N/2)² < 2P(e + f)/q_max. "
                    "Aumente N, B, f_ck ou a distância f dos chumbadores."
                )
            y = soma - math.sqrt(discriminante)
            pressao = f_p_max
            tracao_total = q_max * y - p
            braco_tracao = f - d / 2.0 + tf / 2.0
            t_apoio = espessura_apoio(pressao, y)
            if braco_tracao > 0:
                t_tracao = math.sqrt(4.0 * tracao_total * braco_tracao / (largura * phi_b * fy))
            else:
                avisos.append(
                    "Os chumbadores ficam dentro da mesa (x ≤ 0): a flexão da placa pela tração "
                    "não segue o modelo de cantiléver; posicione-os fora da mesa."
                )
            memoria.append(
                f"Y = (f + N/2) − √[(f + N/2)² − 2P(e + f)/q_max] = {y:.1f} mm; "
                f"T = q_max·Y − P = {tracao_total / 1e3:.2f} kN"
            )
            memoria.append(
                f"t_req (apoio, f_p = f_p,max) = {t_apoio:.2f} mm; "
                f"x = f − d/2 + t_f/2 = {braco_tracao:.1f} mm; "
                f"t_req (tração) = √(4·T·x/(B·φ_b·f_y)) = {t_tracao:.2f} mm"
            )
    else:
        caso = "tração na base (arrancamento) — chumbadores levam tudo (DG1 3.2)"
        y = 0.0
        pressao = 0.0
        e = math.inf if p == 0 and m_u > 0 else e
        # Duas linhas de chumbadores a ±f: a tração total se divide e o
        # momento soma num lado e alivia no outro.
        tracao_total = abs(p) / 2.0 + (m_u / (2.0 * f) if m_u > 0 else 0.0)
        if p == 0 and m_u == 0:
            tracao_total = 0.0
        braco_tracao = f - d / 2.0 + tf / 2.0
        if braco_tracao > 0 and tracao_total > 0:
            t_tracao = math.sqrt(4.0 * tracao_total * braco_tracao / (largura * phi_b * fy))
        memoria.append(
            f"T (lado mais tracionado) = |P|/2 + M/(2f) = {abs(p) / 2e3:.2f} + "
            f"{(m_u / (2.0 * f)) / 1e3 if m_u > 0 else 0.0:.2f} = {tracao_total / 1e3:.2f} kN; "
            f"x = {braco_tracao:.1f} mm; t_req (tração) = {t_tracao:.2f} mm"
        )
        if p == 0 and m_u > 0:
            avisos.append(
                "Momento sem compressão: modelo de binário nos chumbadores, conservador; "
                "confira com o caso de momento grande se houver compressão mínima."
            )

    t_req = max(t_apoio, t_tracao)
    utilizacao_contato = pressao / f_p_max if f_p_max > 0 else math.inf
    # Flexão plástica: M_Rd ∝ t², logo utilização = (t_req/t_p)².
    utilizacao_placa = (t_req / tp) ** 2 if t_req > 0 else 0.0

    area_chumbador = math.pi * d_ch**2 / 4.0
    tracao_por_chumbador = tracao_total / n_lado if tracao_total > 0 else 0.0
    resistencia_tracao = phi_t * FRACAO_TRACAO_NOMINAL * fu_ch * area_chumbador
    utilizacao_tracao = tracao_por_chumbador / resistencia_tracao
    cisalhamento_por_chumbador = v_u / n_ch
    resistencia_cisalhamento = phi_t * FRACAO_CISALHAMENTO_NOMINAL * fu_ch * area_chumbador
    utilizacao_cisalhamento = cisalhamento_por_chumbador / resistencia_cisalhamento
    # AISC J3.7: F'_nt = 1,3·F_nt − F_nt·f_rv/(φ·F_nv) ≤ F_nt.
    f_nt = FRACAO_TRACAO_NOMINAL * fu_ch
    f_nv = FRACAO_CISALHAMENTO_NOMINAL * fu_ch
    f_rv = cisalhamento_por_chumbador / area_chumbador
    f_nt_reduzida = min(f_nt, 1.3 * f_nt - f_nt * f_rv / (phi_t * f_nv))
    if f_nt_reduzida <= 0:
        utilizacao_interacao = math.inf
    else:
        utilizacao_interacao = (
            tracao_por_chumbador / (phi_t * f_nt_reduzida * area_chumbador)
            if tracao_por_chumbador > 0
            else utilizacao_cisalhamento
        )
    memoria.append(
        f"Chumbador Ø{d_ch:.2f} mm, A_b = {area_chumbador:.1f} mm², f_u = {fu_ch:.0f} MPa: "
        f"T_Rd = φ·0,75·f_u·A_b = {resistencia_tracao / 1e3:.2f} kN por chumbador; "
        f"V_Rd = φ·0,45·f_u·A_b = {resistencia_cisalhamento / 1e3:.2f} kN por chumbador"
    )
    memoria.append(
        f"Tração por chumbador = {tracao_por_chumbador / 1e3:.2f} kN ({n_lado} no lado tracionado); "
        f"cisalhamento por chumbador = {cisalhamento_por_chumbador / 1e3:.2f} kN ({n_ch} no total); "
        f"interação J3.7: F'_nt = {f_nt_reduzida:.1f} MPa"
    )
    if utilizacao_contato > 1.0:
        avisos.append(
            f"Pressão de contato {pressao:.3f} MPa acima de f_p,max = {f_p_max:.3f} MPa: aumente a "
            "placa ou o f_ck."
        )
    if utilizacao_cisalhamento > 0.2:
        avisos.append(
            "Cortante relevante nos chumbadores: em bases reais o cortante costuma ir por atrito "
            "ou por chave de cisalhamento; confira o mecanismo adotado e as folgas dos furos."
        )
    avisos.append(
        "Ancoragem no concreto não verificada (comprimento de ancoragem, arrancamento do cone, "
        "fendilhamento — ACI 318 cap. 17 / NBR 6118); dimensionar o bloco ou sapata em separado."
    )
    if tracao_total > 0:
        avisos.append(
            "Base com tração nos chumbadores: o modelo global deve refletir a rigidez real da "
            "base (engaste só se placa, chumbadores e fundação o garantirem)."
        )

    candidatos = {
        "Pressão de contato no concreto": utilizacao_contato,
        "Flexão da placa": utilizacao_placa,
        "Tração do chumbador": utilizacao_tracao,
        "Cisalhamento do chumbador": utilizacao_cisalhamento,
        "Interação tração–cisalhamento (J3.7)": utilizacao_interacao,
    }
    modo, governante = max(candidatos.items(), key=lambda item: item[1])
    return ResultadoPlacaBase(
        caso=caso,
        pressao_maxima_MPa=f_p_max,
        pressao_atuante_MPa=pressao,
        excentricidade_mm=e,
        excentricidade_critica_mm=e_crit,
        comprimento_contato_mm=y,
        m_mm=m,
        n_mm=n,
        lambda_n_linha_mm=lambda_n_linha,
        tracao_chumbadores_N=tracao_total,
        braco_tracao_mm=braco_tracao,
        espessura_requerida_apoio_mm=t_apoio,
        espessura_requerida_tracao_mm=t_tracao,
        espessura_requerida_mm=t_req,
        espessura_adotada_mm=tp,
        utilizacao_contato=utilizacao_contato,
        utilizacao_placa=utilizacao_placa,
        tracao_por_chumbador_N=tracao_por_chumbador,
        resistencia_tracao_chumbador_N=resistencia_tracao,
        utilizacao_tracao_chumbador=utilizacao_tracao,
        cisalhamento_por_chumbador_N=cisalhamento_por_chumbador,
        resistencia_cisalhamento_chumbador_N=resistencia_cisalhamento,
        utilizacao_cisalhamento_chumbador=utilizacao_cisalhamento,
        utilizacao_interacao_chumbador=utilizacao_interacao,
        utilizacao_governante=governante,
        modo_governante=modo,
        atende=governante <= 1.0 and not (m < 0 or n < 0),
        avisos=tuple(avisos),
        memoria=tuple(memoria),
    )
