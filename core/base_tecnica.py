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


def _numero_na_faixa(valor: Any, minimo: float, maximo: float) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) and minimo <= numero <= maximo else None


def de_dicionario(dados: Mapping[str, Any] | None) -> BaseTecnica | None:
    """A base gravada no projeto, ou ``None`` se o projeto ainda não tem uma.

    Campo a campo: o que estiver fora do formato ou fora das opções (projeto antigo, editado à
    mão, corrompido) volta ao valor inicial do critério — a página nunca recebe uma opção que não
    existe. O que a página grava sempre passou por :func:`validar`, então nada válido se perde.
    """
    if not isinstance(dados, Mapping) or not dados:
        return None
    cliente = str(dados.get("cliente") or CLIENTE_NENHUM)
    padrao = base_do_cliente(cliente if cliente in CLIENTES else CLIENTE_NENHUM)
    bruto = dados.get("vento")
    vento_dados: Mapping[str, Any] = bruto if isinstance(bruto, Mapping) else {}
    v = padrao.vento
    v0 = _numero_na_faixa(vento_dados.get("v0_m_s"), 10.0, 70.0)
    s1 = _numero_na_faixa(vento_dados.get("s1"), 0.5, 2.0)
    categoria = str(vento_dados.get("categoria", v.categoria))
    grupo = str(vento_dados.get("grupo_s3", v.grupo_s3))
    s3_gravado = vento_dados.get("s3_cliente", v.s3_cliente)
    s3 = None if s3_gravado is None else _numero_na_faixa(s3_gravado, 0.5, 1.5) or v.s3_cliente
    vento = replace(
        v,
        v0_m_s=v0 if v0 is not None else v.v0_m_s,
        s1=s1 if s1 is not None else v.s1,
        categoria=categoria if categoria in vb.CATEGORIAS_RUGOSIDADE else v.categoria,
        grupo_s3=grupo if grupo in OPCOES_S3 else v.grupo_s3,
        s3_cliente=s3,
    )
    tipo = str(dados.get("tipo_de_estrutura", padrao.tipo_de_estrutura))
    classe = str(dados.get("classe_de_agressividade", padrao.classe_de_agressividade))
    sobrecarga = _numero_na_faixa(dados.get("sobrecarga_kN_m2"), 0.0, 1e4)
    vida_gravada = dados.get("vida_util_anos", padrao.vida_util_anos)
    vida = (
        None
        if vida_gravada in (None, "")
        else _numero_na_faixa(vida_gravada, 1.0, 500.0) or padrao.vida_util_anos
    )

    def texto(chave: str, inicial: str) -> str:
        valor = dados.get(chave, inicial)
        return valor if isinstance(valor, str) else inicial

    return replace(
        padrao,
        vento=vento,
        local=texto("local", padrao.local),
        tipo_de_estrutura=tipo if tipo in TIPOS_DE_ESTRUTURA else padrao.tipo_de_estrutura,
        sobrecarga_local=texto("sobrecarga_local", padrao.sobrecarga_local),
        sobrecarga_kN_m2=sobrecarga if sobrecarga is not None else padrao.sobrecarga_kN_m2,
        classe_de_agressividade=classe
        if classe in CLASSES_DE_AGRESSIVIDADE
        else padrao.classe_de_agressividade,
        vida_util_anos=vida,
        observacoes=texto("observacoes", padrao.observacoes),
        atualizado_em=texto("atualizado_em", padrao.atualizado_em),
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
