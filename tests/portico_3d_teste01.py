"""O teste01 do usuário resolvido como pórtico espacial, com os arquivos que o SolidWorks e a macro
gravam — para os testes de ponta a ponta do núcleo dos Esforços do modelo.

A plataforma: 1500 × 1000 mm, contorno de U 8" × 17,1 no nível Y = 0, quatro pilares W 150 × 13,0
de 2 m com os pés engastados em Y = −2 m (Y para cima, como no SolidWorks). Cada barra é dividida
em elementos (a malha de vigas do Simulation) e resolvida por rigidez direta (12 graus de
liberdade por elemento). Os casos:

* PP: o peso das barras com g = 10,5 m/s² (9,81 × 1,07 das ligações não modeladas);
* SC: 1,5 kN/m no contorno (7,5 kN no total);
* W0, W90, W180, W270: 1,82 kN em X e 2,18 kN em Z, divididos nos quatro nós do topo — W0 → +X,
  W90 → −Z, W180 → −X, W270 → +Z (a convenção do programa).

Saem os arquivos como o usuário envia: "Listar forças da viga" (cp1252, ponto de milhar, vírgula
decimal, forças nas pontas de cada elemento nos eixos locais), "Listar forças resultantes" e os
-apoios.csv e -fixacoes.csv da macro exportar_casos_de_carga, além do …_esqueleto.csv da macro da
lista de corte. As forças nas pontas são as que os nós fazem no elemento: o programa lê o
esforço interno como −F no Fim 1 e +F no Fim 2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

import numpy as np

from core import plano_de_cargas as pc
from core import section_catalog as sc
from tests import dados_solidworks as ds

E_N_M2 = 200e9
G_N_M2 = 77e9
DENSIDADE = 7850.0
GRAVIDADE = 10.5  # 9,81 × 1,07
PILAR = "W 150 x 13,0"
CONTORNO = 'U 8" x 17,10'
ESTUDO = "Análise estática 1"
#: Elementos por barra (a malha de vigas).
DIVISOES = 4


@dataclass(frozen=True)
class Barra:
    viga: str  # o nome no Simulation ("Viga-1(Pilar[1])")
    corpo: str  # o corpo no esqueleto
    perfil: str
    inicio: tuple[float, float, float]  # m
    fim: tuple[float, float, float]

    @property
    def comprimento(self) -> float:
        return math.dist(self.inicio, self.fim)


def _barras() -> tuple[Barra, ...]:
    pes = ((0.0, -1.0), (0.0, 0.0), (1.5, -1.0), (1.5, 0.0))
    barras = []
    for k, (x, z) in enumerate(pes, start=1):
        base, topo = (x, -2.0, z), (x, 0.0, z)
        # Dois pilares listados do pé para o topo e dois do topo para o pé: o programa acha a base.
        inicio, fim = (base, topo) if k <= 2 else (topo, base)
        barras.append(Barra(f"Viga-{k}(Pilar[{k}])", f"Pilar[{k}]", PILAR, inicio, fim))
    contorno = (
        ((0.0, 0.0, -1.0), (1.5, 0.0, -1.0)),
        ((1.5, 0.0, -1.0), (1.5, 0.0, 0.0)),
        ((1.5, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ((0.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
    )
    for k, (a, b) in enumerate(contorno, start=1):
        barras.append(Barra(f"Viga-{4 + k}(Contorno[{k}])", f"Contorno[{k}]", CONTORNO, a, b))
    return tuple(barras)


BARRAS = _barras()
PES = tuple(b.inicio if b.inicio[1] < b.fim[1] else b.fim for b in BARRAS[:4])
TOPOS = tuple(b.fim if b.inicio[1] < b.fim[1] else b.inicio for b in BARRAS[:4])
#: Caso → força horizontal total (N) nos eixos do modelo, dividida nos quatro nós do topo.
VENTOS = {
    "W0": (1820.0, 0.0, 0.0),
    "W90": (0.0, 0.0, -2180.0),
    "W180": (-1820.0, 0.0, 0.0),
    "W270": (0.0, 0.0, 2180.0),
}
SC_N_M = 1500.0
CASOS = ("PP", "SC", *VENTOS)


# ---------------------------------------------------------------------------------------------
# Rigidez direta
# ---------------------------------------------------------------------------------------------
def _eixos(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Linhas: x ao longo da barra; y e z na seção (pilar: y = X do modelo)."""
    x = (b - a) / np.linalg.norm(b - a)
    referencia = np.array([1.0, 0.0, 0.0]) if abs(x[1]) > 0.99 else np.array([0.0, 1.0, 0.0])
    z = np.cross(x, referencia)
    z /= np.linalg.norm(z)
    y = np.cross(z, x)
    return np.vstack([x, y, z])


def _rigidez_local(perfil: sc.PerfilEstrutural, comprimento: float) -> np.ndarray:
    area = perfil.area_mm2 * 1e-6
    iz = perfil.ix_mm4 * 1e-12  # flexão no plano x-y (eixo forte)
    iy = perfil.iy_mm4 * 1e-12
    j = perfil.j_mm4 * 1e-12
    L, E, G = comprimento, E_N_M2, G_N_M2
    k = np.zeros((12, 12))
    k[0, 0] = k[6, 6] = E * area / L
    k[0, 6] = -E * area / L
    k[3, 3] = k[9, 9] = G * j / L
    k[3, 9] = -G * j / L
    a, b, c, d = 12 * E * iz / L**3, 6 * E * iz / L**2, 4 * E * iz / L, 2 * E * iz / L
    k[1, 1] = k[7, 7] = a
    k[1, 7] = -a
    k[1, 5] = k[1, 11] = b
    k[5, 7] = k[7, 11] = -b
    k[5, 5] = k[11, 11] = c
    k[5, 11] = d
    a, b, c, d = 12 * E * iy / L**3, 6 * E * iy / L**2, 4 * E * iy / L, 2 * E * iy / L
    k[2, 2] = k[8, 8] = a
    k[2, 8] = -a
    k[2, 4] = k[2, 10] = -b
    k[4, 8] = k[8, 10] = b
    k[4, 4] = k[10, 10] = c
    k[4, 10] = d
    return k + np.triu(k, 1).T


def _cargas_equivalentes(w_local: np.ndarray, comprimento: float) -> np.ndarray:
    """As forças nodais equivalentes (eixos locais) de uma carga uniforme w (N/m)."""
    L = comprimento
    wx, wy, wz = w_local
    p = np.zeros(12)
    p[0] = p[6] = wx * L / 2
    p[1] = p[7] = wy * L / 2
    p[5], p[11] = wy * L**2 / 12, -wy * L**2 / 12
    p[2] = p[8] = wz * L / 2
    p[4], p[10] = -wz * L**2 / 12, wz * L**2 / 12
    return p


@dataclass(frozen=True)
class Elemento:
    ident: int
    barra: Barra
    i: int
    j: int


@dataclass(frozen=True)
class Resultado:
    #: barra (Simulation) → [(elemento, f nas duas pontas: 12 valores em N e N·m, eixos locais)]
    forcas: dict[str, list[tuple[int, np.ndarray]]]
    #: pé → (reação em N, momento em N·m), eixos do modelo
    reacoes: dict[tuple[float, float, float], tuple[np.ndarray, np.ndarray]]
    cargas_totais_N: np.ndarray


def _malha() -> tuple[list[tuple[float, float, float]], list[Elemento]]:
    nos: list[tuple[float, float, float]] = []

    def no(p: tuple[float, float, float]) -> int:
        chave = tuple(round(c, 9) for c in p)
        for k, q in enumerate(nos):
            if math.dist(q, chave) < 1e-9:
                return k
        nos.append(chave)  # type: ignore[arg-type]
        return len(nos) - 1

    elementos = []
    ident = 30001
    for barra in BARRAS:
        a, b = np.array(barra.inicio), np.array(barra.fim)
        pontos = [tuple(a + (b - a) * t / DIVISOES) for t in range(DIVISOES + 1)]
        for t in range(DIVISOES):
            elementos.append(Elemento(ident, barra, no(pontos[t]), no(pontos[t + 1])))
            ident += 1
    return nos, elementos


@cache
def resolver(caso: str) -> Resultado:
    """Um caso, ou uma soma deles ("PP+W0", "1.4*SC") — o estudo linear superpõe."""
    if "+" in caso or "*" in caso:
        partes = []
        for termo in caso.split("+"):
            fator, _, nome = termo.rpartition("*")
            partes.append((float(fator) if fator else 1.0, _resolver(nome)))
        return Resultado(
            {
                viga: [
                    (ident, sum(f * r.forcas[viga][k][1] for f, r in partes))
                    for k, (ident, _) in enumerate(partes[0][1].forcas[viga])
                ]
                for viga in partes[0][1].forcas
            },
            {
                pe: tuple(sum(f * r.reacoes[pe][i] for f, r in partes) for i in range(2))  # type: ignore[misc]
                for pe in partes[0][1].reacoes
            },
            sum(f * r.cargas_totais_N for f, r in partes),
        )
    return _resolver(caso)


@cache
def _resolver(caso: str) -> Resultado:
    nos, elementos = _malha()
    total = 6 * len(nos)
    K = np.zeros((total, total))
    F = np.zeros(total)
    cargas = np.zeros(3)
    dados_dos_elementos = []
    for e in elementos:
        a, b = np.array(nos[e.i]), np.array(nos[e.j])
        L = float(np.linalg.norm(b - a))
        perfil = sc.obter_perfil(e.barra.perfil)
        R = _eixos(a, b)
        T = np.kron(np.eye(4), R)
        k = _rigidez_local(perfil, L)
        w = np.zeros(3)
        if caso == "PP":
            w[1] -= perfil.area_mm2 * 1e-6 * DENSIDADE * GRAVIDADE
        if caso == "SC" and e.barra.perfil == CONTORNO:
            w[1] -= SC_N_M
        cargas += w * L
        p = _cargas_equivalentes(R @ w, L)
        graus = [6 * e.i + g for g in range(6)] + [6 * e.j + g for g in range(6)]
        K[np.ix_(graus, graus)] += T.T @ k @ T
        F[graus] += T.T @ p
        dados_dos_elementos.append((e, T, k, p, graus))
    if caso in VENTOS:
        forca = np.array(VENTOS[caso]) / len(TOPOS)
        for topo in TOPOS:
            k = nos.index(tuple(round(c, 9) for c in topo))  # type: ignore[arg-type]
            F[6 * k : 6 * k + 3] += forca
            cargas += forca
    presos = [nos.index(tuple(round(c, 9) for c in p)) for p in PES]  # type: ignore[arg-type]
    fixos = sorted(6 * k + g for k in presos for g in range(6))
    livres = [g for g in range(total) if g not in fixos]
    u = np.zeros(total)
    u[livres] = np.linalg.solve(K[np.ix_(livres, livres)], F[livres])
    reacao_total = K @ u - F
    forcas: dict[str, list[tuple[int, np.ndarray]]] = {}
    for e, T, k, p, graus in dados_dos_elementos:
        f = k @ (T @ u[graus]) - p
        forcas.setdefault(e.barra.viga, []).append((e.ident, f))
    reacoes = {
        PES[n]: (reacao_total[6 * k : 6 * k + 3], reacao_total[6 * k + 3 : 6 * k + 6])
        for n, k in enumerate(presos)
    }
    return Resultado(forcas, reacoes, cargas)


# ---------------------------------------------------------------------------------------------
# Os arquivos
# ---------------------------------------------------------------------------------------------
def _pt(valor: float) -> str:
    return ds._pt(float(valor))


def csv_forcas(caso: str, *, de: str | None = None, nome_do_caso: str | None = None) -> bytes:
    """O "Listar forças da viga" do caso; ``de`` põe os números de outro caso (o erro de salvar
    sem trocar o caso no gerenciador)."""
    r = resolver(de or caso)
    linhas = [
        "sep=;",
        "21:14; sábado; outubro 24; 2026",
        f"Nome do estudo:{ESTUDO}",
        f"Caso de carga: {nome_do_caso or caso}",
        "",
        "Nome da viga  ;Elemento  ;Fim  ;Axial (N)  ;Cisalhamento1 (N)  ;Cisalhamento2 (N)  ;"
        "Momento 1 (N.m)  ;Momento 2 (N.m)  ;Torque (N.m)",
    ]
    for barra in BARRAS:
        linhas.append(f"{barra.viga}  ;  ;  ;  ;  ;  ;  ;  ;")
        for ident, f in r.forcas[barra.viga]:
            # Shear 1 e 2 nos eixos y e z; Momento 1 em torno de y, Momento 2 em torno de z.
            for fim, base, rotulo in (("1", 0, str(ident)), ("2", 6, "")):
                valores = (f[base], f[base + 1], f[base + 2], f[base + 4], f[base + 5], f[base + 3])
                linhas.append(f"  ;{rotulo}  ;{fim}  ;" + "  ;".join(_pt(v) for v in valores))
    linhas.append("  ;  ;  ;  ;  ;  ;  ;  ;")
    return "\r\n".join(linhas).encode("cp1252")


def reacao_total_N(caso: str) -> np.ndarray:
    return sum((f for f, _ in resolver(caso).reacoes.values()), np.zeros(3))


def csv_reacoes(caso: str, *, de: str | None = None, fator: float = 1.0) -> bytes:
    r = reacao_total_N(de or caso) * fator
    m = sum((m for _, m in resolver(de or caso).reacoes.values()), np.zeros(3)) * fator
    linhas = [
        "21:14; sábado; outubro 24; 2026",
        f"Nome do estudo:{ESTUDO}",
        f"Caso de carga: {caso}",
        "",
        "Força de reação (N)",
        "",
        "Componente  ;Seleção  ;Modelo inteiro",
        *(f"Soma {e}:  ;{_pt(v)}  ;{_pt(v)}" for e, v in zip("XYZ", r, strict=True)),
        f"Resultante:  ;{_pt(np.linalg.norm(r))}  ;{_pt(np.linalg.norm(r))}",
        "",
        "Momento de reação (N.m)",
        "",
        "Componente  ;Seleção  ;Modelo inteiro",
        *(f"Soma {e}:  ;{_pt(v)}  ;{_pt(v)}" for e, v in zip("XYZ", m, strict=True)),
        f"Resultante:  ;{_pt(np.linalg.norm(m))}  ;{_pt(np.linalg.norm(m))}",
    ]
    return "\r\n".join(linhas).encode("cp1252")


def _n6(valor: float) -> str:
    return f"{float(valor):.6f}".replace(".", ",")


def csv_apoios(caso: str, *, de: str | None = None) -> bytes:
    """O -apoios.csv da macro (v13+): a reação em cada nó apoiado, com a posição em m."""
    r = resolver(de or caso)
    linhas = [
        "sep=;",
        "21:14; 24/10/2026",
        f"Nome do estudo:{ESTUDO}",
        f"Caso de carga: {caso}",
        "Macro: Mecanica Toolkit - exportar_casos_de_carga v16",
        "",
        "Reacoes nos nos (N; N.m)",
        "No;X (m);Y (m);Z (m);Fx (N);Fy (N);Fz (N);Mx (N.m);My (N.m);Mz (N.m)",
    ]
    soma = np.zeros(6)
    for no, pe in enumerate(PES, start=101):
        forca, momento = r.reacoes[pe]
        soma += np.concatenate([forca, momento])
        linhas.append(";".join([str(no), *map(_n6, pe), *map(_n6, forca), *map(_n6, momento)]))
    linhas += [
        "",
        "Reacoes por fixacao (N; N.m)",
        "Fixacao;Fx (N);Fy (N);Fz (N);Mx (N.m);My (N.m);Mz (N.m)",
        "Fixo-1;" + ";".join(map(_n6, soma)),
    ]
    return ("\r\n".join(linhas) + "\r\n").encode("cp1252")


def csv_fixacoes() -> bytes:
    linhas = [
        "sep=;",
        "21:14; 24/10/2026",
        f"Nome do estudo:{ESTUDO}",
        "Macro: Mecanica Toolkit - exportar_casos_de_carga v16",
        "",
        "Fixacoes do estudo",
        "Fixacao;Tipo (codigo);Entidades;Entidade;Tipo da entidade;X (m);Y (m);Z (m)",
    ]
    for k, p in enumerate(PES, start=1):
        linhas.append(f"Fixo-1;0;4;{k};IVertex;" + ";".join(map(_n6, p)))
    return ("\r\n".join(linhas) + "\r\n").encode("cp1252")


def csv_esqueleto() -> bytes:
    corpos = {
        b.corpo: (
            f"{b.perfil}<1>",
            b.perfil,
            tuple(round(c * 1000, 6) for c in b.inicio),
            tuple(round(c * 1000, 6) for c in b.fim),
            b.perfil,
        )
        for b in BARRAS
    }
    return ds.csv_esqueleto(corpos=corpos)


def plano() -> pc.PlanoDeCargas:
    """O plano de cargas do teste01: o que o programa manda aplicar em cada caso."""
    p = pc.PlanoDeCargas(fator_peso_proprio=1.07)
    p = pc.com_acao(p, pc.nova_acao("PP"))
    p = pc.com_acao(
        p,
        pc.nova_acao(
            "SC",
            cargas=[pc.CargaDoModelo("Contorno", 1.5, "kN/m", "Z (vertical)", "", 1, 5.0)],
        ),
    )
    for codigo, direcao, valor in (
        ("W0", "+X", 1.82),
        ("W90", "+Y", 2.18),  # o +Y da planta é o −Z do SolidWorks
        ("W180", "−X", -1.82),
        ("W270", "−Y", -2.18),
    ):
        p = pc.com_acao(
            p, pc.nova_acao(codigo, cargas=[pc.CargaDoModelo("Topo", valor, "kN", direcao)])
        )
    return p
