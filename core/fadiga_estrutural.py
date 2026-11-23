"""Fadiga de estruturas de aço pela categoria do detalhe — ABNT NBR 8800:2025, Anexo H.

Cada detalhe (metal-base, furo, solda, acessório, parafuso) tem uma categoria (A, B, B', C, D, E,
E', F, G, C' ou C'') na Tabela H.1. A faixa admissível de variação de tensões cai com o número de
ciclos (H.4 a):

    σ_SR = (329·C_f/N)^0,333 ≥ σ_TH          (A a E', G)
    σ_SR = (11×10⁴·C_f/N)^0,167 ≥ σ_TH       (F — cisalhamento na garganta da solda)
    σ_SR = R·(14,4×10¹¹/N)^0,333             (C' e C'' — trinca na raiz, sem σ_TH)

A faixa solicitante vem da combinação frequente de fadiga (H.2.1, ψ₁ = 1): Δσ = σ_máx − σ_mín.
Não precisa verificar com menos de 20 000 ciclos (H.2.6) nem quando os dois extremos são de
compressão (H.2.5); as tensões não passam de 0,66·f_y (normal) ou 0,40·f_y (cisalhamento) (H.2.2).

Unidades: MPa.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core import perfil_i as pi
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "fadiga_estrutural"
MODULO_TITULO = "Fadiga da estrutura"
CICLOS_DISPENSA = 20_000  # H.2.6

#: categoria → (C_f, σ_TH em MPa ou None); NBR 8800:2025 Tabela H.1
CATEGORIAS: dict[str, tuple[float, float | None]] = {
    "A": (250e8, 165.0),
    "B": (120e8, 110.0),
    "B'": (61e8, 83.0),
    "C": (44e8, 69.0),
    "D": (22e8, 48.0),
    "E": (11e8, 31.0),
    "E'": (3.9e8, 18.0),
    "F": (160e10, 55.0),
    "G": (3.9e8, 48.0),
    "C'": (44e8, None),
    "C''": (44e8, None),
}


@dataclass(frozen=True)
class CasoH1:
    codigo: str
    descricao: str
    categoria: str
    cisalhamento: bool = False

    @property
    def rotulo(self) -> str:
        return f"{self.codigo} — {self.descricao} [{self.categoria}]"


#: Casos da Tabela H.1 (resumidos); a descrição completa e as figuras estão na norma (Tabela H.2).
CASOS: tuple[CasoH1, ...] = (
    CasoH1(
        "1.1",
        "Metal-base afastado de solda, aço comum, bordas cortadas com rugosidade ≤ 25 µm",
        "A",
    ),
    CasoH1("1.2", "Metal-base afastado de solda, aço patinável sem pintura", "B"),
    CasoH1("1.3", "Canto reentrante de recorte, R ≥ 25 mm, furado/usinado ou esmerilhado", "C"),
    CasoH1("1.3", "Canto reentrante de recorte, R ≥ 25 mm, sem esmerilhar", "E'"),
    CasoH1("1.4", "Abertura de acesso para soldagem, R ≥ 25 mm, esmerilhada", "C"),
    CasoH1("1.4", "Abertura de acesso para soldagem, R ≥ 25 mm, sem esmerilhar", "E'"),
    CasoH1("1.5", "Furo com parafuso protendido (seção líquida)", "C"),
    CasoH1("1.5", "Furo sem parafuso ou com parafuso de aperto normal", "D"),
    CasoH1("2.1", "Seção bruta em junta por sobreposição com parafusos por atrito", "B"),
    CasoH1("2.2", "Seção líquida, parafusos por contato instalados como por atrito", "B"),
    CasoH1("2.3", "Seção líquida de outras ligações parafusadas", "C"),
    CasoH1("2.4", "Seção líquida de chapa ligada por pino", "E"),
    CasoH1(
        "3.1", "Perfil soldado: solda longitudinal contínua (PPT com contrassolda ou filete)", "B"
    ),
    CasoH1("3.2", "Perfil soldado: PPT com chapa de espera não removida ou filete", "B'"),
    CasoH1("3.3", "Fim de solda longitudinal em abertura de acesso, esmerilhada", "D"),
    CasoH1("3.3", "Fim de solda longitudinal em abertura de acesso, sem esmerilhar", "E'"),
    CasoH1("3.4", "Extremidade de segmento de filete intermitente", "E"),
    CasoH1("3.5", "Ponta de lamela mais estreita que a mesa, mesa ≤ 20 mm", "E"),
    CasoH1("3.5", "Ponta de lamela mais estreita que a mesa, mesa > 20 mm", "E'"),
    CasoH1(
        "3.6", "Ponta de lamela mais larga que a mesa, com solda transversal, mesa ≤ 20 mm", "E"
    ),
    CasoH1(
        "3.6", "Ponta de lamela mais larga que a mesa, com solda transversal, mesa > 20 mm", "E'"
    ),
    CasoH1("3.7", "Ponta de lamela mais larga que a mesa, sem solda transversal", "E'"),
    CasoH1("4.1", "Ligação de extremidade com filetes longitudinais, t ≤ 12,7 mm", "E"),
    CasoH1("4.1", "Ligação de extremidade com filetes longitudinais, t > 12,7 mm", "E'"),
    CasoH1("5.1", "Emenda de topo com PPT esmerilhada na direção das tensões", "B"),
    CasoH1("5.2", "Emenda PPT com transição de largura/espessura ≤ 22°, esmerilhada", "B"),
    CasoH1("5.4", "Emenda, junta em T ou de canto com PPT, reforço não removido", "C"),
    CasoH1("5.5", "PPT com chapa de espera não removida, solda da espera dentro do entalhe", "D"),
    CasoH1("5.5", "PPT com chapa de espera não removida, solda da espera fora do entalhe", "E"),
    CasoH1("5.6", "Chapa tracionada com penetração parcial: trinca no pé da solda", "C"),
    CasoH1("5.6", "Chapa tracionada com penetração parcial: trinca na raiz (R_PJP)", "C'"),
    CasoH1("5.7", "Chapa tracionada com dois filetes transversais: trinca no pé da solda", "C"),
    CasoH1("5.7", "Chapa tracionada com dois filetes transversais: trinca na raiz (R_FIL)", "C''"),
    CasoH1("5.8", "Pé do filete de enrijecedor transversal soldado (alma ou mesa)", "C"),
    CasoH1("6.1", "Acessório com PPT longitudinal e raio de transição R ≥ 600 mm", "B"),
    CasoH1("6.1", "Acessório com PPT longitudinal e 150 ≤ R < 600 mm", "C"),
    CasoH1("6.1", "Acessório com PPT longitudinal e 50 ≤ R < 150 mm", "D"),
    CasoH1("6.1", "Acessório com PPT longitudinal e R < 50 mm", "E"),
    CasoH1("6.4", "Acessório transversal com filete ou PPP e raio R > 50 mm", "D"),
    CasoH1("6.4", "Acessório transversal com filete ou PPP e raio R ≤ 50 mm", "E"),
    CasoH1("7.1", "Acessório curto (filete) com comprimento a < 50 mm", "C"),
    CasoH1("7.1", "Acessório com b ≤ 20 mm e 50 ≤ a ≤ mín(12b; 100 mm)", "D"),
    CasoH1("7.1", "Acessório com b ≤ 20 mm e a > mín(12b; 100 mm)", "E"),
    CasoH1("7.1", "Acessório com b > 20 mm e a > 100 mm", "E'"),
    CasoH1("7.2", "Acessório com filete longitudinal e raio de transição R > 50 mm", "D"),
    CasoH1("7.2", "Acessório com filete longitudinal e raio de transição R ≤ 50 mm", "E"),
    CasoH1("8.1", "Metal-base junto ao conector tipo pino com cabeça (stud)", "C"),
    CasoH1("8.2", "Cisalhamento na garganta de filete (contínuo ou intermitente)", "F", True),
    CasoH1("8.3", "Metal-base junto a solda de tampão em furo ou rasgo", "E"),
    CasoH1("8.4", "Cisalhamento em solda de tampão", "F", True),
    CasoH1("8.5", "Parafuso ou barra rosqueada tracionada (área líquida efetiva)", "G"),
)
ROTULOS = tuple(c.rotulo for c in CASOS)


def caso_pelo_rotulo(rotulo: str) -> CasoH1:
    for c in CASOS:
        if c.rotulo == rotulo:
            return c
    return CASOS[0]


REFERENCIAS = (
    "ABNT NBR 8800:2025 — Anexo H (normativo) Fadiga: H.2 (combinação frequente e dispensas), "
    "H.4 (faixa admissível), H.5 (parafusos) e Tabelas H.1 e H.2 (categorias e detalhes).",
    "AISC 360-16 — Appendix 3, Design for Fatigue (mesma origem da Tabela H.1).",
)


@dataclass(frozen=True)
class Detalhe:
    nome: str = "Mesa inferior junto ao enrijecedor"
    caso: str = ROTULOS[33]  # 5.8, categoria C
    sigma_max: float = 120.0  # MPa (tração +)
    sigma_min: float = 30.0
    # C' (R_PJP) e C'' (R_FIL): espessura da chapa tracionada, raiz não soldada 2a e perna w
    tp: float = 16.0
    dois_a: float = 8.0
    w: float = 8.0


@dataclass(frozen=True)
class EntradaFadiga:
    aco: str = "ASTM A572 Gr 50"
    ciclos_por_dia: float = 200.0
    dias_por_ano: float = 300.0
    anos: float = 25.0
    ciclos_informados: float = 0.0  # 0 = pelo cálculo acima
    detalhes: tuple[Detalhe, ...] = field(
        default_factory=lambda: (
            Detalhe(),
            Detalhe("Mesa tracionada afastada de solda", ROTULOS[0], 150.0, 30.0),
            Detalhe("Filete da ligação (garganta)", ROTULOS[47], 45.0, 5.0),
        )
    )

    @property
    def N(self) -> float:
        if self.ciclos_informados > 0:
            return self.ciclos_informados
        return self.ciclos_por_dia * self.dias_por_ano * self.anos


def validar(e: EntradaFadiga) -> list[str]:
    erros: list[str] = []
    if e.aco not in pi.ACOS:
        erros.append("Escolha o aço.")
    if e.N <= 0:
        erros.append("O número de ciclos deve ser positivo.")
    if not e.detalhes:
        erros.append("Informe pelo menos um detalhe.")
    for d in e.detalhes:
        if d.caso not in ROTULOS:
            erros.append(f"{d.nome}: escolha o caso da Tabela H.1.")
        if d.sigma_min > d.sigma_max:
            erros.append(f"{d.nome}: a tensão mínima não pode ser maior que a máxima.")
        if caso_pelo_rotulo(d.caso).categoria in ("C'", "C''") and d.tp <= 0:
            erros.append(f"{d.nome}: informe a espessura da chapa tracionada.")
    return erros


def _n(valor: float, casas: int = 1) -> str:
    return pi.numero(valor, casas)


def fator_r_pjp(tp: float, dois_a: float, w: float) -> float:
    """H.4 c) 2): R_PJP = [1,12 − 1,01·(2a/t_p) + 1,24·(w/t_p)]/t_p^0,167 ≤ 1,0."""
    return min((1.12 - 1.01 * dois_a / tp + 1.24 * w / tp) / tp**0.167, 1.0)


def fator_r_fil(tp: float, w: float) -> float:
    """H.4 c) 3): R_FIL = (0,103 + 1,24·w/t_p)/t_p^0,167 ≤ 1,0."""
    return min((0.103 + 1.24 * w / tp) / tp**0.167, 1.0)


def faixa_admissivel(categoria: str, N: float, *, R: float = 1.0) -> tuple[float, str]:
    """σ_SR (MPa) e a fórmula usada."""
    Cf, th = CATEGORIAS[categoria]
    if categoria == "F":
        valor = (11e4 * Cf / N) ** 0.167
        return max(valor, th or 0.0), "(11×10⁴·C_f/N)^0,167 ≥ σ_TH"
    if categoria in ("C'", "C''"):
        base = (14.4e11 / N) ** 0.333
        if R >= 1.0:
            return max(base, 69.0), "R = 1: categoria C, (14,4×10¹¹/N)^0,333 ≥ 69 MPa"
        return R * base, f"R·(14,4×10¹¹/N)^0,333, R = {_n(R, 3)} (sem σ_TH)"
    valor = (329 * Cf / N) ** 0.333
    return max(valor, th or 0.0), "(329·C_f/N)^0,333 ≥ σ_TH"


@dataclass
class ResultadoFadiga:
    entrada: EntradaFadiga
    fy: float
    grupos: list[vm.Grupo]
    avisos: list[str]

    @property
    def linhas(self) -> list[Verificacao]:
        return vm.decisivas(self.grupos)

    @property
    def situacao(self) -> str:
        return vm.situacao(self.linhas)


def _linhas_do_detalhe(d: Detalhe, N: float, fy: float) -> list[Verificacao]:
    caso = caso_pelo_rotulo(d.caso)
    cat = caso.categoria
    ref = f"ABNT NBR 8800:2025, Anexo H, Tabela H.1 caso {caso.codigo} (categoria {cat})"
    delta = d.sigma_max - d.sigma_min
    linhas: list[Verificacao] = []
    limite = (0.40 if caso.cisalhamento else 0.66) * fy
    maior = max(abs(d.sigma_max), abs(d.sigma_min))
    linhas.append(
        vm.linha_limite(
            "Tensão máxima no regime de aplicação",
            maior,
            limite,
            "MPa",
            "ABNT NBR 8800:2025, H.2.2",
            f"|σ| ≤ {'0,40' if caso.cisalhamento else '0,66'}·f_y na combinação frequente",
        )
    )
    if N < CICLOS_DISPENSA:
        linhas.append(vm.linha_na("Faixa de variação de tensões", "MPa", "ABNT NBR 8800:2025, H.2.6",
                                  f"N = {_n(N, 0)} < 20 000 ciclos: verificação dispensada"))  # fmt: skip
        return linhas
    if not caso.cisalhamento and d.sigma_max <= 0:
        linhas.append(vm.linha_na("Faixa de variação de tensões", "MPa", "ABNT NBR 8800:2025, H.2.5",
                                  "os dois extremos são de compressão: verificação dispensada"))  # fmt: skip
        return linhas
    R = 1.0
    if cat == "C'":
        R = fator_r_pjp(d.tp, d.dois_a, d.w)
    elif cat == "C''":
        R = fator_r_fil(d.tp, d.w)
    sr, formula = faixa_admissivel(cat, N, R=R)
    th = CATEGORIAS[cat][1]
    texto = f"Δσ = σ_máx − σ_mín = {_n(d.sigma_max)} − ({_n(d.sigma_min)}); σ_SR = {formula}"
    if th is not None and delta <= th and cat not in ("C'", "C''"):
        texto += f"; Δσ ≤ σ_TH = {_n(th, 0)} MPa (vida infinita, H.2.5)"
    Cf = CATEGORIAS[cat][0]
    linhas.append(
        Verificacao(
            "Faixa de variação de tensões",
            delta,
            sr,
            "MPa",
            ref
            + (", H.4 c)" if cat in ("C'", "C''") else ", H.4 a)" if cat != "F" else ", H.4 b)"),
            texto,
            equacoes=(
                "σ_SR = (329 C_f / N)^0,333",
                f"σ_SR = (329 · {Cf:.3g} / {N:.4g})^0,333 = {_n(sr, 1)} MPa",
            )
            if cat not in ("F", "C'", "C''")
            else (),
        )
    )
    return linhas


def calcular(e: EntradaFadiga) -> ResultadoFadiga:
    fy = pi.ACOS[e.aco][0]
    N = e.N
    grupos = [vm.Grupo(f"Detalhe: {d.nome}", _linhas_do_detalhe(d, N, fy)) for d in e.detalhes]
    avisos = [
        "Tensões da combinação frequente de fadiga (ações permanentes + variáveis com ψ₁ = 1), "
        "por análise elástica, sem fatores de concentração de tensões (H.2.1 e H.3.1).",
        "Vale para estrutura protegida contra corrosão (ou atmosfera pouco agressiva) e abaixo "
        "de 150 °C (H.2.7).",
    ]
    if any(caso_pelo_rotulo(d.caso).categoria == "G" for d in e.detalhes):
        avisos.append(
            "Parafusos tracionados: a ligação deve ser de chapa rígida, sem efeito de alavanca "
            "significativo (H.3.2); com protensão e pega só de aço, pode-se tomar 20 % da força "
            "da combinação frequente na área efetiva (H.5 b)."
        )
    return ResultadoFadiga(e, fy, grupos, avisos)


def registro(r: ResultadoFadiga) -> dict[str, Any]:
    e = r.entrada
    entradas = {
        "aco": f"{e.aco} (f_y = {_n(r.fy, 0)} MPa)",
        "ciclos": (
            f"N = {_n(e.N, 0)} ciclos"
            + (
                ""
                if e.ciclos_informados > 0
                else f" ({_n(e.ciclos_por_dia, 0)}/dia × {_n(e.dias_por_ano, 0)} dias × "
                f"{_n(e.anos, 0)} anos)"
            )
        ),
        "detalhes": "; ".join(
            f"{d.nome}: caso {caso_pelo_rotulo(d.caso).codigo} "
            f"[{caso_pelo_rotulo(d.caso).categoria}], σ de {_n(d.sigma_min)} a {_n(d.sigma_max)} MPa"
            for d in e.detalhes
        ),
    }
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"Fadiga da estrutura — {len(e.detalhes)} detalhe(s), N = {_n(e.N, 0)}",
        grupos=r.grupos,
        entradas=entradas,
        metodo=(
            "Fadiga pela categoria do detalhe (ABNT NBR 8800:2025, Anexo H): faixa de variação "
            "de tensões da combinação frequente comparada com a faixa admissível da Tabela H.1 "
            "para o número de ciclos da vida útil."
        ),
        premissas=list(r.avisos),
        referencias=REFERENCIAS,
        objeto="A estrutura",
    )


def com(e: EntradaFadiga, **mudancas: Any) -> EntradaFadiga:
    return replace(e, **mudancas)


def detalhes_de_tabela(linhas: Sequence[dict[str, Any]]) -> tuple[Detalhe, ...]:
    def numero(valor: Any, padrao: float) -> float:
        try:
            x = float(valor)
        except (TypeError, ValueError):
            return padrao
        return x if math.isfinite(x) else padrao

    saida: list[Detalhe] = []
    for i, linha in enumerate(linhas):
        caso = str(linha.get("Caso da Tabela H.1") or ROTULOS[0])
        saida.append(
            Detalhe(
                nome=str(linha.get("Detalhe") or "").strip() or f"Detalhe {i + 1}",
                caso=caso if caso in ROTULOS else ROTULOS[0],
                sigma_max=numero(linha.get("σ máx (MPa)"), 0.0),
                sigma_min=numero(linha.get("σ mín (MPa)"), 0.0),
                tp=numero(linha.get("t_p (mm)"), 16.0),
                dois_a=numero(linha.get("2a (mm)"), 0.0),
                w=numero(linha.get("w (mm)"), 0.0),
            )
        )
    return tuple(saida)


def tabela_dos_detalhes(detalhes: Sequence[Detalhe]) -> list[dict[str, Any]]:
    return [
        {
            "Detalhe": d.nome,
            "Caso da Tabela H.1": d.caso,
            "σ máx (MPa)": d.sigma_max,
            "σ mín (MPa)": d.sigma_min,
            "t_p (mm)": d.tp,
            "2a (mm)": d.dois_a,
            "w (mm)": d.w,
        }
        for d in detalhes
    ]
