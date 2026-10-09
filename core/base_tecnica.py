"""Base técnica do projeto: o que se preenche uma vez e as demais páginas leem.

Fica no documento do projeto em ``projeto["base_tecnica"]`` (fora de ``criterios_projeto``, para
não mexer no hash dos critérios que marca registros como desatualizados). Guarda:

* o **critério do cliente** (nenhum ou Anglo American AA-BR-DPST-DR-0001);
* o **local e o vento** (V₀, S₁, categoria do terreno, S₃ pelo grupo da NBR 6123:2023 ou o valor do
  cliente);
* o **tipo de estrutura** que define o limite do deslocamento horizontal sob vento;
* a **sobrecarga** de referência (Tabela 2 do critério Anglo, ou informada), a classe de
  agressividade e a vida útil.

Sem Streamlit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from core import criterio_anglo as ca
from core import vento_nbr6123 as vb

CLIENTE_NENHUM = "nenhum"
CLIENTE_ANGLO = "anglo"
CLIENTES: dict[str, str] = {
    CLIENTE_NENHUM: "Somente as normas (sem critério de cliente)",
    CLIENTE_ANGLO: f"Anglo American — {ca.CODIGO} Rev. {ca.REVISAO}",
}

#: S₃: um dos grupos da Tabela 4 (NBR 6123:2023) ou o valor do critério do cliente.
S3_DO_CLIENTE = "cliente"
OPCOES_S3: tuple[str, ...] = (*[str(g) for g in vb.GRUPOS_S3], S3_DO_CLIENTE)

TIPO_NBR_UM_PAVIMENTO = "NBR — galpão ou edificação de um pavimento"
TIPO_NBR_PAVIMENTOS = "NBR — edificação de dois ou mais pavimentos"
TIPOS_DE_ESTRUTURA: tuple[str, ...] = (
    ca.TIPO_PLATAFORMA,
    ca.TIPO_PIPE_RACK,
    ca.TIPO_COBERTURA,
    TIPO_NBR_UM_PAVIMENTO,
    TIPO_NBR_PAVIMENTOS,
)
CLASSES_DE_AGRESSIVIDADE = ("C1", "C2", "C3", "C4", "C5", "CX")
SOBRECARGA_INFORMADA = "Informada pelo projeto"


@dataclass(frozen=True)
class VentoDoLocal:
    v0_m_s: float = 35.0
    s1: float = 1.0
    categoria: str = "III"
    grupo_s3: str = "3"  # "1".."5" ou "cliente"
    s3_cliente: float | None = None

    @property
    def s3(self) -> float:
        if self.grupo_s3 == S3_DO_CLIENTE:
            if self.s3_cliente is None:
                raise ValueError("S₃ do cliente não informado.")
            return self.s3_cliente
        return vb.fator_s3(int(self.grupo_s3))

    @property
    def texto_s3(self) -> str:
        if self.grupo_s3 == S3_DO_CLIENTE:
            return f"S₃ = {numero(self.s3, 2)} (critério do cliente)"
        return f"S₃ = {numero(self.s3, 2)} (grupo {self.grupo_s3}, NBR 6123:2023 Tabela 4)"


@dataclass(frozen=True)
class BaseTecnica:
    cliente: str = CLIENTE_NENHUM
    local: str = ""
    vento: VentoDoLocal = field(default_factory=VentoDoLocal)
    tipo_de_estrutura: str = ca.TIPO_PLATAFORMA
    sobrecarga_local: str = SOBRECARGA_INFORMADA
    sobrecarga_kN_m2: float = 5.0
    classe_de_agressividade: str = "C3"
    vida_util_anos: float | None = 50.0
    observacoes: str = ""
    atualizado_em: str = ""

    @property
    def anglo(self) -> bool:
        return self.cliente == CLIENTE_ANGLO

    @property
    def rotulo_cliente(self) -> str:
        return CLIENTES.get(self.cliente, self.cliente)


def numero(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def base_do_cliente(cliente: str) -> BaseTecnica:
    """Valores iniciais para o critério escolhido."""
    if cliente == CLIENTE_ANGLO:
        return BaseTecnica(
            cliente=CLIENTE_ANGLO,
            local=ca.LOCAL_DO_VENTO,
            vento=VentoDoLocal(
                v0_m_s=ca.V0_M_S,
                s1=ca.S1,
                categoria="III",
                grupo_s3=S3_DO_CLIENTE,
                s3_cliente=ca.S3,
            ),
            tipo_de_estrutura=ca.TIPO_PLATAFORMA,
            sobrecarga_local="Plataformas de operação em geral",
            sobrecarga_kN_m2=5.0,
        )
    return BaseTecnica()


def validar(base: BaseTecnica) -> list[str]:
    erros: list[str] = []
    if base.cliente not in CLIENTES:
        erros.append(f"Critério de cliente desconhecido: {base.cliente!r}.")
    v = base.vento
    if not (10.0 <= v.v0_m_s <= 70.0):
        erros.append("V₀ precisa estar entre 10 e 70 m/s (mapa de isopletas).")
    if not (0.5 <= v.s1 <= 2.0):
        erros.append("S₁ precisa estar entre 0,5 e 2,0.")
    if v.categoria not in vb.CATEGORIAS_RUGOSIDADE:
        erros.append(f"Categoria do terreno desconhecida: {v.categoria!r}.")
    if v.grupo_s3 not in OPCOES_S3:
        erros.append(f"Grupo de S₃ desconhecido: {v.grupo_s3!r}.")
    if v.grupo_s3 == S3_DO_CLIENTE and not (v.s3_cliente and 0.5 <= v.s3_cliente <= 1.5):
        erros.append("Informe o S₃ do cliente (entre 0,5 e 1,5).")
    if base.tipo_de_estrutura not in TIPOS_DE_ESTRUTURA:
        erros.append(f"Tipo de estrutura desconhecido: {base.tipo_de_estrutura!r}.")
    if not (math.isfinite(base.sobrecarga_kN_m2) and base.sobrecarga_kN_m2 >= 0):
        erros.append("A sobrecarga não pode ser negativa.")
    if base.classe_de_agressividade not in CLASSES_DE_AGRESSIVIDADE:
        erros.append("Classe de agressividade desconhecida.")
    return erros


# ---------------------------------------------------------------------------------------------
# Leitura e gravação no documento do projeto
# ---------------------------------------------------------------------------------------------
def para_dicionario(base: BaseTecnica) -> dict[str, Any]:
    return asdict(base)


def de_dicionario(dados: Mapping[str, Any] | None) -> BaseTecnica | None:
    """A base gravada no projeto, ou ``None`` se o projeto ainda não tem uma."""
    if not isinstance(dados, Mapping) or not dados:
        return None
    padrao = base_do_cliente(str(dados.get("cliente") or CLIENTE_NENHUM))
    bruto = dados.get("vento")
    vento_dados: Mapping[str, Any] = bruto if isinstance(bruto, Mapping) else {}
    vento = replace(
        padrao.vento,
        **{
            k: vento_dados[k]
            for k in ("v0_m_s", "s1", "categoria", "grupo_s3", "s3_cliente")
            if k in vento_dados
        },
    )
    vento = replace(
        vento,
        v0_m_s=float(vento.v0_m_s),
        s1=float(vento.s1),
        categoria=str(vento.categoria),
        grupo_s3=str(vento.grupo_s3),
        s3_cliente=None if vento.s3_cliente is None else float(vento.s3_cliente),
    )
    campos = {
        k: dados[k]
        for k in (
            "local",
            "tipo_de_estrutura",
            "sobrecarga_local",
            "sobrecarga_kN_m2",
            "classe_de_agressividade",
            "vida_util_anos",
            "observacoes",
            "atualizado_em",
        )
        if k in dados
    }
    base = replace(padrao, vento=vento, **campos)
    return replace(
        base,
        sobrecarga_kN_m2=float(base.sobrecarga_kN_m2),
        vida_util_anos=None if base.vida_util_anos in (None, "") else float(base.vida_util_anos),
    )


def base_do_projeto(projeto: Mapping[str, Any] | None) -> BaseTecnica | None:
    if not isinstance(projeto, Mapping):
        return None
    return de_dicionario(projeto.get("base_tecnica"))


# ---------------------------------------------------------------------------------------------
# O que as páginas usam
# ---------------------------------------------------------------------------------------------
def texto_do_vento(base: BaseTecnica) -> str:
    v = base.vento
    return (
        f"V₀ = {numero(v.v0_m_s, 0)} m/s, S₁ = {numero(v.s1, 2)}, terreno categoria {v.categoria}, "
        f"{v.texto_s3}"
    )


@dataclass(frozen=True)
class LimiteDoTopo:
    divisor: float
    maximo_mm: float | None
    referencia: str
    entre_pisos_divisor: float | None

    def limite_mm(self, altura_mm: float) -> float:
        valor = altura_mm / self.divisor
        return min(valor, self.maximo_mm) if self.maximo_mm else valor


def limite_do_topo(base: BaseTecnica | None, n_pisos: int) -> LimiteDoTopo:
    """Deslocamento horizontal do topo sob vento: critério Anglo (Tabela 4) ou NBR 8800 (B.1)."""
    if base is not None and base.tipo_de_estrutura in ca.LIMITE_DO_TOPO_POR_TIPO:
        limite = ca.LIMITE_DO_TOPO_POR_TIPO[base.tipo_de_estrutura]
        return LimiteDoTopo(
            divisor=float(limite.divisor or 300.0),
            maximo_mm=limite.maximo_mm,
            referencia=f"{ca.item('7.2')}, Tabela 4 — {limite.descricao}",
            entre_pisos_divisor=float(ca.LIMITE_ENTRE_PISOS.divisor or 500)
            if n_pisos > 1
            else None,
        )
    if (base is not None and base.tipo_de_estrutura == TIPO_NBR_PAVIMENTOS) or n_pisos > 1:
        return LimiteDoTopo(
            400.0, None, "NBR 8800 Anexo B, Tabela B.1 (dois ou mais pavimentos)", 500.0
        )
    return LimiteDoTopo(300.0, None, "NBR 8800 Anexo B, Tabela B.1 (um pavimento)", None)


def avisos(base: BaseTecnica) -> list[str]:
    """Conflitos que valem para esta base (para mostrar na tela e no registro)."""
    lista: list[str] = []
    v = base.vento
    if v.grupo_s3 == S3_DO_CLIENTE and v.s3_cliente is not None and v.s3_cliente < 1.0:
        lista.append(ca.CONFLITOS[0])
    if base.anglo and base.tipo_de_estrutura in (ca.TIPO_PLATAFORMA, ca.TIPO_COBERTURA):
        lista.append(ca.CONFLITOS[1])
    return lista
