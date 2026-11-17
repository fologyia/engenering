"""Linha de verificação (solicitante × resistente) e as tabelas que a exibem e exportam.

Compartilhado pelos módulos que fecham o cálculo numa tabela de oito colunas — ligações
parafusadas (:mod:`core.bolted_joint_check`) e barras comprimidas
(:mod:`core.column_buckling`):

    Verificação | Solicitante | Resistente | Unidade | Aproveitamento | Status | Fórmula | Referência

Status possíveis: ``OK``, ``NÃO OK``, ``ALERTA`` (atende com ressalva ou não pôde ser
calculado), ``INFO`` (grandeza informativa, sem critério) e ``N/A`` (não se aplica).
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

#: Quanto cada status pesa no status geral: o pior vence.
ORDEM_STATUS = {"NÃO OK": 4, "ALERTA": 3, "OK": 2, "INFO": 1, "N/A": 0}

#: Como o registro técnico (e o memorial) nomeia a situação de cada status geral.
STATUS_REGISTRO = {"OK": "Atende", "ALERTA": "Atenção", "NÃO OK": "Não atende", "N/A": "Pendente"}

COLUNAS_TABELA = (
    "Verificação",
    "Solicitante",
    "Resistente",
    "Unidade",
    "Aproveitamento",
    "Status",
    "Fórmula",
    "Referência",
)


@dataclass
class Verificacao:
    """Uma linha da tabela.

    ``tipo`` diz como a linha entra no resumo: ``"resistencia"`` (a razão
    solicitante/resistente conta para o aproveitamento máximo), ``"limite"`` (só
    OK/NÃO OK) ou ``"informativo"`` (valor mostrado, sem critério). ``obrigatoria`` é falso na boa
    prática: passar do limite dela pede atenção, mas não reprova.
    """

    nome: str
    solicitante: float | None
    resistente: float | None
    unidade: str
    referencia: str
    formula: str = ""
    status: str = ""  # "OK", "NÃO OK", "ALERTA", "N/A", "INFO"
    aproveitamento: float | None = None
    tipo: str = "resistencia"
    obrigatoria: bool = True
    # as contas em notação linear (índice com "_"), para o memorial as escrever como equações do
    # Word: a fórmula simbólica e a mesma com os números (core.equacao_word)
    equacoes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.status:
            if self.solicitante is None or self.resistente is None:
                self.status = "N/A"
            else:
                # Resistência nula OU NEGATIVA (por exemplo ℓ_f ≤ 0) reprova: a divisão
                # devolveria um aproveitamento negativo, que o teste "<= 1" aceitaria.
                self.aproveitamento = (
                    self.solicitante / self.resistente if self.resistente > 0 else math.inf
                )
                self.status = "OK" if self.aproveitamento <= 1.0 + 1e-9 else "NÃO OK"


def status_geral(verificacoes: Sequence[Verificacao]) -> str:
    """NÃO OK > ALERTA > OK. INFO e N/A não decidem; sem nenhuma linha decisiva, N/A."""
    decisivos = [v.status for v in verificacoes if v.status in ("NÃO OK", "ALERTA", "OK")]
    if not decisivos:
        return "N/A"
    return max(decisivos, key=lambda status: ORDEM_STATUS[status])


def formatar_percentual(valor: float | None) -> str:
    if valor is None:
        return "—"
    return "∞" if math.isinf(valor) else f"{100 * valor:.0f}%"


def tabela_verificacoes(verificacoes: Sequence[Verificacao]) -> list[dict[str, Any]]:
    """Linhas da tabela de saída; aproveitamento em % (None quando não se aplica)."""
    return [
        {
            "Verificação": v.nome,
            "Solicitante": v.solicitante,
            "Resistente": v.resistente,
            "Unidade": v.unidade,
            "Aproveitamento": None if v.aproveitamento is None else 100.0 * v.aproveitamento,
            "Status": v.status,
            "Fórmula": v.formula,
            "Referência": v.referencia,
        }
        for v in verificacoes
    ]


def casas_coerentes(v: Verificacao, casas: int = 2, maximo: int = 6) -> int:
    """Casas decimais para mostrar solicitante e resistente sem contradizer o status.

    O status compara os valores sem arredondar: 16,004 mm contra 16 mm reprova, e com 2 casas a
    tela mostraria "16,00 / 16,00". Aqui as casas aumentam até a diferença aparecer (reprova:
    solicitante > resistente; passa: solicitante ≤ resistente).
    """
    s, r = v.solicitante, v.resistente
    if s is None or r is None or v.status not in ("OK", "NÃO OK"):
        return casas
    if not (math.isfinite(s) and math.isfinite(r)) or r <= 0:
        return casas
    reprova = v.status == "NÃO OK"
    for k in range(casas, maximo + 1):
        if (round(s, k) > round(r, k)) == reprova:
            return k
    return maximo


def percentual_coerente(v: Verificacao) -> str:
    """O aproveitamento em % sem mostrar "100 %" numa linha que reprova por pouco."""
    a = v.aproveitamento
    if a is None or math.isinf(a) or math.isnan(a):
        return "—"
    for k in range(0, 4):
        texto = f"{100 * a:.{k}f}"
        if v.status != "NÃO OK" or float(texto) > 100.0:
            return texto.replace(".", ",") + " %"
    return f"{100 * a:.3f}".replace(".", ",") + " %"


def numero_json(valor: float | None, casas: int = 3) -> float | str:
    """Número arredondado, ou texto quando não houver número (o hash do registro proíbe NaN/∞)."""
    if valor is None or math.isnan(valor):
        return "—"
    return "∞" if math.isinf(valor) else round(valor, casas)


def linhas_para_registro(verificacoes: Sequence[Verificacao]) -> list[dict[str, Any]]:
    """Mesma tabela, em chaves que o memorial (Word/PDF) transforma em colunas legíveis."""
    return [
        {
            "verificação": v.nome,
            "solicitante": numero_json(v.solicitante, max(3, casas_coerentes(v, 3))),
            "resistente": numero_json(v.resistente, max(3, casas_coerentes(v, 3))),
            "unidade": v.unidade,
            "aproveitamento_pct": numero_json(
                None if v.aproveitamento is None else 100.0 * v.aproveitamento,
                1 if v.status != "NÃO OK" or round(100.0 * (v.aproveitamento or 0), 1) > 100 else 3,
            ),
            "status": v.status,
            "fórmula": v.formula or "—",
            "referência": v.referencia,
            **({"equações": list(v.equacoes)} if v.equacoes else {}),
        }
        for v in verificacoes
    ]


def csv_verificacoes(verificacoes: Sequence[Verificacao]) -> bytes:
    """CSV (UTF-8 com BOM, aberto direto no Excel) com as oito colunas da tabela."""
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\r\n")
    cabecalho = [("Aproveitamento (%)" if c == "Aproveitamento" else c) for c in COLUNAS_TABELA]
    escritor.writerow(cabecalho)
    for linha in tabela_verificacoes(verificacoes):
        escritor.writerow(
            [
                ""
                if linha[c] is None
                else (f"{linha[c]:.3f}" if isinstance(linha[c], float) else linha[c])
                for c in COLUNAS_TABELA
            ]
        )
    return saida.getvalue().encode("utf-8-sig")
