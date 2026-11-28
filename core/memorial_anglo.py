"""Memorial Anglo gerado sobre as seções e os estilos do Word de referência."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm
from docx.table import Table
from docx.text.paragraph import Paragraph

from core.load_cases import ROTULOS_CARGA, UNIDADES_CARGA, fatores_legiveis
from core.memorial_blocos import blocos_da_secao
from core.project_report import montar_modelo_relatorio

PERFIL_ANGLO = "Anglo de emissão de relatório"
MODELO = Path(__file__).resolve().parents[1] / "assets" / "modelo_anglo.docx"
MODELO_PREENCHIDO = MODELO.with_name("modelo_anglo_preenchido.docx")
MODELO_EMISSAO = MODELO.with_name("modelo_anglo_emissao.docx")
VAZIO = "[a preencher]"
FINALIDADES = ("", "ASB", "ICE", "IFA", "IFC", "IFD", "IFI", "IFP", "VOD")
LAYOUTS_ANGLO = {"emissao": "Padrão do memorial preenchido", "completo": "Modelo completo rev2"}
CAPITULOS = {
    "escopo": "Objetivo e escopo",
    "normas": "Códigos e normas",
    "referencias": "Documentos de referência",
    "premissas": "Premissas de cálculo",
    "materiais": "Materiais",
    "geometria": "Geometria e sistema estrutural",
    "cargas": "Carregamentos",
    "combinacoes": "Combinações de ações",
    "modelo": "Modelo de cálculo e análise estrutural",
    "elu": "Verificação dos elementos — ELU",
    "els": "Deslocamentos e vibrações — ELS",
    "ligacoes": "Ligações",
    "bases": "Bases de pilares e chumbadores",
    "acessos": "Elementos de acesso e proteção contra quedas",
    "montagem": "Fabricação e montagem",
    "resumo": "Resumo das verificações",
    "conclusao": "Conclusão e recomendações",
    "anexos": "Anexos",
}
OPCIONAIS = ("elu", "els", "ligacoes", "bases", "acessos", "montagem", "anexos")
_GRUPOS = {
    **dict.fromkeys(("273", "288", "307", "320", "327", "338", "346"), "elu"),
    **dict.fromkeys(("362", "368", "373"), "els"),
    **dict.fromkeys(("398", "420", "432"), "ligacoes"),
    **dict.fromkeys(("447", "461"), "bases"),
    **dict.fromkeys(("482", "486", "491", "500", "505", "509"), "acessos"),
}
_CAPITULOS_EMISSAO = {
    "escopo": "Objetivo e escopo",
    "normas": "Códigos e normas",
    "referencias": "Documentos de referência",
    "premissas": "Premissas de cálculo",
    "entradas": "DADOS DE ENTRADA E ESFORÇOS SOLICITANTES DE CÁLCULO",
    "geometria": "GEOMETRIA ADOTADA E DETALHAMENTO CONSTRUTIVO",
    "placa": "VERIFICAÇÃO DA PLACA DE BASE À COMPRESSÃO E FLEXÃO",
    "ancoragem": "VERIFICAÇÃO DA ANCORAGEM NO CONCRETO",
    "solda": "VERIFICAÇÃO DAS LIGAÇÕES SOLDADAS",
    "elu": CAPITULOS["elu"],
    "els": CAPITULOS["els"],
    "ligacoes": CAPITULOS["ligacoes"],
    "acessos": CAPITULOS["acessos"],
    "resumo": "QUADRO RESUMO DE VERIFICAÇÕES E NOTAS EXECUTIVAS DE MONTAGEM",
    "anexos": CAPITULOS["anexos"],
}
_DESTINOS_EMISSAO = {"cargas": "entradas", "447": "placa", "461": "ancoragem", "420": "solda"}
_CAMPOS_VERIFICACAO_EMISSAO = {
    "placa": (
        "Tensão de contato no concreto",
        "Espessura mínima da placa sob compressão",
        "Espessura mínima da placa sob tração",
    ),
    "ancoragem": (
        "Resistência do aço dos chumbadores",
        "Ruptura do cone de concreto à tração",
        "Arrancamento e ruptura de borda ao cisalhamento",
    ),
    "solda": ("Solicitação e resistência da ligação soldada",),
}
_FINALIDADES_EMISSAO = {
    "IFA": (2, 0),
    "IFC": (2, 4),
    "IAP": (2, 7),
    "IFI": (2, 10),
    "IFP": (4, 0),
    "ASB": (4, 4),
    "VOD": (4, 7),
    "ICE": (4, 10),
    "IFD": (4, 10),
}
_PREFIXOS_INTERNACIONAIS = ("ACI ", "AISC ", "ANSI", "ASTM ", "AWS ", "EN ", "ISO ", "OSHA", "RCSC")

# Posições no DOCX original rev2. O modelo de emissão conserva os quadros
# dessas referências, mas não copia resultados, taxas ou aprovações de exemplo.
_QUADROS_PADRAO = {
    "normas": 59,
    "criterios": 70,
    "materiais": 107,
    "divergencias": 101,
    "minimos": 113,
    "vento": 166,
    "coeficientes": 199,
    "elu_comb": 206,
    "els_comb": 211,
    "plataformas": 484,
    "escadas": 488,
    "guarda_corpos": 493,
    "marinheiro": 503,
}
_QUADROS_ADICIONAIS = {
    "139": (145,),
    "155": (157,),
    "172": (174,),
    "229": (233,),
    "266": (270,),
    "357": (359,),
    "393": (395,),
    "420": (422,),
    "442": (444,),
}
_TEXTOS_PADRAO = {
    "premissas": tuple(range(84, 97)),
    "115": (116, 117, 118, 119),
    "163": (168, 169, 170),
    "179": (180,),
    "185": (187,),
    "202": (204,),
    "229": (231,),
    "273": tuple(range(275, 287)),
    "288": tuple(i for i in range(290, 307) if i != 298),
    "307": tuple(range(309, 320)),
    "320": tuple(range(322, 327)),
    "327": tuple(range(329, 337)),
    "338": tuple(range(340, 345)),
    "346": (348, 350, 351),
    "362": (363, 364),
    "373": (375, 376, 377),
    "383": tuple(range(385, 393)),
    "398": tuple(i for i in range(400, 420) if i != 403),
    "420": tuple(range(425, 430)),
    "432": tuple(range(433, 437)),
    "447": tuple(range(449, 460)),
    "461": tuple(range(463, 468)),
    "491": (496, 497, 498),
    "505": (506, 507, 508),
    "montagem": tuple(range(515, 524)),
    "532": (533, 534),
}
_ROTULO_REFERENCIA = "Referência do modelo Anglo — confirme a aplicabilidade ao projeto."


@lru_cache(maxsize=1)
def _referencia_anglo():
    conteudo = MODELO_PREENCHIDO.read_bytes()
    doc = Document(BytesIO(conteudo))
    return doc, hashlib.sha256(conteudo).hexdigest()


def _tem_dados(linhas):
    return any(
        valor is not None and str(valor).strip() not in {"", VAZIO}
        for linha in linhas
        for valor in linha
    )


def _texto(valor: Any) -> str:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return VAZIO
    if isinstance(valor, (tuple, list)):
        return "\n".join(_texto(item) for item in valor) if valor else VAZIO
    return str(valor)


def _linhas(itens, *chaves):
    return [[_texto(item.get(chave)) for chave in chaves] for item in itens]


def _secao_calculo(registro: Mapping[str, Any]) -> str:
    titulo = " ".join(
        str(registro.get(k) or "") for k in ("modulo_id", "titulo", "modelo_externo")
    ).casefold()
    if any(t in titulo for t in ("linha de vida", "queda")):
        return "509"
    if any(t in titulo for t in ("gradil", "grade de piso")):
        return "505"
    if any(t in titulo for t in ("chumbador", "ancoragem")):
        return "461"
    if "solda" in titulo:
        return "420"
    if any(t in titulo for t in ("base", "fundação", "fundacao")):
        return "447"
    if "parafus" in titulo:
        return "398"
    if any(t in titulo for t in ("ligaç", "ligacao", "emenda")):
        return "432"
    if any(t in titulo for t in ("marinheiro", "marinheira")):
        return "500"
    if any(t in titulo for t in ("escada", "degrau")):
        return "486"
    if any(t in titulo for t in ("guarda-corpo", "guarda_corpo", "corrimão")):
        return "491"
    if any(t in titulo for t in ("vibra", "frequência")):
        return "373"
    if "deslocamento horizontal" in titulo:
        return "368"
    if any(t in titulo for t in ("deslocamento", "flecha")):
        return "362"
    if any(t in titulo for t in ("vento", "cargas_esqueleto")):
        return "cargas"
    if any(t in titulo for t in ("flambagem", "compressão", "coluna")):
        return "288"
    if any(t in titulo for t in ("tração", "tracao")):
        return "273"
    if "cortante" in titulo:
        return "320"
    if any(t in titulo for t in ("flexão", "viga")):
        return "307"
    if "forcas_localizadas" in titulo:
        return "338"
    return "elu"


def montar_modelo_anglo(projeto, *, registros_ids=None, metadata_extra=None):
    """Compõe o Word e a prévia com o mesmo conjunto de dados."""
    metadata_extra = dict(metadata_extra or {})
    config = projeto.get("configuracao_relatorio") or {}
    anglo = dict(metadata_extra.get("anglo", config.get("anglo") or {}))
    layout = "completo" if anglo.get("layout") == "completo" else "emissao"
    anglo["layout"] = layout
    base = projeto.get("base_projeto") or {}
    omitidos = set(anglo.get("nao_aplicaveis") or ()) & set(OPCIONAIS)
    permitidos = {str(v) for v in registros_ids} if registros_ids is not None else None
    ids = []
    excluidos = []
    for registro in projeto.get("registros_tecnicos", []):
        chave = str(registro.get("id") or "")
        if not chave or (permitidos is not None and chave not in permitidos):
            continue
        secao = _secao_calculo(registro)
        if _GRUPOS.get(secao, secao) in omitidos:
            excluidos.append(registro.get("titulo") or chave)
        else:
            ids.append(chave)
    if registros_ids is not None:
        presentes = set(ids)
        ids = [str(v) for v in registros_ids if str(v) in presentes]
    modelo = montar_modelo_relatorio(
        projeto,
        secoes_incluidas=["registros", "plano_calculo", "conclusao"],
        registros_ids=ids,
        metadata_extra=metadata_extra,
        somente_capitulos=True,
        repetir_bases=True,
    )
    from core.robot_integracao import tabelas_de_proveniencia

    fontes_robot = tabelas_de_proveniencia(
        [r for r in projeto.get("registros_tecnicos", []) if str(r.get("id")) in ids]
    )
    md = modelo["metadata"]
    contexto = md["contexto_estrutural"]
    campos = {
        "unidade_industrial": projeto.get("unidade_industrial"),
        "area": projeto.get("area"),
        "titulo_capa": metadata_extra.get("titulo") or projeto.get("nome"),
        "tag_equipamento": projeto.get("tag_equipamento"),
        **{k: anglo.get(k) for k in ("numero_anglo", "numero_contratada", "fase", "finalidade")},
    }

    casos = [c for c in projeto.get("casos_carga", []) if c.get("ativo", True)]
    combinacoes = [c for c in projeto.get("combinacoes_carga", []) if c.get("ativo", True)]
    documentos = projeto.get("anexos", [])
    normas = projeto.get("normas", [])
    materiais = projeto.get("materiais_projeto", [])
    tabelas = {
        "normas": _linhas(normas, "codigo", "titulo", "edicao", "escopo"),
        "criterios": [[_texto(anglo.get("criterio_cliente")), VAZIO, VAZIO]],
        "documentos": _linhas(documentos, "codigo", "titulo", "revisao"),
        "programas": [
            [_texto(contexto.get("modelo")), VAZIO, VAZIO, _texto(contexto.get("validacao"))]
        ],
        "materiais": [
            [
                _texto(m.get("aplicabilidade")),
                _texto(m.get("nome")),
                _texto((m.get("propriedades") or {}).get("Sy_MPa")),
                _texto((m.get("propriedades") or {}).get("Sut_MPa")),
                _texto(m.get("documento") or m.get("fonte")),
            ]
            for m in materiais
        ],
        "perfis": _linhas(projeto.get("componentes", []), "tag", "perfil", "material", "descricao"),
        "casos": [
            [
                _texto(c.get("codigo")),
                _texto(c.get("nome")),
                _texto(c.get("origem") or c.get("referencia")),
                " · ".join(
                    f"{ROTULOS_CARGA[chave]}: {valor} {UNIDADES_CARGA[chave]}"
                    for chave, valor in (c.get("cargas") or {}).items()
                    if chave in ROTULOS_CARGA and valor != 0
                )
                or VAZIO,
            ]
            for c in casos
        ],
        "elu_comb": [
            [VAZIO, _texto(c.get("nome")), fatores_legiveis(c, casos), "Cadastrada"]
            for c in combinacoes
            if "ELU" in str(c.get("tipo") or "").upper()
        ],
        "els_comb": [
            [
                VAZIO,
                _texto(c.get("nome")),
                _texto(c.get("tipo")),
                fatores_legiveis(c, casos),
                "Cadastrada",
            ]
            for c in combinacoes
            if "ELS" in str(c.get("tipo") or "").upper()
        ],
        "modelo": [["Modelo e método", _texto(contexto.get("modelo"))]],
        "fontes_robot": fontes_robot,
        "pendencias": [],
        "anexos": [],
        "resumo": [],
        "quadro_emissao": [],
        "geometria_emissao": [
            [
                _texto(" · ".join(str(c[k]) for k in ("tag", "nome") if c.get(k))),
                _texto(" · ".join(str(c[k]) for k in ("perfil", "material") if c.get(k))),
                _texto(c.get("descricao")),
            ]
            for c in projeto.get("componentes", [])
        ],
    }
    textos = {
        "41": [projeto.get("objetivo")],
        "45": [projeto.get("descricao"), base.get("limitacoes")],
        "50": [base.get("condicoes_operacao")],
        "premissas": [base.get("criterio_aceitacao"), base.get("vida_requerida")],
        "126": [contexto.get("sistema")],
        "cargas": [contexto.get("acoes")],
        "combinacoes": [
            contexto.get("combinacoes"),
            *[
                f"{_texto(c.get('nome'))} ({_texto(c.get('tipo'))}): {fatores_legiveis(c, casos)}. Cadastrada."
                for c in combinacoes
                if not any(sigla in str(c.get("tipo") or "").upper() for sigla in ("ELU", "ELS"))
            ],
        ],
        "224": [contexto.get("vinculos")],
        "251": [contexto.get("validacao")],
        "els": [contexto.get("servico")],
        "conclusao": [
            *([modelo["maior_aproveitamento"]] if modelo.get("maior_aproveitamento") else []),
            contexto.get("conclusao_geral"),
        ],
        "532": [contexto.get("recomendacoes")],
    }
    registros = {str(r["id"]): r for r in modelo["registros"] if r.get("id")}
    calculos: dict[str, list[dict]] = {}
    blocos_por_id = {s["registro_id"]: s for s in modelo["secoes"] if s.get("registro_id")}
    for registro_id, registro in registros.items():
        secao = blocos_por_id.get(registro_id)
        if secao:
            calculos.setdefault(_secao_calculo(registro), []).append(secao)
    quadro = next((s for s in modelo["secoes"] if "Quadro-resumo dos cálculos" in s["titulo"]), {})
    for bloco in blocos_da_secao(quadro):
        if bloco["tipo"] == "tabela":
            tabelas["resumo"] = [
                [linha[1], linha[2][0], linha[0], linha[5], linha[6]]
                for linha in bloco["linhas"]
                if isinstance(linha[2], tuple)
            ]
            tabelas["quadro_emissao"] = [
                [
                    " · ".join(v for v in (linha[1], linha[2][0]) if v != "-"),
                    VAZIO,
                    VAZIO,
                    linha[5],
                    linha[6],
                ]
                for linha in bloco["linhas"]
                if isinstance(linha[2], tuple)
            ]
    historico = [
        item
        for item in (config.get("emissoes") or [])
        if isinstance(item, Mapping)
        and item.get("perfil") == PERFIL_ANGLO
        and item.get("codigo") == (campos["numero_anglo"] or md["codigo"])
        and str(item.get("revisao")) != str(md["revisao"])
    ]
    anteriores = list({str(item["revisao"]): item for item in historico}.values())[-4:]
    payload = {
        "base": modelo["snapshot_hash"],
        "referencia_anglo": _referencia_anglo()[1],
        "modelo_emissao": _hash_emissao() if layout == "emissao" else None,
        "anglo": anglo,
        "campos": campos,
        "textos": textos,
        "tabelas": tabelas,
        "historico": anteriores,
    }
    snapshot = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()
    capitulos = CAPITULOS
    grupos = {
        chave: [
            s
            for destino, secoes in calculos.items()
            if _GRUPOS.get(destino, destino) == chave
            for s in secoes
        ]
        for chave in CAPITULOS
    }
    if layout == "emissao":
        grupos = {chave: [] for chave in _CAPITULOS_EMISSAO}
        for destino, secoes in calculos.items():
            grupos[_DESTINOS_EMISSAO.get(destino, _GRUPOS.get(destino, destino))].extend(secoes)
        capitulos = {
            chave: titulo
            for chave, titulo in _CAPITULOS_EMISSAO.items()
            if chave
            in {"escopo", "normas", "referencias", "premissas", "entradas", "geometria", "resumo"}
            or grupos[chave]
            or (
                not ids
                and chave in {"placa", "ancoragem", "solda"}
                and ("ligacoes" if chave == "solda" else "bases") not in omitidos
            )
            or (chave == "anexos" and documentos and chave not in omitidos)
        }
    return {
        **modelo,
        "snapshot_hash": snapshot,
        "anglo": anglo,
        "campos_anglo": campos,
        "capitulos_anglo": capitulos,
        "omitidos_anglo": omitidos,
        "textos_anglo": textos,
        "tabelas_anglo": tabelas,
        "calculos_anglo": calculos,
        "excluidos_anglo": excluidos,
        "grupos_anglo": grupos,
        "historico_anglo": anteriores,
    }


@lru_cache(maxsize=1)
def _hash_emissao():
    return hashlib.sha256(MODELO_EMISSAO.read_bytes()).hexdigest()


def _substituir_texto(paragrafo, valor):
    if paragrafo.runs:
        paragrafo.runs[0].text = valor
        for run in paragrafo.runs[1:]:
            run.text = ""
    else:
        paragrafo.add_run(valor)


def _celula(cell, valor):
    _substituir_texto(cell.paragraphs[0], _texto(valor))


def _preencher_tabela(tabela, linhas):
    prototipo = deepcopy(tabela.rows[1]._tr)
    tabela._tbl.remove(tabela.rows[1]._tr)
    for linha in linhas or [[VAZIO] * len(tabela.columns)]:
        tabela._tbl.append(deepcopy(prototipo))
        for cell, valor in zip(tabela.rows[-1].cells, linha, strict=True):
            _celula(cell, valor)


def _inserir_texto(doc, antes, texto, estilo="AFB_PADRAO"):
    p = doc.add_paragraph(_texto(texto), style=estilo)
    antes.addprevious(p._p)
    return p


def _render_calculo(doc, antes, secao, nivel):
    _inserir_texto(
        doc, antes, re.sub(r"^\d+(?:\.\d+)*\s+", "", secao["titulo"]), f"Heading {nivel}"
    )
    for bloco in blocos_da_secao(secao):
        tipo = bloco["tipo"]
        if tipo == "tabela":
            if bloco.get("legenda"):
                _inserir_texto(doc, antes, bloco["legenda"], "Caption")
            tabela = doc.add_table(
                rows=2, cols=len(bloco["cabecalhos"]), style="AA Factsheet Table"
            )
            for cell, valor in zip(tabela.rows[0].cells, bloco["cabecalhos"], strict=True):
                _celula(cell, valor)
            repetir = OxmlElement("w:tblHeader")
            tabela.rows[0]._tr.get_or_add_trPr().append(repetir)
            _preencher_tabela(tabela, bloco["linhas"])
            antes.addprevious(tabela._tbl)
        elif tipo == "imagem" and bloco.get("png"):
            p = _inserir_texto(doc, antes, "")
            p.clear()
            p.add_run().add_picture(BytesIO(bloco["png"]), width=Cm(15))
            if bloco.get("legenda"):
                _inserir_texto(doc, antes, bloco["legenda"], "Caption")
        elif tipo in {"bullets", "passos"}:
            for item in bloco.get("itens", []):
                _inserir_texto(doc, antes, item)
        elif bloco.get("texto"):
            _inserir_texto(
                doc, antes, " ".join(filter(None, [bloco.get("rotulo"), bloco["texto"]]))
            )


def _render_emissao(doc, modelo, referencia):
    """Compõe os capítulos sobre o documento de emissão validado pelo usuário."""
    fim = doc.element.body.sectPr
    quadros = dict(
        zip(
            (
                "normas",
                "internacionais",
                "criterios",
                "documentos",
                "programas",
                "geometria",
                "apoios",
                "resumo",
            ),
            (t._tbl for t in doc.tables[3:]),
            strict=True,
        )
    )
    for elemento in list(doc.element.body)[19:-1]:
        doc.element.body.remove(elemento)
    dados = modelo["tabelas_anglo"]
    textos = modelo["textos_anglo"]
    numero_quadro = 0

    def titulo(texto, nivel=2):
        _inserir_texto(doc, fim, texto, f"Heading {nivel}")

    def paragrafo(texto):
        return _inserir_texto(doc, fim, texto)

    def trecho(*chaves, padrao=False):
        linhas = [
            texto
            for chave in chaves
            for texto in textos.get(chave, [])
            if texto and _texto(texto) != VAZIO
        ]
        if not linhas and padrao:
            paragrafo(_ROTULO_REFERENCIA).paragraph_format.keep_with_next = True
            linhas = [
                Paragraph(referencia.element.body[i], referencia).text
                for i in _TEXTOS_PADRAO[chaves[0]]
            ]
        for linha in linhas or [VAZIO]:
            paragrafo(linha)

    def quadro(chave, linhas, nome, *, padrao=None):
        nonlocal numero_quadro
        numero_quadro += 1
        legenda = _inserir_texto(doc, fim, f"Tabela {numero_quadro}. {nome}.", "Caption")
        legenda.paragraph_format.keep_with_next = True
        if not _tem_dados(linhas) and padrao is not None:
            paragrafo(_ROTULO_REFERENCIA).paragraph_format.keep_with_next = True
            original = Table(referencia.element.body[padrao], referencia)
            largura = len(Table(quadros[chave], doc).columns)
            linhas = [[cell.text for cell in row.cells[:largura]] for row in original.rows[1:]]
        node = quadros[chave]
        fim.addprevious(node)
        _preencher_tabela(Table(node, doc), linhas)

    for chave, nome in modelo["capitulos_anglo"].items():
        titulo(nome, 1)
        if chave == "escopo":
            titulo("Objetivo")
            trecho("41", "45")
            titulo("Localização e condições de operação")
            trecho("50")
        elif chave == "normas":
            nacionais, internacionais = [], []
            for linha in dados["normas"]:
                codigo, descricao, edicao, uso = linha
                if codigo.upper().startswith(_PREFIXOS_INTERNACIONAIS):
                    internacionais.append(
                        [
                            codigo,
                            f"{descricao} ({edicao})" if edicao != VAZIO else descricao,
                            uso,
                        ]
                    )
                else:
                    nacionais.append(linha)
            titulo("Normas brasileiras e regulamentos")
            quadro(
                "normas",
                nacionais,
                "Normas brasileiras e regulamentos",
                padrao=_QUADROS_PADRAO["normas"],
            )
            titulo("Normas e referências internacionais")
            quadro(
                "internacionais", internacionais, "Normas e referências internacionais", padrao=64
            )
        elif chave == "referencias":
            titulo("Critérios e padrões do cliente")
            quadro(
                "criterios",
                [linha[:2] for linha in dados["criterios"]],
                "Critérios e padrões do cliente",
                padrao=_QUADROS_PADRAO["criterios"],
            )
            titulo("Desenhos e documentos do projeto")
            quadro("documentos", dados["documentos"], "Desenhos e documentos do projeto")
            titulo("Programas e planilhas de cálculo")
            quadro("programas", dados["programas"], "Programas e planilhas de cálculo")
        elif chave == "premissas":
            trecho("premissas", padrao=True)
        elif chave == "entradas":
            titulo("Propriedades geométricas e especificação dos materiais")
            linhas = dados["geometria_emissao"] or [
                [
                    elemento,
                    especificacao,
                    _texto(
                        " · ".join(
                            f"{nome} = {valor} MPa"
                            for nome, valor in (("fy", fy), ("fu", fu))
                            if valor != VAZIO
                        )
                    ),
                ]
                for elemento, especificacao, fy, fu, _ in dados["materiais"]
            ]
            quadro("geometria", linhas, "Propriedades geométricas e materiais")
            titulo("Esforços solicitantes críticos nos apoios")
            quadro("apoios", [], "Esforços nos apoios por combinação simultânea")
            if dados["casos"] or dados["elu_comb"] or dados["els_comb"]:
                titulo("Casos de carga e combinações cadastrados")
                for codigo, nome_caso, origem, cargas in dados["casos"]:
                    paragrafo(f"{codigo} · {nome_caso} · {origem} · {cargas}")
                for _, nome_comb, fatores, _ in dados["elu_comb"]:
                    paragrafo(f"ELU · {nome_comb} · {fatores}")
                for _, nome_comb, tipo, fatores, _ in dados["els_comb"]:
                    paragrafo(f"{tipo} · {nome_comb} · {fatores}")
            for texto in textos.get("cargas", []) + textos.get("combinacoes", []):
                if texto:
                    paragrafo(texto)
            if dados["fontes_robot"]:
                _render_calculo(
                    doc,
                    fim,
                    {"titulo": "Dados do Autodesk Robot", "tabelas": dados["fontes_robot"]},
                    2,
                )
        elif chave == "geometria":
            trecho("126", "224", "251")
        elif chave == "resumo":
            quadro("resumo", dados["quadro_emissao"], "Resumo das verificações")
            if "montagem" not in modelo["omitidos_anglo"]:
                titulo("Notas executivas para obra e montagem")
                trecho("532")
            titulo("Conclusão")
            trecho("conclusao")
        elif chave == "anexos":
            for codigo, titulo_doc, revisao in dados["documentos"]:
                paragrafo(f"{codigo} · {titulo_doc} · Rev. {revisao}")
        elif not modelo["grupos_anglo"][chave]:
            for subtitulo in _CAMPOS_VERIFICACAO_EMISSAO[chave]:
                titulo(subtitulo)
                identificacao = paragrafo(f"Elemento: {VAZIO}. Combinação: {VAZIO}.")
                identificacao.paragraph_format.keep_with_next = True
                metodo = paragrafo(
                    f"Método e referência: {VAZIO}. Solicitação e resistência: {VAZIO}."
                )
                metodo.paragraph_format.keep_with_next = True
                paragrafo(f"Conclusão: {VAZIO}.")
        for calculo in modelo["grupos_anglo"][chave]:
            _render_calculo(doc, fim, calculo, 2)


def gerar_word_anglo(modelo) -> bytes:
    """Preenche a cópia preparada do documento, preservando a geometria da referência."""
    emissao = modelo["anglo"].get("layout") == "emissao"
    doc = Document(MODELO_EMISSAO if emissao else MODELO)
    referencia, _ = _referencia_anglo()
    md, campos = modelo["metadata"], modelo["campos_anglo"]
    anglo = modelo["anglo"]
    capa = list(doc.element.body)
    textos_capa = {
        2: _texto(campos["unidade_industrial"]),
        3: _texto(campos["area"]),
        4: _texto(campos["titulo_capa"]),
        5: f"MEMÓRIA DE CÁLCULO ESTRUTURAL – {_texto(campos['tag_equipamento'])}",
        6: f"ESTRUTURAS METÁLICAS – {_texto(campos['fase'])}",
        8: "Anglo American No: ",
        9: f"Revision: {_texto(md['revisao'])}",
        10: f"Date: {_texto(md['emissao'])}\tContractor No: {_texto(campos['numero_contratada'])}",
    }
    if emissao:
        textos_capa = {
            2: "\n".join(
                _texto(campos[k])
                for k in ("unidade_industrial", "area", "titulo_capa", "tag_equipamento")
            )
            + f"\nMEMÓRIA DE CÁLCULO ESTRUTURAL – {_texto(campos['fase'])}",
            3: "Anglo American No: ",
            4: f"Revisão: {_texto(md['revisao'])}",
            5: f"Data: {_texto(md['emissao'])}\tNº Contratada: {_texto(campos['numero_contratada'])}",
        }
    for indice, valor in textos_capa.items():
        _substituir_texto(Paragraph(capa[indice], doc), valor)
    for node in capa[3 if emissao else 8].xpath(".//w:sdtContent//w:t"):
        node.text = _texto(campos["numero_anglo"])
    for n, papel in enumerate(("responsavel", "verificador", "aprovador"), 1):
        _celula(doc.tables[0].cell(n, 1), md.get(papel))
        _celula(doc.tables[0].cell(n, 2), anglo.get(f"cargo_{papel}"))
    linha_atual = (
        md["revisao"],
        md["emissao"],
        anglo.get("descricao_revisao"),
        md["responsavel"],
        None,
        None,
    )
    linhas = [
        (i["revisao"], i["emissao"], i.get("descricao_revisao"), i.get("responsavel"), None, None)
        for i in modelo["historico_anglo"]
    ] + [linha_atual]
    linhas_disponiveis = list(doc.tables[1].rows)[2:]
    for linha, valores in zip(linhas_disponiveis, linhas[-len(linhas_disponiveis) :], strict=False):
        for cell, valor in zip(linha.cells, valores, strict=True):
            _celula(cell, valor)
    destinos = {
        "ASB": (2, 0),
        "ICE": (2, 4),
        "IFA": (2, 7),
        "IFC": (2, 10),
        "IFD": (4, 0),
        "IFI": (4, 4),
        "IFP": (4, 7),
        "VOD": (4, 10),
    }
    if finalidade := (_FINALIDADES_EMISSAO if emissao else destinos).get(campos["finalidade"]):
        linha, coluna = finalidade
        _celula(doc.tables[2].rows[linha].cells[coluna], "X")
        if emissao and campos["finalidade"] in {"ICE", "IFD"}:
            descricao = "CERTIFICADO" if campos["finalidade"] == "ICE" else "PARA PROJETO"
            _celula(
                doc.tables[2].rows[linha].cells[coluna + 1], f"{campos['finalidade']} - {descricao}"
            )
    for part in doc.part.package.parts:
        if "/header" in str(part.partname):
            for node in part.element.xpath("//w:t"):
                if node.text == "{{numero_anglo}}":
                    node.text = _texto(campos["numero_anglo"])
    doc.core_properties.title = "MEMÓRIA DE CÁLCULO ESTRUTURAL"
    doc.core_properties.keywords = _texto(campos["numero_anglo"])
    update = doc.settings.element.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        doc.settings.element.append(update)
    update.set(qn("w:val"), "true")
    if emissao:
        _render_emissao(doc, modelo, referencia)
        saida = BytesIO()
        doc.save(saida)
        return saida.getvalue()
    capitulo = ""
    for node in list(doc.element.body)[22:]:
        if node.tag == qn("w:sectPr"):
            continue
        if node.tag == qn("w:tbl"):
            if capitulo in modelo["omitidos_anglo"]:
                node.getparent().remove(node)
            continue
        p = Paragraph(node, doc)
        if p.style.name == "Heading 1":
            capitulo = next((chave for chave, titulo in CAPITULOS.items() if p.text == titulo), "")
            if capitulo in modelo["omitidos_anglo"]:
                _inserir_texto(doc, node.getnext(), "Não aplicável.")
            continue
        if capitulo in modelo["omitidos_anglo"]:
            node.getparent().remove(node)
            continue
        if match := re.fullmatch(r"\{\{(cap|sub|table):(\w+)\}\}", p.text):
            tipo, chave = match.groups()
            if tipo == "table":
                tabela = Table(node.getnext(), doc)
                linhas = modelo["tabelas_anglo"].get(chave, [])
                if chave in _QUADROS_PADRAO and not _tem_dados(linhas):
                    padrao = referencia.element.body[_QUADROS_PADRAO[chave]]
                    aviso = _inserir_texto(doc, node, _ROTULO_REFERENCIA)
                    aviso.paragraph_format.keep_with_next = True
                    tabela._tbl.addprevious(deepcopy(padrao))
                    if chave == "normas":
                        legenda = _inserir_texto(doc, tabela._tbl, "Referências internacionais")
                        legenda.paragraph_format.keep_with_next = True
                        tabela._tbl.addprevious(deepcopy(referencia.element.body[64]))
                    tabela._tbl.getparent().remove(tabela._tbl)
                else:
                    _preencher_tabela(tabela, linhas)
            else:
                textos = modelo["textos_anglo"].get(chave, [])
                calculos = modelo["calculos_anglo"].get(chave, [])
                if (
                    tipo == "sub"
                    and chave not in _TEXTOS_PADRAO
                    and chave not in _QUADROS_ADICIONAIS
                    and node.getnext().tag != qn("w:tbl")
                    and Paragraph(node.getnext(), doc).style.name != "Caption"
                    and not Paragraph(node.getnext(), doc).text.startswith("{{table:")
                    and not textos
                    and not calculos
                ):
                    textos = (
                        [f"Elemento: {VAZIO}. Dados e método: {VAZIO}. Resultado: {VAZIO}."]
                        if chave in _GRUPOS
                        else [None]
                    )
                for texto in textos:
                    _inserir_texto(doc, node, texto)
                if chave in _QUADROS_ADICIONAIS:
                    aviso = _inserir_texto(doc, node, _ROTULO_REFERENCIA)
                    aviso.paragraph_format.keep_with_next = True
                    for indice in _QUADROS_ADICIONAIS[chave]:
                        node.addprevious(deepcopy(referencia.element.body[indice]))
                if not calculos and chave in _TEXTOS_PADRAO:
                    if chave not in _QUADROS_ADICIONAIS:
                        aviso = _inserir_texto(doc, node, _ROTULO_REFERENCIA)
                        aviso.paragraph_format.keep_with_next = True
                    for indice in _TEXTOS_PADRAO[chave]:
                        texto = Paragraph(referencia.element.body[indice], referencia).text
                        texto = texto.partition(" Na planilha da emenda W 200,")[0]
                        texto = re.sub(r"\[OK(?=\]| \|)", VAZIO[:-1], texto)
                        _inserir_texto(doc, node, texto)
                for calculo in calculos:
                    _render_calculo(doc, node, calculo, 3 if tipo == "sub" else 2)
            node.getparent().remove(node)
    saida = BytesIO()
    doc.save(saida)
    return saida.getvalue()
