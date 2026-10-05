"""Os “?” da página Projeto de parafusos e o aviso que o usuário mandou tirar.

Dois contratos, sem abrir o Streamlit:

* todo texto de ``components/bolted_help.py`` é usado por algum campo, e todo campo usa um
  texto que existe (nada de “?” vazio nem de texto órfão);
* nenhum arquivo do programa volta a dizer que o Projeto NBR 8800:2024 “não tem valor
  normativo” — decisão do usuário, que já trabalha com o documento oficial.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from components.bolted_help import AJUDA
from core import bolted_connection as bc
from core import bolted_joint_check as chk

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVOS_COM_AJUDA = [
    RAIZ / "components" / "structural_bolted_ui.py",
    RAIZ / "app_pages" / "projeto_parafusos.py",
]
USO = re.compile(r'AJUDA\["([A-Za-z_0-9]+)"\]')


def _chaves_usadas() -> set[str]:
    usadas: set[str] = set()
    for arquivo in ARQUIVOS_COM_AJUDA:
        usadas |= set(USO.findall(arquivo.read_text(encoding="utf-8")))
    return usadas


def test_todo_campo_usa_um_texto_que_existe():
    inexistentes = _chaves_usadas() - set(AJUDA)
    assert not inexistentes, f"chaves sem texto em AJUDA: {sorted(inexistentes)}"


def test_nenhum_texto_de_ajuda_fica_sem_uso():
    orfaos = set(AJUDA) - _chaves_usadas()
    assert not orfaos, f"textos de ajuda que nenhum campo usa: {sorted(orfaos)}"


def test_textos_de_ajuda_sao_curtos_e_sem_marcas_de_rascunho():
    for chave, texto in AJUDA.items():
        assert texto.strip() == texto and len(texto) > 15, chave
        assert len(texto) <= 900, f"{chave}: dica longa demais ({len(texto)} caracteres)"
        assert "TODO" not in texto and "XXX" not in texto, chave


@pytest.mark.parametrize(
    ("chave", "deve_citar"),
    [
        ("planos_corte", ("1 plano", "2 planos")),  # quem não sabe o que são planos de corte
        ("rosca_plano", ("rosca", "plano de corte")),
        ("grau", ("A325", "A490", "A307")),
        ("t", ("mais fina", "Não some")),
        ("furo", ("furo-padrão", "Simplificação")),
        ("momento", ("M = V·a", "Emenda por sobreposição")),
        ("ja_calculo", ("Característico", "γ_f")),
        ("res_tabela", ("Solicitante", "Resistente", "Aproveitamento", "Status")),
    ],
)
def test_dicas_para_quem_nao_conhece_o_termo_explicam_o_termo(chave, deve_citar):
    for trecho in deve_citar:
        assert trecho in AJUDA[chave], (chave, trecho)


# ------------------------------------------------------------------ aviso de “valor normativo”
FRASES_PROIBIDAS = ("sem valor normativo", "não tem valor normativo", "nao tem valor normativo")


def test_rotulos_avisos_e_referencias_da_norma_2024_nao_falam_em_valor_normativo():
    textos = [
        *chk.NORMAS_ROTULOS.values(),
        *chk.AVISOS_FIXOS,
        *chk.REFERENCIAS_NORMA.values(),
        *chk.SUPERFICIES_ROTULOS.values(),
        *chk.FORA_DO_ESCOPO.values(),
        bc.__doc__ or "",
        *bc.CONFERIR_NBR8800_2008,
    ]
    for texto in textos:
        for frase in FRASES_PROIBIDAS:
            assert frase not in texto.lower(), texto
    assert chk.NORMAS_ROTULOS["NBR8800_2024"] == "Projeto NBR 8800:2024"


def test_registro_da_norma_2024_nao_traz_o_aviso():
    entrada = chk.EntradaLigacao(norma="NBR8800_2024", V=32.0, excentricidade_mm=105.0, e=60.0)
    resultado = chk.verificar_ligacao(entrada)
    registro = chk.registro_ligacao(entrada, resultado, "M20")
    texto = " ".join(
        [
            *map(str, registro["alertas"]),
            *map(str, registro["referencias"]),
            *map(str, registro["premissas"]),
            str(registro["resumo"]),
            str(registro["conclusao"]),
        ]
    ).lower()
    for frase in FRASES_PROIBIDAS:
        assert frase not in texto
    assert "Projeto de revisão ABNT NBR 8800" in " ".join(registro["referencias"])


def test_nenhum_arquivo_do_programa_volta_a_falar_em_valor_normativo():
    candidatos = [RAIZ / "README.md"]
    for pasta in ("components", "core", "app_pages", "docs", "data"):
        candidatos += [
            p
            for p in (RAIZ / pasta).rglob("*")
            if p.suffix in {".py", ".md", ".json"} and "__pycache__" not in p.parts
        ]
    achados = []
    for arquivo in candidatos:
        texto = arquivo.read_text(encoding="utf-8").lower()
        achados += [
            f"{arquivo.relative_to(RAIZ)}: {frase}" for frase in FRASES_PROIBIDAS if frase in texto
        ]
    assert not achados, achados
