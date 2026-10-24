"""Combinações de carga e envoltória de resultados de vigas e eixos."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from core.beam_model import CASO_PADRAO, Extremo, PontoDiagrama, ResultadoViga, Viga
from core.beam_solver import analisar_viga


@dataclass(frozen=True, slots=True)
class CombinacaoCarga:
    """Um conjunto de fatores por caso de carga.

    Um caso que **não** aparece em ``fatores`` entra com fator zero: a
    combinação declara o que participa dela, e omitir é o mesmo que dizer
    que aquela ação não age naquele cenário.
    """

    nome: str
    fatores: dict[str, float] = field(default_factory=dict)

    def fator(self, caso: str) -> float:
        """Fator do caso, comparando sem depender de maiúsculas.

        `Sobrecarga=1.5` e `caso=sobrecarga` são a mesma ação para quem
        escreve o modelo; fazer a comparação exata só produziria carga
        zerada em silêncio por causa de uma letra.
        """
        procurado = str(caso).strip().casefold()
        for nome, valor in self.fatores.items():
            if str(nome).strip().casefold() == procurado:
                return float(valor)
        return 0.0

    def casos(self) -> tuple[str, ...]:
        return tuple(self.fatores)


@dataclass(frozen=True, slots=True)
class PontoEnvoltoria:
    x_mm: float
    cortante_max_N: float
    cortante_min_N: float
    momento_max_Nmm: float
    momento_min_Nmm: float
    flecha_max_mm: float
    flecha_min_mm: float
    normal_max_N: float
    normal_min_N: float
    von_mises_max_MPa: float


@dataclass(frozen=True, slots=True)
class ResultadoEnvoltoria:
    viga: Viga
    combinacoes: tuple[CombinacaoCarga, ...]
    resultados: dict[str, ResultadoViga]
    pontos: tuple[PontoEnvoltoria, ...]
    governantes: dict[str, tuple[str, Extremo]]

    def governante(self, grandeza: str) -> tuple[str, Extremo]:
        return self.governantes[grandeza]


def casos_declarados(viga: Viga) -> tuple[str, ...]:
    """Casos de carga citados pelo modelo, na ordem em que aparecem."""
    vistos: list[str] = []
    grupos = (
        viga.cargas_pontuais,
        viga.momentos,
        viga.cargas_distribuidas,
        viga.cargas_axiais,
        viga.cargas_axiais_distribuidas,
        viga.torques,
    )
    for grupo in grupos:
        for carga in grupo:
            nome = str(getattr(carga, "caso", CASO_PADRAO) or CASO_PADRAO)
            if nome not in vistos:
                vistos.append(nome)
    if viga.considerar_peso_proprio and CASO_PADRAO not in vistos:
        vistos.append(CASO_PADRAO)
    return tuple(vistos)


def _escalar(carga: Any, fator: float, campos: tuple[str, ...]) -> Any:
    """Copia a carga multiplicando só as intensidades pelo fator.

    Aceita qualquer uma das dataclasses de carga. O tipo é ``Any`` porque
    ``dataclasses.replace`` não preserva o tipo concreto através de uma
    união para o verificador — e amarrar a assinatura a cada tipo exigiria
    seis sobrecargas para uma função de cinco linhas.
    """
    alteracoes: dict[str, float] = {}
    for campo in campos:
        valor = getattr(carga, campo)
        if valor is not None:
            alteracoes[campo] = valor * fator
    return replace(carga, **alteracoes)


def viga_da_combinacao(viga: Viga, combinacao: CombinacaoCarga) -> Viga:
    """Modelo com cada carga multiplicada pelo fator do seu caso.

    Geometria, apoios e rótulas não mudam: a malha sai idêntica em todas as
    combinações, o que é justamente o que torna a envoltória comparável
    ponto a ponto.
    """

    def fator_de(carga: Any) -> float:
        return combinacao.fator(str(getattr(carga, "caso", CASO_PADRAO) or CASO_PADRAO))

    peso = viga.considerar_peso_proprio
    fator_permanente = combinacao.fator(CASO_PADRAO)
    if peso and fator_permanente != 1.0:
        # O peso próprio é gerado como distribuída; para escaloná-lo sem
        # duplicar a fórmula, ele é materializado antes e escalado junto.
        viga = viga.com_peso_proprio()
        peso = False

    return Viga(
        comprimento_mm=viga.comprimento_mm,
        secao=viga.secao,
        material=viga.material,
        apoios=viga.apoios,
        rotulas=viga.rotulas,
        cargas_pontuais=tuple(
            _escalar(item, fator_de(item), ("fy_N",)) for item in viga.cargas_pontuais
        ),
        momentos=tuple(_escalar(item, fator_de(item), ("mz_Nmm",)) for item in viga.momentos),
        cargas_distribuidas=tuple(
            _escalar(item, fator_de(item), ("w_inicial_N_mm", "w_final_N_mm"))
            for item in viga.cargas_distribuidas
        ),
        cargas_axiais=tuple(
            _escalar(item, fator_de(item), ("fx_N",)) for item in viga.cargas_axiais
        ),
        cargas_axiais_distribuidas=tuple(
            _escalar(item, fator_de(item), ("a_inicial_N_mm", "a_final_N_mm"))
            for item in viga.cargas_axiais_distribuidas
        ),
        torques=tuple(_escalar(item, fator_de(item), ("t_Nmm",)) for item in viga.torques),
        considerar_peso_proprio=peso,
        considerar_segunda_ordem=viga.considerar_segunda_ordem,
        divisoes_por_trecho=viga.divisoes_por_trecho,
        nome=f"{viga.nome} — {combinacao.nome}",
    )


_GRANDEZAS_ENVOLTORIA = (
    ("cortante", "cortante_N"),
    ("momento", "momento_Nmm"),
    ("flecha", "deslocamento_mm"),
    ("normal", "normal_N"),
    ("von_mises", "von_mises_MPa"),
)


def _analisar_envoltoria(
    viga: Viga,
    combinacoes: Sequence[CombinacaoCarga],
    pontos_por_elemento: int,
    analisar: Callable[..., ResultadoViga],
) -> ResultadoEnvoltoria:
    lista = list(combinacoes)
    if not lista:
        raise ValueError("Informe pelo menos uma combinação de carga.")
    nomes = [combinacao.nome for combinacao in lista]
    if len(set(nomes)) != len(nomes):
        raise ValueError("Os nomes das combinações devem ser únicos.")

    # Um caso citado na combinação mas ausente do modelo é quase sempre erro
    # de digitação — e o efeito seria uma parcela simplesmente não entrar,
    # sem nenhum aviso.
    declarados = {nome.strip().casefold() for nome in casos_declarados(viga)}
    for combinacao in lista:
        desconhecidos = [
            nome for nome in combinacao.casos() if nome.strip().casefold() not in declarados
        ]
        if desconhecidos:
            disponiveis = ", ".join(casos_declarados(viga)) or "nenhum"
            raise ValueError(
                f"A combinação {combinacao.nome!r} cita casos que não existem no "
                f"modelo: {', '.join(desconhecidos)}. Casos declarados: {disponiveis}."
            )

    resultados: dict[str, ResultadoViga] = {}
    for combinacao in lista:
        try:
            resultados[combinacao.nome] = analisar(
                viga_da_combinacao(viga, combinacao),
                pontos_por_elemento=pontos_por_elemento,
            )
        except ValueError as erro:
            # Com segunda ordem, uma combinação pode passar da carga crítica
            # enquanto as outras resolvem; sem o nome, o erro não diz qual.
            raise ValueError(f"Combinação {combinacao.nome!r}: {erro}") from erro

    # A envoltória é montada sobre as abscissas comuns a todas as
    # combinações. Cada resultado ainda traz as raízes de V(x)=0 e θ(x)=0
    # da sua própria combinação, que naturalmente não coincidem — usar a
    # interseção evita comparar pontos que não existem em todas.
    conjuntos = [
        {round(ponto.x_mm, 9) for ponto in resultado.pontos} for resultado in resultados.values()
    ]
    comuns = sorted(set.intersection(*conjuntos))

    por_x: dict[float, list[PontoDiagrama]] = {chave: [] for chave in comuns}
    for resultado in resultados.values():
        for ponto in resultado.pontos:
            chave = round(ponto.x_mm, 9)
            if chave in por_x:
                por_x[chave].append(ponto)

    pontos: list[PontoEnvoltoria] = []
    for chave in comuns:
        grupo = por_x[chave]
        pontos.append(
            PontoEnvoltoria(
                x_mm=chave,
                cortante_max_N=max(p.cortante_N for p in grupo),
                cortante_min_N=min(p.cortante_N for p in grupo),
                momento_max_Nmm=max(p.momento_Nmm for p in grupo),
                momento_min_Nmm=min(p.momento_Nmm for p in grupo),
                flecha_max_mm=max(p.deslocamento_mm for p in grupo),
                flecha_min_mm=min(p.deslocamento_mm for p in grupo),
                normal_max_N=max(p.normal_N for p in grupo),
                normal_min_N=min(p.normal_N for p in grupo),
                von_mises_max_MPa=max(p.von_mises_MPa for p in grupo),
            )
        )

    # Os extremos governantes vêm dos resultados completos (com as raízes de
    # cada combinação), não da malha comum: assim o pico não é arredondado
    # para a amostra mais próxima.
    governantes: dict[str, tuple[str, Extremo]] = {}
    for grandeza, _ in _GRANDEZAS_ENVOLTORIA:
        melhor_nome = ""
        melhor_extremo: Extremo | None = None
        for nome, resultado in resultados.items():
            extremo = resultado.extremos[grandeza]
            if melhor_extremo is None or abs(extremo.valor) > abs(melhor_extremo.valor):
                melhor_nome, melhor_extremo = nome, extremo
        assert melhor_extremo is not None
        governantes[grandeza] = (melhor_nome, melhor_extremo)

    return ResultadoEnvoltoria(
        viga=viga,
        combinacoes=tuple(lista),
        resultados=resultados,
        pontos=tuple(pontos),
        governantes=governantes,
    )


def analisar_envoltoria(
    viga: Viga,
    combinacoes: Sequence[CombinacaoCarga],
    *,
    pontos_por_elemento: int = 61,
) -> ResultadoEnvoltoria:
    """Resolve a barra em cada combinação e monta a envoltória.

    O máximo de uma grandeza e o máximo de outra costumam vir de combinações
    diferentes; por isso a envoltória guarda, para cada extremo, **qual**
    combinação o governou — em vez de devolver um único número solto que
    ninguém sabe de onde veio.
    """
    return _analisar_envoltoria(viga, combinacoes, pontos_por_elemento, analisar_viga)


def tabela_envoltoria(envoltoria: ResultadoEnvoltoria) -> list[dict[str, float]]:
    """Envoltória em unidades de engenharia."""
    return [
        {
            "x (m)": ponto.x_mm / 1_000.0,
            "V máx (kN)": ponto.cortante_max_N / 1_000.0,
            "V mín (kN)": ponto.cortante_min_N / 1_000.0,
            "M máx (kN·m)": ponto.momento_max_Nmm / 1e6,
            "M mín (kN·m)": ponto.momento_min_Nmm / 1e6,
            "Flecha máx (mm)": ponto.flecha_max_mm,
            "Flecha mín (mm)": ponto.flecha_min_mm,
            "N máx (kN)": ponto.normal_max_N / 1_000.0,
            "N mín (kN)": ponto.normal_min_N / 1_000.0,
            "von Mises máx (MPa)": ponto.von_mises_max_MPa,
        }
        for ponto in envoltoria.pontos
    ]


def resumo_governantes(envoltoria: ResultadoEnvoltoria) -> list[dict[str, object]]:
    """Qual combinação governa cada grandeza, e onde."""
    conversao = {
        "cortante": (1 / 1_000.0, "kN"),
        "momento": (1 / 1e6, "kN·m"),
        "flecha": (1.0, "mm"),
        "normal": (1 / 1_000.0, "kN"),
        "von_mises": (1.0, "MPa"),
    }
    rotulos = {
        "cortante": "Cortante V",
        "momento": "Momento fletor M",
        "flecha": "Flecha",
        "normal": "Esforço normal N",
        "von_mises": "Tensão de von Mises",
    }
    linhas = []
    for grandeza, _ in _GRANDEZAS_ENVOLTORIA:
        nome, extremo = envoltoria.governantes[grandeza]
        escala, unidade = conversao[grandeza]
        linhas.append(
            {
                "Grandeza": rotulos[grandeza],
                "Combinação governante": nome,
                "Valor": extremo.valor * escala,
                "Unidade": unidade,
                "x (m)": extremo.x_mm / 1_000.0,
            }
        )
    return linhas
