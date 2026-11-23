"""Perfis I e H para as verificações de vigas e ligações: laminados do catálogo ou soldados.

Junta num lugar o que as páginas de forças localizadas, monovia, ligação rígida, viga mista,
aberturas na alma e contenção lateral precisam do perfil: as dimensões, o raio de concordância
(dos W e HP da Gerdau, por :mod:`core.perfis_gerdau_k`), a medida ``k`` da NBR 8800 5.7.3 e as
propriedades geométricas. Os I laminados de abas inclinadas do catálogo não trazem o raio: o
programa usa ``k = t_f`` (a favor da segurança) e avisa.

Unidades: mm, mm², mm³, mm⁴, mm⁶.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from core import perfis_gerdau_k as gk
from core.steel_sections import PerfilAco

_DADOS = Path(__file__).resolve().parent.parent / "data"

LAMINADO = "laminado"
SOLDADO = "soldado"

#: aços estruturais mais usados nas vigas e ligações (f_y, f_u em MPa) — NBR 8800 Anexo A
ACOS: dict[str, tuple[float, float]] = {
    "ASTM A36": (250.0, 400.0),
    "ASTM A572 Gr 50": (345.0, 450.0),
    "ASTM A588": (345.0, 485.0),
    "ASTM A242": (345.0, 485.0),
    "USI CIVIL 300": (300.0, 400.0),
    "USI CIVIL 350": (350.0, 500.0),
}
E_ACO = 200_000.0  # MPa — NBR 8800 4.6.2.3
G_ACO = 77_000.0  # MPa
GAMA_A1 = 1.10  # NBR 8800 Tabela 3 — escoamento, flambagem e instabilidade
GAMA_A2 = 1.35  # NBR 8800 Tabela 3 — ruptura

FAMILIA_W = "W e HP (Gerdau)"
FAMILIA_I = "I laminado"
FAMILIA_SOLDADO = "Soldado (informar)"
FAMILIAS = (FAMILIA_W, FAMILIA_I, FAMILIA_SOLDADO)


@dataclass(frozen=True)
class PerfilI:
    """Perfil I/H com dois eixos de simetria.

    ``raio`` é o raio de concordância mesa–alma do laminado; no soldado, a perna do filete
    mesa–alma (a "raiz do filete" da 5.7.3.2). ``raio_conhecido`` é falso nos I laminados de
    abas inclinadas, em que o catálogo não traz o raio.
    """

    nome: str
    tipo: str  # LAMINADO ou SOLDADO
    d: float
    bf: float
    tf: float
    tw: float
    raio: float
    A: float
    Ix: float
    Iy: float
    Zx: float
    Zy: float
    J: float
    Cw: float
    massa: float  # kg/m
    raio_conhecido: bool = True

    @property
    def h_interna(self) -> float:
        """Distância entre as faces internas das mesas, d − 2·t_f."""
        return self.d - 2.0 * self.tf

    @property
    def h(self) -> float:
        """h da NBR 8800 5.7.5: faces internas menos os raios (laminado) ou faces internas
        (soldado)."""
        return self.h_interna - (2.0 * self.raio if self.tipo == LAMINADO else 0.0)

    @property
    def k(self) -> float:
        """k da NBR 8800 5.7.3.2: t_f mais o raio (laminado) ou mais a raiz do filete (soldado)."""
        return self.tf + self.raio

    @property
    def Wx(self) -> float:
        return self.Ix / (self.d / 2.0)

    @property
    def Wy(self) -> float:
        return self.Iy / (self.bf / 2.0)

    @property
    def rx(self) -> float:
        return math.sqrt(self.Ix / self.A)

    @property
    def ry(self) -> float:
        return math.sqrt(self.Iy / self.A)

    @property
    def soldado(self) -> bool:
        return self.tipo == SOLDADO

    def perfil_aco(self) -> PerfilAco:
        """O mesmo perfil no formato de :mod:`core.steel_sections` (para :mod:`core.nbr8800`)."""
        return PerfilAco(
            nome=self.nome,
            familia="W (mesa larga)" if self.tipo == LAMINADO else "I duplamente simétrico",
            area_mm2=self.A,
            ix_mm4=self.Ix,
            iy_mm4=self.Iy,
            zx_mm3=self.Zx,
            zy_mm3=self.Zy,
            j_mm4=self.J,
            cw_mm6=self.Cw,
            altura_mm=self.d,
            largura_mm=self.bf,
            espessura_alma_mm=self.tw,
            espessura_mesa_mm=self.tf,
            area_cisalhamento_mm2=self.d * self.tw,
            massa_kg_m=self.massa,
            descricao=self.descricao,
        )

    @property
    def descricao(self) -> str:
        texto = (
            f"{self.nome}: d = {numero(self.d, 1)}, b_f = {numero(self.bf, 1)}, "
            f"t_f = {numero(self.tf, 2)}, t_w = {numero(self.tw, 2)} mm"
        )
        if self.tipo == LAMINADO and self.raio_conhecido:
            texto += f", raio = {numero(self.raio, 1)} mm"
        elif self.tipo == SOLDADO and self.raio > 0:
            texto += f", filete mesa–alma = {numero(self.raio, 1)} mm"
        return texto


def numero(valor: float, casas: int = 2) -> str:
    """Número com vírgula decimal e sem zeros inúteis no fim."""
    if valor is None or not math.isfinite(valor):
        return "—"
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def _lista(arquivo: str) -> list[dict[str, Any]]:
    dados = json.loads((_DADOS / arquivo).read_text(encoding="utf-8"))
    return list(dados["perfis"] if isinstance(dados, dict) else dados)


def _do_catalogo(c: dict[str, Any], *, raio: float, conhecido: bool) -> PerfilI:
    return PerfilI(
        nome=str(c["nome"]),
        tipo=LAMINADO,
        d=float(c["altura_mm"]),
        bf=float(c["largura_mm"]),
        tf=float(c["espessura_mesa_mm"]),
        tw=float(c["espessura_alma_mm"]),
        raio=raio,
        A=float(c["area_mm2"]),
        Ix=float(c["ix_mm4"]),
        Iy=float(c["iy_mm4"]),
        Zx=float(c["zx_mm3"]),
        Zy=float(c["zy_mm3"]),
        J=float(c["j_mm4"]),
        Cw=float(c["cw_mm6"]),
        massa=float(c["massa_kg_m"]),
        raio_conhecido=conhecido,
    )


@lru_cache(maxsize=1)
def catalogo() -> dict[str, dict[str, PerfilI]]:
    """Família → nome → perfil. W e HP com o raio da tabela da Gerdau; I sem o raio."""
    familias: dict[str, dict[str, PerfilI]] = {FAMILIA_W: {}, FAMILIA_I: {}}
    for c in _lista("perfis_ref_gerdau.json"):
        h_dl = gk.H_E_D_LINHA_MM.get(gk._normalizar(str(c["nome"])))
        raio = (h_dl[0] - h_dl[1]) / 2.0 if h_dl else 0.0
        familias[FAMILIA_W][str(c["nome"])] = _do_catalogo(c, raio=raio, conhecido=bool(h_dl))
    for c in _lista("perfis_ref_gerdau_i.json"):
        familias[FAMILIA_I][str(c["nome"])] = _do_catalogo(c, raio=0.0, conhecido=False)
    return familias


def nomes(familia: str) -> list[str]:
    return list(catalogo().get(familia, {}))


def perfil(nome: str) -> PerfilI:
    """O perfil do catálogo pelo nome (W, HP ou I)."""
    for do_grupo in catalogo().values():
        if nome in do_grupo:
            return do_grupo[nome]
    raise KeyError(f"Perfil fora do catálogo: {nome}")


def soldado(
    d: float, bf: float, tf: float, tw: float, filete: float = 0.0, nome: str = ""
) -> PerfilI:
    """Perfil I soldado de mesas iguais (sem raio; ``filete`` = perna do filete mesa–alma)."""
    for rotulo, valor in (("d", d), ("b_f", bf), ("t_f", tf), ("t_w", tw)):
        if not (math.isfinite(valor) and valor > 0):
            raise ValueError(f"{rotulo} deve ser positivo.")
    if 2 * tf >= d:
        raise ValueError("As mesas ocupam toda a altura do perfil.")
    if tw >= bf:
        raise ValueError("A alma deve ser mais estreita que a mesa.")
    hw = d - 2 * tf
    A = 2 * bf * tf + hw * tw
    Ix = (bf * d**3 - (bf - tw) * hw**3) / 12
    Iy = 2 * tf * bf**3 / 12 + hw * tw**3 / 12
    Zx = bf * tf * (d - tf) + tw * hw**2 / 4
    Zy = tf * bf**2 / 2 + hw * tw**2 / 4
    J = (2 * bf * tf**3 + (d - tf) * tw**3) / 3
    Cw = tf * bf**3 * (d - tf) ** 2 / 24
    nome = nome or f"PS {numero(d, 0)} × {numero(bf, 0)} × {numero(tf, 2)} × {numero(tw, 2)}"
    return PerfilI(
        nome=nome, tipo=SOLDADO, d=d, bf=bf, tf=tf, tw=tw, raio=max(filete, 0.0), A=A, Ix=Ix,
        Iy=Iy, Zx=Zx, Zy=Zy, J=J, Cw=Cw, massa=A * 7850e-6,
    )  # fmt: skip


def com(p: PerfilI, **mudancas: Any) -> PerfilI:
    return replace(p, **mudancas)


def avisos_do_perfil(p: PerfilI) -> list[str]:
    """O que o usuário deve saber sobre as medidas que o programa adotou."""
    if p.tipo == LAMINADO and not p.raio_conhecido:
        return [
            f"{p.nome}: o catálogo não traz o raio de concordância; o programa usa k = t_f e "
            "h = d − 2·t_f (a favor da segurança no escoamento local da alma)."
        ]
    return []


def mr_x(p: PerfilI, fy: float) -> float:
    """M_r em torno de x sem tensões residuais (N·mm), usado em C_r da 5.7.5.2."""
    return p.Wx * fy
