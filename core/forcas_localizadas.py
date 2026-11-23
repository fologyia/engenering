"""Forças transversais localizadas em perfis I e H e os enrijecedores (ABNT NBR 8800:2025, 5.7).

Uma força que atua na face externa de uma mesa, centrada na alma — a reação de apoio de uma viga, o
pé de um equipamento, a mesa de outra viga que chega por cima ou por baixo, a mesa de uma viga
ligada rigidamente ao pilar — pode romper a viga localmente antes da flexão global:

* 5.7.2 flexão local da mesa (força que traciona a alma);
* 5.7.3 escoamento local da alma (tração ou compressão);
* 5.7.4 enrugamento da alma (compressão);
* 5.7.5 flambagem lateral da alma (compressão na mesa comprimida, sem contenção do deslocamento
  lateral relativo entre as mesas);
* 5.7.6 instabilidade da alma por compressão (par de forças opostas nas duas mesas);
* 5.7.7 cisalhamento do painel de alma (ligação rígida viga–pilar; usado pela ligação rígida);
* 5.7.8 apoio sem restrição à rotação com a alma livre (enrijecedor obrigatório).

Quando a força supera a resistência, a norma manda colocar enrijecedores (5.7.9): o programa
confere as proporções (5.7.9.5), a barra comprimida formada pelo enrijecedor e uma faixa de alma
(5.7.9.4), o esmagamento das pontas ajustadas (6.6.2), a tração (5.7.9.1 com 5.2) e as soldas
que levam a diferença entre a força e a resistência da alma.

Unidades: mm, MPa (N/mm²), N; as forças das entradas e das saídas em kN.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core import nbr8800 as nb
from core import perfil_i as pi
from core import soldas as sd
from core import verificacao_modulo as vm
from core.verificacao import Verificacao

MODULO_ID = "forcas_localizadas"
MODULO_TITULO = "Forças localizadas na alma"
NOME_DA_NORMA = "ABNT NBR 8800:2025"

COMPRESSAO = "Compressão na mesa (empurra a alma)"
TRACAO = "Tração na mesa (puxa a alma)"
PAR = "Par de forças opostas nas duas mesas"
TIPOS = (COMPRESSAO, TRACAO, PAR)

EXTREMIDADE = "Na extremidade da viga (faixa de 12·t_w)"
INTERNA = "Em seção interna (faixa de 25·t_w)"
POSICOES = (EXTREMIDADE, INTERNA)

ELETRODOS = dict(sd.ELETRODOS)
GAMA_W2 = 1.35  # NBR 8800 Tabela 3 — soldas, combinação normal

REFERENCIAS = (
    "ABNT NBR 8800:2025 — 5.7 Mesas e almas de perfis I e H submetidas a forças transversais "
    "localizadas (5.7.2 a 5.7.9).",
    "ABNT NBR 8800:2025 — 5.3 (barras comprimidas), 5.2 (tração), 6.2 (soldas) e 6.6.2 (pressão "
    "de contato em superfícies usinadas).",
    "AISC 360-16 — J10 Flanges and Webs with Concentrated Forces (mesma origem das expressões).",
)


@dataclass(frozen=True)
class ForcaLocalizada:
    """Uma força transversal na mesa, centrada na alma.

    ``ln``: comprimento de atuação ao longo da barra (mm); ``largura``: largura de atuação no
    sentido transversal (mm, só para a 5.7.2.1); ``distancia``: da seção da força à extremidade
    mais próxima da barra (mm); ``mesa_comprimida``: a força atua na mesa comprimida pela flexão
    (é o caso que pede a 5.7.5); ``M_Sd``: momento fletor de cálculo na seção (kN·m).
    """

    nome: str = "Reação de apoio"
    F: float = 150.0  # kN
    tipo: str = COMPRESSAO
    ln: float = 100.0
    largura: float = 100.0
    distancia: float = 0.0
    mesa_comprimida: bool = False
    M_Sd: float = 0.0


@dataclass(frozen=True)
class Enrijecedor:
    """Enrijecedores transversais na seção da força (iguais para todas as forças que precisarem)."""

    bs: float = 80.0  # largura de cada enrijecedor (mm)
    ts: float = 9.5  # espessura (mm)
    dois_lados: bool = True
    posicao: str = EXTREMIDADE
    corte: float = 20.0  # recorte junto à mesa (mm), para livrar o raio ou o filete mesa–alma
    ajustado: bool = True  # ponta ajustada (contato) com a mesa carregada; senão, soldada
    aco: str = "ASTM A36"
    perna_alma: float = 6.0  # filete enrijecedor–alma (mm), dos dois lados de cada enrijecedor
    perna_mesa: float = 6.0  # filete enrijecedor–mesa (mm), quando não ajustado
    eletrodo: str = "E70"
    altura_total: bool = True  # até a mesa oposta (obrigatório na 5.7.9.3)


@dataclass(frozen=True)
class EntradaForcas:
    familia: str = pi.FAMILIA_W
    perfil: str = "W 410 x 46,1"
    # perfil soldado (familia = FAMILIA_SOLDADO)
    d: float = 500.0
    bf: float = 200.0
    tf: float = 12.5
    tw: float = 6.3
    filete: float = 5.0
    aco: str = "ASTM A572 Gr 50"
    gama_a1: float = pi.GAMA_A1
    gama_a2: float = pi.GAMA_A2
    E: float = pi.E_ACO
    forcas: tuple[ForcaLocalizada, ...] = (
        ForcaLocalizada(),
        ForcaLocalizada("Equipamento no vão", 120.0, COMPRESSAO, 150.0, 150.0, 2500.0, True, 180.0),
    )
    comprimento_destravado: float = 3000.0  # ℓ da 5.7.5 (mm)
    rotacao_impedida: bool = True  # rotação da mesa carregada impedida (5.7.5.2 a)
    deslocamento_lateral_impedido: bool = False  # 5.7.5.1: impedido dispensa a verificação
    extremidade_livre: bool = False  # 5.7.8: apoio sem restrição à rotação e alma livre
    usar_enrijecedor: bool = False
    enrijecedor: Enrijecedor = field(default_factory=Enrijecedor)


def obter_perfil(e: EntradaForcas) -> pi.PerfilI:
    if e.familia == pi.FAMILIA_SOLDADO:
        return pi.soldado(e.d, e.bf, e.tf, e.tw, e.filete)
    return pi.perfil(e.perfil)


def validar(e: EntradaForcas) -> list[str]:
    erros: list[str] = []
    if e.familia == pi.FAMILIA_SOLDADO:
        try:
            pi.soldado(e.d, e.bf, e.tf, e.tw, e.filete)
        except ValueError as exc:
            erros.append(f"Perfil soldado: {exc}")
    elif e.perfil not in pi.nomes(e.familia):
        erros.append("Escolha um perfil do catálogo.")
    if e.aco not in pi.ACOS:
        erros.append("Escolha o aço do perfil.")
    if not e.forcas:
        erros.append("Informe pelo menos uma força.")
    for f in e.forcas:
        if f.F < 0:
            erros.append(f"{f.nome}: a força é o valor absoluto (o tipo diz o sentido).")
        if f.ln < 0 or f.largura < 0 or f.distancia < 0:
            erros.append(f"{f.nome}: comprimentos e distâncias não podem ser negativos.")
        if f.tipo not in TIPOS:
            erros.append(f"{f.nome}: tipo de força desconhecido.")
    if e.comprimento_destravado <= 0:
        erros.append("O comprimento destravado ℓ deve ser positivo.")
    if e.usar_enrijecedor:
        s = e.enrijecedor
        if s.bs <= 0 or s.ts <= 0:
            erros.append("Enrijecedor: largura e espessura devem ser positivas.")
        if s.corte < 0 or s.corte >= s.bs:
            erros.append("Enrijecedor: o recorte deve ser menor que a largura.")
        if s.aco not in pi.ACOS:
            erros.append("Enrijecedor: escolha o aço.")
    return erros


# ---------------------------------------------------------------- resistências (N, entradas em mm/MPa)
def flexao_local_da_mesa(p: pi.PerfilI, fy: float, g1: float, perto_da_ponta: bool) -> float:
    """5.7.2.2 e 5.7.2.3: 6,25·t_f²·f_y/γ_a1, à metade a menos de 10·t_f da ponta."""
    return (0.5 if perto_da_ponta else 1.0) * 6.25 * p.tf**2 * fy / g1


def escoamento_local_da_alma(p: pi.PerfilI, fy: float, g1: float, ln: float, perto: bool) -> float:
    """5.7.3.2: 1,10·(5k + ℓ_n)·f_y·t_w/γ_a1, ou com 2,5k a até d da ponta."""
    return 1.10 * ((2.5 if perto else 5.0) * p.k + ln) * fy * p.tw / g1


def enrugamento_da_alma(
    p: pi.PerfilI, fy: float, E: float, g1: float, ln: float, perto: bool
) -> tuple[float, str]:
    """5.7.4.2 a) e b). Devolve a força (N) e o item usado."""
    raiz = math.sqrt(E * fy * p.tf / p.tw)
    razao = (p.tw / p.tf) ** 1.5
    if not perto:
        return 0.66 * p.tw**2 / g1 * (1 + 3 * (ln / p.d) * razao) * raiz, "5.7.4.2 a)"
    if ln / p.d <= 0.2:
        return 0.33 * p.tw**2 / g1 * (1 + 3 * (ln / p.d) * razao) * raiz, "5.7.4.2 b), ℓ_n/d ≤ 0,2"
    return (
        0.33 * p.tw**2 / g1 * (1 + (4 * ln / p.d - 0.2) * razao) * raiz,
        "5.7.4.2 b), ℓ_n/d > 0,2",
    )


def flambagem_lateral_da_alma(
    p: pi.PerfilI, fy: float, E: float, g1: float, ell: float, M_Sd: float, rotacao_impedida: bool
) -> tuple[float | None, float, float]:
    """5.7.5.2: devolve (F_Rd em N ou None quando 5.7.5.3 dispensa, a esbeltez relativa, C_r)."""
    rel = (p.h / p.tw) / (ell / p.bf)
    Cr = 32 * E if abs(M_Sd) < pi.mr_x(p, fy) else 16 * E
    base = Cr * p.tw**3 * p.tf / (g1 * p.h**2)
    if rotacao_impedida:
        if rel > 2.30:
            return None, rel, Cr
        return base * (0.94 + 0.37 * rel**3), rel, Cr
    if rel > 1.70:
        return None, rel, Cr
    return base * 0.37 * rel**3, rel, Cr


def instabilidade_por_compressao(
    p: pi.PerfilI, fy: float, E: float, g1: float, perto: bool
) -> float:
    """5.7.6.2 e 5.7.6.3: 24·t_w³·√(E·f_y)/(γ_a1·h), à metade a menos de d/2 da ponta."""
    return (0.5 if perto else 1.0) * 24 * p.tw**3 * math.sqrt(E * fy) / (g1 * p.h)


def painel_de_alma(
    p: pi.PerfilI, fy: float, E: float, g1: float, N_Sd: float, com_enrijecedores: bool
) -> tuple[float, str]:
    """5.7.7.1: F_Rd do painel de alma do pilar (N), com A_w = d_c·t_w e o V_Rd da 5.4.3.

    O painel entre enrijecedores alinhados com as mesas da viga tem a/h pequeno: com eles, o
    programa toma k_v = 5 + 5/(a/h)² com a = altura da viga ≈ h (k_v = 10); sem eles, k_v = 5.
    """
    kv = 10.0 if com_enrijecedores else 5.0
    lam = p.h / p.tw
    lp = 1.10 * math.sqrt(kv * E / fy)
    lr = 1.37 * math.sqrt(kv * E / fy)
    Aw = p.d * p.tw
    Vpl = 0.60 * Aw * fy
    if lam <= lp:
        Vrd = Vpl / g1
        faixa = "λ ≤ λ_p"
    elif lam <= lr:
        Vrd = lp / lam * Vpl / g1
        faixa = "λ_p < λ ≤ λ_r"
    else:
        Vrd = 1.24 * (lp / lam) ** 2 * Vpl / g1
        faixa = "λ > λ_r"
    Npl = p.A * fy
    fator = 1.0 if N_Sd <= 0.4 * Npl else max(1.4 - N_Sd / Npl, 0.0)
    return Vrd * fator, f"V_Rd (5.4.3, k_v = {kv:g}, {faixa}) × {pi.numero(fator, 3)}"


# ---------------------------------------------------------------- linhas da verificação
def _kn(valor_N: float) -> float:
    return valor_N / 1000.0


def _n(valor: float, casas: int = 1) -> str:
    return pi.numero(valor, casas)


@dataclass
class ResultadoDaForca:
    forca: ForcaLocalizada
    linhas: list[Verificacao]
    menor_resistencia: float | None  # kN, a menor resistência da alma/mesa que se aplica
    precisa_enrijecedor: bool
    precisa_altura_total: bool  # 5.7.5 ou 5.7.6 não passou (5.7.9.3)
    enrijecedor: list[Verificacao]


@dataclass
class ResultadoForcas:
    entrada: EntradaForcas
    perfil: pi.PerfilI
    fy: float
    forcas: list[ResultadoDaForca]
    gerais: list[Verificacao]
    avisos: list[str]

    @property
    def grupos(self) -> list[vm.Grupo]:
        grupos = [vm.Grupo("Perfil e apoio", self.gerais)] if self.gerais else []
        for r in self.forcas:
            grupos.append(vm.Grupo(f"Força: {r.forca.nome}", r.linhas))
            if r.enrijecedor:
                grupos.append(vm.Grupo(f"Enrijecedores: {r.forca.nome}", r.enrijecedor))
        return grupos

    @property
    def linhas(self) -> list[Verificacao]:
        return vm.decisivas(self.grupos)

    @property
    def situacao(self) -> str:
        return vm.situacao(self.linhas)

    @property
    def utilizacao_maxima(self) -> float:
        return vm.utilizacao_maxima(self.linhas)


def _cobre(linha: Verificacao, tem_enrijecedor: bool) -> Verificacao:
    """Com enrijecedor, a linha da alma que não passa vira informativa (a força vai a ele)."""
    if tem_enrijecedor and linha.status == "NÃO OK":
        return replace(
            linha,
            status="INFO",
            tipo="informativo",
            formula=linha.formula + " — excedida; os enrijecedores levam a diferença (5.7.9)",
        )
    return linha


def _linhas_da_forca(
    e: EntradaForcas, p: pi.PerfilI, fy: float, f: ForcaLocalizada
) -> tuple[list[Verificacao], list[tuple[str, float]], bool]:
    """As linhas de 5.7.2 a 5.7.6 de uma força; devolve também as resistências (nome, kN) e se a
    falha está num estado que exige o enrijecedor de altura total (5.7.5 ou 5.7.6)."""
    g1, E = e.gama_a1, e.E
    F = f.F
    linhas: list[Verificacao] = []
    resist: list[tuple[str, float]] = []
    altura_total = False
    ref = "ABNT NBR 8800:2025, "
    compressao = f.tipo in (COMPRESSAO, PAR)
    # 5.7.2 flexão local da mesa (força que traciona a alma)
    if f.tipo == TRACAO:
        if f.largura < 0.15 * p.bf:
            linhas.append(
                vm.linha_na(
                    "Flexão local da mesa",
                    "kN",
                    ref + "5.7.2.1",
                    f"largura de atuação {_n(f.largura)} mm < 0,15·b_f = {_n(0.15 * p.bf)} mm: "
                    "dispensada",
                )
            )
        else:
            perto = f.distancia < 10 * p.tf
            rd = _kn(flexao_local_da_mesa(p, fy, g1, perto))
            resist.append(("flexão local da mesa", rd))
            linhas.append(
                Verificacao(
                    "Flexão local da mesa",
                    F,
                    rd,
                    "kN",
                    ref + ("5.7.2.2 e 5.7.2.3" if perto else "5.7.2.2"),
                    f"6,25·t_f²·f_y/γ_a1{' × 0,5 (a menos de 10·t_f da ponta)' if perto else ''}"
                    f", t_f = {_n(p.tf, 2)} mm",
                    equacoes=(
                        "F_Rd = 6,25 t_f^2 f_y / γ_a1",
                        f"F_Rd = {'0,5 · ' if perto else ''}6,25 · {_n(p.tf, 2)}^2 · {_n(fy, 0)}"
                        f" / {_n(g1, 2)} = {_n(rd, 1)} kN",
                    ),
                )
            )
    # 5.7.3 escoamento local da alma
    perto_d = f.distancia <= p.d
    rd = _kn(escoamento_local_da_alma(p, fy, g1, f.ln, perto_d))
    resist.append(("escoamento local da alma", rd))
    mult = "2,5" if perto_d else "5"
    linhas.append(
        Verificacao(
            "Escoamento local da alma",
            F,
            rd,
            "kN",
            ref + ("5.7.3.2 b)" if perto_d else "5.7.3.2 a)"),
            f"1,10·({mult}·k + ℓ_n)·f_y·t_w/γ_a1, k = {_n(p.k, 1)} mm, ℓ_n = {_n(f.ln, 0)} mm, "
            f"t_w = {_n(p.tw, 2)} mm",
            equacoes=(
                f"F_Rd = 1,10 ({mult} k + ℓ_n) f_y t_w / γ_a1",
                f"F_Rd = 1,10 · ({mult} · {_n(p.k, 1)} + {_n(f.ln, 0)}) · {_n(fy, 0)} · "
                f"{_n(p.tw, 2)} / {_n(g1, 2)} = {_n(rd, 1)} kN",
            ),
        )
    )
    if compressao:
        # 5.7.4 enrugamento
        perto = f.distancia < p.d / 2
        valor, item = enrugamento_da_alma(p, fy, E, g1, f.ln, perto)
        rd = _kn(valor)
        resist.append(("enrugamento da alma", rd))
        coef = "0,66" if not perto else "0,33"
        termo = "(4 ℓ_n/d - 0,2)" if perto and f.ln / p.d > 0.2 else "3 (ℓ_n/d)"
        linhas.append(
            Verificacao(
                "Enrugamento da alma",
                F,
                rd,
                "kN",
                ref + item,
                f"{coef}·t_w²·[1 + …·(t_w/t_f)^1,5]·√(E·f_y·t_f/t_w)/γ_a1, ℓ_n/d = "
                f"{_n(f.ln / p.d, 3)}{', a menos de d/2 da ponta' if perto else ''}",
                equacoes=(
                    f"F_Rd = {coef} t_w^2 / γ_a1 [1 + {termo} (t_w/t_f)^1,5] √(E f_y t_f / t_w)",
                    f"F_Rd = {_n(rd, 1)} kN",
                ),
            )
        )
        # 5.7.5 flambagem lateral da alma
        if f.tipo == COMPRESSAO and f.mesa_comprimida and not e.deslocamento_lateral_impedido:
            valor_fl, rel, Cr = flambagem_lateral_da_alma(
                p, fy, E, g1, e.comprimento_destravado, f.M_Sd * 1e6, e.rotacao_impedida
            )
            limite = 2.30 if e.rotacao_impedida else 1.70
            if valor_fl is None:
                linhas.append(
                    vm.linha_na(
                        "Flambagem lateral da alma",
                        "kN",
                        ref + "5.7.5.3",
                        f"(h/t_w)/(ℓ/b_f) = {_n(rel, 2)} > {_n(limite, 2)}: o estado-limite não "
                        "ocorre",
                    )
                )
            else:
                rd = _kn(valor_fl)
                resist.append(("flambagem lateral da alma", rd))
                ok = F <= rd
                altura_total = altura_total or not ok
                linhas.append(
                    Verificacao(
                        "Flambagem lateral da alma",
                        F,
                        rd,
                        "kN",
                        ref + ("5.7.5.2 a)" if e.rotacao_impedida else "5.7.5.2 b)"),
                        f"C_r·t_w³·t_f/(γ_a1·h²)·[{'0,94 + ' if e.rotacao_impedida else ''}"
                        f"0,37·({_n(rel, 2)})³], C_r = {'32' if Cr > 20 * E else '16'}·E, "
                        f"h = {_n(p.h, 1)} mm, ℓ = {_n(e.comprimento_destravado, 0)} mm"
                        + ("" if ok else (
                            "; alternativa: contenção lateral na mesa tracionada (5.7.5.4, 4.12)"
                            if e.rotacao_impedida else
                            "; exige contenção lateral nas duas mesas (5.7.5.5, 4.12)"
                        )),
                    )
                )  # fmt: skip
        elif f.tipo == COMPRESSAO and f.mesa_comprimida:
            linhas.append(
                vm.linha_na(
                    "Flambagem lateral da alma",
                    "kN",
                    ref + "5.7.5.1",
                    "deslocamento lateral relativo entre as mesas impedido na seção",
                )
            )
        # 5.7.6 par de forças
        if f.tipo == PAR:
            perto = f.distancia < p.d / 2
            rd = _kn(instabilidade_por_compressao(p, fy, E, g1, perto))
            resist.append(("instabilidade da alma por compressão", rd))
            altura_total = altura_total or F > rd
            linhas.append(
                Verificacao(
                    "Instabilidade da alma por compressão",
                    F,
                    rd,
                    "kN",
                    ref + ("5.7.6.2 e 5.7.6.3" if perto else "5.7.6.2"),
                    f"24·t_w³·√(E·f_y)/(γ_a1·h){' × 0,5 (a menos de d/2 da ponta)' if perto else ''}"
                    f", h = {_n(p.h, 1)} mm",
                    equacoes=(
                        "F_Rd = 24 t_w^3 √(E f_y) / (γ_a1 h)",
                        f"F_Rd = {_n(rd, 1)} kN",
                    ),
                )
            )
    return linhas, resist, altura_total


def _secao_do_enrijecedor(p: pi.PerfilI, s: Enrijecedor) -> tuple[float, float, float]:
    """5.7.9.4: área, inércia em torno do plano médio da alma e a faixa de alma (mm², mm⁴, mm)."""
    faixa = (12 if s.posicao == EXTREMIDADE else 25) * p.tw
    n = 2 if s.dois_lados else 1
    A = n * s.bs * s.ts + faixa * p.tw
    if s.dois_lados:
        inercia = s.ts * (2 * s.bs + p.tw) ** 3 / 12 + (faixa - s.ts) * p.tw**3 / 12
    else:
        braco = s.bs / 2 + p.tw / 2
        # eixo no plano médio da alma (a norma); o centroide desloca-se, mas o eixo é o da alma
        inercia = s.ts * s.bs**3 / 12 + s.bs * s.ts * braco**2 + faixa * p.tw**3 / 12
    return A, inercia, faixa


def _linhas_do_enrijecedor(
    e: EntradaForcas,
    p: pi.PerfilI,
    fy_perfil: float,
    f: ForcaLocalizada,
    menor: float,
    altura_total: bool,
    *,
    largura_que_entrega: float | None = None,
    espessura_que_entrega: float | None = None,
) -> list[Verificacao]:
    """``largura_que_entrega``/``espessura_que_entrega``: a mesa ou chapa que entrega a força
    (5.7.9.5); sem elas, a própria mesa carregada."""
    s = e.enrijecedor
    b_ent = largura_que_entrega or p.bf
    t_ent = espessura_que_entrega or p.tf
    fy, fu = pi.ACOS[s.aco]
    g1, g2, E = e.gama_a1, e.gama_a2, e.E
    ref = "ABNT NBR 8800:2025, "
    n = 2 if s.dois_lados else 1
    F = f.F
    diferenca = max(F - menor, 0.0)
    linhas: list[Verificacao] = []
    # proporções 5.7.9.5
    linhas.append(
        vm.linha_limite(
            "Largura do enrijecedor",
            s.bs + p.tw / 2,
            b_ent / 3,
            "mm",
            ref + "5.7.9.5 a)",
            f"b_s + t_w/2 = {_n(s.bs + p.tw / 2)} mm ≥ b/3 = {_n(b_ent / 3)} mm (b = largura da "
            "mesa que recebe ou entrega a força)",
            minimo=True,
        )
    )
    t_min = max(t_ent / 2, s.bs / 16)
    linhas.append(
        vm.linha_limite(
            "Espessura do enrijecedor",
            s.ts,
            t_min,
            "mm",
            ref + "5.7.9.5 b)",
            f"t_s ≥ máx(t/2; b_s/16) = máx({_n(t_ent / 2, 2)}; {_n(s.bs / 16, 2)}) mm",
            minimo=True,
        )
    )
    raiz = math.sqrt(E / fy)
    linhas.append(
        vm.linha_limite(
            "Esbeltez local do enrijecedor",
            s.bs / s.ts,
            0.56 * raiz,
            "",
            ref + "5.1.2 (Tabela F.1, grupo 3)",
            f"b_s/t_s ≤ 0,56·√(E/f_y) = {_n(0.56 * raiz, 2)}: sem flambagem local",
        )
    )
    if altura_total and not s.altura_total:
        linhas.append(
            Verificacao(
                "Altura do enrijecedor",
                None,
                None,
                "",
                ref + "5.7.9.3",
                "a flambagem lateral ou a instabilidade da alma exige enrijecedor em toda a "
                "altura da alma, ligado à mesa oposta",
                status="NÃO OK",
                tipo="limite",
            )
        )
    comprimido = f.tipo in (COMPRESSAO, PAR)
    contato = n * (s.bs - s.corte) * s.ts
    if comprimido:
        # 5.7.9.4: barra comprimida (enrijecedor + faixa de alma), L = 0,75·h, eixo no plano da alma
        A, inercia, faixa = _secao_do_enrijecedor(p, s)
        r = math.sqrt(inercia / A)
        L = 0.75 * p.h
        fy_min = min(fy, fy_perfil)
        lam0 = (L / r) / math.pi * math.sqrt(fy_min / E)
        chi = nb.fator_chi(lam0)
        rd = chi * A * fy_min / g1 / 1000
        linhas.append(
            Verificacao(
                "Enrijecedor como barra comprimida",
                F,
                rd,
                "kN",
                ref + "5.7.9.4 e 5.3",
                f"χ·A·f_y/γ_a1, A = {_n(A, 0)} mm² (enrijecedores + faixa de {_n(faixa, 0)} mm de "
                f"alma), r = {_n(r, 1)} mm, L = 0,75·h = {_n(L, 0)} mm, λ₀ = {_n(lam0, 3)}, "
                f"χ = {_n(chi, 3)}; força total da seção",
                equacoes=(
                    "N_c,Rd = χ A f_y / γ_a1",
                    f"N_c,Rd = {_n(chi, 3)} · {_n(A, 0)} · {_n(fy_min, 0)} / {_n(g1, 2)} = "
                    f"{_n(rd, 1)} kN",
                ),
            )
        )
        if s.ajustado:
            rd_c = 1.8 * contato * min(fy, fy_perfil) / g2 / 1000
            linhas.append(
                Verificacao(
                    "Esmagamento da ponta ajustada",
                    diferenca,
                    rd_c,
                    "kN",
                    ref + "5.7.9.2 e 6.6.2",
                    f"1,8·A·f_y/γ_a2, A = {n}·(b_s − recorte)·t_s = {_n(contato, 0)} mm²; "
                    "solicitante = força − resistência da alma",
                )
            )
    else:
        # 5.7.9.1: tração (5.2) — escoamento da área bruta e ruptura da área ligada à mesa
        Ag = n * s.bs * s.ts
        rd_esc = Ag * fy / g1 / 1000
        rd_rup = contato * fu / g2 / 1000
        linhas.append(
            Verificacao(
                "Enrijecedor tracionado: escoamento",
                diferenca,
                rd_esc,
                "kN",
                ref + "5.7.9.1 e 5.2.2 a)",
                f"A_g·f_y/γ_a1, A_g = {_n(Ag, 0)} mm²; solicitante = força − resistência",
            )
        )
        linhas.append(
            Verificacao(
                "Enrijecedor tracionado: ruptura",
                diferenca,
                rd_rup,
                "kN",
                ref + "5.7.9.1 e 5.2.2 b)",
                f"A_e·f_u/γ_a2, A_e = área ligada à mesa = {_n(contato, 0)} mm²",
            )
        )
    # soldas: a diferença vai da mesa ao enrijecedor e dele à alma
    fw = ELETRODOS[s.eletrodo]
    altura = (p.h_interna if (s.altura_total or altura_total) else 0.75 * p.h_interna) - 2 * s.corte
    altura = max(altura, 0.0)
    por_mm_alma = sd.resistencia_filete_por_mm(s.perna_alma, fw, GAMA_W2)
    rd_alma = por_mm_alma * 2 * n * altura
    linhas.append(
        Verificacao(
            "Solda do enrijecedor na alma",
            diferenca,
            rd_alma,
            "kN",
            ref + "5.7.9.1 a 5.7.9.3 e 6.2.5 (Tabela 9)",
            f"0,60·f_w·0,707·a/γ_w2 × 2 filetes × {n} enrijecedor(es) × {_n(altura, 0)} mm "
            f"(a = {_n(s.perna_alma, 1)} mm, {s.eletrodo}); solicitante = força − resistência",
        )
    )
    if not (comprimido and s.ajustado):
        comprimento = s.bs - s.corte
        rd_mesa = sd.resistencia_filete_por_mm(s.perna_mesa, fw, GAMA_W2) * 2 * n * comprimento
        linhas.append(
            Verificacao(
                "Solda do enrijecedor na mesa carregada",
                diferenca,
                rd_mesa,
                "kN",
                ref + "5.7.9.1 a 5.7.9.3 e 6.2.5 (Tabela 9)",
                f"0,60·f_w·0,707·a/γ_w2 × 2 filetes × {n} × {_n(comprimento, 0)} mm "
                f"(a = {_n(s.perna_mesa, 1)} mm)",
            )
        )
    linhas += sd.limites_do_filete(
        sd.NBR_2025, s.perna_alma, min(s.ts, p.tw), None, altura, "Filete na alma"
    )
    return linhas


def sugestao_de_enrijecedor(p: pi.PerfilI) -> tuple[float, float]:
    """Menores b_s e t_s (arredondados) que atendem às proporções da 5.7.9.5."""
    bs = math.ceil(max(p.bf / 3 - p.tw / 2, 40.0) / 5) * 5
    ts_min = max(p.tf / 2, bs / 16)
    for t in (6.3, 8.0, 9.5, 12.5, 16.0, 19.0, 22.4, 25.0, 31.5, 37.5):
        if t >= ts_min:
            return bs, t
    return bs, ts_min


def calcular(e: EntradaForcas) -> ResultadoForcas:
    p = obter_perfil(e)
    fy = pi.ACOS[e.aco][0]
    avisos = pi.avisos_do_perfil(p)
    gerais: list[Verificacao] = []
    if e.extremidade_livre:
        gerais.append(
            Verificacao(
                "Apoio sem restrição à rotação com alma livre",
                None,
                None,
                "",
                "ABNT NBR 8800:2025, 5.7.8",
                "enrijecedores soldados às mesas e à alma, em toda a altura, são obrigatórios"
                + (" — previstos" if e.usar_enrijecedor and e.enrijecedor.altura_total else ""),
                status="OK" if e.usar_enrijecedor and e.enrijecedor.altura_total else "NÃO OK",
                tipo="limite",
            )
        )
    resultados: list[ResultadoDaForca] = []
    for f in e.forcas:
        linhas, resist, altura_total = _linhas_da_forca(e, p, fy, f)
        precisa = any(v.status == "NÃO OK" for v in linhas)
        menor = min((rd for _, rd in resist), default=None)
        enr: list[Verificacao] = []
        if precisa and e.usar_enrijecedor:
            linhas = [_cobre(v, True) for v in linhas]
            enr = _linhas_do_enrijecedor(e, p, fy, f, menor or 0.0, altura_total)
        elif precisa:
            bs, ts = sugestao_de_enrijecedor(p)
            linhas.append(
                Verificacao(
                    "Enrijecedores necessários",
                    None,
                    None,
                    "",
                    "ABNT NBR 8800:2025, 5.7.2.4, 5.7.3.3, 5.7.4.3, 5.7.5.4, 5.7.6.4",
                    f"a seção precisa de enrijecedores (por exemplo, {bs:g} × {pi.numero(ts, 1)} "
                    "mm de cada lado) — ligue a opção de enrijecedores para verificá-los",
                    status="NÃO OK",
                    tipo="limite",
                )
            )
        resultados.append(ResultadoDaForca(f, linhas, menor, precisa, altura_total, enr))
    return ResultadoForcas(e, p, fy, resultados, gerais, avisos)


# ---------------------------------------------------------------- registro e memorial
def entradas_do_registro(r: ResultadoForcas) -> dict[str, Any]:
    e = r.entrada
    entradas: dict[str, Any] = {
        "perfil": r.perfil.descricao,
        "aco": f"{e.aco} (f_y = {_n(r.fy, 0)} MPa)",
        "forcas": "; ".join(
            f"{f.nome}: {_n(f.F, 1)} kN, {f.tipo.split(' (')[0].lower()}, ℓ_n = {_n(f.ln, 0)} mm, "
            f"a {_n(f.distancia, 0)} mm da extremidade"
            for f in e.forcas
        ),  # fmt: skip
        "comprimento_destravado_mm": e.comprimento_destravado,
        "rotacao_da_mesa_impedida": e.rotacao_impedida,
        "deslocamento_lateral_impedido": e.deslocamento_lateral_impedido,
    }
    if e.usar_enrijecedor:
        s = e.enrijecedor
        entradas["enrijecedores"] = (
            f"{'2' if s.dois_lados else '1'} × {_n(s.bs, 0)} × {_n(s.ts, 1)} mm, {s.aco}, "
            f"recorte {_n(s.corte, 0)} mm, {'ajustado' if s.ajustado else 'soldado'} à mesa "
            f"carregada, {s.posicao.split(' (')[0].lower()}"
        )
    return entradas


def registro(r: ResultadoForcas) -> dict[str, Any]:
    premissas = [
        "Forças centradas na alma, aplicadas na face externa da mesa (5.7.1).",
        "Perfil laminado: k = t_f + raio de concordância e h = distância entre as faces internas "
        "das mesas menos os raios; perfil soldado: k = t_f + perna do filete mesa–alma.",
        "Com enrijecedores, a barra comprimida (5.7.9.4) é verificada para a força total da "
        "seção; o esmagamento das pontas ajustadas, a tração e as soldas, para a diferença entre "
        "a força e a menor resistência da alma (5.7.9.1 a 5.7.9.3).",
    ]
    return vm.registro_padrao(
        modulo_id=MODULO_ID,
        modulo_titulo=MODULO_TITULO,
        titulo=f"Forças localizadas — {r.perfil.nome}",
        grupos=r.grupos,
        entradas=entradas_do_registro(r),
        metodo=(
            "Verificação das mesas e da alma de perfil I/H sob forças transversais localizadas "
            "pela ABNT NBR 8800:2025, 5.7: flexão local da mesa, escoamento local e enrugamento "
            "da alma, flambagem lateral da alma, instabilidade por compressão e enrijecedores."
        ),
        premissas=premissas,
        referencias=REFERENCIAS,
        objeto=f"A seção do perfil {r.perfil.nome}",
        alertas=r.avisos,
    )


def com(e: EntradaForcas, **mudancas: Any) -> EntradaForcas:
    return replace(e, **mudancas)


def forcas_de_tabela(linhas: Sequence[dict[str, Any]]) -> tuple[ForcaLocalizada, ...]:
    """As forças da tabela da página (as linhas vazias ou incompletas são puladas)."""

    def numero(valor: Any, padrao: float = 0.0) -> float:
        try:
            x = float(valor)
        except (TypeError, ValueError):
            return padrao
        return x if math.isfinite(x) else padrao

    forcas: list[ForcaLocalizada] = []
    for i, linha in enumerate(linhas):
        nome = str(linha.get("Força") or "").strip() or f"Força {i + 1}"
        tipo = str(linha.get("Tipo") or COMPRESSAO)
        if tipo not in TIPOS:
            tipo = COMPRESSAO
        forcas.append(
            ForcaLocalizada(
                nome=nome,
                F=abs(numero(linha.get("F_Sd (kN)"))),
                tipo=tipo,
                ln=max(numero(linha.get("ℓn (mm)")), 0.0),
                largura=max(numero(linha.get("Largura (mm)")), 0.0),
                distancia=max(numero(linha.get("Dist. à ponta (mm)")), 0.0),
                mesa_comprimida=bool(linha.get("Mesa comprimida") or False),
                M_Sd=numero(linha.get("M_Sd (kN·m)")),
            )
        )
    return tuple(forcas)


def tabela_das_forcas(forcas: Sequence[ForcaLocalizada]) -> list[dict[str, Any]]:
    return [
        {
            "Força": f.nome,
            "F_Sd (kN)": f.F,
            "Tipo": f.tipo,
            "ℓn (mm)": f.ln,
            "Largura (mm)": f.largura,
            "Dist. à ponta (mm)": f.distancia,
            "Mesa comprimida": f.mesa_comprimida,
            "M_Sd (kN·m)": f.M_Sd,
        }
        for f in forcas
    ]
