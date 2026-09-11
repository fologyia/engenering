"""Testes da biblioteca de normas: catálogo, indexação de PDFs e busca.

Extração de texto de PDF é testada com um PDF mínimo gerado com pypdf, para
exercitar o caminho real em vez de simular seu retorno.
"""

import json

import pytest

from core import standards_library as normas

CATALOGO_MINIMO = [
    {
        "id": "abnt-nbr-8800",
        "codigo": "NBR 8800",
        "titulo": "Projeto de estruturas de aço",
        "segmento": "Estruturas",
        "aplicacao": "Dimensionamento de perfis de aço",
        "quando_consultar": "Ao dimensionar vigas e colunas de aço",
        "pontos_chave": ["Flambagem", "Flexão"],
        "modulos": ["vigas_eixos"],
        "palavras_chave": ["aço", "estrutura"],
        "aliases": ["NBR8800"],
        "fonte_url": "https://exemplo.invalido/nbr8800",
    },
    {
        "id": "abnt-nbr-6118",
        "codigo": "NBR 6118",
        "titulo": "Projeto de estruturas de concreto",
        "segmento": "Estruturas",
        "aplicacao": "Dimensionamento de concreto armado",
        "quando_consultar": "Ao dimensionar peças de concreto",
        "pontos_chave": ["Flexão", "Cisalhamento"],
        "modulos": [],
        "palavras_chave": ["concreto"],
        "aliases": [],
        "fonte_url": "https://exemplo.invalido/nbr6118",
    },
]


def _escrever_catalogo(caminho, dados):
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


# ---------------------------------------------------------------------------
# normalizar_texto
# ---------------------------------------------------------------------------


def test_normalizar_texto_remove_acentos_e_pontuacao():
    assert normas.normalizar_texto("Aço-8800, seção!") == "ACO 8800 SECAO"


def test_normalizar_texto_de_valor_vazio_e_string_vazia():
    assert normas.normalizar_texto(None) == ""
    assert normas.normalizar_texto("") == ""


# ---------------------------------------------------------------------------
# carregar_catalogo
# ---------------------------------------------------------------------------


def test_carregar_catalogo_valido(tmp_path):
    caminho = _escrever_catalogo(tmp_path / "catalogo.json", CATALOGO_MINIMO)
    catalogo = normas.carregar_catalogo(caminho)
    assert len(catalogo) == 2
    assert catalogo[0]["codigo"] == "NBR 8800"


def test_carregar_catalogo_arquivo_ausente(tmp_path):
    with pytest.raises(normas.BibliotecaNormasErro, match="não encontrado"):
        normas.carregar_catalogo(tmp_path / "nao_existe.json")


def test_carregar_catalogo_json_invalido(tmp_path):
    caminho = tmp_path / "catalogo.json"
    caminho.write_text("{isto não é json", encoding="utf-8")
    with pytest.raises(normas.BibliotecaNormasErro, match="inválido"):
        normas.carregar_catalogo(caminho)


def test_carregar_catalogo_nao_e_lista(tmp_path):
    caminho = _escrever_catalogo(tmp_path / "catalogo.json", {"nao": "lista"})
    with pytest.raises(normas.BibliotecaNormasErro, match="lista de normas"):
        normas.carregar_catalogo(caminho)


def test_carregar_catalogo_entrada_nao_e_objeto(tmp_path):
    caminho = _escrever_catalogo(tmp_path / "catalogo.json", ["não é objeto"])
    with pytest.raises(normas.BibliotecaNormasErro, match="não é um objeto"):
        normas.carregar_catalogo(caminho)


def test_carregar_catalogo_campo_faltante(tmp_path):
    incompleto = [{**CATALOGO_MINIMO[0]}]
    del incompleto[0]["fonte_url"]
    caminho = _escrever_catalogo(tmp_path / "catalogo.json", incompleto)
    with pytest.raises(normas.BibliotecaNormasErro, match="fonte_url"):
        normas.carregar_catalogo(caminho)


def test_carregar_catalogo_id_vazio(tmp_path):
    invalido = [{**CATALOGO_MINIMO[0], "id": "  "}]
    caminho = _escrever_catalogo(tmp_path / "catalogo.json", invalido)
    with pytest.raises(normas.BibliotecaNormasErro, match="vazio ou duplicado"):
        normas.carregar_catalogo(caminho)


def test_carregar_catalogo_id_duplicado(tmp_path):
    duplicado = [CATALOGO_MINIMO[0], {**CATALOGO_MINIMO[1], "id": CATALOGO_MINIMO[0]["id"]}]
    caminho = _escrever_catalogo(tmp_path / "catalogo.json", duplicado)
    with pytest.raises(normas.BibliotecaNormasErro, match="vazio ou duplicado"):
        normas.carregar_catalogo(caminho)


# ---------------------------------------------------------------------------
# catalogo_por_id / segmentos_catalogo
# ---------------------------------------------------------------------------


def test_catalogo_por_id_indexa_pelo_id():
    indexado = normas.catalogo_por_id(CATALOGO_MINIMO)
    assert set(indexado) == {"abnt-nbr-8800", "abnt-nbr-6118"}
    assert indexado["abnt-nbr-8800"]["codigo"] == "NBR 8800"


def test_segmentos_catalogo_e_ordenado_e_sem_repeticao():
    assert normas.segmentos_catalogo(CATALOGO_MINIMO) == ["Estruturas"]


# ---------------------------------------------------------------------------
# identificar_norma
# ---------------------------------------------------------------------------


def test_identificar_norma_pelo_codigo():
    norma = normas.identificar_norma("Cópia da NBR 8800 revisada", CATALOGO_MINIMO)
    assert norma is not None
    assert norma["id"] == "abnt-nbr-8800"


def test_identificar_norma_por_alias_sem_espaco():
    norma = normas.identificar_norma("arquivo_NBR8800_2008.pdf", CATALOGO_MINIMO)
    assert norma is not None
    assert norma["id"] == "abnt-nbr-8800"


def test_identificar_norma_sem_correspondencia_e_none():
    assert normas.identificar_norma("documento qualquer sem código", CATALOGO_MINIMO) is None


def test_identificar_norma_prefere_o_alias_mais_especifico():
    catalogo = [
        {**CATALOGO_MINIMO[0], "id": "curto", "codigo": "NBR 8800", "aliases": []},
        {
            **CATALOGO_MINIMO[0],
            "id": "longo",
            "codigo": "NBR 8800 PARTE 2",
            "aliases": [],
        },
    ]
    norma = normas.identificar_norma("NBR 8800 PARTE 2 anexo", catalogo)
    assert norma["id"] == "longo"


# ---------------------------------------------------------------------------
# resolver_pasta / listar_pdfs
# ---------------------------------------------------------------------------


def test_resolver_pasta_inexistente(tmp_path):
    with pytest.raises(normas.BibliotecaNormasErro, match="não existe"):
        normas.resolver_pasta(tmp_path / "fantasma")


def test_resolver_pasta_nao_e_diretorio(tmp_path):
    arquivo = tmp_path / "arquivo.txt"
    arquivo.write_text("x", encoding="utf-8")
    with pytest.raises(normas.BibliotecaNormasErro, match="não é uma pasta"):
        normas.resolver_pasta(arquivo)


def test_listar_pdfs_encontra_e_classifica_por_nome(tmp_path):
    (tmp_path / "NBR8800.pdf").write_bytes(b"conteudo")
    (tmp_path / "desconhecido.pdf").write_bytes(b"conteudo")
    (tmp_path / "nota.txt").write_bytes(b"nao e pdf")

    arquivos = normas.listar_pdfs(tmp_path, CATALOGO_MINIMO)
    assert len(arquivos) == 2
    por_nome = {arquivo.nome: arquivo for arquivo in arquivos}
    assert por_nome["NBR8800.pdf"].norma_id == "abnt-nbr-8800"
    assert por_nome["NBR8800.pdf"].codigo == "NBR 8800"
    assert por_nome["desconhecido.pdf"].norma_id is None
    assert por_nome["desconhecido.pdf"].codigo == "Não identificada"


def test_listar_pdfs_e_recursivo(tmp_path):
    subpasta = tmp_path / "estruturas"
    subpasta.mkdir()
    (subpasta / "NBR8800.pdf").write_bytes(b"conteudo")

    arquivos = normas.listar_pdfs(tmp_path, CATALOGO_MINIMO)
    assert len(arquivos) == 1
    assert arquivos[0].caminho_relativo == str(__import__("pathlib").Path("estruturas") / "NBR8800.pdf")


def test_listar_pdfs_limite_de_arquivos(tmp_path):
    for indice in range(3):
        (tmp_path / f"norma_{indice}.pdf").write_bytes(b"x")
    with pytest.raises(normas.BibliotecaNormasErro, match="limite"):
        normas.listar_pdfs(tmp_path, CATALOGO_MINIMO, maximo_arquivos=2)


# ---------------------------------------------------------------------------
# assinatura_biblioteca
# ---------------------------------------------------------------------------


def test_assinatura_biblioteca_e_estavel_para_a_mesma_lista(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"conteudo")
    arquivos = normas.listar_pdfs(tmp_path, CATALOGO_MINIMO)
    assert normas.assinatura_biblioteca(arquivos) == normas.assinatura_biblioteca(arquivos)


def test_assinatura_biblioteca_muda_quando_arquivo_e_alterado(tmp_path):
    caminho = tmp_path / "a.pdf"
    caminho.write_bytes(b"conteudo")
    antes = normas.assinatura_biblioteca(normas.listar_pdfs(tmp_path, CATALOGO_MINIMO))
    caminho.write_bytes(b"conteudo bem maior do que antes")
    depois = normas.assinatura_biblioteca(normas.listar_pdfs(tmp_path, CATALOGO_MINIMO))
    assert antes != depois


def test_assinatura_biblioteca_vazia_e_hash_de_string_vazia():
    from hashlib import sha256

    assert normas.assinatura_biblioteca([]) == sha256(b"").hexdigest()


# ---------------------------------------------------------------------------
# extrair_pdf (PDF real mínimo, gerado com pypdf)
# ---------------------------------------------------------------------------


def _criar_pdf_com_texto(caminho, paginas_texto):
    from pypdf import PdfWriter

    escritor = PdfWriter()
    for _texto in paginas_texto:
        escritor.add_blank_page(width=200, height=200)
    with caminho.open("wb") as arquivo:
        escritor.write(arquivo)


def test_extrair_pdf_arquivo_inexistente(tmp_path):
    with pytest.raises(normas.BibliotecaNormasErro, match="não encontrado"):
        normas.extrair_pdf(tmp_path / "fantasma.pdf", CATALOGO_MINIMO)


def test_extrair_pdf_extensao_errada(tmp_path):
    caminho = tmp_path / "NBR8800.txt"
    caminho.write_text("não é pdf", encoding="utf-8")
    with pytest.raises(normas.BibliotecaNormasErro, match="não encontrado"):
        normas.extrair_pdf(caminho, CATALOGO_MINIMO)


def test_extrair_pdf_excede_tamanho_maximo(tmp_path):
    caminho = tmp_path / "NBR8800.pdf"
    _criar_pdf_com_texto(caminho, [""])
    with pytest.raises(normas.BibliotecaNormasErro, match="excede o limite"):
        normas.extrair_pdf(caminho, CATALOGO_MINIMO, maximo_bytes=1)


def test_extrair_pdf_gera_estrutura_com_metadados_e_paginas(tmp_path):
    caminho = tmp_path / "NBR8800.pdf"
    _criar_pdf_com_texto(caminho, ["", "", ""])

    dado = normas.extrair_pdf(caminho, CATALOGO_MINIMO)

    assert dado["nome"] == "NBR8800.pdf"
    assert dado["numero_paginas"] == 3
    assert len(dado["paginas"]) == 3
    assert dado["criptografado"] is False
    assert dado["codigo"] == "NBR 8800"
    assert dado["norma_id"] == "abnt-nbr-8800"
    assert len(dado["sha256"]) == 64
    # Páginas em branco não têm texto suficiente: precisa de OCR.
    assert dado["paginas_com_texto"] == 0
    assert dado["cobertura_texto"] == 0.0
    assert dado["necessita_ocr"] is True


def test_extrair_pdf_sem_pypdf_gera_erro_dedicado(tmp_path, monkeypatch):
    import builtins

    caminho = tmp_path / "NBR8800.pdf"
    _criar_pdf_com_texto(caminho, [""])

    importador_original = builtins.__import__

    def importador_falho(nome, *args, **kwargs):
        if nome == "pypdf":
            raise ImportError("simulado")
        return importador_original(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importador_falho)
    with pytest.raises(normas.DependenciaPdfAusente):
        normas.extrair_pdf(caminho, CATALOGO_MINIMO)


# ---------------------------------------------------------------------------
# buscar_nos_indices
# ---------------------------------------------------------------------------


def _indice(nome, segmento, paginas):
    return {
        "nome": nome,
        "caminho": f"/normas/{nome}",
        "norma_id": "abnt-nbr-8800",
        "codigo": "NBR 8800",
        "segmento": segmento,
        "paginas": [
            {"numero": numero, "texto": texto, "caracteres": len(texto)}
            for numero, texto in enumerate(paginas, start=1)
        ],
    }


def test_buscar_nos_indices_exige_todos_os_termos():
    indices = [
        _indice("a.pdf", "Estruturas", ["flambagem local da mesa", "flexão simples"]),
    ]
    resultados = normas.buscar_nos_indices(indices, "flambagem mesa")
    assert len(resultados) == 1
    assert resultados[0]["pagina"] == 1

    assert normas.buscar_nos_indices(indices, "flambagem inexistente") == []


def test_buscar_nos_indices_consulta_vazia_devolve_lista_vazia():
    indices = [_indice("a.pdf", "Estruturas", ["texto qualquer"])]
    assert normas.buscar_nos_indices(indices, "") == []
    assert normas.buscar_nos_indices(indices, "  ") == []


def test_buscar_nos_indices_filtra_por_segmento():
    indices = [
        _indice("a.pdf", "Estruturas", ["flambagem de coluna"]),
        _indice("b.pdf", "Fundações", ["flambagem de estaca"]),
    ]
    resultados = normas.buscar_nos_indices(indices, "flambagem", segmentos=["Fundações"])
    assert len(resultados) == 1
    assert resultados[0]["arquivo"] == "b.pdf"


def test_buscar_nos_indices_ordena_por_numero_de_ocorrencias():
    indices = [
        _indice("poucas.pdf", "Estruturas", ["flambagem uma vez"]),
        _indice("muitas.pdf", "Estruturas", ["flambagem flambagem flambagem"]),
    ]
    resultados = normas.buscar_nos_indices(indices, "flambagem")
    assert [resultado["arquivo"] for resultado in resultados] == ["muitas.pdf", "poucas.pdf"]


def test_buscar_nos_indices_respeita_o_limite():
    indices = [_indice(f"arquivo_{i}.pdf", "Estruturas", ["flambagem"]) for i in range(5)]
    resultados = normas.buscar_nos_indices(indices, "flambagem", limite=2)
    assert len(resultados) == 2


# ---------------------------------------------------------------------------
# duplicidades_por_norma
# ---------------------------------------------------------------------------


def test_duplicidades_por_norma_agrupa_mesma_norma(tmp_path):
    (tmp_path / "NBR8800_v1.pdf").write_bytes(b"a")
    (tmp_path / "NBR8800_v2.pdf").write_bytes(b"b")
    (tmp_path / "NBR6118.pdf").write_bytes(b"c")

    arquivos = normas.listar_pdfs(tmp_path, CATALOGO_MINIMO)
    duplicidades = normas.duplicidades_por_norma(arquivos)

    assert set(duplicidades) == {"abnt-nbr-8800"}
    assert len(duplicidades["abnt-nbr-8800"]) == 2


def test_duplicidades_por_norma_sem_repeticao_e_vazio(tmp_path):
    (tmp_path / "NBR8800.pdf").write_bytes(b"a")
    (tmp_path / "NBR6118.pdf").write_bytes(b"c")

    arquivos = normas.listar_pdfs(tmp_path, CATALOGO_MINIMO)
    assert normas.duplicidades_por_norma(arquivos) == {}
