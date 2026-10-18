"""Guarda-corpos pelo esqueleto do modelo: as bordas livres do piso e as vigas que os apoiam.

O guarda-corpo fica nas bordas do piso que não encostam em outro piso, parafusado na viga da borda.
Com as chapas de piso que a macro do SolidWorks exporta (contorno e aberturas, macro v5) — plataforma,
patamar, lance de escada —, o programa:

1. percorre o contorno e as aberturas de cada chapa em estações a cada 5 cm e marca como **livre** a
   estação cujo lado de fora (12 cm para fora, no plano da chapa) não cai em nenhuma outra chapa a
   menos de 30 cm do plano dela. Onde o lance da escada encosta na plataforma há piso dos dois lados:
   é o acesso, e ali não entra guarda-corpo;
2. procura, para cada estação livre, a **viga que a apoia**: barra paralela à borda (até 12°), cuja
   projeção cobre a estação, logo abaixo da chapa (entre 5 cm acima e a altura da seção + 25 cm
   abaixo) e a até 35 cm da borda no plano da chapa — a mais perto. As estações seguidas com a mesma
   viga formam um **trecho**; num lance inclinado (> 10°) é guarda-corpo de escada, na longarina;
3. trecho livre **sem viga embaixo** vira aviso: o guarda-corpo dali precisa de apoio no modelo e
   não recebe carga.

Sem chapas de piso (macro antiga ou modelo sem piso), as bordas saem das vigas: em cada nível, a viga
horizontal que não tem outra paralela do mesmo nível de um dos lados é de borda. Nos dois métodos, o
**acesso da escada** que não está como chapa vem das longarinas: duas barras inclinadas paralelas, a
0,5–2,0 m uma da outra, com a ponta de cima junto da borda e descendo para fora do piso, tiram do
trecho o pedaço entre elas (uma mão-francesa, que desce para baixo do piso, não conta).

Tudo é sugestão para o engenheiro conferir (desmarcar o lado da parede, o portão…). Nada aqui levanta
exceção por geometria estranha: corpo com coordenada inválida, chapa sem área, viga de comprimento
zero ficam de fora, com o motivo nos avisos. Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core import cargas_pelo_modelo as cpm
from core import leitura_do_modelo as ld
from core import plano_de_cargas as pc
from core import travamentos as tv
from core import vento_por_barras as vpb

Ponto2 = tuple[float, float]
Ponto3 = tuple[float, float, float]

SITUACAO_GUARDA_CORPO = "guarda-corpo"
SITUACAO_ESCADA = "guarda-corpo da escada"
SITUACAO_ACESSO = "acesso da escada"
SITUACAO_SEM_VIGA = "sem viga embaixo"
SITUACAO_MAO = "guarda-corpo à mão"
SITUACAO_ACESSO_MAO = "acesso / portão à mão"
SITUACOES = (
    SITUACAO_GUARDA_CORPO,
    SITUACAO_ESCADA,
    SITUACAO_ACESSO,
    SITUACAO_SEM_VIGA,
    SITUACAO_MAO,
    SITUACAO_ACESSO_MAO,
)
COM_GUARDA_CORPO = frozenset({SITUACAO_GUARDA_CORPO, SITUACAO_ESCADA, SITUACAO_MAO})

#: Trechos lançados à mão: guarda-corpo onde o programa não achou, ou acesso/portão onde não tem.
TIPO_MAO_GUARDA_CORPO = "guarda-corpo"
TIPO_MAO_ACESSO = "acesso / portão"
TIPOS_A_MAO = (TIPO_MAO_GUARDA_CORPO, TIPO_MAO_ACESSO)

METODO_CHAPAS = "pelas chapas do piso"
METODO_VIGAS = "pelas vigas (sem chapas de piso)"
METODO_NENHUM = "sem piso no esqueleto"

PASSO_M = 0.05  # estações ao longo da borda
MAXIMO_DE_ESTACOES = 600  # por lado (lado de 30 m: passo de 5 cm)
AFASTAMENTO_M = 0.12  # para olhar o lado de fora (junta entre chapas até isso não é borda)
TOLERANCIA_DO_PLANO_M = 0.30  # o lado de fora "cai" numa chapa a menos disso do plano dela
DISTANCIA_DA_BORDA_M = 0.35  # a viga de borda fica até isso da borda, no plano da chapa
ACIMA_DA_VIGA_M = 0.05  # a estação pode ficar até isso abaixo da linha de centro da viga
ABAIXO_DA_ALTURA_M = 0.25  # e até a altura da seção mais isso acima dela
ALTURA_PADRAO_M = 0.30  # seção sem medida
SEN_PARALELA = math.sin(math.radians(12.0))
TRECHO_MINIMO_M = 0.10  # menos que isso é artefato de junta
INCLINACAO_DE_ESCADA_GRAUS = 10.0
TOLERANCIA_DO_NIVEL_M = 0.25  # método pelas vigas: vigas do mesmo nível
VIZINHA_MAXIMA_M = 15.0  # método pelas vigas: a paralela do outro lado até essa distância
SOBREPOSICAO_MINIMA = 0.30  # da viga mais curta
SECAO_MINIMA_DE_BORDA_M = 0.10  # cantoneira de enrijecimento não é viga de borda
COMPRIMENTO_MINIMO_DE_BORDA_M = 0.50
LONGARINA_INCLINACAO_GRAUS = (15.0, 65.0)
LONGARINA_NA_BORDA_M = 0.40
LARGURA_DE_ESCADA_M = (0.50, 2.00)

PESO_PADRAO_KN_M = 0.40  # ≈ 40 kg/m: guarda-corpo industrial com rodapé
ALTURA_PADRAO_GUARDA_CORPO_M = 1.10  # NR-12 Anexo III (1,10 m); o critério Anglo pede 1,30 m
ALTURA_ANGLO_M = 1.30
MARCA = cpm.MARCA_GUARDA_CORPO
ORIGEM = "Guarda-corpo pelo esqueleto"
CHAVE_DO_PROJETO = "guarda_corpo_do_modelo"


# ---------------------------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TrechoDeBorda:
    """Um trecho de borda livre do piso: onde fica, que viga o apoia e o que é."""

    id: str  # B1, B2… (para a tela)
    chave: str  # estável enquanto o esqueleto não muda (para guardar o que foi desmarcado)
    chapa: str  # "" no método pelas vigas
    inicio: Ponto3  # m, eixos do modelo, na borda do piso
    fim: Ponto3
    viga: str  # o corpo que apoia; "" sem viga
    viga_comprimento_m: float
    situacao: str
    motivo: str
    inclinacao_graus: float = 0.0
    desligado: bool = False  # achado, mas a opção dele está desligada (guarda-corpo dos lances)
    a_mao: bool = False  # lançado à mão pelo engenheiro

    @property
    def comprimento_m(self) -> float:
        return tv._norma(tv._sub(self.fim, self.inicio))

    @property
    def chave_base(self) -> str:
        """A chave do trecho achado (um acesso à mão pode dividi-lo em pedaços "#1", "#2")."""
        return self.chave.split("#", 1)[0]

    @property
    def sugerido(self) -> bool:
        """Entra marcado: tem guarda-corpo, uma viga para receber e a opção dele ligada."""
        return self.situacao in COM_GUARDA_CORPO and bool(self.viga) and not self.desligado


@dataclass(frozen=True)
class BordasDoPiso:
    trechos: tuple[TrechoDeBorda, ...] = ()
    metodo: str = METODO_NENHUM
    avisos: tuple[str, ...] = ()

    def comprimento(self, situacao: str) -> float:
        return sum(t.comprimento_m for t in self.trechos if t.situacao == situacao)

    def marcado(self, trecho: TrechoDeBorda, escolha: Mapping[str, bool] | None = None) -> bool:
        """Se o trecho entra: o lançado à mão entra sempre (a tabela à mão manda nele); o achado
        segue a escolha (pela chave dele ou do trecho de onde saiu) ou a sugestão."""
        if not trecho.viga:
            return False
        if trecho.a_mao:
            return trecho.situacao in COM_GUARDA_CORPO
        escolha = escolha or {}
        valor = escolha.get(trecho.chave, escolha.get(trecho.chave_base, trecho.sugerido))
        return bool(valor)

    def marcados(self, escolha: Mapping[str, bool] | None = None) -> list[TrechoDeBorda]:
        """Os trechos com guarda-corpo: a sugestão, com o que o engenheiro trocou (por chave)."""
        return [t for t in self.trechos if self.marcado(t, escolha)]


# ---------------------------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------------------------
def _finito(*valores: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in valores)


def _corpo_valido(c: ld.CorpoDoModelo) -> bool:
    return _finito(*c.inicio, *c.fim) and c.comprimento_m > 1e-6


def _altura_da_secao(c: ld.CorpoDoModelo) -> float:
    if c.secao_mm and _finito(*c.secao_mm) and max(c.secao_mm) > 0:
        return max(c.secao_mm) / 1000.0
    return ALTURA_PADRAO_M


def _no_espaco(chapa: cpm.ChapaDoPiso, p: Ponto2) -> Ponto3:
    o, a, b = chapa.origem, chapa.e1, chapa.e2
    return (
        o[0] + p[0] * a[0] + p[1] * b[0],
        o[1] + p[0] * a[1] + p[1] * b[1],
        o[2] + p[0] * a[2] + p[1] * b[2],
    )


def _dentro_da_chapa(chapa: cpm.ChapaDoPiso, p: Ponto2) -> bool:
    return cpm.dentro(p, chapa.poligono) and not any(cpm.dentro(p, a) for a in chapa.aberturas)


def _cai_em_outra_chapa(
    ponto: Ponto3, chapas: Sequence[cpm.ChapaDoPiso], propria: cpm.ChapaDoPiso
) -> str:
    """O nome da chapa em que o ponto cai (perto do plano dela), ou ""."""
    for outra in chapas:
        if outra is propria:
            continue
        if abs(outra.altura(ponto)) > TOLERANCIA_DO_PLANO_M:
            continue
        if _dentro_da_chapa(outra, outra.no_plano(ponto)):
            return outra.nome
    return ""


@dataclass(frozen=True)
class _Barra:
    corpo: ld.CorpoDoModelo
    eixo: Ponto3
    altura: float

    @property
    def nome(self) -> str:
        return self.corpo.nome


def _barras(g: ld.GeometriaDoModelo, avisos: list[str]) -> list[_Barra]:
    barras = []
    invalidas = []
    for c in g.corpos:
        if not c.e_barra or c.forma == ld.FORMA_BLOCO:
            continue
        if not _corpo_valido(c):
            invalidas.append(c.nome)
            continue
        eixo = tv._unitario(c.vetor)
        if eixo is None:
            invalidas.append(c.nome)
            continue
        barras.append(_Barra(c, eixo, _altura_da_secao(c)))
    if invalidas:
        avisos.append(
            "Barras com coordenada inválida ou comprimento zero ficaram de fora: "
            + ", ".join(invalidas[:6])
            + ("…" if len(invalidas) > 6 else "")
            + "."
        )
    return barras


def _viga_da_estacao(
    ponto: Ponto3, direcao: Ponto3, normal: Ponto3, barras: Sequence[_Barra]
) -> _Barra | None:
    """A barra que apoia a borda na estação: paralela, cobrindo, logo abaixo e a mais perto."""
    melhor: tuple[float, float, _Barra] | None = None
    for b in barras:
        if tv._norma(tv._cross(b.eixo, direcao)) > SEN_PARALELA:
            continue
        rel = tv._sub(ponto, b.corpo.inicio)
        t = tv._dot(rel, b.eixo)
        if t < -0.02 or t > b.corpo.comprimento_m + 0.02:
            continue
        perto = tuple(b.corpo.inicio[k] + t * b.eixo[k] for k in range(3))
        r = tv._sub(ponto, perto)
        acima = tv._dot(r, normal)  # a estação (a borda do piso) acima da linha de centro
        if not -ACIMA_DA_VIGA_M <= acima <= b.altura + ABAIXO_DA_ALTURA_M:
            continue
        lateral = tv._norma(tuple(r[k] - acima * normal[k] for k in range(3)))
        if lateral > DISTANCIA_DA_BORDA_M:
            continue
        # Cantoneira de enrijecimento perto da borda perde para a viga de verdade.
        penalidade = 0.20 if b.altura < SECAO_MINIMA_DE_BORDA_M else 0.0
        candidato = (lateral + penalidade, abs(acima), b)
        if melhor is None or candidato[:2] < melhor[:2]:
            melhor = candidato
    return None if melhor is None else melhor[2]


# ---------------------------------------------------------------------------------------------
# Método pelas chapas do piso
# ---------------------------------------------------------------------------------------------
@dataclass
class _Pedaco:
    chapa: str
    anel: int
    lado: int
    inicio: Ponto3
    fim: Ponto3
    viga: _Barra | None
    inclinacao: float
    vizinha: str = ""  # quando não é livre: a chapa do outro lado (o acesso)
    fora: Ponto3 | None = None  # para onde é o lado de fora (unitário), quando se sabe


def _bordas_pelas_chapas(
    chapas: Sequence[cpm.ChapaDoPiso], barras: Sequence[_Barra], avisos: list[str]
) -> list[_Pedaco]:
    pedacos: list[_Pedaco] = []
    for chapa in chapas:
        try:
            pedacos.extend(_bordas_da_chapa(chapa, chapas, barras, avisos))
        except (ArithmeticError, ValueError, IndexError) as erro:  # geometria estranha: segue
            avisos.append(f"{chapa.nome}: contorno não lido ({erro}); confira esta chapa à mão.")
    return pedacos


def _bordas_da_chapa(
    chapa: cpm.ChapaDoPiso,
    chapas: Sequence[cpm.ChapaDoPiso],
    barras: Sequence[_Barra],
    avisos: list[str],
) -> list[_Pedaco]:
    pedacos: list[_Pedaco] = []
    indefinidas = 0
    aneis = [chapa.poligono, *chapa.aberturas]
    for k_anel, anel in enumerate(aneis):
        if len(anel) < 3:
            continue
        for k_lado in range(len(anel)):
            a, b = anel[k_lado], anel[(k_lado + 1) % len(anel)]
            if not _finito(*a, *b):
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            comprimento = math.hypot(dx, dy)
            if comprimento < TRECHO_MINIMO_M / 2:
                continue
            n = max(2, min(MAXIMO_DE_ESTACOES, math.ceil(comprimento / PASSO_M)))
            perp = (-dy / comprimento, dx / comprimento)
            direcao = tv._unitario(tv._sub(_no_espaco(chapa, b), _no_espaco(chapa, a)))
            if direcao is None:
                continue
            atual: _Pedaco | None = None
            for i in range(n):
                s0, s1 = i / n, (i + 1) / n
                sm = (s0 + s1) / 2
                meio = (a[0] + sm * dx, a[1] + sm * dy)
                mais = (meio[0] + AFASTAMENTO_M * perp[0], meio[1] + AFASTAMENTO_M * perp[1])
                menos = (meio[0] - AFASTAMENTO_M * perp[0], meio[1] - AFASTAMENTO_M * perp[1])
                dentro_mais, dentro_menos = (
                    _dentro_da_chapa(chapa, mais),
                    _dentro_da_chapa(chapa, menos),
                )
                if dentro_mais == dentro_menos:
                    indefinidas += 1  # lado estreito ou contorno dobrado: não decide
                    atual = None
                    continue
                fora = menos if dentro_mais else mais
                vizinha = _cai_em_outra_chapa(_no_espaco(chapa, fora), chapas, chapa)
                p0 = _no_espaco(chapa, (a[0] + s0 * dx, a[1] + s0 * dy))
                p1 = _no_espaco(chapa, (a[0] + s1 * dx, a[1] + s1 * dy))
                viga = (
                    None
                    if vizinha
                    else _viga_da_estacao(_no_espaco(chapa, meio), direcao, chapa.normal, barras)
                )
                mesma = atual is not None and atual.vizinha == vizinha and (atual.viga is viga)
                if mesma and atual is not None:
                    atual.fim = p1
                else:
                    para_fora = tv._unitario(
                        tv._sub(_no_espaco(chapa, fora), _no_espaco(chapa, meio))
                    )
                    atual = _Pedaco(
                        chapa.nome,
                        k_anel,
                        k_lado,
                        p0,
                        p1,
                        viga,
                        chapa.inclinacao_graus,
                        vizinha,
                        para_fora,
                    )
                    pedacos.append(atual)
    if indefinidas > 20:
        avisos.append(
            f"{chapa.nome}: {indefinidas} pontos do contorno sem lado de dentro claro (chapa "
            "estreita ou contorno dobrado) — confira as bordas dela."
        )
    return pedacos


# ---------------------------------------------------------------------------------------------
# Método pelas vigas (sem chapas de piso)
# ---------------------------------------------------------------------------------------------
def _bordas_pelas_vigas(
    barras: Sequence[_Barra], eixo_vertical: str, avisos: list[str]
) -> list[_Pedaco]:
    """Sem chapas: ao longo de cada viga horizontal de piso, a estação que tem paralela do mesmo
    nível só de um lado é borda (o lado sem paralela é o de fora)."""
    cima = tv.vertical(eixo_vertical)
    horizontais = [
        b
        for b in barras
        if abs(tv._dot(b.eixo, cima)) <= 0.10
        and b.altura >= SECAO_MINIMA_DE_BORDA_M
        and b.corpo.comprimento_m >= COMPRIMENTO_MINIMO_DE_BORDA_M
    ]
    if not horizontais:
        return []

    def cota(b: _Barra) -> float:
        return tv._dot(b.corpo.inicio, cima) / 2 + tv._dot(b.corpo.fim, cima) / 2

    pedacos: list[_Pedaco] = []
    isoladas = []
    for b in horizontais:
        horizontal = tv._unitario(
            tuple(b.eixo[k] - tv._dot(b.eixo, cima) * cima[k] for k in range(3))
        )
        if horizontal is None:
            continue
        lateral = tv._unitario(tv._cross(cima, horizontal))
        if lateral is None:
            continue
        comprimento = b.corpo.comprimento_m
        meio_b = tuple((b.corpo.inicio[k] + b.corpo.fim[k]) / 2 for k in range(3))
        # As paralelas do mesmo nível: (lado, trecho que cobrem ao longo de b).
        vizinhas: list[tuple[int, float, float]] = []
        for c in horizontais:
            if c is b or abs(cota(c) - cota(b)) > TOLERANCIA_DO_NIVEL_M:
                continue
            if tv._norma(tv._cross(c.eixo, b.eixo)) > SEN_PARALELA:
                continue
            meio_c = tuple((c.corpo.inicio[k] + c.corpo.fim[k]) / 2 for k in range(3))
            afastamento = tv._dot(tv._sub(meio_c, meio_b), lateral)
            if not 0.20 <= abs(afastamento) <= VIZINHA_MAXIMA_M:
                continue
            t0, t1 = sorted(
                tv._dot(tv._sub(p, b.corpo.inicio), horizontal)
                for p in (c.corpo.inicio, c.corpo.fim)
            )
            vizinhas.append((1 if afastamento > 0 else -1, t0 - 0.05, t1 + 0.05))
        if not vizinhas:
            isoladas.append(b.nome)
            continue
        n = max(2, min(MAXIMO_DE_ESTACOES, math.ceil(comprimento / (2 * PASSO_M))))
        topo = tuple(b.altura / 2 * cima[k] for k in range(3))

        def ponto(t: float, b: _Barra = b, h: Ponto3 = horizontal, o: tuple = topo) -> Ponto3:
            return tuple(b.corpo.inicio[k] + t * h[k] + o[k] for k in range(3))

        atual: _Pedaco | None = None
        lado_atual = 0
        for i in range(n):
            t0, t1 = comprimento * i / n, comprimento * (i + 1) / n
            tm = (t0 + t1) / 2
            cobertos = {lado for lado, a, c in vizinhas if a <= tm <= c}
            if len(cobertos) != 1:
                atual, lado_atual = None, 0  # interna (dos dois lados) ou sem piso nenhum
                continue
            fora_sinal = -next(iter(cobertos))  # o lado de fora é o sem vizinha
            if atual is not None and lado_atual == fora_sinal:
                atual.fim = ponto(t1)
                continue
            atual = _Pedaco(
                "",
                0,
                0,
                ponto(t0),
                ponto(t1),
                b,
                0.0,
                fora=tuple(fora_sinal * lateral[k] for k in range(3)),  # type: ignore[arg-type]
            )
            lado_atual = fora_sinal
            pedacos.append(atual)
    if isoladas:
        avisos.append(
            "Vigas horizontais sem nenhuma paralela no mesmo nível (não dá para dizer se são de "
            "piso) ficaram de fora: "
            + ", ".join(isoladas[:6])
            + ("…" if len(isoladas) > 6 else "")
            + "."
        )
    return pedacos


# ---------------------------------------------------------------------------------------------
# Acesso da escada pelas longarinas
# ---------------------------------------------------------------------------------------------
def _longarinas(
    barras: Sequence[_Barra], eixo_vertical: str
) -> list[tuple[_Barra, Ponto3, Ponto3]]:
    """Barras inclinadas como longarina, pelas duas pontas: (barra, a ponta, a direção horizontal
    dela para a outra ponta). A escada pode sair da borda descendo ou chegar nela subindo."""
    cima = tv.vertical(eixo_vertical)
    minimo, maximo = (math.sin(math.radians(a)) for a in LONGARINA_INCLINACAO_GRAUS)
    resultado = []
    for b in barras:
        seno = abs(tv._dot(b.eixo, cima))
        if not minimo <= seno <= maximo:
            continue
        for ponta, outra in ((b.corpo.inicio, b.corpo.fim), (b.corpo.fim, b.corpo.inicio)):
            ida = tv._sub(outra, ponta)
            horizontal = tv._unitario(
                tuple(ida[k] - tv._dot(ida, cima) * cima[k] for k in range(3))
            )
            if horizontal is not None:
                resultado.append((b, ponta, horizontal))
    return resultado


def _acessos(
    pedacos: Sequence[_Pedaco],
    barras: Sequence[_Barra],
    eixo_vertical: str,
    dentro_do_piso: Any,
) -> list[_Pedaco]:
    """Divide os pedaços livres onde duas longarinas chegam (o acesso da escada)."""
    longarinas = _longarinas(barras, eixo_vertical)
    if len(longarinas) < 2:
        return list(pedacos)
    cima = tv.vertical(eixo_vertical)
    saida: list[_Pedaco] = []
    for p in pedacos:
        if p.vizinha or p.viga is None:
            saida.append(p)
            continue
        direcao = tv._unitario(tv._sub(p.fim, p.inicio))
        comprimento = tv._norma(tv._sub(p.fim, p.inicio))
        if direcao is None:
            saida.append(p)
            continue
        chegadas = []
        for b, ponta, sentido in longarinas:
            rel = tv._sub(ponta, p.inicio)
            t = tv._dot(rel, direcao)
            if t < -0.1 or t > comprimento + 0.1:
                continue
            perto = tuple(p.inicio[k] + t * direcao[k] for k in range(3))
            if tv._norma(tv._sub(ponta, perto)) > LONGARINA_NA_BORDA_M:
                continue
            # A longarina sai da borda para fora do piso; a mão-francesa e o travamento vão para
            # baixo dele.
            if p.fora is not None:
                if tv._dot(sentido, p.fora) < 0.5:
                    continue
            elif abs(tv._dot(sentido, direcao)) > 0.5:
                continue
            fora = tuple(perto[k] + 0.6 * sentido[k] for k in range(3))
            if dentro_do_piso(fora, tv._dot(perto, cima)):
                continue
            chegadas.append((t, b, sentido))
        corte: tuple[float, float, str] | None = None
        maior = 0.0
        for i, (t0, b0, d0) in enumerate(chegadas):
            for t1, b1, d1 in chegadas[i + 1 :]:
                if b1 is b0:
                    continue
                largura = abs(t1 - t0)
                if (
                    LARGURA_DE_ESCADA_M[0] <= largura <= LARGURA_DE_ESCADA_M[1]
                    and tv._dot(d0, d1) > 0.9
                    and largura > maior
                ):
                    a, c = sorted((t0, t1))
                    nomes = " e ".join(sorted((b0.nome, b1.nome)))
                    corte, maior = (max(a, 0.0), min(c, comprimento), nomes), largura
        if corte is None:
            saida.append(p)
            continue
        t0, t1, nomes = corte

        def ponto(t: float, p: _Pedaco = p, d: Ponto3 = direcao) -> Ponto3:
            return tuple(p.inicio[k] + t * d[k] for k in range(3))  # type: ignore[return-value]

        if t0 > TRECHO_MINIMO_M:
            saida.append(replace(p, fim=ponto(t0)))
        acesso = replace(p, inicio=ponto(t0), fim=ponto(t1), vizinha=f"longarinas {nomes}")
        saida.append(acesso)
        if comprimento - t1 > TRECHO_MINIMO_M:
            saida.append(replace(p, inicio=ponto(t1)))
    return saida


# ---------------------------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------------------------
def _horizontal(p: _Pedaco, cima: Ponto3) -> bool:
    direcao = tv._unitario(tv._sub(p.fim, p.inicio))
    return direcao is not None and abs(tv._dot(direcao, cima)) < math.sin(math.radians(5.0))


def _arredonda(p: Sequence[float]) -> str:
    return ",".join(f"{v:.2f}" for v in p)


def _trechos(
    pedacos: Sequence[_Pedaco],
    metodo: str,
    eixo_vertical: str,
    avisos: list[str],
    *,
    guarda_corpo_nos_lances: bool = True,
) -> list[TrechoDeBorda]:
    cima = tv.vertical(eixo_vertical)
    trechos: list[TrechoDeBorda] = []
    sem_viga = 0.0
    for p in pedacos:
        comprimento = tv._norma(tv._sub(p.fim, p.inicio))
        if comprimento < TRECHO_MINIMO_M:
            continue
        if p.vizinha.startswith("longarinas"):
            situacao, motivo = SITUACAO_ACESSO, f"chegada da escada ({p.vizinha})"
        elif p.vizinha:
            continue  # piso dos dois lados: não é borda
        elif p.inclinacao > INCLINACAO_DE_ESCADA_GRAUS and _horizontal(p, cima):
            # O lado em nível de um lance é a ponta dele (o pé ou o topo): é por onde se passa.
            situacao, motivo = SITUACAO_ACESSO, "ponta do lance (pé ou topo da escada)"
        elif p.viga is None:
            situacao, motivo = SITUACAO_SEM_VIGA, "borda livre sem viga embaixo no esqueleto"
            sem_viga += comprimento
        elif p.inclinacao > INCLINACAO_DE_ESCADA_GRAUS:
            situacao = SITUACAO_ESCADA
            motivo = f"borda do lance ({p.inclinacao:.0f}°) na longarina"
            if not guarda_corpo_nos_lances:
                motivo += " — guarda-corpo dos lances desligado"
        else:
            situacao = SITUACAO_GUARDA_CORPO
            motivo = (
                "borda livre do piso"
                if metodo == METODO_CHAPAS
                else ("sem viga paralela do lado de fora (pelas vigas: confira)")
            )
        viga = p.viga.nome if p.viga is not None else ""
        trechos.append(
            TrechoDeBorda(
                id="",
                chave=f"{p.chapa}|{p.anel}.{p.lado}|{viga}|{_arredonda(p.inicio)}",
                chapa=p.chapa,
                inicio=p.inicio,
                fim=p.fim,
                viga=viga,
                viga_comprimento_m=p.viga.corpo.comprimento_m if p.viga is not None else 0.0,
                situacao=situacao,
                motivo=motivo,
                inclinacao_graus=p.inclinacao,
                desligado=situacao == SITUACAO_ESCADA and not guarda_corpo_nos_lances,
            )
        )
    if sem_viga > 0:
        avisos.append(
            f"{sem_viga:.2f} m de borda livre sem viga embaixo no esqueleto: o guarda-corpo dali "
            "precisa de apoio no modelo (ou a borda é uma parede) — confira.".replace(".", ",", 1)
        )
    trechos.sort(key=lambda t: (t.chapa, t.chave))
    return [replace(t, id=f"B{k}") for k, t in enumerate(trechos, start=1)]


def bordas_do_piso(
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    *,
    acesso_pelas_longarinas: bool = True,
    guarda_corpo_nos_lances: bool = True,
) -> BordasDoPiso:
    """As bordas livres do piso do esqueleto, com a viga de cada trecho e o que ele é.

    ``acesso_pelas_longarinas=False`` não procura o acesso da escada pelas longarinas (o que vem
    das chapas fica: lance encostado é piso dos dois lados); ``guarda_corpo_nos_lances=False`` deixa
    os trechos dos lances desmarcados.
    """
    avisos: list[str] = []
    if not g.corpos:
        return BordasDoPiso(avisos=("Sem o esqueleto do modelo.",))
    barras = _barras(g, avisos)
    try:
        chapas, fora = cpm.chapas_do_piso(g, eixo_vertical)
    except (ArithmeticError, ValueError, IndexError) as erro:
        chapas, fora = [], []
        avisos.append(f"As chapas do esqueleto não foram lidas ({erro}): bordas pelas vigas.")
    chapas = [c for c in chapas if all(_finito(*p) for p in c.poligono)]
    for f in fora:
        avisos.append(f"{f.nome}: {f.motivo} — as bordas dela não entram.")
    if chapas:
        metodo = METODO_CHAPAS
        pedacos = _bordas_pelas_chapas(chapas, barras, avisos)

        def dentro_do_piso(ponto: Ponto3, _cota: float) -> bool:
            return any(
                abs(c.altura(ponto)) <= TOLERANCIA_DO_PLANO_M + 0.6
                and _dentro_da_chapa(c, c.no_plano(ponto))
                for c in chapas
            )
    else:
        metodo = METODO_VIGAS
        pedacos = _bordas_pelas_vigas(barras, eixo_vertical, avisos)
        if pedacos:
            avisos.append(
                "O esqueleto não tem chapas de piso: as bordas saíram das vigas (a que não tem "
                "paralela de um dos lados). Confira — com as chapas (macro v5) o programa vê o "
                "contorno de verdade, os recortes e o acesso da escada."
            )

        def dentro_do_piso(ponto: Ponto3, _cota: float) -> bool:
            return False

    if acesso_pelas_longarinas:
        try:
            pedacos = _acessos(pedacos, barras, eixo_vertical, dentro_do_piso)
        except (ArithmeticError, ValueError, IndexError) as erro:
            avisos.append(f"O acesso da escada pelas longarinas não foi procurado ({erro}).")
    trechos = _trechos(
        pedacos, metodo, eixo_vertical, avisos, guarda_corpo_nos_lances=guarda_corpo_nos_lances
    )
    if not trechos:
        metodo = METODO_NENHUM if not chapas else metodo
    return BordasDoPiso(tuple(trechos), metodo, tuple(dict.fromkeys(avisos)))


# ---------------------------------------------------------------------------------------------
# Trechos à mão
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TrechoAMao:
    """O que o engenheiro lança: numa viga, de ``de_m`` a ``ate_m`` ao longo dela (vazio: a viga
    inteira), um guarda-corpo ou um acesso/portão."""

    viga: str
    de_m: float | None = None
    ate_m: float | None = None
    tipo: str = TIPO_MAO_GUARDA_CORPO


def _parametro(trecho: TrechoDeBorda, corpo: ld.CorpoDoModelo, eixo: Ponto3) -> tuple[float, float]:
    return (
        tv._dot(tv._sub(trecho.inicio, corpo.inicio), eixo),
        tv._dot(tv._sub(trecho.fim, corpo.inicio), eixo),
    )


def _sem_o_intervalo(
    trecho: TrechoDeBorda, corpo: ld.CorpoDoModelo, eixo: Ponto3, a: float, b: float
) -> list[TrechoDeBorda]:
    """O trecho sem a parte que fica entre ``a`` e ``b`` ao longo da viga (0, 1 ou 2 pedaços)."""
    ta, tb = _parametro(trecho, corpo, eixo)
    lo, hi = min(ta, tb), max(ta, tb)
    if hi <= a + 1e-9 or lo >= b - 1e-9 or abs(tb - ta) < 1e-9:
        return [trecho]

    def ponto(t: float) -> Ponto3:
        s = (t - ta) / (tb - ta)
        return tuple(trecho.inicio[k] + s * (trecho.fim[k] - trecho.inicio[k]) for k in range(3))  # type: ignore[return-value]

    pedacos = []
    for j, (p, q) in enumerate(((lo, min(hi, a)), (max(lo, b), hi)), start=1):
        if q - p >= TRECHO_MINIMO_M:
            # mantém o sentido do trecho original
            inicio, fim = (ponto(p), ponto(q)) if tb >= ta else (ponto(q), ponto(p))
            pedacos.append(replace(trecho, inicio=inicio, fim=fim, chave=f"{trecho.chave}#{j}"))
    return pedacos


def aplicar_trechos_a_mao(
    bordas: BordasDoPiso,
    g: ld.GeometriaDoModelo,
    eixo_vertical: str,
    manuais: Sequence[TrechoAMao],
) -> BordasDoPiso:
    """As bordas com os trechos à mão: o guarda-corpo à mão entra no lugar do que o programa
    achou naquela parte da viga (sem contar duas vezes); o acesso/portão à mão tira o guarda-corpo
    daquela parte. Viga que não existe, faixa fora da viga ou invertida viram aviso."""
    if not manuais:
        return bordas
    avisos = list(bordas.avisos)
    corpos = {c.nome: c for c in g.corpos if c.e_barra and _corpo_valido(c)}
    cima = tv.vertical(eixo_vertical)
    trechos = list(bordas.trechos)
    for k, m in enumerate(manuais, start=1):
        rotulo = f"Trecho à mão {k} ({m.viga or 'sem viga'})"
        if m.tipo not in TIPOS_A_MAO:
            avisos.append(f"{rotulo}: tipo desconhecido ({m.tipo!r}) — ficou de fora.")
            continue
        corpo = corpos.get(m.viga)
        if corpo is None:
            avisos.append(
                f"{rotulo}: a viga não está no esqueleto (ou não é barra) — ficou de fora."
            )
            continue
        eixo = tv._unitario(corpo.vetor)
        if eixo is None:
            continue
        comprimento = corpo.comprimento_m
        a = 0.0 if m.de_m is None else m.de_m
        b = comprimento if m.ate_m is None else m.ate_m
        if not _finito(a, b):
            avisos.append(f"{rotulo}: início ou fim inválido — ficou de fora.")
            continue
        if a > b:
            a, b = b, a
            avisos.append(f"{rotulo}: o início vinha depois do fim; foi invertido.")
        if a < -0.01 or b > comprimento + 0.01:
            avisos.append(
                f"{rotulo}: a faixa passa da viga (0 a {comprimento:.2f} m); foi cortada nela.".replace(
                    ".", ",", 1
                )
            )
        a, b = max(0.0, a), min(comprimento, b)
        if b - a < TRECHO_MINIMO_M:
            avisos.append(f"{rotulo}: menos de {TRECHO_MINIMO_M * 100:.0f} cm — ficou de fora.")
            continue
        novos: list[TrechoDeBorda] = []
        for t in trechos:
            novos.extend(_sem_o_intervalo(t, corpo, eixo, a, b) if t.viga == m.viga else [t])
        trechos = novos
        topo = tuple(_altura_da_secao(corpo) / 2 * cima[i] for i in range(3))

        def ponto(
            t: float, c: ld.CorpoDoModelo = corpo, u: Ponto3 = eixo, o: tuple = topo
        ) -> Ponto3:
            return tuple(c.inicio[i] + t * u[i] + o[i] for i in range(3))

        guarda_corpo = m.tipo == TIPO_MAO_GUARDA_CORPO
        trechos.append(
            TrechoDeBorda(
                id=f"M{k}",
                chave=f"mão|{k}|{m.viga}|{a:.2f}-{b:.2f}",
                chapa="",
                inicio=ponto(a),
                fim=ponto(b),
                viga=m.viga,
                viga_comprimento_m=comprimento,
                situacao=SITUACAO_MAO if guarda_corpo else SITUACAO_ACESSO_MAO,
                motivo=f"lançado à mão, de {a:.2f} a {b:.2f} m da viga".replace(".", ","),
                a_mao=True,
            )
        )
    automaticos = [t for t in trechos if not t.a_mao]
    renumerados = [replace(t, id=f"B{i}") for i, t in enumerate(automaticos, start=1)]
    return BordasDoPiso(
        tuple([*renumerados, *(t for t in trechos if t.a_mao)]),
        bordas.metodo,
        tuple(dict.fromkeys(avisos)),
    )


def bordas_do_projeto(
    g: ld.GeometriaDoModelo, eixo_vertical: str, escolha: EscolhaDoGuardaCorpo
) -> BordasDoPiso:
    """As bordas com as opções e os trechos à mão do engenheiro."""
    bordas = bordas_do_piso(
        g,
        eixo_vertical,
        acesso_pelas_longarinas=escolha.acesso_pelas_longarinas,
        guarda_corpo_nos_lances=escolha.guarda_corpo_nos_lances,
    )
    return aplicar_trechos_a_mao(bordas, g, eixo_vertical, escolha.a_mao)


# ---------------------------------------------------------------------------------------------
# Peso no plano de cargas
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PesoNaViga:
    viga: str
    rotulo: str
    trechos: tuple[str, ...]
    comprimento_com_guarda_corpo_m: float
    comprimento_da_viga_m: float
    peso_kN_m: float

    @property
    def total_kN(self) -> float:
        return self.peso_kN_m * self.comprimento_com_guarda_corpo_m

    @property
    def kN_m_na_viga(self) -> float:
        """Uniforme na viga inteira (como o piso): o total ÷ o comprimento da viga."""
        return self.total_kN / self.comprimento_da_viga_m if self.comprimento_da_viga_m > 0 else 0.0


def pesos_nas_vigas(
    trechos: Iterable[TrechoDeBorda],
    peso_kN_m: float,
    nomes_no_simulation: Mapping[str, str] | None = None,
) -> list[PesoNaViga]:
    if not (math.isfinite(peso_kN_m) and peso_kN_m >= 0):
        raise ValueError("O peso do guarda-corpo precisa ser um número positivo (kN/m).")
    nomes = nomes_no_simulation or {}
    por_viga: dict[str, list[TrechoDeBorda]] = {}
    for t in trechos:
        if t.viga and t.viga_comprimento_m > 0:
            por_viga.setdefault(t.viga, []).append(t)
    pesos = []
    for viga, lista in sorted(por_viga.items()):
        rotulo = f"{viga} ({nomes[viga]})" if viga in nomes else viga
        pesos.append(
            PesoNaViga(
                viga=viga,
                rotulo=rotulo,
                trechos=tuple(t.id for t in lista),
                comprimento_com_guarda_corpo_m=sum(t.comprimento_m for t in lista),
                comprimento_da_viga_m=lista[0].viga_comprimento_m,
                peso_kN_m=peso_kN_m,
            )
        )
    return pesos


def e_linha_de_guarda_corpo(carga: pc.CargaDoModelo) -> bool:
    return carga.observacao.startswith(MARCA)


def _sem_o_resumo_do_guarda_corpo(resumo: str) -> str:
    return resumo.split(f" | {MARCA}")[0].removeprefix(f"{MARCA}:").strip() if resumo else ""


def aplicar_peso_no_plano(
    plano: pc.PlanoDeCargas, pesos: Sequence[PesoNaViga], caso: str = "PE"
) -> pc.PlanoDeCargas:
    """O plano com o peso do guarda-corpo nas vigas de borda, no caso dado. As outras linhas do caso
    (o piso, por exemplo) ficam; as do guarda-corpo de um envio anterior são trocadas."""
    linhas = [
        pc.CargaDoModelo(
            elemento=p.rotulo,
            valor=round(p.kN_m_na_viga, 5),
            unidade="kN/m",
            direcao=cpm.VERTICAL,
            observacao=(
                f"{MARCA}: {p.peso_kN_m:.3f} kN/m × {p.comprimento_com_guarda_corpo_m:.2f} m "
                f"({', '.join(p.trechos)}) = {p.total_kN:.3f} kN, uniforme na viga de "
                f"{p.comprimento_da_viga_m:.2f} m"
            ).replace(".", ","),
            comprimento_m=round(p.comprimento_da_viga_m, 4),
        )
        for p in pesos
        if p.total_kN > 0
    ]
    total = sum(p.total_kN for p in pesos)
    frase = f"{MARCA}: {total:.2f} kN em {len(linhas)} vigas".replace(".", ",")
    anterior = plano.acao(caso)
    if anterior is None:
        if not linhas:
            return plano
        acao = pc.nova_acao(caso, origem=ORIGEM, resumo=frase, cargas=linhas)
    else:
        mantidas = [c for c in anterior.cargas if not e_linha_de_guarda_corpo(c)]
        base = _sem_o_resumo_do_guarda_corpo(anterior.resumo)
        resumo = f"{base} | {frase}" if base and linhas else (base or (frase if linhas else ""))
        acao = replace(
            anterior, cargas=tuple([*mantidas, *linhas]), resumo=resumo, atualizado_em=pc.agora()
        )
    return pc.com_acao(plano, acao)


# ---------------------------------------------------------------------------------------------
# Vento: os guarda-corpos como elementos do vento barra a barra
# ---------------------------------------------------------------------------------------------
def elementos_ao_vento(
    trechos: Iterable[TrechoDeBorda],
    eixo_vertical: str,
    *,
    altura_m: float = ALTURA_PADRAO_GUARDA_CORPO_M,
    phi: float = vpb.PHI_PADRAO[vpb.TIPO_GUARDA_CORPO],
) -> list[vpb.ElementoAoVento]:
    """Um guarda-corpo (reticulado plano) por trecho, na viga que o apoia."""
    return [
        vpb.ElementoAoVento(
            nome=f"GC {t.id}",
            tipo=vpb.TIPO_GUARDA_CORPO,
            ponto_1=vpb.para_a_planta(t.inicio, eixo_vertical),
            ponto_2=vpb.para_a_planta(t.fim, eixo_vertical),
            altura_m=altura_m,
            phi=phi,
            barra=t.viga,
        )
        for t in trechos
        if t.viga and t.comprimento_m >= TRECHO_MINIMO_M
    ]


# ---------------------------------------------------------------------------------------------
# O que fica guardado no projeto
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class EscolhaDoGuardaCorpo:
    """O que o engenheiro decidiu: os trechos trocados (marcado/desmarcado), o peso, a altura e φ."""

    trocados: Mapping[str, bool] = field(default_factory=dict)
    peso_kN_m: float = PESO_PADRAO_KN_M
    altura_m: float = ALTURA_PADRAO_GUARDA_CORPO_M
    phi: float = vpb.PHI_PADRAO[vpb.TIPO_GUARDA_CORPO]
    acesso_pelas_longarinas: bool = True
    guarda_corpo_nos_lances: bool = True
    a_mao: tuple[TrechoAMao, ...] = ()


def _numero(valor: Any, padrao: float, minimo: float, maximo: float) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    return numero if math.isfinite(numero) and minimo <= numero <= maximo else padrao


def escolha_do_projeto(projeto: Mapping[str, Any] | None) -> EscolhaDoGuardaCorpo:
    """Lê o que está guardado no projeto; o que vier estragado volta ao padrão (nunca levanta)."""
    dados = (projeto or {}).get(CHAVE_DO_PROJETO) if isinstance(projeto, Mapping) else None
    if not isinstance(dados, Mapping):
        return EscolhaDoGuardaCorpo()
    trocados_brutos = dados.get("trocados")
    trocados = (
        {str(k): bool(v) for k, v in trocados_brutos.items() if isinstance(v, bool)}
        if isinstance(trocados_brutos, Mapping)
        else {}
    )
    return EscolhaDoGuardaCorpo(
        trocados=trocados,
        peso_kN_m=_numero(dados.get("peso_kN_m"), PESO_PADRAO_KN_M, 0.0, 10.0),
        altura_m=_numero(dados.get("altura_m"), ALTURA_PADRAO_GUARDA_CORPO_M, 0.3, 3.0),
        phi=_numero(dados.get("phi"), vpb.PHI_PADRAO[vpb.TIPO_GUARDA_CORPO], 0.01, 1.0),
        acesso_pelas_longarinas=_logico(dados.get("acesso_pelas_longarinas"), True),
        guarda_corpo_nos_lances=_logico(dados.get("guarda_corpo_nos_lances"), True),
        a_mao=_trechos_gravados(dados.get("a_mao")),
    )


def _logico(valor: Any, padrao: bool) -> bool:
    return valor if isinstance(valor, bool) else padrao


def _opcional(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _trechos_gravados(valor: Any) -> tuple[TrechoAMao, ...]:
    if not isinstance(valor, (list, tuple)):
        return ()
    trechos = []
    for item in valor[:200]:
        if not isinstance(item, Mapping):
            continue
        viga = str(item.get("viga") or "").strip()
        tipo = str(item.get("tipo") or TIPO_MAO_GUARDA_CORPO)
        if viga and tipo in TIPOS_A_MAO:
            trechos.append(
                TrechoAMao(viga, _opcional(item.get("de_m")), _opcional(item.get("ate_m")), tipo)
            )
    return tuple(trechos)


def para_dicionario(
    escolha: EscolhaDoGuardaCorpo, bordas: BordasDoPiso | None = None
) -> dict[str, Any]:
    """Para gravar: só os trocados que ainda existem no esqueleto (com ``bordas``)."""
    validas = {t.chave: t.sugerido for t in bordas.trechos} if bordas is not None else None
    trocados = {
        k: v
        for k, v in escolha.trocados.items()
        if validas is None or (k in validas and validas[k] != v)
    }
    return {
        "trocados": trocados,
        "peso_kN_m": escolha.peso_kN_m,
        "altura_m": escolha.altura_m,
        "phi": escolha.phi,
        "acesso_pelas_longarinas": escolha.acesso_pelas_longarinas,
        "guarda_corpo_nos_lances": escolha.guarda_corpo_nos_lances,
        "a_mao": [
            {"viga": m.viga, "de_m": m.de_m, "ate_m": m.ate_m, "tipo": m.tipo}
            for m in escolha.a_mao
        ],
    }
