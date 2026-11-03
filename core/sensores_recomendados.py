"""Os sensores que cada estudo do SolidWorks Simulation precisa ter para o memorial: o mínimo, o
recomendado e, das opções do SolidWorks, as que não precisa criar.

É a lista que a página Sensores do modelo mostra e que ``sensores_do_modelo.conferir_minimo``
confere contra o quadro do estudo estático (o único que passa pelo gerenciador de casos de carga;
flambagem e frequência são estudos à parte). Os nomes sugeridos são os que o programa reconhece
sozinho; ``grandeza`` é a do ``sensores_do_modelo`` que atende o item.

Sem Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import criterio_anglo as ca
from core import structural_2d as s2

MINIMO = "Mínimo"
RECOMENDADO = "Recomendado"
SE_HOUVER = "Se houver"
NAO_PRECISA = "Não precisa"
E_ESTE = "É este"
NIVEIS = (MINIMO, RECOMENDADO, SE_HOUVER, NAO_PRECISA, E_ESTE)

ESTATICO = "Estudo estático"
FLAMBAGEM = "Estudo de flambagem"
FREQUENCIA = "Estudo de frequência"
ESTUDOS = (ESTATICO, FLAMBAGEM, FREQUENCIA)

DADOS_DO_SIMULATION = "Dados do Simulation"

# As grandezas de ``sensores_do_modelo`` (aqui como texto, para este módulo não depender dele).
TENSAO = "tensão"
DESLOCAMENTO = "deslocamento"
FATOR_DE_SEGURANCA = "fator de segurança"
FORCA = "força"
MASSA = "massa"
FATOR_DE_FLAMBAGEM = "fator de flambagem"
FREQUENCIA_HZ = "frequência"

#: Pedaços do nome (sem acento, minúsculo) que dizem a direção de um deslocamento.
PISTAS_HORIZONTAL = ("horiz", "lateral", "topo", "pilar", "coluna", "sway", "drift")
PISTAS_VERTICAL = ("vert", "flecha", "vao", "viga", "deflex", "deflect")
#: … e que dizem que a tensão é das chapas (casca ou sólido), não das barras.
PISTAS_CHAPA = ("chapa", "mises", "casca", "solido", "shell", "solid")
#: … e que a força é a de um conector (parafuso, pino).
PISTAS_CONECTOR = ("conector", "connector", "parafuso", "bolt", "pino", "pin")

#: α_cr do modo de deslocamento lateral que dá Δ₂/Δ₁ = 1,10 e 1,40 (B₂ ≈ 1/(1 − 1/α_cr)).
ALFA_PEQUENA_DESLOCABILIDADE = 1.0 / (1.0 - 1.0 / s2.LIMITE_PEQUENA_DESLOCABILIDADE)
ALFA_MEDIA_DESLOCABILIDADE = 1.0 / (1.0 - 1.0 / s2.LIMITE_MEDIA_DESLOCABILIDADE)
#: Frequência natural mínima do piso (ABNT NBR 8800:2008, Anexo L).
FREQUENCIA_MINIMA_HZ = 3.0  # L.1.2: em nenhum caso
FREQUENCIA_MINIMA_CAMINHAR_HZ = 4.0  # L.3.2: pessoas caminhando regularmente
REFERENCIA_FREQUENCIA = "ABNT NBR 8800:2008, Anexo L (L.1.2 e L.3.2)"


def _n(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _g(valor: float) -> str:
    """Sem os zeros do fim: 11, 3,5, 0,575."""
    return f"{valor:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def texto_da_deslocabilidade() -> str:
    """α_cr ≥ 11: pequena; 3,5 a 11: média; abaixo de 3,5: grande (pelos limites da norma)."""
    return (
        f"α_cr ≥ {_g(ALFA_PEQUENA_DESLOCABILIDADE)} → pequena deslocabilidade (Δ₂/Δ₁ ≤ "
        f"{_n(s2.LIMITE_PEQUENA_DESLOCABILIDADE)}); de {_g(ALFA_MEDIA_DESLOCABILIDADE)} a "
        f"{_g(ALFA_PEQUENA_DESLOCABILIDADE)} → média (≤ {_n(s2.LIMITE_MEDIA_DESLOCABILIDADE)}); "
        f"abaixo de {_g(ALFA_MEDIA_DESLOCABILIDADE)} → grande (ABNT NBR 8800:2025, 4.10.4)"
    )


def texto_do_equipamento() -> str:
    """As faixas de Ne/Nm do critério Anglo (5.7)."""
    p, a = ca.FAIXA_PREFERENCIAL, ca.FAIXA_ALTERNATIVA
    return (
        f"Ne/Nm entre {_g(p[0])} e {_g(p[1])} (preferencial), entre {_g(a[0])} e {_g(a[1])} "
        f"(alternativa) ou abaixo de {_g(ca.LIMITE_INFERIOR)}, e nunca múltiplo inteiro "
        "(critério Anglo, 5.7)"
    )


@dataclass(frozen=True)
class SensorRecomendado:
    chave: str
    estudo: str
    nivel: str
    titulo: str  # o que o item verifica ("Flecha das vigas")
    nome: str  # o nome a dar no SolidWorks (o programa reconhece)
    quantidade: str  # Dados do Simulation › Quantidade de dados
    componente: str
    criterio: str
    onde: str
    unidade: str
    alerta: str  # o valor para ligar o Alerta do sensor no SolidWorks
    para_que: str
    condicao: str = ""  # "" = em todo modelo; senão "se o modelo tem pilares"…
    grandeza: str = ""

    @property
    def caminho(self) -> str:
        partes = [DADOS_DO_SIMULATION, self.quantidade]
        if self.componente:
            partes.append(self.componente)
        return " › ".join(partes)

    @property
    def obrigatorio(self) -> bool:
        """Mínimo em todo modelo: a falta dele deixa uma verificação de fora."""
        return self.nivel == MINIMO and not self.condicao


RECOMENDADOS: tuple[SensorRecomendado, ...] = (
    # ------------------------------------------------------------------ estudo estático
    SensorRecomendado(
        "tensao_barras",
        ESTATICO,
        MINIMO,
        "Tensão nas barras",
        "Tensão barras",
        "Tensão da viga",
        "Limite superior de axial e flexão",
        "Máximo do modelo",
        "o modelo inteiro (todas as barras)",
        "N/mm² (MPa)",
        "maior que f_y/1,10 (227 MPa no A36; 314 MPa no A572 Gr 50)",
        "Escoamento nas combinações últimas (ELU): σ ≤ f_y/γ_a1 (ABNT NBR 8800:2025).",
        grandeza=TENSAO,
    ),
    SensorRecomendado(
        "fator_de_seguranca",
        ESTATICO,
        MINIMO,
        "Fator de segurança",
        "Fator de segurança",
        "Fator de segurança",
        "",
        "Mínimo do modelo",
        "o modelo inteiro",
        "—",
        "menor que 1,10",
        "Confere o escoamento ponto a ponto, cada barra com o seu aço, e mostra o f_y pelo σ·FS — "
        "é o que confirma a unidade da tensão.",
        grandeza=FATOR_DE_SEGURANCA,
    ),
    SensorRecomendado(
        "flecha_vigas",
        ESTATICO,
        MINIMO,
        "Flecha das vigas",
        "Flecha vigas",
        "Deslocamento",
        "UY (o eixo vertical do modelo)",
        "Mínimo sobre entidades selecionadas (com Y para cima, a flecha sai negativa)",
        "as vigas de piso (selecione as vigas)",
        "mm",
        "menor que −L/350 do maior vão (−17,1 mm com L = 6 m)",
        "Flecha nas combinações de serviço (ELS) contra L/350 (vigas principais) ou L/300 "
        "(secundárias), critério Anglo, Tabela 3. Com o máximo do UY sai o maior deslocamento "
        "para cima, não a flecha.",
        grandeza=DESLOCAMENTO,
    ),
    SensorRecomendado(
        "deslocamento_topo",
        ESTATICO,
        MINIMO,
        "Deslocamento horizontal do topo dos pilares",
        "Deslocamento topo pilares",
        "Deslocamento",
        "URES (resultante)",
        "Máximo sobre entidades selecionadas",
        "os vértices do topo dos pilares (o nível mais alto)",
        "mm",
        "maior que H/400 (15 mm com H = 6 m)",
        "Deslocamento lateral nas ELS contra H/400 (colunas ao nível das plataformas, com "
        "vento), critério Anglo, Tabela 4. A resultante soma o encurtamento do pilar, que é "
        "pequeno: fica a favor da segurança.",
        condicao="se o modelo tem pilares",
        grandeza=DESLOCAMENTO,
    ),
    SensorRecomendado(
        "tensao_chapas",
        ESTATICO,
        MINIMO,
        "Tensão nas chapas",
        "Tensão chapas",
        "Tensão",
        "VON: tensão de von Mises",
        "Máximo sobre entidades selecionadas",
        "os corpos de casca ou sólido (chapa de piso, chapas de ligação)",
        "N/mm² (MPa)",
        "maior que f_y/1,10",
        "Escoamento das chapas nas ELU. Um pico num canto vivo ou num ponto de apoio é efeito da "
        "malha: confira antes de aceitar.",
        condicao="se o modelo tem chapas em casca ou sólido",
        grandeza=TENSAO,
    ),
    SensorRecomendado(
        "tensao_por_grupo",
        ESTATICO,
        RECOMENDADO,
        "Tensão por grupo de barras",
        "Tensão vigas, Tensão pilares, Tensão contraventamentos",
        "Tensão da viga",
        "Limite superior de axial e flexão",
        "Máximo sobre entidades selecionadas",
        "as barras de cada grupo (um sensor por grupo)",
        "N/mm² (MPa)",
        "maior que f_y/1,10",
        "Mostra qual grupo governa e quanto cada um trabalha: o memorial ganha uma linha por grupo.",
        grandeza=TENSAO,
    ),
    SensorRecomendado(
        "massa",
        ESTATICO,
        RECOMENDADO,
        "Massa do modelo",
        "Massa do modelo",
        "Propriedades de massa do Simulation",
        "Massa",
        "—",
        "o estudo",
        "kg",
        "—",
        "Confere o peso próprio do estudo com a lista de material: corpo excluído da análise, "
        "material sem densidade ou peça fora da lista aparecem aqui.",
        grandeza=MASSA,
    ),
    SensorRecomendado(
        "forca_conector",
        ESTATICO,
        RECOMENDADO,
        "Força nos parafusos (conectores)",
        "Força parafusos",
        "Força do conector",
        "Cisalhamento e axial (um sensor de cada)",
        "Máximo sobre entidades selecionadas",
        "os conectores de parafuso ou pino",
        "N",
        "—",
        "A força do parafuso mais carregado, para a verificação em Ligações.",
        condicao="se parafusos ou pinos foram modelados como conectores",
        grandeza=FORCA,
    ),
    # ------------------------------------------------------------------ estudo de flambagem
    SensorRecomendado(
        "fator_flambagem",
        FLAMBAGEM,
        MINIMO,
        "Fator de flambagem do modo 1",
        "Fator de flambagem modo 1",
        "Fator de segurança de flambagem",
        "Modo 1",
        "—",
        "o estudo de flambagem com as cargas da combinação ELU que governa (a de maior "
        "compressão nos pilares)",
        "—",
        f"menor que {_g(ALFA_PEQUENA_DESLOCABILIDADE)}",
        "É o α_cr: a carga que flamba dividida pela aplicada. Abaixo de 1 a estrutura flamba com "
        "as cargas de cálculo. Se o modo 1 desloca o conjunto para o lado, B₂ ≈ 1/(1 − 1/α_cr): "
        + texto_da_deslocabilidade()
        + ". Se o modo 1 é uma barra sozinha, é a flambagem dela: confira na verificação barra a "
        "barra (Esforços do modelo).",
        grandeza=FATOR_DE_FLAMBAGEM,
    ),
    SensorRecomendado(
        "modos_flambagem",
        FLAMBAGEM,
        RECOMENDADO,
        "Fator de flambagem dos modos 2 e 3",
        "Fator de flambagem modo 2, Fator de flambagem modo 3",
        "Fator de segurança de flambagem",
        "Modo 2 e Modo 3",
        "—",
        "o mesmo estudo, com pelo menos 3 modos (Propriedades do estudo → Número de modos)",
        "—",
        "—",
        "Mostra se os primeiros modos são do conjunto ou de barras soltas, e a folga entre eles.",
        grandeza=FATOR_DE_FLAMBAGEM,
    ),
    # ------------------------------------------------------------------ estudo de frequência
    SensorRecomendado(
        "frequencia_modo1",
        FREQUENCIA,
        MINIMO,
        "Frequência do primeiro modo vertical do piso",
        "Frequência modo 1",
        "Frequência",
        "Modo 1 (e o primeiro modo que sobe e desce o piso)",
        "—",
        "o estudo de frequência, com o peso do piso, dos equipamentos e a parte da sobrecarga das "
        "combinações frequentes (ψ1) como massa (massa distribuída ou remota) — sem isso a "
        "frequência sai alta demais",
        "Hz",
        f"menor que {_g(FREQUENCIA_MINIMA_CAMINHAR_HZ)} Hz",
        f"Piso onde as pessoas caminham: f₁ ≥ {_g(FREQUENCIA_MINIMA_CAMINHAR_HZ)} Hz; em nenhum "
        f"caso abaixo de {_g(FREQUENCIA_MINIMA_HZ)} Hz ({REFERENCIA_FREQUENCIA}). O modo 1 pode "
        "ser lateral: o que vale para o piso é o primeiro que o desloca na vertical.",
        grandeza=FREQUENCIA_HZ,
    ),
    SensorRecomendado(
        "frequencia_equipamento",
        FREQUENCIA,
        MINIMO,
        "Frequência da estrutura contra a do equipamento",
        "Frequência modo 1, 2, 3…",
        "Frequência",
        "os modos até 1,5 vez a frequência do equipamento",
        "—",
        "o estudo de frequência, com a massa do equipamento como massa remota no ponto de apoio",
        "Hz",
        "—",
        "Com Ne = frequência própria da estrutura e Nm = a do equipamento (rotação/60): "
        + texto_do_equipamento()
        + ".",
        condicao="se há equipamento rotativo ou vibratório apoiado",
        grandeza=FREQUENCIA_HZ,
    ),
    SensorRecomendado(
        "modos_frequencia",
        FREQUENCIA,
        RECOMENDADO,
        "Frequência dos modos seguintes",
        "Frequência modo 2, Frequência modo 3…",
        "Frequência",
        "Modos 2 a 5",
        "—",
        "o mesmo estudo, com pelo menos 5 modos",
        "Hz",
        "—",
        "Acha o primeiro modo vertical do piso quando os primeiros são laterais e mostra se há "
        "modos perto da frequência de algum equipamento.",
        grandeza=FREQUENCIA_HZ,
    ),
)


def recomendados(estudo: str) -> tuple[SensorRecomendado, ...]:
    return tuple(r for r in RECOMENDADOS if r.estudo == estudo)


def recomendado(chave: str) -> SensorRecomendado:
    return next(r for r in RECOMENDADOS if r.chave == chave)


@dataclass(frozen=True)
class OpcaoDoSolidWorks:
    """Uma opção da lista do SolidWorks e se a estrutura precisa dela."""

    grupo: str  # "Tipo de sensor" ou "Quantidade de dados"
    nome: str
    uso: str
    porque: str


TIPO_DE_SENSOR = "Tipo de sensor"
QUANTIDADE_DE_DADOS = "Quantidade de dados (Dados do Simulation)"

OPCOES_DO_SOLIDWORKS: tuple[OpcaoDoSolidWorks, ...] = (
    OpcaoDoSolidWorks(
        TIPO_DE_SENSOR,
        DADOS_DO_SIMULATION,
        E_ESTE,
        "Todos os sensores de resultado (tensão, deslocamento, FS, frequência…) ficam aqui.",
    ),
    OpcaoDoSolidWorks(
        TIPO_DE_SENSOR,
        "Propriedades de massa",
        NAO_PRECISA,
        "É a massa da peça no modelo. Para conferir o peso use Dados do Simulation → "
        "Propriedades de massa do Simulation: é a massa do estudo, sem os corpos excluídos.",
    ),
    OpcaoDoSolidWorks(
        TIPO_DE_SENSOR, "Dimensão", NAO_PRECISA, "Acompanha uma cota; não é resultado de cálculo."
    ),
    OpcaoDoSolidWorks(
        TIPO_DE_SENSOR, "Medida", NAO_PRECISA, "Acompanha uma medição; não é resultado de cálculo."
    ),
    OpcaoDoSolidWorks(TIPO_DE_SENSOR, "Dados de Costing", NAO_PRECISA, "Custo de fabricação."),
    OpcaoDoSolidWorks(
        TIPO_DE_SENSOR,
        "Propriedades da caixa delimitadora de chapa metálica",
        NAO_PRECISA,
        "Tamanho da chapa planificada.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Tensão",
        SE_HOUVER,
        "Von Mises nas chapas em casca ou sólido (piso em chapa, chapas de ligação). As barras "
        "usam Tensão da viga.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Deformação",
        NAO_PRECISA,
        "É a deformação específica (strain, sem unidade), não o deslocamento. A verificação usa "
        "tensão e deslocamento.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Deslocamento",
        MINIMO,
        "Flecha das vigas (UY) e deslocamento do topo dos pilares (URES).",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Frequência",
        MINIMO,
        "No estudo de frequência: vibração do piso e ressonância com equipamentos.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Fator de segurança de flambagem",
        MINIMO,
        "No estudo de flambagem: o α_cr, que diz se a estrutura é de pequena, média ou grande "
        "deslocabilidade.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Força do conector",
        SE_HOUVER,
        "Só se parafusos ou pinos foram modelados como conectores: a força de cada um.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Forças de corpo livre",
        NAO_PRECISA,
        "As reações dos apoios já vêm pela macro (…-reacoes.csv). Serve para ver a força que "
        "passa por uma face ou ligação específica.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Térmico",
        NAO_PRECISA,
        "Só em estudo térmico. A variação de temperatura (T+ e T−) entra no estudo estático como "
        "carga.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Velocidade",
        SE_HOUVER,
        "Só em estudo dinâmico (equipamento vibrando, resposta harmônica).",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Aceleração",
        SE_HOUVER,
        "Só em estudo dinâmico (equipamento vibrando, resposta harmônica).",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Tensão da viga",
        MINIMO,
        "A tensão nas barras: limite superior de axial e flexão.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Sensível ao fluxo de trabalho",
        NAO_PRECISA,
        "Sensor de estudos de projeto (otimização).",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Fator de segurança",
        MINIMO,
        "O FS mínimo do modelo, com o aço de cada barra.",
    ),
    OpcaoDoSolidWorks(
        QUANTIDADE_DE_DADOS,
        "Propriedades de massa do Simulation",
        RECOMENDADO,
        "A massa do estudo, para conferir o peso próprio com a lista de material.",
    ),
)
