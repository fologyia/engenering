"""Documento Word (editável) da Flambagem de colunas, com tudo o que a página mostra.

O botão no fim da página "Flambagem de colunas" baixa este arquivo para reaproveitar os dados em
outro documento: o que a página não faz, os dados de entrada (com as propriedades da seção e as
ações), o resumo (N_c,Rd, λ, N_e, χ, Q, B₁, momentos e interação), os avisos, a curva de
flambagem, a tabela de verificações com a fórmula e o item de cada linha, as paredes da seção, a
mesma coluna nas três normas, as regras adotadas e o método, as premissas e as referências. As
tabelas são tabelas do Word (copiáveis); a curva, imagem PNG.

Sem Streamlit; usa o registro e as figuras do memorial (:mod:`core.column_buckling`,
:mod:`core.record_charts`) e a base de :mod:`core.word_documento`.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Mapping, Sequence
from typing import Any

from core import column_buckling as cb
from core import memorial_verificacoes as mv
from core.column_design import ESPESSURA_MIN_ANGLO
from core.verificacao import formatar_percentual
from core.word_documento import DocumentoWord, numero_pt

MODULO_ID = "flambagem_colunas"
#: Texto de cálculo em português: ponto decimal vira vírgula; número de item não muda.
_pt = mv.decimal_ptbr


def _n(valor: float | None, casas: int = 2, unidade: str = "") -> str:
    if valor is None:
        return "—"
    if not math.isfinite(valor):
        return "∞"
    return numero_pt(valor, casas) + unidade


def _valor_de_entrada(valor: Any) -> str:
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, float):
        return _n(valor, 3)
    if isinstance(valor, Mapping):
        return "; ".join(f"{k}: {_valor_de_entrada(v)}" for k, v in valor.items()) or "—"
    if isinstance(valor, (list, tuple)):
        return "; ".join(_valor_de_entrada(v) for v in valor)
    return str(valor)


def _rotulo_livre(chave: str) -> str:
    texto = chave.replace("_", " ").strip()
    return texto[:1].upper() + texto[1:]


def _registro(
    entrada: cb.EntradaColuna,
    resultado: cb.ResultadoColuna,
    contexto: Mapping[str, Any] | None,
    equacoes: Sequence[str],
) -> dict[str, Any]:
    return cb.registro_coluna(
        entrada, resultado, contexto=contexto, equacoes_de_carga=list(equacoes)
    )


def dados_de_entrada(registro: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Os dados de entrada como (rótulo, valor), com os rótulos do memorial."""
    return mv.pares_de_entrada(
        {"modulo_id": MODULO_ID, "entradas": registro["entradas"]},
        _valor_de_entrada,
        _rotulo_livre,
    )


def propriedades_da_secao(entrada: cb.EntradaColuna) -> list[list[str]]:
    s = entrada.secao
    return [
        ["Área A", _n(s.A, 1), "mm²"],
        ["Inércia I_x", _n(s.Ix, 0), "mm⁴"],
        ["Inércia I_y", _n(s.Iy, 0), "mm⁴"],
        ["Raio de giração r_x", _n(s.rx, 2), "mm"],
        ["Raio de giração r_y", _n(s.ry, 2), "mm"],
        ["Constante de torção J", _n(s.J, 0), "mm⁴"],
        ["Constante de empenamento C_w", _n(s.Cw, 0), "mm⁶"],
        ["Centro de torção x₀ / y₀", f"{_n(s.x0, 2)} / {_n(s.y0, 2)}", "mm"],
    ]


def linhas_do_resumo(entrada: cb.EntradaColuna, resultado: cb.ResultadoColuna) -> list[list[str]]:
    """O quadro "Resumo" da página, na mesma ordem."""
    comp = resultado.compressao
    sec = entrada.secao
    linhas = [
        ["Status geral", resultado.status_geral],
        ["Aproveitamento máximo", formatar_percentual(resultado.aproveitamento_max)],
    ]
    if comp is not None:
        linhas.append(["N_c,Rd", _n(comp["Nc_Rd"], 2, " kN")])
    linhas.append(["N_Sd", _n(entrada.N_Sd_kN, 2, " kN")])
    linhas.append(["λx = Kx·Lx/rx", _n(entrada.kx * entrada.Lx_mm / sec.rx, 1)])
    linhas.append(["λy = Ky·Ly/ry", _n(entrada.ky * entrada.Ly_mm / sec.ry, 1)])
    if comp is not None:
        linhas.append(
            ["N_e adotado", f"{_n(comp['Ne'], 1, ' kN')} (modo que governa: {comp['modo']})"]
        )
        linhas.append(["χ", _n(comp["chi"], 3)])
        rotulo_q = "Q = Q_s·Q_a" if entrada.norma == "NBR8800_2008" else "A_ef/A_g"
        linhas.append([rotulo_q, _n(comp["Q"], 3)])
    for eixo, momento, b1, amplificado, mrd, da_norma in (
        ("x", resultado.momento_x_primeira_ordem_kNm, resultado.b1_x, resultado.momento_x_amplificado_kNm, resultado.mrd_x_kNm, resultado.flexao_x is not None),
        ("y", resultado.momento_y_primeira_ordem_kNm, resultado.b1_y, resultado.momento_y_amplificado_kNm, resultado.mrd_y_kNm, resultado.flexao_y is not None),
    ):  # fmt: skip
        if momento <= 0:
            continue
        linhas.append([f"B₁ em {eixo}", _n(b1, 3)])
        linhas.append([f"M_{eixo},Sd amplificado", _n(amplificado, 3, " kN·m")])
        origem = "" if da_norma else " (informado)"
        linhas.append([f"M_{eixo},Rd", "—" if mrd is None else _n(mrd, 3, " kN·m") + origem])
    if resultado.indice_interacao is not None:
        linhas.append(["Índice de interação", _n(resultado.indice_interacao, 3)])
    linhas.append(["Verificação que governa", resultado.governante])
    return linhas


def _linhas_da_comparacao(entrada: cb.EntradaColuna) -> list[list[Any]]:
    linhas = []
    for item in cb.comparar_normas(entrada):
        aprov = item.get("aproveitamento_max")
        linhas.append(
            [
                item["rotulo"],
                item["status"],
                "—" if aprov is None else _n(100 * aprov, 0),
                item.get("governante", ""),
                _n(item.get("Nc_Rd_kN"), 1),
                _n(item.get("fator_Q"), 3),
                _n(item.get("chi"), 3),
                _n(item.get("MRd_x_kNm"), 1),
                _n(item.get("MRd_y_kNm"), 1),
                _n(item.get("indice_interacao"), 3),
                item.get("erro", ""),
            ]
        )
    return linhas


def gerar_word_coluna(
    entrada: cb.EntradaColuna,
    resultado: cb.ResultadoColuna,
    *,
    contexto: Mapping[str, Any] | None = None,
    equacoes_de_carga: Sequence[str] = (),
    projeto: Mapping[str, Any] | None = None,
) -> bytes:
    """O .docx com todas as informações da página (``contexto`` e ``equacoes_de_carga`` como no
    registro; ``projeto`` dá o nome e o código do projeto ativo, quando houver)."""
    registro = _registro(entrada, resultado, contexto, equacoes_de_carga)
    norma = cb.NORMAS_ROTULOS[entrada.norma]
    comp = resultado.compressao
    doc = DocumentoWord()
    doc.titulo(f"Flambagem de colunas — {entrada.secao.nome}", 0)
    doc.paragrafo(
        f"{norma} · critério Anglo American AA-BR-DPST-DR-0001 — verificação da barra isolada "
        "(todos os modos de flambagem, flambagem local, flexão em x e y e interação N + Mx + My).",
        legenda=True,
    )
    if projeto and (projeto.get("nome") or projeto.get("codigo")):
        doc.tabela(
            ["Projeto", "Código", "Revisão"],
            [
                [
                    projeto.get("nome") or "-",
                    projeto.get("codigo") or "-",
                    projeto.get("revisao") or "-",
                ]
            ],
            [120, 80, 73],
        )

    doc.titulo("O que esta página não faz", 1)
    doc.itens(list(cb.FORA_DO_ESCOPO))

    doc.titulo("Dados de entrada", 1)
    doc.tabela(["Dado", "Valor"], dados_de_entrada(registro), [140, 133], fonte=8.5)
    doc.paragrafo("Propriedades da seção", negrito=True)
    doc.tabela(["Propriedade", "Valor", "Un."], propriedades_da_secao(entrada), [120, 100, 53])
    if equacoes_de_carga:
        doc.paragrafo("Ações de cálculo", negrito=True)
        doc.itens(list(equacoes_de_carga))

    doc.titulo("1. Resumo", 1)
    doc.tabela(["Item", "Resultado"], linhas_do_resumo(entrada, resultado), [80, 193])
    if resultado.bloqueios:
        doc.paragrafo(
            "Casos que a norma não cobre — o programa não estima o resultado:", negrito=True
        )
        doc.itens([_pt(texto) for texto in resultado.bloqueios])
    for aviso in resultado.avisos:
        doc.paragrafo(f"Aviso: {_pt(aviso)}")

    if comp is not None:
        imagens_flambagem = importlib.import_module("core.record_charts").imagens_flambagem
        try:
            figuras = imagens_flambagem(registro["entradas"], registro["resultados"])
        except (KeyError, TypeError, ValueError):
            figuras = []
        if figuras:
            doc.titulo("2. Curva de flambagem", 1)
            for figura in figuras:
                doc.figura(figura.png, figura.legenda, 200)

    doc.titulo(f"3. Tabela de verificações ({len(resultado.verificacoes)})", 1)
    doc.paragrafo(
        "Aproveitamento = solicitante ÷ resistente; até 100 % a verificação passa. Os limites "
        "(esbeltez, espessuras) só dizem OK ou NÃO OK.",
        legenda=True,
    )
    doc.tabela(
        [
            "Verificação",
            "Norma/item",
            "Solicitante",
            "Resistente",
            "Un.",
            "Aprov. (%)",
            "Status",
            "Fórmula",
        ],
        [
            [
                v.nome,
                v.referencia,
                _n(v.solicitante, 3),
                _n(v.resistente, 3),
                v.unidade,
                "—" if v.aproveitamento is None else _n(100 * v.aproveitamento, 1),
                v.status,
                _pt(v.formula),
            ]
            for v in resultado.verificacoes
        ],
        [55, 34, 18, 18, 12, 14, 14, 108],
        status_coluna=6,
        fonte=7.5,
    )

    if comp is not None and entrada.secao.elementos:
        doc.titulo("4. Paredes da seção — flambagem local", 1)
        paredes = cb.tabela_elementos(
            entrada.secao, entrada.fy_MPa, entrada.norma, comp, entrada.E_MPa
        )
        doc.tabela(
            ["Elemento", "Tipo", "Grupo (Tabela 4)", "b (mm)", "t (mm)", "b/t", "(b/t) lim", "Esbelto", "Q_s", "b_ef (mm)"],
            [
                [
                    p["Elemento"],
                    p["Tipo"],
                    str(p["Grupo (Tabela 4)"]),
                    _n(p["b (mm)"], 1),
                    _n(p["t (mm)"], 2),
                    _n(p["b/t"], 1),
                    _n(p["(b/t) lim"], 1),
                    p["Esbelto"],
                    _n(p["Q_s"], 3),
                    _n(p["b_ef (mm)"], 1),
                ]
                for p in paredes
            ],
        )  # fmt: skip
        doc.paragrafo(
            "Esbelto = b/t acima do limite da Tabela 4. Na NBR 2008, Q_s vale para elemento livre "
            "(AL) e b_ef para elemento apoiado (AA); no NBR 8800:2025 e no AISC todos usam b_ef.",
            legenda=True,
        )

    doc.titulo("5. A mesma coluna nas três normas", 1)
    doc.tabela(
        ["Norma", "Status", "Aprov. máx. (%)", "Governa", "N_c,Rd (kN)", "Q ou A_ef/A_g", "χ", "M_x,Rd (kN·m)", "M_y,Rd (kN·m)", "Interação", "Observação"],
        _linhas_da_comparacao(entrada),
        [30, 16, 16, 50, 18, 17, 13, 18, 18, 16, 61],
        status_coluna=1,
        fonte=7.0,
    )  # fmt: skip
    doc.paragrafo(
        "A comparação usa os mesmos dados de entrada. A norma que não cobre o caso mostra o "
        "motivo em “Observação”. Q é o fator da NBR 2008; nas outras duas a coluna mostra A_ef/A_g.",
        legenda=True,
    )

    doc.titulo("6. Regras adotadas nesta verificação", 1)
    doc.paragrafo("Efeito B₁ (momentos amplificados)", negrito=True)
    doc.itens(list(cb.REGRAS_B1))
    doc.paragrafo("Flambagem lateral com torção (FLT): diferença entre as versões", negrito=True)
    doc.itens(
        [
            texto + (" (norma escolhida)" if chave == entrada.norma else "")
            for chave, texto in cb.EXPLICACAO_FLT.items()
        ]
    )
    doc.paragrafo("Espessuras mínimas da Anglo (item 8.8)", negrito=True)
    doc.itens(
        [
            f"{rotulo[:1].upper()}{rotulo[1:]}: {numero_pt(ESPESSURA_MIN_ANGLO[categoria], 2)} mm"
            for categoria, rotulo in cb.ROTULOS_ESPESSURA_ANGLO.items()
        ]
    )
    if entrada.norma == "NBR8800_2008":
        doc.paragrafo("Valores da NBR 8800:2008 conferidos na norma", negrito=True)
        doc.itens(list(cb.CONFERIDOS_NBR8800_2008))

    doc.titulo("7. Método, premissas, critérios e referências", 1)
    doc.paragrafo(f"Método: {_pt(registro['metodo'])}")
    doc.paragrafo("Premissas", negrito=True)
    doc.itens([_pt(texto) for texto in registro.get("premissas") or []])
    doc.paragrafo("Critérios", negrito=True)
    doc.itens(list(registro.get("criterios") or []))
    doc.paragrafo("Conclusão", negrito=True)
    doc.paragrafo(_pt(str(registro.get("conclusao") or "")))
    doc.paragrafo("Referências", negrito=True)
    doc.itens(list(registro.get("referencias") or []))
    doc.paragrafo(
        "Verificação de barra isolada pela NBR 8800:2008, pela NBR 8800:2025 ou pelo "
        "AISC 360-16, com o critério da Anglo. Para a estrutura completa (pórtico, B₂, cargas "
        "nocionais, ligações e placa de base), use Estruturas de aço.",
        legenda=True,
    )
    return doc.bytes()
