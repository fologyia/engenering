"""As seções do montador de fórmulas, escritas em letras.

σ e τ máximos raramente caem no mesmo ponto: na flexão com cortante, a fibra externa tem o maior σ e
τ zero, e a linha neutra o contrário. Por isso cada seção diz, ponto a ponto, quanto cada esforço vale
ali. O critério roda em cada ponto, e quem manda é o pior deles. Somar os máximos dá uma tensão que
não existe em lugar nenhum da peça.

XX e YY são os eixos da flexão: M_x tem h como braço, e M_y tem b. Com os dois juntos, o pior ponto da
seção retangular é o canto, onde as duas tensões somam. Na seção redonda não há canto: os momentos se
compõem como vetores, e a fibra mais tensa fica na direção da resultante.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import sympy as sp

from core import elementos_vigas as ev
from core import geometria_da_secao as gs
from core import montador_grandezas as g
from core.montador_grandezas import Grandeza

PI = sp.pi
ZERO = sp.S.Zero
LADO_H = "h é o lado maior"
LADO_B = "b é o lado maior"
LADOS = (LADO_H, LADO_B)
EIXO_XX = "XX"
EIXO_YY = "YY"
EIXOS = (EIXO_XX, EIXO_YY)
_SALTO_DE_LARGURA = 0.2  # acima disso, a mudança de largura é uma junção, como alma e mesa
_ESFORCOS = {"Mx": "mx", "My": "my", "N": "n", "Vy": "vy", "Vx": "vx", "T": "t"}


@dataclass(frozen=True)
class Validade:
    """``expressao`` precisa dar zero ou mais. Com os números prontos, o programa confere."""

    expressao: sp.Expr
    mensagem: str


@dataclass(frozen=True)
class Ponto:
    """Quanto cada esforço vale neste ponto: σ = M_x·por_momento + N·por_normal, e assim por diante."""

    nome: str
    por_momento: sp.Expr = ZERO
    por_normal: sp.Expr = ZERO
    por_cortante: sp.Expr = ZERO
    por_torque: sp.Expr = ZERO
    por_momento_y: sp.Expr = ZERO
    por_cortante_x: sp.Expr = ZERO  # na mesma direção do τ dos outros esforços
    cruzado_x: sp.Expr = ZERO  # V_x perpendicular a V_y: entra pela raiz da soma dos quadrados
    exige: tuple[str, ...] = ()  # o ponto só existe com estes esforços: o canto pede mx e my
    nome_so_my: str = ""
    nome_com_my: str = ""


@dataclass(frozen=True)
class Secao:
    nome: str
    area: sp.Expr
    inercia: sp.Expr  # em XX
    inercia_min: sp.Expr
    fibra: sp.Expr
    polar: sp.Expr
    pontos: tuple[Ponto, ...]
    grandezas: tuple[Grandeza, ...]
    validade: tuple[Validade, ...] = ()
    hipoteses: tuple[str, ...] = ()
    pressao: tuple[sp.Expr, sp.Expr] | None = None  # σ longitudinal e σ circunferencial, por p
    avisos: tuple[str, ...] = ()
    validade_do_lado: tuple[Validade, ...] = ()  # só pesa na torção e na inércia fraca
    inercia_y: sp.Expr = ZERO
    redonda: bool = False

    def propriedades(self) -> tuple[tuple[str, sp.Expr], ...]:
        """Para o passo a passo."""
        return (("A", self.area), ("I", self.inercia), ("c", self.fibra), ("J", self.polar))


@dataclass(frozen=True)
class Tensao:
    ponto: str
    sx: sp.Expr = ZERO
    sy: sp.Expr = ZERO
    tau: sp.Expr = ZERO

    @property
    def nula(self) -> bool:
        return self.sx == 0 and self.sy == 0 and self.tau == 0


@dataclass(frozen=True)
class Estado:
    """A seção e os esforços somados até aqui. Vai de bloco em bloco pelo fio da seção."""

    secao: Secao
    validade: tuple[Validade, ...] = ()
    mx: sp.Expr = ZERO
    my: sp.Expr = ZERO
    n: sp.Expr = ZERO
    vy: sp.Expr = ZERO
    vx: sp.Expr = ZERO
    t: sp.Expr = ZERO
    longitudinal: sp.Expr = ZERO  # da pressão
    circunferencial: sp.Expr = ZERO
    forcas_sem_cortante: tuple[str, ...] = ()  # letras de forças com braço que ainda não cortam

    @staticmethod
    def inicial(secao: Secao) -> Estado:
        return Estado(secao, secao.validade)

    def somar(self, esforco: str, valor: sp.Expr) -> Estado:
        campo = _ESFORCOS[esforco]
        estado = replace(self, **{campo: getattr(self, campo) + valor})
        if esforco == "Vy" or esforco == "Vx":
            estado = replace(estado, forcas_sem_cortante=())
        return estado.usando_o_lado() if esforco == "T" else estado

    def lembrar_forca(self, letra: str) -> Estado:
        return replace(self, forcas_sem_cortante=(*self.forcas_sem_cortante, letra))

    def usando_o_lado(self) -> Estado:
        """A conta passou a depender de qual lado é o maior: a hipótese entra na conferência."""
        novas = [v for v in self.secao.validade_do_lado if v not in self.validade]
        return self.com_validade(*novas)

    def multiplicar(self, normal: sp.Expr, cisalhamento: sp.Expr) -> Estado:
        return replace(
            self,
            mx=self.mx * normal,
            my=self.my * normal,
            n=self.n * normal,
            longitudinal=self.longitudinal * normal,
            circunferencial=self.circunferencial * normal,
            vy=self.vy * cisalhamento,
            vx=self.vx * cisalhamento,
            t=self.t * cisalhamento,
        )

    def com_pressao(self, longitudinal: sp.Expr, circunferencial: sp.Expr) -> Estado:
        return replace(
            self,
            longitudinal=self.longitudinal + longitudinal,
            circunferencial=self.circunferencial + circunferencial,
        )

    def com_validade(self, *novas: Validade) -> Estado:
        return replace(self, validade=(*self.validade, *novas))

    def _no_ponto(self, p: Ponto) -> Tensao | None:
        if any(getattr(self, campo) == 0 for campo in p.exige):
            return None
        nome = p.nome
        if self.my != 0 and p.nome_com_my:
            nome = p.nome_com_my
        elif self.mx == 0 and self.my != 0 and p.nome_so_my:
            nome = p.nome_so_my
        sx = (
            self.mx * p.por_momento
            + self.my * p.por_momento_y
            + self.n * p.por_normal
            + self.longitudinal
        )
        linear = self.vy * p.por_cortante + self.vx * p.por_cortante_x + self.t * p.por_torque
        cruzado = self.vx * p.cruzado_x
        tau = sp.sqrt(linear**2 + cruzado**2) if cruzado != 0 else linear
        return Tensao(nome, sx, self.circunferencial, tau)

    def _na_seccao_redonda(self) -> tuple[Tensao, ...]:
        """Os momentos e as cortantes se compõem como vetores. Sinais pelo pior caso.

        A fibra mais tensa fica na direção de M_r. Ali, cortante é a parte de V ao longo da tangente,
        e por isso V_y some quando só há M_x. A 90° dela fica a linha neutra da resultante.
        """
        fibra, neutra = self.secao.pontos
        resultante = sp.sqrt(self.mx**2 + self.my**2)
        if resultante == 0:
            v_fibra, v_neutra = ZERO, sp.sqrt(self.vx**2 + self.vy**2)
        else:
            v_fibra = (self.vx * self.mx + self.vy * self.my) / resultante
            v_neutra = (self.vy * self.mx + self.vx * self.my) / resultante
        normal = self.n * fibra.por_normal + self.longitudinal
        return (
            Tensao(
                fibra.nome,
                resultante * fibra.por_momento + normal,
                self.circunferencial,
                v_fibra * neutra.por_cortante + self.t * fibra.por_torque,
            ),
            Tensao(
                neutra.nome,
                normal,
                self.circunferencial,
                v_neutra * neutra.por_cortante + self.t * neutra.por_torque,
            ),
        )

    @property
    def tensoes(self) -> tuple[Tensao, ...]:
        if self.secao.redonda:
            return self._na_seccao_redonda()
        calculadas = (self._no_ponto(p) for p in self.secao.pontos)
        return tuple(t for t in calculadas if t is not None)


def _redonda(
    nome: str,
    grandezas: tuple[Grandeza, ...],
    d: sp.Expr,
    di: sp.Expr,
    *,
    validade: tuple[Validade, ...] = (),
    hipoteses: tuple[str, ...] = (),
    pressao: tuple[sp.Expr, sp.Expr] | None = None,
) -> Secao:
    area = PI * (d**2 - di**2) / 4
    inercia = PI * (d**4 - di**4) / 64
    polar = 2 * inercia
    fibra = d / 2
    momento_estatico = (d**3 - di**3) / 12
    largura = d - di
    por_t = fibra / polar
    return Secao(
        nome,
        area,
        inercia,
        inercia,
        fibra,
        polar,
        (
            Ponto("fibra externa", fibra / inercia, 1 / area, ZERO, por_t),
            Ponto(
                "linha neutra",
                ZERO,
                1 / area,
                momento_estatico / (inercia * largura),
                por_t,
            ),
        ),
        grandezas,
        validade,
        hipoteses,
        pressao,
        inercia_y=inercia,
        redonda=True,
    )


def circular() -> Secao:
    d = g.D.simbolo
    return _redonda("Circular maciça", (g.D,), d, ZERO)


def tubo_por_parede() -> Secao:
    d, t = g.D.simbolo, g.PAREDE.simbolo
    return _redonda(
        "Tubo circular",
        (g.D, g.PAREDE),
        d,
        d - 2 * t,
        validade=(
            Validade(d - 2 * t, "A parede passa do centro do tubo: d precisa ser maior que 2·t."),
        ),
        hipoteses=("Tubo sem flambagem local da parede: confira em paredes muito finas.",),
        pressao=(d / (4 * t), d / (2 * t)),
    )


def tubo_por_relacao() -> Secao:
    d, k = g.D.simbolo, g.RELACAO.simbolo
    return _redonda(
        "Tubo circular",
        (g.D, g.RELACAO),
        d,
        k * d,
        validade=(Validade(1 - k, "A relação k = d_i/d precisa ficar abaixo de 1."),),
        hipoteses=("Tubo sem flambagem local da parede: confira em paredes muito finas.",),
        pressao=(1 / (2 * (1 - k)), 1 / (1 - k)),
    )


def retangular(lado_maior: str = LADO_H) -> Secao:
    b, h = g.B.simbolo, g.H.simbolo
    maior, menor = (h, b) if lado_maior == LADO_H else (b, h)
    area = b * h
    por_mx = 6 / (b * h**2)
    por_my = 6 / (h * b**2)
    pico = sp.Rational(3, 2) / area
    # Shigley, eq. 3-40: τ = T/(a·c²)·(3 + 1,8·c/a), com a o lado maior. Vale no meio do lado maior.
    por_t = (3 + sp.Rational(9, 5) * menor / maior) / (maior * menor**2)
    trocado = "h" if lado_maior == LADO_B else "b"
    return Secao(
        "Retangular",
        area,
        b * h**3 / 12,
        maior * menor**3 / 12,
        h / 2,
        maior * menor**3 / 3,
        (
            Ponto(
                "fibra externa",
                por_mx,
                1 / area,
                por_torque=por_t,
                por_cortante_x=pico,
                nome_so_my="linha neutra",
            ),
            Ponto(
                "linha neutra",
                por_normal=1 / area,
                por_cortante=pico,
                por_torque=por_t,
                por_momento_y=por_my,
                nome_com_my="fibra externa em YY",
            ),
            Ponto(
                "canto",
                por_mx,
                1 / area,
                por_momento_y=por_my,
                exige=("mx", "my"),
            ),
            Ponto(
                "centro",
                por_normal=1 / area,
                por_cortante=pico,
                cruzado_x=pico,
                exige=("vx", "vy"),
            ),
        ),
        (g.B, g.H),
        (),
        (
            "Na torção da seção retangular, τ do meio do lado maior vale nos dois pontos, a favor da "
            "segurança: no meio do lado menor ele é menor.",
        ),
        validade_do_lado=(
            Validade(
                maior - menor,
                f'Deu {trocado} maior que o outro lado: troque em "Lado maior" na seção, porque a '
                "fórmula da torção e a inércia fraca dependem disso.",
            ),
        ),
        inercia_y=h * b**3 / 12,
    )


def perfil_i() -> Secao:
    bf, h, tf, tw = g.BF.simbolo, g.H.simbolo, g.TF.simbolo, g.TW.simbolo
    alma = h - 2 * tf
    area = 2 * bf * tf + tw * alma
    inercia = (bf * h**3 - (bf - tw) * alma**3) / 12
    inercia_fraca = (2 * tf * bf**3 + alma * tw**3) / 12
    constante = (2 * bf * tf**3 + alma * tw**3) / 3
    q_mesa = bf * tf * (h - tf) / 2
    q_centro = q_mesa + tw * (h / 2 - tf) ** 2 / 2
    por_my_mesa = (bf / 2) / inercia_fraca
    por_my_alma = (tw / 2) / inercia_fraca
    return Secao(
        "Perfil I",
        area,
        inercia,
        inercia_fraca,
        h / 2,
        constante,
        (
            Ponto(
                "fibra externa",
                (h / 2) / inercia,
                1 / area,
                por_torque=tf / constante,
                por_cortante_x=sp.Rational(3, 4) / (bf * tf),
                nome_so_my="meio da mesa",
            ),
            Ponto(
                "ponta da mesa",
                (h / 2) / inercia,
                1 / area,
                por_torque=tf / constante,
                por_momento_y=por_my_mesa,
                exige=("my",),
            ),
            Ponto(
                "junção alma-mesa",
                (h / 2 - tf) / inercia,
                1 / area,
                q_mesa / (inercia * tw),
                tw / constante,
                por_momento_y=por_my_alma,
            ),
            Ponto(
                "linha neutra",
                ZERO,
                1 / area,
                q_centro / (inercia * tw),
                tw / constante,
                por_momento_y=por_my_alma,
            ),
        ),
        (g.BF, g.H, g.TF, g.TW),
        (
            Validade(alma, "A altura precisa ser maior que as duas mesas somadas."),
            Validade(bf - tw, "A mesa precisa ser mais larga que a alma."),
        ),
        (
            "Na torção do perfil I vale a parcela de Saint-Venant, sem o empenamento impedido, que "
            "pode pesar mais em seção aberta.",
            "Sem flambagem local da mesa e da alma nem flambagem lateral da viga.",
            "No perfil I, a cortante V_x fica toda nas mesas.",
        ),
        inercia_y=inercia_fraca,
    )


def _niveis_de_juncao(y: np.ndarray, b: np.ndarray) -> list[int]:
    """Onde a largura pula: o lado estreito do salto, que é onde o cortante aperta."""
    niveis = []
    for i in range(len(y) - 1):
        menor, maior = sorted((float(b[i]), float(b[i + 1])))
        if maior > 0 and menor > 0 and (maior - menor) / maior > _SALTO_DE_LARGURA:
            niveis.append(i if b[i] < b[i + 1] else i + 1)
    return niveis


def _nivel(faixas: gs.Faixas, posicao: float, inercia: float) -> float:
    """τ por unidade de cortante na altura pedida. Num salto de largura, vale o lado largo."""
    distancia = np.abs(faixas.y - posicao)
    perto = np.flatnonzero(distancia <= distancia.min() + 1e-6 * max(abs(faixas.y_topo), 1.0))
    valores = [
        abs(float(faixas.q[i])) / (inercia * float(faixas.b[i]))
        for i in perto.tolist()
        if faixas.b[i] > 0
    ]
    return min(valores) if valores else 0.0


def _cantos(x: np.ndarray, y: np.ndarray) -> list[tuple[float, float]]:
    """Os pontos da borda que podem mandar com M_x e M_y juntos, em módulo: poucos, sem repetir."""
    x_max, y_max = float(x.max()), float(y.max())
    achados: list[tuple[float, float]] = []
    for peso in (0.25, 0.5, 0.75):
        nota = peso * x / x_max + (1.0 - peso) * y / y_max
        i = int(np.argmax(nota))
        ponto = (float(x[i]), float(y[i]))
        if all(abs(ponto[0] - a) + abs(ponto[1] - b) > 1e-6 for a, b in achados):
            achados.append(ponto)
    return achados


def desenhada(nome: str) -> Secao:
    """A seção da prancheta só tem números: o que varia é a escala ``s`` do desenho inteiro."""
    desenho = ev.desenho_salvo(nome)
    p = desenho.analise.prop
    fx, fy = desenho.faixas_x, desenho.faixas_y
    s = g.ESCALA.simbolo

    def numero(valor: float) -> sp.Float:
        return sp.Float(valor, 6)

    x0, x1, y0, y1 = desenho.analise.malha.faixas.T
    xs = np.abs(np.concatenate((x0, x0, x1, x1)) - p.xc)
    ys = np.abs(np.concatenate((y0, y1, y0, y1)) - p.yc)
    y_fibra = float(ys.max())
    x_fibra = float(xs.max())
    # Na fibra de um eixo, a posição no outro eixo é a mais perto do centro: lá a cortante aperta.
    x_na_fibra = float(xs[ys >= y_fibra - 1e-6].min())
    y_na_fibra = float(ys[xs >= x_fibra - 1e-6].min())
    por_t = 1.0 / p.w_torcao if p.w_torcao > 0 else 0.0

    def ponto(
        rotulo: str,
        x: float,
        y: float,
        *,
        por_vy: float = 0.0,
        por_vx: float = 0.0,
        exige: tuple[str, ...] = (),
        torque: bool = True,
        nome_com_my: str = "",
    ) -> Ponto:
        return Ponto(
            rotulo,
            numero(abs(y) / p.ix) / s**3,
            numero(1.0 / p.area) / s**2,
            numero(por_vy) / s**2,
            numero(por_t if torque else 0.0) / s**3,
            numero(abs(x) / p.iy) / s**3,
            numero(por_vx) / s**2,
            exige=exige,
            nome_com_my=nome_com_my,
        )

    centro_x = _nivel(fx, 0.0, p.ix)
    pontos = [
        ponto(
            "fibra externa",
            x_na_fibra,
            y_fibra,
            por_vx=_nivel(fy, x_na_fibra, p.iy),
        )
    ]
    vistos = set()
    for i in _niveis_de_juncao(fx.y, fx.b):
        y = float(fx.y[i])
        if round(abs(y), 6) in vistos or abs(y) < 1e-9:
            continue
        vistos.add(round(abs(y), 6))
        tau = abs(float(fx.q[i] / (p.ix * fx.b[i])))
        pontos.append(ponto(f"junção em y = {y:.4g} mm".replace(".", ","), 0.0, y, por_vy=tau))
    pontos.append(ponto("linha neutra", 0.0, 0.0, por_vy=centro_x))
    pontos.append(
        ponto(
            "fibra externa em YY",
            x_fibra,
            y_na_fibra,
            por_vy=_nivel(fx, y_na_fibra, p.ix),
            exige=("my",),
        )
    )
    pontos.append(
        ponto(
            "linha neutra de YY",
            0.0,
            0.0,
            por_vx=_nivel(fy, 0.0, p.iy),
            exige=("vx",),
        )
    )
    for k, (x, y) in enumerate(_cantos(xs, ys), start=1):
        pontos.append(ponto(f"canto {k}", x, y, exige=("mx", "my"), torque=False))
    avisos: tuple[str, ...] = ()
    if p.eixos_girados:
        avisos = ("Seção sem simetria: M·c/I não vê a flexão no outro eixo.",)
    return Secao(
        f"Seção desenhada: {nome}",
        numero(p.area) * s**2,
        numero(p.ix) * s**4,
        numero(min(p.i1, p.i2)) * s**4,
        numero(y_fibra) * s,
        numero(p.j) * s**4,
        tuple(pontos),
        (g.ESCALA,),
        (),
        (
            "Na seção desenhada, a escala muda todas as medidas juntas, furos e chapas inclusive.",
            "Na torção da seção desenhada, o τ máximo vale em todos os pontos, a favor da segurança.",
        ),
        None,
        avisos,
        inercia_y=numero(p.iy) * s**4,
    )
