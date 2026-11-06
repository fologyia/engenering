"""Cotas vivas: cada letra do desenho de um caso ligada ao campo que ela representa.

O desenho dos casos é fixo e sem escala, e o rótulo dele é a mesma letra do formulário. Basta dizer
qual letra é qual campo para o desenho mostrar o valor e aceitar a edição ali mesmo. Letra que é
resultado (a reação, a força no dente) fica de fora: só entra o que o usuário informa.

Em ``COTAS``, a chave é o texto exato do desenho. O valor é o campo, uma :class:`Celula` de campo em
forma de tabela, ou uma tupla quando o texto junta duas letras, como ``"P, n"``.
"""

from __future__ import annotations

import html
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.elementos_base import Campo, Caso, Coluna, Metrica
from core.medidas_comerciais import Serie, serie_do_campo

MARGEM_X = 34
MARGEM_Y = 8
SEPARADOR = "  ·  "


@dataclass(frozen=True)
class Celula:
    """Uma célula de um campo em forma de tabela.

    ``so_se`` liga a letra só quando outra coluna da linha vale tal coisa: o ``q`` do desenho da
    viga é a primeira carga apenas enquanto ela for distribuída.
    """

    campo: str
    linha: int
    coluna: str
    so_se: tuple[str, str] | None = None


Alvo = str | Celula


def _trecho(linha: int, coluna: str) -> Celula:
    return Celula("trechos", linha, coluna)


COTAS: dict[str, dict[str, Alvo | tuple[Alvo, ...]]] = {
    # Parafusos e roscas
    "parafuso_axial": {"P": "forca_kN", "aperto": "aperto_mm"},
    "rosca_arrancamento": {"F": "forca_kN", "L_e": "le_mm"},
    "torque_aperto": {"T": "torque_Nm"},
    "grupo_parafusos": {"N, M": ("n_kN", "mx_kNm"), "V, T": ("vy_kN", "t_kNm"), "d_c": "dc_mm"},
    # Vigas e flexão
    "viga_reacoes": {
        "L": "l_m",
        "q": Celula("cargas", 0, "valor", ("tipo", "Distribuída")),
    },
    "flexao_secao": {"M": "m_kNm"},
    "perfil_nbr8800": {"M": "mx_kNm"},
    # Barras e estruturas
    "barra_axial": {
        "L₁": _trecho(0, "l_mm"),
        "L₂": _trecho(1, "l_mm"),
        "A₁": _trecho(0, "a_mm2"),
        "A₂": _trecho(1, "a_mm2"),
        "F": _trecho(1, "f_kN"),
    },
    "barra_torcao": {
        "L₁": _trecho(0, "l_mm"),
        "L₂": _trecho(1, "l_mm"),
        "d₁": _trecho(0, "d_mm"),
        "d₂": _trecho(1, "d_mm"),
        "T": _trecho(1, "t_Nm"),
    },
    "coluna_simples": {"L": "l_m", "P": "p_kN"},
    "portico_simples": {"h": "h_m", "L": "l_m", "q": "q_kNm", "H": "h_kN"},
    # Peças, seções e chapas
    "chapa_furo": {"F": "f_kN", "b": "b_mm", "d": "d_mm"},
    # Transmissão de potência
    "acionamento": {
        "P, n": ("potencia_kW", "rotacao_rpm"),
        "i, η": ("i1", "eta1"),
        "J": "inercia_carga",
    },
    "engrenagem": {"z₁": "z1", "z₂": "z2"},
    "engrenagem_conica": {"z₁": "z1", "z₂": "z2"},
    "sem_fim": {"z₂": "z2", "T": "torque_Nm"},
    "correia": {"C": "C_mm", "D": "D_mm", "d": "d_mm"},
    "corrente": {"p": "passo_mm", "z₁": "z1", "z₂": "z2"},
    "acoplamento": {"D": "circulo_mm", "T": "torque_Nm", "n parafusos": "parafusos"},
    # Eixos e cubos
    "eixo_transmissao": {"F₁": "f1_fy_kN", "F₂": "f2_fy_kN"},
    "eixo_secao": {"D": "D_mm", "d": "d_mm", "r": "r_mm", "M": "ma_Nm"},
    "chaveta": {"d": "d_mm", "b": "b_mm", "h": "h_mm"},
    "ajuste_prensado": {"L": "L_mm", "cubo D": "D_cubo_mm", "d": "d_mm"},
    # Mancais, pinos e contato
    "rolamento": {"F_a": "fa_kN", "F_r": "fr_kN"},
    "bucha": {"F": "forca_kN", "L": "largura_mm", "d": "d_mm"},
    "pino_articulacao": {
        "a": "t_garfo_mm",
        "b": "t_olhal_mm",
        "c": "folga_mm",
        "d": "d_mm",
    },
    "hertz": {"F": "forca_kN", "d₁": "d1_mm"},
    # Molas
    "mola_compressao": {
        "D": "D_mm",
        "F": "f_max_N",
        "L₀": "L0_mm",
        "N_a, d": ("ativas", "d_mm"),
    },
    "mola_tracao": {
        "D": "D_mm",
        "F": "f_max_N",
        "N_b, d": ("espiras", "d_mm"),
        "r₂": "r2_mm",
    },
    "mola_torcao": {
        "D": "D_mm",
        "F": "f_max_N",
        "a": "braco_mm",
        "D_p": "d_pino_mm",
        "N_b, d": ("espiras", "d_mm"),
    },
    "mola_prato": {
        "D_e": "de_mm",
        "D_i": "di_mm",
        "F": "f_max_N",
        "h₀": "h0_mm",
        "t": "t_mm",
    },
    # Freios, embreagens e fusos
    "embreagem_disco": {"D": "D_ext_mm", "d": "D_int_mm", "T": "torque_Nm", "F": "forca_kN"},
    "freio_cinta": {"D": "D_mm"},
    "parafuso_potencia": {
        "F": "forca_kN",
        "d, p": ("d_mm", "passo_mm"),
        "n filetes": "filetes",
    },
    # Içamento
    "acoes_icamento": {"S_L": "carga_kN"},
    "cabo_tambor": {"D": "d_tambor_mm"},
    "roda_ponte": {"D": "d_mm", "F_r": "f_max_kN", "boleto ℓ": "boleto_mm"},
    "mecanismo_nbr8400": {
        "σ_t": "sigma_axial_MPa",
        "σ_f, τ": ("sigma_flexao_MPa", "tau_MPa"),
    },
    "gancho": {"F": "forca_kN", "h": "h_mm", "r_i": "ri_mm"},
    "olhal": {
        "F": "forca_kN",
        "L": "base_mm",
        "a": "a_mm",
        "d": "d_furo_mm",
        "h": "h_mm",
        "t": "t_mm",
    },
    # Máquinas e vibração
    "base_maquina": {"ℓ_x": "lx_mm", "F_h": "fh_x_kN", "T": "torque_Nm"},
    "disco_girante": {"D_ext": "D_ext_mm", "espessura t": "t_mm", "ω": "rotacao_rpm"},
    # Hidráulica e tampas
    "cilindro_hidraulico": {
        "D": "d_camisa_mm",
        "haste d": "d_haste_mm",
        "curso": "curso_mm",
        "p": "pressao_bar",
    },
    "placa_circular": {"diâmetro livre": "d_mm", "p": "pressao_MPa", "t": "t_mm"},
    "placa_retangular": {
        "a (lado maior)": "a_mm",
        "b": "b_mm",
        "q": "pressao_MPa",
        "t": "t_mm",
    },
    # Seção e tensão no ponto
    "Barra sob carga axial": {"A": "area_mm2", "F": "forca_kN"},
    "Barra sob carga axial excêntrica": {
        "F": "forca_kN",
        "b": "b_mm",
        "h": "h_mm",
        "e": "ey_mm",
    },
    "Eixo circular maciço": {"F": "forca_kN", "T": "torque_Nm", "d": "d_mm"},
    "Eixo circular vazado": {
        "De": "de_mm",
        "Di": "di_mm",
        "F": "forca_kN",
        "T": "torque_Nm",
    },
    "Mola helicoidal de compressão": {"F": "forca_N", "d": "d_mm"},
    "Viga de seção retangular": {
        "M": "momento_Nm",
        "V": "cortante_kN",
        "b": "b_mm",
        "h": "h_mm",
    },
    "Seção retangular com flexão biaxial": {"My": "my_Nm", "Mz": "mz_Nm"},
    "Torção de seção retangular": {"T": "torque_Nm", "b": "b_mm", "c": "c_mm"},
    "Seção I sob força axial, flexão e cortante": {
        "M": "momento_Nm",
        "V": "cortante_kN",
        "b": "b_mm",
        "h": "h_mm",
        "tf": "tf_mm",
        "tw": "tw_mm",
    },
    "Perfil U sob força axial, flexão e cortante": {
        "V": "cortante_kN",
        "bf": "b_mm",
        "h": "h_mm",
        "tf": "tf_mm",
        "tw": "tw_mm",
    },
    "Cantoneira de abas iguais": {"b (as duas abas)": "aba_mm", "t": "t_mm"},
    "Perfil tubular retangular (caixão)": {
        "T": "torque_Nm",
        "b": "b_mm",
        "h": "h_mm",
        "t": "t_mm",
    },
    "Pinos ou parafusos sob cisalhamento": {
        "F": "forca_kN",
        "d": "d_mm",
        "a": "a_mm",
        "b": "b_mm",
        "c": "c_mm",
        "n_c": "planos",
    },
    "pino_balanco": {
        "F": "forca_kN",
        "d": "d_mm",
        "a": "braco_mm",
        "L": "engaste_mm",
        "t": "t_chapa_mm",
    },
    "pino_transversal": {
        "T": "torque_Nm",
        "D": "d_eixo_mm",
        "D_c": "d_cubo_mm",
        "d": "d_mm",
    },
    "Vaso cilíndrico de parede fina": {"D": "d_mm", "p": "pressao_MPa", "t": "t_mm"},
    "Vaso esférico de parede fina": {"p": "pressao_MPa", "t": "t_mm"},
    "Cilindro de parede espessa": {
        "pe": "pe_MPa",
        "pi": "pi_MPa",
        "re": "re_mm",
        "ri": "ri_mm",
    },
}


#: Quantos campos cada rótulo junta, com o mesmo texto em qualquer caso.
COTAS_DO_ROTULO: dict[str, tuple[Alvo, ...]] = {
    rotulo: mapa if isinstance(mapa, tuple) else (mapa,)
    for caso in COTAS.values()
    for rotulo, mapa in caso.items()
}


@dataclass(frozen=True)
class CotaViva:
    """Uma medida editável, já com o valor de agora."""

    indice: int
    rotulo: str  # o texto inteiro no desenho
    letra: str
    alvo: Alvo
    valor: float
    unidade: str
    nome: str
    ajuda: str
    minimo: float | None
    maximo: float | None
    inteiro: bool
    passo: float | None = None
    serie: Serie | None = None

    @property
    def identidade(self) -> str:
        """Identifica a medida entre rodadas: o índice muda quando um campo aparece ou some."""
        if isinstance(self.alvo, Celula):
            return f"{self.alvo.campo}|{self.alvo.linha}|{self.alvo.coluna}"
        return self.alvo

    @property
    def no_desenho(self) -> bool:
        return bool(self.rotulo)

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "letra": self.letra,
            "valor": self.valor,
            "unidade": self.unidade,
            "nome": self.nome,
            "ajuda": self.ajuda,
            "minimo": self.minimo,
            "maximo": self.maximo,
            "inteiro": self.inteiro,
            "passo": self.passo,
            "serie": self.serie.nome if self.serie else "",
            "comerciais": list(self.serie.valores) if self.serie else [],
        }


def numero(valor: float) -> str:
    """Número em pt-BR, sem zeros sobrando: 1,5 e 300."""
    return f"{valor:.6g}".replace(".", ",")


def _letras(rotulo: str, alvos: Sequence[Alvo]) -> list[str]:
    if len(alvos) > 1:
        return [parte.strip() for parte in rotulo.split(",")]
    return [rotulo.split(" (")[0]]


def _valor_valido(valor: Any) -> float | None:
    if isinstance(valor, bool) or valor is None:
        return None
    try:
        numero_lido = float(valor)
    except (TypeError, ValueError):
        return None
    return numero_lido if math.isfinite(numero_lido) else None


def _da_celula(caso: Caso, alvo: Celula, valores: Mapping[str, Any]) -> tuple[Coluna, float] | None:
    campo = next(c for c in caso.campos if c.chave == alvo.campo)
    if not campo.visivel(valores):
        return None
    linhas = valores.get(alvo.campo) or ()
    if alvo.linha >= len(linhas):
        return None
    linha = linhas[alvo.linha]
    if alvo.so_se is not None and linha.get(alvo.so_se[0]) != alvo.so_se[1]:
        return None
    valor = _valor_valido(linha.get(alvo.coluna))
    if valor is None:
        return None
    return next(c for c in campo.colunas if c.chave == alvo.coluna), valor


def _do_campo(caso: Caso, chave: str, valores: Mapping[str, Any]) -> tuple[Campo, float] | None:
    campo = next(c for c in caso.campos if c.chave == chave)
    if not campo.visivel(valores):
        return None
    valor = _valor_valido(valores.get(chave))
    return None if valor is None else (campo, valor)


def _cota(
    caso: Caso, indice: int, rotulo: str, letra: str, alvo: Alvo, valores: Mapping[str, Any]
) -> CotaViva | None:
    lida: tuple[Campo | Coluna, float] | None
    if isinstance(alvo, Celula):
        lida = _da_celula(caso, alvo, valores)
    else:
        lida = _do_campo(caso, alvo, valores)
    if lida is None:
        return None
    origem, valor = lida
    return CotaViva(
        indice,
        rotulo,
        letra,
        alvo,
        valor,
        origem.unidade,
        origem.rotulo,
        origem.ajuda,
        origem.minimo,
        origem.maximo,
        isinstance(origem.padrao, int) and not isinstance(origem.padrao, bool),
        getattr(origem, "passo", None),
        serie_do_campo(caso.id, alvo),
    )


def cotas_do_caso(caso: Caso, valores: Mapping[str, Any]) -> list[CotaViva]:
    """As medidas do desenho que estão valendo agora. Campo escondido fica como letra."""
    cotas: list[CotaViva] = []
    for rotulo, mapa in COTAS.get(caso.id, {}).items():
        alvos = mapa if isinstance(mapa, tuple) else (mapa,)
        for letra, alvo in zip(_letras(rotulo, alvos), alvos, strict=True):
            cota = _cota(caso, len(cotas), rotulo, letra, alvo, valores)
            if cota is not None:
                cotas.append(cota)
    return cotas


def medidas_do_caso(caso: Caso, valores: Mapping[str, Any]) -> list[CotaViva]:
    """As cotas do desenho e, depois delas, os outros números do caso que estão à vista."""
    medidas = cotas_do_caso(caso, valores)
    no_desenho = {cota.alvo for cota in medidas}
    for campo in caso.campos:
        numerico = isinstance(campo.padrao, (int, float)) and not isinstance(campo.padrao, bool)
        if not numerico or campo.chave in no_desenho:
            continue
        medida = _cota(caso, len(medidas), "", campo.rotulo, campo.chave, valores)
        if medida is not None:
            medidas.append(medida)
    return medidas


def com_valor(valores: Mapping[str, Any], alvo: Alvo, valor: float) -> dict[str, Any]:
    """Os mesmos dados com uma medida trocada. Os originais ficam como estavam."""
    novos = dict(valores)
    if isinstance(alvo, Celula):
        linhas = [dict(linha) for linha in valores[alvo.campo]]
        linhas[alvo.linha][alvo.coluna] = valor
        novos[alvo.campo] = linhas
    else:
        novos[alvo] = valor
    return novos


def _texto_da_cota(cota: CotaViva) -> str:
    unidade = f" {cota.unidade}" if cota.unidade else ""
    return f"{cota.letra} = {numero(cota.valor)}{unidade}"


def _conteudo(rotulo: str, cotas: Sequence[CotaViva]) -> str:
    """O texto no lugar da letra. Num rótulo duplo, o campo escondido continua só como letra."""
    do_rotulo = {c.letra: c for c in cotas if c.rotulo == rotulo}
    mapa = COTAS_DO_ROTULO[rotulo]
    if len(mapa) == 1:
        return "".join(_tspan(c) for c in do_rotulo.values())
    partes = [parte.strip() for parte in rotulo.split(",")]
    # Separador largo: cada medida tem a própria caixinha, e elas não podem se tocar.
    return SEPARADOR.join(
        _tspan(do_rotulo[parte]) if parte in do_rotulo else html.escape(parte) for parte in partes
    )


def _tspan(cota: CotaViva) -> str:
    return f'<tspan data-cota="{cota.indice}">{html.escape(_texto_da_cota(cota))}</tspan>'


def _trocar_texto(svg: str, rotulo: str, conteudo: str) -> str:
    def trocar(achado: re.Match[str]) -> str:
        return f'{achado[1]} class="cota">{conteudo}</text>'

    return re.sub(r"(<text\b[^>]*)>" + re.escape(rotulo) + r"</text>", trocar, svg)


def desenho_com_cotas(svg: str, cotas: Sequence[CotaViva]) -> str:
    """O SVG com o valor no lugar da letra, e com folga dos lados para o texto mais longo caber."""

    def folgar(achado: re.Match[str]) -> str:
        largura, altura = float(achado[1]), float(achado[2])
        return (
            f'viewBox="{-MARGEM_X} {-MARGEM_Y} {largura + 2 * MARGEM_X:g} '
            f'{altura + 2 * MARGEM_Y:g}"'
        )

    saida = re.sub(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', folgar, svg, count=1)
    for rotulo in dict.fromkeys(c.rotulo for c in cotas):
        saida = _trocar_texto(saida, rotulo, _conteudo(rotulo, cotas))
    return saida


def valor_aceito(cota: CotaViva, digitado: Any) -> tuple[float | int | None, str]:
    """O valor pronto para gravar, ou ``None`` com o motivo. A prancheta também confere, mas é JS."""
    valor = _valor_valido(digitado)
    if valor is None:
        return None, f"{cota.nome}: digite um número."
    if cota.minimo is not None and valor < cota.minimo:
        return None, f"{cota.nome}: mínimo {numero(cota.minimo)} {cota.unidade}".rstrip() + "."
    if cota.maximo is not None and valor > cota.maximo:
        return None, f"{cota.nome}: máximo {numero(cota.maximo)} {cota.unidade}".rstrip() + "."
    return (int(valor) if cota.inteiro else valor), ""


# ---------------------------------------------------------------------------
# O que mudou no resultado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Mudanca:
    rotulo: str
    antes: float
    depois: float
    unidade: str

    @property
    def relativa(self) -> float:
        return (self.depois - self.antes) / abs(self.antes) if self.antes else math.inf

    def texto(self) -> str:
        unidade = f" {self.unidade}" if self.unidade else ""
        faixa = f"{_curto(self.antes)} → {_curto(self.depois)}{unidade}"
        if not math.isfinite(self.relativa):
            return f"{self.rotulo}: {faixa}"
        return f"{self.rotulo}: {faixa} ({self.relativa * 100:+.0f} %)".replace("-", "−")


def _curto(valor: float) -> str:
    return f"{valor:.4g}".replace(".", ",")


def metricas_numericas(metricas: Sequence[Metrica]) -> dict[str, tuple[float, str]]:
    """Só o que é número: o texto de situação não tem antes e depois."""
    return {
        m.rotulo: (float(m.valor), m.unidade)
        for m in metricas
        if isinstance(m.valor, (int, float)) and math.isfinite(m.valor)
    }


def mudancas(
    antes: Mapping[str, tuple[float, str]], agora: Sequence[Metrica], limite: int = 3
) -> list[Mudanca]:
    """As métricas que mais mudaram. Abaixo de 0,1 % é ruído de conta, e fica de fora."""
    achadas = []
    for rotulo, (depois, unidade) in metricas_numericas(agora).items():
        if rotulo not in antes:
            continue
        mudou = Mudanca(rotulo, antes[rotulo][0], depois, unidade)
        if abs(mudou.relativa) >= 0.001:
            achadas.append(mudou)
    achadas.sort(key=lambda m: min(abs(m.relativa), 1e9), reverse=True)
    return achadas[:limite]
