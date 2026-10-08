"""Capítulo de memorial para os cálculos que fecham numa tabela de verificações.

A flambagem de colunas e as ligações parafusadas registram, em ``resultados["verificações"]``, uma
linha por verificação (solicitante × resistente, aproveitamento, status, fórmula e referência). O
capítulo genérico do memorial despejava tudo — trinta linhas de entradas, vinte de resultados e a
tabela de oito colunas na ordem do cálculo —, e quem queria saber "passou ou não?" percorria três
páginas por análise. Este módulo reorganiza o capítulo pelo que o leitor procura:

1. **Resultado**, em destaque: a contagem do que passou e do que não passou e o que governa;
2. os **dados de entrada** que importam, em tabela compacta, com rótulos legíveis;
3. método, premissas, critérios e referências — uma vez só quando várias análises os compartilham;
4. **O que passou**, verificação por verificação, com o cálculo;
5. os **valores de apoio** (grandezas informativas, sem critério);
6. **Não passou**, sempre no fim: o que reprovou, o que passou com ressalva ou não pôde ser avaliado
   e o que o módulo manda conferir antes de emitir — ou a declaração explícita de que nada reprovou.

O memorial existe para ser incluído em outro documento, então nada aqui é decoração: cada tabela é
nativa do Word e cada bloco se lê sozinho.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

Formatador = Callable[[Any], str]

STATUS_OK = "OK"
STATUS_NAO_OK = "NÃO OK"
STATUS_ALERTA = "ALERTA"
STATUS_INFO = "INFO"
STATUS_NA = "N/A"

RESULTADO_ATENDE = "ATENDE"
RESULTADO_NAO_ATENDE = "NÃO ATENDE"
RESULTADO_ATENCAO = "ATENÇÃO"
RESULTADO_NAO_AVALIADO = "NÃO AVALIADO"

_TOM_DO_RESULTADO = {
    RESULTADO_ATENDE: "ok",
    RESULTADO_NAO_ATENDE: "erro",
    RESULTADO_ATENCAO: "atencao",
    RESULTADO_NAO_AVALIADO: "neutro",
}

#: Colunas das tabelas de verificação (somam 9 360, a largura útil do memorial).
CABECALHOS_VERIFICACAO = [
    "Verificação",
    "Solicitante",
    "Resistente",
    "Un.",
    "Aprov.",
    "Cálculo e referência",
]
LARGURAS_VERIFICACAO = [1950, 950, 950, 520, 760, 4230]
CABECALHOS_APOIO = ["Grandeza", "Valor", "Un.", "Cálculo e referência"]
LARGURAS_APOIO = [2900, 1100, 560, 4800]

# O número logo depois de "Anglo " ou "item " é um item do critério ou da norma ("Anglo 10.2"), não
# um decimal.
_DECIMAL_COM_PONTO = re.compile(r"(?<![\d.,])(?<!Anglo )(?<!item )(?<!itens )(\d+)\.(\d+)(?![\d.])")
_IDENTIFICADOR = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")


def decimal_ptbr(texto: str) -> str:
    """Troca o ponto decimal por vírgula nos números soltos de um texto de cálculo.

    As fórmulas do módulo saem em notação de máquina ("0.270·1.000·1963·250/1.10 = 120.71 kN"); o
    memorial é em português. Números de item ("5.3.2", "Anglo 10.2"), siglas ("A.3") e números já
    com vírgula não mudam: só vira vírgula o ponto que fica entre dois grupos de dígitos isolados.
    """
    return _DECIMAL_COM_PONTO.sub(r"\1,\2", texto)


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def normalizar_status(valor: Any) -> str:
    """Um dos cinco status da tabela; o que não for reconhecido vira ``N/A`` (não avaliado)."""
    chave = _sem_acento(str(valor or "")).strip().casefold()
    return {
        "ok": STATUS_OK,
        "nao ok": STATUS_NAO_OK,
        "alerta": STATUS_ALERTA,
        "atencao": STATUS_ALERTA,
        "info": STATUS_INFO,
        "n/a": STATUS_NA,
        "na": STATUS_NA,
    }.get(chave, STATUS_NA)


def _numero(valor: Any) -> float | None:
    """Número do registro: ``None`` quando é traço, texto ou vazio; ``inf`` para "∞"."""
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return None if math.isnan(valor) else float(valor)
    texto = str(valor).strip()
    if texto == "∞":
        return math.inf
    try:
        convertido = float(texto.replace(",", "."))
    except ValueError:
        return None
    return None if math.isnan(convertido) else convertido


@dataclass(frozen=True)
class Linha:
    """Uma verificação do registro, já com o status normalizado."""

    nome: str
    solicitante: Any
    resistente: Any
    unidade: str
    aproveitamento: float | None  # em %, ``inf`` quando a resistência é nula
    status: str
    formula: str
    referencia: str


def _texto(valor: Any) -> str:
    texto = "" if valor is None else str(valor).strip()
    return "" if texto in ("—", "-", "–") else texto


def _primeiro(item: Mapping[str, Any], *chaves: str) -> Any:
    for chave in chaves:
        if chave in item:
            return item[chave]
    return None


def extrair_linhas(registro: Mapping[str, Any]) -> list[Linha] | None:
    """Linhas de ``resultados["verificações"]``; ``None`` quando o registro não tem a tabela.

    Registro malformado (lista que não é de mapas, item sem nome) não derruba o memorial: o item
    inválido é ignorado e, se nada sobrar, o capítulo volta ao formato genérico.
    """
    resultados = registro.get("resultados")
    if not isinstance(resultados, Mapping):
        return None
    bruto = _primeiro(resultados, "verificações", "verificacoes")
    if not isinstance(bruto, Sequence) or isinstance(bruto, (str, bytes)):
        return None
    linhas: list[Linha] = []
    for item in bruto:
        if not isinstance(item, Mapping):
            continue
        nome = _texto(_primeiro(item, "verificação", "verificacao", "nome"))
        if not nome:
            continue
        linhas.append(
            Linha(
                nome=nome,
                solicitante=_primeiro(item, "solicitante"),
                resistente=_primeiro(item, "resistente"),
                unidade=_texto(_primeiro(item, "unidade")),
                aproveitamento=_numero(_primeiro(item, "aproveitamento_pct", "aproveitamento")),
                status=normalizar_status(_primeiro(item, "status")),
                formula=_texto(_primeiro(item, "fórmula", "formula")),
                referencia=_texto(_primeiro(item, "referência", "referencia")),
            )
        )
    return linhas or None


@dataclass
class Resumo:
    passaram: list[Linha] = field(default_factory=list)
    reprovadas: list[Linha] = field(default_factory=list)
    atencao: list[Linha] = field(default_factory=list)
    nao_avaliadas: list[Linha] = field(default_factory=list)
    informativas: list[Linha] = field(default_factory=list)

    @property
    def com_criterio(self) -> int:
        return len(self.passaram) + len(self.reprovadas) + len(self.atencao)

    @property
    def resultado(self) -> str:
        if self.reprovadas:
            return RESULTADO_NAO_ATENDE
        if self.atencao:
            return RESULTADO_ATENCAO
        if self.passaram:
            return RESULTADO_ATENDE
        return RESULTADO_NAO_AVALIADO

    @property
    def tom(self) -> str:
        return _TOM_DO_RESULTADO[self.resultado]

    @property
    def governante(self) -> Linha | None:
        """A verificação de maior aproveitamento entre as que têm critério."""
        candidatas = [
            linha
            for linha in (*self.passaram, *self.reprovadas, *self.atencao)
            if linha.aproveitamento is not None
        ]
        return max(candidatas, key=lambda linha: linha.aproveitamento or 0.0, default=None)


def resumir(linhas: Sequence[Linha]) -> Resumo:
    resumo = Resumo()
    destino = {
        STATUS_OK: resumo.passaram,
        STATUS_NAO_OK: resumo.reprovadas,
        STATUS_ALERTA: resumo.atencao,
        STATUS_INFO: resumo.informativas,
        STATUS_NA: resumo.nao_avaliadas,
    }
    for linha in linhas:
        destino[linha.status].append(linha)
    return resumo


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _percentual(valor: float | None) -> str:
    if valor is None:
        return "-"
    if math.isinf(valor):
        return "∞"
    return f"{valor:.1f}%".replace(".", ",")


def texto_do_resultado(registro: Mapping[str, Any], resumo: Resumo, formatar: Formatador) -> str:
    """A frase do destaque: quantas passaram, quantas não, o que governa e o dado-chave do módulo."""
    partes = [
        f"{_plural(resumo.com_criterio, 'verificação com critério', 'verificações com critério')}: "
        + _plural(len(resumo.passaram), "passou", "passaram")
    ]
    if resumo.reprovadas:
        partes[0] += f", {_plural(len(resumo.reprovadas), 'não passou', 'não passaram')}"
    if resumo.atencao:
        partes[0] += f", {len(resumo.atencao)} em atenção"
    partes[0] += "."
    governante = resumo.governante
    if governante is not None:
        partes.append(
            f"Maior aproveitamento: {_percentual(governante.aproveitamento)} em «{governante.nome}»."
        )
    if resumo.nao_avaliadas:
        partes.append(f"{_plural(len(resumo.nao_avaliadas), 'não avaliada', 'não avaliadas')}.")
    resultados = registro.get("resultados")
    if isinstance(resultados, Mapping):
        destaque = str(resultados.get("destaque_memorial") or "").strip()
        if destaque:
            partes.append(destaque)
        if resultados.get("resistencia_kN") is not None:
            partes.append(f"N_c,Rd = {formatar(resultados['resistencia_kN'])} kN.")
        menor = str(resultados.get("menor_parafuso_que_atende") or "").strip()
        if menor.casefold().startswith("nenhum"):
            partes.append("Nenhum parafuso da tabela atende com esta geometria.")
        elif menor:
            partes.append(f"Menor parafuso que atende esta geometria: {menor}.")
    return " ".join(partes)


def contagens(registro: Mapping[str, Any]) -> dict[str, Any] | None:
    """Resumo numérico de um registro com tabela, para o quadro-resumo; ``None`` sem tabela."""
    linhas = extrair_linhas(registro)
    if linhas is None:
        return None
    resumo = resumir(linhas)
    governante = resumo.governante
    return {
        "passaram": len(resumo.passaram),
        "reprovadas": len(resumo.reprovadas),
        "atencao": len(resumo.atencao),
        "nao_avaliadas": len(resumo.nao_avaliadas),
        "aproveitamento_max": None if governante is None else governante.aproveitamento,
        "governante": None if governante is None else governante.nome,
        "resultado": resumo.resultado,
        "reprovacoes": [
            {"verificacao": linha.nome, "aproveitamento": linha.aproveitamento}
            for linha in resumo.reprovadas
        ],
    }


# ---------------------------------------------------------------------------------------------
# Tabelas
# ---------------------------------------------------------------------------------------------
def _valor_celula(valor: Any, formatar: Formatador) -> str:
    if _texto(valor) == "":
        return "-"
    return formatar(valor)


def _celula_de_calculo(linha: Linha) -> tuple[str, str]:
    formula = decimal_ptbr(linha.formula) if linha.formula else "-"
    return formula, f"Ref.: {linha.referencia}" if linha.referencia else ""


def tabela_de_verificacoes(
    linhas: Sequence[Linha], *, legenda: str, tom: str, formatar: Formatador
) -> dict[str, Any]:
    """Verificações com solicitante × resistente; o cálculo e a referência numa só coluna."""
    return {
        "legenda": legenda,
        "cabecalhos": list(CABECALHOS_VERIFICACAO),
        "linhas": [
            [
                linha.nome,
                _valor_celula(linha.solicitante, formatar),
                _valor_celula(linha.resistente, formatar),
                linha.unidade or "-",
                _percentual(linha.aproveitamento),
                _celula_de_calculo(linha),
            ]
            for linha in linhas
        ],
        "larguras": list(LARGURAS_VERIFICACAO),
        "fonte": 7.2,
        "tom": tom,
    }


def tabela_de_apoio(
    linhas: Sequence[Linha], *, legenda: str, formatar: Formatador
) -> dict[str, Any]:
    """Grandezas informativas: um só valor por linha (ou ``solicitante / resistente``)."""
    linhas_tabela = []
    for linha in linhas:
        valores = [
            formatar(valor) for valor in (linha.solicitante, linha.resistente) if _texto(valor)
        ]
        linhas_tabela.append(
            [
                linha.nome,
                " / ".join(valores) or "-",
                linha.unidade or "-",
                _celula_de_calculo(linha),
            ]
        )
    return {
        "legenda": legenda,
        "cabecalhos": list(CABECALHOS_APOIO),
        "linhas": linhas_tabela,
        "larguras": list(LARGURAS_APOIO),
        "fonte": 7.2,
    }


# ---------------------------------------------------------------------------------------------
# Dados de entrada
# ---------------------------------------------------------------------------------------------
NOMES_DE_NORMA = {
    "NBR8800_2008": "ABNT NBR 8800:2008",
    "NBR8800_2024": "Projeto de revisão ABNT NBR 8800 (2024)",
    "AISC360_16_LRFD": "AISC 360-16 (LRFD)",
    "AISC360_LRFD": "AISC 360 (LRFD)",
    "RCSC2004": "RCSC 2004",
}

#: (chave do registro, rótulo, quando mostrar). ``sempre`` mostra mesmo zerado; ``se_preenchido``
#: omite o que é vazio, falso ou zero — um dado que só existe quando o usuário o informou.
_Entrada = tuple[str, str, str]
_ENTRADAS_FLAMBAGEM: tuple[_Entrada, ...] = (
    ("norma", "Norma", "sempre"),
    ("secao", "Seção", "sempre"),
    ("tipo_secao", "Tipo de seção", "sempre"),
    ("tipo_secao_escolhido", "Tipo escolhido na entrada", "se_preenchido"),
    ("perfil_soldado", "Perfil soldado", "se_preenchido"),
    ("area_mm2", "Área A [mm²]", "sempre"),
    ("inercia_x_mm4", "Inércia Ix [mm⁴]", "sempre"),
    ("inercia_y_mm4", "Inércia Iy [mm⁴]", "sempre"),
    ("raio_giracao_x_mm", "Raio de giração rx [mm]", "sempre"),
    ("raio_giracao_y_mm", "Raio de giração ry [mm]", "sempre"),
    ("J_mm4", "Constante de torção J [mm⁴]", "sempre"),
    ("Cw_mm6", "Empenamento Cw [mm⁶]", "se_preenchido"),
    ("x0_mm", "Centro de cisalhamento x0 [mm]", "se_preenchido"),
    ("y0_mm", "Centro de cisalhamento y0 [mm]", "se_preenchido"),
    ("modulo_elasticidade_MPa", "Módulo E [MPa]", "sempre"),
    ("modulo_cisalhamento_MPa", "Módulo G [MPa]", "sempre"),
    ("escoamento_MPa", "Escoamento fy [MPa]", "sempre"),
    ("gamma_a1", "Coeficiente γa1", "se_preenchido"),
    ("fator_resistencia", "Fator de resistência", "sempre"),
    ("comprimento_total_mm", "Comprimento total L [mm]", "se_preenchido"),
    ("comprimento_x_mm", "Comprimento Lx [mm]", "sempre"),
    ("comprimento_y_mm", "Comprimento Ly [mm]", "sempre"),
    ("comprimento_z_mm", "Comprimento Lz [mm]", "sempre"),
    ("kx", "Coeficiente Kx", "sempre"),
    ("ky", "Coeficiente Ky", "sempre"),
    ("kz", "Coeficiente Kz", "sempre"),
    ("condicao_apoio_x", "Vinculação em x", "se_preenchido"),
    ("condicao_apoio_y", "Vinculação em y", "se_preenchido"),
    ("k_recomendado_de_norma", "K recomendado pela norma", "se_preenchido"),
    ("permanente_kN", "Ação permanente [kN]", "se_preenchido"),
    ("variavel_kN", "Ação variável [kN]", "se_preenchido"),
    ("gamma_g", "Coeficiente γg", "se_preenchido"),
    ("gamma_q", "Coeficiente γq", "se_preenchido"),
    ("forca_solicitante_kN", "Força axial NSd [kN]", "sempre"),
    ("momento_x_kNm", "Momento Mx,Sd [kN·m]", "sempre"),
    ("momento_y_kNm", "Momento My,Sd [kN·m]", "sempre"),
    ("excentricidade_x_mm", "Excentricidade ex [mm]", "se_preenchido"),
    ("excentricidade_y_mm", "Excentricidade ey [mm]", "se_preenchido"),
    ("diagrama_momentos_x", "Diagrama de momentos em x", "se_preenchido"),
    ("diagrama_momentos_y", "Diagrama de momentos em y", "se_preenchido"),
    ("razao_M1_M2_x", "Razão M1/M2 em x", "se_preenchido"),
    ("razao_M1_M2_y", "Razão M1/M2 em y", "se_preenchido"),
    ("forcas_transversais_x", "Forças transversais em x", "se_preenchido"),
    ("forcas_transversais_y", "Forças transversais em y", "se_preenchido"),
    ("comprimento_destravado_FLT_mm", "Comprimento destravado Lb [mm]", "se_preenchido"),
    ("cb", "Coeficiente Cb", "se_preenchido"),
    ("MRd_x_informado_kNm", "MRd,x informado [kN·m]", "se_preenchido"),
    ("MRd_y_informado_kNm", "MRd,y informado [kN·m]", "se_preenchido"),
    ("secao_compacta_confirmada", "Seção compacta confirmada", "se_preenchido"),
    ("espessuras_anglo_mm", "Espessuras (critério Anglo) [mm]", "se_preenchido"),
    ("mao_francesa", "Mão-francesa", "se_preenchido"),
    ("mao_francesa_eixo", "Mão-francesa: eixo fletido", "se_preenchido"),
    ("mao_francesa_forca_kN", "Mão-francesa: força característica [kN]", "se_preenchido"),
    ("mao_francesa_gamma_f", "Mão-francesa: coeficiente γf", "se_preenchido"),
    ("mao_francesa_forca_calculo_kN", "Mão-francesa: força de cálculo [kN]", "se_preenchido"),
    ("mao_francesa_angulo_graus", "Mão-francesa: ângulo [°]", "se_preenchido"),
    ("mao_francesa_altura_no_mm", "Mão-francesa: altura do nó [mm]", "se_preenchido"),
    ("mao_francesa_vinculo", "Mão-francesa: vínculo", "se_preenchido"),
    ("mao_francesa_excentricidade_mm", "Mão-francesa: excentricidade [mm]", "se_preenchido"),
    ("mao_francesa_H_kN", "Mão-francesa: componente H [kN]", "se_preenchido"),
    ("mao_francesa_V_kN", "Mão-francesa: componente V [kN]", "se_preenchido"),
    ("mao_francesa_V_somado_a_NSd", "Mão-francesa: V somado a NSd", "se_preenchido"),
    ("mao_francesa_momento_kNm", "Mão-francesa: momento [kN·m]", "se_preenchido"),
    ("momento_mao_francesa_x_kNm", "Momento da mão-francesa em x [kN·m]", "se_preenchido"),
    ("momento_mao_francesa_y_kNm", "Momento da mão-francesa em y [kN·m]", "se_preenchido"),
    ("mao_francesa_expressao", "Mão-francesa: expressão", "se_preenchido"),
)

_ENTRADAS_PARAFUSOS: tuple[_Entrada, ...] = (
    ("modo", "Modo", "se_preenchido"),
    ("norma", "Norma", "sempre"),
    ("parafuso", "Parafuso", "sempre"),
    ("grau", "Grau", "sempre"),
    ("aco", "Aço das chapas", "se_preenchido"),
    ("furo_dh_mm", "Furo dh [mm]", "se_preenchido"),
    ("planos_de_corte", "Planos de corte", "sempre"),
    ("rosca_no_plano_corte", "Rosca no plano de corte", "sempre"),
    ("espessura_mais_fina_t_mm", "Espessura t da parte mais fina [mm]", "sempre"),
    ("pega_mm", "Pega [mm]", "se_preenchido"),
    ("n_lin", "Linhas de parafusos", "se_preenchido"),
    ("n_col", "Colunas de parafusos", "se_preenchido"),
    ("passo_s_mm", "Passo s [mm]", "se_preenchido"),
    ("gabarito_g_mm", "Gabarito g [mm]", "se_preenchido"),
    ("coordenadas_mm", "Coordenadas dos parafusos [mm]", "se_preenchido"),
    ("borda_e_mm", "Distância à borda e [mm]", "sempre"),
    ("borda_vertical_ev_mm", "Distância à borda transversal ev [mm]", "se_preenchido"),
    ("N_kN", "Força axial N [kN]", "sempre"),
    ("V_kN", "Força cortante V [kN]", "sempre"),
    ("M_kNm", "Momento M [kN·m]", "sempre"),
    ("excentricidade_a_mm", "Excentricidade da carga [mm]", "se_preenchido"),
    ("gama_f", "Coeficiente γf", "se_preenchido"),
    ("valores_ja_de_calculo", "Esforços já majorados", "sempre"),
    ("superficie", "Superfície de contato", "se_preenchido"),
    ("ligacao_por_atrito", "Ligação por atrito", "sempre"),
    ("Ce", "Coeficiente Ce", "se_preenchido"),
    ("deformacao_do_furo_limitada", "Deformação do furo limitada", "sempre"),
    ("A_g_peca_mm2", "Área bruta da peça Ag [mm²]", "se_preenchido"),
    ("e_c_peca_mm", "Excentricidade da peça ec [mm]", "se_preenchido"),
    ("ligacao_principal_anglo", "Ligação principal (Anglo)", "sempre"),
    ("revestimento", "Revestimento", "se_preenchido"),
    ("peca_por_esbeltez", "Peça dimensionada por esbeltez", "se_preenchido"),
    ("fora_do_escopo_marcado", "Itens marcados como fora do escopo", "se_preenchido"),
)

_ENTRADAS_VENTO: tuple[_Entrada, ...] = (
    ("edicao_da_norma", "Edição da norma", "sempre"),
    ("v0_m_s", "Velocidade básica V₀ [m/s]", "sempre"),
    ("relevo", "Relevo", "se_preenchido"),
    ("s1", "Fator topográfico S₁", "sempre"),
    ("categoria_rugosidade", "Categoria de rugosidade", "sempre"),
    ("grupo_s3", "Grupo da edificação (S₃)", "sempre"),
    ("probabilidade_pm", "Probabilidade P_m (Anexo B)", "se_preenchido"),
    ("vida_util_anos", "Vida útil m_a [anos] (Anexo B)", "se_preenchido"),
    ("s3_informado", "S₃ adotado (Anexo B)", "se_preenchido"),
    ("classe_forcada", "Classe imposta (S₂)", "se_preenchido"),
    ("referencia_de_altura", "Altura de referência de S₂", "sempre"),
    ("vedacoes_com_092", "Vedações com 0,92·S₃", "se_preenchido"),
    ("cobertura", "Cobertura", "sempre"),
    ("comprimento_a_m", "Comprimento a [m]", "sempre"),
    ("largura_b_m", "Largura b [m]", "sempre"),
    ("altura_h_m", "Altura do beiral h [m]", "sempre"),
    ("inclinacao_theta_graus", "Inclinação do telhado θ [°]", "sempre"),
    ("altura_do_topo_m", "Altura do topo [m]", "sempre"),
    ("balanco_do_beiral_m", "Balanço do beiral [m]", "se_preenchido"),
    ("espacamento_porticos_m", "Espaçamento dos pórticos [m]", "sempre"),
    ("periodo_fundamental_s", "Período fundamental T₁ [s]", "se_preenchido"),
    ("permeabilidade", "Pressão interna (permeabilidade)", "sempre"),
    ("alta_turbulencia_solicitada", "Alta turbulência solicitada", "se_preenchido"),
    ("efeito_de_vizinhanca", "Efeito de vizinhança", "se_preenchido"),
    ("afastamento_vizinha_m", "Afastamento da vizinha s [m]", "se_preenchido"),
    ("coeficiente_de_atrito_ct", "Coeficiente de atrito C_t", "sempre"),
    ("portico_bases", "Bases do pórtico", "se_preenchido"),
    ("portico_pilar", "Seção dos pilares", "se_preenchido"),
    ("portico_rafter", "Seção das águas", "se_preenchido"),
)

_ENTRADAS_DEGRAU: tuple[_Entrada, ...] = (
    ("obra", "Obra", "se_preenchido"),
    ("tag", "TAG", "se_preenchido"),
    ("data_do_calculo", "Data do cálculo", "se_preenchido"),
    ("enquadramento", "Enquadramento legal", "sempre"),
    ("espelho_fechado", "Degrau com espelho fechado", "sempre"),
    ("uso", "Uso (Anglo 10.2)", "sempre"),
    ("desnivel_H_mm", "Desnível total H [mm]", "sempre"),
    ("espelho_alvo_mm", "Espelho alvo [mm]", "sempre"),
    ("n_espelhos_imposto", "Nº de espelhos imposto", "se_preenchido"),
    ("piso_b_imposto_mm", "Piso b imposto [mm]", "se_preenchido"),
    ("profundidade_C_imposta_mm", "Profundidade C imposta [mm]", "se_preenchido"),
    ("C_padronizado", "C da série padrão (175, 200, … 300)", "sempre"),
    ("comprimento_L_mm", "Comprimento do degrau L [mm]", "sempre"),
    ("reducao_da_largura_util_mm", "Redução da largura útil [mm]", "se_preenchido"),
    ("altura_max_lance_imposta_mm", "Altura máxima por lance imposta [mm]", "se_preenchido"),
    ("patamar_mm", "Patamar intermediário [mm]", "sempre"),
    ("selecao_do_modelo", "Seleção do modelo", "sempre"),
    ("malha_preferida", "Malha preferencial", "sempre"),
    ("ligacao_preferida", "Barras de ligação preferenciais", "sempre"),
    ("modelo_manual", "Modelo escolhido", "se_preenchido"),
    ("superficie", "Superfície", "sempre"),
    ("chapa_xadrez_no_bocel", "Chapa xadrez no bocel", "sempre"),
    ("acabamento", "Acabamento", "sempre"),
    ("material", "Material", "sempre"),
    ("lado_barra_ligacao_mm", "Lado da barra de ligação (adotado) [mm]", "sempre"),
    ("parafuso", "Parafuso A307", "sempre"),
    ("n_parafusos_por_lado", "Parafusos por chapa lateral", "sempre"),
    ("sobrecarga_q_kN_m2", "Sobrecarga q [kN/m²]", "sempre"),
    ("carga_concentrada_P_kN", "Carga concentrada P [kN]", "sempre"),
    ("carga_ISO_kN", "Carga concentrada ISO [kN]", "sempre"),
    ("largura_de_aplicacao_mm", "Largura de aplicação b_c [mm]", "sempre"),
    ("n_ef_imposto", "n_ef imposto", "se_preenchido"),
    ("gamma_g", "Coeficiente γg", "sempre"),
    ("gamma_q", "Coeficiente γq", "sempre"),
    ("gamma_a1", "Coeficiente γa1", "sempre"),
    ("gamma_a2", "Coeficiente γa2", "sempre"),
    ("cb", "Coeficiente Cb", "sempre"),
    ("flecha_distribuida_L_sobre", "Flecha distribuída: L/", "sempre"),
    ("flecha_ISO_L_sobre", "Flecha ISO: L/", "sempre"),
    ("flecha_ISO_maxima_mm", "Flecha ISO máxima [mm]", "sempre"),
    ("gc_travessao_superior_mm", "Guarda-corpo, travessão superior [mm]", "sempre"),
    ("gc_travessao_intermediario_mm", "Guarda-corpo, travessão intermediário [mm]", "sempre"),
    ("gc_rodape_mm", "Guarda-corpo, rodapé [mm]", "sempre"),
    ("gc_espacamento_mm", "Guarda-corpo, espaçamento entre barras [mm]", "sempre"),
)

ENTRADAS_CURADAS: dict[str, tuple[_Entrada, ...]] = {
    "flambagem_colunas": _ENTRADAS_FLAMBAGEM,
    "projeto_parafusos": _ENTRADAS_PARAFUSOS,
    "vento_nbr6123": _ENTRADAS_VENTO,
    "degrau_escada": _ENTRADAS_DEGRAU,
}

LARGURAS_ENTRADAS = [2350, 2330, 2350, 2330]

#: Chaves de ``resultados`` que o capítulo já mostra de outra forma (o destaque, a tabela de
#: verificações ou a de paredes). As demais chaves escalares aparecem em "Outros resultados": um
#: resultado que o módulo passe a registrar não some do memorial só porque ninguém o listou aqui.
_RESULTADOS_JA_TRATADOS = frozenset(
    {
        "verificações",
        "verificacoes",
        "status_geral",
        "utilizacao_maxima",
        # flambagem de colunas
        "modo_governante",
        "eixo_governante",
        "esbeltez_x",
        "esbeltez_y",
        "esbeltez_governante",
        "utilizacao",
        "indice_interacao",
        "b1_x",
        "b1_y",
        "momento_x_amplificado_kNm",
        "momento_y_amplificado_kNm",
        "momento_resistente_x_kNm",
        "momento_resistente_y_kNm",
        "atende",
        "bloqueios",
        "ne_x_kN",
        "ne_y_kN",
        "ne_z_kN",
        "ne_kN",
        "modo_flambagem",
        "fator_q",
        "area_efetiva_mm2",
        "lambda_0",
        "chi",
        "resistencia_kN",
        "utilizacao_axial",
        "esbeltez_paredes",
        # ligação parafusada estrutural
        "verificacao_governante",
        "menor_parafuso_que_atende",
        "forca_parafuso_critico_ELU_kN",
        "forca_parafuso_critico_ELS_kN",
        "momento_polar_J_mm2",
        "torque_estimado_Nm",
        # vento nas estruturas
        "destaque_memorial",
        "tabelas_memorial",
        "casos_de_vento",
        "arrasto_global",
        "cargas_do_portico",
        "solucao_do_portico",
        # degrau de escada em grade (as tabelas do memorial já trazem estes valores)
        "modelo_adotado",
        "número_de_espelhos",
        "espelho_h_mm",
        "piso_b_mm",
        "inclinação_graus",
        "profundidade_C_mm",
        "furação_F_mm",
        "distribuição_dos_lances",
        "degraus_em_grade",
        "projeção_horizontal_total_mm",
        "peso_unitário_kg",
        "peso_total_kg",
    }
)


def _vazio(valor: Any) -> bool:
    if valor is None or valor is False:
        return True
    if isinstance(valor, (int, float)):
        return valor == 0
    if isinstance(valor, str):
        return valor.strip() in ("", "0", "não incluída")
    if isinstance(valor, (Mapping, Sequence)):
        return len(valor) == 0
    return False


def _chave_interna(chave: str) -> bool:
    return chave.endswith(("_id", "_ids")) or chave == "registro_origem"


def pares_de_entrada(
    registro: Mapping[str, Any], formatar: Formatador, rotular: Callable[[str], str]
) -> list[tuple[str, str]]:
    """Os dados de entrada como pares (rótulo, valor), na ordem do módulo.

    O que o módulo conhece sai com rótulo e unidade próprios e na ordem do cálculo; o que ele
    acrescentar no futuro e este mapa ainda não souber aparece depois, com o rótulo automático —
    nenhum dado de entrada some do memorial só porque ninguém o cadastrou aqui.
    """
    entradas = registro.get("entradas")
    if not isinstance(entradas, Mapping) or not entradas:
        return []
    curadas = ENTRADAS_CURADAS.get(str(registro.get("modulo_id") or ""), ())
    conhecidas = {chave for chave, _, _ in curadas}
    pares: list[tuple[str, str]] = []

    def valor_legivel(chave: str, valor: Any) -> str:
        if chave == "norma":
            return NOMES_DE_NORMA.get(str(valor), str(valor))
        if isinstance(valor, bool):
            return "Sim" if valor else "Não"
        if isinstance(valor, str) and "_" in valor and _IDENTIFICADOR.match(valor):
            return valor.replace("_", " ")  # "galvanizada_sem_tratamento" é um código, não um texto
        return formatar(valor)

    for chave, rotulo, quando in curadas:
        if chave not in entradas:
            continue
        valor = entradas[chave]
        if valor is None or (quando == "se_preenchido" and _vazio(valor)):
            continue
        pares.append((rotulo, valor_legivel(chave, valor)))
    for chave, valor in entradas.items():
        chave = str(chave)
        if chave in conhecidas or _chave_interna(chave) or valor is None:
            continue
        if curadas and _vazio(valor):
            continue  # num módulo conhecido, o que sobra e está vazio é ruído
        pares.append((rotular(chave), valor_legivel(chave, valor)))
    return pares


def pares_de_resultados(
    registro: Mapping[str, Any], formatar: Formatador, rotular: Callable[[str], str]
) -> list[tuple[str, str]]:
    """Resultados escalares do registro que o capítulo não mostra em outro lugar."""
    resultados = registro.get("resultados")
    if not isinstance(resultados, Mapping):
        return []
    pares: list[tuple[str, str]] = []
    for chave, valor in resultados.items():
        chave = str(chave)
        if chave in _RESULTADOS_JA_TRATADOS or _chave_interna(chave) or valor is None:
            continue
        if isinstance(valor, (Mapping, list, tuple, set)):
            continue  # listas viram tabela própria; aqui só entram os escalares
        texto = ("Sim" if valor else "Não") if isinstance(valor, bool) else formatar(valor)
        pares.append((rotular(chave), texto))
    return pares


def tabela_de_entradas(
    pares: Sequence[tuple[str, str]], *, legenda: str, rotulo: str = "Dado"
) -> dict[str, Any]:
    """Pares (rótulo, valor) em quatro colunas: dois dados por linha, metade do comprimento."""
    linhas = []
    for indice in range(0, len(pares), 2):
        a_rotulo, a_valor = pares[indice]
        b_rotulo, b_valor = pares[indice + 1] if indice + 1 < len(pares) else ("", "")
        linhas.append([a_rotulo, a_valor, b_rotulo, b_valor])
    return {
        "legenda": legenda,
        "cabecalhos": [rotulo, "Valor", rotulo, "Valor"],
        "linhas": linhas,
        "larguras": list(LARGURAS_ENTRADAS),
        "fonte": 7.4,
    }


# ---------------------------------------------------------------------------------------------
# Texto de base (método, premissas, critérios, referências) e alertas livres
# ---------------------------------------------------------------------------------------------
def _lista_de_textos(valor: Any) -> list[str]:
    if not isinstance(valor, Sequence) or isinstance(valor, (str, bytes)):
        return []
    return [str(item).strip() for item in valor if str(item).strip()]


def equacoes_gerais(registro: Mapping[str, Any], linhas: Sequence[Linha]) -> list[str]:
    """Equações do registro que não são o cálculo de uma linha da tabela.

    Na ligação parafusada são as equações do método (corte, contato, grupo excêntrico…), as
    mesmas em toda análise da mesma norma; na coluna, a combinação de ações, que muda com os dados.
    """
    das_linhas = {decimal_ptbr(linha.formula) for linha in linhas if linha.formula}
    equacoes = (decimal_ptbr(texto) for texto in _lista_de_textos(registro.get("equacoes")))
    return [texto for texto in equacoes if texto not in das_linhas]


def assinatura_da_base(registro: Mapping[str, Any], linhas: Sequence[Linha]) -> tuple[Any, ...]:
    """Identifica método, premissas, critérios, referências e equações gerais de uma análise.

    Duas análises com a mesma assinatura têm a mesma base: a segunda a cita em vez de repeti-la.
    """
    return (
        str(registro.get("modulo_id") or ""),
        str(registro.get("metodo") or "").strip(),
        tuple(_lista_de_textos(registro.get("premissas"))),
        tuple(_lista_de_textos(registro.get("criterios"))),
        tuple(_lista_de_textos(registro.get("referencias"))),
        tuple(equacoes_gerais(registro, linhas)),
    )


def _base_do_calculo(
    registro: Mapping[str, Any], equacoes: Sequence[str], repetida_de: str | None
) -> list[dict[str, Any]]:
    metodo = str(registro.get("metodo") or "").strip()
    premissas = _lista_de_textos(registro.get("premissas"))
    criterios = _lista_de_textos(registro.get("criterios"))
    referencias = _lista_de_textos(registro.get("referencias"))
    if not (metodo or premissas or criterios or referencias or equacoes):
        return []
    if repetida_de:
        return [
            {
                "tipo": "paragrafo",
                "texto": (
                    "Método, premissas, critérios, referências e equações gerais: "
                    f"os mesmos do item {repetida_de}."
                ),
            }
        ]
    blocos: list[dict[str, Any]] = [{"tipo": "subtitulo", "texto": "Método, premissas e critérios"}]
    if metodo:
        blocos.append({"tipo": "paragrafo", "texto": f"Método: {decimal_ptbr(metodo)}"})
    itens = (
        [f"Premissa: {decimal_ptbr(texto)}" for texto in premissas]
        + [f"Critério: {decimal_ptbr(texto)}" for texto in criterios]
        + [f"Referência: {texto}" for texto in referencias]
    )
    if itens:
        blocos.append({"tipo": "bullets", "itens": itens})
    blocos.extend({"tipo": "formula", "texto": equacao} for equacao in equacoes)
    return blocos


def alertas_livres(registro: Mapping[str, Any], linhas: Sequence[Linha]) -> list[str]:
    """Alertas do registro que não são o eco de uma linha da tabela (essas já têm a sua)."""
    prefixos = tuple(
        f"{linha.nome}: " for linha in linhas if linha.status in (STATUS_NAO_OK, STATUS_ALERTA)
    )
    return [
        decimal_ptbr(texto)
        for texto in _lista_de_textos(registro.get("alertas"))
        if not texto.startswith(prefixos)
    ]


# ---------------------------------------------------------------------------------------------
# O capítulo
# ---------------------------------------------------------------------------------------------
def _data_legivel(valor: Any) -> str:
    try:
        return datetime.fromisoformat(str(valor)).astimezone().strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return ""


def _bloco_nao_passou(
    registro: Mapping[str, Any], linhas: Sequence[Linha], resumo: Resumo, formatar: Formatador
) -> list[dict[str, Any]]:
    """O fim do capítulo: o que não passou, o que pede atenção e o que o módulo manda conferir."""
    blocos: list[dict[str, Any]] = []
    livres = alertas_livres(registro, linhas)
    if resumo.reprovadas:
        blocos.append(
            {
                "tipo": "subtitulo",
                "texto": f"Não passou ({len(resumo.reprovadas)})",
                "tom": "erro",
            }
        )
        blocos.append(
            {
                "tipo": "tabela",
                **tabela_de_verificacoes(
                    resumo.reprovadas,
                    legenda="Aprov. = solicitante ÷ resistente; acima de 100% a verificação reprova.",
                    tom="erro",
                    formatar=formatar,
                ),
            }
        )
    else:
        blocos.append(
            {
                "tipo": "destaque",
                "rotulo": "Não passou: nenhuma.",
                "texto": "Nenhuma verificação com critério reprovou."
                if resumo.passaram or resumo.atencao
                else "Nenhuma verificação com critério foi avaliada.",
                "tom": "ok" if resumo.passaram or resumo.atencao else "neutro",
            }
        )
    if resumo.atencao:
        blocos.append(
            {
                "tipo": "subtitulo",
                "texto": f"Atenção — passou com ressalva ou precisa de conferência ({len(resumo.atencao)})",
                "tom": "atencao",
            }
        )
        blocos.append(
            {
                "tipo": "tabela",
                **tabela_de_verificacoes(
                    resumo.atencao,
                    legenda="Verificações que o módulo marcou como atenção.",
                    tom="atencao",
                    formatar=formatar,
                ),
            }
        )
    if resumo.nao_avaliadas:
        blocos.append(
            {
                "tipo": "subtitulo",
                "texto": f"Não avaliadas ({len(resumo.nao_avaliadas)})",
                "tom": "atencao",
            }
        )
        blocos.append(
            {
                "tipo": "bullets",
                "itens": [
                    decimal_ptbr(f"{linha.nome}: {linha.formula}" if linha.formula else linha.nome)
                    for linha in resumo.nao_avaliadas
                ],
            }
        )
    if livres:
        blocos.append({"tipo": "subtitulo", "texto": "Conferir antes de emitir", "tom": "atencao"})
        blocos.append({"tipo": "bullets", "itens": livres})
    return blocos


def capitulo_de_verificacoes(
    registro: Mapping[str, Any],
    linhas: Sequence[Linha],
    *,
    titulo: str,
    nivel: int,
    peca: str,
    formatar: Formatador,
    rotular: Callable[[str], str],
    base_repetida_de: str | None = None,
    imagens: Sequence[Mapping[str, Any]] = (),
    aviso_imagens: str = "",
) -> dict[str, Any]:
    """O capítulo completo de uma análise com tabela de verificações (ver o docstring do módulo)."""
    resumo = resumir(linhas)
    blocos: list[dict[str, Any]] = [
        {
            "tipo": "destaque",
            "rotulo": f"Resultado: {resumo.resultado}.",
            "texto": texto_do_resultado(registro, resumo, formatar),
            "tom": resumo.tom,
            "manter_com_proximo": True,
        }
    ]
    quando = _data_legivel(registro.get("criado_em"))
    identificacao = (
        f"Módulo: {registro.get('modulo') or '-'}. Peça: {peca}. "
        f"Situação registrada: {registro.get('status') or '-'}."
        + (f" Registrado em {quando}." if quando else "")
    )
    blocos.append({"tipo": "paragrafo", "texto": identificacao})
    if aviso_imagens:
        blocos.append({"tipo": "paragrafo", "texto": aviso_imagens})

    pares = pares_de_entrada(registro, formatar, rotular)
    if pares:
        blocos.append({"tipo": "tabela", **tabela_de_entradas(pares, legenda="Dados de entrada.")})
    blocos.extend(_base_do_calculo(registro, equacoes_gerais(registro, linhas), base_repetida_de))
    blocos.extend({"tipo": "imagem", **imagem} for imagem in imagens)

    blocos.append(
        {"tipo": "subtitulo", "texto": f"O que passou ({len(resumo.passaram)})", "tom": "ok"}
    )
    if resumo.passaram:
        blocos.append(
            {
                "tipo": "tabela",
                **tabela_de_verificacoes(
                    resumo.passaram,
                    legenda="Aprov. = solicitante ÷ resistente; até 100% a verificação passa.",
                    tom="ok",
                    formatar=formatar,
                ),
            }
        )
    else:
        blocos.append({"tipo": "paragrafo", "texto": "Nenhuma verificação com critério passou."})
    if resumo.informativas:
        blocos.append(
            {
                "tipo": "tabela",
                **tabela_de_apoio(
                    resumo.informativas,
                    legenda="Valores de apoio ao cálculo (sem critério de aceitação).",
                    formatar=formatar,
                ),
            }
        )
    resultados = registro.get("resultados")
    paredes = resultados.get("esbeltez_paredes") if isinstance(resultados, Mapping) else None
    if isinstance(paredes, Sequence) and not isinstance(paredes, (str, bytes)) and paredes:
        blocos.append({"tipo": "tabela", **_tabela_de_paredes(paredes, formatar)})
    blocos.extend({"tipo": "tabela", **tabela} for tabela in tabelas_do_registro(registro))
    outros = pares_de_resultados(registro, formatar, rotular)
    if outros:
        blocos.append(
            {
                "tipo": "tabela",
                **tabela_de_entradas(
                    outros, legenda="Outros resultados registrados.", rotulo="Resultado"
                ),
            }
        )
    blocos.extend(_bloco_nao_passou(registro, linhas, resumo, formatar))
    return {"titulo": titulo, "nivel": nivel, "blocos": blocos}


def tabelas_do_registro(registro: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Tabelas prontas que o módulo guardou em ``resultados["tabelas_memorial"]``.

    Cada uma traz ``legenda``, ``cabecalhos`` e ``linhas`` (textos já formatados) e, se quiser,
    ``larguras`` (que somam a largura útil) e ``fonte``. Tabela malformada é ignorada: o capítulo
    nunca deixa de sair por causa de uma tabela de apoio.
    """
    resultados = registro.get("resultados")
    bruto = resultados.get("tabelas_memorial") if isinstance(resultados, Mapping) else None
    if not isinstance(bruto, Sequence) or isinstance(bruto, (str, bytes)):
        return []
    tabelas: list[dict[str, Any]] = []
    for item in bruto:
        if not isinstance(item, Mapping):
            continue
        cabecalhos = item.get("cabecalhos")
        linhas = item.get("linhas")
        if (
            not isinstance(cabecalhos, Sequence)
            or isinstance(cabecalhos, (str, bytes))
            or not cabecalhos
            or not isinstance(linhas, Sequence)
            or isinstance(linhas, (str, bytes))
        ):
            continue
        n = len(cabecalhos)
        linhas_texto = [
            [str(celula) for celula in linha][:n] + [""] * (n - len(linha))
            for linha in linhas
            if isinstance(linha, Sequence) and not isinstance(linha, (str, bytes))
        ]
        larguras = item.get("larguras")
        if not (isinstance(larguras, Sequence) and len(larguras) == n):
            larguras = [round(9360 / n)] * n
        tabelas.append(
            {
                "legenda": decimal_ptbr(str(item.get("legenda") or "")),
                "cabecalhos": [str(c) for c in cabecalhos],
                "linhas": linhas_texto or [["-"] * n],
                "larguras": [int(x) for x in larguras],
                "fonte": float(item.get("fonte") or 7.2),
            }
        )
    return tabelas


def _tabela_de_paredes(paredes: Sequence[Any], formatar: Formatador) -> dict[str, Any]:
    linhas = []
    for item in paredes:
        if not isinstance(item, Mapping):
            continue
        linhas.append(
            [
                formatar(item.get("elemento")),
                formatar(item.get("tipo")),
                formatar(item.get("razao")),
                formatar(item.get("limite_r")),
                formatar(item.get("grupo")),
                formatar(item.get("esbelto")),
            ]
        )
    return {
        "legenda": "Esbeltez local das paredes da seção (flambagem local).",
        "cabecalhos": ["Elemento", "Tipo", "b/t", "Limite (b/t)lim", "Grupo", "Esbelto"],
        "linhas": linhas or [["-", "-", "-", "-", "-", "-"]],
        "larguras": [2400, 1000, 1200, 1700, 1860, 1200],
        "fonte": 7.4,
    }
