"""Solver matricial linear para treliças e pórticos planos.

Unidades internas: N, mm, MPa e N·mm.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class NoTrelica:
    id: int
    x_mm: float
    y_mm: float
    restringe_x: bool = False
    restringe_y: bool = False
    fx_N: float = 0.0
    fy_N: float = 0.0


@dataclass(frozen=True)
class ElementoTrelica:
    id: int
    no_i: int
    no_j: int
    area_mm2: float
    modulo_elasticidade_MPa: float


@dataclass(frozen=True)
class NoPortico:
    id: int
    x_mm: float
    y_mm: float
    restringe_x: bool = False
    restringe_y: bool = False
    restringe_rotacao: bool = False
    fx_N: float = 0.0
    fy_N: float = 0.0
    mz_Nmm: float = 0.0


@dataclass(frozen=True)
class ElementoPortico:
    id: int
    no_i: int
    no_j: int
    area_mm2: float
    inercia_mm4: float
    modulo_elasticidade_MPa: float
    carga_distribuida_local_y_N_mm: float = 0.0


@dataclass(frozen=True)
class ResultadoEstrutural:
    deslocamentos_nodais: tuple[dict, ...]
    reacoes_nodais: tuple[dict, ...]
    esforcos_elementos: tuple[dict, ...]
    deslocamento_maximo_mm: float
    # -- só no pórtico -------------------------------------------------------
    segunda_ordem: bool = False
    # Multiplicador de TODAS as cargas que leva o pórtico à flambagem
    # elástica global (K_e·φ = λ·(−K_g)·φ). None sem compressão.
    fator_carga_critica: float | None = None
    # Maior deslocamento horizontal em 1ª ordem e (se pedida) em 2ª ordem;
    # a razão Δ2/Δ1 classifica a deslocabilidade (NBR 8800, 4.9.4.1).
    deslocamento_horizontal_1a_ordem_mm: float = 0.0
    deslocamento_horizontal_2a_ordem_mm: float | None = None
    razao_delta2_delta1: float | None = None
    classificacao_deslocabilidade: str = ""
    coeficiente_b2: float | None = None
    carga_nocional_total_N: float = 0.0
    carga_gravitacional_total_N: float = 0.0
    carga_horizontal_total_N: float = 0.0
    altura_referencia_mm: float = 0.0
    reducao_rigidez: float = 1.0
    iteracoes: int = 0
    avisos: tuple[str, ...] = ()


# Limites da classificação quanto à sensibilidade a deslocamentos laterais
# (NBR 8800, 4.9.4.1): razão entre o deslocamento lateral de 2ª e de 1ª ordem.
LIMITE_PEQUENA_DESLOCABILIDADE = 1.10
LIMITE_MEDIA_DESLOCABILIDADE = 1.40
# Imperfeições geométricas iniciais como carga nocional horizontal: 0,3 % das
# cargas gravitacionais de cálculo de cada pavimento (4.9.7.1.1).
CARGA_NOCIONAL_PADRAO = 0.003
# Redução de rigidez na análise de estruturas de média deslocabilidade (4.9.7.1.2).
REDUCAO_RIGIDEZ_MEDIA_DESLOCABILIDADE = 0.80
# Rs do coeficiente B2 (4.9.4.6): 0,85 quando a rigidez lateral vem de pórticos.
RS_PORTICO = 0.85


def classificar_deslocabilidade(razao: float) -> str:
    if razao <= LIMITE_PEQUENA_DESLOCABILIDADE:
        return "pequena deslocabilidade"
    if razao <= LIMITE_MEDIA_DESLOCABILIDADE:
        return "média deslocabilidade"
    return "grande deslocabilidade"


def _rigidez_geometrica_local(normal: float, l: float) -> np.ndarray:
    """K_g consistente do elemento de pórtico (6×6, só os graus de flexão).

    ``normal`` positivo em tração. É a mesma matriz do módulo de vigas; a
    compressão amolece a barra à flexão e é isso que produz o P–Δ.
    """
    kg = np.zeros((6, 6))
    base = (normal / (30.0 * l)) * np.array(
        [
            [36.0, 3.0 * l, -36.0, 3.0 * l],
            [3.0 * l, 4.0 * l**2, -3.0 * l, -(l**2)],
            [-36.0, -3.0 * l, 36.0, -3.0 * l],
            [3.0 * l, -(l**2), -3.0 * l, 4.0 * l**2],
        ]
    )
    indices = [1, 2, 4, 5]
    kg[np.ix_(indices, indices)] = base
    return kg


def _fator_carga_critica(
    k_elastica: np.ndarray, k_geometrica: np.ndarray, restringidos: list[int]
) -> float | None:
    """Menor λ de ``K_e·φ = λ·(−K_g)·φ`` nos graus livres, pela forma simétrica."""
    if not np.any(k_geometrica):
        return None
    total = k_elastica.shape[0]
    livres = [i for i in range(total) if i not in set(restringidos)]
    if not livres:
        return None
    kff = k_elastica[np.ix_(livres, livres)]
    kgff = k_geometrica[np.ix_(livres, livres)]
    diagonal = np.abs(np.diag(kff))
    escala = 1.0 / np.sqrt(np.where(diagonal > 0, diagonal, 1.0))
    k_escalada = escala[:, None] * kff * escala[None, :]
    kg_escalada = escala[:, None] * kgff * escala[None, :]
    try:
        cholesky = np.linalg.cholesky(k_escalada)
        parcial = np.linalg.solve(cholesky, -kg_escalada)
        simetrica = np.linalg.solve(cholesky, parcial.T)
    except np.linalg.LinAlgError:
        return None
    simetrica = 0.5 * (simetrica + simetrica.T)
    autovalores = np.linalg.eigvalsh(simetrica)
    maior = float(autovalores[-1])
    if maior <= 1e-12 * max(1.0, float(np.abs(autovalores).max())):
        return None
    return 1.0 / maior


def _finito(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor):
        raise ValueError(f"{nome} deve ser finito.")
    return valor


def _positivo(nome: str, valor: float) -> float:
    valor = _finito(nome, valor)
    if valor <= 0:
        raise ValueError(f"{nome} deve ser maior que zero.")
    return valor


def _validar_nos(nos: Iterable, graus_por_no: int) -> tuple[list, dict[int, int]]:
    lista = list(nos)
    if not lista:
        raise ValueError("Informe pelo menos um nó.")
    ids = [int(no.id) for no in lista]
    if len(set(ids)) != len(ids):
        raise ValueError("Os IDs dos nós devem ser únicos.")
    for no in lista:
        _finito("x_mm", no.x_mm)
        _finito("y_mm", no.y_mm)
    mapa = {identificador: indice for indice, identificador in enumerate(ids)}
    if len(lista) * graus_por_no == 0:
        raise ValueError("Modelo vazio.")
    return lista, mapa


def _resolver(
    rigidez: np.ndarray,
    cargas: np.ndarray,
    restringidos: list[int],
) -> tuple[np.ndarray, np.ndarray]:
    total = rigidez.shape[0]
    livres = [i for i in range(total) if i not in set(restringidos)]
    if not livres:
        raise ValueError("Todos os graus de liberdade estão restringidos.")
    kff = rigidez[np.ix_(livres, livres)]
    ff = cargas[livres]
    try:
        deslocamentos_livres = np.linalg.solve(kff, ff)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "A matriz de rigidez é singular. Verifique apoios, conectividade e mecanismos internos."
        ) from exc
    deslocamentos = np.zeros(total)
    deslocamentos[livres] = deslocamentos_livres
    reacoes = rigidez @ deslocamentos - cargas
    return deslocamentos, reacoes


def analisar_trelica(
    nos: Iterable[NoTrelica],
    elementos: Iterable[ElementoTrelica],
) -> ResultadoEstrutural:
    lista_nos, mapa = _validar_nos(nos, 2)
    lista_elementos = list(elementos)
    if not lista_elementos:
        raise ValueError("Informe pelo menos um elemento.")
    ndof = 2 * len(lista_nos)
    k_global = np.zeros((ndof, ndof))
    f_global = np.zeros(ndof)
    restringidos: list[int] = []

    for indice, no in enumerate(lista_nos):
        f_global[2 * indice] = _finito("fx_N", no.fx_N)
        f_global[2 * indice + 1] = _finito("fy_N", no.fy_N)
        if no.restringe_x:
            restringidos.append(2 * indice)
        if no.restringe_y:
            restringidos.append(2 * indice + 1)

    dados_elementos = []
    ids_elementos = set()
    for elemento in lista_elementos:
        if elemento.id in ids_elementos:
            raise ValueError("Os IDs dos elementos devem ser únicos.")
        ids_elementos.add(elemento.id)
        if elemento.no_i not in mapa or elemento.no_j not in mapa:
            raise ValueError(f"Elemento {elemento.id} referencia nó inexistente.")
        i, j = mapa[elemento.no_i], mapa[elemento.no_j]
        ni, nj = lista_nos[i], lista_nos[j]
        dx, dy = nj.x_mm - ni.x_mm, nj.y_mm - ni.y_mm
        l = math.hypot(dx, dy)
        if l <= 0:
            raise ValueError(f"Elemento {elemento.id} possui comprimento zero.")
        c, s = dx / l, dy / l
        a = _positivo("area_mm2", elemento.area_mm2)
        e = _positivo("modulo_elasticidade_MPa", elemento.modulo_elasticidade_MPa)
        k = (
            a
            * e
            / l
            * np.array(
                [
                    [c * c, c * s, -c * c, -c * s],
                    [c * s, s * s, -c * s, -s * s],
                    [-c * c, -c * s, c * c, c * s],
                    [-c * s, -s * s, c * s, s * s],
                ]
            )
        )
        dofs = [2 * i, 2 * i + 1, 2 * j, 2 * j + 1]
        k_global[np.ix_(dofs, dofs)] += k
        dados_elementos.append((elemento, dofs, l, c, s, a, e))

    u, reacoes = _resolver(k_global, f_global, restringidos)
    esforcos = []
    for elemento, dofs, l, c, s, a, e in dados_elementos:
        ue = u[dofs]
        deformacao = np.dot(np.array([-c, -s, c, s]), ue) / l
        normal = a * e * deformacao
        esforcos.append(
            {
                "elemento": elemento.id,
                "no_i": elemento.no_i,
                "no_j": elemento.no_j,
                "normal_N": normal,
                "tensao_MPa": normal / a,
                "estado": "Tração" if normal >= 0 else "Compressão",
            }
        )

    deslocamentos_nos = []
    reacoes_nos = []
    for indice, no in enumerate(lista_nos):
        ux, uy = u[2 * indice : 2 * indice + 2]
        rx, ry = reacoes[2 * indice : 2 * indice + 2]
        deslocamentos_nos.append({"no": no.id, "ux_mm": ux, "uy_mm": uy})
        reacoes_nos.append({"no": no.id, "rx_N": rx, "ry_N": ry})
    maximo = max(math.hypot(item["ux_mm"], item["uy_mm"]) for item in deslocamentos_nos)
    return ResultadoEstrutural(
        deslocamentos_nodais=tuple(deslocamentos_nos),
        reacoes_nodais=tuple(reacoes_nos),
        esforcos_elementos=tuple(esforcos),
        deslocamento_maximo_mm=maximo,
    )


def _matriz_portico_local(a: float, e: float, i: float, l: float) -> np.ndarray:
    ea_l = e * a / l
    ei = e * i
    return np.array(
        [
            [ea_l, 0, 0, -ea_l, 0, 0],
            [0, 12 * ei / l**3, 6 * ei / l**2, 0, -12 * ei / l**3, 6 * ei / l**2],
            [0, 6 * ei / l**2, 4 * ei / l, 0, -6 * ei / l**2, 2 * ei / l],
            [-ea_l, 0, 0, ea_l, 0, 0],
            [0, -12 * ei / l**3, -6 * ei / l**2, 0, 12 * ei / l**3, -6 * ei / l**2],
            [0, 6 * ei / l**2, 2 * ei / l, 0, -6 * ei / l**2, 4 * ei / l],
        ],
        dtype=float,
    )


def _transformacao_portico(c: float, s: float) -> np.ndarray:
    return np.array(
        [
            [c, s, 0, 0, 0, 0],
            [-s, c, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0],
            [0, 0, 0, c, s, 0],
            [0, 0, 0, -s, c, 0],
            [0, 0, 0, 0, 0, 1],
        ],
        dtype=float,
    )


def analisar_portico(
    nos: Iterable[NoPortico],
    elementos: Iterable[ElementoPortico],
    *,
    segunda_ordem: bool = False,
    carga_nocional: float = 0.0,
    sentido_nocional: float = 1.0,
    reducao_rigidez: float = 1.0,
    altura_referencia_mm: float | None = None,
    iteracoes_maximas: int = 20,
    tolerancia: float = 1e-8,
) -> ResultadoEstrutural:
    """Pórtico plano por rigidez direta, com efeitos de 2ª ordem opcionais.

    * ``carga_nocional``: fração das cargas gravitacionais de cálculo aplicada
      como força horizontal em cada nó carregado (NBR 8800, 4.9.7.1.1: 0,3 %),
      no sentido ``sentido_nocional`` (+1 = +x). Representa as imperfeições
      geométricas iniciais e entra também na análise de 1ª ordem.
    * ``segunda_ordem``: rigidez geométrica consistente a partir do esforço
      normal de cada barra, iterada até o esforço normal convergir (P–Δ e
      P–δ na análise elástica). O resultado traz o fator de carga crítica
      global e a razão Δ2/Δ1 que classifica a deslocabilidade (4.9.4.1).
    * ``reducao_rigidez``: multiplica E·A e E·I (0,8 para estruturas de
      média deslocabilidade, 4.9.7.1.2).
    * ``altura_referencia_mm``: altura do pavimento para o coeficiente B2 e
      para o critério H/…; por padrão, a altura total dos nós.
    """
    lista_nos, mapa = _validar_nos(nos, 3)
    lista_elementos = list(elementos)
    if not lista_elementos:
        raise ValueError("Informe pelo menos um elemento.")
    nocional = float(carga_nocional)
    if not 0.0 <= nocional < 1.0:
        raise ValueError("carga_nocional deve ser uma fração em [0, 1).")
    reducao = float(reducao_rigidez)
    if not 0.0 < reducao <= 1.0:
        raise ValueError("reducao_rigidez deve estar em (0, 1].")
    sentido = 1.0 if float(sentido_nocional) >= 0 else -1.0
    ndof = 3 * len(lista_nos)
    k_global = np.zeros((ndof, ndof))
    f_global = np.zeros(ndof)
    restringidos: list[int] = []

    for indice, no in enumerate(lista_nos):
        f_global[3 * indice : 3 * indice + 3] = (
            _finito("fx_N", no.fx_N),
            _finito("fy_N", no.fy_N),
            _finito("mz_Nmm", no.mz_Nmm),
        )
        if no.restringe_x:
            restringidos.append(3 * indice)
        if no.restringe_y:
            restringidos.append(3 * indice + 1)
        if no.restringe_rotacao:
            restringidos.append(3 * indice + 2)

    dados_elementos = []
    ids_elementos = set()
    for elemento in lista_elementos:
        if elemento.id in ids_elementos:
            raise ValueError("Os IDs dos elementos devem ser únicos.")
        ids_elementos.add(elemento.id)
        if elemento.no_i not in mapa or elemento.no_j not in mapa:
            raise ValueError(f"Elemento {elemento.id} referencia nó inexistente.")
        ni_idx, nj_idx = mapa[elemento.no_i], mapa[elemento.no_j]
        ni, nj = lista_nos[ni_idx], lista_nos[nj_idx]
        dx, dy = nj.x_mm - ni.x_mm, nj.y_mm - ni.y_mm
        l = math.hypot(dx, dy)
        if l <= 0:
            raise ValueError(f"Elemento {elemento.id} possui comprimento zero.")
        c, s = dx / l, dy / l
        a = _positivo("area_mm2", elemento.area_mm2)
        inercia = _positivo("inercia_mm4", elemento.inercia_mm4)
        e = _positivo("modulo_elasticidade_MPa", elemento.modulo_elasticidade_MPa) * reducao
        q = _finito(
            "carga_distribuida_local_y_N_mm",
            elemento.carga_distribuida_local_y_N_mm,
        )
        kl = _matriz_portico_local(a, e, inercia, l)
        t = _transformacao_portico(c, s)
        kg = t.T @ kl @ t
        fl = np.array([0, q * l / 2, q * l**2 / 12, 0, q * l / 2, -q * l**2 / 12])
        fg = t.T @ fl
        dofs = [
            3 * ni_idx,
            3 * ni_idx + 1,
            3 * ni_idx + 2,
            3 * nj_idx,
            3 * nj_idx + 1,
            3 * nj_idx + 2,
        ]
        k_global[np.ix_(dofs, dofs)] += kg
        f_global[dofs] += fg
        dados_elementos.append((elemento, dofs, l, t, kl, fl))

    # -- carga nocional (imperfeições geométricas iniciais) ------------------
    # Proporcional à carga gravitacional que chega a cada nó — cargas nodais
    # e equivalentes das distribuídas — e só nos nós não travados em x, onde
    # ela produz efeito; num apoio ela iria direto para a reação.
    avisos: list[str] = []
    gravitacional_total = float(
        sum(-f_global[3 * i + 1] for i in range(len(lista_nos)) if f_global[3 * i + 1] < 0)
    )
    nocional_total = 0.0
    if nocional > 0:
        for indice, no in enumerate(lista_nos):
            vertical = f_global[3 * indice + 1]
            if vertical < 0 and not no.restringe_x:
                forca = nocional * (-vertical)
                f_global[3 * indice] += sentido * forca
                nocional_total += forca
        if nocional_total == 0.0:
            avisos.append(
                "Carga nocional pedida, mas nenhum nó livre em x recebe carga gravitacional: "
                "nada foi acrescentado."
            )
    horizontal_total = float(sum(f_global[3 * i] for i in range(len(lista_nos))))

    # -- primeira ordem --------------------------------------------------------
    u1, reacoes1 = _resolver(k_global, f_global, restringidos)

    def normais(u: np.ndarray) -> list[float]:
        valores = []
        for _, dofs, _, t, kl, fl in dados_elementos:
            fim = kl @ (t @ u[dofs]) - fl
            valores.append(float(fim[3]))  # esforço normal (tração positiva) no nó j
        return valores

    def montar_geometrica(normais_elementos: list[float]) -> np.ndarray:
        kgeo = np.zeros((ndof, ndof))
        for (_, dofs, l, t, _, _), normal in zip(dados_elementos, normais_elementos, strict=True):
            if normal != 0.0:
                kgeo[np.ix_(dofs, dofs)] += t.T @ _rigidez_geometrica_local(normal, l) @ t
        return kgeo

    normais_1 = normais(u1)
    k_geometrica = montar_geometrica(normais_1)
    fator_critico = _fator_carga_critica(k_global, k_geometrica, restringidos)

    def maior_horizontal(u: np.ndarray) -> float:
        return float(max(abs(u[3 * i]) for i in range(len(lista_nos))))

    delta1 = maior_horizontal(u1)
    u, reacoes = u1, reacoes1
    iteracoes = 0
    delta2: float | None = None
    razao: float | None = None
    if segunda_ordem:
        if fator_critico is not None and fator_critico <= 1.0:
            raise ValueError(
                "As cargas ultrapassam a carga crítica de flambagem elástica global do "
                f"pórtico (fator de carga crítica = {fator_critico:.3f}): não há equilíbrio "
                "de segunda ordem. Reduza as cargas ou enrijeça a estrutura."
            )
        normais_atuais = normais_1
        for passo in range(1, iteracoes_maximas + 1):
            iteracoes = passo
            kg_final = montar_geometrica(normais_atuais)
            u_novo, reacoes = _resolver(k_global + kg_final, f_global, restringidos)
            normais_novos = normais(u_novo)
            convergiu = np.linalg.norm(u_novo - u) <= tolerancia * max(
                1.0, float(np.linalg.norm(u_novo))
            )
            u = u_novo
            normais_atuais = normais_novos
            if convergiu:
                break
        else:
            avisos.append(
                f"A iteração de segunda ordem não convergiu em {iteracoes_maximas} passos; "
                "o resultado usa o último esforço normal calculado."
            )
        delta2 = maior_horizontal(u)
        razao = delta2 / delta1 if delta1 > 0 else 1.0

    esforcos = []
    for (elemento, dofs, l, t, kl, fl), normal in zip(dados_elementos, normais(u), strict=True):
        ul = t @ u[dofs]
        rigidez = kl + (_rigidez_geometrica_local(normal, l) if segunda_ordem else 0.0)
        fim = rigidez @ ul - fl
        esforcos.append(
            {
                "elemento": elemento.id,
                "no_i": elemento.no_i,
                "no_j": elemento.no_j,
                "Ni_N": fim[0],
                "Vi_N": fim[1],
                "Mi_Nmm": fim[2],
                "Nj_N": fim[3],
                "Vj_N": fim[4],
                "Mj_Nmm": fim[5],
            }
        )

    deslocamentos_nos = []
    reacoes_nos = []
    for indice, no in enumerate(lista_nos):
        ux, uy, rz = u[3 * indice : 3 * indice + 3]
        rx, ry, mz = reacoes[3 * indice : 3 * indice + 3]
        deslocamentos_nos.append({"no": no.id, "ux_mm": ux, "uy_mm": uy, "rz_rad": rz})
        reacoes_nos.append({"no": no.id, "rx_N": rx, "ry_N": ry, "mz_Nmm": mz})
    maximo = max(math.hypot(item["ux_mm"], item["uy_mm"]) for item in deslocamentos_nos)

    # -- deslocabilidade e B2 ---------------------------------------------------
    alturas = [no.y_mm for no in lista_nos]
    altura = (
        _positivo("altura_referencia_mm", altura_referencia_mm)
        if altura_referencia_mm
        else max(alturas) - min(alturas)
    )
    classificacao = ""
    if razao is not None:
        classificacao = classificar_deslocabilidade(razao)
    elif fator_critico is not None and fator_critico > 1.0:
        # Sem a análise de 2ª ordem, a razão é estimada pela amplificação
        # elástica 1/(1 − 1/λ): é o que o B2 aproxima.
        classificacao = (
            classificar_deslocabilidade(1.0 / (1.0 - 1.0 / fator_critico)) + " (estimada)"
        )
    coeficiente_b2: float | None = None
    if altura > 0 and horizontal_total != 0.0 and gravitacional_total > 0 and delta1 > 0:
        # 4.9.4.6: B2 = 1 / [1 − (1/Rs)·(Δh/h)·(ΣN_Sd/ΣH_Sd)], com Rs = 0,85 em pórticos.
        denominador = 1.0 - (1.0 / RS_PORTICO) * (delta1 / altura) * (
            gravitacional_total / abs(horizontal_total)
        )
        coeficiente_b2 = 1.0 / denominador if denominador > 0 else math.inf
    if fator_critico is not None and fator_critico <= 1.0 and not segunda_ordem:
        avisos.append(
            f"Fator de carga crítica global = {fator_critico:.3f} ≤ 1: as cargas já "
            "ultrapassam a carga crítica de flambagem elástica do pórtico; os esforços "
            "de primeira ordem não representam a estrutura."
        )
    elif fator_critico is not None and fator_critico < 10.0 and not segunda_ordem:
        avisos.append(
            f"Fator de carga crítica global = {fator_critico:.2f}: os efeitos de segunda "
            "ordem são relevantes; ative a análise de segunda ordem (P–Δ)."
        )
    if classificacao.startswith("média") and reducao > REDUCAO_RIGIDEZ_MEDIA_DESLOCABILIDADE + 1e-9:
        avisos.append(
            "Estrutura de média deslocabilidade: a NBR 8800 (4.9.7.1.2) pede a análise de "
            "segunda ordem com as rigidezes reduzidas a 80 % — refaça com reducao_rigidez = 0,8."
        )
    if classificacao.startswith("grande"):
        avisos.append(
            "Estrutura de grande deslocabilidade (Δ2/Δ1 > 1,4): o método da amplificação "
            "não se aplica; a NBR 8800 exige análise rigorosa de segunda ordem com "
            "imperfeições (4.9.7.2) ou o enrijecimento da estrutura."
        )
    return ResultadoEstrutural(
        deslocamentos_nodais=tuple(deslocamentos_nos),
        reacoes_nodais=tuple(reacoes_nos),
        esforcos_elementos=tuple(esforcos),
        deslocamento_maximo_mm=maximo,
        segunda_ordem=segunda_ordem,
        fator_carga_critica=fator_critico,
        deslocamento_horizontal_1a_ordem_mm=delta1,
        deslocamento_horizontal_2a_ordem_mm=delta2,
        razao_delta2_delta1=razao,
        classificacao_deslocabilidade=classificacao,
        coeficiente_b2=coeficiente_b2,
        carga_nocional_total_N=nocional_total,
        carga_gravitacional_total_N=gravitacional_total,
        carga_horizontal_total_N=horizontal_total,
        altura_referencia_mm=altura,
        reducao_rigidez=reducao,
        iteracoes=iteracoes,
        avisos=tuple(avisos),
    )


def verificar_deslocamento_horizontal(
    resultado: ResultadoEstrutural,
    *,
    altura_mm: float | None = None,
    divisor: float = 400.0,
) -> dict[str, float | bool | str]:
    """Deslocamento horizontal do topo contra ``H/divisor`` (Anexo C da NBR 8800).

    Usa o deslocamento de segunda ordem quando ele existe. ``H/400`` é o
    limite usual para colunas de plataformas e edifícios industriais sob
    vento; o critério do projeto prevalece.
    """
    altura = _positivo("altura_mm", altura_mm) if altura_mm else resultado.altura_referencia_mm
    if altura <= 0:
        raise ValueError("Informe a altura de referência da estrutura.")
    divisor = _positivo("divisor", divisor)
    deslocamento = (
        resultado.deslocamento_horizontal_2a_ordem_mm
        if resultado.deslocamento_horizontal_2a_ordem_mm is not None
        else resultado.deslocamento_horizontal_1a_ordem_mm
    )
    limite = altura / divisor
    return {
        "deslocamento_mm": deslocamento,
        "limite_mm": limite,
        "altura_mm": altura,
        "criterio": f"H/{divisor:.0f}",
        "utilizacao": deslocamento / limite if limite > 0 else math.inf,
        "atende": deslocamento <= limite,
        "ordem": "2ª ordem"
        if resultado.deslocamento_horizontal_2a_ordem_mm is not None
        else "1ª ordem",
    }
