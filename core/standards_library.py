"""Catálogo e indexação local de normas técnicas em PDF.

O módulo não interpreta requisitos normativos nem decide conformidade. Ele organiza
arquivos fornecidos pelo usuário, extrai texto por página e mantém a origem de cada
resultado para que a conferência seja feita no documento licenciado.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
PASTA_NORMAS_PADRAO = RAIZ_PROJETO / "normas_pdf"
CATALOGO_PADRAO = RAIZ_PROJETO / "data" / "normas_catalogo.json"
MAXIMO_ARQUIVOS = 500
MAXIMO_BYTES_PDF = 500 * 1024 * 1024
MINIMO_CARACTERES_POR_PAGINA = 80


class BibliotecaNormasErro(RuntimeError):
    """Erro controlado ao ler o catálogo ou a biblioteca de PDFs."""


class DependenciaPdfAusente(BibliotecaNormasErro):
    """A extração foi solicitada sem a dependência opcional de PDF."""


@dataclass(frozen=True)
class ArquivoNorma:
    caminho: str
    nome: str
    caminho_relativo: str
    tamanho_bytes: int
    modificado_ns: int
    norma_id: str | None
    codigo: str
    segmento: str


@dataclass(frozen=True)
class PaginaNorma:
    numero: int
    texto: str
    caracteres: int


def normalizar_texto(valor: object) -> str:
    """Remove acentos e pontuação para comparação tolerante de códigos e termos."""
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    return " ".join(re.findall(r"[A-Z0-9]+", texto.upper()))


def carregar_catalogo(caminho: str | Path = CATALOGO_PADRAO) -> list[dict]:
    """Carrega e valida o catálogo informativo de normas."""
    arquivo = Path(caminho)
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise BibliotecaNormasErro(f"Catálogo não encontrado: {arquivo}") from erro
    except (OSError, json.JSONDecodeError) as erro:
        raise BibliotecaNormasErro(f"Catálogo inválido: {erro}") from erro

    if not isinstance(dados, list):
        raise BibliotecaNormasErro("O catálogo deve conter uma lista de normas.")

    obrigatorios = {
        "id",
        "codigo",
        "titulo",
        "segmento",
        "aplicacao",
        "quando_consultar",
        "pontos_chave",
        "modulos",
        "palavras_chave",
        "aliases",
        "fonte_url",
    }
    ids: set[str] = set()
    catalogo: list[dict] = []
    for indice, item in enumerate(dados, start=1):
        if not isinstance(item, dict):
            raise BibliotecaNormasErro(f"Entrada {indice} do catálogo não é um objeto.")
        faltantes = obrigatorios - set(item)
        if faltantes:
            raise BibliotecaNormasErro(
                f"Entrada {indice} sem os campos: {', '.join(sorted(faltantes))}."
            )
        identificador = str(item["id"]).strip()
        if not identificador or identificador in ids:
            raise BibliotecaNormasErro(
                f"Identificador vazio ou duplicado na entrada {indice}: {identificador!r}."
            )
        ids.add(identificador)
        catalogo.append(dict(item))
    return catalogo


def catalogo_por_id(catalogo: Sequence[Mapping]) -> dict[str, dict]:
    return {str(item["id"]): dict(item) for item in catalogo}


def segmentos_catalogo(catalogo: Sequence[Mapping]) -> list[str]:
    return sorted({str(item["segmento"]) for item in catalogo})


def _aliases_norma(item: Mapping) -> list[str]:
    valores = [str(item.get("codigo", "")), *map(str, item.get("aliases", []))]
    aliases = {normalizar_texto(valor) for valor in valores}
    return sorted((alias for alias in aliases if alias), key=len, reverse=True)


def identificar_norma(
    texto: str,
    catalogo: Sequence[Mapping],
) -> dict | None:
    """Identifica a melhor norma pelo código presente no nome ou no texto."""
    alvo = f" {normalizar_texto(texto)} "
    candidatas: list[tuple[int, int, dict]] = []
    for item in catalogo:
        aliases = _aliases_norma(item)
        correspondencias = [alias for alias in aliases if f" {alias} " in alvo]
        if correspondencias:
            maior = max(correspondencias, key=len)
            candidatas.append((len(maior), len(normalizar_texto(item["codigo"])), dict(item)))
    if not candidatas:
        return None
    candidatas.sort(key=lambda valor: (valor[0], valor[1]), reverse=True)
    return candidatas[0][2]


def resolver_pasta(pasta: str | Path) -> Path:
    caminho = Path(pasta).expanduser().resolve()
    if not caminho.exists():
        raise BibliotecaNormasErro(f"A pasta não existe: {caminho}")
    if not caminho.is_dir():
        raise BibliotecaNormasErro(f"O caminho não é uma pasta: {caminho}")
    return caminho


def listar_pdfs(
    pasta: str | Path,
    catalogo: Sequence[Mapping],
    *,
    maximo_arquivos: int = MAXIMO_ARQUIVOS,
) -> list[ArquivoNorma]:
    """Lista PDFs recursivamente e tenta classificá-los pelo nome do arquivo."""
    raiz = resolver_pasta(pasta)
    caminhos = sorted(
        (
            caminho
            for caminho in raiz.rglob("*")
            if caminho.is_file() and caminho.suffix.casefold() == ".pdf"
        ),
        key=lambda caminho: str(caminho.relative_to(raiz)).casefold(),
    )
    if len(caminhos) > maximo_arquivos:
        raise BibliotecaNormasErro(
            f"Foram encontrados {len(caminhos)} PDFs; o limite é {maximo_arquivos}. "
            "Separe a biblioteca em pastas menores."
        )

    arquivos: list[ArquivoNorma] = []
    for caminho in caminhos:
        estatistica = caminho.stat()
        norma = identificar_norma(caminho.stem, catalogo)
        arquivos.append(
            ArquivoNorma(
                caminho=str(caminho),
                nome=caminho.name,
                caminho_relativo=str(caminho.relative_to(raiz)),
                tamanho_bytes=estatistica.st_size,
                modificado_ns=estatistica.st_mtime_ns,
                norma_id=str(norma["id"]) if norma else None,
                codigo=str(norma["codigo"]) if norma else "Não identificada",
                segmento=str(norma["segmento"]) if norma else "A classificar",
            )
        )
    return arquivos


def assinatura_biblioteca(arquivos: Sequence[ArquivoNorma]) -> str:
    """Assinatura estável para detectar inclusão, remoção ou alteração de PDFs."""
    conteudo = "\n".join(
        f"{item.caminho}|{item.tamanho_bytes}|{item.modificado_ns}" for item in arquivos
    )
    return sha256(conteudo.encode("utf-8")).hexdigest()


def _hash_arquivo(caminho: Path) -> str:
    digest = sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def extrair_pdf(
    caminho: str | Path,
    catalogo: Sequence[Mapping],
    *,
    maximo_bytes: int = MAXIMO_BYTES_PDF,
) -> dict:
    """Extrai texto, metadados e rastreabilidade página a página de um PDF."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as erro:
        raise DependenciaPdfAusente(
            "Instale 'pypdf' para indexar o conteúdo das normas."
        ) from erro

    arquivo = Path(caminho).expanduser().resolve()
    if not arquivo.is_file() or arquivo.suffix.casefold() != ".pdf":
        raise BibliotecaNormasErro(f"PDF não encontrado: {arquivo}")
    tamanho = arquivo.stat().st_size
    if tamanho > maximo_bytes:
        raise BibliotecaNormasErro(
            f"O arquivo possui {tamanho / (1024 * 1024):.1f} MB e excede o limite "
            f"de {maximo_bytes / (1024 * 1024):.0f} MB."
        )

    try:
        leitor = PdfReader(str(arquivo), strict=False)
        criptografado = bool(leitor.is_encrypted)
        if criptografado:
            try:
                desbloqueado = leitor.decrypt("")
            except Exception as erro:  # pypdf varia por método de criptografia
                raise BibliotecaNormasErro(
                    f"O PDF '{arquivo.name}' é protegido por senha."
                ) from erro
            if not desbloqueado:
                raise BibliotecaNormasErro(
                    f"O PDF '{arquivo.name}' é protegido por senha."
                )

        paginas: list[PaginaNorma] = []
        erros_paginas: list[str] = []
        for numero, pagina in enumerate(leitor.pages, start=1):
            try:
                texto = pagina.extract_text() or ""
            except Exception as erro:  # mantém as demais páginas pesquisáveis
                texto = ""
                erros_paginas.append(f"Página {numero}: {type(erro).__name__}")
            texto = texto.replace("\x00", " ").strip()
            paginas.append(PaginaNorma(numero, texto, len(texto)))

        metadados = leitor.metadata or {}
    except BibliotecaNormasErro:
        raise
    except (OSError, PdfReadError, ValueError) as erro:
        raise BibliotecaNormasErro(f"Não foi possível ler '{arquivo.name}': {erro}") from erro

    texto_amostra = " ".join(pagina.texto[:4000] for pagina in paginas[:5])
    norma = identificar_norma(f"{arquivo.stem} {texto_amostra}", catalogo)
    paginas_com_texto = sum(
        pagina.caracteres >= MINIMO_CARACTERES_POR_PAGINA for pagina in paginas
    )
    cobertura = paginas_com_texto / len(paginas) if paginas else 0.0

    return {
        "caminho": str(arquivo),
        "nome": arquivo.name,
        "tamanho_bytes": tamanho,
        "sha256": _hash_arquivo(arquivo),
        "numero_paginas": len(paginas),
        "paginas_com_texto": paginas_com_texto,
        "cobertura_texto": cobertura,
        "necessita_ocr": bool(paginas) and cobertura < 0.6,
        "criptografado": criptografado,
        "titulo_pdf": str(getattr(metadados, "title", "") or ""),
        "autor_pdf": str(getattr(metadados, "author", "") or ""),
        "norma_id": str(norma["id"]) if norma else None,
        "codigo": str(norma["codigo"]) if norma else "Não identificada",
        "segmento": str(norma["segmento"]) if norma else "A classificar",
        "erros_paginas": erros_paginas,
        "paginas": [asdict(pagina) for pagina in paginas],
    }


def _termos_consulta(consulta: str) -> list[str]:
    return [termo for termo in normalizar_texto(consulta).split() if len(termo) >= 2]


def _trecho_resultado(texto: str, termos: Sequence[str], largura: int = 360) -> str:
    texto_limpo = re.sub(r"\s+", " ", texto).strip()
    if not texto_limpo:
        return ""
    texto_normalizado = normalizar_texto(texto_limpo)
    posicao_normalizada = min(
        (texto_normalizado.find(termo) for termo in termos if termo in texto_normalizado),
        default=0,
    )
    proporcao = posicao_normalizada / max(1, len(texto_normalizado))
    centro = int(proporcao * len(texto_limpo))
    inicio = max(0, centro - largura // 3)
    fim = min(len(texto_limpo), inicio + largura)
    prefixo = "…" if inicio else ""
    sufixo = "…" if fim < len(texto_limpo) else ""
    return f"{prefixo}{texto_limpo[inicio:fim].strip()}{sufixo}"


def buscar_nos_indices(
    indices: Iterable[Mapping],
    consulta: str,
    *,
    segmentos: Sequence[str] | None = None,
    limite: int = 100,
) -> list[dict]:
    """Pesquisa todos os termos e retorna resultados rastreáveis por página."""
    termos = _termos_consulta(consulta)
    if not termos:
        return []
    segmentos_ativos = set(segmentos or [])
    resultados: list[dict] = []

    for indice in indices:
        segmento = str(indice.get("segmento", "A classificar"))
        if segmentos_ativos and segmento not in segmentos_ativos:
            continue
        for pagina in indice.get("paginas", []):
            texto = str(pagina.get("texto", ""))
            normalizado = normalizar_texto(texto)
            if not all(termo in normalizado for termo in termos):
                continue
            ocorrencias = sum(normalizado.count(termo) for termo in termos)
            resultados.append(
                {
                    "arquivo": str(indice.get("nome", "")),
                    "caminho": str(indice.get("caminho", "")),
                    "norma_id": indice.get("norma_id"),
                    "codigo": str(indice.get("codigo", "Não identificada")),
                    "segmento": segmento,
                    "pagina": int(pagina.get("numero", 0)),
                    "ocorrencias": ocorrencias,
                    "trecho": _trecho_resultado(texto, termos),
                }
            )

    resultados.sort(
        key=lambda item: (-item["ocorrencias"], item["arquivo"].casefold(), item["pagina"])
    )
    return resultados[: max(1, limite)]


def duplicidades_por_norma(arquivos: Sequence[ArquivoNorma]) -> dict[str, list[str]]:
    """Agrupa possíveis edições duplicadas da mesma norma."""
    grupos: dict[str, list[str]] = {}
    for arquivo in arquivos:
        if arquivo.norma_id:
            grupos.setdefault(arquivo.norma_id, []).append(arquivo.caminho_relativo)
    return {chave: nomes for chave, nomes in grupos.items() if len(nomes) > 1}

