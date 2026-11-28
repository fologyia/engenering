"""Representação lateral esquemática do enrijecedor de chapa estendida 4ES."""

from __future__ import annotations

from core import cena_3d as c3
from core import desenho_2d as d2
from core import perfil_i as pi


def vista_lateral(
    altura: float, comprimento: float, esp_chapa: float, esp_mesa: float
) -> c3.Desenho2D:
    """Desenha parte da viga, chapa e reforço; não posiciona parafusos ou soldas."""
    # O perfil e chapa se estendem além do recorte local mostrado.
    enq = c3.Enquadramento(
        [(-esp_chapa - 45, -70), (comprimento + 45, altura + 70)], (40, 65, 580, 330)
    )

    def p(x: float, y: float) -> tuple[float, float]:
        return enq((x, -y))

    def pol(pontos: tuple[tuple[float, float], ...], cor: str) -> c3.Poligono2D:
        return c3.Poligono2D(tuple(p(x, y) for x, y in pontos), cor, "#405b6b", 1.2)

    itens: list[d2.Item] = [
        pol(((-esp_chapa, -55), (0, -55), (0, altura), (-esp_chapa, altura)), "#d7e6ec"),
        pol(
            ((0, -esp_mesa), (comprimento + 35, -esp_mesa), (comprimento + 35, 0), (0, 0)),
            "#839ba9",
        ),
        pol(((0, 0), (comprimento, 0), (0, altura)), "#8bbbd2"),
    ]
    itens += d2.cota(
        p(-esp_chapa - 20, 0), p(-esp_chapa - 20, altura), f"h_st = {pi.numero(altura)} mm"
    )
    itens += d2.cota(
        p(0, -esp_mesa - 22), p(comprimento, -esp_mesa - 22), f"L_st = {pi.numero(comprimento)} mm"
    )
    itens.append(
        d2.texto(
            310,
            385,
            "Azul: enrijecedor · cinza: mesa da viga · claro: chapa de extremidade",
            tamanho=10,
        )
    )
    itens.append(
        d2.texto(
            310,
            405,
            "Esquema local: sem recortes, trechos planos, soldas ou parafusos.",
            tamanho=10,
            cor=d2.COR_SUAVE,
        )
    )
    return c3.Desenho2D(620, 425, tuple(itens), titulo="4ES — vista lateral esquemática")
