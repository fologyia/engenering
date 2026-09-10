"""Cadastro de perfis: catálogos de referência e perfis do usuário.

O programa nasceu com um catálogo geométrico embutido em código. Este módulo
acrescenta duas camadas por cima, sem tocar naquele:

* **catálogos de referência** — arquivos JSON distribuídos junto do programa,
  como a tabela de bitolas de um fabricante. São somente leitura: se o
  usuário pudesse apagá-los, a próxima atualização os traria de volta e a
  exclusão pareceria não ter funcionado;
* **perfis do usuário** — cadastrados na interface e gravados em
  ``data/perfis_usuario.json``. Esses podem ser editados e removidos.

Os três níveis são fundidos em um único catálogo, com o perfil do usuário
tendo prioridade sobre o de referência de mesmo nome: quem cadastra um
perfil com o nome de um existente está corrigindo aquele valor para o seu
uso, e o programa respeita isso em vez de recusar em silêncio.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.steel_sections import CATALOGO_PERFIS, PerfilAco

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
ARQUIVO_USUARIO = PASTA_DADOS / "perfis_usuario.json"
PADRAO_REFERENCIA = "perfis_ref_*.json"

SCHEMA = "mecanica-toolkit/catalogo-perfis/v1"

ORIGEM_EMBUTIDO = "Catálogo geométrico do programa"
ORIGEM_USUARIO = "Cadastrado no programa"

# Campos numéricos de PerfilAco, em ordem, com o rótulo e a unidade que a
# interface mostra. A unidade é sempre a interna (mm), porque converter em
# dois lugares diferentes é como se criam dois valores para a mesma peça.
CAMPOS_NUMERICOS: tuple[tuple[str, str, str], ...] = (
    ("area_mm2", "Área", "mm²"),
    ("ix_mm4", "Momento de inércia Ix", "mm⁴"),
    ("iy_mm4", "Momento de inércia Iy", "mm⁴"),
    ("zx_mm3", "Módulo plástico Zx", "mm³"),
    ("zy_mm3", "Módulo plástico Zy", "mm³"),
    ("j_mm4", "Constante de torção J", "mm⁴"),
    ("cw_mm6", "Constante de empenamento Cw", "mm⁶"),
    ("altura_mm", "Altura d", "mm"),
    ("largura_mm", "Largura bf", "mm"),
    ("espessura_alma_mm", "Espessura da alma tw", "mm"),
    ("espessura_mesa_mm", "Espessura da mesa tf", "mm"),
    ("area_cisalhamento_mm2", "Área de cisalhamento", "mm²"),
    ("massa_kg_m", "Massa linear", "kg/m"),
)

_OBRIGATORIOS_POSITIVOS = (
    "area_mm2",
    "ix_mm4",
    "iy_mm4",
    "altura_mm",
    "largura_mm",
    "espessura_alma_mm",
    "espessura_mesa_mm",
)


class ErroDeCatalogo(ValueError):
    """Perfil inválido ou operação não permitida sobre o catálogo."""


@dataclass(frozen=True, slots=True)
class PerfilCadastrado:
    """Um perfil com a procedência anexada."""

    perfil: PerfilAco
    origem: str
    editavel: bool
    observacoes: str = ""
    atualizado_em: str = ""


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------


def _numero(nome: str, valor: Any, *, positivo: bool = False) -> float:
    try:
        convertido = float(valor)
    except (TypeError, ValueError):
        raise ErroDeCatalogo(f"{nome} deve ser um número; recebi {valor!r}.") from None
    if not math.isfinite(convertido):
        raise ErroDeCatalogo(f"{nome} deve ser um número finito.")
    if positivo and convertido <= 0:
        raise ErroDeCatalogo(f"{nome} deve ser maior que zero.")
    if not positivo and convertido < 0:
        raise ErroDeCatalogo(f"{nome} não pode ser negativo.")
    return convertido


def perfil_de_dicionario(dados: Mapping[str, Any]) -> PerfilAco:
    """Constrói um :class:`PerfilAco` validando os campos."""
    nome = str(dados.get("nome", "")).strip()
    if not nome:
        raise ErroDeCatalogo("O perfil precisa de um nome.")
    familia = str(dados.get("familia", "")).strip() or "Personalizado"

    valores: dict[str, Any] = {"nome": nome, "familia": familia}
    for campo, rotulo, unidade in CAMPOS_NUMERICOS:
        valores[campo] = _numero(
            f"{rotulo} ({unidade})",
            dados.get(campo, 0.0),
            positivo=campo in _OBRIGATORIOS_POSITIVOS,
        )
    valores["descricao"] = str(dados.get("descricao", "")).strip()

    if valores["espessura_mesa_mm"] * 2 >= valores["altura_mm"]:
        raise ErroDeCatalogo(
            "As mesas não cabem na altura informada: 2·tf precisa ser menor que d."
        )
    return PerfilAco(**valores)


def conferir_coerencia(perfil: PerfilAco) -> list[str]:
    """Avisos de coerência interna — não bloqueiam, mas apontam digitação errada.

    Um raio de giração que não bate com ``sqrt(I/A)`` é quase sempre coluna
    trocada ou vírgula fora de lugar. Como o catálogo pode legitimamente
    trazer valores com arredondamento e raio de concordância, isto é aviso e
    não erro.
    """
    avisos: list[str] = []
    for eixo, inercia, dimensao in (
        ("x", perfil.ix_mm4, perfil.altura_mm),
        ("y", perfil.iy_mm4, perfil.largura_mm),
    ):
        modulo_elastico = inercia / (dimensao / 2.0)
        plastico = perfil.zx_mm3 if eixo == "x" else perfil.zy_mm3
        if plastico > 0 and not (1.0 <= plastico / modulo_elastico <= 1.8):
            avisos.append(
                f"Z{eixo}/W{eixo} = {plastico / modulo_elastico:.2f} está fora da "
                "faixa usual de 1,0 a 1,8 para perfis metálicos."
            )
    if perfil.iy_mm4 > perfil.ix_mm4:
        avisos.append(
            "Iy é maior que Ix: confira se os eixos não foram trocados."
        )
    if perfil.massa_kg_m > 0:
        # Aço a 7 850 kg/m³: massa esperada = área × densidade.
        esperada = perfil.area_mm2 * 7_850.0 / 1_000_000.0
        if abs(perfil.massa_kg_m - esperada) > 0.12 * max(esperada, 1e-9):
            avisos.append(
                f"A massa informada ({perfil.massa_kg_m:.2f} kg/m) difere mais de "
                f"12% da massa da área em aço ({esperada:.2f} kg/m)."
            )
    if perfil.area_cisalhamento_mm2 > perfil.area_mm2:
        avisos.append("A área de cisalhamento é maior que a área total.")
    return avisos


# ---------------------------------------------------------------------------
# Leitura e gravação
# ---------------------------------------------------------------------------


def _ler_arquivo(caminho: Path) -> dict[str, Any]:
    if not caminho.exists():
        return {"schema": SCHEMA, "origem": "", "perfis": []}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ErroDeCatalogo(
            f"Não foi possível ler o catálogo {caminho.name}: {erro}"
        ) from erro
    if not isinstance(dados, Mapping) or not isinstance(dados.get("perfis"), list):
        raise ErroDeCatalogo(
            f"O catálogo {caminho.name} não tem o formato esperado "
            "(objeto com a lista 'perfis')."
        )
    return dict(dados)


def _gravar_arquivo(caminho: Path, documento: Mapping[str, Any]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # Escrita em arquivo temporário e troca: um desligamento no meio da
    # gravação não pode deixar o catálogo do usuário truncado.
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    temporario.replace(caminho)


def catalogos_de_referencia() -> list[Path]:
    """Arquivos de catálogo distribuídos junto do programa."""
    return sorted(PASTA_DADOS.glob(PADRAO_REFERENCIA))


def _carregar(caminho: Path, *, editavel: bool) -> dict[str, PerfilCadastrado]:
    documento = _ler_arquivo(caminho)
    origem_padrao = str(documento.get("origem") or caminho.stem)
    resultado: dict[str, PerfilCadastrado] = {}
    for item in documento["perfis"]:
        if not isinstance(item, Mapping):
            continue
        try:
            perfil = perfil_de_dicionario(item)
        except ErroDeCatalogo:
            # Um perfil corrompido não pode impedir o programa de abrir; ele
            # simplesmente não entra no catálogo.
            continue
        resultado[perfil.nome] = PerfilCadastrado(
            perfil=perfil,
            origem=str(item.get("origem") or origem_padrao),
            editavel=editavel,
            observacoes=str(item.get("observacoes", "")),
            atualizado_em=str(item.get("atualizado_em", "")),
        )
    return resultado


def listar_cadastrados() -> dict[str, PerfilCadastrado]:
    """Catálogo completo: embutidos, de referência e do usuário.

    A ordem de sobreposição é deliberada: o perfil do usuário vence o de
    referência, que vence o embutido. Cadastrar com um nome existente é
    corrigir aquele valor, não um erro.
    """
    completo: dict[str, PerfilCadastrado] = {
        nome: PerfilCadastrado(perfil=perfil, origem=ORIGEM_EMBUTIDO, editavel=False)
        for nome, perfil in CATALOGO_PERFIS.items()
    }
    for caminho in catalogos_de_referencia():
        completo.update(_carregar(caminho, editavel=False))
    completo.update(_carregar(ARQUIVO_USUARIO, editavel=True))
    return completo


def listar_perfis() -> dict[str, PerfilAco]:
    """Catálogo completo no formato que os módulos de cálculo consomem."""
    return {nome: item.perfil for nome, item in listar_cadastrados().items()}


def obter(nome: str) -> PerfilCadastrado:
    catalogo = listar_cadastrados()
    if nome in catalogo:
        return catalogo[nome]
    parecidos = [
        chave
        for chave in catalogo
        if str(nome).strip().casefold() in chave.casefold()
    ][:6]
    sugestao = f" Parecidos: {'; '.join(parecidos)}." if parecidos else ""
    raise ErroDeCatalogo(f"Perfil {nome!r} não está no catálogo.{sugestao}")


def obter_perfil(nome: str) -> PerfilAco:
    """Perfil do catálogo completo, com a mesma assinatura da versão embutida."""
    return obter(nome).perfil


# ---------------------------------------------------------------------------
# Cadastro e exclusão
# ---------------------------------------------------------------------------


def salvar_perfil(
    dados: Mapping[str, Any],
    *,
    origem: str = ORIGEM_USUARIO,
    observacoes: str = "",
    substituir: bool = True,
) -> PerfilCadastrado:
    """Cadastra ou atualiza um perfil do usuário."""
    perfil = perfil_de_dicionario(dados)
    documento = _ler_arquivo(ARQUIVO_USUARIO)
    perfis = [
        item
        for item in documento["perfis"]
        if isinstance(item, Mapping) and str(item.get("nome")) != perfil.nome
    ]
    if len(perfis) != len(documento["perfis"]) and not substituir:
        raise ErroDeCatalogo(
            f"Já existe um perfil do usuário chamado {perfil.nome!r}."
        )
    registro = {
        **asdict(perfil),
        "origem": origem or ORIGEM_USUARIO,
        "observacoes": observacoes,
        "atualizado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    perfis.append(registro)
    perfis.sort(key=lambda item: str(item.get("nome", "")).casefold())
    _gravar_arquivo(
        ARQUIVO_USUARIO,
        {"schema": SCHEMA, "origem": ORIGEM_USUARIO, "perfis": perfis},
    )
    return PerfilCadastrado(
        perfil=perfil,
        origem=registro["origem"],
        editavel=True,
        observacoes=observacoes,
        atualizado_em=registro["atualizado_em"],
    )


def remover_perfil(nome: str) -> None:
    """Exclui um perfil do usuário.

    Perfis embutidos e de catálogos de referência não podem ser excluídos: a
    exclusão não sobreviveria à próxima atualização do programa, e um botão
    que desfaz sozinho é pior do que um botão que não existe.
    """
    nome = str(nome).strip()
    documento = _ler_arquivo(ARQUIVO_USUARIO)
    restantes = [
        item
        for item in documento["perfis"]
        if isinstance(item, Mapping) and str(item.get("nome")) != nome
    ]
    if len(restantes) == len(documento["perfis"]):
        catalogo = listar_cadastrados()
        if nome in catalogo:
            raise ErroDeCatalogo(
                f"{nome!r} vem de {catalogo[nome].origem} e não pode ser excluído. "
                "Cadastre um perfil com outro nome, ou com o mesmo nome para "
                "sobrepor os valores no seu uso."
            )
        raise ErroDeCatalogo(f"Perfil {nome!r} não está cadastrado.")
    _gravar_arquivo(
        ARQUIVO_USUARIO,
        {"schema": SCHEMA, "origem": ORIGEM_USUARIO, "perfis": restantes},
    )


def importar_lote(
    entradas: Iterable[Mapping[str, Any]],
    *,
    origem: str,
    observacoes: str = "",
) -> tuple[list[str], list[tuple[str, str]]]:
    """Cadastra vários perfis de uma vez.

    Devolve ``(cadastrados, rejeitados)``, com o motivo de cada rejeição: um
    lote é aceito parcialmente de propósito, porque perder trinta perfis bons
    por causa de uma linha malformada seria pior do que importar os trinta e
    avisar sobre a linha.
    """
    aceitos: list[str] = []
    rejeitados: list[tuple[str, str]] = []
    documento = _ler_arquivo(ARQUIVO_USUARIO)
    perfis = [item for item in documento["perfis"] if isinstance(item, Mapping)]
    por_nome = {str(item.get("nome")): item for item in perfis}
    agora = datetime.now().astimezone().isoformat(timespec="seconds")

    for entrada in entradas:
        rotulo = str(entrada.get("nome", "")).strip() or "(sem nome)"
        try:
            perfil = perfil_de_dicionario(entrada)
        except ErroDeCatalogo as erro:
            rejeitados.append((rotulo, str(erro)))
            continue
        por_nome[perfil.nome] = {
            **asdict(perfil),
            "origem": str(entrada.get("origem") or origem),
            "observacoes": str(entrada.get("observacoes") or observacoes),
            "atualizado_em": agora,
        }
        aceitos.append(perfil.nome)

    ordenados = sorted(por_nome.values(), key=lambda item: str(item["nome"]).casefold())
    _gravar_arquivo(
        ARQUIVO_USUARIO,
        {"schema": SCHEMA, "origem": ORIGEM_USUARIO, "perfis": ordenados},
    )
    return aceitos, rejeitados


def catalogo_dataframe():
    """Catálogo completo como tabela, com a procedência de cada perfil.

    Espelha ``core.steel_sections.catalogo_dataframe`` acrescentando de onde
    o perfil veio — sem isso, a interface não teria como dizer quais podem
    ser excluídos.
    """
    import pandas as pd

    linhas = []
    for nome, item in listar_cadastrados().items():
        perfil = item.perfil
        linhas.append(
            {
                "nome": nome,
                "familia": perfil.familia,
                "origem": item.origem,
                "editavel": item.editavel,
                "massa_kg_m": perfil.massa_kg_m,
                "area_mm2": perfil.area_mm2,
                "altura_mm": perfil.altura_mm,
                "largura_mm": perfil.largura_mm,
                "espessura_alma_mm": perfil.espessura_alma_mm,
                "espessura_mesa_mm": perfil.espessura_mesa_mm,
                "ix_mm4": perfil.ix_mm4,
                "iy_mm4": perfil.iy_mm4,
                "zx_mm3": perfil.zx_mm3,
                "zy_mm3": perfil.zy_mm3,
                "j_mm4": perfil.j_mm4,
                "cw_mm6": perfil.cw_mm6,
                # Colunas derivadas da versão embutida: manter o mesmo conjunto
                # permite este catálogo substituir aquele sem que as páginas
                # que já leem a tabela precisem ser reescritas.
                "sx_mm3": perfil.sx_mm3,
                "sy_mm3": perfil.sy_mm3,
                "rx_mm": perfil.rx_mm,
                "ry_mm": perfil.ry_mm,
                "area_cisalhamento_mm2": perfil.area_cisalhamento_mm2,
                "descricao": perfil.descricao,
            }
        )
    tabela = pd.DataFrame(linhas)
    if not tabela.empty:
        tabela = tabela.sort_values(["familia", "nome"]).reset_index(drop=True)
    return tabela


def resumo_do_catalogo() -> dict[str, int]:
    """Quantidade de perfis por procedência."""
    contagem: dict[str, int] = {}
    for item in listar_cadastrados().values():
        contagem[item.origem] = contagem.get(item.origem, 0) + 1
    return dict(sorted(contagem.items(), key=lambda par: (-par[1], par[0])))
