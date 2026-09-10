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
            "A matriz de rigidez é singular. Verifique apoios, conectividade "
            "e mecanismos internos."
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
        k = a * e / l * np.array(
            [
                [c * c, c * s, -c * c, -c * s],
                [c * s, s * s, -c * s, -s * s],
                [-c * c, -c * s, c * c, c * s],
                [-c * s, -s * s, c * s, s * s],
            ]
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
        deslocamentos_nos.append(
            {"no": no.id, "ux_mm": ux, "uy_mm": uy}
        )
        reacoes_nos.append(
            {"no": no.id, "rx_N": rx, "ry_N": ry}
        )
    maximo = max(
        math.hypot(item["ux_mm"], item["uy_mm"])
        for item in deslocamentos_nos
    )
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
) -> ResultadoEstrutural:
    lista_nos, mapa = _validar_nos(nos, 3)
    lista_elementos = list(elementos)
    if not lista_elementos:
        raise ValueError("Informe pelo menos um elemento.")
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
        e = _positivo("modulo_elasticidade_MPa", elemento.modulo_elasticidade_MPa)
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

    u, reacoes = _resolver(k_global, f_global, restringidos)
    esforcos = []
    for elemento, dofs, _, t, kl, fl in dados_elementos:
        ul = t @ u[dofs]
        fim = kl @ ul - fl
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
        deslocamentos_nos.append(
            {"no": no.id, "ux_mm": ux, "uy_mm": uy, "rz_rad": rz}
        )
        reacoes_nos.append(
            {"no": no.id, "rx_N": rx, "ry_N": ry, "mz_Nmm": mz}
        )
    maximo = max(
        math.hypot(item["ux_mm"], item["uy_mm"])
        for item in deslocamentos_nos
    )
    return ResultadoEstrutural(
        deslocamentos_nodais=tuple(deslocamentos_nos),
        reacoes_nodais=tuple(reacoes_nos),
        esforcos_elementos=tuple(esforcos),
        deslocamento_maximo_mm=maximo,
    )
