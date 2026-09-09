"""Regras puras do assistente de projeto."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RotaProjeto:
    chave: str
    titulo: str
    pagina: str
    icone: str
    entrada: str
    saida: str


ROTAS: dict[str, RotaProjeto] = {
    "cargas": RotaProjeto(
        "cargas",
        "Assistente de cargas",
        "app_pages/assistente_cargas.py",
        ":material/manufacturing:",
        "forças, momentos, torque, pressão e geometria",
        "componentes de tensão em MPa",
    ),
    "estatica": RotaProjeto(
        "estatica",
        "Análise estática",
        "app_pages/analise_estatica.py",
        ":material/analytics:",
        "σx, σy, τxy e propriedades resistentes",
        "von Mises, tensões principais e fatores de segurança",
    ),
    "mohr": RotaProjeto(
        "mohr",
        "Círculo de Mohr",
        "app_pages/circulo_mohr.py",
        ":material/donut_large:",
        "estado de tensão 2D ou tensor 3D",
        "planos principais, cisalhamento máximo e transformações",
    ),
    "fadiga": RotaProjeto(
        "fadiga",
        "Análise de fadiga",
        "app_pages/analise_fadiga.py",
        ":material/cycle:",
        "tensões máxima e mínima, material, acabamento e geometria",
        "Goodman, Soderberg, limite corrigido e vida estimada",
    ),
    "parafusos": RotaProjeto(
        "parafusos",
        "Projeto de parafusos",
        "app_pages/projeto_parafusos.py",
        ":material/build:",
        "padrão da junta, parafusos, cargas e propriedades da chapa",
        "pré-carga, torque, separação, deslizamento e resistências",
    ),
    "aco": RotaProjeto(
        "aco",
        "Estruturas de aço",
        "app_pages/estruturas_aco.py",
        ":material/domain:",
        "geometria, apoios, ações, combinações e material",
        "esforços, deslocamentos, utilização de barras e ligações",
    ),
    "casos_carga": RotaProjeto(
        "casos_carga",
        "Casos e combinações de carga",
        "app_pages/casos_carga.py",
        ":material/layers:",
        "cenários operacionais e fatores de cada caso",
        "vetor de esforços governante por componente",
    ),
    "analise_sensibilidade": RotaProjeto(
        "analise_sensibilidade",
        "Análise de sensibilidade",
        "app_pages/analise_sensibilidade.py",
        ":material/tune:",
        "um cálculo já registrado no projeto e a incerteza de cada entrada",
        "ranking de influência e risco de não atendimento",
    ),
}


OBJETIVOS = [
    "Transformar cargas e geometria em tensões",
    "Verificar resistência estática",
    "Transformar o estado de tensões e encontrar planos críticos",
    "Verificar fadiga e estimar vida",
    "Dimensionar ou conferir uma junta parafusada",
    "Verificar uma estrutura de aço",
    "Ainda não sei qual análise usar",
]


DADOS_DISPONIVEIS = [
    "Forças, momentos, torque ou pressão e dimensões",
    "Componentes de tensão em um ponto",
    "Tensões máxima e mínima de um ciclo",
    "Desenho e cargas de uma junta parafusada",
    "Geometria, apoios e ações de uma estrutura",
    "Somente uma ideia inicial do problema",
]


COMPONENTES = [
    "Peça, barra, eixo ou viga",
    "Ponto com tensões conhecidas",
    "Componente sob carga variável",
    "Junta parafusada",
    "Estrutura de aço",
    "Outro ou ainda não definido",
]


_ROTA_POR_OBJETIVO = {
    OBJETIVOS[0]: "cargas",
    OBJETIVOS[1]: "estatica",
    OBJETIVOS[2]: "mohr",
    OBJETIVOS[3]: "fadiga",
    OBJETIVOS[4]: "parafusos",
    OBJETIVOS[5]: "aco",
}

_ROTA_POR_DADOS = {
    DADOS_DISPONIVEIS[0]: "cargas",
    DADOS_DISPONIVEIS[1]: "estatica",
    DADOS_DISPONIVEIS[2]: "fadiga",
    DADOS_DISPONIVEIS[3]: "parafusos",
    DADOS_DISPONIVEIS[4]: "aco",
    DADOS_DISPONIVEIS[5]: "cargas",
}

_ROTA_POR_COMPONENTE = {
    COMPONENTES[0]: "cargas",
    COMPONENTES[1]: "estatica",
    COMPONENTES[2]: "fadiga",
    COMPONENTES[3]: "parafusos",
    COMPONENTES[4]: "aco",
    COMPONENTES[5]: "cargas",
}


def recomendar_rota(
    objetivo: str,
    dados_disponiveis: str,
    componente: str | None = None,
) -> RotaProjeto:
    """Retorna o primeiro módulo útil para o estado atual do projeto."""
    if objetivo not in OBJETIVOS:
        raise ValueError("Objetivo de projeto desconhecido.")
    if dados_disponiveis not in DADOS_DISPONIVEIS:
        raise ValueError("Tipo de dado disponível desconhecido.")

    if (
        dados_disponiveis == DADOS_DISPONIVEIS[0]
        and objetivo in {OBJETIVOS[1], OBJETIVOS[2], OBJETIVOS[3]}
    ):
        return ROTAS["cargas"]

    if objetivo == OBJETIVOS[6]:
        if componente is not None and componente not in COMPONENTES:
            raise ValueError("Tipo de componente desconhecido.")
        if dados_disponiveis == DADOS_DISPONIVEIS[5] and componente:
            return ROTAS[_ROTA_POR_COMPONENTE[componente]]
        return ROTAS[_ROTA_POR_DADOS[dados_disponiveis]]

    return ROTAS[_ROTA_POR_OBJETIVO[objetivo]]


def sequencia_recomendada(
    objetivo: str,
    dados_disponiveis: str,
    componente: str | None = None,
) -> list[str]:
    """Lista o fluxo completo sugerido, do primeiro passo ao acompanhamento.

    O roteiro sempre começa por "Casos e combinações de carga" (quando o
    primeiro passo calculado não é ele mesmo) e termina por "Análise de
    sensibilidade" (quando o último não é ela mesma). Essas duas pontas são
    sugestões de trabalho, não módulos que o assistente pré-preenche.
    """
    primeira = recomendar_rota(objetivo, dados_disponiveis, componente).chave
    destino = _ROTA_POR_OBJETIVO.get(objetivo, primeira)
    nucleo = [primeira] if primeira == destino else [primeira, destino]
    sequencia = list(nucleo)
    if sequencia[0] != "casos_carga":
        sequencia.insert(0, "casos_carga")
    if sequencia[-1] != "analise_sensibilidade":
        sequencia.append("analise_sensibilidade")
    return sequencia


def calcular_tensoes_ciclo(
    tensao_minima_mpa: float, tensao_maxima_mpa: float
) -> tuple[float, float]:
    """Retorna tensão média e alternada a partir dos extremos do ciclo."""
    if tensao_maxima_mpa < tensao_minima_mpa:
        raise ValueError("A tensão máxima deve ser maior ou igual à mínima.")
    media = (tensao_maxima_mpa + tensao_minima_mpa) / 2.0
    alternada = (tensao_maxima_mpa - tensao_minima_mpa) / 2.0
    return media, alternada
