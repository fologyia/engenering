"""Cantoneiras laminadas de abas iguais — uma fonte só para o programa inteiro.

As bitolas da tabela de bolso da Gerdau (``data/perfis_ref_gerdau_l.json``) usam os valores do
fabricante: área, inércia Ix = Iy, raio de giração mínimo r_z, posição do centroide e massa. As da
série usual que a tabela não traz (nenhuma, hoje, mas o catálogo pode mudar) ficam com a seção
idealizada: dois retângulos ``b × t``, sem o raio de concordância, um pouco menor que a real (a
favor da segurança). O nome é sempre ``L 2 1/2" × 1/4"``; ``obter_cantoneira`` aceita também o
nome do catálogo de perfis (``L 2.1/2" x 1/4"``).

Eixos: ``x`` e ``y`` passam pelo centro geométrico paralelos às abas (iguais, por simetria); ``w``
é o eixo principal de maior inércia (ao longo da bissetriz) e ``z`` o de menor inércia.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

POLEGADA_MM = 25.4
DENSIDADE_ACO_KG_MM3 = 7.85e-6
ARQUIVO_GERDAU = Path(__file__).resolve().parent.parent / "data" / "perfis_ref_gerdau_l.json"
FONTE_GERDAU = "Gerdau (tabela de bolso)"
FONTE_GEOMETRIA = "seção idealizada (dois retângulos)"

#: (aba em polegadas, espessura em polegadas) — série usual de cantoneiras de abas iguais.
SERIE_POLEGADAS: tuple[tuple[str, str], ...] = (
    ("1", "1/8"),
    ("1", "3/16"),
    ("1", "1/4"),
    ("1 1/4", "1/8"),
    ("1 1/4", "3/16"),
    ("1 1/4", "1/4"),
    ("1 1/2", "1/8"),
    ("1 1/2", "3/16"),
    ("1 1/2", "1/4"),
    ("1 3/4", "1/8"),
    ("1 3/4", "3/16"),
    ("1 3/4", "1/4"),
    ("2", "1/8"),
    ("2", "3/16"),
    ("2", "1/4"),
    ("2", "5/16"),
    ("2", "3/8"),
    ("2 1/2", "3/16"),
    ("2 1/2", "1/4"),
    ("2 1/2", "5/16"),
    ("2 1/2", "3/8"),
    ("3", "1/4"),
    ("3", "5/16"),
    ("3", "3/8"),
    ("3", "1/2"),
    ("4", "1/4"),
    ("4", "5/16"),
    ("4", "3/8"),
    ("4", "1/2"),
    ("5", "3/8"),
    ("5", "1/2"),
    ("6", "3/8"),
    ("6", "1/2"),
    ("6", "5/8"),
    ("6", "3/4"),
)


@dataclass(frozen=True)
class Cantoneira:
    nome: str
    b_mm: float
    t_mm: float
    area_mm2: float
    x_barra_mm: float  # do dorso (face externa da aba) ao centro geométrico
    i_x_mm4: float  # = i_y: eixo pelo centro, paralelo a uma aba
    i_w_mm4: float  # principal, maior
    i_z_mm4: float  # principal, menor
    j_mm4: float
    massa_tabelada_kg_m: float = 0.0  # massa do fabricante; zero = pela área
    fonte: str = FONTE_GEOMETRIA

    @property
    def r_x_mm(self) -> float:
        return math.sqrt(self.i_x_mm4 / self.area_mm2)

    @property
    def r_z_mm(self) -> float:
        return math.sqrt(self.i_z_mm4 / self.area_mm2)

    @property
    def b_sobre_t(self) -> float:
        return self.b_mm / self.t_mm

    @property
    def massa_kg_m(self) -> float:
        if self.massa_tabelada_kg_m > 0:
            return self.massa_tabelada_kg_m
        return self.area_mm2 * DENSIDADE_ACO_KG_MM3 * 1000.0

    @property
    def area_aba_mm2(self) -> float:
        """Área bruta de uma aba inteira (``A_c`` da aba ligada, 5.2.5)."""
        return self.b_mm * self.t_mm


def _polegadas(texto: str) -> float:
    return float(sum(Fraction(parte) for parte in texto.split()))


def propriedades(b_mm: float, t_mm: float, nome: str = "") -> Cantoneira:
    """Propriedades da cantoneira de abas iguais ``b × t`` (dois retângulos, sem raios)."""
    b, t = float(b_mm), float(t_mm)
    if not (b > 0 and 0 < t < b):
        raise ValueError("A cantoneira precisa de aba b > 0 e espessura 0 < t < b.")
    a1, x1, y1 = b * t, t / 2.0, b / 2.0  # aba vertical inteira
    a2, x2, y2 = (b - t) * t, t + (b - t) / 2.0, t / 2.0  # aba horizontal sem o canto
    area = a1 + a2
    xb = (a1 * x1 + a2 * x2) / area
    yb = (a1 * y1 + a2 * y2) / area  # = xb
    ix = t * b**3 / 12.0 + a1 * (y1 - yb) ** 2 + (b - t) * t**3 / 12.0 + a2 * (y2 - yb) ** 2
    ixy = a1 * (x1 - xb) * (y1 - yb) + a2 * (x2 - xb) * (y2 - yb)
    j = t**3 * (2.0 * b - t) / 3.0
    return Cantoneira(
        nome=nome or f"L {b:g}×{t:g}",
        b_mm=b,
        t_mm=t,
        area_mm2=area,
        x_barra_mm=xb,
        i_x_mm4=ix,
        i_w_mm4=ix + abs(ixy),
        i_z_mm4=ix - abs(ixy),
        j_mm4=j,
    )


def _aba_do_catalogo(texto: str) -> str:
    """``1.1/4`` (jeito da Gerdau) → ``1 1/4``."""
    return texto.replace('"', "").replace(".", " ").strip()


def _da_gerdau() -> dict[tuple[str, str], Cantoneira]:
    """(aba, espessura) → cantoneira com os valores da tabela Gerdau."""
    try:
        dados = json.loads(ARQUIVO_GERDAU.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    tabela: dict[tuple[str, str], Cantoneira] = {}
    for p in dados.get("perfis", []):
        m = re.fullmatch(r"L\s+(\S+)\s+x\s+(\S+)", str(p.get("nome", "")).strip())
        if not m:
            continue
        aba, espessura = _aba_do_catalogo(m.group(1)), _aba_do_catalogo(m.group(2))
        b = _polegadas(aba) * POLEGADA_MM
        t = _polegadas(espessura) * POLEGADA_MM
        ideal = propriedades(b, t)
        area = float(p["area_mm2"])
        i_x = float(p["ix_mm4"])
        i_z = float(p.get("i_min_mm4") or 0.0) or ideal.i_z_mm4 * i_x / ideal.i_x_mm4
        tabela[(aba, espessura)] = replace(
            ideal,
            nome=f'L {aba}" × {espessura}"',
            area_mm2=area,
            x_barra_mm=float(p.get("centroide_x_mm") or ideal.x_barra_mm),
            i_x_mm4=i_x,
            # A soma das inércias não muda com a rotação dos eixos: Iw + Iz = Ix + Iy = 2·Ix.
            i_w_mm4=2.0 * i_x - i_z,
            i_z_mm4=i_z,
            massa_tabelada_kg_m=float(p.get("massa_kg_m") or 0.0),
            fonte=FONTE_GERDAU,
        )
    return tabela


def _criar_catalogo() -> dict[str, Cantoneira]:
    gerdau = _da_gerdau()
    lista: dict[tuple[str, str], Cantoneira] = dict(gerdau)
    for aba, espessura in SERIE_POLEGADAS:
        if (aba, espessura) not in lista:
            b = _polegadas(aba) * POLEGADA_MM
            t = _polegadas(espessura) * POLEGADA_MM
            lista[(aba, espessura)] = propriedades(b, t, f'L {aba}" × {espessura}"')
    ordem = sorted(lista, key=lambda chave: (_polegadas(chave[0]), _polegadas(chave[1])))
    return {lista[chave].nome: lista[chave] for chave in ordem}


CATALOGO_CANTONEIRAS: dict[str, Cantoneira] = _criar_catalogo()


def nome_do_catalogo(nome: str) -> str | None:
    """O nome da cantoneira no catálogo, aceitando ``x`` no lugar de ``×`` e ``1.1/4`` (Gerdau)."""
    texto = str(nome or "").strip()
    if texto in CATALOGO_CANTONEIRAS:
        return texto
    m = re.fullmatch(r'L\s*([\d./ ]+?)\s*"\s*[xX×]\s*([\d./ ]+?)\s*"', texto)
    if not m:
        return None
    candidato = f'L {_aba_do_catalogo(m.group(1))}" × {_aba_do_catalogo(m.group(2))}"'
    return candidato if candidato in CATALOGO_CANTONEIRAS else None


def obter_cantoneira(nome: str) -> Cantoneira:
    chave = nome_do_catalogo(nome)
    if chave is None:
        raise ValueError(f"Cantoneira fora do catálogo: {nome!r}.")
    return CATALOGO_CANTONEIRAS[chave]


def gabarito_usual_mm(b_mm: float) -> float:
    """Distância usual do dorso à linha de furação: ~55 % da aba, arredondada a 5 mm."""
    return max(5.0, 5.0 * round(0.55 * float(b_mm) / 5.0))


# ---------------------------------------------------------------------------------------------
# A cantoneira pelo nome que vem de fora (SolidWorks, lista de corte, catálogo do fabricante)
# ---------------------------------------------------------------------------------------------
TOLERANCIA_ABA = 0.02  # 50 mm não é 2" (50,8): 1,6 %, passa; 48 mm não passa
TOLERANCIA_ESPESSURA = (
    0.03  # 6,3 mm é 1/4" (6,35); 6 mm não é (5,5 % mais fina, contra a segurança)
)
ABA_MAXIMA_POL = 8.5  # sem aspas: até aqui é polegada; de 10 para cima é milímetro
ABA_MINIMA_MM = 10.0

_PREFIXO = re.compile(
    r"(?:cantoneira|cant\.?|angle|[âa]ngulo|(?<![A-Za-zÀ-ÿ])[Ll](?![A-Za-zÀ-ÿ]))", re.IGNORECASE
)
_MEDIDAS = re.compile(r"""[\s\-:]*([\d.,/ \-"'×xX]*(?:pol|in)?[\d.,/ \-"'×xX]*)""")
_MISTO = re.compile(r"^(\d+)\s*[.\- ]\s*(\d+)\s*/\s*(\d+)$")  # 2 1/2, 2.1/2 (Gerdau), 2-1/2
_FRACAO = re.compile(r"^(\d+)\s*/\s*(\d+)$")


@dataclass(frozen=True)
class MedidaLida:
    valor: float
    em_polegadas: bool | None  # None: sem aspas, decide pelo tamanho


def _medida(texto: str) -> MedidaLida | None:
    bruto = texto.strip()
    polegada = bool(re.search(r"(\"|''|pol|in)\s*$", bruto, re.IGNORECASE))
    numero = re.sub(r"(\"|''|pol|in)\s*$", "", bruto, flags=re.IGNORECASE).strip(" -'\"")
    if not numero:
        return None
    m = _MISTO.match(numero)
    if m and int(m.group(3)) in (2, 4, 8, 16, 32, 64) and int(m.group(2)) < int(m.group(3)):
        valor = int(m.group(1)) + int(m.group(2)) / int(m.group(3))
        return MedidaLida(valor, True)
    m = _FRACAO.match(numero)
    if m:
        if int(m.group(2)) == 0:
            return None
        return MedidaLida(int(m.group(1)) / int(m.group(2)), True)
    try:
        valor = float(numero.replace(",", "."))
    except ValueError:
        return None
    return MedidaLida(valor, True if polegada else None) if valor > 0 else None


def _aba_mm(m: MedidaLida) -> float | None:
    if m.em_polegadas or (m.em_polegadas is None and m.valor <= ABA_MAXIMA_POL):
        return m.valor * POLEGADA_MM
    return m.valor if m.valor >= ABA_MINIMA_MM else None


def _espessura_mm(m: MedidaLida) -> float | None:
    # Nenhuma cantoneira laminada tem 1" de espessura: abaixo de 1 é polegada, acima é milímetro.
    return m.valor * POLEGADA_MM if (m.em_polegadas or m.valor < 1.0) else m.valor


def medidas_do_nome(texto: str) -> tuple[float, float, float] | None:
    """(aba a, aba b, espessura) em mm do nome de uma cantoneira, ou ``None``.

    Lê ``L 2 1/2" x 1/4"``, ``L 2.1/2" x 1/4"`` (Gerdau), ``L 2-1/2"``, ``L2.5X2.5X0.25``
    (SolidWorks em polegadas), ``L 3"X0,25"``, ``Cantoneira 2" x 3/16"``, ``L 50,8 x 6,35`` e
    ``L 76x76x6`` (milímetros). Sem aspas, aba até 8,5 é polegada e de 10 para cima é milímetro;
    espessura abaixo de 1 é polegada.
    """
    for prefixo in _PREFIXO.finditer(str(texto or "")):
        m = _MEDIDAS.match(texto, prefixo.end())
        trecho = m.group(1) if m else ""
        partes = [p for p in re.split(r"[×xX]", trecho)]
        partes = [p for p in partes if p.strip(" -'\"")]
        if len(partes) not in (2, 3):
            continue
        lidas = [_medida(p) for p in partes]
        if any(x is None for x in lidas):
            continue
        abas = [_aba_mm(x) for x in lidas[:-1]]  # type: ignore[arg-type]
        espessura = _espessura_mm(lidas[-1])  # type: ignore[arg-type]
        if any(a is None for a in abas) or espessura is None:
            continue
        a = abas[0]
        b = abas[-1]
        if a is None or b is None or not (0 < espessura < min(a, b)):
            continue
        return a, b, espessura
    return None


def cantoneira_pelas_medidas(aba_a_mm: float, aba_b_mm: float, espessura_mm: float) -> str | None:
    """A bitola do catálogo com estas medidas (abas iguais; ±2 % na aba, ±3 % na espessura)."""
    if abs(aba_a_mm - aba_b_mm) > TOLERANCIA_ABA * max(aba_a_mm, aba_b_mm):
        return None  # abas desiguais: o catálogo só tem abas iguais
    aba = (aba_a_mm + aba_b_mm) / 2.0
    candidatos = [
        (abs(c.b_mm - aba) / c.b_mm + abs(c.t_mm - espessura_mm) / c.t_mm, nome)
        for nome, c in CATALOGO_CANTONEIRAS.items()
        if abs(c.b_mm - aba) <= TOLERANCIA_ABA * c.b_mm
        and abs(c.t_mm - espessura_mm) <= TOLERANCIA_ESPESSURA * c.t_mm
    ]
    return min(candidatos)[1] if candidatos else None


def cantoneira_pelo_nome(texto: str) -> str | None:
    """A cantoneira do catálogo que o nome indica, por qualquer jeito de escrever; ou ``None``.

    Abas desiguais, espessura fora das bitolas (6 mm não é 1/4") e medidas que não existem no
    catálogo dão ``None``: melhor não reconhecer do que trocar a peça por outra.
    """
    exato = nome_do_catalogo(texto)
    if exato:
        return exato
    medidas = medidas_do_nome(texto)
    return cantoneira_pelas_medidas(*medidas) if medidas else None


def _mm(valor: float) -> str:
    return f"{valor:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def por_que_nao_reconheceu(texto: str) -> str:
    """Por que o nome de cantoneira não casou com o catálogo (vazio se casou ou se não é cantoneira)."""
    if cantoneira_pelo_nome(texto):
        return ""
    medidas = medidas_do_nome(texto)
    if medidas is None:
        return ""
    a, b, t = medidas
    if abs(a - b) > TOLERANCIA_ABA * max(a, b):
        return (
            f"cantoneira de abas desiguais ({_mm(a)} × {_mm(b)} × {_mm(t)} mm): o catálogo só tem "
            "abas iguais; informe a massa ou cadastre o perfil"
        )
    aba = (a + b) / 2.0
    mais_perto = min(
        CATALOGO_CANTONEIRAS.values(),
        key=lambda c: abs(c.b_mm - aba) / c.b_mm + abs(c.t_mm - t) / c.t_mm,
    )
    return (
        f"cantoneira {_mm(aba)} × {_mm(t)} mm fora das bitolas do catálogo (a mais próxima é a "
        f"{mais_perto.nome}, {_mm(mais_perto.b_mm)} × {_mm(mais_perto.t_mm)} mm); não troquei pela "
        "mais próxima: confira a peça"
    )
