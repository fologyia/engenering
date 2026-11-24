"""Emendas dos pilares do modelo do SolidWorks: onde ficam, os esforços nelas e a verificação de todas.

**Onde ficam.** O esqueleto da macro (:mod:`core.leitura_do_modelo`) traz cada pilar como um corpo.
Dois pilares em pé que se encontram (o topo de um a menos de 5 cm do pé do outro) são uma emenda;
se os perfis forem diferentes, é a emenda da troca de perfil. O usuário também informa emendas no
meio de um pilar (a barra e a altura a partir do pé) e tira as achadas que não quer.

**Os esforços.** São os de cálculo das combinações ELU do plano de cargas, os mesmos da verificação
das barras (:func:`core.esforcos_modelo.combinados_do_membro`), multiplicados pelo B₂ do tipo
Pilar, lidos no pilar de **cima**, no ponto da emenda:

* a ponta de baixo do pilar vem de :func:`core.quadro_fundacoes.ponta_da_base` (a mesma das placas
  de base: o peso dentro dos elementos ou a escolha da tabela das barras);
* a altura de cada ponto da lista do SolidWorks sai da ordem dos elementos (malha uniforme ao longo
  da viga); no pé do pilar (emenda no encontro) é o próprio ponto, sem interpolar; no meio, a
  interpolação linear entre os dois pontos vizinhos;
* nos eixos da seção, como nas Ligações: com o eixo forte no Momento 2, V = V1, M_x = M2 e M_y = M1
  (no Momento 1, V = V2, M_x = M1, M_y = M2). N positivo é compressão, como na Emenda de pilar.

**A verificação.** Cada emenda vira uma :class:`core.emenda_pilar.EntradaEmenda`: os perfis e o aço
da tabela das barras; K·L_x e K·L_y pelos travamentos do esqueleto (:mod:`core.colunas_do_modelo`);
o N_c,Rd do pilar de cima pela Flambagem de colunas (:func:`core.column_buckling.verificar_coluna`,
com a flexo-torção); o vão e a altura da situação b de 6.1.6.2 pelo trecho travado em L_x que
contém a emenda; as combinações como os casos. O parafuso, os aços das talas e o tipo de emenda vêm
de um padrão escolhido pelo usuário, e as talas, de :func:`core.emenda_pilar.sugerir_talas`.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from core import column_buckling as cbk
from core import colunas_do_modelo as cdm
from core import emenda_pilar as ep
from core import esforcos_modelo as em
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf
from core import section_catalog as sc
from core import travamentos_da_coluna as tc
from core.technical_records import criar_registro_tecnico
from core.verificacao import STATUS_REGISTRO, Verificacao, linhas_para_registro, numero_json

MODULO_ID = ep.MODULO_ID  # o registro é da Emenda de pilar
MODULO_TITULO = "Emendas dos pilares do modelo"

#: O topo de um pilar e o pé do outro a menos disso (m) são o mesmo ponto: uma emenda.
TOLERANCIA_ENCONTRO_M = 0.05
ORIGEM_TROCA = "troca de perfil"
ORIGEM_ENCONTRO = "encontro de dois pilares"
ORIGEM_INFORMADA = "informada"
STATUS_PENDENTE = "PENDENTE"


# ---------------------------------------------------------------------------------------------
# Onde ficam
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EmendaDoModelo:
    """Uma emenda: a barra em que os esforços são lidos (o pilar de cima), a altura a partir do pé
    dela, os dois perfis e de onde a emenda veio."""

    barra: str
    altura_m: float
    perfil_superior: str
    perfil_inferior: str
    origem: str
    barra_inferior: str = ""
    cota_m: float | None = None  # altura no modelo (eixo vertical), para mostrar

    @property
    def chave(self) -> str:
        if self.origem == ORIGEM_INFORMADA:
            return f"{self.barra}@{self.altura_m:.3f}"
        return f"{self.barra_inferior}|{self.barra}"

    @property
    def nome(self) -> str:
        if self.origem == ORIGEM_INFORMADA:
            return f"{self.barra} a {_n(self.altura_m)} m do pé"
        cota = "" if self.cota_m is None else f" (cota {_n(self.cota_m)} m)"
        return f"{self.barra_inferior} → {self.barra}{cota}"


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _i_vertical(eixo_vertical: str) -> int:
    return 1 if eixo_vertical == "Y" else 2


def _pe_e_topo(
    corpo: ld.CorpoDoModelo, eixo_vertical: str
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    i = _i_vertical(eixo_vertical)
    return (
        (corpo.inicio, corpo.fim) if corpo.inicio[i] <= corpo.fim[i] else (corpo.fim, corpo.inicio)
    )


def _perfil(dados: em.EsforcosDoModelo, leitura: ld.LeituraDaBarra) -> str:
    cfg = dados.membros.get(leitura.barra, em.ConfiguracaoDoMembro())
    return cfg.perfil or leitura.perfil_sugerido or ""


def emendas_informadas(dados: em.EsforcosDoModelo) -> list[tuple[str, float]]:
    """As emendas que o usuário informou: (barra, altura a partir do pé, m)."""
    saida = []
    for item in dados.emendas.get("informadas", ()) or ():
        if isinstance(item, Mapping) and item.get("barra"):
            try:
                altura = float(item.get("altura_m") or 0.0)
            except (TypeError, ValueError):
                continue
            if math.isfinite(altura) and altura >= 0:
                saida.append((str(item["barra"]), altura))
    return saida


def emendas_tiradas(dados: em.EsforcosDoModelo) -> set[str]:
    return {str(x) for x in dados.emendas.get("tiradas", ()) or ()}


def com_informadas_e_tiradas(
    dados: em.EsforcosDoModelo, informadas: Sequence[tuple[str, float]], tiradas: Sequence[str]
) -> em.EsforcosDoModelo:
    return em.com_emendas(
        dados,
        {
            "informadas": [{"barra": b, "altura_m": round(float(h), 4)} for b, h in informadas],
            "tiradas": sorted(set(tiradas)),
        },
    )


def achar_emendas(
    dados: em.EsforcosDoModelo,
    leituras: Sequence[ld.LeituraDaBarra],
    *,
    com_as_tiradas: bool = False,
) -> list[EmendaDoModelo]:
    """As emendas do modelo: os encontros de dois pilares em pé e as informadas."""
    eixo = dados.eixo_vertical
    pilares = [
        x for x in cdm.pilares_do_modelo(dados, leituras)
        if x.corpo is not None and cdm.e_pilar(x.corpo, eixo)
    ]  # fmt: skip
    i = _i_vertical(eixo)
    achadas: list[EmendaDoModelo] = []
    for de_baixo in pilares:
        assert de_baixo.corpo is not None
        _, topo = _pe_e_topo(de_baixo.corpo, eixo)
        for de_cima in pilares:
            if de_cima is de_baixo:
                continue
            assert de_cima.corpo is not None
            pe, _ = _pe_e_topo(de_cima.corpo, eixo)
            if math.dist(topo, pe) > TOLERANCIA_ENCONTRO_M:
                continue
            p_sup, p_inf = _perfil(dados, de_cima), _perfil(dados, de_baixo)
            achadas.append(
                EmendaDoModelo(
                    de_cima.barra,
                    0.0,
                    p_sup,
                    p_inf,
                    ORIGEM_TROCA if p_sup != p_inf else ORIGEM_ENCONTRO,
                    de_baixo.barra,
                    pe[i],
                )  # fmt: skip
            )
    por_barra = {x.barra: x for x in leituras}
    for barra, altura in emendas_informadas(dados):
        leitura = por_barra.get(barra)
        if leitura is None:
            continue
        perfil = _perfil(dados, leitura)
        cota = None
        if leitura.corpo is not None:
            pe, _ = _pe_e_topo(leitura.corpo, eixo)
            cota = pe[i] + altura
        achadas.append(EmendaDoModelo(barra, altura, perfil, perfil, ORIGEM_INFORMADA, "", cota))
    if not com_as_tiradas:
        tiradas = emendas_tiradas(dados)
        achadas = [x for x in achadas if x.chave not in tiradas]
    return sorted(achadas, key=lambda x: (x.cota_m if x.cota_m is not None else 0.0, x.barra))


# ---------------------------------------------------------------------------------------------
# Os esforços na emenda
# ---------------------------------------------------------------------------------------------
def posicoes_dos_pontos(pontos: Sequence[em.PontoDeEsforco], comprimento_m: float) -> list[float]:
    """A distância de cada ponto da lista ao começo dela (m), pela ordem dos elementos.

    Cada elemento ocupa 1/n do comprimento (a malha da viga é uniforme): o primeiro ponto de um
    elemento fica no começo dele e o segundo no fim; um elemento com um ponto só, no meio."""
    ordem: list[str] = []
    for p in pontos:
        if not ordem or ordem[-1] != p.elemento:
            ordem.append(p.elemento)
    n = max(len(ordem), 1)
    contagem: dict[int, int] = {}
    total: dict[int, int] = {}
    k = -1
    indices: list[int] = []
    anterior = None
    for p in pontos:
        if p.elemento != anterior:
            k += 1
            anterior = p.elemento
        indices.append(k)
        total[k] = total.get(k, 0) + 1
    posicoes = []
    for k in indices:
        j = contagem.get(k, 0)
        contagem[k] = j + 1
        if total[k] == 1:
            frac = (k + 0.5) / n
        else:
            frac = (k + j / (total[k] - 1)) / n
        posicoes.append(frac * comprimento_m)
    return posicoes


@dataclass(frozen=True)
class EsforcosNaEmenda:
    emenda: EmendaDoModelo
    casos: tuple[ep.CasoEsforco, ...]
    v_fraco_max_kN: float
    como: str  # como o ponto foi lido
    avisos: tuple[str, ...] = ()
    motivo: str = ""  # vazio = deu para ler; senão, por que não

    @property
    def lidos(self) -> bool:
        return not self.motivo


def _interpolar(
    alturas: Sequence[float], vetores: Sequence[Sequence[float]], h: float
) -> tuple[list[float], str]:
    pares = sorted(zip(alturas, range(len(vetores)), strict=True))
    if h <= pares[0][0] + 1e-6:
        return list(vetores[pares[0][1]]), "no pé do pilar"
    if h >= pares[-1][0] - 1e-6:
        return list(vetores[pares[-1][1]]), "no topo do pilar"
    no_ponto = [j for hk, j in pares if abs(hk - h) <= 1e-6]
    if no_ponto:
        # num nó da malha há dois pontos (fim de um elemento e começo do outro): vale o de cima
        return list(vetores[no_ponto[-1]]), f"no ponto do arquivo a {_n(h)} m do pé"
    for (h0, j0), (h1, j1) in zip(pares, pares[1:], strict=False):
        if h0 - 1e-9 <= h <= h1 + 1e-9:
            if h1 - h0 <= 1e-9:
                return list(vetores[j1]), "num ponto do arquivo"
            f = (h - h0) / (h1 - h0)
            return [a + f * (b - a) for a, b in zip(vetores[j0], vetores[j1], strict=True)], (
                f"interpolado entre {_n(h0)} e {_n(h1)} m do pé"
            )
    return list(vetores[pares[-1][1]]), "no topo do pilar"


def esforcos_na_emenda(
    emenda: EmendaDoModelo,
    dados: em.EsforcosDoModelo,
    preparo: em.PreparoDasCombinacoes,
    comprimento_m: float | None,
) -> EsforcosNaEmenda:
    """N (+ compressão), M_x, V e M_y de cálculo de cada combinação ELU no ponto da emenda."""
    barra = emenda.barra
    cfg = dados.membros.get(barra, em.ConfiguracaoDoMembro())
    vazio = (emenda, (), 0.0, "")
    pontos_por_caso = {
        c: caso.membros[barra] for c, caso in dados.casos.items() if caso.membros.get(barra)
    }
    if not pontos_por_caso:
        return EsforcosNaEmenda(*vazio, motivo=f"{barra} não está nos casos importados")
    base, origem = qf.ponta_da_base(
        pontos_por_caso, cfg.base, qf.casos_de_gravidade(dados), qf.casos_com_gravidade(dados)
    )
    if base is None:
        return EsforcosNaEmenda(
            *vazio,
            motivo=f"não deu para saber qual ponta de {barra} é a de baixo ({origem}); escolha a "
            "base do pilar na tabela das barras (coluna Base), em Esforços do modelo",
        )
    combinados, metodo, aviso = em.combinados_do_membro(barra, preparo)
    avisos = [aviso] if aviso else []
    b2 = dados.parametros_do_tipo(ld.TIPO_PILAR).b2
    forte_v = 1 if cfg.eixo_forte == em.EIXO_M2 else 2
    fraco_v = 2 if forte_v == 1 else 1
    forte_m = 4 if cfg.eixo_forte == em.EIXO_M2 else 3
    fraco_m = 3 if forte_m == 4 else 4
    por_combinacao: dict[str, list[tuple[str, tuple[float, ...]]]] = {}
    for nome, rotulo, vetor in combinados:
        por_combinacao.setdefault(nome, []).append((rotulo, vetor))
    if metodo.startswith("soma"):
        como = "envoltória dos pontos da barra (a numeração dos elementos muda entre os casos)"
        lidos = {nome: max(lista, key=lambda rv: abs(rv[1][0]))[1] for nome, lista in
                 por_combinacao.items()}  # fmt: skip
    else:
        referencia = preparo.casos[0].membros[barra]
        comprimento = comprimento_m or 0.0
        if comprimento <= 0:
            return EsforcosNaEmenda(*vazio, motivo=f"o comprimento de {barra} não é conhecido")
        if emenda.altura_m > comprimento + 1e-6:
            return EsforcosNaEmenda(
                *vazio,
                motivo=f"a emenda a {_n(emenda.altura_m)} m passa do comprimento de {barra} "
                f"({_n(comprimento)} m)",
            )
        s = posicoes_dos_pontos(referencia, comprimento)
        alturas = [comprimento - x for x in s] if base == em.BASE_FIM else s
        lidos = {}
        como = ""
        sobe = base != em.BASE_FIM  # a lista sempre de baixo para cima (o nó vale o de cima)
        alturas_ordem = alturas if sobe else alturas[::-1]
        for nome, lista in por_combinacao.items():
            vetores = [v for _, v in lista] if sobe else [v for _, v in lista][::-1]
            lido, como = _interpolar(alturas_ordem, vetores, emenda.altura_m)
            lidos[nome] = tuple(lido)
        como = f"{como}; ponta de baixo: {origem}"
    casos = tuple(
        ep.CasoEsforco(nome, -v[0] * b2, v[forte_m] * b2, v[forte_v] * b2, v[fraco_m] * b2)
        for nome, v in lidos.items()
    )
    v_fraco = max((abs(v[fraco_v]) * b2 for v in lidos.values()), default=0.0)
    v_forte = max((abs(c.V) for c in casos), default=0.0)
    if v_fraco > max(0.1 * v_forte, 1.0):
        avisos.append(
            f"{emenda.nome}: há cortante no eixo fraco (até {_n(v_fraco)} kN), que vai para as "
            "talas das mesas; a Emenda de pilar verifica só a cortante da alma."
        )
    if b2 != 1.0:
        como += f"; com B₂ = {_n(b2)}"
    return EsforcosNaEmenda(emenda, casos, v_fraco, como, tuple(avisos))


# ---------------------------------------------------------------------------------------------
# A entrada da Emenda de pilar
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EmendaMontada:
    emenda: EmendaDoModelo
    entrada: ep.EntradaEmenda | None
    notas: tuple[str, ...] = ()
    motivo: str = ""


def _corpo(leituras: Sequence[ld.LeituraDaBarra], barra: str) -> ld.LeituraDaBarra | None:
    return next((x for x in leituras if x.barra == barra), None)


def nc_rd_do_pilar(perfil: str, fy: float, kl_x: float, kl_y: float, norma: str) -> float | None:
    """N_c,Rd do pilar pela Flambagem de colunas (flexo-torção incluída), kN."""
    try:
        secao = cbk.secao_de_perfil(sc.obter_perfil(perfil))
    except KeyError:
        return None
    r = cbk.verificar_coluna(
        cbk.EntradaColuna(
            secao=secao,
            fy_MPa=fy,
            norma=norma,
            Lx_mm=kl_x,
            Ly_mm=kl_y,
            Lb_mm=kl_y,
            N_Sd_kN=1e-3,
            Mx_kNm=0.0,
            My_kNm=0.0,
        )  # fmt: skip
    )
    return float(r.compressao["Nc_Rd"]) if r.compressao else None


def montar_entrada(
    esforcos: EsforcosNaEmenda,
    dados: em.EsforcosDoModelo,
    geometria: ld.GeometriaDoModelo,
    leituras: Sequence[ld.LeituraDaBarra],
    padrao: ep.EntradaEmenda,
    *,
    base: str = cdm.BASE_ROTULADA,
) -> EmendaMontada:
    """A entrada da Emenda de pilar desta emenda do modelo (as talas ficam as do ``padrao``)."""
    emenda = esforcos.emenda
    if not esforcos.lidos:
        return EmendaMontada(emenda, None, motivo=esforcos.motivo)
    faltam = [p for p in (emenda.perfil_superior, emenda.perfil_inferior) if p not in ep.PERFIS]
    if faltam:
        return EmendaMontada(
            emenda, None,
            motivo="perfil fora das famílias da Emenda de pilar (W, HP e U): " + ", ".join(
                p or "sem perfil na tabela das barras" for p in faltam),
        )  # fmt: skip
    if ep.PERFIS[emenda.perfil_superior].familia != ep.PERFIS[emenda.perfil_inferior].familia:
        return EmendaMontada(emenda, None, motivo="os dois pilares são de famílias diferentes")
    leitura = _corpo(leituras, emenda.barra)
    if leitura is None or leitura.corpo is None:
        return EmendaMontada(emenda, None, motivo=f"{emenda.barra} não está no esqueleto do modelo")
    notas: list[str] = []
    cfg = dados.membros.get(emenda.barra, em.ConfiguracaoDoMembro())
    aco = cfg.aco or dados.parametros_do_tipo(ld.TIPO_PILAR).aco
    if aco not in ep.ACOS:
        notas.append(f"Aço {aco} fora da lista da emenda: usei {padrao.aco_perfis}.")
        aco = padrao.aco_perfis
    ponta = tc.ENGASTE if base == cdm.BASE_ENGASTADA else tc.PINO
    pilar = cdm.ler_pilar(geometria, leitura.corpo, dados.eixo_vertical, ponta)
    try:
        eixo_x, eixo_y = cdm.trechos_do_pilar(pilar)
    except (KeyError, ValueError) as falha:
        return EmendaMontada(emenda, None, motivo=f"travamentos do pilar: {falha}")
    kl_x, kl_y = eixo_x.governa.kl_mm, eixo_y.governa.kl_mm
    h = emenda.altura_m * 1000.0
    trecho = next(
        (t for t in eixo_x.trechos if t.de_mm - 1e-6 <= h <= t.ate_mm + 1e-6), eixo_x.trechos[0]
    )
    a = min(max(h - trecho.de_mm, 0.0), trecho.comprimento_mm * (1 - 1e-6))
    fy = ep.ACOS[aco][0]
    nc_rd = nc_rd_do_pilar(emenda.perfil_superior, fy, kl_x, kl_y, dados.norma)
    if nc_rd is None:
        notas.append("Sem o N_c,Rd da Flambagem de colunas: vale a estimativa da Emenda de pilar.")
    entrada = replace(
        padrao,
        perfil_superior=emenda.perfil_superior, perfil_inferior=emenda.perfil_inferior,
        aco_perfis=aco, Lx=kl_x, Kx=1.0, Ly=kl_y, Ky=1.0, a=a, vao_b=trecho.comprimento_mm,
        Nc_Rd_informado=nc_rd, casos=esforcos.casos,
    )  # fmt: skip
    notas.append(
        f"K·L_x = {_n(kl_x / 1000)} m e K·L_y = {_n(kl_y / 1000)} m pelos travamentos do esqueleto; "
        f"situação b no trecho de {_n(trecho.comprimento_mm / 1000)} m, a {_n(a / 1000)} m do "
        "travamento de baixo."
    )
    return EmendaMontada(emenda, entrada, tuple(notas))


# ---------------------------------------------------------------------------------------------
# Todas as emendas
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EmendaVerificada:
    emenda: EmendaDoModelo
    status: str  # "OK", "ALERTA", "NÃO OK" ou "PENDENTE"
    esforcos: EsforcosNaEmenda | None = None
    sugestao: ep.Sugestao | None = None
    notas: tuple[str, ...] = ()
    motivo: str = ""

    @property
    def resultado(self) -> ep.ResultadoEmenda | None:
        return None if self.sugestao is None else self.sugestao.resultado

    @property
    def aproveitamento(self) -> float | None:
        r = self.resultado
        return None if r is None else r.utilizacao_maxima


def preparar(
    dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas, estados: Sequence[str]
) -> em.PreparoDasCombinacoes | None:
    from core import verificacao_barras as vb

    return em.preparar_combinacoes(dados, plano, vb.estados_ultimos(estados))


def ler_esforcos(
    dados: em.EsforcosDoModelo,
    leituras: Sequence[ld.LeituraDaBarra],
    preparo: em.PreparoDasCombinacoes,
    emendas: Sequence[EmendaDoModelo],
) -> list[EsforcosNaEmenda]:
    saida = []
    for emenda in emendas:
        leitura = _corpo(leituras, emenda.barra)
        comprimento = None
        if leitura is not None:
            comprimento = leitura.comprimento_m or (
                leitura.corpo.comprimento_m if leitura.corpo is not None else None
            )
        saida.append(esforcos_na_emenda(emenda, dados, preparo, comprimento))
    return saida


def verificar_emendas(
    dados: em.EsforcosDoModelo,
    geometria: ld.GeometriaDoModelo,
    plano: pc.PlanoDeCargas,
    estados: Sequence[str],
    padrao: ep.EntradaEmenda,
    *,
    base: str = cdm.BASE_ROTULADA,
    leituras: Sequence[ld.LeituraDaBarra] | None = None,
) -> tuple[list[EmendaVerificada], list[str]]:
    """Todas as emendas do modelo, cada uma com as talas sugeridas para o parafuso do padrão."""
    if leituras is None:
        leituras = ld.ler_barras(dados, geometria, plano)
    preparo = preparar(dados, plano, estados)
    if preparo is None:
        return [], ["Nenhum caso do plano de cargas foi importado."]
    emendas = achar_emendas(dados, leituras)
    avisos: list[str] = []
    saida: list[EmendaVerificada] = []
    for esforcos in ler_esforcos(dados, leituras, preparo, emendas):
        avisos += esforcos.avisos
        montada = montar_entrada(esforcos, dados, geometria, leituras, padrao, base=base)
        if montada.entrada is None:
            saida.append(
                EmendaVerificada(esforcos.emenda, STATUS_PENDENTE, esforcos, motivo=montada.motivo)
            )
            continue
        try:
            sugestao = ep.sugerir_talas(montada.entrada)
        except ValueError as falha:
            saida.append(
                EmendaVerificada(esforcos.emenda, STATUS_PENDENTE, esforcos, motivo=str(falha))
            )
            continue
        notas = montada.notas + sugestao.notas
        if sugestao.resultado is None:
            saida.append(
                EmendaVerificada(
                    esforcos.emenda,
                    STATUS_PENDENTE,
                    esforcos,
                    sugestao,
                    notas,
                    motivo=sugestao.notas[0] if sugestao.notas else "as talas não cabem",
                )  # fmt: skip
            )
            continue
        r = sugestao.resultado
        if r.situacao != "ATENDE":
            status = "NÃO OK"
        elif r.itens_a_verificar:
            status = "ALERTA"
        else:
            status = "OK"
        saida.append(EmendaVerificada(esforcos.emenda, status, esforcos, sugestao, notas))
    return saida, avisos


# ---------------------------------------------------------------------------------------------
# Tabela e registro
# ---------------------------------------------------------------------------------------------
COLUNAS = (
    "Emenda",
    "Origem",
    "Perfis (de cima / de baixo)",
    "N máx. (kN)",
    "M_x máx. (kN·m)",
    "V máx. (kN)",
    "Talas da mesa",
    "Parafusos",
    "Aproveitamento (%)",
    "Situação",
    "Observação",
)
NOMES_DO_STATUS = {
    "OK": "Atende",
    "ALERTA": "Atende (verificar)",
    "NÃO OK": "Não atende",
    STATUS_PENDENTE: "Sem dados",
}


def linhas_da_tabela(verificadas: Sequence[EmendaVerificada]) -> list[list[object]]:
    linhas: list[list[object]] = []
    for v in verificadas:
        casos = v.esforcos.casos if v.esforcos is not None else ()
        n = max((c.N for c in casos), default=None)
        mx = max((abs(c.Mx) for c in casos), default=None)
        vv = max((abs(c.V) for c in casos), default=None)
        r = v.resultado
        e = v.sugestao.entrada if v.sugestao is not None else None
        talas = (
            f"{ep._n(e.bp)} × {ep._n(e.tp)} ({e.nl} × {e.nr} por lado)" if e is not None and r
            else ""
        )  # fmt: skip
        observacao = v.motivo
        if not observacao and r is not None:
            if r.situacao != "ATENDE":
                g = r.governante
                observacao = g.nome if g else ""
            elif r.itens_a_verificar:
                observacao = "; ".join(x.nome for x in r.itens_a_verificar)
        linhas.append(
            [
                v.emenda.nome,
                v.emenda.origem,
                f"{v.emenda.perfil_superior} / {v.emenda.perfil_inferior}",
                n,
                mx,
                vv,
                talas,
                r.total_de_parafusos if r is not None else None,
                None if v.aproveitamento is None else 100 * v.aproveitamento,
                NOMES_DO_STATUS.get(v.status, v.status),
                observacao,
            ]  # fmt: skip
        )
    return linhas


def _linha_do_registro(v: EmendaVerificada) -> Verificacao:
    if v.status == STATUS_PENDENTE or v.aproveitamento is None:
        return Verificacao(
            f"Emenda {v.emenda.nome}", None, None, "–", "Emenda de pilar",
            f"sem verificação: {v.motivo}", status="ALERTA", tipo="limite",
        )  # fmt: skip
    r = v.resultado
    assert r is not None
    g = r.governante
    linha = Verificacao(
        f"Emenda {v.emenda.nome}", v.aproveitamento, 1.0, "–",
        "NBR 8800:2025; SCI P207 5", f"utilização máxima ({g.nome if g else '—'})",
    )  # fmt: skip
    if v.status == "ALERTA":
        linha.status = "ALERTA"
        linha.formula += "; a verificar: " + "; ".join(x.nome for x in r.itens_a_verificar)
    return linha


def registro_das_emendas(
    verificadas: Sequence[EmendaVerificada],
    padrao: ep.EntradaEmenda,
    estados: Sequence[str],
    *,
    figuras: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    from core.verificacao import status_geral

    linhas = [_linha_do_registro(v) for v in verificadas]
    geral = status_geral(linhas) if linhas else "N/A"
    atendem = sum(1 for v in verificadas if v.status in ("OK", "ALERTA"))
    destaque = (
        f"{len(verificadas)} emenda(s) de pilar do modelo: {atendem} atendem, "
        f"{sum(1 for v in verificadas if v.status == 'NÃO OK')} não atendem e "
        f"{sum(1 for v in verificadas if v.status == STATUS_PENDENTE)} sem dados."
    )
    tabela = {
        "subtitulo": "Emendas do modelo",
        "legenda": "Cada emenda com os esforços de cálculo no ponto da emenda (pilar de cima), as "
        "talas da mesa adotadas e a utilização máxima.",
        "cabecalhos": list(COLUNAS),
        "linhas": [
            ["" if c is None else (ep._n(c, 1) if isinstance(c, float) else str(c)) for c in linha]
            for linha in linhas_da_tabela(verificadas)
        ],
        "fonte": 6.5,
    }
    resultados: dict[str, object] = {
        "status_geral": geral,
        "verificações": linhas_para_registro(linhas),
        "utilizacao_maxima": numero_json(
            max((v.aproveitamento or 0.0 for v in verificadas), default=0.0), 4
        ),
        "destaque_memorial": destaque,
        "tabelas_memorial": [tabela],
    }
    if figuras:
        resultados["figuras_2d"] = list(figuras)
    return criar_registro_tecnico(
        modulo=MODULO_TITULO,
        modulo_id=MODULO_ID,
        titulo=f"Emendas dos pilares do modelo — {len(verificadas)} emenda(s)",
        status=STATUS_REGISTRO.get(geral, "Pendente"),
        resumo=destaque,
        entradas={
            "parafuso": f"{padrao.diametro} {padrao.grau}",
            "aco_das_talas": padrao.aco_talas,
            "contato": padrao.contato,
            "estados_limites": ", ".join(estados),
        },
        resultados=resultados,
        metodo=(
            "Emendas dos pilares achadas no esqueleto do modelo (encontro de dois pilares em pé) "
            "ou informadas; esforços das combinações ELU no ponto da emenda, no pilar de cima, com o "
            "B₂ do tipo Pilar; cada emenda verificada pela Emenda de pilar (SCI P207, seção 5, e "
            "ABNT NBR 8800:2025) com as talas sugeridas para o parafuso adotado."
        ),
        premissas=[
            "Altura dos pontos do SolidWorks pela ordem dos elementos (malha uniforme ao longo da "
            "viga); emenda no meio da barra por interpolação linear entre os pontos vizinhos.",
            "K·L_x e K·L_y pelos travamentos do esqueleto; N_c,Rd do pilar de cima pela "
            "Flambagem de colunas (flexo-torção incluída).",
            "Talas sugeridas pelas regras de detalhamento da página Emenda de pilar; o parafuso, o "
            "aço das talas e o tipo de emenda são os mesmos para todas.",
        ],
        alertas=[f"{v.emenda.nome}: {v.motivo}" for v in verificadas if v.motivo],
        referencias=list(ep.REFERENCIAS),
        conclusao=destaque,
    )
