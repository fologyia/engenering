"""Leitura do modelo: o que o programa entende dos arquivos do SolidWorks e o que parece errado.

Os arquivos do SolidWorks dizem números; aqui eles viram entendimento:

* **Esqueleto** (macro ``exportar_lista_de_corte.bas`` → ``<peça>_esqueleto.csv``): cada corpo com
  as pontas da linha de centro, o comprimento, o item da lista de corte e o volume. Com ele cada
  viga do Simulation ("Viga-12(<corpo>)") ganha posição: vertical é pilar, horizontal é viga,
  inclinada é contraventamento; o comprimento vira o comprimento de flambagem inicial; o item da
  lista de corte (conferido pela área real da seção) dá o perfil — inclusive das barras
  "Aparar/Estender", cujo nome não diz o perfil.
* **Barra a barra, pelos esforços**: as pontas soltas (todos os esforços nulos — junta que faltou
  no SolidWorks), articuladas (sem momento) ou rígidas; barras sem esforço em caso nenhum; a malha
  grossa que deixa o máximo do meio do vão entre dois nós; o comportamento (só força normal: barra
  articulada ou contraventamento; normal que cresce com o peso próprio: barra não horizontal).
* **O conjunto** (:func:`diagnosticar`): estudo duplicado do PP que ficou com a gravidade, dois
  casos com o mesmo resultado, estudo sem carga, modelo que mudou entre os estudos, malha diferente
  entre os estudos, eixo vertical trocado, valores fora de escala (unidade), barras sem corpo no
  esqueleto.
* **Na hora de enviar** (:func:`avisos_da_importacao`): o mesmo caso em dois arquivos, nome do
  estudo que não bate com o caso escolhido, reações de outro estudo.

As **sugestões** (:func:`aplicar_sugestoes`) preenchem a tabela das barras só onde ela está vazia:
nada do que foi escolhido à mão é trocado.

Sem Streamlit.
"""

from __future__ import annotations

import math
import re
import statistics
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from core import cantoneiras as ct
from core import esforcos_modelo as em
from core import lista_de_material as lm
from core import plano_de_cargas as pc
from core import section_catalog as sc
from core import steel_sections as ss

TIPO_ESQUELETO = "Esqueleto do modelo"
TIPO_LISTA_DE_CORTE = "Lista de corte"
PONTA_SOLTA = "solta"
PONTA_ARTICULADA = "articulada"
PONTA_RIGIDA = "rígida"
PONTA_SEM_ESFORCO = "sem esforço"
TIPO_PILAR, TIPO_VIGA, TIPO_CONTRAVENTAMENTO = "Pilar", "Viga", "Contraventamento"
VERTICAL_MINIMO = 0.97  # cosseno com a vertical para ser pilar (~14°)
HORIZONTAL_MAXIMO = 0.03  # seno com a horizontal para ser viga ou barra do piso
ALINHADO_MINIMO = 0.985  # em planta, alinhada a um eixo (~10°)
TOLERANCIA_LIGACAO_M = 0.30  # ponta a esta distância de outra barra está ligada a ela
VALOR_ABSURDO = 1e5  # kN ou kN·m: acima disso, quase certamente unidade errada
ANGULO_PILAR = 76.0  # graus com a horizontal (= 14° do prumo): pilar
ANGULO_HORIZONTAL = 2.0  # graus: horizontal
SINAL_MINIMO_KN = 0.02  # ΔN + ΔV do peso próprio abaixo disso: sem sinal para a inclinação
DIFERENCA_DE_INCLINACAO = 10.0  # graus entre o esqueleto e o PP: o corpo não é o da viga
#: De onde veio o eixo forte de cada barra (qual momento do Simulation é o do eixo forte).
EIXO_PELA_MACRO = "seção medida pela macro v6"
EIXO_PELO_PERFIL = "seção do perfil"
EIXO_PELO_MOMENTO = "momento que domina"
EIXOS_CERTOS = (EIXO_PELA_MACRO, EIXO_PELO_PERFIL)
FAMILIAS_I = ("w", "hp", "i")
FAMILIAS_U = ("u", "c")
FOLGA_DO_CATALOGO = 1.05  # a aresta mais longa passa a outra em 5 %, com o raio já descontado


class GeometriaInvalida(ValueError):
    """Arquivo do esqueleto que o programa não lê; a mensagem diz o que fazer."""


# ---------------------------------------------------------------------------------------------
# Esqueleto do modelo
# ---------------------------------------------------------------------------------------------
FORMA_BARRA, FORMA_CHAPA, FORMA_BLOCO = "BARRA", "CHAPA", "BLOCO"
FORMAS = (FORMA_BARRA, FORMA_CHAPA, FORMA_BLOCO)
VERSAO_ATUAL_DA_MACRO = "v6"
COORDENADA_ABSURDA_M = 10_000.0  # 10 km: o arquivo não está em mm
#: Linhas de cabeçalho da macro (antes da linha das colunas) → campo da geometria.
_METADADOS = {
    "macro": "versao_da_macro",
    "peca": "peca",
    "configuracao": "configuracao",
    "data": "gerado_em",
}
MACRO_ANTIGA = (
    "Arquivo de uma versão antiga da macro: baixe a macro nova (botão “Macro do SolidWorks”) e "
    "gere de novo — ela lê tubos redondos e chapas inclinadas e diz a forma de cada corpo."
)


@dataclass(frozen=True)
class CorpoDoModelo:
    nome: str  # o corpo no SolidWorks: o que vai entre parênteses no nome da viga do Simulation
    item: str  # o item da lista de corte (ex.: "C8x13.75<1>")
    descricao: str  # o perfil do item
    inicio: tuple[float, float, float]  # m, nos eixos do modelo
    fim: tuple[float, float, float]
    comprimento_m: float
    volume_m3: float | None = None
    forma: str = ""  # BARRA, CHAPA ou BLOCO (macro v4); vazio nas versões antigas
    secao_mm: tuple[float, float] | None = None  # as duas medidas da seção (maior, menor)
    #: Direção da medida maior da seção (a alma de um I ou de um U), unitária (macro v5).
    direcao_secao: tuple[float, float, float] | None = None
    #: Chapa: o contorno da face maior (m) e as aberturas dela (macro v5).
    contorno: tuple[tuple[float, float, float], ...] = ()
    aberturas: tuple[tuple[tuple[float, float, float], ...], ...] = ()
    #: A direção 1 da viga no Simulation (macro v6): paralela à aresta reta mais longa da seção,
    #: unitária, sem o sentido (o Simulation escolhe; o programa o tira dos resultados).
    direcao_1: tuple[float, float, float] | None = None
    #: Quanto essa aresta passa a mais longa das outras direções (mm): perto de zero é empate.
    folga_da_direcao_1_mm: float | None = None

    @property
    def vetor(self) -> tuple[float, float, float]:
        return (
            self.fim[0] - self.inicio[0],
            self.fim[1] - self.inicio[1],
            self.fim[2] - self.inicio[2],
        )

    @property
    def area_mm2(self) -> float | None:
        if not self.volume_m3 or self.comprimento_m <= 0:
            return None
        return self.volume_m3 / self.comprimento_m * 1e6

    @property
    def e_barra(self) -> bool:
        """Barra (ou forma não informada, nas versões antigas da macro)."""
        return self.forma in ("", FORMA_BARRA)


@dataclass(frozen=True)
class GeometriaDoModelo:
    corpos: tuple[CorpoDoModelo, ...] = ()
    arquivo: str = ""
    importado_em: str = ""
    peca: str = ""
    configuracao: str = ""
    gerado_em: str = ""
    versao_da_macro: str = ""
    avisos: tuple[str, ...] = ()

    def corpo(self, nome: str) -> CorpoDoModelo | None:
        return next((c for c in self.corpos if c.nome == nome), None)

    @property
    def origem(self) -> str:
        """De onde veio: "portico.SLDPRT, configuração Padrão, gerado em 2026-10-12 18:30"."""
        partes = [
            self.peca,
            f"configuração {self.configuracao}" if self.configuracao else "",
            f"gerado em {self.gerado_em}" if self.gerado_em else "",
        ]
        return ", ".join(p for p in partes if p)

    @property
    def formas(self) -> dict[str, int]:
        contagem = {forma: 0 for forma in FORMAS}
        for c in self.corpos:
            if c.forma in contagem:
                contagem[c.forma] += 1
        return contagem


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    ).lower()


def tipo_do_arquivo(conteudo: bytes) -> str | None:
    """Reconhece os arquivos da macro pelo cabeçalho: o esqueleto ou a lista de corte."""
    try:
        linhas = lm._celulas_do_arquivo(conteudo, "x.csv")
    except Exception:  # noqa: BLE001 — não reconhecer não é erro
        return None
    for linha in linhas[:20]:
        nomes = {_sem_acento(c).strip() for c in linha}
        if "corpo" in nomes and any(n.startswith("x1") for n in nomes):
            return TIPO_ESQUELETO
        if any(n.startswith("qtd") for n in nomes) and any(n.startswith("descri") for n in nomes):
            return TIPO_LISTA_DE_CORTE
    return None


def _em_metros(texto: str) -> float | None:
    valor, _ = lm.numero_da_celula(texto, "mm")
    return None if valor is None or not math.isfinite(valor) else valor / 1000.0


def ler_esqueleto(conteudo: bytes, nome_arquivo: str) -> GeometriaDoModelo:
    """O ``<peça>_esqueleto.csv`` da macro: um corpo por linha, coordenadas em mm.

    Só sai :class:`GeometriaInvalida` (um ``ValueError``) com uma mensagem para quem usa: um trecho
    inesperado do arquivo vira essa mensagem e uma ocorrência no diagnóstico (com
    ``MECANICA_TOOLKIT_ERROS=levantar``, a falha original sobe). O que dá para ler com ressalva
    (versão antiga da macro, linhas puladas, corpos repetidos, coordenadas fora de escala) vira
    aviso em :attr:`GeometriaDoModelo.avisos`.
    """
    try:
        return _ler_esqueleto(conteudo, nome_arquivo)
    except GeometriaInvalida:
        raise
    except Exception as erro:
        from core import diagnostico as dg

        if dg.levantar_erros():
            raise
        ocorrencia = dg.ocorrencia_de_falha("Esforços do modelo › leitura do esqueleto", erro)
        dg.gravar(ocorrencia)
        raise GeometriaInvalida(
            f"{nome_arquivo} tem um trecho fora do formato esperado e não foi lido "
            f"(ref. {ocorrencia.referencia}). Gere o arquivo de novo pela macro do SolidWorks."
        ) from erro


def _versao(texto: str) -> str:
    """A versão no fim da linha MACRO (… exportar_lista_de_corte v4 → v4); vazio sem ela."""
    for palavra in reversed(texto.split()):
        if len(palavra) > 1 and palavra[0] in "vV" and palavra[1:].replace(".", "").isdigit():
            return palavra.lower()
    return ""


def _ler_esqueleto(conteudo: bytes, nome_arquivo: str) -> GeometriaDoModelo:
    try:
        linhas = lm._celulas_do_arquivo(conteudo, nome_arquivo)
    except ValueError as erro:
        raise GeometriaInvalida(str(erro)) from erro
    if not linhas:
        raise GeometriaInvalida("O arquivo do esqueleto está vazio.")
    metadados: dict[str, str] = {}
    cabecalho_i = None
    for i, linha in enumerate(linhas[:20]):
        nomes_da_linha = [_sem_acento(c).strip() for c in linha]
        if "corpo" in nomes_da_linha and any(n.startswith("x1") for n in nomes_da_linha):
            cabecalho_i = i
            break
        if len(linha) >= 2 and nomes_da_linha[0] in _METADADOS:
            metadados[_METADADOS[nomes_da_linha[0]]] = str(linha[1]).strip()
    if cabecalho_i is None:
        raise GeometriaInvalida(
            "Não achei a linha das colunas do esqueleto (CORPO, X1…Z2, COMPRIMENTO): gere o "
            "arquivo de novo pela macro do SolidWorks."
        )
    cabecalho = [_sem_acento(c).strip() for c in linhas[cabecalho_i]]

    def opcional(prefixo: str) -> int | None:
        return next((j for j, nome in enumerate(cabecalho) if nome.startswith(prefixo)), None)

    def coluna(prefixo: str) -> int:
        j = opcional(prefixo)
        if j is None:
            raise GeometriaInvalida(
                f"O arquivo não tem a coluna {prefixo.upper()}: gere-o de novo pela macro do "
                "SolidWorks (versão com o esqueleto)."
            )
        return j

    c_corpo = coluna("corpo")
    c_coord = [coluna(p) for p in ("x1", "y1", "z1", "x2", "y2", "z2")]
    c_comp = coluna("compr")
    c_item, c_desc, c_forma = opcional("item"), opcional("descri"), opcional("forma")
    c_secao = (opcional("secao a"), opcional("secao b"))
    c_vol = opcional("volume")
    c_direcao = (opcional("direcao a x"), opcional("direcao a y"), opcional("direcao a z"))
    c_contorno, c_aberturas = opcional("contorno"), opcional("aberturas")
    c_direcao_1 = (opcional("direcao 1 x"), opcional("direcao 1 y"), opcional("direcao 1 z"))
    c_folga = opcional("direcao 1 folga")
    obrigatorias = max([c_corpo, c_comp, *c_coord])

    def celula(linha: list[str], j: int | None) -> str:
        return str(linha[j]).strip() if j is not None and j < len(linha) else ""

    corpos: list[CorpoDoModelo] = []
    vistos: set[str] = set()
    repetidos: list[str] = []
    pulados = fora_de_escala = sem_volume = 0
    for linha in linhas[cabecalho_i + 1 :]:
        if not any(str(c).strip() for c in linha):
            continue
        nome = celula(linha, c_corpo)
        if len(linha) <= obrigatorias or not nome:
            pulados += 1
            continue
        coords = [_em_metros(linha[j]) for j in c_coord]
        comprimento = _em_metros(linha[c_comp])
        if any(v is None for v in coords) or comprimento is None or comprimento <= 0:
            pulados += 1
            continue
        if nome in vistos:
            repetidos.append(nome)
            continue
        vistos.add(nome)
        x1, y1, z1, x2, y2, z2 = (v or 0.0 for v in coords)
        if max(abs(v or 0.0) for v in coords) > COORDENADA_ABSURDA_M:
            fora_de_escala += 1
        volume = None
        if c_vol is not None:
            cm3, _ = lm.numero_da_celula(celula(linha, c_vol))
            volume = cm3 / 1e6 if cm3 and math.isfinite(cm3) and cm3 > 0 else None
        if volume is None:
            sem_volume += 1
        forma = celula(linha, c_forma).upper()
        medidas = [m * 1e3 for j in c_secao if (m := _em_metros(celula(linha, j))) and m > 0]
        secao = (max(medidas), min(medidas)) if len(medidas) == 2 else None
        componentes = [lm.numero_da_celula(celula(linha, j), "")[0] for j in c_direcao]
        direcao = _direcao(componentes)
        contorno = _poligono(celula(linha, c_contorno))
        aberturas = tuple(
            poligono
            for trecho in celula(linha, c_aberturas).split("||")
            if len(poligono := _poligono(trecho)) >= 3
        )
        direcao_1 = _direcao([lm.numero_da_celula(celula(linha, j), "")[0] for j in c_direcao_1])
        folga = lm.numero_da_celula(celula(linha, c_folga), "")[0] if direcao_1 else None
        corpos.append(
            CorpoDoModelo(
                nome=nome,
                item=celula(linha, c_item),
                descricao=celula(linha, c_desc),
                inicio=(x1, y1, z1),
                fim=(x2, y2, z2),
                comprimento_m=comprimento,
                volume_m3=volume,
                forma=forma if forma in FORMAS else "",
                secao_mm=secao,
                direcao_secao=direcao,
                contorno=contorno if len(contorno) >= 3 else (),
                aberturas=aberturas,
                direcao_1=direcao_1,
                folga_da_direcao_1_mm=folga if folga is not None and math.isfinite(folga) else None,
            )
        )
    if not corpos:
        raise GeometriaInvalida("Nenhum corpo com coordenadas foi lido do arquivo do esqueleto.")
    versao = _versao(metadados.get("versao_da_macro", ""))
    avisos: list[str] = []
    if not versao or c_forma is None:
        avisos.append(MACRO_ANTIGA)
    elif versao == "v4":
        avisos.append(
            "Esqueleto da macro v4: lê tudo, mas sem a orientação das seções (nos pilares, "
            "Lx = Ly = o maior trecho, a favor da segurança) e sem o contorno das chapas (só as "
            "chapas retangulares recebem as cargas do piso). Rode a macro v5 (botão “Macro do "
            "SolidWorks”) para ter os dois."
        )
    elif versao == "v5":
        avisos.append(
            "Esqueleto da macro v5: lê tudo, mas sem a direção 1 das seções do Simulation (as "
            "setas das reações horizontais no Modelo em 3D saem só pelos resultados de um caso "
            "com vento nos pilares). Rode a macro v6 (botão “Macro do SolidWorks”) para ter a "
            "direção de cada seção."
        )
    elif versao != VERSAO_ATUAL_DA_MACRO:
        avisos.append(
            f"Gerado pela macro {versao}; o programa espera a {VERSAO_ATUAL_DA_MACRO}: baixe a "
            "macro nova (botão “Macro do SolidWorks”) e gere de novo."
        )
    if pulados:
        avisos.append(
            f"{pulados} linha(s) sem coordenadas ou sem comprimento foram puladas (corpo que a "
            "macro não conseguiu medir?)."
        )
    if repetidos:
        avisos.append(
            f"{len(repetidos)} corpo(s) repetido(s) no arquivo — ficou o primeiro: "
            f"{_lista(sorted(set(repetidos)))}."
        )
    if fora_de_escala:
        avisos.append(
            f"{fora_de_escala} corpo(s) com coordenadas acima de 10 km: o arquivo não está em mm? "
            "Gere de novo pela macro."
        )
    grupos: dict[str, list[float]] = {}
    for c in corpos:
        # Só peças longas (≥ 10 vezes a seção): o corte das pontas pouco muda o volume.
        if c.e_barra and c.area_mm2 and c.secao_mm and c.comprimento_m * 1e3 >= 10 * c.secao_mm[0]:
            grupos.setdefault(c.descricao or c.item.split("<")[0], []).append(c.area_mm2)
    diferentes = [
        f"{nome} ({_n(min(a) / 100, 1)} a {_n(max(a) / 100, 1)} cm²)"
        for nome, a in grupos.items()
        if len(a) > 1 and max(a) > 1.3 * min(a)
    ]
    if diferentes:
        avisos.append(
            f"Mesmo perfil com volumes por metro diferentes: {_lista(diferentes, 4)} — algum corpo "
            "foi recortado ou tem outra seção. O Simulation calcula com a seção do perfil e a "
            "lista de material pesa pelo volume: confira esses corpos no SolidWorks."
        )
    por_item: dict[str, dict[str, list[str]]] = {}
    perfis_lidos = _perfis_dos_corpos(corpos)
    for c in corpos:
        if c.e_barra and c.area_mm2 and c.descricao:
            perfil, _ = perfis_lidos.get(c.nome, ("", ""))
            if perfil:
                por_item.setdefault(c.descricao, {}).setdefault(perfil, []).append(c.nome)
    misturados = []
    for descricao, perfis in por_item.items():
        if len(perfis) > 1:
            maioria = max(perfis, key=lambda k: len(perfis[k]))
            outros = "; ".join(
                f"{len(nomes)} com o {perfil} ({_lista(sorted(nomes), 3)})"
                for perfil, nomes in perfis.items()
                if perfil != maioria
            )
            misturados.append(
                f"“{descricao}”: {len(perfis[maioria])} corpo(s) com a seção do {maioria}, {outros}"
            )
    if misturados:
        avisos.append(
            f"O mesmo item da lista de corte com perfis diferentes — {_lista(misturados, 3)}. "
            "Se for engano (um membro que ficou com o perfil antigo), troque no SolidWorks; o "
            "Simulation calcula cada um com a seção dele."
        )
    pelo_nome: dict[str, list[CorpoDoModelo]] = {}
    for c in corpos:
        if c.e_barra and c.area_mm2:
            pelo_nome.setdefault(_prefixo_e_indice(c.nome)[0], []).append(c)
    nomes_errados = []
    for prefixo, grupo in pelo_nome.items():
        do_nome = em.perfil_do_nome(prefixo)
        if not do_nome:
            continue
        do_catalogo = lm._secao_do_catalogo(do_nome)
        area = max(c.area_mm2 or 0.0 for c in grupo)
        if do_catalogo is None or abs(area - do_catalogo[0]) <= 0.05 * do_catalogo[0]:
            continue
        desenhado = next(
            (
                conhecido.nome
                for texto in (grupo[0].descricao, grupo[0].item.split("<")[0])
                if texto and (conhecido := lm.perfil_conhecido(texto)) is not None
            ),
            "",
        )
        nomes_errados.append(
            f"“{prefixo}” ({len(grupo)} corpo(s)): o nome diz {do_nome} ({_n(do_catalogo[0] / 100, 1)} "
            f"cm²), a seção desenhada tem {_n(area / 100, 1)} cm²"
            + (f" ({desenhado})" if desenhado else "")
        )
    if nomes_errados:
        avisos.append(
            f"Nome do membro diferente da seção desenhada: {_lista(nomes_errados, 3)}. O Simulation "
            "calcula com a seção desenhada: troque o perfil no SolidWorks para o do nome (ou corrija "
            "o nome), para o modelo, a lista de material e a verificação serem o mesmo perfil."
        )
    if sem_volume and sem_volume < len(corpos):
        avisos.append(
            f"{sem_volume} corpo(s) sem volume: o peso próprio não é conferido pelo esqueleto."
        )
    return GeometriaDoModelo(
        corpos=tuple(corpos),
        arquivo=nome_arquivo,
        importado_em=datetime.now().isoformat(timespec="seconds"),
        peca=metadados.get("peca", ""),
        configuracao=metadados.get("configuracao", ""),
        gerado_em=metadados.get("gerado_em", ""),
        versao_da_macro=versao,
        avisos=tuple(avisos),
    )


def para_dicionario(g: GeometriaDoModelo) -> dict[str, Any]:
    return {
        "arquivo": g.arquivo,
        "importado_em": g.importado_em,
        "peca": g.peca,
        "configuracao": g.configuracao,
        "gerado_em": g.gerado_em,
        "versao_da_macro": g.versao_da_macro,
        "avisos": list(g.avisos),
        "corpos": [
            [
                c.nome,
                c.item,
                c.descricao,
                *(round(v, 4) for v in (*c.inicio, *c.fim)),
                round(c.comprimento_m, 4),
                c.volume_m3,
                c.forma,
                *(c.secao_mm or (None, None)),
                list(c.direcao_secao) if c.direcao_secao else None,
                [[round(v, 4) for v in ponto] for ponto in c.contorno],
                [[[round(v, 4) for v in ponto] for ponto in abertura] for abertura in c.aberturas],
                list(c.direcao_1) if c.direcao_1 else None,
                c.folga_da_direcao_1_mm,
            ]
            for c in g.corpos
        ],
    }


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _direcao(componentes: Sequence[float | None]) -> tuple[float, float, float] | None:
    """Vetor unitário a partir de três números; ``None`` se faltar algum ou for nulo."""
    if len(componentes) != 3 or any(c is None or not math.isfinite(c) for c in componentes):
        return None
    x, y, z = (float(c or 0.0) for c in componentes)
    norma = math.sqrt(x * x + y * y + z * z)
    return (x / norma, y / norma, z / norma) if norma > 1e-9 else None


def _poligono(texto: str) -> tuple[tuple[float, float, float], ...]:
    """ "x y z | x y z | …" (mm, da macro) → pontos em m; ponto fora do formato é pulado."""
    pontos = []
    for trecho in texto.split("|"):
        partes = trecho.split()
        if len(partes) != 3:
            continue
        valores = [_em_metros(p) for p in partes]
        if all(v is not None for v in valores):
            pontos.append((valores[0] or 0.0, valores[1] or 0.0, valores[2] or 0.0))
    return tuple(pontos)


def _pontos_gravados(valor: Any) -> tuple[tuple[float, float, float], ...]:
    if not isinstance(valor, list | tuple):
        return ()
    pontos = []
    for ponto in valor:
        if isinstance(ponto, list | tuple) and len(ponto) == 3:
            numeros = [_numero(v) for v in ponto]
            if all(n is not None for n in numeros):
                pontos.append((numeros[0] or 0.0, numeros[1] or 0.0, numeros[2] or 0.0))
    return tuple(pontos)


def _texto(valor: Any) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def de_dicionario(dados: Mapping[str, Any] | None) -> GeometriaDoModelo:
    """Lê o esqueleto gravado no projeto; linhas fora do formato são puladas."""
    if not isinstance(dados, Mapping):
        return GeometriaDoModelo()
    corpos = []
    linhas = dados.get("corpos")
    for linha in linhas if isinstance(linhas, list | tuple) else ():
        if not isinstance(linha, list | tuple) or len(linha) < 10:
            continue
        numeros = [_numero(v) for v in linha[3:10]]
        if any(n is None for n in numeros) or not numeros[6] or (numeros[6] or 0) <= 0:
            continue
        x1, y1, z1, x2, y2, z2, comprimento = (n or 0.0 for n in numeros)
        volume = _numero(linha[10]) if len(linha) > 10 else None
        forma = _texto(linha[11]).upper() if len(linha) > 11 else ""
        medidas = [m for v in linha[12:14] if (m := _numero(v)) and m > 0]
        secao = (max(medidas), min(medidas)) if len(medidas) == 2 else None
        gravada = linha[14] if len(linha) > 14 else None
        direcao = (
            _direcao([_numero(v) for v in gravada])
            if isinstance(gravada, list | tuple) and len(gravada) == 3
            else None
        )
        contorno = _pontos_gravados(linha[15]) if len(linha) > 15 else ()
        aberturas = (
            tuple(a for item in linha[16] if len(a := _pontos_gravados(item)) >= 3)
            if len(linha) > 16 and isinstance(linha[16], list | tuple)
            else ()
        )
        gravada_1 = linha[17] if len(linha) > 17 else None
        direcao_1 = (
            _direcao([_numero(v) for v in gravada_1])
            if isinstance(gravada_1, list | tuple) and len(gravada_1) == 3
            else None
        )
        folga = _numero(linha[18]) if len(linha) > 18 and direcao_1 else None
        corpos.append(
            CorpoDoModelo(
                str(linha[0]),
                str(linha[1]),
                str(linha[2]),
                (x1, y1, z1),
                (x2, y2, z2),
                comprimento,
                volume if volume and volume > 0 else None,
                forma if forma in FORMAS else "",
                secao,
                direcao,
                contorno if len(contorno) >= 3 else (),
                aberturas,
                direcao_1,
                folga,
            )
        )
    avisos = dados.get("avisos")
    return GeometriaDoModelo(
        corpos=tuple(corpos),
        arquivo=_texto(dados.get("arquivo")),
        importado_em=_texto(dados.get("importado_em")),
        peca=_texto(dados.get("peca")),
        configuracao=_texto(dados.get("configuracao")),
        gerado_em=_texto(dados.get("gerado_em")),
        versao_da_macro=_texto(dados.get("versao_da_macro")),
        avisos=tuple(a for a in avisos if isinstance(a, str)) if isinstance(avisos, list) else (),
    )


def geometria_do_projeto(projeto: Mapping[str, Any] | None) -> GeometriaDoModelo:
    if not isinstance(projeto, Mapping):
        return GeometriaDoModelo()
    return de_dicionario(projeto.get("geometria_do_modelo"))


def nome_do_corpo(nome_da_viga: str) -> str:
    """'Viga-2(Canal c C8X13.75(1)[2])' → 'Canal c C8X13.75(1)[2]' (o corpo no SolidWorks)."""
    inicio, fim = nome_da_viga.find("("), nome_da_viga.rfind(")")
    return nome_da_viga[inicio + 1 : fim].strip() if 0 <= inicio < fim else nome_da_viga.strip()


def _chave(nome: str) -> str:
    return "".join(_sem_acento(nome).split())


def corpo_da_viga(g: GeometriaDoModelo, nome_da_viga: str) -> CorpoDoModelo | None:
    alvo = nome_do_corpo(nome_da_viga)
    exato = g.corpo(alvo)
    if exato is not None:
        return exato
    chave = _chave(alvo)
    return next((c for c in g.corpos if _chave(c.nome) == chave), None)


def _prefixo_e_indice(nome_do_corpo: str) -> tuple[str, str]:
    """'U 8"x17,1 - Plataforma[12]' → ('U 8"x17,1 - Plataforma', '12'); sem índice, (nome, '')."""
    m = re.match(r"^(.*?)\[(\d+)\]\s*$", nome_do_corpo.strip())
    return (m.group(1).strip(), m.group(2)) if m else (nome_do_corpo.strip(), "")


@dataclass(frozen=True)
class Correspondencia:
    """Que corpo do esqueleto é cada viga do Simulation, e quais foram casadas por renomeação."""

    corpos: Mapping[str, CorpoDoModelo]
    renomeados: Mapping[str, str]  # prefixo antigo (no Simulation) → prefixo novo (no esqueleto)

    @property
    def pela_renomeacao(self) -> int:
        return sum(
            1
            for viga in self.corpos
            if _prefixo_e_indice(nome_do_corpo(viga))[0] in self.renomeados
        )


def correspondencia(
    g: GeometriaDoModelo,
    nomes_das_vigas: Iterable[str],
    dados: em.EsforcosDoModelo | None = None,
) -> Correspondencia:
    """Cada viga do Simulation no seu corpo do esqueleto.

    Primeiro pelo nome. As que sobram são de corpos renomeados depois do estudo (o Simulation
    guarda o nome de quando a malha foi feita): o membro estrutural renomeado mantém a numeração
    ``[n]`` dos corpos, então cada grupo antigo ("Canal c C8X13.75(1)") vai para o grupo novo
    ("U 8"x17,1 - Plataforma") que tem os mesmos números, o perfil do item da lista de corte no
    nome antigo e — com o caso PP — a mesma inclinação que o peso próprio mostra. Um grupo novo
    serve a um só grupo antigo; na dúvida (pontuação ≤ 0), fica sem corpo.
    """
    nomes = list(nomes_das_vigas)
    mapa: dict[str, CorpoDoModelo] = {}
    for viga in nomes:
        corpo = corpo_da_viga(g, viga) if g.corpos else None
        if corpo is not None:
            mapa[viga] = corpo
    usados = {c.nome for c in mapa.values()}
    antigos: dict[str, dict[str, str]] = {}
    for viga in nomes:
        if viga not in mapa:
            prefixo, indice = _prefixo_e_indice(nome_do_corpo(viga))
            if indice:
                antigos.setdefault(prefixo, {})[indice] = viga
    novos: dict[str, dict[str, CorpoDoModelo]] = {}
    for corpo in g.corpos:
        if corpo.nome not in usados and corpo.forma != FORMA_CHAPA:
            prefixo, indice = _prefixo_e_indice(corpo.nome)
            if indice:
                novos.setdefault(prefixo, {})[indice] = corpo
    if not antigos or not novos:
        return Correspondencia(mapa, {})
    eixo = dados.eixo_vertical if dados is not None else "Y"
    angulos = (
        {
            viga: inclinacao_pelo_peso(dados, viga)
            for grupo in antigos.values()
            for viga in grupo.values()
        }
        if dados is not None
        else {}
    )

    def pontos(antigo: str, novo: str) -> float:
        comuns = set(antigos[antigo]) & set(novos[novo])
        if not comuns:
            return -math.inf
        total = 0.0
        for indice in comuns:
            viga, corpo = antigos[antigo][indice], novos[novo][indice]
            total += 1.0
            perfil = _chave(corpo.descricao or corpo.item.split("<")[0])
            if perfil and perfil in _chave(antigo):
                total += 1.0
            angulo = angulos.get(viga)
            if angulo is not None:
                diferenca = abs(angulo - _angulo_do_corpo(corpo, eixo))
                total += 2.0 if diferenca <= DIFERENCA_DE_INCLINACAO else -3.0
        return total - 0.5 * len(set(antigos[antigo]) ^ set(novos[novo]))

    pares = sorted(
        ((pontos(a, n), a, n) for a in antigos for n in novos), key=lambda x: x[0], reverse=True
    )
    renomeados: dict[str, str] = {}
    for valor, antigo, novo in pares:
        if valor <= 0 or antigo in renomeados or novo in renomeados.values():
            continue
        renomeados[antigo] = novo
        for indice in set(antigos[antigo]) & set(novos[novo]):
            mapa[antigos[antigo][indice]] = novos[novo][indice]
    return Correspondencia(mapa, renomeados)


def _indice_vertical(eixo_vertical: str) -> int:
    return 1 if eixo_vertical == "Y" else 2


def tipo_pela_geometria(corpo: CorpoDoModelo, eixo_vertical: str) -> tuple[str, str]:
    vetor = corpo.vetor
    comprimento = math.hypot(*vetor)
    if comprimento <= 0:
        return "—", "comprimento nulo no esqueleto"
    iv = _indice_vertical(eixo_vertical)
    vertical = abs(vetor[iv]) / comprimento
    if vertical >= VERTICAL_MINIMO:
        return TIPO_PILAR, "vertical no modelo"
    if vertical <= HORIZONTAL_MAXIMO:
        horizontais = [vetor[i] for i in range(3) if i != iv]
        if max(abs(h) for h in horizontais) / math.hypot(*horizontais) >= ALINHADO_MINIMO:
            return TIPO_VIGA, "horizontal no modelo"
        return TIPO_CONTRAVENTAMENTO, "horizontal e diagonal em planta (contraventamento do piso)"
    angulo = math.degrees(math.asin(vertical))
    return TIPO_CONTRAVENTAMENTO, f"inclinada {angulo:.0f}° com a horizontal"


def _angulo_do_corpo(corpo: CorpoDoModelo, eixo_vertical: str) -> float:
    """Graus com a horizontal."""
    vetor = corpo.vetor
    comprimento = math.hypot(*vetor)
    if comprimento <= 0:
        return 0.0
    return math.degrees(
        math.asin(min(1.0, abs(vetor[_indice_vertical(eixo_vertical)]) / comprimento))
    )


def _distancia_ponto_segmento(p: Sequence[float], a: Sequence[float], b: Sequence[float]) -> float:
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    comprimento2 = sum(v * v for v in ab)
    t = (
        0.0
        if comprimento2 == 0
        else max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / comprimento2))
    )
    return math.dist(p, [a[i] + t * ab[i] for i in range(3)])


def pontas_soltas_pela_geometria(
    g: GeometriaDoModelo, eixo_vertical: str, nomes: Iterable[str] | None = None
) -> dict[str, list[str]]:
    """Corpo → pontas ("início", "fim") que não tocam outra barra nem estão no apoio (o mais baixo)."""
    if not g.corpos:
        return {}
    iv = _indice_vertical(eixo_vertical)
    piso = min(min(c.inicio[iv], c.fim[iv]) for c in g.corpos)
    escolhidos = set(nomes) if nomes is not None else None
    soltas: dict[str, list[str]] = {}
    for corpo in g.corpos:
        if not corpo.e_barra or (escolhidos is not None and corpo.nome not in escolhidos):
            continue  # chapa e bloco não têm "ponta solta"
        for rotulo, ponta in (("início", corpo.inicio), ("fim", corpo.fim)):
            if abs(ponta[iv] - piso) <= TOLERANCIA_LIGACAO_M:
                continue  # apoio
            ligada = any(
                _distancia_ponto_segmento(ponta, outro.inicio, outro.fim) <= TOLERANCIA_LIGACAO_M
                for outro in g.corpos
                if outro is not corpo
            )
            if not ligada:
                soltas.setdefault(corpo.nome, []).append(rotulo)
    return soltas


# ---------------------------------------------------------------------------------------------
# Barra a barra
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class LeituraDaBarra:
    barra: str
    corpo: CorpoDoModelo | None
    tipo_sugerido: str
    motivo_do_tipo: str
    perfil_sugerido: str
    origem_do_perfil: str
    comprimento_m: float | None
    elementos: int
    pontas: tuple[str, str]
    eixo_forte: str
    avisos: tuple[str, ...] = ()
    #: Comprimentos de flambagem sugeridos pelos travamentos do esqueleto (:mod:`core.travamentos`).
    lx_m: float | None = None
    ly_m: float | None = None
    lb_m: float | None = None
    motivo_dos_comprimentos: str = ""
    #: De onde veio o eixo forte (EIXO_PELA_MACRO, EIXO_PELO_PERFIL ou EIXO_PELO_MOMENTO).
    origem_do_eixo: str = EIXO_PELO_MOMENTO

    @property
    def tem_ponta_solta(self) -> bool:
        return PONTA_SOLTA in self.pontas


def _pontos(dados: em.EsforcosDoModelo, barra: str) -> list[em.PontoDeEsforco]:
    return [p for caso in dados.casos.values() for p in caso.membros.get(barra, ())]


def classificar_pontas(dados: em.EsforcosDoModelo, barra: str) -> tuple[str, str]:
    """Cada ponta (a primeira e a última da lista do SolidWorks), olhando todos os casos."""
    todos = _pontos(dados, barra)
    escala_f = max((max(abs(p.n), abs(p.v1), abs(p.v2)) for p in todos), default=0.0)
    escala_m = max((max(abs(p.m1), abs(p.m2), abs(p.t)) for p in todos), default=0.0)
    if escala_f < 1e-6 and escala_m < 1e-6:
        return PONTA_SEM_ESFORCO, PONTA_SEM_ESFORCO
    limite_f = max(0.01, 1e-3 * escala_f)
    limite_m_solta = max(0.01, 1e-3 * escala_m)
    limite_m_articulada = max(0.01, 0.02 * escala_m)
    resultado = []
    for indice in (0, -1):
        forcas = momentos = 0.0
        for caso in dados.casos.values():
            pontos = caso.membros.get(barra, ())
            if not pontos:
                continue
            p = pontos[indice]
            forcas = max(forcas, abs(p.n), abs(p.v1), abs(p.v2))
            momentos = max(momentos, abs(p.m1), abs(p.m2), abs(p.t))
        if forcas <= limite_f and momentos <= limite_m_solta:
            resultado.append(PONTA_SOLTA)
        elif momentos <= limite_m_articulada:
            resultado.append(PONTA_ARTICULADA)
        else:
            resultado.append(PONTA_RIGIDA)
    return resultado[0], resultado[1]


def _casos_verticais(
    dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas | None
) -> list[em.CasoImportado]:
    """Os casos só com carga vertical (o PP sempre; os outros, pelo plano de cargas)."""
    verticais = []
    for caso in dados.casos.values():
        acao = plano.acao(caso.codigo) if plano is not None else None
        if caso.codigo == "PP" or (acao is not None and acao.cargas and em._so_vertical(acao)):
            verticais.append(caso)
    return verticais


def variacao_no_pp(dados: em.EsforcosDoModelo, barra: str) -> tuple[float, float] | None:
    """O que o peso próprio faz *dentro* de cada elemento da barra no caso PP: (ΔN, ΔV) somados.

    Dentro de um elemento só uma carga distribuída ao longo da barra muda a normal e a cortante
    (as barras que chegam nos nós mudam os esforços *entre* elementos, não dentro deles). No PP
    essa carga é o peso próprio: a parte ao longo do eixo muda N, a parte transversal muda V.
    Somados na barra, ``hypot(ΔN, ΔV)`` é a carga distribuída total e ``atan2(ΔN, ΔV)`` a
    inclinação da barra com a horizontal. ``None`` sem caso PP ou sem a barra nele.
    """
    pp = dados.casos.get("PP")
    pontos = pp.membros.get(barra) if pp is not None else None
    if not pontos:
        return None
    por_elemento: dict[str, dict[str, em.PontoDeEsforco]] = {}
    for p in pontos:
        por_elemento.setdefault(p.elemento, {})[p.fim] = p
    delta_n = delta_v = 0.0
    for pontas in por_elemento.values():
        if "1" in pontas and "2" in pontas:
            a, b = pontas["1"], pontas["2"]
            delta_n += abs(b.n - a.n)
            delta_v += math.hypot(b.v1 - a.v1, b.v2 - a.v2)
    return delta_n, delta_v


def inclinacao_pelo_peso(dados: em.EsforcosDoModelo, barra: str) -> float | None:
    """A inclinação da barra com a horizontal (graus) pelo peso próprio no PP; ``None`` sem sinal."""
    variacao = variacao_no_pp(dados, barra)
    if variacao is None or sum(variacao) < SINAL_MINIMO_KN:
        return None
    return math.degrees(math.atan2(*variacao))


def _flexao_domina(dados: em.EsforcosDoModelo, barra: str) -> bool:
    """Cortante acima de 10 % da normal (em todos os casos): a barra trabalha fletida."""
    todos = _pontos(dados, barra)
    normal = max((abs(p.n) for p in todos), default=0.0)
    cortante = max((math.hypot(p.v1, p.v2) for p in todos), default=0.0)
    return cortante > max(0.05, 0.10 * normal)


def _tipo_inclinada(
    dados: em.EsforcosDoModelo, barra: str, angulo: float, fonte: str
) -> tuple[str, str]:
    if _flexao_domina(dados, barra):
        return (
            TIPO_VIGA,
            f"inclinada {angulo:.0f}° {fonte} e fletida (banzo de escada, viga inclinada)",
        )
    return TIPO_CONTRAVENTAMENTO, f"inclinada {angulo:.0f}° {fonte}, força normal dominante"


def tipo_pelos_esforcos(
    dados: em.EsforcosDoModelo, barra: str, plano: pc.PlanoDeCargas | None = None
) -> tuple[str, str]:
    """Pelo comportamento, quando não há o esqueleto.

    Primeiro pelo peso próprio (:func:`inclinacao_pelo_peso`): vertical é pilar, horizontal é viga
    (ou contraventamento do piso, se só trabalha à força normal), inclinada é contraventamento ou
    viga inclinada, conforme a flexão. Sem esse sinal (PP sem peso próprio nas barras): só força
    normal → contraventamento; sob carga só vertical (PP, SC…), o pilar fica comprimido com N
    muito maior que V e a viga, o contrário.
    """
    todos = _pontos(dados, barra)
    normal = max((abs(p.n) for p in todos), default=0.0)
    cortante = max((math.hypot(p.v1, p.v2) for p in todos), default=0.0)
    momento = max((max(abs(p.m1), abs(p.m2)) for p in todos), default=0.0)
    if normal < 0.01 and momento < 0.01:
        return "—", ""
    so_normal = momento <= 0.02 * normal and cortante <= 0.05 * normal
    angulo = inclinacao_pelo_peso(dados, barra)
    if angulo is not None:
        if angulo >= ANGULO_PILAR:
            return TIPO_PILAR, (
                "vertical: no PP a normal varia dentro dos elementos e a cortante não (peso "
                "próprio ao longo do eixo)"
            )
        if angulo <= ANGULO_HORIZONTAL:
            if so_normal:
                return TIPO_CONTRAVENTAMENTO, "horizontal e só com força normal"
            return TIPO_VIGA, "horizontal: no PP a normal não varia dentro dos elementos"
        return _tipo_inclinada(dados, barra, angulo, "(pelo peso próprio)")
    if so_normal:
        return TIPO_CONTRAVENTAMENTO, "trabalha só à força normal (barra articulada)"
    verticais = [p for caso in _casos_verticais(dados, plano) for p in caso.membros.get(barra, ())]
    if verticais:
        n_vertical = max(abs(p.n) for p in verticais)
        v_vertical = max(math.hypot(p.v1, p.v2) for p in verticais)
        comprimida = min(p.n for p in verticais) < 0
        if comprimida and n_vertical > 2 * v_vertical:
            return TIPO_PILAR, "sob carga vertical, comprimida com N muito maior que V"
        if v_vertical > 2 * n_vertical:
            return TIPO_VIGA, "sob carga vertical, fletida com pouca força normal"
    return "—", ""


def _elementos(dados: em.EsforcosDoModelo, barra: str) -> int:
    for caso in dados.casos.values():
        pontos = caso.membros.get(barra)
        if pontos:
            return len({p.elemento for p in pontos})
    return 0


def _secao_no_modelo(corpo: CorpoDoModelo) -> str:
    if corpo.secao_mm is None:
        return ""
    return f"; seção de {corpo.secao_mm[0]:.0f} × {corpo.secao_mm[1]:.0f} mm no modelo"


def _chave_do_perfil(corpo: CorpoDoModelo) -> str:
    return corpo.descricao or corpo.item.split("<")[0]


def areas_por_perfil(g: GeometriaDoModelo) -> dict[str, float]:
    """A maior área de seção (volume ÷ comprimento) entre as barras de mesmo perfil.

    Corte inclinado na ponta só tira volume: a peça mais reta do grupo dá a área verdadeira — o
    mesmo critério da Lista de material. Sem isso, um U 8" em meia-esquadria "vira" um U 6".
    """
    areas: dict[str, float] = {}
    for c in g.corpos:
        if c.e_barra and c.area_mm2:
            chave = _chave_do_perfil(c)
            areas[chave] = max(areas.get(chave, 0.0), c.area_mm2)
    return areas


def _dimensoes(nome: str) -> tuple[float, float] | None:
    """(altura, largura) do perfil do catálogo ou da cantoneira, em mm."""
    perfis = sc.listar_perfis()
    if nome in perfis:
        return perfis[nome].altura_mm, perfis[nome].largura_mm
    if nome in ct.CATALOGO_CANTONEIRAS:
        aba = ct.CATALOGO_CANTONEIRAS[nome].b_mm
        return aba, aba
    return None


def cabe_na_secao(nome: str, secao_mm: tuple[float, float] | None) -> bool:
    """O perfil pode ser o corpo medido? A maior medida da seção do corpo (nas direções do próprio
    corpo) não passa da diagonal do perfil, nem o perfil é mais estreito que ela."""
    dimensoes = _dimensoes(nome)
    if secao_mm is None or dimensoes is None:
        return True
    maior = secao_mm[0]
    return math.hypot(*dimensoes) >= 0.95 * maior and min(dimensoes) <= 1.05 * maior


def _familia(nome: str) -> dict[str, float]:
    """Os perfis da mesma família do catálogo (nome → área, mm²)."""
    secao = lm._secao_do_catalogo(nome)
    if secao is None:
        return {}
    familia = secao[1]
    if familia == "Cantoneira":
        return {n: c.area_mm2 for n, c in ct.CATALOGO_CANTONEIRAS.items()}
    return {n: p.area_mm2 for n, p in sc.listar_perfis().items() if p.familia == familia}


def _cabe_na_caixa(nome: str, secao_mm: tuple[float, float] | None) -> bool:
    """A seção do perfil cabe na caixa medida? Nenhuma peça, cortada ou não, tem a caixa menor que a
    própria seção (I, U, W e H: a caixa nas direções da seção é altura × aba). A cantoneira é
    medida nos eixos principais (a caixa não é aba × aba): não entra nesta conferência."""
    dimensoes = _dimensoes(nome)
    if secao_mm is None or dimensoes is None or nome in ct.CATALOGO_CANTONEIRAS:
        return True
    return max(dimensoes) <= secao_mm[0] * 1.025 and min(dimensoes) <= secao_mm[1] * 1.025


def _caixa_bate(nome: str, secao_mm: tuple[float, float] | None) -> bool:
    """A seção medida (maior, menor) é a altura e a largura do perfil (± 2,5 %)?"""
    dimensoes = _dimensoes(nome)
    if secao_mm is None or dimensoes is None:
        return False
    maior, menor = max(dimensoes), min(dimensoes)
    return abs(secao_mm[0] - maior) <= 0.025 * maior and abs(secao_mm[1] - menor) <= 0.025 * menor


@dataclass(frozen=True)
class _Opcoes:
    base: str  # o perfil que o item da lista de corte indica
    texto_base: str
    pelo_nome: str  # o que o nome do corpo indica (U 8"x17,1)
    area: float | None
    opcoes: Mapping[str, float]  # perfis da família → área
    candidatos: tuple[str, ...]  # os que a área e as medidas permitem
    exatos: tuple[str, ...]  # peça reta: a caixa e a área batem com o perfil


def _opcoes(corpo: CorpoDoModelo) -> _Opcoes:
    base = texto_base = ""
    for texto in (corpo.descricao, corpo.item.split("<")[0]):
        conhecido = lm.perfil_conhecido(texto) if texto else None
        if conhecido is not None:
            base, texto_base = conhecido.nome, texto
            break
    pelo_nome = em.perfil_do_nome(_prefixo_e_indice(corpo.nome)[0]) or ""
    area = corpo.area_mm2
    if not base or not area:
        return _Opcoes(base, texto_base, pelo_nome, area, {}, (), ())
    opcoes = _familia(base)
    altura_m = (corpo.secao_mm[0] if corpo.secao_mm else 300.0) / 1e3
    perda = min(0.6, 2 * altura_m / corpo.comprimento_m) if corpo.comprimento_m > 0 else 0.6
    # A caixa só acompanha a seção numa barra comprida (no toco muito cortado, os eixos giram).
    caixa_confiavel = corpo.forma != FORMA_BLOCO
    candidatos = tuple(
        n
        for n, a in opcoes.items()
        if a * (1 - perda) <= area <= a * 1.03
        and cabe_na_secao(n, corpo.secao_mm)
        and (not caixa_confiavel or _cabe_na_caixa(n, corpo.secao_mm))
    )
    # Peça reta tem a caixa exata da seção e a área do perfil (a caixa sozinha engana: um 17,1
    # cortado a 45° pode ter a aba de 59,5 mm do 20,5).
    exatos = tuple(
        n
        for n in candidatos
        if _caixa_bate(n, corpo.secao_mm) and abs(area - opcoes[n]) <= 0.03 * opcoes[n]
    )
    return _Opcoes(base, texto_base, pelo_nome, area, opcoes, candidatos, exatos)


def perfil_do_corpo(corpo: CorpoDoModelo, do_membro: str = "") -> tuple[str, str]:
    """O perfil do catálogo que o corpo é, e de onde saiu.

    A área da seção (volume ÷ comprimento) só pode ser menor que a do perfil — o corte nas pontas
    tira volume, no máximo duas alturas de seção sobre o comprimento (até 60 %) —, o perfil tem de
    caber na seção medida e, numa barra comprida, a caixa não pode ser menor que a seção. Entre os
    perfis da família que passam, nesta ordem: o da peça reta (caixa e área exatas), o das peças
    retas do mesmo membro (``do_membro``, :func:`perfis_do_esqueleto`), o que o nome do corpo
    indica (U 8"x17,1), o do item da lista de corte; sem nenhum, o mais leve que cobre a área.
    """
    o = _opcoes(corpo)
    if not o.base:
        return (o.pelo_nome, "nome do corpo no SolidWorks") if o.pelo_nome else ("", "")
    origem = f"lista de corte ({o.texto_base})"
    if not o.area:
        return o.base, origem + _secao_no_modelo(corpo)
    area = o.area
    cm2 = f"{_n(area / 100, 1)} cm²"
    if not o.candidatos:
        return o.base, (
            f"{origem}; a seção do modelo ({cm2}) não confere com a do {o.base} nem com outro "
            "perfil da família" + _secao_no_modelo(corpo)
        )
    if o.exatos:
        escolhido = next(
            (n for n in (o.pelo_nome, o.base) if n in o.exatos),
            min(o.exatos, key=lambda n: abs(o.opcoes[n] - area)),
        )
        por = "peça reta: a caixa e a área da seção são as do perfil"
    elif do_membro in o.candidatos:
        escolhido, por = do_membro, "as peças retas do mesmo membro"
    elif o.pelo_nome in o.candidatos:
        escolhido, por = o.pelo_nome, "o nome do corpo"
    elif o.base in o.candidatos:
        escolhido, por = o.base, ""
    else:
        escolhido = min(o.candidatos, key=lambda n: o.opcoes[n])
        por = "a área da seção"
    if escolhido == o.base and por in ("", "peça reta: a caixa e a área da seção são as do perfil"):
        return o.base, origem + _secao_no_modelo(corpo)
    return escolhido, f"{origem}; {escolhido} por {por} ({cm2})" + _secao_no_modelo(corpo)


def perfis_do_esqueleto(g: GeometriaDoModelo) -> dict[str, tuple[str, str]]:
    """O perfil de cada corpo, com a evidência do membro: as peças retas de um membro (o mesmo nome
    antes do [n]) dizem o perfil dele, e as peças cortadas do mesmo membro seguem, se couberem."""
    return _perfis_dos_corpos(g.corpos)


def _perfis_dos_corpos(corpos: Sequence[CorpoDoModelo]) -> dict[str, tuple[str, str]]:
    votos: dict[str, dict[str, int]] = {}
    for corpo in corpos:
        if corpo.forma == FORMA_CHAPA:
            continue
        o = _opcoes(corpo)
        if len(o.exatos) == 1:
            membro = _prefixo_e_indice(corpo.nome)[0]
            votos.setdefault(membro, {})
            votos[membro][o.exatos[0]] = votos[membro].get(o.exatos[0], 0) + 1
    do_membro = {m: max(v, key=lambda k: v[k]) for m, v in votos.items()}
    return {
        corpo.nome: perfil_do_corpo(corpo, do_membro.get(_prefixo_e_indice(corpo.nome)[0], ""))
        for corpo in corpos
        if corpo.forma != FORMA_CHAPA
    }


def _perfil(
    barra: str, corpo: CorpoDoModelo | None, perfis: Mapping[str, tuple[str, str]] | None = None
) -> tuple[str, str]:
    if corpo is not None:
        perfil, origem = (perfis or {}).get(corpo.nome) or perfil_do_corpo(corpo)
        if perfil:
            return perfil, origem
    pelo_nome = em.perfil_do_nome(barra)
    if pelo_nome:
        return pelo_nome, "nome da viga no SolidWorks"
    return "", ""


def _direcao_1_na_alma(perfil: Any, corpo: CorpoDoModelo | None) -> tuple[bool, str] | None:
    """A direção 1 do Simulation (a aresta reta mais longa da seção) está ao longo da altura d
    (a alma) ou da largura b (a mesa)? Pela macro v6 quando ela mede sem dúvida; senão pelo
    catálogo, com a folga do raio de concordância; ``None`` na dúvida."""
    familia = ss.familia_do_perfil(perfil)
    d, b = float(perfil.altura_mm), float(perfil.largura_mm)
    tf, tw = float(perfil.espessura_mesa_mm), float(perfil.espessura_alma_mm)
    if familia in FAMILIAS_I:
        alma_max = d - 2.0 * tf  # a face reta da alma, sem o raio
        alma_min = alma_max - 2.0 * max(tw, tf)  # com um raio generoso
    elif familia in FAMILIAS_U:
        alma_max = alma_min = d  # as costas da alma são retas na altura toda
    elif familia == "t":
        alma_max = d - tf
        alma_min = alma_max - max(tw, tf)
    elif familia == "tubo" and ss.e_tubo_retangular(perfil):
        alma_max = alma_min = d  # os cantos arredondados descontam o mesmo dos dois lados
    else:
        return None  # cantoneira, barra, tubo redondo: o eixo forte não vem daqui
    # 1) A macro v6 mediu a direção 1; a direção A (a medida maior da caixa) diz se é a alma.
    if (
        corpo is not None
        and corpo.direcao_1 is not None
        and corpo.direcao_secao is not None
        and (corpo.folga_da_direcao_1_mm or 0.0) >= 1.0
        and corpo.secao_mm is not None
        and corpo.secao_mm[0] >= 1.05 * corpo.secao_mm[1]
        and abs(d - b) >= 0.05 * max(d, b)
    ):
        cos = abs(sum(x * y for x, y in zip(corpo.direcao_1, corpo.direcao_secao, strict=True)))
        a_e_a_altura = d > b
        if cos >= 0.9:
            return a_e_a_altura, EIXO_PELA_MACRO
        if cos <= 0.1:
            return not a_e_a_altura, EIXO_PELA_MACRO
    # 2) O catálogo: só sem dúvida (alma e mesa longe uma da outra).
    if alma_min >= FOLGA_DO_CATALOGO * b:
        return True, EIXO_PELO_PERFIL
    if b >= FOLGA_DO_CATALOGO * alma_max:
        return False, EIXO_PELO_PERFIL
    return None


def eixo_forte_pela_secao(
    perfil: str, corpo: CorpoDoModelo | None = None
) -> tuple[str, str] | None:
    """Qual momento do Simulation é o do eixo forte, pela seção — (EIXO_M1 ou EIXO_M2, origem).

    O Simulation põe a direção 1 na aresta reta mais longa da seção. Ao longo da alma (altura d),
    o M₂ é em torno da direção da mesa: o eixo forte (x do catálogo). Ao longo da mesa, o M₁.
    Conferido no modelo real pelo módulo resistente que o Simulation usa (S = M/σ): pilar
    W 200 × 31,3 com S₁ = W_y e S₂ = W_x; vigas U com S₂ = W_x. ``None`` sem o perfil no catálogo
    ou na dúvida (cantoneira, tubo quadrado, alma e mesa quase iguais sem a macro v6).
    """
    if not perfil:
        return None
    try:
        p = sc.obter_perfil(perfil)
    except (KeyError, ValueError):
        return None
    na_alma = _direcao_1_na_alma(p, corpo)
    if na_alma is None:
        return None
    return (em.EIXO_M2 if na_alma[0] else em.EIXO_M1), na_alma[1]


def esqueleto_de_outro_modelo(g: GeometriaDoModelo, dados: em.EsforcosDoModelo) -> bool:
    """Menos da metade das barras do Simulation acha o corpo no esqueleto: ele é de outra peça (ou
    de outra versão) e as deduções pela geometria — tipo, perfil, peso, bases — sairiam erradas."""
    nomes = list(dados.nomes_dos_membros)
    if not g.corpos or len(nomes) < 2:
        return False
    achadas = len(correspondencia(g, nomes, dados).corpos)
    return achadas < 0.5 * len(nomes)


def ler_barras(
    dados: em.EsforcosDoModelo,
    geometria: GeometriaDoModelo | None = None,
    plano: pc.PlanoDeCargas | None = None,
) -> list[LeituraDaBarra]:
    from core import travamentos as tv  # importa este módulo: só aqui, sem ciclo na carga

    g = geometria or GeometriaDoModelo()
    if esqueleto_de_outro_modelo(g, dados):
        g = GeometriaDoModelo()
    soltas_geo = pontas_soltas_pela_geometria(g, dados.eixo_vertical) if g.corpos else {}
    perfis = perfis_do_esqueleto(g) if g.corpos else {}
    leituras = []
    corpos = correspondencia(g, dados.nomes_dos_membros, dados).corpos if g.corpos else {}
    for barra in dados.nomes_dos_membros:
        corpo = corpos.get(barra)
        avisos: list[str] = []
        pelo_peso = inclinacao_pelo_peso(dados, barra)
        if corpo is not None and corpo.forma == FORMA_BLOCO and pelo_peso is not None:
            # Peça curta: a maior medida pode ser a da seção, não a do eixo.
            tipo, motivo = tipo_pelos_esforcos(dados, barra, plano)
            motivo = f"{motivo} (peça curta no esqueleto: a direção vem do peso próprio)"
        elif corpo is not None:
            tipo, motivo = tipo_pela_geometria(corpo, dados.eixo_vertical)
            pela_geometria = _angulo_do_corpo(corpo, dados.eixo_vertical)
            if tipo == TIPO_CONTRAVENTAMENTO and motivo.startswith("inclinada"):
                tipo, motivo = _tipo_inclinada(dados, barra, pela_geometria, "no modelo")
            if pelo_peso is not None and abs(pelo_peso - pela_geometria) > DIFERENCA_DE_INCLINACAO:
                avisos.append(
                    f"no esqueleto a barra está a {pela_geometria:.0f}° da horizontal, e pelo peso "
                    f"próprio no PP a {pelo_peso:.0f}°: o corpo não é o desta viga (esqueleto de "
                    "outra versão) ou a gravidade do PP não está na vertical"
                )
        else:
            tipo, motivo = tipo_pelos_esforcos(dados, barra, plano)
        perfil, origem = _perfil(barra, corpo, perfis)
        elementos = _elementos(dados, barra)
        pontas = classificar_pontas(dados, barra)
        if PONTA_SOLTA in pontas:
            onde = (
                "nas duas pontas"
                if pontas == (PONTA_SOLTA, PONTA_SOLTA)
                else ("no início" if pontas[0] == PONTA_SOLTA else "no fim")
            )
            avisos.append(
                f"ponta solta {onde}: nenhum esforço em caso nenhum — falta a junta no SolidWorks "
                "(ou é um balanço de propósito)"
            )
        if corpo is not None and corpo.nome in soltas_geo and PONTA_SOLTA not in pontas:
            avisos.append(
                f"no esqueleto, a ponta {' e '.join(soltas_geo[corpo.nome])} não encosta em outra "
                "barra nem no apoio"
            )
        if pontas == (PONTA_SEM_ESFORCO, PONTA_SEM_ESFORCO):
            avisos.append("sem esforço em caso nenhum: barra solta ou fora do caminho das cargas")
        if tipo == TIPO_VIGA and elementos and elementos % 2 == 1 and elementos < 7:
            avisos.append(
                f"malha de {elementos} elemento(s): sem nó no meio do vão, o momento máximo de "
                f"uma carga distribuída pode ficar até {100 / elementos**2:.0f} % abaixo do real "
                "— refine a malha (número par de elementos ou 7 ou mais)"
            )
        escolhido = dados.membros[barra].perfil if barra in dados.membros else ""
        pela_secao = eixo_forte_pela_secao(escolhido or perfil, corpo)
        if pela_secao is not None:
            eixo_forte, origem_do_eixo = pela_secao
        else:
            eixo_forte = em.eixo_forte_sugerido(_pontos(dados, barra))
            origem_do_eixo = EIXO_PELO_MOMENTO
        sugeridos = (
            tv.comprimentos(g, corpo, tipo, dados.eixo_vertical) if corpo is not None else None
        )
        if sugeridos is not None and sugeridos.balanco:
            avisos.append(
                "ponta livre (nada encosta nela e não é apoio): balanço, comprimento de "
                "flambagem com K = 2,1 — confira se é mesmo um balanço ou se falta a junta"
            )
        leituras.append(
            LeituraDaBarra(
                barra=barra,
                corpo=corpo,
                tipo_sugerido=tipo,
                motivo_do_tipo=motivo,
                perfil_sugerido=perfil,
                origem_do_perfil=origem,
                comprimento_m=corpo.comprimento_m if corpo is not None else None,
                elementos=elementos,
                pontas=pontas,
                eixo_forte=eixo_forte,
                avisos=tuple(avisos),
                lx_m=sugeridos.lx_m if sugeridos else None,
                ly_m=sugeridos.ly_m if sugeridos else None,
                lb_m=sugeridos.lb_m if sugeridos else None,
                motivo_dos_comprimentos=sugeridos.motivo if sugeridos else "",
                origem_do_eixo=origem_do_eixo,
            )
        )
    return leituras


def aplicar_sugestoes(
    dados: em.EsforcosDoModelo, leituras: Sequence[LeituraDaBarra]
) -> tuple[em.EsforcosDoModelo, int]:
    """Preenche a tabela das barras só onde está vazia; devolve os dados e quantas barras mudaram.

    Tipo, perfil (só do catálogo), eixo forte e os comprimentos de flambagem: os dos travamentos do
    esqueleto (:mod:`core.travamentos`) ou, sem eles, o comprimento da barra (K = 1).
    O eixo forte pela seção (macro v6 ou perfil) não é escolha: é qual momento do Simulation é o
    do eixo forte, e ele troca o que estiver na tabela. Pelo momento que domina (sem a seção), só
    entra quando o tipo também era vazio.
    O perfil que entrou sozinho pelo nome da viga (na importação) não é escolha de ninguém: com o
    esqueleto, ele dá lugar ao perfil do modelo (lista de corte conferida pela área da seção), que
    é a seção que a análise usou.
    """
    catalogo = set(em._catalogo())
    novos: dict[str, em.ConfiguracaoDoMembro] = {}
    mudaram = 0
    for leitura in leituras:
        atual = dados.membros.get(leitura.barra, em.ConfiguracaoDoMembro())
        tipo = atual.tipo if atual.tipo != "—" else leitura.tipo_sugerido
        do_modelo = leitura.perfil_sugerido if leitura.perfil_sugerido in catalogo else ""
        so_pelo_nome = (
            leitura.corpo is not None
            and bool(do_modelo)
            and atual.perfil == (em.perfil_do_nome(leitura.barra) or "")
        )
        perfil = do_modelo if so_pelo_nome else (atual.perfil or do_modelo)
        comprimento = leitura.comprimento_m
        novo = replace(
            atual,
            tipo=tipo if tipo in em.TIPOS_DE_BARRA else atual.tipo,
            perfil=perfil,
            eixo_forte=(
                leitura.eixo_forte
                if leitura.origem_do_eixo in EIXOS_CERTOS or atual.tipo == "—"
                else atual.eixo_forte
            ),
            lx_m=atual.lx_m or leitura.lx_m or comprimento,
            ly_m=atual.ly_m or leitura.ly_m or comprimento,
            lb_m=atual.lb_m or leitura.lb_m or comprimento,
        )
        if novo != atual:
            mudaram += 1
            novos[leitura.barra] = novo
    return (em.com_membros(dados, novos) if novos else dados), mudaram


# ---------------------------------------------------------------------------------------------
# O conjunto
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Achado:
    nivel: str  # pc.NIVEL_ERRO, pc.NIVEL_ATENCAO, em.NIVEL_INFO ou pc.NIVEL_OK
    titulo: str
    texto: str
    barras: tuple[str, ...] = ()


ORDEM_DOS_NIVEIS = {pc.NIVEL_ERRO: 0, pc.NIVEL_ATENCAO: 1, em.NIVEL_INFO: 2, pc.NIVEL_OK: 3}


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _lista(nomes: Sequence[str], limite: int = 6) -> str:
    texto = ", ".join(nomes[:limite])
    return texto + (f" e mais {len(nomes) - limite}" if len(nomes) > limite else "")


def peso_dos_corpos_kN(corpos: Iterable[CorpoDoModelo]) -> float | None:
    """O aço dos corpos pelo volume da macro (7 850 kg/m³); ``None`` se faltar o volume de algum."""
    lista = list(corpos)
    if not lista or any(c.volume_m3 is None for c in lista):
        return None
    return sum(c.volume_m3 or 0.0 for c in lista) * lm.DENSIDADE_ACO * lm.G / 1e3


def peso_do_esqueleto_kN(g: GeometriaDoModelo | None) -> float | None:
    """O que a gravidade do modelo deveria dar no PP, pelos volumes de todos os corpos."""
    return peso_dos_corpos_kN(g.corpos) if g is not None else None


def _mesmo_papel(escolhido: str, sugerido: str) -> bool:
    articuladas = {TIPO_CONTRAVENTAMENTO, "Diagonal"}
    return escolhido == sugerido or (escolhido in articuladas and sugerido in articuladas)


def _vertical(dados: em.EsforcosDoModelo, caso: em.CasoImportado) -> float | None:
    if caso.reacoes is None:
        return None
    return em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)[2]


def _iguais(a: em.CasoImportado, b: em.CasoImportado) -> bool:
    if a.reacoes is None or b.reacoes is None:
        return False
    if any(
        abs(x - y) > 1e-6 * max(1.0, abs(x))
        for x, y in zip(a.reacoes.modelo, b.reacoes.modelo, strict=True)
    ):
        return False
    if all(abs(v) < 1e-9 for v in a.reacoes.modelo):
        return False  # dois casos sem carga já viram outro achado
    for barra, pontos in list(a.membros.items())[:20]:
        outros = b.membros.get(barra)
        if outros is None or len(outros) != len(pontos):
            return False
        if any(
            abs(x - y) > 1e-6 * max(1.0, abs(x))
            for p, q in zip(pontos, outros, strict=True)
            for x, y in zip(p.vetor(), q.vetor(), strict=True)
        ):
            return False
    return True


def diagnosticar(
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    geometria: GeometriaDoModelo | None = None,
    leituras: Sequence[LeituraDaBarra] | None = None,
    *,
    peso_da_estrutura_kN: float | None = None,
) -> list[Achado]:
    """Os achados sobre o conjunto dos casos importados, do mais grave ao informativo.

    ``peso_da_estrutura_kN`` (da Lista de material) serve quando o esqueleto não diz o peso de
    cada barra: a carga que o PP leva ao longo das barras não pode passar do aço todo.
    """
    if not dados.casos:
        return []
    leituras = list(leituras) if leituras is not None else ler_barras(dados, geometria, plano)
    g = geometria or GeometriaDoModelo()
    achados: list[Achado] = []
    if esqueleto_de_outro_modelo(g, dados):
        achadas = len(correspondencia(g, dados.nomes_dos_membros, dados).corpos)
        achados.append(
            Achado(
                pc.NIVEL_ERRO,
                "Esqueleto de outro modelo",
                f"Só {achadas} das {len(dados.nomes_dos_membros)} barras do Simulation acham o "
                f"corpo no esqueleto ({g.arquivo}"
                + (f", {g.origem}" if g.origem else "")
                + "): ele é de outra peça ou de outra versão. O programa não usa esse esqueleto "
                "— tipo, perfil, peso e bases das barras saem só dos esforços. Rode a macro da "
                "lista de corte na peça do estudo e envie o …_esqueleto.csv dela.",
            )
        )
        g = GeometriaDoModelo()
    casos = list(dados.casos.values())

    # Valores fora de escala: unidade errada no SolidWorks ou no arquivo.
    absurdos = sorted(
        {
            barra
            for caso in casos
            for barra, pontos in caso.membros.items()
            if any(abs(v) > VALOR_ABSURDO for p in pontos for v in p.vetor())
        }
    )
    if absurdos:
        achados.append(
            Achado(
                pc.NIVEL_ERRO,
                "Valores fora de escala",
                f"Esforços acima de {VALOR_ABSURDO:,.0f} kN ou kN·m em {_lista(absurdos)}: confira "
                "a unidade do SolidWorks (N × kN, mm × m) e o arquivo.".replace(",", "."),
                tuple(absurdos),
            )
        )

    # Eixo vertical: no PP só há gravidade, a reação tem de ser vertical.
    pp = dados.casos.get("PP")
    if pp is not None and pp.reacoes is not None:
        componentes = [abs(v) for v in pp.reacoes.modelo]
        total = math.hypot(*componentes)
        dominante = componentes.index(max(componentes))
        vertical = _indice_vertical(dados.eixo_vertical)
        if total > 0.01 and dominante != vertical and componentes[dominante] > 0.9 * total:
            eixo = "XYZ"[dominante]
            achados.append(
                Achado(
                    pc.NIVEL_ERRO,
                    "Eixo vertical trocado",
                    f"O peso do PP aparece em {eixo}, mas a página está com {dados.eixo_vertical} "
                    f"para cima: troque o eixo vertical no passo 1 para {eixo}.",
                )
            )

    # Casos sem carga e casos repetidos.
    for caso in casos:
        sem_reacao = caso.reacoes is not None and all(abs(v) < 1e-6 for v in caso.reacoes.modelo)
        sem_forca = all(
            abs(v) < 1e-9 for pontos in caso.membros.values() for p in pontos for v in p.vetor()
        )
        if sem_reacao and sem_forca:
            achados.append(
                Achado(
                    pc.NIVEL_ERRO,
                    f"{caso.codigo}: estudo sem carga",
                    f"O estudo {caso.estudo or caso.codigo} não tem reação nem esforço: as cargas "
                    "do caso não foram aplicadas (ou o estudo não foi rodado de novo).",
                )
            )
    for i, a in enumerate(casos):
        for b in casos[i + 1 :]:
            if _iguais(a, b):
                achados.append(
                    Achado(
                        pc.NIVEL_ERRO,
                        f"{a.codigo} e {b.codigo} têm o mesmo resultado",
                        f"Os dois casos dão as mesmas reações e os mesmos esforços: o mesmo arquivo "
                        f"foi enviado duas vezes ou o estudo {b.codigo} foi duplicado sem trocar "
                        "as cargas.",
                    )
                )

    # Gravidade que ficou num estudo duplicado do PP.
    peso = _vertical(dados, pp) if pp is not None else None
    if peso is not None and peso > 0.5:
        for caso in casos:
            if caso.codigo == "PP" or caso.reacoes is None:
                continue
            acao = plano.acao(caso.codigo)
            esperado = em.total_esperado(acao) if acao is not None else None
            if esperado is None and acao is not None and acao.cargas:
                continue  # carga por área ou distribuída sem comprimento: não dá para separar
            esperado_vertical = -esperado[2] if esperado is not None else 0.0
            reacao_vertical = _vertical(dados, caso) or 0.0
            sobra = reacao_vertical - esperado_vertical
            if abs(sobra - peso) <= 0.03 * peso:
                achados.append(
                    Achado(
                        pc.NIVEL_ERRO,
                        f"{caso.codigo}: ficou com a gravidade",
                        f"A reação vertical do {caso.codigo} tem {_n(sobra)} kN a mais do que as "
                        f"cargas do plano — é o peso da estrutura ({_n(peso)} kN no PP). O estudo "
                        "foi duplicado do PP sem excluir a gravidade: exclua-a e rode de novo.",
                    )
                )

    # Peso próprio contra o aço do esqueleto: entre o das barras do estudo e o de todos os corpos.
    if g.corpos and peso is not None and peso > 0.01:
        fator = plano.fator_peso_proprio
        todos = peso_do_esqueleto_kN(g)
        corpos_do_estudo = {lb.corpo.nome: lb.corpo for lb in leituras if lb.corpo is not None}
        das_barras = peso_dos_corpos_kN(corpos_do_estudo.values())
        if todos is not None and das_barras is not None:
            maximo, minimo = todos * fator, das_barras * fator
            ligacoes = f", × {_n(fator)} de ligações não modeladas" if fator > 1 else ""
            faixa = (
                f"{_n(maximo)} kN"
                if maximo - minimo < 0.01
                else f"entre {_n(minimo)} kN (só as barras do estudo) e {_n(maximo)} kN (todos "
                "os corpos)"
            )
            if peso > (1 + em.TOLERANCIA_PESO) * maximo:
                razao = peso / maximo
                gama = em.coeficiente_aparente(razao)
                texto = (
                    f"O PP dá {_n(peso)} kN de reação vertical, e o aço de todos os corpos do "
                    f"esqueleto pesa {_n(maximo)} kN (volume × 7 850 kg/m³{ligacoes})"
                )
                if gama is not None:
                    texto += (
                        f": {_n(razao)} vez — o estudo PP parece majorado (γ ≈ {_n(gama)}). "
                        f"{em.ESTUDO_MAJORADO}"
                    )
                else:
                    texto += (
                        f": {_n(razao, 1)} vezes. O estudo PP leva só a gravidade — sobrecarga, "
                        "equipamentos e o que não está modelado vão nos estudos deles (SC, EQ, "
                        "PE…), com as cargas características. Confira também a densidade dos "
                        "materiais (7 850 kg/m³) e a gravidade (9,81 m/s²)."
                    )
                achados.append(Achado(pc.NIVEL_ERRO, "PP mais pesado que a estrutura", texto))
            elif peso < (1 - em.TOLERANCIA_PESO) * minimo:
                achados.append(
                    Achado(
                        pc.NIVEL_ATENCAO,
                        "PP mais leve que o aço das barras",
                        f"O PP dá {_n(peso)} kN de reação vertical, e só o aço das "
                        f"{len(corpos_do_estudo)} barras do estudo pesa {_n(minimo)} kN "
                        f"(volume × 7 850 kg/m³{ligacoes}): há corpo sem material, com material "
                        "que não é aço (o alumínio pesa um terço) ou com densidade diferente de "
                        "7 850 kg/m³"
                        + (
                            f", ou a gravidade do PP ficou sem o fator das ligações "
                            f"(9,81 × {_n(fator)})."
                            if fator > 1
                            else "."
                        ),
                    )
                )
            else:
                achados.append(
                    Achado(
                        pc.NIVEL_OK,
                        "Peso próprio confere com o esqueleto",
                        f"PP: {_n(peso)} kN de reação vertical; aço do esqueleto {faixa}"
                        f"{ligacoes}.",
                    )
                )

    # O caminho do peso no PP: o que chega ao longo das barras (peso delas e cargas por metro) e o
    # que chega pelos nós (chapas, sólidos, forças concentradas). Com o esqueleto, barra a barra
    # (não precisa das reações: a carga ao longo de cada barra sai das forças da viga).
    if pp is not None:
        ao_longo = 0.0
        a_mais: list[str] = []
        barras_a_mais: list[str] = []
        carga_da_barra: dict[str, float] = {}
        conferidas, com_pp = 0, 0
        proprio_total = carga_conferida = 0.0
        for lb in leituras:
            variacao = variacao_no_pp(dados, lb.barra)
            if variacao is None:
                continue
            carga = math.hypot(*variacao)
            ao_longo += carga
            carga_da_barra[lb.barra] = carga
            com_pp += 1
            corpo = lb.corpo
            if corpo is None or not corpo.volume_m3 or corpo.comprimento_m <= 0:
                continue
            proprio = (
                corpo.volume_m3
                * lm.DENSIDADE_ACO
                * lm.G
                / 1e3
                / corpo.comprimento_m
                * plano.fator_peso_proprio
            )
            por_metro = carga / corpo.comprimento_m
            conferidas += 1
            proprio_total += proprio * corpo.comprimento_m
            carga_conferida += carga
            if por_metro > 1.15 * proprio + 0.05:
                barras_a_mais.append(lb.barra)
                a_mais.append(
                    f"{lb.barra} ({_n(por_metro)} kN/m; o peso dela é {_n(proprio)} kN/m)"
                )
        apoiados = [c for c in g.corpos if c.forma in ("CHAPA", "BLOCO") and c.volume_m3]
        aco_todo = (
            sum(c.volume_m3 or 0.0 for c in g.corpos)
            * lm.DENSIDADE_ACO
            * lm.G
            / 1e3
            * plano.fator_peso_proprio
        )
        if a_mais and apoiados and peso is not None and peso <= 1.15 * aco_todo + 0.1:
            # O PP total bate com o aço de todos os corpos: o que passa do peso das barras é o
            # peso das chapas e blocos apoiados nelas, não carga posta no estudo PP.
            achados.append(
                Achado(
                    em.NIVEL_INFO,
                    "Peso das chapas sobre as barras no PP",
                    f"{_lista(a_mais, 4)}: ao longo dessas barras o PP leva mais que o peso delas, "
                    f"mas o PP inteiro ({_n(peso)} kN) bate com o aço de todos os corpos "
                    f"({_n(aco_todo)} kN, com {len(apoiados)} chapa(s)/bloco(s)): é o peso das "
                    "chapas apoiadas nelas, não carga a mais no estudo PP.",
                    tuple(barras_a_mais),
                )
            )
        elif a_mais:
            achados.append(
                Achado(
                    pc.NIVEL_ERRO,
                    "Carga além do peso próprio no PP",
                    f"{_lista(a_mais, 4)}: ao longo dessas barras o PP leva mais que o peso delas "
                    "— há carga por metro aplicada no estudo PP. O PP leva só a gravidade: mova "
                    "essas cargas para os estudos dos casos delas (SC, EQ, PE…), com os valores "
                    "característicos.",
                    tuple(barras_a_mais),
                )
            )
        elif conferidas and conferidas >= 0.8 * com_pp:
            achados.append(
                Achado(
                    pc.NIVEL_OK,
                    "PP só com a gravidade nas barras",
                    f"Em {conferidas} barra(s), o PP leva ao longo delas {_n(carga_conferida)} kN "
                    f"e o aço delas pesa {_n(proprio_total)} kN (volume do esqueleto × 7 850 "
                    "kg/m³): nenhuma carga a mais por metro no estudo PP.",
                )
            )
        elif peso_da_estrutura_kN and ao_longo > (
            1.15 * peso_da_estrutura_kN * plano.fator_peso_proprio + 0.1
        ):
            maiores = sorted(carga_da_barra, key=carga_da_barra.__getitem__, reverse=True)[:5]
            achados.append(
                Achado(
                    pc.NIVEL_ERRO,
                    "Carga além do peso próprio no PP",
                    f"Ao longo das barras o PP leva {_n(ao_longo)} kN, e o aço da estrutura "
                    f"inteira pesa {_n(peso_da_estrutura_kN)} kN (Lista de material): há carga "
                    "por metro aplicada no estudo PP. As barras que mais recebem: "
                    + ", ".join(f"{b} ({_n(carga_da_barra[b])} kN)" for b in maiores)
                    + ". O PP leva só a gravidade: mova essas cargas para os estudos dos casos "
                    "delas (SC, EQ, PE…), com os valores característicos. Com o esqueleto da "
                    "macro, o programa aponta barra a barra.",
                    tuple(maiores),
                )
            )
        pelos_nos = (peso or 0.0) - ao_longo
        if peso is not None and peso > 0.01 and ao_longo > 0 and pelos_nos > 0.05 * peso:
            achados.append(
                Achado(
                    em.NIVEL_INFO,
                    "Caminho do peso no PP",
                    f"Dos {_n(peso)} kN do PP, {_n(ao_longo)} kN chegam distribuídos ao longo das "
                    f"barras (o peso delas e cargas por metro) e {_n(pelos_nos)} kN pelos nós "
                    "(chapas, sólidos, forças concentradas). Se o modelo é só o esqueleto, quase "
                    "tudo deveria vir ao longo das barras.",
                )
            )

    # Modelo que mudou entre os estudos e malhas diferentes.
    todas = dados.nomes_dos_membros
    for caso in casos:
        faltam = [b for b in todas if b not in caso.membros]
        if faltam and caso.membros:
            achados.append(
                Achado(
                    pc.NIVEL_ERRO,
                    f"{caso.codigo}: faltam barras",
                    f"O {caso.codigo} não tem {_lista(faltam)}: o modelo mudou entre os estudos. "
                    "Rode todos os estudos com o mesmo modelo.",
                    tuple(faltam),
                )
            )
    malha_diferente = sorted(
        barra
        for barra in todas
        if len(
            {tuple(p.chave for p in caso.membros[barra]) for caso in casos if barra in caso.membros}
        )
        > 1
    )
    if malha_diferente:
        achados.append(
            Achado(
                pc.NIVEL_ATENCAO,
                "Malha diferente entre os estudos",
                f"{_lista(malha_diferente)}: a numeração dos elementos muda de um estudo para "
                "outro, e as combinações deixam de ser ponto a ponto. Duplique o estudo PP para "
                "os outros casos, sem refazer a malha.",
                tuple(malha_diferente),
            )
        )

    # Barra a barra.
    soltas = [lb.barra for lb in leituras if lb.tem_ponta_solta]
    if soltas:
        achados.append(
            Achado(
                pc.NIVEL_ATENCAO,
                "Pontas soltas",
                f"{_lista(soltas)}: uma ponta sem nenhum esforço em caso nenhum. Quase sempre é a "
                "junta que faltou entre as vigas no SolidWorks (Juntas › Calcular de novo, ou "
                "estender e aparar até encostar) — confira, a não ser que seja um balanço.",
                tuple(soltas),
            )
        )
    paradas = [lb.barra for lb in leituras if lb.pontas == (PONTA_SEM_ESFORCO, PONTA_SEM_ESFORCO)]
    if paradas:
        achados.append(
            Achado(
                pc.NIVEL_ATENCAO,
                "Barras sem esforço",
                f"{_lista(paradas)}: nenhum esforço em caso nenhum. Barra solta ou fora do caminho "
                "das cargas — confira as juntas.",
                tuple(paradas),
            )
        )
    grossas = [lb.barra for lb in leituras if any("malha de" in a for a in lb.avisos)]
    if grossas:
        achados.append(
            Achado(
                pc.NIVEL_ATENCAO,
                "Malha grossa nas vigas",
                f"{_lista(grossas)}: número ímpar e pequeno de elementos, sem nó no meio do vão — "
                "o momento máximo pode ficar de fora. Refine a malha das vigas.",
                tuple(grossas),
            )
        )
    tipos = {
        lb.barra: (dados.membros.get(lb.barra, em.ConfiguracaoDoMembro()).tipo, lb.tipo_sugerido)
        for lb in leituras
    }
    trocados = [
        lb.barra
        for lb in leituras
        if lb.corpo is not None
        and tipos[lb.barra][0] not in ("—", "Outro")
        and lb.tipo_sugerido != "—"
        and not _mesmo_papel(*tipos[lb.barra])
    ]
    if trocados:
        achados.append(
            Achado(
                pc.NIVEL_ATENCAO,
                "Tipo diferente da posição no modelo",
                f"{_lista(trocados)}: o tipo escolhido na tabela não é o da posição da barra no "
                "esqueleto (vertical = pilar, horizontal = viga, inclinada = contraventamento). "
                "Os parâmetros da verificação (comprimentos, Cb, aço, B₂) saem do tipo da tabela.",
                tuple(trocados),
            )
        )
    pilares = [lb.barra for lb in leituras if TIPO_PILAR in tipos[lb.barra]]
    if pilares and dados.parametros_do_tipo(TIPO_PILAR).b2 <= 1.0:
        contraventada = any(
            TIPO_CONTRAVENTAMENTO in par or "Diagonal" in par for par in tipos.values()
        )
        achados.append(
            Achado(
                em.NIVEL_INFO if contraventada else pc.NIVEL_ATENCAO,
                "Segunda ordem global (B₂)",
                "O estudo do SolidWorks é linear (1ª ordem) e o B₂ dos pilares está em 1,00. "
                + (
                    "Com contraventamento, isso só vale se a estrutura for de pequena "
                    "deslocabilidade"
                    if contraventada
                    else "Sem contraventamento, o pórtico costuma ser de média ou grande "
                    "deslocabilidade e os momentos de 2ª ordem não podem ser desprezados"
                )
                + ": classifique a estrutura na página Contraventamento e informe o B₂ na "
                "tabela de parâmetros (passo 6). Considere também as imperfeições iniciais "
                "(força nocional de 0,3 % das cargas gravitacionais de cálculo).",
                tuple(pilares),
            )
        )
    rigidas = [
        lb.barra
        for lb in leituras
        if TIPO_VIGA in tipos[lb.barra] and lb.pontas == (PONTA_RIGIDA, PONTA_RIGIDA)
    ]
    if rigidas:
        achados.append(
            Achado(
                em.NIVEL_INFO,
                "Vigas engastadas nas pontas",
                f"{len(rigidas)} viga(s) com momento nas duas pontas ({_lista(rigidas, 4)}): no "
                "SolidWorks as juntas das vigas são rígidas. Se a ligação real só transmite "
                "cortante (cantoneiras, chapa de alma), articule essas pontas no modelo — senão o "
                "momento no meio do vão sai menor que o real e a ligação recebe um momento que ela "
                "não tem. Num pórtico sem contraventamento é o contrário: a ligação rígida é o que "
                "dá a estabilidade lateral e tem de ser detalhada para o momento.",
                tuple(rigidas),
            )
        )
    eixo_trocado = [
        lb.barra
        for lb in leituras
        if lb.origem_do_eixo in EIXOS_CERTOS
        and lb.barra in dados.membros
        and dados.membros[lb.barra].eixo_forte != lb.eixo_forte
    ]
    if eixo_trocado:
        achados.append(
            Achado(
                pc.NIVEL_ERRO,
                "Eixo forte trocado",
                f"{_lista(eixo_trocado)}: na tabela, o eixo forte é o outro momento. Pela seção, "
                "o Simulation põe a direção 1 na aresta reta mais longa — ao longo da alma, o M₂ é "
                "o do eixo forte; ao longo da mesa, o M₁ — e a verificação compararia o momento "
                "do eixo fraco com a resistência do forte. “Aplicar as sugestões” corrige.",
                tuple(eixo_trocado),
            )
        )
    escolhidos = {
        lb.barra: dados.membros[lb.barra].perfil
        for lb in leituras
        if lb.barra in dados.membros and dados.membros[lb.barra].perfil
    }
    divergentes = [
        lb.barra
        for lb in leituras
        if lb.perfil_sugerido
        and lb.corpo is not None
        and escolhidos.get(lb.barra)
        and escolhidos[lb.barra] != lb.perfil_sugerido
    ]
    if divergentes:
        achados.append(
            Achado(
                pc.NIVEL_ATENCAO,
                "Perfil diferente do modelo",
                f"{_lista(divergentes)}: o perfil da tabela não é a seção do modelo (lista de "
                "corte conferida pela área). Os esforços saíram da seção do modelo e a verificação "
                "usa a da tabela: se o perfil da tabela veio só do nome da viga, “Aplicar as "
                "sugestões” troca pelo do modelo; se foi escolhido de propósito, troque o perfil "
                "no SolidWorks e rode os estudos de novo.",
                tuple(divergentes),
            )
        )

    # Corpos renomeados depois do estudo: casados pela numeração e pela inclinação.
    if g.corpos:
        casamento = correspondencia(g, todas, dados)
        if casamento.renomeados:
            mapa_texto = "; ".join(f"“{a}” → “{n}”" for a, n in casamento.renomeados.items())
            achados.append(
                Achado(
                    pc.NIVEL_ATENCAO,
                    "Corpos renomeados depois do estudo",
                    f"{casamento.pela_renomeacao} viga(s) do Simulation têm o nome antigo do corpo; "
                    f"o programa casou pela numeração [n] de cada membro, pelo perfil e pela "
                    f"inclinação do peso próprio: {mapa_texto}. Confira; para não depender disso, "
                    "refaça a malha dos estudos (os nomes novos passam ao Simulation) ou gere o "
                    "esqueleto com os nomes do estudo.",
                )
            )

    # Esqueleto: barras sem corpo.
    if g.corpos:
        sem_corpo = [lb.barra for lb in leituras if lb.corpo is None]
        if sem_corpo:
            achados.append(
                Achado(
                    pc.NIVEL_ATENCAO,
                    "Barras fora do esqueleto",
                    f"{_lista(sem_corpo)}: não achei o corpo no arquivo do esqueleto — ele é de "
                    "outra versão do modelo? Gere os dois arquivos de novo.",
                    tuple(sem_corpo),
                )
            )
    if not [a for a in achados if a.nivel in (pc.NIVEL_ERRO, pc.NIVEL_ATENCAO)]:
        achados.append(
            Achado(
                pc.NIVEL_OK,
                "Nada de estranho",
                f"{len(casos)} caso(s), {len(todas)} barras: os casos são diferentes entre si, "
                "têm carga, usam o mesmo modelo e a mesma malha, e nenhuma barra ficou solta.",
            )
        )
    return sorted(achados, key=lambda a: ORDEM_DOS_NIVEIS.get(a.nivel, 9))


def resumo_das_barras(leituras: Sequence[LeituraDaBarra]) -> dict[str, int]:
    resumo = {TIPO_PILAR: 0, TIPO_VIGA: 0, TIPO_CONTRAVENTAMENTO: 0, "—": 0}
    for lb in leituras:
        resumo[lb.tipo_sugerido if lb.tipo_sugerido in resumo else "—"] += 1
    return resumo


# ---------------------------------------------------------------------------------------------
# Na hora de enviar
# ---------------------------------------------------------------------------------------------
def avisos_da_importacao(
    escolhas: Sequence[tuple[em.ArquivoLido, str]], codigos: Iterable[str]
) -> list[Achado]:
    """O que não fecha entre os arquivos enviados e os casos escolhidos para eles."""
    achados: list[Achado] = []
    lista_codigos = list(codigos)
    forcas: dict[str, list[em.ArquivoLido]] = {}
    reacoes: dict[str, list[em.ArquivoLido]] = {}
    for arquivo, caso in escolhas:
        if not caso:
            continue
        destino = forcas if arquivo.tipo == em.TIPO_VIGAS else reacoes
        if arquivo.tipo in (em.TIPO_VIGAS, em.TIPO_REACOES):
            destino.setdefault(caso, []).append(arquivo)
        sugerido = em.caso_do_arquivo_sugerido(arquivo, lista_codigos)
        if sugerido and sugerido != caso:
            achados.append(
                Achado(
                    pc.NIVEL_ATENCAO,
                    f"{arquivo.nome_arquivo}: estudo {arquivo.estudo}",
                    f"O estudo se chama {arquivo.estudo} (caso {sugerido}), mas foi escolhido o caso "
                    f"{caso}. Confira.",
                )
            )
    for caso, arquivos in forcas.items():
        if len(arquivos) > 1:
            achados.append(
                Achado(
                    pc.NIVEL_ERRO,
                    f"{caso}: dois arquivos de forças",
                    f"{', '.join(a.nome_arquivo for a in arquivos)} foram escolhidos para o mesmo "
                    "caso: só o último ficaria. Escolha o caso certo de cada um.",
                )
            )
        if caso not in reacoes:
            achados.append(
                Achado(
                    em.NIVEL_INFO,
                    f"{caso}: sem o arquivo de reações",
                    f"Sem as reações do {caso} (Listar forças resultantes), o equilíbrio do caso "
                    "não é conferido.",
                )
            )
    for caso, arquivos in reacoes.items():
        if len(arquivos) > 1:
            achados.append(
                Achado(
                    pc.NIVEL_ERRO,
                    f"{caso}: dois arquivos de reações",
                    f"{', '.join(a.nome_arquivo for a in arquivos)} foram escolhidos para o mesmo "
                    "caso.",
                )
            )
        if caso in forcas:
            estudos = {forcas[caso][-1].estudo, arquivos[-1].estudo} - {""}
            if len(estudos) > 1:
                achados.append(
                    Achado(
                        pc.NIVEL_ATENCAO,
                        f"{caso}: forças e reações de estudos diferentes",
                        f"As forças são do estudo {forcas[caso][-1].estudo} e as reações do "
                        f"{arquivos[-1].estudo}. Confira se são do mesmo estudo.",
                    )
                )
    return sorted(achados, key=lambda a: ORDEM_DOS_NIVEIS.get(a.nivel, 9))


# ---------------------------------------------------------------------------------------------
# Tensões da viga: a seção que o Simulation usou
# ---------------------------------------------------------------------------------------------
ESCOAMENTO_A36_MPA = 250.0
TOLERANCIA_SECAO_SIMULATION = 0.05
#: S de um eixo ÷ o do outro para o Simulation dizer qual momento é o do eixo forte.
RAZAO_DOS_MODULOS = 1.5
TOLERANCIA_MODULO_SIMULATION = 0.10


def area_no_simulation(
    forcas: Mapping[str, Sequence[em.PontoDeEsforco]],
    tensoes: Mapping[str, Sequence[em.TensaoDaViga]],
) -> dict[str, float]:
    """A área (mm²) que o Simulation usou em cada barra: força normal ÷ tensão axial, ponta a ponta
    (mesmo elemento e mesma ponta nos dois arquivos do mesmo estudo); a mediana da barra."""
    areas: dict[str, float] = {}
    for barra, pontos in tensoes.items():
        forca = {(p.elemento, p.fim): p for p in forcas.get(barra, ())}
        valores = [
            abs(f.n) * 1e3 / abs(t.axial)
            for t in pontos
            if (f := forca.get((t.elemento, t.fim))) is not None
            and abs(t.axial) >= 0.1
            and abs(f.n) >= 0.05
        ]
        if valores:
            areas[barra] = statistics.median(valores)
    return areas


def modulos_no_simulation(
    forcas: Mapping[str, Sequence[em.PontoDeEsforco]],
    tensoes: Mapping[str, Sequence[em.TensaoDaViga]],
) -> dict[str, tuple[float | None, float | None]]:
    """O módulo resistente (mm³) que o Simulation usou em torno de cada direção da seção:
    S₁ = |M₁| ÷ |σ da flexão 1| e S₂ = |M₂| ÷ |σ da flexão 2|, ponta a ponta (mesmo elemento e
    ponta nos dois arquivos do mesmo estudo); a mediana da barra, ``None`` sem momento."""
    saida: dict[str, tuple[float | None, float | None]] = {}
    for barra, pontos in tensoes.items():
        forca = {(p.elemento, p.fim): p for p in forcas.get(barra, ())}
        s1: list[float] = []
        s2: list[float] = []
        for t in pontos:
            f = forca.get((t.elemento, t.fim))
            if f is None:
                continue
            if abs(f.m1) >= 0.001 and abs(t.flexao1) >= 0.05:
                s1.append(abs(f.m1) * 1e6 / abs(t.flexao1))
            if abs(f.m2) >= 0.001 and abs(t.flexao2) >= 0.05:
                s2.append(abs(f.m2) * 1e6 / abs(t.flexao2))
        if s1 or s2:
            saida[barra] = (
                statistics.median(s1) if s1 else None,
                statistics.median(s2) if s2 else None,
            )
    return saida


def _eixos_pelas_tensoes(
    estudo: str,
    forcas: Mapping[str, Sequence[em.PontoDeEsforco]],
    tensoes: Mapping[str, Sequence[em.TensaoDaViga]],
    dados: em.EsforcosDoModelo,
    leituras: Mapping[str, LeituraDaBarra],
) -> list[Achado]:
    """Qual momento é o do eixo forte, pelo próprio Simulation (o S maior), contra a tabela; e o
    S do eixo forte contra o W_x do perfil."""
    trocados: list[str] = []
    barras_trocadas: list[str] = []
    modulo_diferente: list[str] = []
    conferidas = 0
    for nome, (s1, s2) in sorted(modulos_no_simulation(forcas, tensoes).items()):
        if s1 is None or s2 is None:
            continue
        leitura = leituras.get(nome)
        escolhido = dados.membros[nome].perfil if nome in dados.membros else ""
        perfil = escolhido or (leitura.perfil_sugerido if leitura else "") or ""
        try:
            p = sc.obter_perfil(perfil) if perfil else None
        except (KeyError, ValueError):
            p = None
        if p is None or ss.familia_do_perfil(p) not in (*FAMILIAS_I, *FAMILIAS_U, "t", "tubo"):
            continue
        if not p.sx_mm3 or p.sx_mm3 < 1.3 * p.sy_mm3:
            continue  # seção quase simétrica: não há um eixo forte claro
        if s2 >= RAZAO_DOS_MODULOS * s1:
            pelo_simulation, forte = em.EIXO_M2, s2
        elif s1 >= RAZAO_DOS_MODULOS * s2:
            pelo_simulation, forte = em.EIXO_M1, s1
        else:
            continue
        conferidas += 1
        na_tabela = (
            dados.membros[nome].eixo_forte
            if nome in dados.membros
            else (leitura.eixo_forte if leitura else em.EIXO_M2)
        )
        if na_tabela != pelo_simulation:
            barras_trocadas.append(nome)
            trocados.append(
                f"{nome} (S₁ = {_n(s1 / 1e3, 1)} e S₂ = {_n(s2 / 1e3, 1)} cm³: o forte é o "
                f"{pelo_simulation}; na tabela, {na_tabela})"
            )
        if abs(forte - p.sx_mm3) > TOLERANCIA_MODULO_SIMULATION * p.sx_mm3:
            modulo_diferente.append(
                f"{nome} ({_n(forte / 1e3, 1)} cm³ no Simulation; {perfil}: "
                f"W_x = {_n(p.sx_mm3 / 1e3, 1)} cm³)"
            )
    achados: list[Achado] = []
    if trocados:
        achados.append(
            Achado(
                pc.NIVEL_ERRO,
                f"{estudo}: eixo forte trocado (pelas tensões)",
                f"{_lista(trocados, 4)}. O módulo resistente que o próprio Simulation usou "
                "(momento ÷ tensão de flexão) mostra qual momento é o do eixo forte: a "
                "verificação compararia o momento do eixo fraco com a resistência do forte. "
                "“Aplicar as sugestões” (com o esqueleto da macro v6) ou a coluna Eixo forte "
                "corrige.",
                tuple(barras_trocadas),
            )
        )
    elif conferidas:
        achados.append(
            Achado(
                pc.NIVEL_OK,
                f"{estudo}: eixo forte confere pelas tensões",
                f"Em {conferidas} barra(s), o momento do eixo forte da tabela é o que o Simulation "
                "usou com o módulo resistente maior.",
            )
        )
    if modulo_diferente:
        achados.append(
            Achado(
                pc.NIVEL_ATENCAO,
                f"{estudo}: módulo resistente do Simulation diferente do perfil",
                f"{_lista(modulo_diferente, 4)}: o S do eixo forte que o Simulation usou não é o "
                "W_x do perfil — a seção do modelo não é a da tabela.",
            )
        )
    return achados


def conferir_tensoes(
    lidos: Sequence[em.ArquivoLido],
    dados: em.EsforcosDoModelo,
    geometria: GeometriaDoModelo | None = None,
) -> list[Achado]:
    """O que os "Listar tensões da viga" enviados dizem: a maior tensão (só referência — a NBR 8800
    verifica pelos esforços) e, com as forças do mesmo estudo, se a seção que o Simulation usou em
    cada barra é a do perfil da tabela (ou o sugerido pelo modelo)."""
    achados: list[Achado] = []
    for arquivo in lidos:
        if arquivo.tipo != em.TIPO_TENSOES_VIGA or not arquivo.tensoes_da_viga:
            continue
        estudo = arquivo.estudo or arquivo.nome_arquivo
        barra, maior = max(
            (
                (nome, max(abs(t.pior) for t in pontos))
                for nome, pontos in arquivo.tensoes_da_viga.items()
            ),
            key=lambda par: par[1],
        )
        texto = (
            f"Maior tensão normal (pior cenário: axial + flexão) de {_n(maior, 1)} MPa, em {barra}. "
            "É só referência: a verificação da NBR 8800 é pelos esforços (flambagem, flambagem "
            "lateral, interação)."
        )
        nivel = em.NIVEL_INFO
        if maior > ESCOAMENTO_A36_MPA:
            nivel = pc.NIVEL_ATENCAO
            texto += " Passa do escoamento do A36 (250 MPa): essa barra não vai atender."
        achados.append(Achado(nivel, f"{estudo}: tensões da viga", texto, (barra,)))
        enviado = next(
            (
                a
                for a in lidos
                if a.tipo == em.TIPO_VIGAS and a.estudo == arquivo.estudo and a.membros
            ),
            None,
        )
        caso = next((c for c in dados.casos.values() if c.estudo == arquivo.estudo), None)
        if enviado is not None:
            # As forças vieram junto: a leitura (perfil sugerido pelo esqueleto) sai delas.
            fonte = em.com_caso(
                em.EsforcosDoModelo(eixo_vertical=dados.eixo_vertical),
                em.caso_do_arquivo(enviado, arquivo.estudo or "?"),
            )
            forcas: Mapping[str, Sequence[em.PontoDeEsforco]] | None = enviado.membros
        else:
            fonte = dados
            forcas = caso.membros if caso is not None else None
        if forcas is None:
            achados.append(
                Achado(
                    em.NIVEL_INFO,
                    f"{estudo}: seção do Simulation",
                    "Envie também o “Listar forças da viga” do mesmo estudo: com as duas listas o "
                    "programa confere a seção que o Simulation usou em cada barra.",
                )
            )
            continue
        leituras = {lb.barra: lb for lb in ler_barras(fonte, geometria)}
        diferentes: list[str] = []
        barras_diferentes: list[str] = []
        conferidas = 0
        for nome, area in sorted(area_no_simulation(forcas, arquivo.tensoes_da_viga).items()):
            escolhido = dados.membros[nome].perfil if nome in dados.membros else ""
            sugerido = leituras[nome].perfil_sugerido if nome in leituras else ""
            perfil = escolhido or sugerido or em.perfil_do_nome(nome) or ""
            catalogo = lm._secao_do_catalogo(perfil) if perfil else None
            if catalogo is None:
                continue
            conferidas += 1
            if abs(area - catalogo[0]) / catalogo[0] > TOLERANCIA_SECAO_SIMULATION:
                barras_diferentes.append(nome)
                diferentes.append(
                    f"{nome} ({_n(area / 100, 1)} cm² no Simulation; {perfil}: "
                    f"{_n(catalogo[0] / 100, 1)} cm²)"
                )
        if diferentes:
            achados.append(
                Achado(
                    pc.NIVEL_ATENCAO,
                    f"{estudo}: seção do Simulation diferente do perfil",
                    f"{_lista(diferentes, 4)}: a área que o Simulation usou (força normal ÷ tensão "
                    "axial) não é a do perfil. Os esforços saíram da seção do modelo: acerte o "
                    "perfil no SolidWorks ou na tabela das barras, para os dois serem o mesmo.",
                    tuple(barras_diferentes),
                )
            )
        elif conferidas:
            achados.append(
                Achado(
                    pc.NIVEL_OK,
                    f"{estudo}: seção do Simulation confere",
                    f"Em {conferidas} barra(s), a área que o Simulation usou (força normal ÷ tensão "
                    "axial) é a do perfil.",
                )
            )
        achados.extend(
            _eixos_pelas_tensoes(estudo, forcas, arquivo.tensoes_da_viga, dados, leituras)
        )
    return sorted(achados, key=lambda a: ORDEM_DOS_NIVEIS.get(a.nivel, 9))


COLUNAS_LEITURA = (
    "Barra",
    "Tipo sugerido",
    "Por quê",
    "Perfil sugerido",
    "De onde",
    "Comprimento (m)",
    "Elementos",
    "Pontas",
    "Observação",
    "Lx / Ly / Lb (m)",
    "Comprimentos de flambagem",
    "Eixo forte",
)


def comprimentos_em_texto(lb: LeituraDaBarra) -> str:
    """ "3,09 / 3,09 / 3,09" (m) ou "—" sem sugestão."""
    if lb.lx_m is None and lb.ly_m is None and lb.lb_m is None:
        return "—"
    return " / ".join(
        "—" if v is None else f"{v:.2f}".replace(".", ",") for v in (lb.lx_m, lb.ly_m, lb.lb_m)
    )


def linhas_da_leitura(leituras: Sequence[LeituraDaBarra]) -> list[list[object]]:
    return [
        [
            lb.barra,
            lb.tipo_sugerido,
            lb.motivo_do_tipo,
            lb.perfil_sugerido or "—",
            lb.origem_do_perfil or "—",
            lb.comprimento_m,  # None (sem corpo) e não texto: a coluna é numérica
            lb.elementos,
            " / ".join(lb.pontas),
            "; ".join(lb.avisos),
            comprimentos_em_texto(lb),
            lb.motivo_dos_comprimentos,
            f"{lb.eixo_forte} ({lb.origem_do_eixo})",
        ]
        for lb in leituras
    ]
