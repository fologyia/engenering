"""Os casos de aceite que a Central de validação mostra são os mesmos que o CI confere."""

from __future__ import annotations

import pytest

from core import casos_de_aceite as ca


@pytest.mark.parametrize("caso", ca.casos(), ids=lambda c: f"{c.caso} · {c.grandeza}")
def test_cada_caso_de_aceite_passa(caso):
    (resultado,) = ca.rodar([caso])
    assert resultado.passou, (resultado.obtido, caso.esperado, resultado.erro)


def test_caso_que_quebra_aparece_reprovado_com_o_motivo():
    quebrado = ca.CasoDeAceite("teste", "x", "y", 1.0, lambda: 1 / 0)
    (resultado,) = ca.rodar([quebrado])
    assert not resultado.passou and "ZeroDivisionError" in resultado.erro
    assert ca.linhas([resultado])[0][-1].startswith("NÃO — ZeroDivisionError")
