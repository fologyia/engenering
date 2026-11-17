"""O piso lido do esqueleto do modelo, chapa a chapa: o que é cada chapa, a carga de cada uma e
o envio ao plano de cargas.

:mod:`core.cargas_pelo_modelo` acha as chapas de piso do esqueleto e a área que cada viga recebe.
Este módulo põe o projeto em cima disso:

* **o que o programa entendeu** (:func:`ler`): cada chapa é piso, patamar ou lance de escada (pela
  inclinação e pelos lances que encostam nela), em que nível fica (a cota acima do ponto mais
  baixo do modelo), que vigas a apoiam e quanto pesa (volume × 7 850 kg/m³); quantos pilares,
  vigas, diagonais e longarinas o esqueleto tem; e o que parece faltar (um nível de vigas sem
  chapa em cima, uma chapa sem viga embaixo);
* **a carga de cada chapa** (:class:`EscolhaDaChapa`): a sobrecarga e o peso próprios dela, e como
  ela apoia (dois sentidos ou um sentido). O peso do piso sai do volume da chapa, de um valor
  informado ou fica de fora quando o peso próprio do estudo já conta as chapas
  (:func:`pp_conta_as_chapas`);
* **a carga nas vigas** (:func:`distribuir`): a viga inteira ou só o trecho sob a chapa;
* **um envio só** (:func:`aplicar_no_plano`, :func:`comparar`): troca no plano só as linhas do
  piso (as lançadas à mão ficam), tira as sobras da grade de eixos, acerta o fator do peso próprio
  e a temperatura, e mostra antes o que muda em cada caso.

As cargas por área informadas valem na projeção horizontal (como a NBR 6120 dá a sobrecarga); o
peso pelo volume é o peso da chapa inteira, inclinada ou não. Sem Streamlit.
"""

from __future__ import annotations

import functools
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core import cargas_pelo_modelo as cpm
from core import criterio_anglo as ca
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import lista_de_material as lm
from core import papel_pelo_nome as pn
from core import plano_de_cargas as pc
from core import travamentos as tv

CHAVE_DO_PROJETO = "piso_do_modelo"
ORIGEM = cpm.ORIGEM
#: Começo da observação de toda linha do piso no plano: é por ela que um envio novo troca as suas.
MARCA = "Piso do modelo"
#: Linhas do piso de um envio antigo (antes da marca): "7,50 kN de Chapa1; trecho carregado…".
_LINHA_ANTIGA = re.compile(r"^[\d.,]+ kN de .+; trecho carregado ")

TIPO_PISO = "Piso"
TIPO_PATAMAR = "Patamar"
TIPO_ESCADA = "Escada"
TIPO_SEM_CARGA = "Sem carga"
TIPOS = (TIPO_PISO, TIPO_PATAMAR, TIPO_ESCADA, TIPO_SEM_CARGA)

PESO_PELO_VOLUME = "Pelo volume das chapas do modelo"
PESO_INFORMADO = "Informado em cada chapa (kN/m²)"
PESO_NO_PP = "Já está no peso próprio do estudo (PP)"
PESOS = (PESO_PELO_VOLUME, PESO_INFORMADO, PESO_NO_PP)

PAPEL_LONGARINA = "Longarina de escada"
PAPEL_PECA_CURTA = "Peça curta"

INCLINACAO_DE_ESCADA_GRAUS = 10.0  # acima disso a chapa é lance (o mesmo do guarda-corpo)
ENCOSTO_M = 0.30  # chapas a menos que isso uma da outra encostam (o patamar e o lance)
PATAMAR_AREA_MAXIMA_M2 = 3.0  # com um lance só encostado, maior que isso é piso
TOLERANCIA_DO_NIVEL_M = 0.25
VIGAS_DE_UM_NIVEL_SEM_CHAPA = 4  # a partir de quantas vigas num nível sem chapa vale o aviso
TOLERANCIA_DO_PP = 0.05


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------------------------
# O que o programa entendeu do modelo
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ChapaLida:
    """Uma chapa de piso do esqueleto e o que o programa entendeu dela."""

    codigo: str  # C1, C2…: o nome curto da chapa na tabela e no desenho
    chapa: cpm.ChapaDoPiso
    tipo: str  # o tipo sugerido
    motivo: str
    cota_m: float  # do centro da chapa, acima do ponto mais baixo do modelo
    nivel: int  # 1, 2… (de baixo para cima); 0 no lance de escada
    vigas: tuple[str, ...]  # as barras logo abaixo dela
    direcoes: int  # em quantas direções as vigas dela correm
    peso_kN: float | None  # volume × 7 850 kg/m³; None sem o volume
    espessura_mm: float | None

    @property
    def nome(self) -> str:
        return self.chapa.nome

    @property
    def area_m2(self) -> float:
        return self.chapa.area_m2

    @property
    def area_projetada_m2(self) -> float:
        return self.chapa.area_projetada_m2

    @property
    def inclinacao_graus(self) -> float:
        return self.chapa.inclinacao_graus

    @property
    def peso_kN_m2(self) -> float | None:
        """O peso da chapa por metro quadrado de projeção horizontal."""
        if self.peso_kN is None or self.area_projetada_m2 <= 0:
            return None
        return self.peso_kN / self.area_projetada_m2


@dataclass(frozen=True)
class LeituraDoPiso:
    chapas: tuple[ChapaLida, ...]
    fora: tuple[cpm.ChapaFora, ...]
    niveis: tuple[float, ...]  # a cota de cada nível de piso (m), de baixo para cima
    barras: tuple[tuple[str, int], ...]  # (papel, quantas): pilares, vigas, diagonais…
    papeis: tuple[tuple[str, str], ...]  # (corpo, papel)
    altura_m: float  # do ponto mais baixo ao mais alto do esqueleto
    avisos: tuple[str, ...]

    def chapa(self, nome: str) -> ChapaLida | None:
        return next((c for c in self.chapas if c.nome == nome), None)

    def do_tipo(self, tipo: str) -> list[ChapaLida]:
        return [c for c in self.chapas if c.tipo == tipo]

    @property
    def papel(self) -> dict[str, str]:
        return dict(self.papeis)

    @property
    def vigas_com_piso(self) -> set[str]:
        return {viga for c in self.chapas for viga in c.vigas}


def _altura(ponto: Sequence[float], cima: Sequence[float]) -> float:
    return tv._dot(ponto, cima)


def _contorno_no_espaco(chapa: cpm.ChapaDoPiso) -> list[cpm.Ponto3]:
    o, a, b = chapa.origem, chapa.e1, chapa.e2
    return [
        (o[0] + x * a[0] + y * b[0], o[1] + x * a[1] + y * b[1], o[2] + x * a[2] + y * b[2])
        for x, y in chapa.poligono
    ]


def _encostam(a: Sequence[cpm.Ponto3], b: Sequence[cpm.Ponto3]) -> bool:
    """Os contornos (no espaço) passam a menos de ``ENCOSTO_M`` um do outro?"""
    lados_a = list(zip(a, [*a[1:], a[0]], strict=True))
    lados_b = list(zip(b, [*b[1:], b[0]], strict=True))
    for p1, q1 in lados_a:
        for p2, q2 in lados_b:
            if tv.mais_proximos(p1, q1, p2, q2)[2] <= ENCOSTO_M:
                return True
    return False


def _niveis(cotas: Sequence[float]) -> list[float]:
    """As cotas agrupadas (± ``TOLERANCIA_DO_NIVEL_M``): a média de cada grupo, de baixo para
    cima."""
    grupos: list[list[float]] = []
    for cota in sorted(cotas):
        if grupos and cota - grupos[-1][-1] <= TOLERANCIA_DO_NIVEL_M:
            grupos[-1].append(cota)
        else:
            grupos.append([cota])
    return [sum(g) / len(g) for g in grupos]


def _nivel_da_cota(cota: float, niveis: Sequence[float]) -> int:
    if not niveis:
        return 0
    return min(range(len(niveis)), key=lambda i: abs(niveis[i] - cota)) + 1


def _papel_pelo_nome(corpo: ld.CorpoDoModelo, eixo_vertical: str) -> pn.Papel | None:
    """O papel de barra que o nome do corpo diz, se a posição o deixa valer."""
    declarado = ld.papel_declarado(corpo, eixo_vertical)
    return declarado.papel if declarado is not None and declarado.vale else None


def _longarina_do_lance(corpo: ld.CorpoDoModelo, eixo_vertical: str) -> bool:
    """A barra sob o lance é longarina: pelo nome, ou inclinada sem outro papel no nome."""
    papel = _papel_pelo_nome(corpo, eixo_vertical)
    if papel is not None and papel.tipo:
        return papel is pn.LONGARINA
    return ld.tipo_pela_posicao(corpo, eixo_vertical)[0] == ld.TIPO_CONTRAVENTAMENTO


#: O tipo da chapa que o nome dá (PS, PT, ES); o nome CH tira a chapa antes (cargas_pelo_modelo).
_TIPO_DA_CHAPA_PELO_NOME = {pn.PISO: TIPO_PISO, pn.PATAMAR: TIPO_PATAMAR, pn.LANCE: TIPO_ESCADA}


def _tipo_da_chapa_pelo_nome(chapa: cpm.ChapaDoPiso) -> tuple[str, str] | None:
    """(tipo, motivo) pelo nome da chapa, se ele diz e a inclinação deixa; senão ``None``."""
    lido = pn.papel_do_nome(chapa.nome)
    if lido is None or lido.papel not in _TIPO_DA_CHAPA_PELO_NOME:
        return None
    avaliacao = pn.avaliar(lido.papel, chapa.inclinacao_graus, ld.FORMA_CHAPA)
    if not avaliacao.vale:
        return None
    motivo = f"{lido.papel.nome.lower()} pelo nome no SolidWorks"
    if avaliacao.nota:
        motivo += f" ({avaliacao.nota})"
    return _TIPO_DA_CHAPA_PELO_NOME[lido.papel], motivo


@functools.lru_cache(maxsize=32)
def ler(g: ld.GeometriaDoModelo, eixo_vertical: str) -> LeituraDoPiso:
    """O que o programa entende do esqueleto para as cargas do piso (guardado enquanto o esqueleto
    não muda: a página pede a cada clique)."""
    cima = tv.vertical(eixo_vertical)
    alturas = [_altura(p, cima) for c in g.corpos for p in (c.inicio, c.fim)]
    alturas += [_altura(p, cima) for c in g.corpos for p in c.contorno]
    chao = min(alturas, default=0.0)
    chapas, fora = cpm.chapas_do_piso(g, eixo_vertical)
    contornos = {c.nome: _contorno_no_espaco(c) for c in chapas}
    lances = [c for c in chapas if c.inclinacao_graus > INCLINACAO_DE_ESCADA_GRAUS]
    horizontais = [c for c in chapas if c.inclinacao_graus <= INCLINACAO_DE_ESCADA_GRAUS]
    maior = max((c.area_m2 for c in horizontais), default=0.0)
    cota_de = {
        c.nome: sum(_altura(p, cima) for p in contornos[c.nome]) / len(contornos[c.nome]) - chao
        for c in chapas
    }
    niveis = _niveis([cota_de[c.nome] for c in horizontais])
    lidas: list[ChapaLida] = []
    longarinas: set[str] = set()
    for indice, chapa in enumerate(chapas, start=1):
        vigas = cpm.vigas_que_apoiam(g, chapa)
        pelo_nome = _tipo_da_chapa_pelo_nome(chapa)
        if chapa.inclinacao_graus > INCLINACAO_DE_ESCADA_GRAUS:
            tipo = TIPO_ESCADA
            motivo = f"inclinada {_n(chapa.inclinacao_graus, 0)}°: lance de escada"
            longarinas.update(
                corpo.nome for corpo, _, _ in vigas if _longarina_do_lance(corpo, eixo_vertical)
            )
        else:
            encostados = sum(
                1 for lance in lances if _encostam(contornos[chapa.nome], contornos[lance.nome])
            )
            if encostados >= 2:
                tipo, motivo = TIPO_PATAMAR, "em nível, entre dois lances de escada"
            elif (
                encostados == 1
                and chapa.area_m2 <= PATAMAR_AREA_MAXIMA_M2
                and (chapa.area_m2 < maior or len(horizontais) == 1)
            ):
                tipo = TIPO_PATAMAR
                motivo = f"em nível, {_n(chapa.area_m2)} m², na ponta de um lance de escada"
            else:
                tipo, motivo = TIPO_PISO, "em nível"
        if pelo_nome is not None:
            tipo, motivo = pelo_nome  # o nome (PS, PT, ES) diz, e a inclinação deixa
        corpo = chapa.corpo
        peso = None
        if corpo.volume_m3 is not None and corpo.volume_m3 > 0:
            peso = corpo.volume_m3 * lm.DENSIDADE_ACO * lm.G / 1e3
        lidas.append(
            ChapaLida(
                codigo=f"C{indice}",
                chapa=chapa,
                tipo=tipo,
                motivo=motivo,
                cota_m=cota_de[chapa.nome],
                nivel=0 if tipo == TIPO_ESCADA else _nivel_da_cota(cota_de[chapa.nome], niveis),
                vigas=tuple(v.nome for v, _, _ in vigas),
                direcoes=len(cpm.direcoes_das_vigas(vigas)),
                peso_kN=peso,
                espessura_mm=corpo.secao_mm[1] if corpo.secao_mm else None,
            )
        )
    # O papel de cada barra
    papeis: list[tuple[str, str]] = []
    contagem: dict[str, int] = {}
    for corpo in g.corpos:
        if corpo.forma == ld.FORMA_CHAPA or corpo.comprimento_m <= 0:
            continue
        if corpo.forma == ld.FORMA_BLOCO:
            papel = PAPEL_PECA_CURTA
        elif corpo.nome in longarinas or _papel_pelo_nome(corpo, eixo_vertical) is pn.LONGARINA:
            papel = PAPEL_LONGARINA  # a escada modelada sem as chapas: a longarina pelo nome
        else:
            papel = ld.tipo_pela_geometria(corpo, eixo_vertical)[0]
        papeis.append((corpo.nome, papel))
        contagem[papel] = contagem.get(papel, 0) + 1
    # O que parece faltar
    avisos: list[str] = []
    com_piso = {viga for c in lidas for viga in c.vigas}
    vigas_por_cota: list[tuple[float, str]] = [
        ((_altura(c.inicio, cima) + _altura(c.fim, cima)) / 2 - chao, c.nome)
        for c in g.corpos
        if dict(papeis).get(c.nome) == ld.TIPO_VIGA
    ]
    for cota in _niveis([cota for cota, _ in vigas_por_cota]):
        do_nivel = [
            nome for c, nome in vigas_por_cota if abs(c - cota) <= 2 * TOLERANCIA_DO_NIVEL_M
        ]
        if len(do_nivel) >= VIGAS_DE_UM_NIVEL_SEM_CHAPA and not com_piso.intersection(do_nivel):
            avisos.append(
                f"Há {len(do_nivel)} vigas em nível na cota +{_n(cota)} m sem chapa de piso em "
                "cima: se ali há piso, a carga dele não entra — modele a chapa no SolidWorks ou "
                "lance a carga no Plano de cargas."
            )
    for lida in lidas:
        if not lida.vigas:
            avisos.append(
                f"{lida.codigo} ({lida.nome}): nenhuma viga logo abaixo da chapa — a carga "
                "dela fica de fora."
            )
    return LeituraDoPiso(
        chapas=tuple(lidas),
        fora=tuple(fora),
        niveis=tuple(niveis),
        barras=tuple(sorted(contagem.items(), key=lambda par: -par[1])),
        papeis=tuple(papeis),
        altura_m=(max(alturas) - chao) if alturas else 0.0,
        avisos=tuple(avisos),
    )


def pp_conta_as_chapas(
    g: ld.GeometriaDoModelo, dados: em.EsforcosDoModelo | None, plano: pc.PlanoDeCargas
) -> bool | None:
    """O peso próprio do estudo (a reação vertical do PP) já conta as chapas do esqueleto?

    ``True`` quando o PP dá o peso de todos os corpos, ``False`` quando dá o das barras sem as
    chapas (± 5 %), ``None`` quando não dá para saber (sem a reação do PP, sem o volume, as
    chapas pesam pouco demais para separar ou o PP não bate com nenhum dos dois)."""
    if dados is None:
        return None
    pp = dados.casos.get("PP")
    if pp is None or pp.reacoes is None:
        return None
    vertical = ld._vertical(dados, pp)
    todos = ld.peso_do_esqueleto_kN(g)
    chapas = ld.peso_dos_corpos_kN(c for c in g.corpos if c.forma == ld.FORMA_CHAPA)
    if vertical is None or not todos or not chapas:
        return None
    peso = abs(vertical)
    barras = todos - chapas
    if barras <= 0 or chapas < 2 * TOLERANCIA_DO_PP * barras:
        return None
    fator = plano.fator_peso_proprio
    com = min(abs(peso / (todos * f) - 1) for f in (1.0, fator))
    sem = min(abs(peso / (barras * f) - 1) for f in (1.0, fator))
    if (com <= TOLERANCIA_DO_PP) == (sem <= TOLERANCIA_DO_PP):
        return None
    return com <= TOLERANCIA_DO_PP


# ---------------------------------------------------------------------------------------------
# A escolha: a carga de cada chapa
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EscolhaDaChapa:
    tipo: str = TIPO_PISO
    sc_kN_m2: float = 0.0
    pe_kN_m2: float = 0.0  # só vale com o peso informado
    sentido: str = cpm.SENTIDO_DOIS


@dataclass(frozen=True)
class EscolhaDoPiso:
    chapas: Mapping[str, EscolhaDaChapa] = field(default_factory=dict)  # pelo nome do corpo
    peso: str = PESO_PELO_VOLUME
    so_no_trecho: bool = False
    #: Outros casos por área (kN/m², na projeção), em todas as chapas com carga.
    outros: tuple[tuple[str, float], ...] = ()
    acrescimo_ligacoes_pct: float = 7.0
    temperatura: bool = False
    tirar_a_grade: bool = True

    @property
    def fator_peso_proprio(self) -> float:
        return 1.0 + self.acrescimo_ligacoes_pct / 100.0

    def da_chapa(self, nome: str) -> EscolhaDaChapa:
        return self.chapas.get(nome, EscolhaDaChapa(tipo=TIPO_SEM_CARGA))


def sobrecarga_da_escada(anglo: bool, sobrecarga_do_piso: float) -> float:
    """A sobrecarga sugerida para escadas e patamares: a da Tabela 2 do critério Anglo ("Escadas
    e passadiços em geral") nos projetos Anglo; nos outros, a mesma do piso (o usuário ajusta)."""
    if anglo:
        return ca.sobrecarga("Escadas e passadiços em geral").valor_kN_m2
    return sobrecarga_do_piso


def _numero(valor: Any, padrao: float, minimo: float = 0.0, maximo: float = 1e4) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    return numero if math.isfinite(numero) and minimo <= numero <= maximo else padrao


def escolha_inicial(
    leitura: LeituraDoPiso,
    gravado: Mapping[str, Any] | None,
    *,
    sc_do_piso: float,
    sc_da_escada: float,
    peso: str = PESO_PELO_VOLUME,
    acrescimo_ligacoes_pct: float = 7.0,
    temperatura: bool = False,
) -> EscolhaDoPiso:
    """A escolha gravada no projeto; para o que não está gravado (uma chapa nova, o projeto sem
    nada), a sugestão: o tipo lido do modelo e a sobrecarga do critério do projeto."""
    gravado = gravado if isinstance(gravado, Mapping) else {}
    das_chapas = gravado.get("chapas")
    das_chapas = das_chapas if isinstance(das_chapas, Mapping) else {}
    chapas: dict[str, EscolhaDaChapa] = {}
    for chapa in leitura.chapas:
        sugerida = EscolhaDaChapa(
            tipo=chapa.tipo,
            sc_kN_m2=sc_do_piso if chapa.tipo == TIPO_PISO else sc_da_escada,
        )
        item = das_chapas.get(chapa.nome)
        if isinstance(item, Mapping):
            tipo = str(item.get("tipo") or "")
            sentido = str(item.get("sentido") or "")
            sugerida = EscolhaDaChapa(
                tipo=tipo if tipo in TIPOS else sugerida.tipo,
                sc_kN_m2=_numero(item.get("sc_kN_m2"), sugerida.sc_kN_m2),
                pe_kN_m2=_numero(item.get("pe_kN_m2"), 0.0),
                sentido=sentido if sentido in cpm.SENTIDOS else cpm.SENTIDO_DOIS,
            )
        chapas[chapa.nome] = sugerida
    outros = []
    for item in gravado.get("outros") or ():
        if isinstance(item, Sequence) and not isinstance(item, str) and len(item) == 2:
            caso, valor = str(item[0]).strip(), _numero(item[1], 0.0)
            if caso and valor > 0 and caso not in ("SC", "PE"):
                outros.append((caso, valor))
    peso_gravado = str(gravado.get("peso") or "")
    return EscolhaDoPiso(
        chapas=chapas,
        peso=peso_gravado if peso_gravado in PESOS else peso,
        so_no_trecho=bool(gravado.get("so_no_trecho", False)),
        outros=tuple(outros),
        acrescimo_ligacoes_pct=_numero(
            gravado.get("acrescimo_ligacoes_pct"),
            acrescimo_ligacoes_pct,
            0.0,
            100 * (pc.FATOR_PESO_PROPRIO_MAXIMO - 1),
        ),
        temperatura=bool(gravado.get("temperatura", temperatura)),
        tirar_a_grade=bool(gravado.get("tirar_a_grade", True)),
    )


def para_dicionario(escolha: EscolhaDoPiso) -> dict[str, Any]:
    return {
        "chapas": {
            nome: {
                "tipo": c.tipo,
                "sc_kN_m2": c.sc_kN_m2,
                "pe_kN_m2": c.pe_kN_m2,
                "sentido": c.sentido,
            }
            for nome, c in escolha.chapas.items()
        },
        "peso": escolha.peso,
        "so_no_trecho": escolha.so_no_trecho,
        "outros": [[caso, valor] for caso, valor in escolha.outros],
        "acrescimo_ligacoes_pct": escolha.acrescimo_ligacoes_pct,
        "temperatura": escolha.temperatura,
        "tirar_a_grade": escolha.tirar_a_grade,
    }


def validar(escolha: EscolhaDoPiso) -> list[str]:
    erros = []
    for nome, c in escolha.chapas.items():
        if not (math.isfinite(c.sc_kN_m2) and 0 <= c.sc_kN_m2 <= 100):
            erros.append(f"{nome}: a sobrecarga precisa ficar entre 0 e 100 kN/m².")
        if not (math.isfinite(c.pe_kN_m2) and 0 <= c.pe_kN_m2 <= 100):
            erros.append(f"{nome}: o peso do piso precisa ficar entre 0 e 100 kN/m².")
    maximo = 100 * (pc.FATOR_PESO_PROPRIO_MAXIMO - 1)
    if not (0 <= escolha.acrescimo_ligacoes_pct <= maximo + 1e-9):
        erros.append(f"O acréscimo das ligações precisa ficar entre 0 e {_n(maximo, 0)} %.")
    return erros


# ---------------------------------------------------------------------------------------------
# A carga de cada chapa e a carga nas vigas
# ---------------------------------------------------------------------------------------------
def totais_da_chapa(chapa: ChapaLida, escolha: EscolhaDoPiso) -> dict[str, float]:
    """Caso → kN que a chapa leva às vigas (vazio na chapa sem carga)."""
    da_chapa = escolha.da_chapa(chapa.nome)
    if da_chapa.tipo == TIPO_SEM_CARGA:
        return {}
    area = chapa.area_projetada_m2
    totais = {"SC": da_chapa.sc_kN_m2 * area}
    if escolha.peso == PESO_PELO_VOLUME:
        totais["PE"] = chapa.peso_kN or 0.0
    elif escolha.peso == PESO_INFORMADO:
        totais["PE"] = da_chapa.pe_kN_m2 * area
    for caso, valor in escolha.outros:
        totais[caso] = totais.get(caso, 0.0) + valor * area
    return {caso: total for caso, total in totais.items() if total > 0 and math.isfinite(total)}


def distribuir(
    g: ld.GeometriaDoModelo, leitura: LeituraDoPiso, escolha: EscolhaDoPiso
) -> cpm.DistribuicaoDoPiso:
    """A carga de cada chapa nas vigas que a apoiam, caso a caso."""
    lista: list[cpm.InfluenciaNaViga] = []
    avisos: list[str] = []
    por_viga: dict[str, dict[str, float]] = {}  # viga → caso → kN
    itens_da_viga: dict[str, list[cpm.InfluenciaNaViga]] = {}
    usadas: list[cpm.ChapaDoPiso] = []
    for chapa in leitura.chapas:
        da_chapa = escolha.da_chapa(chapa.nome)
        totais = totais_da_chapa(chapa, escolha)
        if da_chapa.tipo == TIPO_SEM_CARGA:
            continue
        usadas.append(chapa.chapa)
        if escolha.peso == PESO_PELO_VOLUME and chapa.peso_kN is None:
            avisos.append(
                f"{chapa.codigo} ({chapa.nome}): sem o volume da chapa no esqueleto, o peso "
                "dela não entra — informe o peso em kN/m²."
            )
        resultado, _, avisos_da_chapa = cpm.influencias(g, chapa.chapa, da_chapa.sentido)
        avisos.extend(avisos_da_chapa)
        lista.extend(resultado)
        for item in resultado:
            itens_da_viga.setdefault(item.viga, []).append(item)
            casos = por_viga.setdefault(item.viga, {})
            for caso, total in totais.items():
                casos[caso] = casos.get(caso, 0.0) + total * item.fracao
    for f in leitura.fora:
        avisos.append(f"{f.nome}: {f.motivo}.")
    cargas: list[cpm.CargaNaViga] = []
    parciais: list[str] = []
    ordem = list(dict.fromkeys(["PE", "SC", *(caso for caso, _ in escolha.outros)]))
    for viga, itens in itens_da_viga.items():
        comprimento = itens[0].comprimento_m
        de, ate = min(i.de_m for i in itens), max(i.ate_m for i in itens)
        trecho = max(min(comprimento, ate - de), 1e-9)
        parcial = trecho < cpm.TRECHO_PARCIAL * comprimento
        if parcial:
            parciais.append(f"{viga} ({_n(trecho)} de {_n(comprimento)} m)")
        no_trecho = parcial and escolha.so_no_trecho
        carregado = trecho if no_trecho else comprimento
        for caso in ordem:
            total = por_viga[viga].get(caso, 0.0)
            if total <= 0:
                continue
            cargas.append(
                cpm.CargaNaViga(
                    caso=caso,
                    viga=viga,
                    kN_m=total / carregado if carregado > 0 else 0.0,
                    total_kN=total,
                    trecho_m=trecho,
                    comprimento_m=comprimento,
                    chapas=tuple(dict.fromkeys(i.chapa for i in itens)),
                    de_m=de,
                    ate_m=ate,
                    parcial=no_trecho,
                )
            )
    cargas.sort(key=lambda c: (ordem.index(c.caso), c.viga))
    if parciais and not escolha.so_no_trecho:
        avisos.append(
            f"Carga só em parte da viga: {ld._lista(parciais, 4)}. A tabela dá a carga uniforme "
            "na viga inteira (o mesmo total); para o momento sair certo, ligue “Carga só no "
            "trecho sob a chapa” e aplique a carga só nesse trecho no SolidWorks."
        )
    return cpm.DistribuicaoDoPiso(
        chapas=tuple(usadas),
        fora=leitura.fora,
        influencias=tuple(lista),
        cargas=tuple(cargas),
        avisos=tuple(dict.fromkeys(avisos)),
    )


def conferencia(
    leitura: LeituraDoPiso, escolha: EscolhaDoPiso, d: cpm.DistribuicaoDoPiso
) -> list[dict[str, object]]:
    """Caso a caso: o que as chapas mandam (kN) contra o que chegou às vigas."""
    entrou: dict[str, float] = {}
    com_viga = {i.chapa for i in d.influencias}
    for chapa in leitura.chapas:
        if chapa.nome not in com_viga:
            continue
        for caso, total in totais_da_chapa(chapa, escolha).items():
            entrou[caso] = entrou.get(caso, 0.0) + total
    linhas = []
    for caso in dict.fromkeys([*d.casos, *entrou]):
        aplicado = d.total(caso)
        linhas.append(
            {
                "Caso": caso,
                "Das chapas (kN)": entrou.get(caso, 0.0),
                "Nas vigas (kN)": aplicado,
                "Confere": "sim"
                if abs(aplicado - entrou.get(caso, 0.0)) <= 1e-6 * max(1.0, aplicado)
                else "não",
            }
        )
    return linhas


# ---------------------------------------------------------------------------------------------
# Plano de cargas
# ---------------------------------------------------------------------------------------------
def e_linha_do_piso(carga: pc.CargaDoModelo) -> bool:
    return carga.observacao.startswith(MARCA) or bool(_LINHA_ANTIGA.match(carga.observacao))


def linhas_do_caso(
    d: cpm.DistribuicaoDoPiso, caso: str, nomes_no_simulation: Mapping[str, str] | None = None
) -> list[pc.CargaDoModelo]:
    """As linhas do plano: uma carga distribuída por viga (o corpo no SolidWorks)."""
    nomes = nomes_no_simulation or {}
    linhas = []
    for c in sorted(d.do_caso(caso), key=lambda c: c.viga):
        no_simulation = f" ({nomes[c.viga]})" if c.viga in nomes else ""
        if c.parcial:
            onde = (
                f"só no trecho de {_n(c.de_m)} a {_n(c.ate_m)} m da ponta inicial da viga "
                f"(viga de {_n(c.comprimento_m)} m)"
            )
        else:
            onde = (
                f"uniforme na viga de {_n(c.comprimento_m)} m "
                f"(trecho sob a chapa: {_n(c.trecho_m)} m)"
            )
        linhas.append(
            pc.CargaDoModelo(
                elemento=f"{c.viga}{no_simulation}",
                valor=round(c.kN_m, 4),
                unidade="kN/m",
                direcao=cpm.VERTICAL,
                observacao=f"{MARCA}: {_n(c.total_kN)} kN de {', '.join(c.chapas)}; {onde}",
                quantidade=1,
                comprimento_m=round(c.comprimento_carregado_m, 4),
                inicio_m=round(c.de_m, 4) if c.parcial else 0.0,
            )
        )
    return linhas


def _resumo_do_caso(
    caso: str, leitura: LeituraDoPiso, escolha: EscolhaDoPiso, d: cpm.DistribuicaoDoPiso
) -> str:
    com_viga = {i.chapa for i in d.influencias}
    por_tipo: dict[str, tuple[float, float]] = {}
    for chapa in leitura.chapas:
        total = totais_da_chapa(chapa, escolha).get(caso, 0.0)
        if chapa.nome not in com_viga or total <= 0:
            continue
        tipo = escolha.da_chapa(chapa.nome).tipo
        area, soma = por_tipo.get(tipo, (0.0, 0.0))
        por_tipo[tipo] = (area + chapa.area_projetada_m2, soma + total)
    partes = [
        f"{tipo.lower()} {_n(soma)} kN em {_n(area)} m²" for tipo, (area, soma) in por_tipo.items()
    ]
    return (
        f"{MARCA} ({caso}): {_n(d.total(caso))} kN nas vigas que apoiam as chapas do esqueleto"
        + (f" — {'; '.join(partes)}" if partes else "")
        + "."
    )


def _frase_do_guarda_corpo(resumo: str) -> str:
    if cpm.MARCA_GUARDA_CORPO not in resumo:
        return ""
    return resumo[resumo.index(cpm.MARCA_GUARDA_CORPO) :].split(" | ")[0]


def aplicar_no_plano(
    plano: pc.PlanoDeCargas,
    leitura: LeituraDoPiso,
    escolha: EscolhaDoPiso,
    d: cpm.DistribuicaoDoPiso,
    nomes_no_simulation: Mapping[str, str] | None = None,
) -> pc.PlanoDeCargas:
    """O plano com as cargas do piso nas vigas.

    Em cada caso, só as linhas do piso de um envio anterior e a carga por área (kN/m²) que elas
    substituem são trocadas: o peso do guarda-corpo e o que foi lançado à mão ficam. As sobras da grade de eixos saem (``tirar_a_grade``), o peso
    próprio ganha o fator das ligações e a temperatura entra ou sai conforme a escolha."""
    if escolha.tirar_a_grade:
        plano = cpm.sem_cargas_da_grade(plano)
    com_piso_antes = [a.codigo for a in plano.acoes if any(e_linha_do_piso(c) for c in a.cargas)]
    for caso in dict.fromkeys([*d.casos, *com_piso_antes]):
        linhas = linhas_do_caso(d, caso, nomes_no_simulation)
        anterior = plano.acao(caso)
        if anterior is None:
            if linhas:
                plano = pc.com_acao(
                    plano,
                    pc.nova_acao(
                        caso,
                        origem=ORIGEM,
                        resumo=_resumo_do_caso(caso, leitura, escolha, d),
                        cargas=linhas,
                    ),
                )
            continue
        # A carga por área do mesmo caso (kN/m², "todos os pisos") é a que as vigas passam a levar.
        mantidas = [
            c
            for c in anterior.cargas
            if not e_linha_do_piso(c) and not (linhas and c.unidade == "kN/m²")
        ]
        partes = [_resumo_do_caso(caso, leitura, escolha, d)] if linhas else []
        do_guarda_corpo = _frase_do_guarda_corpo(anterior.resumo)
        if do_guarda_corpo and any(
            c.observacao.startswith(cpm.MARCA_GUARDA_CORPO) for c in mantidas
        ):
            partes.append(do_guarda_corpo)
        plano = pc.com_acao(
            plano,
            replace(
                anterior,
                origem=ORIGEM if linhas else anterior.origem,
                resumo=" | ".join(partes) if partes else anterior.resumo,
                cargas=tuple([*linhas, *mantidas]),
                atualizado_em=pc.agora(),
            ),
        )
    if "PP" not in plano.codigos:
        plano = pc.com_acao(plano, pc.nova_acao("PP", origem=ORIGEM))
    plano = pc.com_fator_peso_proprio(plano, escolha.fator_peso_proprio)
    return _com_a_temperatura(plano, escolha.temperatura)


ORIGENS_DA_TEMPERATURA = (ORIGEM, "Cargas do esqueleto")
#: Onde cada origem da temperatura guarda a sua chave (o próximo envio lê dali).
_CHAVE_DA_TEMPERATURA = {ORIGEM: CHAVE_DO_PROJETO, "Cargas do esqueleto": "cargas_do_esqueleto"}


def campos_sem_a_temperatura(projeto: Mapping[str, Any] | None, origem: str) -> dict[str, Any]:
    """Os campos do projeto com a temperatura desligada na página que gerou T+/T−.

    Quem tira T+ ou T− do plano à mão não quer que o próximo envio das cargas do esqueleto as
    devolva: a chave "Temperatura ±10 °C" daquela forma (modelo ou grade) passa a desligada.
    Vazio quando a ação não veio das cargas do esqueleto."""
    chave = _CHAVE_DA_TEMPERATURA.get(origem)
    if chave is None:
        return {}
    gravado = (projeto or {}).get(chave)
    gravado = gravado if isinstance(gravado, Mapping) else {}
    return {chave: {**gravado, "temperatura": False}}


def _com_a_temperatura(plano: pc.PlanoDeCargas, ligada: bool) -> pc.PlanoDeCargas:
    for codigo, sinal in (("T+", 1.0), ("T−", -1.0)):
        anterior = plano.acao(codigo)
        if not ligada:
            # Só sai a que esta página gerou; a informada à mão fica.
            if anterior is not None and anterior.origem in ORIGENS_DA_TEMPERATURA:
                plano = pc.sem_acao(plano, codigo)
            continue
        if anterior is not None and anterior.origem not in ORIGENS_DA_TEMPERATURA:
            continue
        plano = pc.com_acao(
            plano,
            pc.nova_acao(
                codigo,
                origem=ORIGEM,
                resumo="Variação de temperatura do critério Anglo (5.8).",
                cargas=[
                    pc.CargaDoModelo(
                        "Todas as barras do esqueleto",
                        sinal * ca.TEMPERATURA_VARIACAO_C,
                        "°C",
                        "—",
                    )
                ],
            ),
        )
    return plano


def _total(acao: pc.Acao | None) -> tuple[float, int]:
    """(kN que as linhas com resultante conhecida levam, quantas linhas)."""
    if acao is None:
        return 0.0, 0
    return sum(abs(c.resultante or 0.0) for c in acao.cargas), len(acao.cargas)


def _renomeadas(
    cargas_a: tuple[pc.CargaDoModelo, ...],
    cargas_b: tuple[pc.CargaDoModelo, ...],
    nomes_no_simulation: Mapping[str, str],
) -> list[tuple[str, str]]:
    """As vigas que saem só com o nome do corpo e voltam com o da barra no Simulation.

    As linhas do piso e do guarda-corpo levam "corpo (barra)" (``linhas_do_caso``); outra
    página pode levar só a barra."""
    antes = {c.elemento for c in cargas_a}
    depois = {c.elemento for c in cargas_b}
    trocas = []
    for corpo, barra in nomes_no_simulation.items():
        if corpo == barra or corpo not in antes or corpo in depois:
            continue
        for novo in (f"{corpo} ({barra})", barra):
            if novo in depois and novo not in antes:
                trocas.append((corpo, barra))
                break
    return sorted(trocas)


def comparar(
    antes: pc.PlanoDeCargas,
    depois: pc.PlanoDeCargas,
    nomes_no_simulation: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    """Caso a caso, o que o envio muda no plano de cargas (só os casos que mudam).

    Com ``nomes_no_simulation`` (corpo → barra), diz quando as vigas só trocam de nome: o envio
    feito antes de importar os esforços leva o nome do corpo; depois, o da barra no Simulation."""
    nomes = nomes_no_simulation or {}
    linhas: list[dict[str, object]] = []
    do_fator = ""
    if abs(antes.fator_peso_proprio - depois.fator_peso_proprio) > 1e-9:
        do_fator = (
            f"gravidade × {_n(antes.fator_peso_proprio)} → "
            f"× {_n(depois.fator_peso_proprio)} (ligações não modeladas)"
        )
    for codigo in dict.fromkeys([*antes.codigos, *depois.codigos]):
        a, b = antes.acao(codigo), depois.acao(codigo)
        (total_a, n_a), (total_b, n_b) = _total(a), _total(b)
        cargas_a = tuple(a.cargas) if a else ()
        cargas_b = tuple(b.cargas) if b else ()
        fator = do_fator if codigo == "PP" else ""
        if (a is None) == (b is None) and cargas_a == cargas_b and not fator:
            continue
        if a is None:
            muda = "caso novo no plano"
        elif b is None:
            muda = "sai do plano"
        else:
            partes = []
            renomeadas = _renomeadas(cargas_a, cargas_b, nomes)
            if renomeadas:
                corpo, barra = renomeadas[0]
                partes.append(
                    f"{len(renomeadas)} viga(s) ganham o nome da barra no Simulation "
                    f"(ex.: {corpo} → {barra})"
                )
            da_grade = sum(1 for c in cargas_a if cpm._NOME_DA_GRADE.match(c.elemento.strip()))
            ainda = sum(1 for c in cargas_b if cpm._NOME_DA_GRADE.match(c.elemento.strip()))
            if da_grade > ainda:
                partes.append(f"saem {da_grade - ainda} linha(s) da grade de eixos")
            por_area = sum(1 for c in cargas_a if c.unidade == "kN/m²") - sum(
                1 for c in cargas_b if c.unidade == "kN/m²"
            )
            if por_area > 0:
                partes.append(f"sai a carga por área ({por_area} linha em kN/m²)")
            piso_a = sum(1 for c in cargas_a if e_linha_do_piso(c))
            piso_b = sum(1 for c in cargas_b if e_linha_do_piso(c))
            if piso_a or piso_b:
                partes.append(f"piso: {piso_a} → {piso_b} viga(s)")
            gc_a = sum(1 for c in cargas_a if c.observacao.startswith(cpm.MARCA_GUARDA_CORPO))
            gc_b = sum(1 for c in cargas_b if c.observacao.startswith(cpm.MARCA_GUARDA_CORPO))
            if gc_a != gc_b or [
                c for c in cargas_a if c.observacao.startswith(cpm.MARCA_GUARDA_CORPO)
            ] != [c for c in cargas_b if c.observacao.startswith(cpm.MARCA_GUARDA_CORPO)]:
                partes.append(f"guarda-corpo: {gc_a} → {gc_b} viga(s)")
            muda = "; ".join(partes) or ("" if fator else "valores atualizados")
        muda = "; ".join(parte for parte in (muda, fator) if parte)
        linhas.append(
            {
                "Caso": codigo,
                "Antes (kN)": total_a if a is not None else None,
                "Depois (kN)": total_b if b is not None else None,
                "Linhas": f"{n_a} → {n_b}",
                "O que muda": muda,
            }
        )
    return linhas


def resumo_do_envio(mudancas: Sequence[Mapping[str, object]]) -> str:
    """A confirmação que a página mostra depois de gravar: caso a caso, como o plano ficou."""
    if not mudancas:
        return "Gravado. O plano de cargas já estava com estas cargas: nada mudou."
    partes = []
    for m in mudancas:
        caso, depois = m.get("Caso"), m.get("Depois (kN)")
        n = str(m.get("Linhas") or "").split("→")[-1].strip()
        if depois is None:
            partes.append(f"{caso} saiu do plano")
        elif isinstance(depois, int | float) and depois > 0:
            partes.append(f"{caso}: {n} linha(s), {_n(float(depois))} kN")
        else:
            partes.append(f"{caso}: {n} linha(s)")
    return "Enviado ao plano de cargas — " + " · ".join(partes) + "."


# ---------------------------------------------------------------------------------------------
# Tabelas e CSV
# ---------------------------------------------------------------------------------------------
def linhas_das_vigas(
    d: cpm.DistribuicaoDoPiso, caso: str, nomes_no_simulation: Mapping[str, str] | None = None
) -> list[dict[str, object]]:
    nomes = nomes_no_simulation or {}
    return [
        {
            "Viga (corpo no SolidWorks)": c.viga,
            "Viga no Simulation": nomes.get(c.viga, "—"),
            "kN/m": c.kN_m,
            "Onde": f"de {_n(c.de_m)} a {_n(c.ate_m)} m" if c.parcial else "viga inteira",
            "Total (kN)": c.total_kN,
            "Trecho sob a chapa (m)": c.trecho_m,
            "Comprimento (m)": c.comprimento_m,
            "Chapas": ", ".join(c.chapas),
        }
        for c in d.do_caso(caso)
    ]


def csv_das_cargas(
    d: cpm.DistribuicaoDoPiso, nomes_no_simulation: Mapping[str, str] | None = None
) -> bytes:
    nomes = nomes_no_simulation or {}
    linhas = [
        "Caso;Viga (corpo no SolidWorks);Viga no Simulation;kN/m;Onde;De (m);Até (m);"
        "Total (kN);Trecho sob a chapa (m);Comprimento (m);Chapas"
    ]

    def numero(valor: float) -> str:
        return f"{valor:.3f}".replace(".", ",")

    for c in d.cargas:
        linhas.append(
            ";".join(
                [
                    c.caso,
                    c.viga,
                    nomes.get(c.viga, ""),
                    numero(c.kN_m),
                    "trecho" if c.parcial else "viga inteira",
                    numero(c.de_m if c.parcial else 0.0),
                    numero(c.ate_m if c.parcial else c.comprimento_m),
                    numero(c.total_kN),
                    numero(c.trecho_m),
                    numero(c.comprimento_m),
                    ", ".join(c.chapas),
                ]
            )
        )
    return ("\r\n".join(linhas) + "\r\n").encode("utf-8-sig")


def escolha_do_projeto(projeto: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    gravado = (projeto or {}).get(CHAVE_DO_PROJETO)
    return gravado if isinstance(gravado, Mapping) else None
