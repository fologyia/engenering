"""Linguagem de texto para descrever vigas e eixos.

A ideia é digitar o modelo em vez de desenhá-lo: cada linha é um comando com
números em unidades de engenharia (m, kN, kN·m, kN/m, mm, GPa, MPa). O
parser é deliberadamente tolerante com acentos, maiúsculas e separadores,
mas rigoroso com o que não entende — todo erro traz o número da linha, o
texto original e o que era esperado.

Exemplo mínimo::

    viga 6
    secao retangular 100 200
    material aco
    apoio 0 pino
    apoio 6 rolete
    q 0 6 15 baixo
    P 3 20 baixo

Convenção de sinais: valores positivos apontam para **cima** (+y) e momentos
positivos giram no sentido anti-horário. O sufixo ``baixo`` (ou ``down``,
``↓``) inverte o sinal do valor informado, para quem prefere digitar só a
intensidade.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core import beam_analysis as vb


class ErroDeScript(ValueError):
    """Erro de sintaxe ou de semântica no script, com a linha de origem."""

    def __init__(self, mensagem: str, *, linha: int | None = None, texto: str = "") -> None:
        self.linha = linha
        self.texto = texto
        if linha is not None:
            mensagem = f"Linha {linha}: {mensagem}"
            if texto:
                mensagem = f"{mensagem}\n    → {texto.strip()}"
        super().__init__(mensagem)


# ---------------------------------------------------------------------------
# Normalização e tokenização
# ---------------------------------------------------------------------------


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def _chave(token: str) -> str:
    return _sem_acento(token).strip().lower().replace("-", "_")


_SUFIXO_SENTIDO = {
    "baixo": -1.0,
    "down": -1.0,
    "↓": -1.0,
    "cima": 1.0,
    "up": 1.0,
    "↑": 1.0,
    "horario": -1.0,
    "antihorario": 1.0,
    "anti_horario": 1.0,
    "tracao": 1.0,
    "compressao": -1.0,
}

# O catálogo de materiais do programa tabela Sut e Sy, mas não E nem G.
# Estes são os valores típicos por categoria, usados apenas para completar
# o que o catálogo não traz — e sempre sinalizados como estimativa.
_ELASTICIDADE_POR_CATEGORIA: dict[str, tuple[float, float, float]] = {
    # categoria: (E em GPa, G em GPa, densidade em kg/m³)
    "aco": (200.0, 77.0, 7_850.0),
    "aluminio": (69.0, 26.0, 2_700.0),
    "cobre": (117.0, 44.0, 8_960.0),
    "ferro_fundido": (100.0, 41.0, 7_200.0),
}

_MATERIAIS_PRONTOS: dict[str, tuple[float, float, float, float]] = {
    # nome: (E em GPa, G em GPa, Sy em MPa, densidade em kg/m³)
    "aco": (200.0, 77.0, 250.0, 7_850.0),
    "aco_inox": (193.0, 74.0, 205.0, 8_000.0),
    "aluminio": (69.0, 26.0, 240.0, 2_700.0),
    "ferro_fundido": (100.0, 41.0, 200.0, 7_200.0),
    "cobre": (117.0, 44.0, 70.0, 8_960.0),
    "titanio": (110.0, 42.0, 830.0, 4_500.0),
    "madeira": (11.0, 0.7, 40.0, 600.0),
    "concreto": (25.0, 10.0, 20.0, 2_500.0),
}

# Alias preferido ao escrever de volta um modelo como texto.
ALIAS_CANONICO = {
    "pino": "pino",
    "rolete": "rolete",
    "engaste": "engaste",
    "engaste deslizante": "deslizante",
    "apoio horizontal": "trava_axial",
    "mola": "mola",
    "livre": "livre",
}

_TIPOS_APOIO_ALIAS = {
    "pino": "pino",
    "pinado": "pino",
    "articulado": "pino",
    "2o_genero": "pino",
    "rolete": "rolete",
    "movel": "rolete",
    "simples": "rolete",
    "1o_genero": "rolete",
    "engaste": "engaste",
    "fixo": "engaste",
    "engastado": "engaste",
    "3o_genero": "engaste",
    "engaste_deslizante": "engaste deslizante",
    "deslizante": "engaste deslizante",
    "guiado": "engaste deslizante",
    "trava_axial": "apoio horizontal",
    "apoio_horizontal": "apoio horizontal",
    "axial": "apoio horizontal",
    "mola": "mola",
    "elastico": "mola",
    "livre": "livre",
}


# Espaço e ponto e vírgula sempre separam. A vírgula só separa quando NÃO
# está entre dois dígitos — assim "apoio 0, pino" tem dois campos e "viga 4,5"
# continua sendo um número decimal, como se escreve em português.
_SEPARADOR = re.compile(r"[\s;]+|(?<![0-9]),|,(?![0-9])")


def _tokenizar(linha: str) -> list[str]:
    sem_comentario = linha.split("#", 1)[0]
    return [token for token in _SEPARADOR.split(sem_comentario.strip()) if token]


def _numero(token: str, *, campo: str, linha: int, texto: str) -> float:
    bruto = token.replace(" ", "").strip()
    # "1.5e3", "1,5" e "2_000" são todos aceitos; a vírgula só vira ponto
    # quando não há nenhum ponto no token (senão "1,234.5" viraria lixo).
    if "," in bruto and "." not in bruto:
        bruto = bruto.replace(",", ".")
    bruto = bruto.replace("_", "")
    try:
        valor = float(bruto)
    except ValueError:
        raise ErroDeScript(
            f"{campo} deve ser um número; recebi {token!r}.", linha=linha, texto=texto
        ) from None
    if not math.isfinite(valor):
        raise ErroDeScript(f"{campo} deve ser um número finito.", linha=linha, texto=texto)
    return valor


def _separar_nomeados(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    posicionais: list[str] = []
    nomeados: dict[str, str] = {}
    for token in tokens:
        if "=" in token:
            nome, _, valor = token.partition("=")
            nomeados[_chave(nome)] = valor
        else:
            posicionais.append(token)
    return posicionais, nomeados


def _caso(nom: dict[str, str]) -> str:
    """Caso de carga declarado na linha, ou o permanente por padrão."""
    for chave in ("caso", "acao", "grupo"):
        if chave in nom and nom[chave].strip():
            return nom[chave].strip()
    return vb.CASO_PADRAO


def _sentido(tokens: list[str]) -> tuple[list[str], float]:
    """Remove um eventual sufixo de sentido e devolve o multiplicador."""
    if tokens and _chave(tokens[-1]) in _SUFIXO_SENTIDO:
        return tokens[:-1], _SUFIXO_SENTIDO[_chave(tokens[-1])]
    return tokens, 1.0


# ---------------------------------------------------------------------------
# Estado acumulado durante a leitura
# ---------------------------------------------------------------------------


@dataclass
class _Acumulador:
    comprimento_m: float | None = None
    secao: vb.SecaoViga | None = None
    material: vb.MaterialViga | None = None
    apoios: list[vb.Apoio] = None  # type: ignore[assignment]
    rotulas: list[vb.Rotula] = None  # type: ignore[assignment]
    pontuais: list[vb.CargaPontual] = None  # type: ignore[assignment]
    momentos: list[vb.MomentoConcentrado] = None  # type: ignore[assignment]
    distribuidas: list[vb.CargaDistribuida] = None  # type: ignore[assignment]
    axiais: list[vb.CargaAxial] = None  # type: ignore[assignment]
    axiais_distribuidas: list[vb.CargaAxialDistribuida] = None  # type: ignore[assignment]
    torques: list[vb.Torque] = None  # type: ignore[assignment]
    combinacoes: list[vb.CombinacaoCarga] = None  # type: ignore[assignment]
    peso_proprio: bool = False
    segunda_ordem: bool = False
    divisoes: int = 1
    nome: str = "Viga"
    material_id: str | None = None
    material_fonte: str = ""
    materiais_projeto: tuple = ()

    def __post_init__(self) -> None:
        for campo in (
            "apoios",
            "rotulas",
            "pontuais",
            "momentos",
            "distribuidas",
            "axiais",
            "axiais_distribuidas",
            "torques",
            "combinacoes",
        ):
            if getattr(self, campo) is None:
                setattr(self, campo, [])


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------


def _comando_viga(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    if not pos:
        raise ErroDeScript(
            "Informe o comprimento da viga em metros. Ex.: `viga 6`.", linha=n, texto=texto
        )
    acc.comprimento_m = _numero(pos[0], campo="comprimento da viga", linha=n, texto=texto)
    if acc.comprimento_m <= 0:
        raise ErroDeScript("O comprimento da viga deve ser maior que zero.", linha=n, texto=texto)
    if len(pos) > 1:
        acc.nome = " ".join(pos[1:])


def _comando_nome(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    if not pos:
        raise ErroDeScript("Informe um nome. Ex.: `nome Viga do mezanino`.", linha=n, texto=texto)
    acc.nome = " ".join(pos)


def _material_do_catalogo(nome: str, n: int, texto: str) -> tuple:
    """Resolve um material da base do programa (``data/materials.csv``)."""
    from core import materials as base

    try:
        dados = base.obter_material(nome)
    except (ValueError, FileNotFoundError):
        alvo = _chave(nome)
        try:
            nomes = base.listar_nomes()
        except (ValueError, FileNotFoundError) as erro:  # pragma: no cover
            raise ErroDeScript(str(erro), linha=n, texto=texto) from None
        parecidos = [item for item in nomes if alvo and alvo in _chave(item)]
        if len(parecidos) == 1:
            dados = base.obter_material(parecidos[0])
        else:
            sugestao = parecidos[:5] or nomes[:5]
            raise ErroDeScript(
                f"Material {nome!r} não está no catálogo. "
                + ("Você quis dizer: " if parecidos else "Alguns disponíveis: ")
                + "; ".join(sugestao)
                + ".",
                linha=n,
                texto=texto,
            ) from None
    categoria = _chave(str(dados.get("categoria", "")))
    if categoria not in _ELASTICIDADE_POR_CATEGORIA:
        raise ErroDeScript(
            f"O catálogo não traz E e G para a categoria {categoria!r} de "
            f"{dados['nome']!r}. Informe E= e G= na mesma linha.",
            linha=n,
            texto=texto,
        )
    e_gpa, g_gpa, densidade = _ELASTICIDADE_POR_CATEGORIA[categoria]
    fonte = (
        f"Catálogo orientativo do programa · {dados['nome']} · "
        "E e G são valores típicos da categoria"
    )
    return str(dados["nome"]), e_gpa, g_gpa, _numero_ou_none(dados.get("Sy_MPa")), densidade, None, fonte


def _numero_ou_none(valor) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) and numero > 0 else None


def _material_do_projeto(
    identificador: str, materiais: tuple, n: int, texto: str
) -> tuple:
    """Resolve um material qualificado do projeto ativo, por id ou por nome."""
    from core.materials_registry import avaliar_material, resumir_fonte

    alvo = _chave(identificador)
    escolhido = None
    for material in materiais:
        if _chave(str(material.get("id", ""))) == alvo or _chave(
            str(material.get("nome", ""))
        ) == alvo:
            escolhido = material
            break
    if escolhido is None:
        if not materiais:
            raise ErroDeScript(
                "O projeto ativo não tem materiais cadastrados. Cadastre em "
                "Materiais técnicos, ou use `material catalogo <nome>`.",
                linha=n,
                texto=texto,
            )
        nomes = "; ".join(str(item.get("nome")) for item in materiais[:6])
        raise ErroDeScript(
            f"Material {identificador!r} não está no projeto ativo. "
            f"Disponíveis: {nomes}.",
            linha=n,
            texto=texto,
        )
    props = escolhido.get("propriedades", {}) or {}
    e_gpa = _numero_ou_none(props.get("E_GPa"))
    if e_gpa is None:
        raise ErroDeScript(
            f"O material {escolhido.get('nome')!r} do projeto não tem módulo de "
            "elasticidade cadastrado. Complete-o em Materiais técnicos ou "
            "informe E= nesta linha.",
            linha=n,
            texto=texto,
        )
    nu = _numero_ou_none(props.get("nu"))
    # G = E / (2(1+ν)); sem ν cadastrado usa-se o 0,3 típico de metais.
    g_gpa = e_gpa / (2.0 * (1.0 + (nu if nu is not None else 0.3)))
    densidade = _numero_ou_none(props.get("densidade_kg_m3")) or 7_850.0
    avaliacao = avaliar_material(escolhido)
    fonte = (
        f"Material do projeto · {escolhido.get('nome')} · "
        f"{avaliacao['nivel']} · {resumir_fonte(escolhido)}"
    )
    return (
        str(escolhido.get("nome")),
        e_gpa,
        g_gpa,
        _numero_ou_none(props.get("Sy_MPa")),
        densidade,
        str(escolhido.get("id")),
        fonte,
    )


def _comando_material(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    e_gpa = g_gpa = sy = densidade = None
    nome_material = "personalizado"
    material_id = nom.get("id") or nom.get("material_id")
    fonte = ""

    if pos:
        primeiro = _chave(pos[0])
        if primeiro == "catalogo" or primeiro == "catalogo_referencia":
            if len(pos) < 2:
                raise ErroDeScript(
                    "Informe o nome do material do catálogo. Ex.: "
                    "`material catalogo AISI 1045 temperado e revenido`.",
                    linha=n,
                    texto=texto,
                )
            nome_material, e_gpa, g_gpa, sy, densidade, _, fonte = _material_do_catalogo(
                " ".join(pos[1:]), n, texto
            )
        elif primeiro == "projeto":
            if len(pos) < 2:
                raise ErroDeScript(
                    "Informe o material do projeto pelo nome ou pelo id. Ex.: "
                    "`material projeto Chapa A36 certificada`.",
                    linha=n,
                    texto=texto,
                )
            (
                nome_material,
                e_gpa,
                g_gpa,
                sy,
                densidade,
                material_id,
                fonte,
            ) = _material_do_projeto(" ".join(pos[1:]), acc.materiais_projeto, n, texto)
        elif primeiro in _MATERIAIS_PRONTOS:
            e_gpa, g_gpa, sy, densidade = _MATERIAIS_PRONTOS[primeiro]
            nome_material = primeiro
            fonte = "Atalho genérico da linguagem — valores típicos, sem rastreabilidade"
        else:
            disponiveis = ", ".join(sorted(_MATERIAIS_PRONTOS))
            raise ErroDeScript(
                f"Material {pos[0]!r} não está na lista de atalhos ({disponiveis}). "
                "Use `material catalogo <nome>` para a base do programa, "
                "`material projeto <nome>` para um material qualificado, ou "
                "`material E=200 G=77 Sy=250` para valores próprios.",
                linha=n,
                texto=texto,
            )

    for nome_campo, chaves in (
        ("e", ("e", "modulo", "young")),
        ("g", ("g", "cisalhamento")),
        ("sy", ("sy", "escoamento", "fy")),
        ("densidade", ("densidade", "rho", "massa_especifica")),
    ):
        for chave in chaves:
            if chave in nom:
                valor = _numero(nom[chave], campo=nome_campo.upper(), linha=n, texto=texto)
                if nome_campo == "e":
                    e_gpa = valor
                elif nome_campo == "g":
                    g_gpa = valor
                elif nome_campo == "sy":
                    sy = valor
                else:
                    densidade = valor
                break

    if e_gpa is None:
        raise ErroDeScript(
            "Faltou o módulo de elasticidade. Use um atalho (`material aco`) ou "
            "`material E=200 G=77` — E e G em GPa.",
            linha=n,
            texto=texto,
        )
    if g_gpa is None:
        # Coeficiente de Poisson típico de metais: G = E / (2(1+ν)) com ν = 0,3.
        g_gpa = e_gpa / 2.6
    try:
        acc.material = vb.MaterialViga(
            nome=nome_material,
            modulo_elasticidade_MPa=e_gpa * 1_000.0,
            modulo_cisalhamento_MPa=g_gpa * 1_000.0,
            escoamento_MPa=sy,
            densidade_kg_m3=densidade if densidade is not None else 7_850.0,
            material_id=material_id or None,
            fonte=nom.get("fonte") or fonte,
        )
    except ValueError as erro:
        raise ErroDeScript(str(erro), linha=n, texto=texto) from None


_SECOES_POSICIONAIS: dict[str, tuple[int, tuple[str, ...]]] = {
    "retangular": (2, ("base (mm)", "altura (mm)")),
    "circular": (1, ("diâmetro (mm)",)),
    "tubo": (2, ("diâmetro externo (mm)", "diâmetro interno (mm)")),
    "tubo_retangular": (3, ("largura (mm)", "altura (mm)", "espessura (mm)")),
    "perfil_i": (4, ("altura (mm)", "largura da mesa (mm)", "espessura da alma (mm)", "espessura da mesa (mm)")),
}


def _comando_secao(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    if not pos:
        raise ErroDeScript(
            "Informe o tipo de seção. Ex.: `secao retangular 100 200`, "
            "`secao circular 50`, `secao tubo 60 48`, `secao perfil W ideal 200x200x8x12`.",
            linha=n,
            texto=texto,
        )
    tipo = _chave(pos[0])
    argumentos = pos[1:]

    if tipo in {"manual", "personalizada", "propria"}:
        acc.secao = _secao_manual(nom, n, texto)
        return

    if tipo in {"perfil", "catalogo"}:
        if not argumentos:
            raise ErroDeScript(
                "Informe o nome do perfil do catálogo. Ex.: `secao perfil W ideal 200x200x8x12`.",
                linha=n,
                texto=texto,
            )
        nome_perfil = " ".join(argumentos)
        perfil = _buscar_perfil(nome_perfil, n, texto)
        eixo = nom.get("eixo", "x")
        acc.secao = vb.secao_de_perfil_catalogo(perfil, eixo=eixo)
        return

    if tipo not in _SECOES_POSICIONAIS:
        disponiveis = ", ".join([*sorted(_SECOES_POSICIONAIS), "perfil", "manual"])
        raise ErroDeScript(
            f"Tipo de seção {pos[0]!r} desconhecido. Use: {disponiveis}.",
            linha=n,
            texto=texto,
        )

    esperados, rotulos = _SECOES_POSICIONAIS[tipo]
    if len(argumentos) < esperados:
        raise ErroDeScript(
            f"A seção {tipo} precisa de {esperados} número(s): {', '.join(rotulos)}.",
            linha=n,
            texto=texto,
        )
    valores = [
        _numero(argumentos[i], campo=rotulos[i], linha=n, texto=texto) for i in range(esperados)
    ]
    try:
        if tipo == "retangular":
            acc.secao = vb.secao_retangular(*valores)
        elif tipo == "circular":
            acc.secao = vb.secao_circular_macica(*valores)
        elif tipo == "tubo":
            acc.secao = vb.secao_tubo_circular(*valores)
        elif tipo == "tubo_retangular":
            acc.secao = vb.secao_tubo_retangular(*valores)
        else:
            acc.secao = vb.secao_i_simetrica(*valores)
    except ValueError as erro:
        raise ErroDeScript(str(erro), linha=n, texto=texto) from None


def _normalizar_perfil(nome: str) -> str:
    """Compara nomes de perfil ignorando caixa, acento, espaço e × vs x."""
    return _sem_acento(nome).lower().replace("×", "x").replace("ø", "o").replace(" ", "")


def _buscar_perfil(nome: str, n: int, texto: str):
    from core import section_catalog as catalogo

    disponiveis = catalogo.listar_perfis()
    if nome in disponiveis:
        return disponiveis[nome]
    alvo = _normalizar_perfil(nome)
    for chave, perfil in disponiveis.items():
        if _normalizar_perfil(chave) == alvo:
            return perfil
    # Sem correspondência exata, sugere os que contêm o texto digitado.
    parecidos = [
        chave for chave in disponiveis if alvo and alvo in _normalizar_perfil(chave)
    ]
    if len(parecidos) == 1:
        return disponiveis[parecidos[0]]
    sugestao = parecidos[:6] or list(disponiveis)[:6]
    raise ErroDeScript(
        f"Perfil {nome!r} não está no catálogo. "
        + ("Você quis dizer: " if parecidos else "Alguns disponíveis: ")
        + "; ".join(sugestao)
        + ". A lista completa está no seletor de seção do modo formulário.",
        linha=n,
        texto=texto,
    )


def _secao_manual(nom: dict[str, str], n: int, texto: str) -> vb.SecaoViga:
    def pegar(chaves: tuple[str, ...], campo: str, obrigatorio: bool = True) -> float | None:
        for chave in chaves:
            if chave in nom:
                return _numero(nom[chave], campo=campo, linha=n, texto=texto)
        if obrigatorio:
            raise ErroDeScript(
                f"A seção manual precisa de {campo}. Ex.: "
                "`secao manual A=5000 I=2.5e7 c=100 Q=250000 t=10 J=5e6 Wt=1e5`.",
                linha=n,
                texto=texto,
            )
        return None

    area = pegar(("a", "area"), "A (mm²)")
    inercia = pegar(("i", "inercia", "ix"), "I (mm⁴)")
    # ``pegar`` só devolve None quando obrigatorio=False; estas quatro são
    # obrigatórias, e o assert documenta isso para o verificador de tipos.
    assert area is not None and inercia is not None
    c_sup = pegar(("c_sup", "csup"), "c superior (mm)", obrigatorio=False)
    c_inf = pegar(("c_inf", "cinf"), "c inferior (mm)", obrigatorio=False)
    # ``c`` só é exigido quando as duas distâncias específicas não vieram.
    c = pegar(("c", "c_max", "y"), "c (mm)", obrigatorio=c_sup is None or c_inf is None)
    c_sup = c_sup if c_sup is not None else c
    c_inf = c_inf if c_inf is not None else c
    assert c_sup is not None and c_inf is not None
    q = pegar(("q", "momento_estatico"), "Q (mm³)", obrigatorio=False) or 0.0
    t = pegar(("t", "espessura", "b"), "t (mm)", obrigatorio=False) or 1.0
    j = pegar(("j", "torcao"), "J (mm⁴)", obrigatorio=False) or 0.0
    wt = pegar(("wt", "modulo_torcao"), "Wt (mm³)", obrigatorio=False) or 0.0
    av = pegar(("av", "area_cisalhamento"), "Av (mm²)", obrigatorio=False) or 0.0
    try:
        return vb.SecaoViga(
            nome="Manual",
            area_mm2=area,
            inercia_mm4=inercia,
            c_superior_mm=c_sup,
            c_inferior_mm=c_inf,
            momento_estatico_mm3=q,
            espessura_cisalhamento_mm=t,
            constante_torcao_mm4=j,
            modulo_torcao_mm3=wt,
            area_cisalhamento_mm2=av,
            descricao="Seção informada diretamente pelas propriedades.",
        )
    except ValueError as erro:
        raise ErroDeScript(str(erro), linha=n, texto=texto) from None


def _comando_apoio(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    if len(pos) < 1:
        raise ErroDeScript(
            "Informe a posição do apoio em metros. Ex.: `apoio 0 pino`.", linha=n, texto=texto
        )
    x = _numero(pos[0], campo="posição do apoio", linha=n, texto=texto)
    tipo_bruto = pos[1] if len(pos) > 1 else "pino"
    tipo = _TIPOS_APOIO_ALIAS.get(_chave(tipo_bruto))
    if tipo is None:
        disponiveis = ", ".join(sorted(set(_TIPOS_APOIO_ALIAS.values())))
        raise ErroDeScript(
            f"Tipo de apoio {tipo_bruto!r} desconhecido. Use: {disponiveis}.",
            linha=n,
            texto=texto,
        )
    rigidez_v = (
        _numero(nom["kv"], campo="kv (N/mm)", linha=n, texto=texto) if "kv" in nom else 0.0
    )
    rigidez_r = (
        _numero(nom["kr"], campo="kr (N·mm/rad)", linha=n, texto=texto)
        if "kr" in nom
        else 0.0
    )
    try:
        acc.apoios.append(
            vb.Apoio(
                x_mm=x * 1_000.0,
                tipo=tipo,
                rigidez_vertical_N_mm=rigidez_v,
                rigidez_rotacional_Nmm_rad=rigidez_r,
            )
        )
    except ValueError as erro:
        raise ErroDeScript(str(erro), linha=n, texto=texto) from None


def _comando_rotula(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    if not pos:
        raise ErroDeScript("Informe a posição da rótula em metros.", linha=n, texto=texto)
    x = _numero(pos[0], campo="posição da rótula", linha=n, texto=texto)
    acc.rotulas.append(vb.Rotula(x_mm=x * 1_000.0))


def _comando_pontual(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    pos, sinal = _sentido(pos)
    if len(pos) < 2:
        raise ErroDeScript(
            "Carga pontual precisa de posição (m) e valor (kN). Ex.: `P 3 20 baixo`.",
            linha=n,
            texto=texto,
        )
    x = _numero(pos[0], campo="posição da carga", linha=n, texto=texto)
    valor = _numero(pos[1], campo="valor da carga (kN)", linha=n, texto=texto)
    acc.pontuais.append(
        vb.CargaPontual(x_mm=x * 1_000.0, fy_N=sinal * valor * 1_000.0, caso=_caso(nom))
    )


def _comando_momento(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    pos, sinal = _sentido(pos)
    if len(pos) < 2:
        raise ErroDeScript(
            "Momento concentrado precisa de posição (m) e valor (kN·m). Ex.: `M 2 15`.",
            linha=n,
            texto=texto,
        )
    x = _numero(pos[0], campo="posição do momento", linha=n, texto=texto)
    valor = _numero(pos[1], campo="valor do momento (kN·m)", linha=n, texto=texto)
    acc.momentos.append(
        vb.MomentoConcentrado(
            x_mm=x * 1_000.0, mz_Nmm=sinal * valor * 1e6, caso=_caso(nom)
        )
    )


def _comando_distribuida(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    pos, sinal = _sentido(pos)
    if len(pos) < 3:
        raise ErroDeScript(
            "Carga distribuída precisa de x inicial (m), x final (m) e intensidade "
            "(kN/m). Ex.: `q 0 6 15 baixo` ou `q 0 6 0 20` para trapezoidal.",
            linha=n,
            texto=texto,
        )
    x1 = _numero(pos[0], campo="x inicial", linha=n, texto=texto)
    x2 = _numero(pos[1], campo="x final", linha=n, texto=texto)
    w1 = _numero(pos[2], campo="intensidade inicial (kN/m)", linha=n, texto=texto)
    w2 = _numero(pos[3], campo="intensidade final (kN/m)", linha=n, texto=texto) if len(pos) > 3 else None
    try:
        acc.distribuidas.append(
            vb.CargaDistribuida(
                x_inicial_mm=x1 * 1_000.0,
                x_final_mm=x2 * 1_000.0,
                w_inicial_N_mm=sinal * w1,
                w_final_N_mm=None if w2 is None else sinal * w2,
                caso=_caso(nom),
            )
        )
    except ValueError as erro:
        raise ErroDeScript(str(erro), linha=n, texto=texto) from None


def _comando_axial(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    pos, sinal = _sentido(pos)
    if len(pos) < 2:
        raise ErroDeScript(
            "Carga axial precisa de posição (m) e valor (kN). Ex.: `N 6 50 compressao`.",
            linha=n,
            texto=texto,
        )
    x = _numero(pos[0], campo="posição da carga axial", linha=n, texto=texto)
    valor = _numero(pos[1], campo="valor da carga axial (kN)", linha=n, texto=texto)
    acc.axiais.append(
        vb.CargaAxial(x_mm=x * 1_000.0, fx_N=sinal * valor * 1_000.0, caso=_caso(nom))
    )


def _comando_axial_distribuida(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    pos, sinal = _sentido(pos)
    if len(pos) < 3:
        raise ErroDeScript(
            "Carga axial distribuída precisa de x inicial, x final e intensidade "
            "(kN/m). Ex.: `qn 0 6 2`.",
            linha=n,
            texto=texto,
        )
    x1 = _numero(pos[0], campo="x inicial", linha=n, texto=texto)
    x2 = _numero(pos[1], campo="x final", linha=n, texto=texto)
    a1 = _numero(pos[2], campo="intensidade inicial (kN/m)", linha=n, texto=texto)
    a2 = _numero(pos[3], campo="intensidade final (kN/m)", linha=n, texto=texto) if len(pos) > 3 else None
    try:
        acc.axiais_distribuidas.append(
            vb.CargaAxialDistribuida(
                x_inicial_mm=x1 * 1_000.0,
                x_final_mm=x2 * 1_000.0,
                a_inicial_N_mm=sinal * a1,
                a_final_N_mm=None if a2 is None else sinal * a2,
                caso=_caso(nom),
            )
        )
    except ValueError as erro:
        raise ErroDeScript(str(erro), linha=n, texto=texto) from None


def _comando_torque(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    pos, sinal = _sentido(pos)
    if len(pos) < 2:
        raise ErroDeScript(
            "Torque precisa de posição (m) e valor (kN·m). Ex.: `T 4 2.5`.",
            linha=n,
            texto=texto,
        )
    x = _numero(pos[0], campo="posição do torque", linha=n, texto=texto)
    valor = _numero(pos[1], campo="valor do torque (kN·m)", linha=n, texto=texto)
    acc.torques.append(
        vb.Torque(x_mm=x * 1_000.0, t_Nmm=sinal * valor * 1e6, caso=_caso(nom))
    )


def _comando_segunda_ordem(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    ligado = True
    if pos:
        ligado = _chave(pos[0]) not in {"nao", "off", "0", "false", "desligado"}
    acc.segunda_ordem = ligado


def _comando_divisoes(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    if not pos:
        raise ErroDeScript(
            "Informe em quantas partes dividir cada trecho. Ex.: `divisoes 12`.",
            linha=n,
            texto=texto,
        )
    valor = _numero(pos[0], campo="número de divisões", linha=n, texto=texto)
    if valor < 1 or valor != int(valor):
        raise ErroDeScript(
            "O número de divisões deve ser um inteiro maior ou igual a 1.",
            linha=n,
            texto=texto,
        )
    acc.divisoes = int(valor)


def _comando_combinacao(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    if not pos:
        raise ErroDeScript(
            "Informe o nome da combinação e os fatores por caso. Ex.: "
            "`combinacao ELU Permanente=1.4 Sobrecarga=1.5`.",
            linha=n,
            texto=texto,
        )
    nome = " ".join(pos)
    if not nom:
        raise ErroDeScript(
            f"A combinação {nome!r} não tem nenhum fator. Escreva os casos que "
            "participam dela, como `Permanente=1.4 Vento=1.4`.",
            linha=n,
            texto=texto,
        )
    # ``nom`` chega com as chaves normalizadas; aqui interessa a grafia que o
    # usuário escreveu, porque ela precisa casar com o `caso=` das cargas e
    # aparece como está na tabela de combinações.
    originais = {}
    for token in _tokenizar(texto)[1:]:
        if "=" in token:
            chave, _, valor = token.partition("=")
            originais[chave.strip()] = valor
    fatores = {
        chave: _numero(valor, campo=f"fator de {chave}", linha=n, texto=texto)
        for chave, valor in originais.items()
    }
    if any(nome == existente.nome for existente in acc.combinacoes):
        raise ErroDeScript(
            f"Já existe uma combinação chamada {nome!r}.", linha=n, texto=texto
        )
    acc.combinacoes.append(vb.CombinacaoCarga(nome=nome, fatores=fatores))


def _comando_peso_proprio(acc: _Acumulador, pos: list[str], nom: dict[str, str], n: int, texto: str) -> None:
    ligado = True
    if pos:
        ligado = _chave(pos[0]) not in {"nao", "off", "0", "false", "desligado"}
    acc.peso_proprio = ligado


_COMANDOS = {
    "viga": _comando_viga,
    "comprimento": _comando_viga,
    "barra": _comando_viga,
    "eixo": _comando_viga,
    "nome": _comando_nome,
    "material": _comando_material,
    "mat": _comando_material,
    "secao": _comando_secao,
    "seccao": _comando_secao,
    "apoio": _comando_apoio,
    "suporte": _comando_apoio,
    "rotula": _comando_rotula,
    "articulacao": _comando_rotula,
    "p": _comando_pontual,
    "carga": _comando_pontual,
    "forca": _comando_pontual,
    "f": _comando_pontual,
    "m": _comando_momento,
    "momento": _comando_momento,
    "q": _comando_distribuida,
    "dist": _comando_distribuida,
    "distribuida": _comando_distribuida,
    "w": _comando_distribuida,
    "n": _comando_axial,
    "axial": _comando_axial,
    "normal": _comando_axial,
    "qn": _comando_axial_distribuida,
    "axial_dist": _comando_axial_distribuida,
    "t": _comando_torque,
    "torque": _comando_torque,
    "torcao": _comando_torque,
    "combinacao": _comando_combinacao,
    "comb": _comando_combinacao,
    "peso_proprio": _comando_peso_proprio,
    "segunda_ordem": _comando_segunda_ordem,
    "p_delta": _comando_segunda_ordem,
    "divisoes": _comando_divisoes,
    "peso": _comando_peso_proprio,
}


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def interpretar(script: str, *, materiais_projeto: Sequence[Mapping] = ()) -> vb.Viga:
    """Converte o texto do modelo em uma :class:`core.beam_analysis.Viga`.

    ``materiais_projeto`` são os materiais qualificados do projeto ativo,
    injetados pela página. O parser não busca o projeto sozinho de propósito:
    assim ele continua testável sem banco e sem sessão do Streamlit.
    """
    if not str(script or "").strip():
        raise ErroDeScript(
            "O modelo está vazio. Comece com `viga <comprimento em m>` e adicione "
            "seção, material, apoios e cargas."
        )
    acc = _Acumulador(materiais_projeto=tuple(materiais_projeto))
    for numero, linha_texto in enumerate(str(script).splitlines(), start=1):
        tokens = _tokenizar(linha_texto)
        if not tokens:
            continue
        comando = _chave(tokens[0])
        # `P 3 20` e `P=3` não devem ser confundidos: o comando nunca traz "=".
        if "=" in tokens[0]:
            raise ErroDeScript(
                f"A linha começa com {tokens[0]!r}. O primeiro item precisa ser um "
                "comando (viga, secao, material, apoio, P, q, M, N, T…).",
                linha=numero,
                texto=linha_texto,
            )
        funcao = _COMANDOS.get(comando)
        if funcao is None:
            sugestao = _sugerir(comando)
            extra = f" Você quis dizer `{sugestao}`?" if sugestao else ""
            raise ErroDeScript(
                f"Comando {tokens[0]!r} desconhecido.{extra} Comandos válidos: "
                "viga, nome, material, secao, apoio, rotula, P, M, q, N, qn, T, peso_proprio.",
                linha=numero,
                texto=linha_texto,
            )
        posicionais, nomeados = _separar_nomeados(tokens[1:])
        funcao(acc, posicionais, nomeados, numero, linha_texto)

    return _montar(acc)


def _sugerir(comando: str) -> str | None:
    """Sugestão simples por prefixo/subcadeia — sem dependência externa."""
    candidatos = [chave for chave in _COMANDOS if chave.startswith(comando[:2])]
    if not candidatos:
        candidatos = [chave for chave in _COMANDOS if comando in chave or chave in comando]
    return candidatos[0] if candidatos else None


def combinacoes_do_script(script: str) -> list[vb.CombinacaoCarga]:
    """Lê apenas as combinações declaradas, sem exigir um modelo completo.

    A página precisa delas antes de decidir se mostra a envoltória; separar
    a leitura evita ter de interpretar o modelo duas vezes ou guardar estado
    global no interpretador.
    """
    combinacoes: list[vb.CombinacaoCarga] = []
    acumulador = _Acumulador(combinacoes=combinacoes)
    for numero, linha_texto in enumerate(str(script or "").splitlines(), start=1):
        tokens = _tokenizar(linha_texto)
        if not tokens or _chave(tokens[0]) not in {"combinacao", "comb"}:
            continue
        posicionais, nomeados = _separar_nomeados(tokens[1:])
        _comando_combinacao(acumulador, posicionais, nomeados, numero, linha_texto)
    return combinacoes


def _montar(acc: _Acumulador) -> vb.Viga:
    faltando = []
    if acc.comprimento_m is None:
        faltando.append("o comprimento (`viga 6`)")
    if acc.secao is None:
        faltando.append("a seção (`secao retangular 100 200`)")
    if acc.material is None:
        faltando.append("o material (`material aco`)")
    if not acc.apoios:
        faltando.append("pelo menos um apoio (`apoio 0 pino`)")
    if faltando:
        raise ErroDeScript("Falta definir " + "; ".join(faltando) + ".")
    # A checagem acima já garante que os três existem; o assert torna isso
    # explícito para o verificador de tipos em vez de deixá-lo adivinhar.
    assert acc.comprimento_m is not None
    assert acc.secao is not None and acc.material is not None

    try:
        return vb.Viga(
            comprimento_mm=acc.comprimento_m * 1_000.0,
            secao=acc.secao,
            material=acc.material,
            apoios=tuple(acc.apoios),
            rotulas=tuple(acc.rotulas),
            cargas_pontuais=tuple(acc.pontuais),
            momentos=tuple(acc.momentos),
            cargas_distribuidas=tuple(acc.distribuidas),
            cargas_axiais=tuple(acc.axiais),
            cargas_axiais_distribuidas=tuple(acc.axiais_distribuidas),
            torques=tuple(acc.torques),
            considerar_peso_proprio=acc.peso_proprio,
            considerar_segunda_ordem=acc.segunda_ordem,
            divisoes_por_trecho=acc.divisoes,
            nome=acc.nome,
        )
    except ValueError as erro:
        raise ErroDeScript(str(erro)) from None


def linhas_de_combinacoes_do_projeto(
    casos: Sequence[Mapping], combinacoes: Sequence[Mapping]
) -> list[str]:
    """Converte as combinações do projeto em linhas de `combinacao`.

    Os fatores do projeto apontam para o **id** do caso de carga; aqui eles
    viram o **nome**, que é o que as cargas do modelo usam em `caso=`. Se um
    nome não bater com nenhum caso do modelo, a análise recusa a combinação
    com a lista do que existe — melhor do que zerar a parcela em silêncio.
    """
    nomes_por_id = {
        str(caso.get("id")): str(caso.get("nome") or caso.get("id"))
        for caso in casos
        if caso.get("id")
    }
    linhas: list[str] = []
    for combinacao in combinacoes:
        if not combinacao.get("ativo", True):
            continue
        fatores = combinacao.get("fatores") or {}
        partes = []
        for caso_id, fator in fatores.items():
            nome = nomes_por_id.get(str(caso_id), str(caso_id))
            # Espaço quebraria a leitura em campos; o modelo usa um token.
            partes.append(f"{nome.replace(' ', '_')}={float(fator):g}")
        if partes:
            rotulo = str(combinacao.get("nome") or "Combinação").replace(" ", "_")
            linhas.append(f"combinacao {rotulo} " + " ".join(partes))
    return linhas


def _sufixo_caso(carga: object) -> str:
    """Escreve `caso=` só quando não é o permanente, para não poluir."""
    nome = str(getattr(carga, "caso", vb.CASO_PADRAO) or vb.CASO_PADRAO)
    return "" if nome == vb.CASO_PADRAO else f" caso={nome}"


def gerar_script(viga: vb.Viga) -> str:
    """Escreve o script equivalente a um modelo — usado pelo modo formulário.

    Manter as duas entradas (formulário e texto) sincronizadas evita que o
    usuário monte a viga nos campos e depois não consiga salvar/compartilhar
    o mesmo modelo como texto.
    """
    linhas = [f"# {viga.nome}", f"viga {viga.comprimento_mm / 1_000.0:g}"]
    secao = viga.secao
    # ``.17g`` preserva o double exatamente: com menos dígitos o modelo
    # reconstruído a partir do texto devolveria tensões um pouco diferentes.
    linhas.append(
        f"secao manual A={secao.area_mm2:.17g} I={secao.inercia_mm4:.17g} "
        f"c_sup={secao.c_superior_mm:.17g} c_inf={secao.c_inferior_mm:.17g} "
        f"Q={secao.momento_estatico_mm3:.17g} t={secao.espessura_cisalhamento_mm:.17g} "
        f"J={secao.constante_torcao_mm4:.17g} Wt={secao.modulo_torcao_mm3:.17g} "
        f"Av={secao.area_cisalhamento_mm2:.17g}"
        f"   # {secao.nome}"
    )
    material = viga.material
    partes = [
        f"E={material.modulo_elasticidade_MPa / 1_000.0:.17g}",
        f"G={material.modulo_cisalhamento_MPa / 1_000.0:.17g}",
    ]
    if material.escoamento_MPa:
        partes.append(f"Sy={material.escoamento_MPa:.17g}")
    partes.append(f"densidade={material.densidade_kg_m3:.17g}")
    if material.material_id:
        # Preserva o vínculo com o material do projeto sem depender de o
        # projeto estar aberto na hora de reler o texto.
        partes.append(f"id={material.material_id}")
    linhas.append("material " + " ".join(partes) + f"   # {material.nome}")

    for apoio in viga.apoios:
        extras = ""
        if apoio.rigidez_vertical_N_mm > 0:
            extras += f" kv={apoio.rigidez_vertical_N_mm:.17g}"
        if apoio.rigidez_rotacional_Nmm_rad > 0:
            extras += f" kr={apoio.rigidez_rotacional_Nmm_rad:.17g}"
        linhas.append(
            f"apoio {apoio.x_mm / 1_000.0:g} "
            f"{ALIAS_CANONICO.get(apoio.tipo, apoio.tipo)}{extras}"
        )
    for rotula in viga.rotulas:
        linhas.append(f"rotula {rotula.x_mm / 1_000.0:g}")
    for pontual in viga.cargas_pontuais:
        linhas.append(
            f"P {pontual.x_mm / 1_000.0:g} {pontual.fy_N / 1_000.0:g}"
            f"{_sufixo_caso(pontual)}"
        )
    for momento in viga.momentos:
        linhas.append(
            f"M {momento.x_mm / 1_000.0:g} {momento.mz_Nmm / 1e6:g}"
            f"{_sufixo_caso(momento)}"
        )
    for distribuida in viga.cargas_distribuidas:
        linhas.append(
            f"q {distribuida.x_inicial_mm / 1_000.0:g} "
            f"{distribuida.x_final_mm / 1_000.0:g} "
            f"{distribuida.w_inicial_N_mm:g} {distribuida.w_final:g}"
            f"{_sufixo_caso(distribuida)}"
        )
    for axial in viga.cargas_axiais:
        linhas.append(
            f"N {axial.x_mm / 1_000.0:g} {axial.fx_N / 1_000.0:g}"
            f"{_sufixo_caso(axial)}"
        )
    for axial_distribuida in viga.cargas_axiais_distribuidas:
        linhas.append(
            f"qn {axial_distribuida.x_inicial_mm / 1_000.0:g} "
            f"{axial_distribuida.x_final_mm / 1_000.0:g} "
            f"{axial_distribuida.a_inicial_N_mm:g} {axial_distribuida.a_final:g}"
            f"{_sufixo_caso(axial_distribuida)}"
        )
    for torque in viga.torques:
        linhas.append(
            f"T {torque.x_mm / 1_000.0:g} {torque.t_Nmm / 1e6:g}"
            f"{_sufixo_caso(torque)}"
        )
    if viga.considerar_peso_proprio:
        linhas.append("peso_proprio")
    if viga.considerar_segunda_ordem:
        linhas.append("segunda_ordem")
    if viga.divisoes_por_trecho > 1:
        linhas.append(f"divisoes {viga.divisoes_por_trecho}")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Exemplos prontos
# ---------------------------------------------------------------------------

EXEMPLOS: dict[str, str] = {
    "Viga biapoiada com carga distribuída": """# Viga biapoiada — o caso mais comum
viga 6
secao perfil W ideal 200x200x8x12
material aco
apoio 0 pino
apoio 6 rolete
q 0 6 15 baixo
P 3 20 baixo
""",
    "Balanço engastado (extremidade livre)": """# Balanço: engaste à esquerda, extremidade livre à direita
viga 2.5
secao retangular 80 200
material aco
apoio 0 engaste
q 0 2.5 8 baixo
P 2.5 12 baixo
""",
    "Viga contínua de dois vãos": """# Viga contínua — hiperestática, resolvida por rigidez direta
viga 10
secao perfil W ideal 250x250x9x14
material aco
apoio 0 pino
apoio 5 rolete
apoio 10 rolete
q 0 10 20 baixo
""",
    "Viga Gerber (com rótula interna)": """# Rótula interna: transmite cortante, mas o momento é zero nela
viga 9
secao perfil I ideal 300x150x6.5x10
material aco
apoio 0 pino
apoio 6 rolete
apoio 9 rolete
rotula 4.5
q 0 9 10 baixo
""",
    "Eixo com torção e flexão combinadas": """# Eixo de transmissão: flexão das engrenagens + torque + tração
viga 1.2
secao circular 60
material aco Sy=350
apoio 0 pino
apoio 1.2 rolete
P 0.4 8 baixo
P 0.9 6 baixo
T 0.4 1.5
T 0.9 -1.5
N 1.2 25 tracao
""",
    "Coluna-viga: flexão + compressão axial": """# Cargas combinadas: a compressão soma tensão à flexão
viga 4
secao tubo 168.3 152.3
material aco Sy=350
apoio 0 pino
apoio 4 rolete
q 0 4 6 baixo
N 4 180 compressao
peso_proprio
""",
    "Envoltória de combinações (viga de piso)": """# Cada carga pertence a um caso; cada combinação pesa os casos.
# O programa resolve a barra uma vez por combinação e envelopa o resultado.
viga 8
secao perfil W ideal 250x250x9x14
material catalogo ASTM A572 grau 50
apoio 0 pino
apoio 8 rolete

q 0 8 12 baixo                 # sem caso=, logo Permanente
q 0 8 20 baixo caso=Sobrecarga
q 0 8 8 cima   caso=Vento      # sucção
peso_proprio

combinacao ELU_gravidade Permanente=1.4 Sobrecarga=1.5
combinacao ELU_vento     Permanente=1.0 Vento=1.4
combinacao ELS_rara      Permanente=1.0 Sobrecarga=1.0
""",
    "Coluna-viga com efeito P–Δ (segunda ordem)": """# A compressão reduz a rigidez à flexão: a flecha e o momento crescem.
# Compare ligando e desligando a linha `segunda_ordem`.
viga 4
secao tubo 168.3 152.3
material catalogo ASTM A572 grau 50
apoio 0 pino
apoio 4 rolete
q 0 4 3 baixo
N 4 600 compressao
segunda_ordem
""",
    "Carga triangular (empuxo em comporta)": """# Distribuída trapezoidal: intensidade inicial e final
# Empuxo hidrostático cresce com a profundidade, de 0 no topo ao máximo na base
viga 3
secao retangular 150 300
material aco
apoio 0 engaste
q 0 3 0 25 baixo
""",
}


AJUDA_SINTAXE = """\
| Comando | Para que serve | Exemplo |
| --- | --- | --- |
| `viga L` | Comprimento total, em metros | `viga 6` |
| `nome ...` | Identifica o modelo | `nome Viga do mezanino` |
| `material <atalho>` | aco, aco_inox, aluminio, ferro_fundido, cobre, titanio, madeira, concreto | `material aco` |
| `material catalogo <nome>` | Material da base do programa (Sy do catálogo) | `material catalogo AISI 1045 temperado e revenido` |
| `material projeto <nome>` | Material qualificado do projeto ativo, com rastreabilidade | `material projeto Chapa A36 certificada` |
| `material E= G= Sy= densidade=` | Material próprio (E e G em GPa, Sy em MPa) | `material E=200 G=77 Sy=250` |
| `secao retangular b h` | Retangular maciça, em mm | `secao retangular 100 200` |
| `secao circular d` | Barra redonda, em mm | `secao circular 50` |
| `secao tubo de di` | Tubo circular, em mm | `secao tubo 60 48` |
| `secao tubo_retangular b h t` | Tubo retangular, em mm | `secao tubo_retangular 100 200 6` |
| `secao perfil_i h bf tw tf` | Perfil I soldado, em mm | `secao perfil_i 300 150 8 12` |
| `secao perfil <nome>` | Perfil do catálogo do programa | `secao perfil W ideal 200x200x8x12` |
| `secao manual A= I= c= Q= t= J= Wt= Av=` | Propriedades diretas | `secao manual A=5000 I=2.5e7 c=100` |
| `apoio x <tipo>` | pino, rolete, engaste, deslizante, trava_axial | `apoio 0 pino` |
| `apoio x mola kv= kr=` | Apoio elástico: kv em N/mm, kr em N·mm/rad | `apoio 3 mola kv=500` |
| `rotula x` | Articulação interna (M = 0) | `rotula 4.5` |
| `P x valor` | Força concentrada, em kN | `P 3 20 baixo` |
| `M x valor` | Momento concentrado, em kN·m | `M 2 15` |
| `q x1 x2 w1 [w2]` | Distribuída, em kN/m (trapezoidal se houver w2) | `q 0 6 15 baixo` |
| `N x valor` | Carga axial, em kN | `N 4 180 compressao` |
| `qn x1 x2 a1 [a2]` | Axial distribuída, em kN/m | `qn 0 6 2` |
| `T x valor` | Torque, em kN·m | `T 0.4 1.5` |
| `peso_proprio` | Soma o peso da própria barra | `peso_proprio` |
| `segunda_ordem` | Inclui o efeito P–Δ: a compressão amplifica a flecha | `segunda_ordem` |
| `divisoes n` | Refina a malha de cada trecho (só afeta a segunda ordem) | `divisoes 12` |
| `caso=<nome>` | Marca a que ação a carga pertence (sufixo de qualquer carga) | `q 0 6 15 baixo caso=Sobrecarga` |
| `combinacao <nome> <Caso>=<fator>` | Combinação a envelopar | `combinacao ELU Permanente=1.4 Sobrecarga=1.5` |

Posições em **metros**, forças em **kN**, momentos e torques em **kN·m**,
dimensões de seção em **mm**. Tudo depois de `#` é comentário. Valores
positivos apontam para **cima**; escreva `baixo` (ou `compressao`) no fim da
linha para inverter o sinal sem digitar o menos.

Carga sem `caso=` é **Permanente**. Quando há pelo menos uma `combinacao`,
o programa resolve a barra uma vez por combinação e desenha a envoltória;
um caso que não aparece na combinação entra com fator zero.
"""
