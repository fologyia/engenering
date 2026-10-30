"""O programa chama a edição vigente de "ABNT NBR 8800:2025" (pedido de 30/10/2026).

A chave interna continua ``NBR8800_2024`` (trocá-la quebraria os projetos gravados); o que aparece
para o usuário — telas, ajudas, memoriais e Word — não volta a dizer "Projeto NBR 8800:2024" nem
"Projeto de revisão". As categorias de ações gravadas com o nome antigo continuam valendo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core import column_buckling as cb
from core import contraventamento_plataforma as cp
from core import load_combinations as comb
from core import plano_de_cargas as pc

RAIZ = Path(__file__).resolve().parent.parent
PROIBIDO = re.compile(r"Projeto NBR 8800|Projeto de revisão|NBR 8800:2024|Projeto (de )?2024")


@pytest.mark.parametrize("pasta", ["app_pages", "components", "core"])
def test_nenhum_texto_do_programa_chama_a_norma_de_projeto_de_2024(pasta):
    achados = []
    for arquivo in sorted((RAIZ / pasta).rglob("*.py")):
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            # só o mapa dos rótulos antigos (para ler projetos gravados) cita o nome antigo
            if PROIBIDO.search(linha) and not any(k in linha for k in comb.ROTULOS_ANTIGOS):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: {linha.strip()[:90]}")
    assert not achados, achados


def test_rotulo_da_flambagem_e_a_2025():
    assert cb.NORMAS_ROTULOS["NBR8800_2024"] == "ABNT NBR 8800:2025"


@pytest.mark.parametrize("antigo, atual", sorted(comb.ROTULOS_ANTIGOS.items()))
def test_categoria_gravada_com_o_nome_antigo_continua_valendo(antigo, atual):
    assert comb.categoria_nbr(antigo) is comb.categoria_nbr(atual)
    assert "2025" in atual and "Projeto" not in atual
    # código fora da lista: sem o mapa, a categoria cairia na sobrecarga padrão
    plano = pc.de_dicionario({"acoes": [{"codigo": "Q9", "nome": "Ação", "categoria": antigo}]})
    assert [a.categoria for a in plano.acoes] == [atual]


def test_contraventamento_aceita_as_categorias_antigas():
    cargas = cp.Cargas(
        categoria_equipamentos="Peso próprio de equipamentos (Projeto NBR 8800:2024)",
        categoria_sobrecarga="Sobrecarga de cobertura (Projeto NBR 8800:2024)",
    )
    erros = cp.validar_entrada(cp.EntradaContraventamento(cargas=cargas))
    assert not [e for e in erros if "Categoria" in e], erros
