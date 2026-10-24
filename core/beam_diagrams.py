"""Amostragem, diagramas e verificações dos resultados de vigas e eixos."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np

from core.beam_model import (
    TOLERANCIA_POSICAO_MM,
    Apoio,
    Extremo,
    PontoDiagrama,
    ResultadoViga,
    Viga,
)
from core.beam_numerics import _Elemento
from core.beam_sections import SecaoViga, _finito, _positivo
from core.load_to_stress import EstadoPlanoCalculado
from core.section_stress import EsforcosSecao, tensoes_combinadas


def _amostras(elemento: _Elemento, quantidade: int, ei: float) -> list[float]:
    """Pontos locais do elemento, incluindo raízes de V, M e θ.

    Incluir as raízes garante que o momento máximo (V = 0), a flecha máxima
    (θ = 0) e a rotação máxima (M = 0, pois dθ/dx = M/EI) caiam exatamente
    sobre uma amostra, em vez de dependerem da densidade da malha.
    """
    l = elemento.comprimento
    valores: list[float] = [float(item) for item in np.linspace(0.0, l, quantidade)]
    v_i = float(elemento.esforcos_flexao[0])
    m_i = float(elemento.esforcos_flexao[1])
    q_i = float(elemento.esforcos_equilibrio[0])
    mq_i = float(elemento.esforcos_equilibrio[1])
    inclinacao = (elemento.w_j - elemento.w_i) / l
    # Sem segunda ordem N̄ = 0: V volta à parábola clássica e M à cúbica.
    fator = elemento.normal_geometrico / ei
    # EI θ(x) = EI θ_i + v_i x²/2 - m_i x + w_i x³/6 + (w_j - w_i) x⁴/(24 L)
    theta = [inclinacao / 24.0, elemento.w_i / 6.0, v_i / 2.0, -m_i, ei * elemento.theta_i]
    # EI (v(x) − v_i) = EI θ_i x + v_i x³/6 − m_i x²/2 + w_i x⁴/24 + (w_j − w_i) x⁵/(120 L)
    flecha = [
        inclinacao / 120.0,
        elemento.w_i / 24.0,
        v_i / 6.0,
        -m_i / 2.0,
        ei * elemento.theta_i,
        0.0,
    ]
    # V(x) = Q(x) + N̄ θ(x), com Q(x) = q_i + w_i x + (w_j - w_i) x² / (2 L).
    cortante = [
        theta[0] * fator,
        theta[1] * fator,
        theta[2] * fator + inclinacao / 2.0,
        theta[3] * fator + elemento.w_i,
        theta[4] * fator + q_i,
    ]
    # M(x) = q_i x − mq_i + w_i x²/2 + (w_j − w_i) x³/(6 L) + N̄ (v(x) − v_i).
    momento = [
        flecha[0] * fator,
        flecha[1] * fator,
        flecha[2] * fator + inclinacao / 6.0,
        flecha[3] * fator + elemento.w_i / 2.0,
        flecha[4] * fator + q_i,
        -mq_i,
    ]
    for polinomio in (theta, cortante, momento):
        valores.extend(_raizes_polinomio(polinomio, l))
    # Uma trapezoidal que troca de sinal dentro do trecho (w = 0) dá um
    # extremo interno de V; o mesmo vale para a axial distribuída e N.
    for inicio, fim in ((elemento.w_i, elemento.w_j), (elemento.a_i, elemento.a_j)):
        if inicio * fim < 0:
            valores.append(l * inicio / (inicio - fim))
    valores = sorted(set(round(valor, 9) for valor in valores if 0.0 <= valor <= l))
    return valores


def _raizes_polinomio(coeficientes: Sequence[float], limite: float) -> list[float]:
    """Raízes reais em ``[0, limite]``, com os coeficientes em ordem decrescente.

    O polinômio é reescrito em ``t = x / limite`` antes de ir ao ``np.roots``:
    com ``x`` em mm e coeficientes que vão de N/mm² a N·mm, os termos
    diferem por muitas ordens de grandeza e a matriz companheira fica mal
    condicionada. Em ``t ∈ [0, 1]`` todos os termos ficam comparáveis, e os
    de maior grau que são desprezíveis nessa escala são descartados — em
    vez de produzir uma raiz "no infinito" cheia de ruído.
    """
    grau = len(coeficientes) - 1
    escalados = [
        float(valor) * limite ** (grau - indice) for indice, valor in enumerate(coeficientes)
    ]
    maior = max((abs(valor) for valor in escalados), default=0.0)
    if not maior or not math.isfinite(maior):
        return []
    while escalados and abs(escalados[0]) <= 1e-12 * maior:
        escalados = escalados[1:]
    if len(escalados) < 2:
        return []
    try:
        raizes = np.roots(escalados)
    except np.linalg.LinAlgError:  # pragma: no cover - numpy raramente falha aqui
        return []
    return [
        float(raiz.real) * limite
        for raiz in raizes
        if abs(raiz.imag) <= 1e-7 and -1e-9 <= raiz.real <= 1.0 + 1e-9
    ]


def _ponto_diagrama(
    elemento: _Elemento,
    x_local: float,
    viga: Viga,
    ei: float,
    ea: float,
    gj: float,
) -> PontoDiagrama:
    l = elemento.comprimento
    w_i, w_j = elemento.w_i, elemento.w_j
    delta_w = (w_j - w_i) / l
    # Parcela elástica: gera a linha elástica (integração exata de 1ª ordem).
    v_i = float(elemento.esforcos_flexao[0])
    m_i = float(elemento.esforcos_flexao[1])
    # Parcela em equilíbrio (com K_g): gera os esforços internos.
    q_i = float(elemento.esforcos_equilibrio[0])
    mq_i = float(elemento.esforcos_equilibrio[1])
    n_geo = elemento.normal_geometrico
    x = x_local

    rotacao = (
        elemento.theta_i
        + (v_i * x**2 / 2.0 - m_i * x + w_i * x**3 / 6.0 + delta_w * x**4 / 24.0) / ei
    )
    flecha = (
        elemento.v_i
        + elemento.theta_i * x
        + (v_i * x**3 / 6.0 - m_i * x**2 / 2.0 + w_i * x**4 / 24.0 + delta_w * x**5 / 120.0) / ei
    )
    # Equilíbrio do trecho [0, x] na configuração deformada: o esforço normal
    # N̄ atuando no braço (v − v_i) é o momento P–Δ dentro do elemento, e
    # V = dM/dx = Q + N̄ θ é o cortante na seção (perpendicular ao eixo
    # deformado), que é o que gera a tensão de cisalhamento. Sem segunda
    # ordem N̄ = 0 e as expressões voltam às de primeira ordem.
    transversal = q_i + w_i * x + delta_w * x**2 / 2.0
    momento = (
        q_i * x - mq_i + w_i * x**2 / 2.0 + delta_w * x**3 / 6.0 + n_geo * (flecha - elemento.v_i)
    )
    cortante = transversal + n_geo * rotacao

    a_i, a_j = elemento.a_i, elemento.a_j
    delta_a = (a_j - a_i) / l
    normal = -elemento.esforco_axial_i - (a_i * x + delta_a * x**2 / 2.0)
    deslocamento_axial = (
        elemento.u_i
        + (-elemento.esforco_axial_i * x - a_i * x**2 / 2.0 - delta_a * x**3 / 6.0) / ea
    )

    torque = elemento.esforco_torcao_i
    giro = elemento.phi_i + (torque * x / gj if gj > 0 else 0.0)

    return _montar_ponto(
        x_global=elemento.x_i + x,
        normal=normal,
        cortante=cortante,
        momento=momento,
        torque=torque,
        flecha=flecha,
        rotacao=rotacao,
        deslocamento_axial=deslocamento_axial,
        giro=giro,
        secao=viga.secao,
    )


def _montar_ponto(
    *,
    x_global: float,
    normal: float,
    cortante: float,
    momento: float,
    torque: float,
    flecha: float,
    rotacao: float,
    deslocamento_axial: float,
    giro: float,
    secao: SecaoViga,
) -> PontoDiagrama:
    # As tensões vêm do núcleo compartilhado com o assistente de cargas, para
    # que as duas páginas nunca divirjam na mesma seção.
    tensoes = tensoes_combinadas(
        EsforcosSecao(
            normal_N=normal,
            momento_Nmm=momento,
            cortante_N=cortante,
            torque_Nmm=torque,
        ),
        secao,
    )
    critico = tensoes.critico

    return PontoDiagrama(
        x_mm=x_global,
        normal_N=normal,
        cortante_N=cortante,
        momento_Nmm=momento,
        torque_Nmm=torque,
        deslocamento_mm=flecha,
        rotacao_rad=rotacao,
        deslocamento_axial_mm=deslocamento_axial,
        giro_torcao_rad=giro,
        tensao_axial_MPa=tensoes.axial_MPa,
        tensao_flexao_superior_MPa=tensoes.flexao_superior_MPa,
        tensao_flexao_inferior_MPa=tensoes.flexao_inferior_MPa,
        tensao_normal_superior_MPa=tensoes.normal_superior_MPa,
        tensao_normal_inferior_MPa=tensoes.normal_inferior_MPa,
        tensao_cisalhamento_MPa=tensoes.cisalhamento_MPa,
        tensao_torcao_MPa=tensoes.torcao_MPa,
        von_mises_MPa=critico.von_mises_MPa,
        tresca_MPa=critico.tresca_MPa,
        ponto_critico=critico.nome,
        sigma_critico_MPa=critico.sigma_MPa,
        tau_critico_MPa=critico.tau_MPa,
    )


def estado_no_ponto_critico(ponto: PontoDiagrama) -> tuple[float, float]:
    """Par (σ, τ) que governou o von Mises daquela seção."""
    return ponto.sigma_critico_MPa, ponto.tau_critico_MPa


def ponto_em(resultado: ResultadoViga, x_mm: float) -> PontoDiagrama:
    """Ponto do diagrama em ``x_mm``, escolhendo o mais solicitado.

    Numa descontinuidade (carga concentrada, apoio, momento aplicado) há dois
    valores na mesma abscissa — um de cada lado. Devolver o de maior von
    Mises é o que interessa para levar a seção adiante: é ele que governa a
    verificação no módulo seguinte.
    """
    if not resultado.pontos:  # pragma: no cover - resultado sempre tem pontos
        raise ValueError("O resultado não contém pontos de diagrama.")
    alvo = _finito("x_mm", x_mm)
    distancia_minima = min(abs(ponto.x_mm - alvo) for ponto in resultado.pontos)
    candidatos = [
        ponto
        for ponto in resultado.pontos
        if abs(abs(ponto.x_mm - alvo) - distancia_minima) <= TOLERANCIA_POSICAO_MM
    ]
    return max(candidatos, key=lambda ponto: ponto.von_mises_MPa)


def secoes_notaveis(resultado: ResultadoViga) -> dict[str, float]:
    """Abscissas que valem a pena levar adiante, por grandeza governante."""
    extremos = resultado.extremos
    return {
        "Seção mais solicitada (von Mises)": extremos["von_mises"].x_mm,
        "Momento fletor máximo": extremos["momento"].x_mm,
        "Cortante máximo": extremos["cortante"].x_mm,
        "Esforço normal máximo": extremos["normal"].x_mm,
        "Torque máximo": extremos["torque"].x_mm,
        "Flecha máxima": extremos["flecha"].x_mm,
    }


def estado_plano_da_secao(
    resultado: ResultadoViga,
    x_mm: float | None = None,
    *,
    ponto: str | None = None,
) -> EstadoPlanoCalculado:
    """Converte uma seção da barra no estado plano usado pelos outros módulos.

    É o mesmo contrato que o assistente de cargas entrega ao Círculo de Mohr
    e à Análise estática, então a seção crítica de uma viga entra nesses
    módulos sem ninguém redigitar número nenhum.
    """
    if x_mm is None:
        x_mm = resultado.extremos["von_mises"].x_mm
    diagrama = ponto_em(resultado, x_mm)
    tensoes = tensoes_combinadas(
        EsforcosSecao(
            normal_N=diagrama.normal_N,
            momento_Nmm=diagrama.momento_Nmm,
            cortante_N=diagrama.cortante_N,
            torque_Nmm=diagrama.torque_Nmm,
        ),
        resultado.viga.secao,
    )
    escolhido = tensoes.critico if ponto is None else tensoes.ponto(ponto)
    return EstadoPlanoCalculado(
        sigma_x=escolhido.sigma_MPa,
        sigma_y=0.0,
        tau_xy=escolhido.tau_MPa,
        descricao=(
            f"{escolhido.nome} da seção em x = {diagrama.x_mm / 1_000.0:.3f} m "
            f"de {resultado.viga.nome} ({resultado.viga.secao.nome})"
        ),
        hipoteses=(
            "Estado plano na superfície da barra: a tensão transversal é nula.",
            "Tensões de flexão, axial, cortante e torção superpostas linearmente.",
            f"Esforços da seção: N = {diagrama.normal_N / 1_000.0:.3f} kN, "
            f"V = {diagrama.cortante_N / 1_000.0:.3f} kN, "
            f"M = {diagrama.momento_Nmm / 1e6:.3f} kN·m, "
            f"T = {diagrama.torque_Nmm / 1e6:.3f} kN·m.",
            "Concentração de tensão e efeitos locais de apoio não incluídos.",
        ),
    )


def amplitudes_de_fadiga(
    resultado: ResultadoViga, x_mm: float | None = None, *, eixo_girante: bool = True
) -> dict[str, float]:
    """Componentes alternada e média para levar à Análise de fadiga.

    Num **eixo girante** a fibra passa alternadamente por tração e compressão
    a cada volta: a flexão é totalmente alternada (``σa = |M| c/I``, média
    zero) e a parcela axial permanece estática. Numa viga fixa o mesmo
    momento é estático — por isso ``eixo_girante=False`` devolve amplitude
    zero, em vez de fingir que há ciclo onde não há.
    """
    if x_mm is None:
        x_mm = resultado.extremos["momento"].x_mm
    diagrama = ponto_em(resultado, x_mm)
    secao = resultado.viga.secao
    flexao = (
        abs(diagrama.momento_Nmm)
        * max(secao.c_superior_mm, secao.c_inferior_mm)
        / secao.inercia_mm4
    )
    axial = diagrama.normal_N / secao.area_mm2
    if eixo_girante:
        return {
            "x_mm": diagrama.x_mm,
            "sigma_alternada_MPa": flexao,
            "sigma_media_MPa": axial,
            "tensao_torcao_MPa": abs(diagrama.tensao_torcao_MPa),
        }
    return {
        "x_mm": diagrama.x_mm,
        "sigma_alternada_MPa": 0.0,
        "sigma_media_MPa": axial + flexao,
        "tensao_torcao_MPa": abs(diagrama.tensao_torcao_MPa),
    }


_EXTREMOS = (
    ("normal", "normal_N", "N"),
    ("cortante", "cortante_N", "N"),
    ("momento", "momento_Nmm", "N·mm"),
    ("torque", "torque_Nmm", "N·mm"),
    ("flecha", "deslocamento_mm", "mm"),
    ("rotacao", "rotacao_rad", "rad"),
    ("giro_torcao", "giro_torcao_rad", "rad"),
    ("tensao_normal", "tensao_normal_inferior_MPa", "MPa"),
    ("tensao_cisalhamento", "tensao_cisalhamento_MPa", "MPa"),
    ("tensao_torcao", "tensao_torcao_MPa", "MPa"),
    ("von_mises", "von_mises_MPa", "MPa"),
    ("tresca", "tresca_MPa", "MPa"),
)


def _extremo_por_modulo(pontos: Sequence[PontoDiagrama], atributo: str) -> PontoDiagrama:
    """Ponto de maior módulo; empate fica com o de menor ``x``.

    Numa viga simétrica o cortante vale +wL/2 num apoio e −wL/2 no outro:
    o módulo empata e, sem um critério explícito, o sinal reportado passa a
    depender de ruído de arredondamento — refinar a malha invertia o sinal.
    A tolerância relativa absorve esse ruído e o desempate por ``x`` torna a
    escolha reprodutível.

    A folga de 1e-9 é escolhida pelo ruído do solver, que cresce com o número
    de elementos: dois extremos de fato distintos num diagrama de viga nunca
    diferem por menos de uma parte em 1e9.
    """
    maximo = max(abs(getattr(ponto, atributo)) for ponto in pontos)
    limite = maximo * (1.0 - 1e-9)
    empatados = [ponto for ponto in pontos if abs(getattr(ponto, atributo)) >= limite]
    return min(empatados, key=lambda ponto: ponto.x_mm)


def _calcular_extremos(pontos: Sequence[PontoDiagrama]) -> dict[str, Extremo]:
    """Extremo = valor de maior módulo, preservando o sinal original."""
    extremos: dict[str, Extremo] = {}
    for chave, atributo, unidade in _EXTREMOS:
        melhor = _extremo_por_modulo(pontos, atributo)
        extremos[chave] = Extremo(
            grandeza=chave,
            valor=float(getattr(melhor, atributo)),
            x_mm=melhor.x_mm,
            unidade=unidade,
        )
    # A tensão normal extrema pode estar na fibra superior; refaz o confronto.
    melhor_superior = _extremo_por_modulo(pontos, "tensao_normal_superior_MPa")
    if abs(melhor_superior.tensao_normal_superior_MPa) > abs(extremos["tensao_normal"].valor):
        extremos["tensao_normal"] = Extremo(
            grandeza="tensao_normal",
            valor=float(melhor_superior.tensao_normal_superior_MPa),
            x_mm=melhor_superior.x_mm,
            unidade="MPa",
        )
    return extremos


def _grau_hiperestaticidade(apoios: Iterable[Apoio], numero_rotulas: int) -> int:
    """Reações incógnitas − equações de equilíbrio no plano (3) − rótulas.

    Apoios elásticos entram como reação: eles de fato aplicam uma força, e
    ignorá-los faria uma viga estável sobre duas molas aparecer com grau
    negativo, como se fosse um mecanismo.
    """
    incognitas = 0
    for apoio in apoios:
        incognitas += int(apoio.restringe_vertical or apoio.rigidez_vertical_N_mm > 0)
        incognitas += int(apoio.restringe_horizontal)
        incognitas += int(apoio.restringe_rotacao or apoio.rigidez_rotacional_Nmm_rad > 0)
    return incognitas - 3 - numero_rotulas


def verificar_flecha(
    resultado: ResultadoViga,
    *,
    limite_vao: float = 350.0,
    vao_mm: float | None = None,
) -> dict[str, float | bool | str]:
    """Compara a flecha máxima com o clássico L/limite.

    ``vao_mm`` permite informar o vão real entre apoios quando a barra tem
    balanços; por padrão usa a distância entre o primeiro e o último apoio,
    ou o comprimento total quando há um só apoio (balanço engastado).
    """
    limite_vao = _positivo("limite_vao", limite_vao)
    if vao_mm is None:
        comprimento = resultado.viga.comprimento_mm
        # Só conta como extremo do vão quem segura a barra na vertical: uma
        # trava axial ou um apoio "livre" não define vão nenhum.
        posicoes_apoio = sorted(
            min(max(apoio.x_mm, 0.0), comprimento)
            for apoio in resultado.viga.apoios
            if apoio.restringe_vertical or apoio.rigidez_vertical_N_mm > 0
        )
        if len(posicoes_apoio) >= 2 and posicoes_apoio[-1] - posicoes_apoio[0] > 0:
            vao_mm = posicoes_apoio[-1] - posicoes_apoio[0]
        else:
            vao_mm = comprimento
    vao_mm = _positivo("vao_mm", vao_mm)
    flecha = abs(resultado.extremos["flecha"].valor)
    admissivel = vao_mm / limite_vao
    return {
        "vao_mm": vao_mm,
        "limite_vao": limite_vao,
        "flecha_mm": flecha,
        "flecha_admissivel_mm": admissivel,
        "utilizacao": flecha / admissivel if admissivel > 0 else math.inf,
        "atende": flecha <= admissivel,
        "criterio": f"L/{limite_vao:.0f}",
    }


def tabela_diagramas(resultado: ResultadoViga) -> list[dict[str, float | str]]:
    """Diagramas em unidades de engenharia (m, kN, kN·m, mm, MPa)."""
    return [
        {
            "x (m)": ponto.x_mm / 1_000.0,
            "N (kN)": ponto.normal_N / 1_000.0,
            "V (kN)": ponto.cortante_N / 1_000.0,
            "M (kN·m)": ponto.momento_Nmm / 1e6,
            "T (kN·m)": ponto.torque_Nmm / 1e6,
            "Flecha (mm)": ponto.deslocamento_mm,
            "Rotação (mrad)": ponto.rotacao_rad * 1_000.0,
            "Giro torção (°)": math.degrees(ponto.giro_torcao_rad),
            "σ sup (MPa)": ponto.tensao_normal_superior_MPa,
            "σ inf (MPa)": ponto.tensao_normal_inferior_MPa,
            "τ V (MPa)": ponto.tensao_cisalhamento_MPa,
            "τ T (MPa)": ponto.tensao_torcao_MPa,
            "von Mises (MPa)": ponto.von_mises_MPa,
            "Ponto crítico": ponto.ponto_critico,
        }
        for ponto in resultado.pontos
    ]


def resumo_reacoes(resultado: ResultadoViga) -> list[dict[str, object]]:
    return [
        {
            "x (m)": reacao.x_mm / 1_000.0,
            "Apoio": reacao.tipo,
            "Fy (kN)": reacao.fy_N / 1_000.0,
            "Fx (kN)": reacao.fx_N / 1_000.0,
            "Mz (kN·m)": reacao.mz_Nmm / 1e6,
            "Mt (kN·m)": reacao.mt_Nmm / 1e6,
        }
        for reacao in resultado.reacoes
    ]


def conferir_equilibrio(resultado: ResultadoViga) -> dict[str, float]:
    """Resíduo do equilíbrio global — controle numérico do próprio solver.

    Momentos tomados em torno de ``x = 0``. Com a segunda ordem ligada, as
    reações equilibram as cargas na **configuração deformada**: cada esforço
    normal age no braço da flecha, e esse momento P–Δ (``∫ N dv``, devolvido
    em ``momento_p_delta_Nmm``) entra na soma — sem ele, o resíduo de ΣM
    seria exatamente o efeito de segunda ordem, e não um erro do solver.

    ``residuo_relativo`` é o pior dos quatro resíduos, cada um dividido pela
    escala da sua própria grandeza (força, momento = força × L, torque).
    """
    viga = resultado.viga
    comprimento_total = viga.comprimento_mm
    soma_fy = sum(reacao.fy_N for reacao in resultado.reacoes)
    soma_fx = sum(reacao.fx_N for reacao in resultado.reacoes)
    soma_mz = sum(reacao.mz_Nmm + reacao.fy_N * reacao.x_mm for reacao in resultado.reacoes)
    soma_mt = sum(reacao.mt_Nmm for reacao in resultado.reacoes)
    escala_forca = escala_axial = escala_torque = 0.0
    escala_momento = 0.0
    for pontual in viga.cargas_pontuais:
        soma_fy += pontual.fy_N
        soma_mz += pontual.fy_N * pontual.x_mm
        escala_forca = max(escala_forca, abs(pontual.fy_N))
    for momento in viga.momentos:
        soma_mz += momento.mz_Nmm
        escala_momento = max(escala_momento, abs(momento.mz_Nmm))
    for distribuida in viga.cargas_distribuidas:
        comprimento = distribuida.x_final_mm - distribuida.x_inicial_mm
        w_i, w_f = distribuida.w_inicial_N_mm, distribuida.w_final
        resultante = (w_i + w_f) * comprimento / 2.0
        # Momento do trapézio de carga em torno de x = 0, escrito sem dividir
        # pela resultante — que pode ser nula numa carga antissimétrica.
        soma_fy += resultante
        soma_mz += resultante * distribuida.x_inicial_mm + comprimento**2 * (w_i + 2.0 * w_f) / 6.0
        escala_forca = max(escala_forca, abs(w_i) * comprimento, abs(w_f) * comprimento)
    for axial in viga.cargas_axiais:
        soma_fx += axial.fx_N
        escala_axial = max(escala_axial, abs(axial.fx_N))
    for axial_distribuida in viga.cargas_axiais_distribuidas:
        comprimento = axial_distribuida.x_final_mm - axial_distribuida.x_inicial_mm
        a_i, a_f = axial_distribuida.a_inicial_N_mm, axial_distribuida.a_final
        soma_fx += (a_i + a_f) * comprimento / 2.0
        escala_axial = max(escala_axial, abs(a_i) * comprimento, abs(a_f) * comprimento)
    for torque in viga.torques:
        soma_mt += torque.t_Nmm
        escala_torque = max(escala_torque, abs(torque.t_Nmm))

    momento_p_delta = 0.0
    if resultado.segunda_ordem:
        # ∫ N dv pelos pontos do diagrama: dentro de cada elemento N̄ é
        # constante e a soma telescopa para N̄ (v_j − v_i), exatamente a
        # parcela que a rigidez geométrica acrescentou às reações.
        pontos = resultado.pontos
        for anterior, atual in zip(pontos, pontos[1:], strict=False):
            momento_p_delta += (
                0.5
                * (anterior.normal_N + atual.normal_N)
                * (atual.deslocamento_mm - anterior.deslocamento_mm)
            )
        soma_mz -= momento_p_delta

    escala_forca = max(escala_forca, escala_axial, 1.0)
    escala_momento = max(escala_momento, escala_forca * comprimento_total, 1.0)
    escala_torque = max(escala_torque, 1.0)
    return {
        "residuo_fy_N": soma_fy,
        "residuo_fx_N": soma_fx,
        "residuo_mz_Nmm": soma_mz,
        "residuo_mt_Nmm": soma_mt,
        "momento_p_delta_Nmm": momento_p_delta,
        "residuo_relativo": max(
            abs(soma_fy) / escala_forca,
            abs(soma_fx) / escala_forca,
            abs(soma_mz) / escala_momento,
            abs(soma_mt) / escala_torque,
        ),
    }
