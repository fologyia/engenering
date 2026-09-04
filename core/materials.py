"""Acesso e validação da base local de materiais."""
from pathlib import Path

import pandas as pd


CAMINHO_CSV = Path(__file__).resolve().parent.parent / "data" / "materials.csv"
COLUNAS_OBRIGATORIAS = {"nome", "categoria", "Sut_MPa", "Sy_MPa", "observacao"}


def carregar_materiais() -> pd.DataFrame:
    """Carrega a base de materiais validando seu esquema mínimo."""
    if not CAMINHO_CSV.exists():
        raise FileNotFoundError(f"Base de materiais não encontrada: {CAMINHO_CSV}")

    df = pd.read_csv(CAMINHO_CSV)
    faltantes = COLUNAS_OBRIGATORIAS.difference(df.columns)
    if faltantes:
        raise ValueError(
            "Base de materiais inválida. Colunas ausentes: "
            + ", ".join(sorted(faltantes))
        )
    if df.empty:
        raise ValueError("A base de materiais está vazia.")
    if df["nome"].duplicated().any():
        raise ValueError("A base de materiais contém nomes duplicados.")
    if (df["Sut_MPa"] <= 0).any() or (df["Sy_MPa"] < 0).any():
        raise ValueError("A base contém propriedades mecânicas inválidas.")
    if ((df["Sy_MPa"] > 0) & (df["Sy_MPa"] > df["Sut_MPa"])).any():
        raise ValueError("A base contém material com Sy maior que Sut.")
    return df


def listar_nomes() -> list[str]:
    return carregar_materiais()["nome"].tolist()


def obter_material(nome: str) -> dict:
    """Retorna os dados de um material pelo nome exato."""
    df = carregar_materiais()
    linha = df[df["nome"] == nome]
    if linha.empty:
        raise ValueError(f"Material '{nome}' não encontrado na base.")
    dados = linha.iloc[0].to_dict()
    # Compatibilidade com os módulos antigos: deixa explícito que o CSV é uma
    # fonte orientativa, e não um certificado de propriedades do lote real.
    dados.update(
        {
            "nivel_confianca": "Referência",
            "origem_tipo": "Valor típico / estimativa",
            "fonte_controlada": False,
            "aviso_rastreabilidade": (
                "Confirmar forma do produto, condição, espessura, temperatura e "
                "propriedades em certificado, norma ou ensaio aplicável."
            ),
        }
    )
    return dados
