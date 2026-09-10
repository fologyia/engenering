"""Converte a tabela de bitolas da Gerdau em um catálogo de perfis do programa.

Uso::

    python scripts/importar_catalogo_gerdau.py <arquivo.pdf> [--saida data/perfis_ref_gerdau.json]

A extração de texto do PDF devolve as colunas embaralhadas e os números
partidos em pedaços — ``118`` sai como ``11`` + ``8``. Por isso a tabela é
reconstruída pela **posição** de cada fragmento na página: agrupa por y para
formar a linha e por x para formar a coluna.

Nada disso seria confiável sozinho. Cada perfil reconstruído passa por uma
conferência de coerência interna antes de entrar no catálogo: o raio de
giração precisa bater com ``sqrt(I/A)`` e o módulo elástico com ``I/(d/2)``,
ambos calculados a partir de colunas diferentes da mesma linha. Uma coluna
deslocada quebra essas relações imediatamente, então um erro de leitura vira
um perfil rejeitado com o motivo — nunca uma propriedade errada entrando em
silêncio num cálculo de engenharia.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

NOME_PERFIL = re.compile(r"^(W|HP)\s*\d")

# Colunas da tabela de perfis W/HP, na ordem em que aparecem na página.
COLUNAS_W = (
    "nome",
    "massa_kg_m",
    "d_mm",
    "bf_mm",
    "tw_mm",
    "tf_mm",
    "h_mm",
    "d_linha_mm",
    "area_cm2",
    "ix_cm4",
    "wx_cm3",
    "rx_cm",
    "zx_cm3",
    "iy_cm4",
    "wy_cm3",
    "ry_cm",
    "zy_cm3",
    "rt_cm",
    "it_cm4",
    "bf_2tf",
    "d_tw",
    "cw_cm6",
    "u_m2_m",
    "nome_pol",
)

TOLERANCIA_COERENCIA = 0.06


def fragmentos(pagina) -> list[tuple[float, float, str]]:
    itens: list[tuple[float, float, str]] = []

    def visitante(texto, cm, tm, fonte, tamanho):  # noqa: ANN001 - assinatura do pypdf
        limpo = texto.strip()
        if limpo:
            itens.append((round(tm[4], 1), round(tm[5], 1), limpo))

    pagina.extract_text(visitor_text=visitante)
    return itens


def agrupar_por_linha(itens, tolerancia: float = 2.5):
    grupos: dict[float, list[tuple[float, str]]] = {}
    for x, y, texto in itens:
        chave = next((k for k in grupos if abs(k - y) <= tolerancia), y)
        grupos.setdefault(chave, []).append((x, texto))
    return [(y, sorted(grupos[y])) for y in sorted(grupos, reverse=True)]


def posicoes_das_colunas(linhas_dados, tolerancia: float = 6.0) -> list[float]:
    """x que se repete na maioria das linhas de dados = uma coluna."""
    contagem: dict[float, int] = {}
    for _y, campos in linhas_dados:
        for x, _texto in campos:
            chave = next((k for k in contagem if abs(k - x) <= tolerancia), x)
            contagem[chave] = contagem.get(chave, 0) + 1
    minimo = len(linhas_dados) * 0.5
    return sorted(x for x, n in contagem.items() if n >= minimo)


def montar_linha(campos, colunas: list[float]) -> list[str]:
    """Junta os fragmentos de cada coluna na ordem em que foram desenhados."""
    baldes: dict[int, list[str]] = {indice: [] for indice in range(len(colunas))}
    for x, texto in campos:
        indice = min(range(len(colunas)), key=lambda i: abs(x - colunas[i]))
        baldes[indice].append(texto)
    return ["".join(baldes[indice]) for indice in range(len(colunas))]


def numero(texto: str) -> float | None:
    bruto = texto.replace(" ", "").replace(" ", "")
    bruto = bruto.replace(".", "").replace(",", ".")
    if not bruto or not re.fullmatch(r"-?\d+(\.\d+)?", bruto):
        return None
    valor = float(bruto)
    return valor if math.isfinite(valor) else None


def limpar_nome(texto: str) -> str:
    nome = re.sub(r"\s+", " ", texto.replace(" ", " ")).strip()
    # "W 310 x 11 7 ,0" -> "W 310 x 117,0"; o kerning separa os dígitos.
    nome = re.sub(r"(\d)\s+(\d)", r"\1\2", nome)
    nome = re.sub(r"\s*,\s*", ",", nome)
    nome = re.sub(r"\s*x\s*", " x ", nome)
    return re.sub(r"\s+", " ", nome).strip()


def conferir(valores: dict[str, float]) -> str:
    """Confere relações que só fecham se as colunas estiverem alinhadas."""
    area_mm2 = valores["area_cm2"] * 100.0
    for eixo, inercia_cm4, raio_cm, modulo_cm3, dimensao_mm in (
        ("x", valores["ix_cm4"], valores["rx_cm"], valores["wx_cm3"], valores["d_mm"]),
        ("y", valores["iy_cm4"], valores["ry_cm"], valores["wy_cm3"], valores["bf_mm"]),
    ):
        inercia_mm4 = inercia_cm4 * 1e4
        raio_calculado = math.sqrt(inercia_mm4 / area_mm2) / 10.0
        if abs(raio_calculado - raio_cm) > TOLERANCIA_COERENCIA * raio_cm:
            return (
                f"r{eixo} tabelado {raio_cm:.2f} cm contra "
                f"{raio_calculado:.2f} cm de sqrt(I/A)"
            )
        modulo_calculado = inercia_mm4 / (dimensao_mm / 2.0) / 1e3
        if abs(modulo_calculado - modulo_cm3) > TOLERANCIA_COERENCIA * modulo_cm3:
            return (
                f"W{eixo} tabelado {modulo_cm3:.1f} cm³ contra "
                f"{modulo_calculado:.1f} cm³ de I/(dim/2)"
            )
    esperada = area_mm2 * 7_850.0 / 1e6
    if abs(esperada - valores["massa_kg_m"]) > 0.05 * valores["massa_kg_m"]:
        return (
            f"massa {valores['massa_kg_m']:.1f} kg/m contra {esperada:.1f} kg/m "
            "da área em aço"
        )
    return ""


def altura_nominal(nome: str) -> int | None:
    """Altura da designação: em "W 310 x 38,7" a bitola nominal é 310 mm."""
    achado = re.search(r"\s(\d+)\s*x", nome)
    return int(achado.group(1)) if achado else None


def familia_de(nome: str) -> str:
    return "HP (perfil de estaca)" if nome.upper().startswith("HP") else "W (mesa larga)"


def extrair(
    caminho_pdf: Path, *, altura_maxima_mm: int | None = None
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho_pdf))
    perfis: list[dict[str, Any]] = []
    rejeitados: list[tuple[str, str]] = []
    vistos: set[str] = set()

    for pagina in leitor.pages:
        linhas = agrupar_por_linha(fragmentos(pagina))
        dados = [
            (y, campos)
            for y, campos in linhas
            if campos and NOME_PERFIL.match("".join(t for _x, t in campos[:3]))
        ]
        if len(dados) < 5:
            continue
        colunas = posicoes_das_colunas(dados)
        if len(colunas) != len(COLUNAS_W):
            rejeitados.append(
                (
                    f"página com {len(dados)} linhas",
                    f"{len(colunas)} colunas detectadas, esperadas {len(COLUNAS_W)}",
                )
            )
            continue

        for _y, campos in dados:
            bruto = dict(zip(COLUNAS_W, montar_linha(campos, colunas), strict=True))
            nome = limpar_nome(bruto["nome"])
            if not NOME_PERFIL.match(nome):
                rejeitados.append((nome or "(sem nome)", "nome irreconhecível"))
                continue

            # Fora da faixa pedida não é rejeição: é escolha de escopo, e
            # listá-la junto dos erros de leitura esconderia os erros reais.
            altura = altura_nominal(nome)
            if altura_maxima_mm is not None and (
                altura is None or altura > altura_maxima_mm
            ):
                continue

            valores: dict[str, float] = {}
            faltando = []
            for chave in COLUNAS_W:
                if chave in {"nome", "nome_pol"}:
                    continue
                convertido = numero(bruto[chave])
                if convertido is None or convertido <= 0:
                    faltando.append(chave)
                else:
                    valores[chave] = convertido

            if "massa_kg_m" in faltando:
                # A designação já traz a massa nominal: "W 250 x 25,3" é um
                # perfil de 25,3 kg/m. Quando o fragmento da coluna de peso
                # cai no balde do nome, o próprio nome a devolve — e a
                # conferência de massa contra a área continua valendo.
                massa = numero(nome.split("x")[-1])
                if massa:
                    valores["massa_kg_m"] = massa
                    faltando.remove("massa_kg_m")
            if faltando:
                rejeitados.append((nome, "colunas ilegíveis: " + ", ".join(faltando)))
                continue

            motivo = conferir(valores)
            if motivo:
                rejeitados.append((nome, motivo))
                continue
            if nome in vistos:
                continue
            vistos.add(nome)

            perfis.append(
                {
                    "nome": nome,
                    "familia": familia_de(nome),
                    "area_mm2": round(valores["area_cm2"] * 100.0, 3),
                    "ix_mm4": round(valores["ix_cm4"] * 1e4, 1),
                    "iy_mm4": round(valores["iy_cm4"] * 1e4, 1),
                    "zx_mm3": round(valores["zx_cm3"] * 1e3, 1),
                    "zy_mm3": round(valores["zy_cm3"] * 1e3, 1),
                    "j_mm4": round(valores["it_cm4"] * 1e4, 1),
                    "cw_mm6": round(valores["cw_cm6"] * 1e6, 1),
                    "altura_mm": valores["d_mm"],
                    "largura_mm": valores["bf_mm"],
                    "espessura_alma_mm": valores["tw_mm"],
                    "espessura_mesa_mm": valores["tf_mm"],
                    # Convenção usual para perfis I e W: só a alma resiste ao
                    # cortante, e é a mesma que o catálogo embutido adota.
                    "area_cisalhamento_mm2": round(
                        valores["d_mm"] * valores["tw_mm"], 2
                    ),
                    "massa_kg_m": valores["massa_kg_m"],
                    "descricao": (
                        f"{nome} — d {valores['d_mm']:.0f} mm, bf "
                        f"{valores['bf_mm']:.0f} mm, tw {valores['tw_mm']:.1f} mm, "
                        f"tf {valores['tf_mm']:.1f} mm"
                    ),
                }
            )
    return perfis, rejeitados


def principal() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("pdf", type=Path)
    analisador.add_argument(
        "--saida", type=Path, default=Path("data/perfis_ref_gerdau.json")
    )
    analisador.add_argument(
        "--origem", default="Gerdau — Tabela de bitolas (perfis W e HP)"
    )
    analisador.add_argument(
        "--altura-maxima",
        type=int,
        default=310,
        help=(
            "Maior bitola nominal a importar, em mm. O padrão de 310 cobre as "
            "bitolas correntes; acima disso o catálogo cresce sem que os "
            "perfis sejam de fato usados."
        ),
    )
    argumentos = analisador.parse_args()

    perfis, rejeitados = extrair(
        argumentos.pdf, altura_maxima_mm=argumentos.altura_maxima
    )
    print(f"Perfis aceitos: {len(perfis)} (até W/HP {argumentos.altura_maxima})")
    print(f"Rejeitados: {len(rejeitados)}")
    for nome, motivo in rejeitados[:25]:
        print(f"  - {nome}: {motivo}")

    if not perfis:
        print("Nenhum perfil validado; nada foi gravado.", file=sys.stderr)
        return 1

    documento = {
        "schema": "mecanica-toolkit/catalogo-perfis/v1",
        "origem": argumentos.origem,
        "observacoes": (
            "Extraído da tabela de bitolas do fabricante e conferido por "
            "coerência interna (raio de giração e módulo elástico contra I e "
            "A da mesma linha). Confirme a bitola no catálogo vigente antes "
            "de usar em projeto. Bitolas maiores que a importada podem ser "
            "acrescentadas pela página Catálogo de perfis."
        ),
        "perfis": perfis,
    }
    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    argumentos.saida.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Gravado em {argumentos.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
