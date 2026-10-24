"""Malha, matrizes elementares e solução numérica de vigas e eixos."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from core.beam_model import (
    DIVISOES_SEGUNDA_ORDEM,
    ELEMENTOS_MAXIMOS,
    FRACAO_FUSAO_DE_NOS,
    TOLERANCIA_POSICAO_MM,
    CargaAxialDistribuida,
    CargaDistribuida,
    Viga,
)
from core.beam_sections import _finito


def _tolerancia_de_posicao(comprimento: float) -> float:
    """Distância abaixo da qual duas posições viram o mesmo nó.

    Absoluta (1e-6 mm) para absorver arredondamento, e relativa (1e-4 do
    comprimento) para não criar um elemento minúsculo entre duas cargas
    quase coincidentes: a rigidez EI/L³ desse elemento fica bilhões de vezes
    maior que a dos vizinhos, a matriz perde o condicionamento e o solver
    acusava "mecanismo" numa viga perfeitamente estável. Fundir cargas a
    0,6 mm uma da outra numa viga de 6 m muda os braços de alavanca em 1e-4
    — nada, para uma análise de vigas.
    """
    return max(TOLERANCIA_POSICAO_MM, comprimento * FRACAO_FUSAO_DE_NOS)


def _mesmo_ponto(a: float, b: float, tolerancia: float = TOLERANCIA_POSICAO_MM) -> bool:
    return abs(a - b) <= tolerancia


def _inserir(posicoes: list[float], valor: float, tolerancia: float) -> None:
    for existente in posicoes:
        if _mesmo_ponto(existente, valor, tolerancia):
            return
    posicoes.append(valor)


def _validar_posicao(nome: str, x: float, comprimento: float, tolerancia: float) -> float:
    x = _finito(nome, x)
    if x < -tolerancia or x > comprimento + tolerancia:
        raise ValueError(f"{nome} = {x:.4g} mm está fora da viga (0 a {comprimento:.4g} mm).")
    return min(max(x, 0.0), comprimento)


@dataclass(frozen=True, slots=True)
class _Malha:
    """Nós da malha e como ela foi refinada."""

    posicoes: list[float]
    trechos: int
    divisoes: int
    divisoes_pedidas: int
    tolerancia: float

    def no_de(self, x: float) -> int:
        for indice, posicao in enumerate(self.posicoes):
            if _mesmo_ponto(posicao, x, self.tolerancia):
                return indice
        raise ValueError(f"Posição {x:.4g} mm não corresponde a nenhum nó da malha.")

    def ajustar(self, x: float) -> float:
        """Coordenada do nó em que ``x`` cai — o modelo é "encaixado" na malha."""
        return self.posicoes[self.no_de(x)]


def _ajustar_modelo_a_malha(viga: Viga, malha: _Malha) -> Viga:
    """Cópia do modelo com toda posição movida para o nó em que ela caiu.

    Depois da fusão de nós, uma carga declarada a 0,3 mm de um apoio passa
    a agir *no* apoio; ajustar o modelo mantém a conferência de equilíbrio,
    o esquema da página e o registro coerentes com o que foi resolvido.
    """
    comprimento = viga.comprimento_mm
    tolerancia = malha.tolerancia

    def no(nome: str, x: float) -> float:
        return malha.ajustar(_validar_posicao(nome, x, comprimento, tolerancia))

    return replace(
        viga,
        apoios=tuple(replace(a, x_mm=no("posição do apoio", a.x_mm)) for a in viga.apoios),
        rotulas=tuple(replace(r, x_mm=no("posição da rótula", r.x_mm)) for r in viga.rotulas),
        cargas_pontuais=tuple(
            replace(c, x_mm=no("posição da carga pontual", c.x_mm)) for c in viga.cargas_pontuais
        ),
        momentos=tuple(replace(m, x_mm=no("posição do momento", m.x_mm)) for m in viga.momentos),
        cargas_distribuidas=tuple(
            _distribuida_ajustada(
                c,
                no("início da carga distribuída", c.x_inicial_mm),
                no("fim da carga distribuída", c.x_final_mm),
                tolerancia,
            )
            for c in viga.cargas_distribuidas
        ),
        cargas_axiais=tuple(
            replace(c, x_mm=no("posição da carga axial", c.x_mm)) for c in viga.cargas_axiais
        ),
        cargas_axiais_distribuidas=tuple(
            _distribuida_ajustada(
                c,
                no("início da carga axial distribuída", c.x_inicial_mm),
                no("fim da carga axial distribuída", c.x_final_mm),
                tolerancia,
            )
            for c in viga.cargas_axiais_distribuidas
        ),
        torques=tuple(replace(t, x_mm=no("posição do torque", t.x_mm)) for t in viga.torques),
    )


def _distribuida_ajustada(carga: Any, inicio: float, fim: float, tolerancia: float) -> Any:
    """Distribuída com os extremos nos nós; recusa a que caberia num único nó."""
    if fim <= inicio:
        raise ValueError(
            f"A carga distribuída de x = {carga.x_inicial_mm:.4g} mm a "
            f"{carga.x_final_mm:.4g} mm é mais curta que a distância mínima entre "
            f"nós ({tolerancia:.3g} mm, 0,01 % do comprimento). Troque-a por uma "
            "carga pontual com a mesma resultante."
        )
    return replace(carga, x_inicial_mm=inicio, x_final_mm=fim)


def _posicoes_nodais(viga: Viga) -> _Malha:
    comprimento = viga.comprimento_mm
    tolerancia = _tolerancia_de_posicao(comprimento)
    posicoes: list[float] = [0.0, comprimento]

    def inserir(nome: str, x: float) -> None:
        _inserir(posicoes, _validar_posicao(nome, x, comprimento, tolerancia), tolerancia)

    for apoio in viga.apoios:
        inserir("posição do apoio", apoio.x_mm)
    for rotula in viga.rotulas:
        inserir("posição da rótula", rotula.x_mm)
    for pontual in viga.cargas_pontuais:
        inserir("posição da carga pontual", pontual.x_mm)
    for momento in viga.momentos:
        inserir("posição do momento", momento.x_mm)
    for axial in viga.cargas_axiais:
        inserir("posição da carga axial", axial.x_mm)
    for torque in viga.torques:
        inserir("posição do torque", torque.x_mm)
    for distribuida in viga.cargas_distribuidas:
        inserir("início da carga distribuída", distribuida.x_inicial_mm)
        inserir("fim da carga distribuída", distribuida.x_final_mm)
    for axial_distribuida in viga.cargas_axiais_distribuidas:
        inserir("início da carga axial distribuída", axial_distribuida.x_inicial_mm)
        inserir("fim da carga axial distribuída", axial_distribuida.x_final_mm)
    posicoes.sort()

    divisoes = max(1, int(viga.divisoes_por_trecho))
    pedidas = divisoes
    trechos = len(posicoes) - 1
    tem_axial = bool(viga.cargas_axiais or viga.cargas_axiais_distribuidas)
    if viga.considerar_segunda_ordem or tem_axial:
        # A rigidez geométrica converge com o refino: com um elemento por
        # trecho o fator de carga crítica de uma coluna biapoiada sai 21,6%
        # alto (12EI/L² em vez de π²EI/L²) — e alto demais é justamente o
        # lado inseguro. Refinar não altera V, M nem a flecha de primeira
        # ordem, que são exatos em qualquer malha, então o custo é só tempo.
        # Num modelo com centenas de trechos o refino automático se limita
        # ao teto da malha, em vez de recusar a análise; analisar_viga avisa.
        pedidas = max(divisoes, DIVISOES_SEGUNDA_ORDEM)
        automatico = max(1, min(DIVISOES_SEGUNDA_ORDEM, ELEMENTOS_MAXIMOS // max(trechos, 1)))
        divisoes = max(divisoes, automatico)

    # Sem refino, um elemento por trecho: a solução nodal é exata. Com
    # refino, a malha mira um comprimento de elemento uniforme, L/(trechos ×
    # divisões), com pelo menos um elemento por trecho. Dividir cada trecho
    # em n partes iguais — como antes — transformava um trecho curto (uma
    # carga a 20 mm do apoio) em oito lascas minúsculas ao lado de elementos
    # de metros, e o mau condicionamento voltava pela porta dos fundos.
    alvo = comprimento / max(1, trechos * divisoes)
    refinadas: list[float] = []
    n_elementos = 0
    for inicio, fim in zip(posicoes, posicoes[1:], strict=False):
        partes = max(1, round((fim - inicio) / alvo)) if divisoes > 1 else 1
        refinadas.append(inicio)
        refinadas.extend(inicio + (fim - inicio) * indice / partes for indice in range(1, partes))
        n_elementos += partes
    refinadas.append(posicoes[-1])
    if n_elementos > ELEMENTOS_MAXIMOS:
        raise ValueError(
            f"A malha teria {n_elementos} elementos ({trechos} trecho(s) com até "
            f"{divisoes} divisões), acima do máximo de {ELEMENTOS_MAXIMOS}. Reduza "
            "`divisoes`: a solução de primeira ordem é exata em qualquer malha e a "
            "segunda ordem já converge com 8 a 32 divisões por trecho."
        )
    return _Malha(
        posicoes=refinadas,
        trechos=trechos,
        divisoes=divisoes,
        divisoes_pedidas=pedidas,
        tolerancia=tolerancia,
    )


def _carga_no_elemento(
    cargas: Sequence[CargaDistribuida] | Sequence[CargaAxialDistribuida],
    x_i: float,
    x_j: float,
) -> tuple[float, float]:
    """Soma as intensidades das distribuídas nos dois extremos do elemento."""
    meio = 0.5 * (x_i + x_j)
    w_i = w_j = 0.0
    for carga in cargas:
        if (
            carga.x_inicial_mm - TOLERANCIA_POSICAO_MM
            <= meio
            <= carga.x_final_mm + TOLERANCIA_POSICAO_MM
        ):
            w_i += carga.intensidade_em(x_i)
            w_j += carga.intensidade_em(x_j)
    return w_i, w_j


def _rigidez_flexao(ei: float, l: float) -> np.ndarray:
    return (ei / l**3) * np.array(
        [
            [12.0, 6.0 * l, -12.0, 6.0 * l],
            [6.0 * l, 4.0 * l**2, -6.0 * l, 2.0 * l**2],
            [-12.0, -6.0 * l, 12.0, -6.0 * l],
            [6.0 * l, 2.0 * l**2, -6.0 * l, 4.0 * l**2],
        ],
        dtype=float,
    )


def _rigidez_geometrica(normal: float, l: float) -> np.ndarray:
    """Rigidez geométrica consistente de um elemento sob esforço normal.

    ``normal`` é positivo em tração: tração enrijece a barra à flexão e
    compressão a amolece. Somada à rigidez elástica, é o que produz o efeito
    de segunda ordem (P–Δ e P–δ) numa análise ainda linear — a flecha cresce
    porque a compressão reduz a rigidez, não porque a geometria foi
    atualizada.
    """
    return (normal / (30.0 * l)) * np.array(
        [
            [36.0, 3.0 * l, -36.0, 3.0 * l],
            [3.0 * l, 4.0 * l**2, -3.0 * l, -(l**2)],
            [-36.0, -3.0 * l, 36.0, -3.0 * l],
            [3.0 * l, -(l**2), -3.0 * l, 4.0 * l**2],
        ],
        dtype=float,
    )


def _cargas_equivalentes_flexao(w_i: float, w_j: float, l: float) -> np.ndarray:
    """Vetor de engastamento perfeito de uma distribuída linear (positiva ↑)."""
    return np.array(
        [
            l * (7.0 * w_i + 3.0 * w_j) / 20.0,
            l**2 * (3.0 * w_i + 2.0 * w_j) / 60.0,
            l * (3.0 * w_i + 7.0 * w_j) / 20.0,
            -(l**2) * (2.0 * w_i + 3.0 * w_j) / 60.0,
        ],
        dtype=float,
    )


def _cargas_equivalentes_axial(a_i: float, a_j: float, l: float) -> np.ndarray:
    return np.array(
        [l * (2.0 * a_i + a_j) / 6.0, l * (a_i + 2.0 * a_j) / 6.0],
        dtype=float,
    )


@dataclass(slots=True)
class _Elemento:
    indice: int
    no_i: int
    no_j: int
    x_i: float
    x_j: float
    comprimento: float
    w_i: float
    w_j: float
    a_i: float
    a_j: float
    dofs_flexao: tuple[int, int, int, int] = (0, 0, 0, 0)
    dofs_axial: tuple[int, int] = (0, 0)
    dofs_torcao: tuple[int, int] = (0, 0)
    # ``esforcos_flexao`` vem só da rigidez elástica (K_e·u − F_eq): são os
    # esforços de extremidade que, integrados com a teoria de primeira
    # ordem, reproduzem exatamente v_j e θ_j — por isso geram a linha
    # elástica. ``esforcos_equilibrio`` inclui a parcela geométrica
    # (K_g·u) e é o conjunto que está em equilíbrio com os nós na
    # configuração deformada — por isso gera V(x) e M(x). Sem segunda
    # ordem os dois são o mesmo vetor.
    esforcos_flexao: np.ndarray = field(default_factory=lambda: np.zeros(4))
    esforcos_equilibrio: np.ndarray = field(default_factory=lambda: np.zeros(4))
    normal_geometrico: float = 0.0
    esforco_axial_i: float = 0.0
    esforco_torcao_i: float = 0.0
    v_i: float = 0.0
    theta_i: float = 0.0
    u_i: float = 0.0
    phi_i: float = 0.0


def _normal_medio(elemento: _Elemento) -> float:
    """Esforço normal médio do elemento (positivo em tração)."""
    n_inicial = -elemento.esforco_axial_i
    n_final = n_inicial - (
        elemento.a_i * elemento.comprimento
        + (elemento.a_j - elemento.a_i) * elemento.comprimento / 2.0
    )
    return 0.5 * (n_inicial + n_final)


def _escala_de_jacobi(matriz: np.ndarray) -> np.ndarray:
    """``1/√|diagonal|`` — leva a matriz a diagonal unitária.

    Translação (N/mm) e rotação (N·mm/rad) diferem por um fator L² só por
    causa das unidades; sem o escalonamento, o teste de posto e o solver
    enxergam um mau condicionamento que não é da estrutura. O escalonamento
    simétrico ``D K D`` preserva a simetria e os autovalores generalizados.
    """
    diagonal = np.abs(np.diag(matriz))
    return 1.0 / np.sqrt(np.where(diagonal > 0, diagonal, 1.0))


def _fator_carga_critica(
    k_elastica: np.ndarray, k_geometrica: np.ndarray, restritos: set[int]
) -> float | None:
    """Multiplicador das cargas axiais que leva o modelo à flambagem.

    Resolve ``K_e φ = λ (−K_g) φ`` nos graus livres. Um fator de 3,2 quer
    dizer que as cargas **axiais** poderiam ser multiplicadas por 3,2 antes
    da instabilidade elástica. Devolve ``None`` quando não há compressão —
    aí não existe carga crítica a reportar.

    O problema é reduzido à forma simétrica ``L⁻¹(−K_g)L⁻ᵀ ψ = μ ψ`` pela
    fatoração de Cholesky ``K_e = L Lᵀ`` (``λ = 1/μ``): os autovalores saem
    reais por construção, sem depender de um filtro de parte imaginária
    que, na forma não simétrica ``K_e⁻¹(−K_g)``, descartava modos por ruído.
    """
    if not np.any(k_geometrica):
        return None
    total = k_elastica.shape[0]
    livres = [i for i in range(total) if i not in restritos]
    if not livres:
        return None
    kff = k_elastica[np.ix_(livres, livres)]
    kgff = k_geometrica[np.ix_(livres, livres)]
    escala = _escala_de_jacobi(kff)
    k_escalada = escala[:, None] * kff * escala[None, :]
    kg_escalada = escala[:, None] * kgff * escala[None, :]
    try:
        cholesky = np.linalg.cholesky(k_escalada)
        # C = L⁻¹ (−K_g) L⁻ᵀ, montada em dois sistemas triangulares.
        parcial = np.linalg.solve(cholesky, -kg_escalada)
        simetrica = np.linalg.solve(cholesky, parcial.T)
    except np.linalg.LinAlgError:
        # K_e não é definida positiva: o modelo é um mecanismo, e o erro
        # explicativo sai do solver de flexão logo em seguida.
        return None
    simetrica = 0.5 * (simetrica + simetrica.T)
    autovalores = np.linalg.eigvalsh(simetrica)
    maior = float(autovalores[-1])
    limiar = 1e-12 * max(1.0, float(np.abs(autovalores).max()))
    if maior <= limiar:
        return None
    return 1.0 / maior


def _resolver_sistema(
    k: np.ndarray,
    f: np.ndarray,
    restritos: set[int],
    contexto: str,
) -> tuple[np.ndarray, np.ndarray]:
    total = k.shape[0]
    livres = [i for i in range(total) if i not in restritos]
    deslocamentos = np.zeros(total)
    if livres:
        kff = k[np.ix_(livres, livres)]
        escala = _escala_de_jacobi(kff)
        k_escalada = escala[:, None] * kff * escala[None, :]
        # Na matriz escalonada um mecanismo aparece como autovalor na casa
        # de 1e-17 do maior (ruído do épsilon da máquina), enquanto o modo
        # mais flexível de uma barra estável decai com n⁴ e ainda está em
        # 1e-13 com 2 000 elementos num vão. O corte em 1e-14 separa os dois
        # com folga de três ordens de grandeza para cada lado. A matriz é
        # simétrica, então os autovalores (em módulo) são os valores
        # singulares — e ``eigvalsh`` custa um quarto do SVD.
        k_escalada = 0.5 * (k_escalada + k_escalada.T)
        autovalores = np.abs(np.linalg.eigvalsh(k_escalada))
        posto = int(np.count_nonzero(autovalores > 1e-14 * float(autovalores.max())))
        if posto < len(livres):
            mecanismos = len(livres) - posto
            raise ValueError(
                f"O modelo é instável em {contexto}: há {mecanismos} movimento(s) de corpo "
                "rígido ou mecanismo(s) sem restrição. Revise os apoios (e as rótulas "
                "internas, que não podem deixar um trecho isolado sem apoio)."
            )
        try:
            # (D K D)(D⁻¹u) = D f  →  u = D · solve(D K D, D f)
            deslocamentos[livres] = escala * np.linalg.solve(k_escalada, escala * f[livres])
        except np.linalg.LinAlgError as erro:  # pragma: no cover - proteção extra
            raise ValueError(
                f"Não foi possível resolver o sistema de {contexto}: matriz singular."
            ) from erro
    reacoes = k @ deslocamentos - f
    return deslocamentos, reacoes
