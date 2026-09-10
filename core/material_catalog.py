"""Cadastro de materiais metálicos: base, catálogos de critério e do usuário.

Mesma estrutura em três camadas do cadastro de perfis
(:mod:`core.section_catalog`), pelo mesmo motivo: o programa nasceu com uma
base fixa em ``data/materials.csv`` e não havia como acrescentar o aço que o
projeto de fato usa.

* **base do programa** — ``data/materials.csv``, orientativa;
* **catálogos de critério** — ``data/materiais_ref_*.json`` distribuídos
  junto do programa, tipicamente a tabela de materiais de um critério de
  projeto corporativo. São somente leitura;
* **materiais do usuário** — ``data/materiais_usuario.json``, editáveis e
  removíveis.

A diferença em relação aos perfis está no que um critério de projeto
acrescenta: ele não diz só *quais* materiais existem, mas **para que
aplicação cada um é permitido**. Por isso um material de catálogo carrega
``aplicacoes`` e ``criterio``, e a interface pode responder à pergunta que o
projetista realmente faz — "que aço posso usar num perfil laminado neste
projeto?".

Atenção à procedência: um critério de projeto especifica a **designação** e
a norma, não as propriedades mecânicas. Os valores de Sy e Sut vêm da norma
citada e ficam marcados como tal em ``origem_propriedades``; nunca são
atribuídos ao critério.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core import materials as base_csv

PASTA_DADOS = Path(__file__).resolve().parent.parent / "data"
ARQUIVO_USUARIO = PASTA_DADOS / "materiais_usuario.json"
PADRAO_REFERENCIA = "materiais_ref_*.json"

SCHEMA = "mecanica-toolkit/catalogo-materiais/v1"

ORIGEM_BASE = "Base orientativa do programa"
ORIGEM_USUARIO = "Cadastrado no programa"

CATEGORIAS = (
    "aco",
    "aco_inox",
    "aluminio",
    "cobre",
    "ferro_fundido",
    "titanio",
    "outro",
)

AVISO_PADRAO = (
    "Confirmar forma do produto, condição, espessura, temperatura e "
    "propriedades em certificado, norma ou ensaio aplicável."
)


class ErroDeMaterial(ValueError):
    """Material inválido ou operação não permitida sobre o catálogo."""


@dataclass(frozen=True, slots=True)
class MaterialCadastrado:
    """Um material com procedência, aplicações permitidas e critério."""

    nome: str
    categoria: str
    sy_MPa: float
    sut_MPa: float
    origem: str
    editavel: bool
    origem_propriedades: str = ""
    criterio: str = ""
    aplicacoes: tuple[str, ...] = ()
    protecao: str = ""
    observacao: str = ""
    atualizado_em: str = ""

    @property
    def relacao_sy_sut(self) -> float:
        return self.sy_MPa / self.sut_MPa if self.sut_MPa else 0.0

    @property
    def sem_escoamento_definido(self) -> bool:
        """Material frágil: rompe sem patamar de escoamento (Sy tabelado zero)."""
        return self.sy_MPa == 0.0

    def como_dicionario(self) -> dict[str, Any]:
        """Formato compatível com ``core.materials.obter_material``."""
        return {
            "nome": self.nome,
            "categoria": self.categoria,
            "Sy_MPa": self.sy_MPa,
            "Sut_MPa": self.sut_MPa,
            "observacao": self.observacao,
            "origem": self.origem,
            "origem_propriedades": self.origem_propriedades,
            "criterio": self.criterio,
            "aplicacoes": list(self.aplicacoes),
            "protecao": self.protecao,
            "nivel_confianca": "Referência",
            "origem_tipo": self.origem_propriedades or "Valor típico / estimativa",
            "fonte_controlada": bool(self.criterio),
            "aviso_rastreabilidade": AVISO_PADRAO,
        }


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------


def _numero(rotulo: str, valor: Any, *, permite_zero: bool = False) -> float:
    try:
        convertido = float(valor)
    except (TypeError, ValueError):
        raise ErroDeMaterial(f"{rotulo} deve ser um número; recebi {valor!r}.") from None
    if not math.isfinite(convertido) or convertido < 0:
        raise ErroDeMaterial(f"{rotulo} deve ser um número finito não negativo.")
    if convertido == 0 and not permite_zero:
        raise ErroDeMaterial(f"{rotulo} deve ser maior que zero.")
    return convertido


def _lista(valor: Any) -> tuple[str, ...]:
    if valor is None or valor == "":
        return ()
    if isinstance(valor, str):
        partes = [parte.strip() for parte in valor.replace(";", ",").split(",")]
    elif isinstance(valor, Sequence):
        partes = [str(parte).strip() for parte in valor]
    else:
        partes = [str(valor).strip()]
    return tuple(parte for parte in partes if parte)


def material_de_dicionario(
    dados: Mapping[str, Any], *, origem: str = ORIGEM_USUARIO, editavel: bool = True
) -> MaterialCadastrado:
    """Constrói um material validando o que o cálculo depende."""
    nome = str(dados.get("nome", "")).strip()
    if not nome:
        raise ErroDeMaterial("O material precisa de uma designação.")

    categoria = str(dados.get("categoria", "")).strip().lower() or "aco"
    if categoria not in CATEGORIAS:
        validas = ", ".join(CATEGORIAS)
        raise ErroDeMaterial(
            f"Categoria {categoria!r} desconhecida. Use uma de: {validas}."
        )

    # Sy zero é físico, não ausência de dado: ferro fundido cinzento e outros
    # materiais frágeis rompem sem patamar de escoamento definido. Recusar o
    # zero apagaria esses materiais da base em silêncio.
    sy = _numero(
        "Limite de escoamento Sy (MPa)", dados.get("Sy_MPa"), permite_zero=True
    )
    sut = _numero("Resistência à tração Sut (MPa)", dados.get("Sut_MPa"))
    if sy > sut:
        raise ErroDeMaterial(
            f"O escoamento ({sy:g} MPa) não pode ser maior que a resistência à "
            f"tração ({sut:g} MPa)."
        )

    return MaterialCadastrado(
        nome=nome,
        categoria=categoria,
        sy_MPa=sy,
        sut_MPa=sut,
        origem=str(dados.get("origem") or origem),
        editavel=editavel,
        origem_propriedades=str(dados.get("origem_propriedades", "")).strip(),
        criterio=str(dados.get("criterio", "")).strip(),
        aplicacoes=_lista(dados.get("aplicacoes")),
        protecao=str(dados.get("protecao", "")).strip(),
        observacao=str(dados.get("observacao", "")).strip(),
        atualizado_em=str(dados.get("atualizado_em", "")).strip(),
    )


def conferir_coerencia(material: MaterialCadastrado) -> list[str]:
    """Avisos que apontam digitação errada sem bloquear o cadastro.

    Aço estrutural tem Sy entre 60% e 90% de Sut; muito fora disso costuma
    ser vírgula fora de lugar ou coluna trocada. Como ligas encruadas e
    parafusos de alta resistência fogem legitimamente dessa faixa, isto é
    aviso e não erro.
    """
    avisos: list[str] = []
    relacao = material.relacao_sy_sut
    if not material.sem_escoamento_definido and material.categoria in {
        "aco",
        "aco_inox",
    }:
        # O piso de 0,30 acomoda o inoxidável austenítico recozido, que fica
        # legitimamente em torno de 0,36 — uma faixa mais estreita acusaria
        # material correto como erro de digitação.
        if not (0.30 <= relacao <= 0.95):
            avisos.append(
                f"Sy/Sut = {relacao:.2f} está fora da faixa usual de 0,30 a 0,95 "
                "para aços; confira as unidades e qual valor é qual."
            )
    if material.sut_MPa > 2_000:
        avisos.append(
            f"Sut de {material.sut_MPa:g} MPa é muito alto para um metal "
            "estrutural; confirme se a unidade é MPa e não psi."
        )
    if material.sem_escoamento_definido:
        avisos.append(
            "Sem limite de escoamento definido: verificações que dependem de Sy "
            "(escoamento, von Mises contra Sy) não se aplicam a este material. "
            "Use um critério de ruptura."
        )
    elif material.sy_MPa < 50:
        avisos.append(
            f"Sy de {material.sy_MPa:g} MPa é muito baixo para um metal; "
            "confirme a unidade."
        )
    if not material.origem_propriedades:
        avisos.append(
            "As propriedades não declaram de onde vieram (norma, certificado "
            "ou ensaio). Sem isso o cálculo não fica rastreável."
        )
    return avisos


# ---------------------------------------------------------------------------
# Leitura e gravação
# ---------------------------------------------------------------------------


def _ler_arquivo(caminho: Path) -> dict[str, Any]:
    if not caminho.exists():
        return {"schema": SCHEMA, "origem": "", "materiais": []}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ErroDeMaterial(
            f"Não foi possível ler o catálogo {caminho.name}: {erro}"
        ) from erro
    if not isinstance(dados, Mapping) or not isinstance(dados.get("materiais"), list):
        raise ErroDeMaterial(
            f"O catálogo {caminho.name} não tem o formato esperado "
            "(objeto com a lista 'materiais')."
        )
    return dict(dados)


def _gravar_arquivo(caminho: Path, documento: Mapping[str, Any]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # Grava em temporário e troca: um desligamento durante a escrita não pode
    # deixar o catálogo do usuário truncado.
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(caminho)


def catalogos_de_criterio() -> list[Path]:
    return sorted(PASTA_DADOS.glob(PADRAO_REFERENCIA))


def _carregar_json(caminho: Path, *, editavel: bool) -> dict[str, MaterialCadastrado]:
    documento = _ler_arquivo(caminho)
    origem_padrao = str(documento.get("origem") or caminho.stem)
    criterio_padrao = str(documento.get("criterio", ""))
    resultado: dict[str, MaterialCadastrado] = {}
    for item in documento["materiais"]:
        if not isinstance(item, Mapping):
            continue
        try:
            material = material_de_dicionario(
                {"criterio": criterio_padrao, **item},
                origem=origem_padrao,
                editavel=editavel,
            )
        except ErroDeMaterial:
            # Um registro corrompido não pode impedir o programa de abrir.
            continue
        resultado[material.nome] = material
    return resultado


def _carregar_base() -> dict[str, MaterialCadastrado]:
    try:
        tabela = base_csv.carregar_materiais()
    except (FileNotFoundError, ValueError):
        return {}
    resultado: dict[str, MaterialCadastrado] = {}
    for linha in tabela.to_dict("records"):
        try:
            material = material_de_dicionario(
                {
                    "nome": linha["nome"],
                    "categoria": linha.get("categoria", "aco"),
                    "Sy_MPa": linha["Sy_MPa"],
                    "Sut_MPa": linha["Sut_MPa"],
                    "observacao": linha.get("observacao", ""),
                    "origem_propriedades": "Valor típico / estimativa",
                },
                origem=ORIGEM_BASE,
                editavel=False,
            )
        except ErroDeMaterial:
            continue
        resultado[material.nome] = material
    return resultado


def listar_cadastrados() -> dict[str, MaterialCadastrado]:
    """Catálogo completo: base, critérios e materiais do usuário.

    A sobreposição segue a mesma regra dos perfis: o material do usuário
    vence o de critério, que vence a base. Cadastrar com um nome existente é
    corrigir aquele valor para o seu uso.
    """
    completo = _carregar_base()
    for caminho in catalogos_de_criterio():
        completo.update(_carregar_json(caminho, editavel=False))
    completo.update(_carregar_json(ARQUIVO_USUARIO, editavel=True))
    return dict(sorted(completo.items(), key=lambda par: par[0].casefold()))


def listar_nomes() -> list[str]:
    """Compatível com ``core.materials.listar_nomes``."""
    return list(listar_cadastrados())


def obter(nome: str) -> MaterialCadastrado:
    catalogo = listar_cadastrados()
    if nome in catalogo:
        return catalogo[nome]
    alvo = str(nome).strip().casefold()
    parecidos = [chave for chave in catalogo if alvo and alvo in chave.casefold()][:6]
    sugestao = f" Parecidos: {'; '.join(parecidos)}." if parecidos else ""
    raise ErroDeMaterial(f"Material {nome!r} não está no catálogo.{sugestao}")


def obter_material(nome: str) -> dict[str, Any]:
    """Compatível com ``core.materials.obter_material``."""
    return obter(nome).como_dicionario()


def carregar_materiais():
    """Compatível com ``core.materials.carregar_materiais``.

    Devolve as colunas da base original mais a procedência, para este módulo
    poder substituir ``core.materials`` sem que cada página que já lê a base
    precise ser reescrita.
    """
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "nome": material.nome,
                "categoria": material.categoria,
                "Sut_MPa": material.sut_MPa,
                "Sy_MPa": material.sy_MPa,
                "observacao": material.observacao,
                "origem": material.origem,
            }
            for material in listar_cadastrados().values()
        ]
    )


# ---------------------------------------------------------------------------
# Aplicações permitidas por critério
# ---------------------------------------------------------------------------


def aplicacoes_disponiveis() -> list[str]:
    """Todas as aplicações citadas pelos critérios carregados."""
    aplicacoes: set[str] = set()
    for material in listar_cadastrados().values():
        aplicacoes.update(material.aplicacoes)
    return sorted(aplicacoes)


def materiais_para(aplicacao: str) -> list[MaterialCadastrado]:
    """Materiais que algum critério permite para a aplicação informada.

    É a pergunta que o projetista faz de verdade: não "quais aços existem",
    mas "qual aço posso usar num perfil laminado neste projeto".
    """
    alvo = str(aplicacao).strip().casefold()
    return [
        material
        for material in listar_cadastrados().values()
        if any(alvo == item.casefold() for item in material.aplicacoes)
    ]


def criterios_carregados() -> list[str]:
    criterios = {
        material.criterio
        for material in listar_cadastrados().values()
        if material.criterio
    }
    return sorted(criterios)


# ---------------------------------------------------------------------------
# Cadastro e exclusão
# ---------------------------------------------------------------------------


def salvar_material(
    dados: Mapping[str, Any], *, origem: str = ORIGEM_USUARIO
) -> MaterialCadastrado:
    """Cadastra ou atualiza um material do usuário."""
    material = material_de_dicionario(dados, origem=origem, editavel=True)
    documento = _ler_arquivo(ARQUIVO_USUARIO)
    materiais = [
        item
        for item in documento["materiais"]
        if isinstance(item, Mapping) and str(item.get("nome")) != material.nome
    ]
    registro = {
        "nome": material.nome,
        "categoria": material.categoria,
        "Sy_MPa": material.sy_MPa,
        "Sut_MPa": material.sut_MPa,
        "origem": material.origem,
        "origem_propriedades": material.origem_propriedades,
        "criterio": material.criterio,
        "aplicacoes": list(material.aplicacoes),
        "protecao": material.protecao,
        "observacao": material.observacao,
        "atualizado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    materiais.append(registro)
    materiais.sort(key=lambda item: str(item.get("nome", "")).casefold())
    _gravar_arquivo(
        ARQUIVO_USUARIO,
        {"schema": SCHEMA, "origem": ORIGEM_USUARIO, "materiais": materiais},
    )
    return material_de_dicionario(registro, origem=material.origem, editavel=True)


def remover_material(nome: str) -> None:
    """Exclui um material do usuário.

    Base e critérios não podem ser excluídos: a exclusão não sobreviveria à
    próxima atualização do programa. Para deixar de usar um material de
    critério, cadastre um com o mesmo nome e os valores que valem no seu
    projeto.
    """
    nome = str(nome).strip()
    documento = _ler_arquivo(ARQUIVO_USUARIO)
    restantes = [
        item
        for item in documento["materiais"]
        if isinstance(item, Mapping) and str(item.get("nome")) != nome
    ]
    if len(restantes) == len(documento["materiais"]):
        catalogo = listar_cadastrados()
        if nome in catalogo:
            raise ErroDeMaterial(
                f"{nome!r} vem de {catalogo[nome].origem} e não pode ser excluído. "
                "Cadastre um material com o mesmo nome para sobrepor os valores "
                "no seu uso."
            )
        raise ErroDeMaterial(f"Material {nome!r} não está cadastrado.")
    _gravar_arquivo(
        ARQUIVO_USUARIO,
        {"schema": SCHEMA, "origem": ORIGEM_USUARIO, "materiais": restantes},
    )


def importar_lote(
    entradas: Iterable[Mapping[str, Any]], *, origem: str
) -> tuple[list[str], list[tuple[str, str]]]:
    """Cadastra vários materiais de uma vez, aceitando o lote parcialmente."""
    aceitos: list[str] = []
    rejeitados: list[tuple[str, str]] = []
    for entrada in entradas:
        rotulo = str(entrada.get("nome", "")).strip() or "(sem nome)"
        try:
            salvar_material(entrada, origem=origem)
        except ErroDeMaterial as erro:
            rejeitados.append((rotulo, str(erro)))
        else:
            aceitos.append(rotulo)
    return aceitos, rejeitados


def catalogo_dataframe():
    """Catálogo completo como tabela, com procedência e aplicações."""
    import pandas as pd

    linhas = [
        {
            "nome": material.nome,
            "categoria": material.categoria,
            "Sy_MPa": material.sy_MPa,
            "Sut_MPa": material.sut_MPa,
            "Sy/Sut": round(material.relacao_sy_sut, 3),
            "origem": material.origem,
            "editavel": material.editavel,
            "criterio": material.criterio,
            "aplicacoes": "; ".join(material.aplicacoes),
            "protecao": material.protecao,
            "origem_propriedades": material.origem_propriedades,
            "observacao": material.observacao,
        }
        for material in listar_cadastrados().values()
    ]
    return pd.DataFrame(linhas)


def resumo_do_catalogo() -> dict[str, int]:
    contagem: dict[str, int] = {}
    for material in listar_cadastrados().values():
        contagem[material.origem] = contagem.get(material.origem, 0) + 1
    return dict(sorted(contagem.items(), key=lambda par: (-par[1], par[0])))
