"""O que conferir e corrigir antes de verificar: o painel do início da página Esforços do modelo.

Junta as conferências espalhadas pela página (plano × reações, forças × reações, apoios × reações,
rodadas diferentes, cargas da grade que sobraram no plano, ventos com nomes trocados) e diz, para
cada problema, **em linguagem simples**: o que está errado, por que importa e o passo a passo para
corrigir — no SolidWorks, no envio dos arquivos ou no próprio programa (alguns se corrigem com um
botão: ``Achado.acao``).

Sem Streamlit.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from core import apoios_do_modelo as am
from core import cargas_pelo_modelo as cpm
from core import esforcos_modelo as em
from core import plano_de_cargas as pc
from core import quadro_fundacoes as qf

NIVEL_ERRO = pc.NIVEL_ERRO  # o resultado está errado: corrigir antes de usar
NIVEL_ATENCAO = pc.NIVEL_ATENCAO  # pode estar errado: conferir
NIVEL_INFO = em.NIVEL_INFO  # falta algo, mas o resto vale

ACAO_TROCAR_NOMES = "trocar_nomes"
ACAO_TIRAR_GRADE = "tirar_grade"

#: Passos que se repetem.
LISTAR_FORCAS = (
    "No SolidWorks, abra o gerenciador de casos de carga › Vista de resultados.",
    "Dê duplo clique no caso {caso} (o gráfico tem de mudar para ele).",
    "Resultados › Listar forças da viga (todas as vigas) › Salvar, com o nome {caso}-forcas.csv.",
    "Envie o arquivo no passo 1 desta página e clique em Gravar no projeto.",
)


@dataclass(frozen=True)
class Achado:
    nivel: str
    titulo: str
    problema: str
    passos: tuple[str, ...] = ()
    acao: str = ""  # ACAO_TROCAR_NOMES, ACAO_TIRAR_GRADE ou vazio
    detalhe: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Diagnostico:
    achados: tuple[Achado, ...]
    certos: tuple[str, ...]  # o que conferiu, em frases curtas

    @property
    def erros(self) -> int:
        return sum(a.nivel == NIVEL_ERRO for a in self.achados)

    @property
    def atencoes(self) -> int:
        return sum(a.nivel == NIVEL_ATENCAO for a in self.achados)

    @property
    def tudo_certo(self) -> bool:
        return not any(a.nivel in (NIVEL_ERRO, NIVEL_ATENCAO) for a in self.achados)


def _n(valor: float, casas: int = 2) -> str:
    if round(valor, casas) == 0:
        valor = 0.0
    return f"{valor:.{casas}f}".replace(".", ",")


def _lista(itens: Sequence[str]) -> str:
    itens = list(itens)
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


# ---------------------------------------------------------------------------------------------
# Conferências
# ---------------------------------------------------------------------------------------------
def _assinatura(caso: em.CasoImportado) -> frozenset[tuple[str, str]]:
    return frozenset(
        (membro, p.elemento) for membro, pontos in caso.membros.items() for p in pontos
    )


def _rodadas(dados: em.EsforcosDoModelo) -> list[Achado]:
    """Casos cujas forças são de outra malha (outra rodada do estudo) que a dos outros."""
    assinaturas = {c: _assinatura(caso) for c, caso in dados.casos.items() if caso.membros}
    if len(assinaturas) < 3:
        return []
    contagem = Counter(assinaturas.values())
    maioria, vezes = contagem.most_common(1)[0]
    if vezes < 2 or vezes == len(assinaturas):
        return []
    fora = [c for c, a in assinaturas.items() if a != maioria]
    if len(fora) > len(assinaturas) / 2:
        return []
    passos = tuple(
        p.format(caso=fora[0] if len(fora) == 1 else "de cada um") for p in LISTAR_FORCAS
    )
    return [
        Achado(
            NIVEL_ATENCAO,
            f"Forças de outra rodada: {_lista(fora)}",
            f"O arquivo de forças de {_lista(fora)} tem outra numeração dos elementos que os "
            "outros casos — é de uma rodada anterior do estudo (antes de refazer a malha ou de "
            "Executar de novo). As combinações juntam os casos elemento a elemento: com malhas "
            "diferentes, o programa combina pela ordem dos elementos, o que é só aproximado.",
            passos,
            detalhe={"casos": fora},
        )
    ]


def _forcas_e_reacoes(dados: em.EsforcosDoModelo) -> list[Achado]:
    """O arquivo de forças é do mesmo resultado que o de reações? (soma das bases dos pilares)"""
    quadro = qf.montar_quadro(dados)
    if not quadro.pilares or quadro.pendentes:
        return []
    achados = []
    verticais = {
        c: em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)[2]
        for c, caso in dados.casos.items()
        if caso.reacoes is not None
    }
    soma_total = sum(verticais.values())  # o estudo base liga todas as cargas juntas
    for codigo, vertical in verticais.items():
        soma = sum(c.n for p in quadro.pilares for c in p.cargas if c.caso == codigo)
        if abs(soma - vertical) <= max(0.02 * abs(vertical), 0.1):
            continue
        estudo_base = abs(soma - soma_total) <= max(0.02 * abs(soma_total), 0.1)
        achados.append(
            Achado(
                NIVEL_ERRO,
                f"{codigo}: as forças não são do caso {codigo}",
                f"Os pilares do arquivo de forças de {codigo} levam {_n(soma)} kN à fundação, mas a "
                f"reação de {codigo} é {_n(vertical)} kN."
                + (
                    " Esse valor é a soma de todos os casos: o arquivo foi salvo com o estudo "
                    "base (todas as cargas ligadas), não com o caso carregado."
                    if estudo_base
                    else " O arquivo de forças e o de reações não são do mesmo resultado."
                ),
                tuple(p.format(caso=codigo) for p in LISTAR_FORCAS),
                detalhe={"caso": codigo, "soma": soma, "reacao": vertical},
            )
        )
    return achados


def _lado_a_lado(texto: str) -> str:
    """O trecho "no seu estudo … No programa …" do resumo dos ventos, sem a conclusão."""
    texto = texto.replace("Ventos — no seu estudo", "No seu estudo")
    for corte in (" Cada caso do estudo", " Não dá para"):
        texto = texto.split(corte)[0]
    return texto.strip()


def _linha_que_explica(dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas, codigo: str) -> str:
    """Se a diferença entre o plano e o modelo é uma linha do plano (um guarda-corpo de uma borda,
    uma carga de uma viga), diz qual — a pista mais provável do que faltou ou sobrou."""
    acao = plano.acao(codigo)
    caso = dados.casos.get(codigo)
    if acao is None or caso is None or caso.reacoes is None:
        return ""
    esperado = em.total_esperado(acao)
    if esperado is None:
        return ""
    recebido = em.para_o_plano(caso.reacoes.modelo, dados.eixo_vertical)[2]
    diferenca = abs(esperado[2]) - abs(recebido)
    if abs(diferenca) < 0.05:
        return ""
    candidatas = [
        c
        for c in acao.cargas
        if c.resultante and abs(abs(c.resultante) - abs(diferenca)) <= 0.03 * abs(diferenca)
    ]
    if not candidatas or len(candidatas) > 4:
        return ""
    lado = "a mais no plano" if diferenca > 0 else "faltando no plano"
    if len(candidatas) == 1:
        c = candidatas[0]
        return (
            f"A diferença ({_n(abs(diferenca))} kN, {lado}) é exatamente a linha “{c.elemento}” "
            f"({c.observacao or _n(abs(c.resultante or 0.0)) + ' kN'}): confira essa carga no plano "
            "e no modelo."
        )
    nomes = _lista([f"“{c.elemento}”" for c in candidatas])
    return (
        f"A diferença ({_n(abs(diferenca))} kN, {lado}) é o valor de uma destas linhas do plano: "
        f"{nomes} — por exemplo um guarda-corpo numa borda que no modelo não tem (o acesso)."
    )


def _plano_e_reacoes(dados: em.EsforcosDoModelo, plano: pc.PlanoDeCargas) -> list[Achado]:
    achados: list[Achado] = []
    da_grade = cpm.cargas_da_grade_no_plano(plano)
    casos_da_grade = sorted({c for c, _ in da_grade})
    if da_grade:
        total = sum(abs(c.resultante or 0.0) for _, c in da_grade)
        achados.append(
            Achado(
                NIVEL_ERRO,
                f"Plano de cargas com cargas de exemplo em {_lista(casos_da_grade)}",
                f"O plano ainda tem {len(da_grade)} linha(s) da grade de eixos da página Cargas do "
                f'esqueleto ({_n(total)} kN em barras "N1 · eixo A…" que o seu modelo não tem). '
                "Elas fazem o plano somar muito mais que o modelo recebeu, e a conferência não fecha.",
                (
                    "Clique no botão abaixo: as linhas da grade saem do plano e o resto fica.",
                    "Se ainda faltar carga, mande o piso e o guarda-corpo pela página Cargas do "
                    "esqueleto › Cargas do piso pelo esqueleto (as chapas do seu modelo).",
                ),
                acao=ACAO_TIRAR_GRADE,
                detalhe={"casos": casos_da_grade},
            )
        )
    ventos = em.resumo_dos_ventos(dados, plano)
    if ventos is not None:
        mapa = em.mapa_de_nomes_dos_ventos(dados, plano)
        if mapa:
            trocas = _lista([f"{a} → {b}" for a, b in mapa.items()])
            achados.append(
                Achado(
                    NIVEL_ERRO,
                    "Ventos com os nomes trocados",
                    f"As forças de vento do seu estudo estão certas, mas com o nome de outro caso: "
                    f"{trocas}. {_lado_a_lado(ventos.texto)}",
                    (
                        "Opção 1 (no programa, agora): clique no botão abaixo — os casos importados "
                        "trocam de nome e passam a bater com o plano.",
                        "Opção 2 (no SolidWorks, para as próximas vezes): renomeie os casos no "
                        "gerenciador. Na vista Superior: W0 vem da esquerda (+X), W180 da direita "
                        "(−X), W90 de baixo para cima (−Z) e W270 de cima para baixo (+Z).",
                    ),
                    acao=ACAO_TROCAR_NOMES,
                    detalhe={"mapa": dict(mapa)},
                )
            )
        else:
            achados.append(
                Achado(
                    NIVEL_ERRO,
                    "Ventos em direção diferente da do plano",
                    _lado_a_lado(ventos.texto)
                    + " Há caso com a direção de um vento e o valor de outro (o valor do vento "
                    "muda com a direção, porque ele vê outra face): só renomear não resolve.",
                    (
                        "Na vista Superior do SolidWorks (X para a direita, Z para baixo): W0 vem da "
                        "esquerda (+X), W180 da direita (−X), W90 de baixo para cima (−Z) e W270 de "
                        "cima para baixo (+Z).",
                        "Vento em X: o valor do W0 e do W180; vento em Z: o do W90 e do W270.",
                        "Acerte a força de cada caso (face, direção e valor), clique em Executar no "
                        "gerenciador, rode a macro e envie os arquivos de novo.",
                    ),
                )
            )
    nomes_de_vento = set(pc.CODIGOS_DE_VENTO)
    for item in em.conferir_reacoes(dados, plano, peso_conferido_no_esqueleto=True):
        codigo = item.texto.split(":", 1)[0]
        if item.nivel == pc.NIVEL_ERRO:
            achados.append(
                Achado(
                    NIVEL_ERRO,
                    f"{codigo}: problema no estudo",
                    item.texto.split(":", 1)[1].strip() if ":" in item.texto else item.texto,
                    ("Corrija no SolidWorks, rode de novo e envie os arquivos.",),
                )
            )
        elif (
            item.nivel == pc.NIVEL_ATENCAO
            and "Falta ou sobra carga" in item.texto
            and codigo not in nomes_de_vento
            and codigo not in casos_da_grade
        ):
            pista = _linha_que_explica(dados, plano, codigo)
            achados.append(
                Achado(
                    NIVEL_ATENCAO,
                    f"{codigo}: o modelo não recebeu a carga do plano",
                    item.texto.split(":", 1)[1].strip() + (f" {pista}" if pista else ""),
                    (
                        f"Compare a carga {codigo} do SolidWorks com a do plano (página Plano de "
                        "cargas): valor, área ou comprimento carregado e “Por item” × “Total”.",
                        "Se o plano estiver errado, refaça a ação na página que a gerou (o "
                        "guarda-corpo de cada borda se marca em Cargas do esqueleto › Guarda-corpo "
                        "nas bordas do piso); se for o modelo, corrija, rode e envie os arquivos.",
                    ),
                )
            )
        elif item.nivel == pc.NIVEL_ATENCAO and "falta o arquivo de reações" in item.texto:
            achados.append(
                Achado(
                    NIVEL_ATENCAO,
                    f"{codigo}: falta o arquivo de reações",
                    "Sem a reação do caso, o programa não confere se o modelo recebeu a carga.",
                    (
                        "Rode a macro exportar_casos_de_carga (grava o -reacoes.csv de cada caso) ou, "
                        f"com o caso {codigo} carregado, Listar forças resultantes › Salvar.",
                        "Envie o arquivo no passo 1.",
                    ),
                )
            )
    faltam = [c for c in plano.codigos if c not in dados.casos]
    if dados.casos and faltam:
        achados.append(
            Achado(
                NIVEL_INFO,
                f"Casos do plano sem resultado do modelo: {_lista(faltam)}",
                "As combinações saem só com os casos importados: esses ficam de fora da "
                "verificação.",
                (
                    "Crie esses casos no gerenciador do SolidWorks, Execute e envie os arquivos; "
                    "ou, se não se aplicam (por exemplo a temperatura), tire-os do plano na página "
                    "que os gerou.",
                ),
            )
        )
    return achados


def _apoios(dados: em.EsforcosDoModelo, apoios: am.ApoiosDoModelo) -> list[Achado]:
    if not apoios.casos:
        return []
    achados: list[Achado] = []
    outra_rodada = []
    for codigo, c in apoios.casos.items():
        caso = dados.casos.get(codigo)
        if caso is None or caso.reacoes is None:
            continue
        soma = [sum(n.forca_N[k] for n in c.nos) / 1e3 for k in range(3)]
        modelo = list(caso.reacoes.modelo)
        escala = max(max(abs(v) for v in modelo), 1e-9)
        if max(abs(a - b) for a, b in zip(soma, modelo, strict=True)) > max(0.02 * escala, 0.01):
            outra_rodada.append(codigo)
    sem_posicao = []
    for codigo, c in apoios.casos.items():
        pontos = [n.ponto for n in c.nos if n.ponto is not None]
        distintos = {tuple(round(v, 6) for v in p) for p in pontos}
        if len(pontos) > 1 and len(distintos) < len(pontos):
            sem_posicao.append(codigo)
    if outra_rodada or sem_posicao:
        partes = []
        if outra_rodada:
            partes.append(
                f"a reação nos apoios de {_lista(outra_rodada)} não bate com a reação total do "
                "mesmo caso: os -apoios.csv são de outra rodada"
            )
        if sem_posicao:
            partes.append(
                f"{_lista(sem_posicao)} vieram sem a posição dos nós (a macro v12 gravava 0, 0, 0)"
            )
        achados.append(
            Achado(
                NIVEL_ATENCAO,
                "Reação em cada apoio: arquivos antigos",
                "No quadro por apoio, " + "; ".join(partes) + ".",
                (
                    "Na pasta da peça, os -apoios.csv da última rodada têm a mesma hora dos "
                    "-reacoes.csv (a macro grava os dois juntos).",
                    "Envie todos os -apoios.csv e -reacoes.csv dessa rodada juntos no passo 1 e "
                    "clique em Gravar no projeto.",
                ),
                detalhe={"outra_rodada": outra_rodada, "sem_posicao": sem_posicao},
            )
        )
    return achados


def diagnosticar(
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    apoios: am.ApoiosDoModelo | None = None,
) -> Diagnostico:
    """Tudo o que conferir e corrigir, do mais grave ao menos, e o que já confere."""
    if not dados.casos:
        return Diagnostico((), ())
    achados = [
        *_forcas_e_reacoes(dados),
        *_plano_e_reacoes(dados, plano),
        *_rodadas(dados),
        *_apoios(dados, apoios or am.ApoiosDoModelo()),
    ]
    ordem = {NIVEL_ERRO: 0, NIVEL_ATENCAO: 1, NIVEL_INFO: 2}
    achados.sort(key=lambda a: ordem.get(a.nivel, 3))
    certos = []
    equilibrados = [
        i.texto.split(":", 1)[0]
        for i in em.conferir_reacoes(dados, plano, peso_conferido_no_esqueleto=True)
        if i.nivel == pc.NIVEL_OK and "equilibram" in i.texto
    ]
    if equilibrados:
        certos.append(f"O modelo recebeu a carga do plano em {_lista(equilibrados)}.")
    com_problema_de_forca = {a.detalhe.get("caso") for a in achados if "caso" in a.detalhe}
    if not any(a.titulo.startswith("Forças de outra rodada") for a in achados):
        certos.append("Os arquivos de forças são todos da mesma rodada (mesma malha).")
    bons = [c for c in dados.casos if c not in com_problema_de_forca]
    if bons and not com_problema_de_forca:
        certos.append("As forças de cada caso batem com a reação do mesmo caso.")
    return Diagnostico(tuple(achados), tuple(certos))


# ---------------------------------------------------------------------------------------------
# Correções pelo programa
# ---------------------------------------------------------------------------------------------
def corrigir_nomes(
    dados: em.EsforcosDoModelo, apoios: am.ApoiosDoModelo, mapa: Mapping[str, str]
) -> tuple[em.EsforcosDoModelo, am.ApoiosDoModelo]:
    """Os casos importados (forças, reações e apoios) com os nomes trocados pelo ``mapa``."""
    return em.trocar_codigos(dados, mapa), am.trocar_codigos(apoios, mapa)


def tirar_grade(plano: pc.PlanoDeCargas) -> pc.PlanoDeCargas:
    return cpm.sem_cargas_da_grade(plano)
