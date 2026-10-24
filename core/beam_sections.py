"""Seções transversais e materiais para a análise de vigas e eixos."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import Any

from core.steel_sections import centro_de_cisalhamento_do_perfil


def _positivo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser um número finito maior que zero.")
    return valor


def _nao_negativo(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor) or valor < 0:
        raise ValueError(f"{nome} deve ser um número finito não negativo.")
    return valor


def _finito(nome: str, valor: float) -> float:
    valor = float(valor)
    if not math.isfinite(valor):
        raise ValueError(f"{nome} deve ser um número finito.")
    return valor


@dataclass(frozen=True, slots=True)
class SecaoViga:
    """Propriedades da seção necessárias para esforços e tensões.

    ``modulo_torcao_mm3`` (Wt) é usado como ``tau_max = T / Wt``, o que vale
    tanto para seções circulares (Wt = J / c) quanto para retangulares e
    perfis abertos, onde a tensão máxima **não** é ``T c / J``.
    """

    nome: str
    area_mm2: float
    inercia_mm4: float
    c_superior_mm: float
    c_inferior_mm: float
    momento_estatico_mm3: float
    espessura_cisalhamento_mm: float
    constante_torcao_mm4: float
    modulo_torcao_mm3: float
    area_cisalhamento_mm2: float = 0.0
    descricao: str = ""
    # Inércia em torno do outro eixo principal (zero = desconhecida). Não
    # entra na flexão — o modelo é plano —, mas é o que permite estimar a
    # carga crítica **fora do plano**: uma barra comprimida flamba em torno
    # do eixo de menor inércia, que raramente é o eixo em que ela é fletida.
    inercia_transversal_mm4: float = 0.0
    # Distância entre o centro de cisalhamento e o centroide, medida na
    # direção perpendicular às cargas transversais. Zero quando a carga passa
    # pelo centro de cisalhamento (seções bissimétricas e monossimétricas
    # carregadas no plano de simetria). Não entra nos esforços — o modelo é
    # plano — mas é o que denuncia que um U carregado na alma torce, T ≈ V·e.
    excentricidade_cisalhamento_mm: float = 0.0

    def __post_init__(self) -> None:
        _positivo("area_mm2", self.area_mm2)
        _positivo("inercia_mm4", self.inercia_mm4)
        _positivo("c_superior_mm", self.c_superior_mm)
        _positivo("c_inferior_mm", self.c_inferior_mm)
        _nao_negativo("momento_estatico_mm3", self.momento_estatico_mm3)
        _nao_negativo("espessura_cisalhamento_mm", self.espessura_cisalhamento_mm)
        _nao_negativo("constante_torcao_mm4", self.constante_torcao_mm4)
        _nao_negativo("modulo_torcao_mm3", self.modulo_torcao_mm3)
        _nao_negativo("area_cisalhamento_mm2", self.area_cisalhamento_mm2)
        _nao_negativo("inercia_transversal_mm4", self.inercia_transversal_mm4)
        _nao_negativo("excentricidade_cisalhamento_mm", self.excentricidade_cisalhamento_mm)
        if not self.tem_cisalhamento:
            raise ValueError(
                "A seção precisa de Q e t (para V·Q/(I·t)) ou de uma área de "
                "cisalhamento (para V/Av); sem isso a tensão de cisalhamento "
                "seria sempre zero."
            )
        # Limites que toda seção real respeita (I = ∫y²dA ≤ A·c², Q ≤ A·c/2,
        # Av ≤ A). Violá-los não é geometria: é unidade trocada (cm⁴ por mm⁴,
        # I em vez de W…), e o cálculo seguiria com tensões absurdas.
        c_maximo = max(self.c_superior_mm, self.c_inferior_mm)
        if self.inercia_mm4 > self.area_mm2 * c_maximo**2 * (1.0 + 1e-9):
            raise ValueError(
                f"I = {self.inercia_mm4:.4g} mm⁴ é maior que A·c² = "
                f"{self.area_mm2 * c_maximo**2:.4g} mm⁴, o que nenhuma seção tem "
                "(I = ∫y²dA ≤ A·c²). Confira as unidades: I em mm⁴, A em mm², c em mm."
            )
        if self.momento_estatico_mm3 > self.area_mm2 * c_maximo / 2.0 * (1.0 + 1e-9):
            raise ValueError(
                f"Q = {self.momento_estatico_mm3:.4g} mm³ é maior que A·c/2 = "
                f"{self.area_mm2 * c_maximo / 2.0:.4g} mm³, o que nenhuma seção tem. "
                "Confira as unidades de Q (mm³)."
            )
        if self.area_cisalhamento_mm2 > self.area_mm2 * (1.0 + 1e-9):
            raise ValueError(
                f"A área de cisalhamento Av = {self.area_cisalhamento_mm2:.4g} mm² é "
                f"maior que a área da seção A = {self.area_mm2:.4g} mm²."
            )

    @property
    def tem_cisalhamento(self) -> bool:
        exato = self.momento_estatico_mm3 > 0 and self.espessura_cisalhamento_mm > 0
        return exato or self.area_cisalhamento_mm2 > 0

    @property
    def modulo_resistencia_superior_mm3(self) -> float:
        return self.inercia_mm4 / self.c_superior_mm

    @property
    def modulo_resistencia_inferior_mm3(self) -> float:
        return self.inercia_mm4 / self.c_inferior_mm

    @property
    def altura_mm(self) -> float:
        return self.c_superior_mm + self.c_inferior_mm


@dataclass(frozen=True, slots=True)
class MaterialViga:
    """Propriedades do material e de onde elas vieram.

    ``material_id`` aponta para um material qualificado do projeto ativo. É
    o que permite o registro técnico declarar ``materiais_ids`` e a Central
    de Validação avisar quando aquele material for revisado — sem isso, o
    cálculo sabe o valor de Sy mas não sabe de quem ele é.
    """

    nome: str
    modulo_elasticidade_MPa: float
    modulo_cisalhamento_MPa: float
    escoamento_MPa: float | None = None
    densidade_kg_m3: float = 7_850.0
    material_id: str | None = None
    fonte: str = ""

    def __post_init__(self) -> None:
        _positivo("modulo_elasticidade_MPa", self.modulo_elasticidade_MPa)
        _positivo("modulo_cisalhamento_MPa", self.modulo_cisalhamento_MPa)
        if self.escoamento_MPa is not None:
            _positivo("escoamento_MPa", self.escoamento_MPa)
        _nao_negativo("densidade_kg_m3", self.densidade_kg_m3)


def secao_retangular(base_mm: float, altura_mm: float, *, nome: str = "Retangular") -> SecaoViga:
    b = _positivo("base_mm", base_mm)
    h = _positivo("altura_mm", altura_mm)
    maior, menor = (b, h) if b >= h else (h, b)
    # Torção de Saint-Venant em seção retangular maciça (Roark/Shigley).
    j = maior * menor**3 * (1 / 3 - 0.21 * (menor / maior) * (1 - menor**4 / (12 * maior**4)))
    wt = maior**2 * menor**2 / (3 * maior + 1.8 * menor)
    return SecaoViga(
        nome=nome,
        area_mm2=b * h,
        inercia_mm4=b * h**3 / 12.0,
        c_superior_mm=h / 2.0,
        c_inferior_mm=h / 2.0,
        momento_estatico_mm3=b * h**2 / 8.0,
        espessura_cisalhamento_mm=b,
        constante_torcao_mm4=j,
        modulo_torcao_mm3=wt,
        area_cisalhamento_mm2=b * h,
        inercia_transversal_mm4=h * b**3 / 12.0,
        descricao=f"Retangular {b:.4g} × {h:.4g} mm (flexão em torno do eixo horizontal).",
    )


def secao_circular_macica(diametro_mm: float, *, nome: str = "Circular maciça") -> SecaoViga:
    d = _positivo("diametro_mm", diametro_mm)
    inercia = math.pi * d**4 / 64.0
    return SecaoViga(
        nome=nome,
        area_mm2=math.pi * d**2 / 4.0,
        inercia_mm4=inercia,
        c_superior_mm=d / 2.0,
        c_inferior_mm=d / 2.0,
        momento_estatico_mm3=d**3 / 12.0,
        espessura_cisalhamento_mm=d,
        constante_torcao_mm4=2 * inercia,
        modulo_torcao_mm3=math.pi * d**3 / 16.0,
        area_cisalhamento_mm2=math.pi * d**2 / 4.0,
        inercia_transversal_mm4=inercia,
        descricao=f"Barra circular maciça ⌀{d:.4g} mm.",
    )


def secao_tubo_circular(
    diametro_externo_mm: float,
    diametro_interno_mm: float,
    *,
    nome: str = "Tubo circular",
) -> SecaoViga:
    de = _positivo("diametro_externo_mm", diametro_externo_mm)
    di = _nao_negativo("diametro_interno_mm", diametro_interno_mm)
    if di >= de:
        raise ValueError("O diâmetro interno deve ser menor que o externo.")
    inercia = math.pi * (de**4 - di**4) / 64.0
    return SecaoViga(
        nome=nome,
        area_mm2=math.pi * (de**2 - di**2) / 4.0,
        inercia_mm4=inercia,
        c_superior_mm=de / 2.0,
        c_inferior_mm=de / 2.0,
        momento_estatico_mm3=(de**3 - di**3) / 12.0,
        espessura_cisalhamento_mm=de - di,
        constante_torcao_mm4=2 * inercia,
        modulo_torcao_mm3=2 * inercia / (de / 2.0),
        area_cisalhamento_mm2=math.pi * (de**2 - di**2) / 4.0,
        inercia_transversal_mm4=inercia,
        descricao=f"Tubo circular ⌀{de:.4g} × ⌀{di:.4g} mm.",
    )


def secao_tubo_retangular(
    largura_mm: float,
    altura_mm: float,
    espessura_mm: float,
    *,
    nome: str = "Tubo retangular",
) -> SecaoViga:
    b = _positivo("largura_mm", largura_mm)
    h = _positivo("altura_mm", altura_mm)
    t = _positivo("espessura_mm", espessura_mm)
    if 2 * t >= min(b, h):
        raise ValueError("A espessura da parede é grande demais para as dimensões informadas.")
    bi, hi = b - 2 * t, h - 2 * t
    inercia = (b * h**3 - bi * hi**3) / 12.0
    # Momento estático das duas almas + mesa superior, na linha neutra.
    q = b * t * (h - t) / 2.0 + 2 * t * ((h / 2.0 - t) ** 2) / 2.0
    # Bredt para seção fechada de parede fina.
    area_media = (b - t) * (h - t)
    perimetro_medio = 2 * ((b - t) + (h - t))
    return SecaoViga(
        nome=nome,
        area_mm2=b * h - bi * hi,
        inercia_mm4=inercia,
        c_superior_mm=h / 2.0,
        c_inferior_mm=h / 2.0,
        momento_estatico_mm3=q,
        espessura_cisalhamento_mm=2 * t,
        constante_torcao_mm4=4 * area_media**2 * t / perimetro_medio,
        modulo_torcao_mm3=2 * area_media * t,
        area_cisalhamento_mm2=2 * t * h,
        inercia_transversal_mm4=(h * b**3 - hi * bi**3) / 12.0,
        descricao=f"Tubo retangular {b:.4g} × {h:.4g} × {t:.4g} mm.",
    )


def secao_i_simetrica(
    altura_mm: float,
    largura_mesa_mm: float,
    espessura_alma_mm: float,
    espessura_mesa_mm: float,
    *,
    nome: str = "Perfil I",
) -> SecaoViga:
    h = _positivo("altura_mm", altura_mm)
    bf = _positivo("largura_mesa_mm", largura_mesa_mm)
    tw = _positivo("espessura_alma_mm", espessura_alma_mm)
    tf = _positivo("espessura_mesa_mm", espessura_mesa_mm)
    if 2 * tf >= h:
        raise ValueError("As mesas não cabem na altura informada.")
    hw = h - 2 * tf
    area = 2 * bf * tf + tw * hw
    inercia = (bf * h**3 - (bf - tw) * hw**3) / 12.0
    q = bf * tf * (h - tf) / 2.0 + tw * hw**2 / 8.0
    # Perfil aberto: J = Σ b t³/3 e tau_max = T t_max / J.
    j = (2 * bf * tf**3 + hw * tw**3) / 3.0
    t_max = max(tf, tw)
    return SecaoViga(
        nome=nome,
        area_mm2=area,
        inercia_mm4=inercia,
        c_superior_mm=h / 2.0,
        c_inferior_mm=h / 2.0,
        momento_estatico_mm3=q,
        espessura_cisalhamento_mm=tw,
        constante_torcao_mm4=j,
        modulo_torcao_mm3=j / t_max,
        area_cisalhamento_mm2=tw * h,
        inercia_transversal_mm4=(2 * tf * bf**3 + hw * tw**3) / 12.0,
        descricao=(
            f"Perfil I {h:.4g} × {bf:.4g} mm (alma {tw:.4g}, mesa {tf:.4g}). "
            "Torção de perfil aberto — muito pouco rígida."
        ),
    )


def _familia_do_perfil(perfil: Any) -> str:
    """Primeira palavra da família, em maiúsculas: "T", "U", "W", "TUBO"…"""
    familia = str(getattr(perfil, "familia", "") or "").strip()
    return familia.split()[0].upper() if familia else ""


def _familia_normalizada(perfil: Any) -> str:
    familia = str(getattr(perfil, "familia", "") or "")
    decomposta = unicodedata.normalize("NFD", familia)
    return "".join(c for c in decomposta if unicodedata.category(c) != "Mn").casefold()


def _modulo_de_torcao_do_perfil(perfil: Any) -> tuple[float, str]:
    """``Wt`` coerente com a forma da seção, e uma nota quando é estimativa.

    ``J / t_máx`` é a torção de Saint-Venant de perfil **aberto** (I, W, U,
    C, T). Aplicada a um tubo — seção fechada — ela dava um ``Wt`` seis
    vezes maior que o de Bredt, ou seja, tensão de torção seis vezes menor
    que a real; numa barra maciça o erro ia para o outro lado. Cada família
    usa a sua fórmula: circular ``J/(d/2)``, tubo retangular Bredt
    ``2·A_m·t``, barra retangular Roark ``a²b²/(3a + 1,8b)``.
    """
    familia = _familia_normalizada(perfil)
    j = float(perfil.j_mm4)
    h = float(perfil.altura_mm)
    b = float(perfil.largura_mm)
    tw = float(perfil.espessura_alma_mm)
    tf = float(perfil.espessura_mesa_mm)
    circular = "circ" in familia or "redond" in familia
    if "tubo" in familia and circular:
        return (j / (h / 2.0), "") if h > 0 else (0.0, "")
    if "tubo" in familia:
        t = min(tw, tf) if min(tw, tf) > 0 else max(tw, tf)
        if t > 0 and b > t and h > t:
            return 2.0 * (b - t) * (h - t) * t, ""
        return (0.0, "")
    if "barra" in familia and circular:
        return (j / (h / 2.0), "") if h > 0 else (0.0, "")
    if "barra" in familia:
        maior, menor = max(h, b), min(h, b)
        if menor > 0:
            return maior**2 * menor**2 / (3.0 * maior + 1.8 * menor), ""
        return (0.0, "")
    t_max = max(tw, tf)
    primeira_palavra = familia.split()[0] if familia.split() else ""
    nota = ""
    if primeira_palavra not in _FAMILIAS_ABERTAS:
        nota = (
            "Wt = J/t_máx, fórmula de perfil aberto: se este perfil for um tubo "
            "ou uma barra maciça, cadastre-o com a família 'Tubo …' ou 'Barra …' "
            "para o programa usar a fórmula certa."
        )
    return (j / t_max if t_max > 0 else 0.0), nota


# Famílias de perfil aberto de parede fina, em que τ_máx = T·t_máx/J.
_FAMILIAS_ABERTAS = frozenset(
    {"i", "w", "u", "c", "t", "hp", "hea", "heb", "hem", "ipe", "ipn", "upn", "l", "cantoneira"}
)


def _area_de_cisalhamento_em_y(perfil: Any) -> tuple[float, str]:
    """Área que resiste ao cortante paralelo às mesas (flexão em torno de y).

    O catálogo tabela a área de cisalhamento da alma (cortante em y, flexão
    em x). Na flexão em torno de y o cortante é resistido pelas **mesas**:
    usar a alma superestimava τ em cerca de três vezes nos perfis I, W e U —
    conservador, mas capaz de reprovar falsamente um membro curto com muito
    cortante. Tubos e barras são tratados pela geometria; família
    desconhecida mantém a área tabelada, com nota.
    """
    familia = _familia_normalizada(perfil)
    primeira = familia.split()[0] if familia.split() else ""
    b = float(perfil.largura_mm)
    tw = float(perfil.espessura_alma_mm)
    tf = float(perfil.espessura_mesa_mm)
    tabelada = float(perfil.area_cisalhamento_mm2)
    circular = "circ" in familia or "redond" in familia
    if "tubo" in familia and not circular:
        t = min(tw, tf) if min(tw, tf) > 0 else max(tw, tf)
        if t > 0 and b > 2 * t:
            return 2.0 * t * (b - 2.0 * t), ""
        return tabelada, ""
    if "tubo" in familia or "barra" in familia:
        return tabelada, ""
    if primeira == "t" and b > 0 and tf > 0:
        return b * tf, ""
    if primeira in _FAMILIAS_ABERTAS and b > 0 and tf > 0:
        return 2.0 * b * tf, ""
    return tabelada, (
        "Cisalhamento com a área de cisalhamento tabelada (alma), conservadora "
        "para a flexão em torno de y."
    )


def _distancias_monossimetricas(perfil: Any, eixo: str) -> tuple[float, float, str] | None:
    """(c_superior, c_inferior, nota) para T em x e U em y; ``None`` se simétrico.

    Quando o perfil traz o centroide (fábricas idealizadas e perfis
    cadastrados com ele), as distâncias saem dele — exatas. As bitolas de
    catálogo não tabelam o centroide, mas tabelam as dimensões (altura,
    largura, alma e mesa), e com elas o centroide sai da composição de
    retângulos com erro pequeno. Usar ``altura / 2`` num T subestimava a
    tensão no talão em mais de 30 % para as bitolas comuns.
    """
    familia = _familia_do_perfil(perfil)
    h = float(perfil.altura_mm)
    bf = float(perfil.largura_mm)
    tw = float(perfil.espessura_alma_mm)
    tf = float(perfil.espessura_mesa_mm)
    centroide_x = float(getattr(perfil, "centroide_x_mm", 0.0) or 0.0)
    centroide_y = float(getattr(perfil, "centroide_y_mm", 0.0) or 0.0)
    if eixo == "x" and 0.0 < centroide_y < h and abs(centroide_y - h / 2.0) > 1e-9 * h:
        return (
            h - centroide_y,
            centroide_y,
            f"Fibras medidas do centroide cadastrado (ȳ = {centroide_y:.1f} mm da base): "
            "fibra superior = topo, fibra inferior = base do perfil.",
        )
    if eixo == "y" and 0.0 < centroide_x < bf and abs(centroide_x - bf / 2.0) > 1e-9 * bf:
        return (
            bf - centroide_x,
            centroide_x,
            f"Fibras medidas do centroide cadastrado (x̄ = {centroide_x:.1f} mm da face "
            "esquerda/dorso): fibra superior = lado direito (pontas das mesas), fibra "
            "inferior = lado esquerdo (dorso).",
        )
    if familia == "T" and eixo == "x" and 0 < tf < h and 0 < tw < bf:
        # Mesa em cima, talão para baixo: centroide medido do topo da mesa.
        area_mesa, area_alma = bf * tf, tw * (h - tf)
        do_topo = (area_mesa * tf / 2.0 + area_alma * (tf + (h - tf) / 2.0)) / (
            area_mesa + area_alma
        )
        return (
            do_topo,
            h - do_topo,
            "Perfil T com a mesa para cima: fibra superior = topo da mesa, "
            f"fibra inferior = ponta do talão (centroide a {do_topo:.1f} mm do topo, "
            "estimado pela geometria idealizada).",
        )
    if familia == "U" and eixo == "y" and 0 < tw < bf and 0 < 2 * tf < h:
        # Dorso da alma de um lado, pontas das mesas do outro.
        area_alma, area_mesas = h * tw, 2.0 * (bf - tw) * tf
        do_dorso = (area_alma * tw / 2.0 + area_mesas * (tw + (bf - tw) / 2.0)) / (
            area_alma + area_mesas
        )
        return (
            bf - do_dorso,
            do_dorso,
            "Perfil U fletido em torno de y: fibra superior = pontas das mesas, "
            f"fibra inferior = dorso da alma (centroide a {do_dorso:.1f} mm do dorso, "
            "estimado pela geometria idealizada).",
        )
    return None


def _excentricidade_do_centro_de_cisalhamento(perfil: Any, eixo: str) -> tuple[float, str]:
    """Distância do centro de cisalhamento ao centroide, transversal às cargas.

    U/C fletido em x: o centro de cisalhamento fica fora da alma, e a carga
    vertical no centroide (ou na alma) torce o perfil. T fletido em y: o
    centro de cisalhamento está na mesa, e a carga horizontal no centroide
    torce. Nas demais famílias, ou com a carga no plano de simetria, é zero.
    """
    try:
        x0, y0 = centro_de_cisalhamento_do_perfil(perfil)
    except (AttributeError, TypeError, ValueError):
        return 0.0, ""
    excentricidade = abs(float(x0)) if eixo == "x" else abs(float(y0))
    if not math.isfinite(excentricidade) or excentricidade <= 0:
        return 0.0, ""
    return excentricidade, (
        f"Centro de cisalhamento a e = {excentricidade:.1f} mm do centroide: carga "
        "transversal aplicada no centroide ou na alma gera torção T ≈ V·e."
    )


def secao_de_perfil_catalogo(perfil: Any, *, eixo: str = "x") -> SecaoViga:
    """Converte um :class:`core.steel_sections.PerfilAco` em :class:`SecaoViga`.

    O catálogo não tabela o momento estático ``Q``, então o cisalhamento usa
    a rota normativa ``tau = V / A_v`` com a área de cisalhamento do próprio
    catálogo, em vez de um ``Q`` inventado. Para T fletido em x e U fletido
    em y — os casos em que o centroide está longe do meio — as distâncias às
    fibras extremas são estimadas pela geometria idealizada; nos demais
    perfis monossimétricos (C enrijecido) mantém-se ``c = altura / 2``, a
    mesma convenção do catálogo em ``sx_mm3``, e a descrição sinaliza isso.
    """
    eixo = str(eixo).strip().lower()
    if eixo not in {"x", "y"}:
        raise ValueError("O eixo de flexão deve ser 'x' ou 'y'.")
    if eixo == "x":
        inercia = float(perfil.ix_mm4)
        altura = float(perfil.altura_mm)
        espessura = float(perfil.espessura_alma_mm)
    else:
        inercia = float(perfil.iy_mm4)
        altura = float(perfil.largura_mm)
        espessura = float(perfil.espessura_mesa_mm) * 2.0
    monossimetrica = _distancias_monossimetricas(perfil, eixo)
    if monossimetrica is None:
        c_superior = c_inferior = altura / 2.0
        nota = ""
    else:
        c_superior, c_inferior, nota = monossimetrica
    area_cisalhamento = float(perfil.area_cisalhamento_mm2)
    if eixo == "y":
        area_cisalhamento, nota_cisalhamento = _area_de_cisalhamento_em_y(perfil)
        if nota_cisalhamento:
            nota = (nota + " " if nota else "") + nota_cisalhamento
    modulo_torcao, nota_torcao = _modulo_de_torcao_do_perfil(perfil)
    if nota_torcao:
        nota = (nota + " " if nota else "") + nota_torcao
    excentricidade, nota_excentricidade = _excentricidade_do_centro_de_cisalhamento(perfil, eixo)
    if nota_excentricidade:
        nota = (nota + " " if nota else "") + nota_excentricidade
    return SecaoViga(
        nome=str(perfil.nome),
        area_mm2=float(perfil.area_mm2),
        inercia_mm4=inercia,
        c_superior_mm=c_superior,
        c_inferior_mm=c_inferior,
        momento_estatico_mm3=0.0,
        espessura_cisalhamento_mm=espessura,
        constante_torcao_mm4=float(perfil.j_mm4),
        modulo_torcao_mm3=modulo_torcao,
        area_cisalhamento_mm2=area_cisalhamento,
        inercia_transversal_mm4=float(perfil.iy_mm4 if eixo == "x" else perfil.ix_mm4),
        excentricidade_cisalhamento_mm=excentricidade,
        descricao=(
            f"{perfil.nome} — {perfil.descricao} (flexão em torno de {eixo})."
            + (f" {nota}" if nota else "")
        ),
    )
