"""Arquivos CSV no formato do SolidWorks Simulation em português, gerados para os testes.

O pórtico do mini exemplo (dois pilares W 200 × 35,9 de 4 m engastados e uma viga W 310 × 32,7 de
6 m) é resolvido pelo solver do programa para os casos PP, SC, W0 e W180; cada barra é dividida em
elementos, como a malha de vigas do SolidWorks, e as forças nas pontas de cada elemento são
escritas como "Listar forças da viga" (codificação cp1252, ponto de milhar, vírgula decimal). As
reações saem como "Listar forças resultantes", com Y vertical.
"""

from __future__ import annotations

from functools import cache

from core import section_catalog as sc
from core import structural_2d as s2

H, L, E = 4000.0, 6000.0, 200_000.0
CASOS = {"PP": (1.5, 0.0), "SC": (10.0, 0.0), "W0": (0.0, 8000.0), "W180": (0.0, -8000.0)}
#: Barra do SolidWorks → elementos (id, nó i, nó j) do solver.
BARRAS = {
    "Viga-1(Aparar/Estender12[1])": [(101, 1, 11), (102, 11, 2)],
    "Viga-2(Canal c C8X13.75(1)[2])": [(201, 2, 21), (202, 21, 22), (203, 22, 23), (204, 23, 3)],
    "Viga-3(Aparar/Estender12[2])": [(301, 4, 31), (302, 31, 3)],
}


def _pt(valor: float, casas: int = 4) -> str:
    texto = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto.rstrip("0").rstrip(",") if "," in texto else texto


@cache
def resolver(caso: str) -> s2.ResultadoEstrutural:
    q, fh = CASOS[caso]
    pilar = sc.obter_perfil("W 200 x 35,9 (H)")
    viga = sc.obter_perfil("W 310 x 32,7")
    nos = [
        s2.NoPortico(1, 0, 0, True, True, True),
        s2.NoPortico(11, 0, H / 2),
        s2.NoPortico(2, 0, H, fx_N=fh),
        s2.NoPortico(21, L / 4, H),
        s2.NoPortico(22, L / 2, H),
        s2.NoPortico(23, 3 * L / 4, H),
        s2.NoPortico(3, L, H),
        s2.NoPortico(31, L, H / 2),
        s2.NoPortico(4, L, 0, True, True, True),
    ]
    elementos = []
    for nome, lista in BARRAS.items():
        perfil = viga if "C8" in nome else pilar
        carga = -q if "C8" in nome else 0.0
        for ident, i, j in lista:
            elementos.append(
                s2.ElementoPortico(ident, i, j, perfil.area_mm2, perfil.ix_mm4, E, carga)
            )
    return s2.analisar_portico(nos, elementos)


def csv_forcas_da_viga(caso: str, *, estudo: str | None = None, ids: dict | None = None) -> bytes:
    """O "Listar forças da viga" do caso; ``ids`` troca a numeração de elementos (malha diferente)."""
    r = resolver(caso)
    por_id = {e["elemento"]: e for e in r.esforcos_elementos}
    linhas = [
        "sep=;",
        "08:28; sexta-feira; outubro 09; 2026",
        f"Nome do estudo:{estudo or caso}",
        "",
        "Nome da viga  ;Elemento  ;Fim  ;Axial (N)  ;Cisalhamento1 (N)  ;Cisalhamento2 (N)  ;"
        "Momento 1 (N.m)  ;Momento 2 (N.m)  ;Torque (N.m)",
    ]
    for nome, lista in BARRAS.items():
        linhas.append(f"{nome}  ;  ;  ;  ;  ;  ;  ;  ;")
        for ident, _, _ in lista:
            e = por_id[ident]
            rotulo = (ids or {}).get(ident, 30000 + ident)
            linhas.append(
                f"  ;{rotulo}  ;1  ;{_pt(e['Ni_N'])}  ;{_pt(e['Vi_N'])}  ;0  ;0  ;"
                f"{_pt(e['Mi_Nmm'] / 1000)}  ;0"
            )
            linhas.append(
                f"  ;  ;2  ;{_pt(e['Nj_N'])}  ;{_pt(e['Vj_N'])}  ;0  ;0  ;"
                f"{_pt(e['Mj_Nmm'] / 1000)}  ;0"
            )
    linhas.append("  ;  ;  ;  ;  ;  ;  ;  ;")
    return "\r\n".join(linhas).encode("cp1252")


def csv_reacoes(caso: str, *, extra_z_N: float = 0.0) -> bytes:
    r = resolver(caso)
    rx = sum(float(x["rx_N"]) for x in r.reacoes_nodais)
    ry = sum(float(x["ry_N"]) for x in r.reacoes_nodais)
    linhas = [
        "08:29; sexta-feira; outubro 09; 2026",
        f"Nome do estudo:{caso}",
        "",
        "Força de reação (N)",
        "",
        "Componente  ;Seleção  ;Modelo inteiro",
        f"Soma X:  ;{_pt(rx)}  ;{_pt(rx)}",
        f"Soma Y:  ;{_pt(ry)}  ;{_pt(ry)}",
        f"Soma Z:  ;{_pt(extra_z_N)}  ;{_pt(extra_z_N)}",
        f"Resultante:  ;{_pt(abs(ry))}  ;{_pt(abs(ry))}",
        "",
        "",
        "Momento de reação (N.m)",
        "",
        "Componente  ;Seleção  ;Modelo inteiro",
        "Soma X:  ;0  ;0",
        "Soma Y:  ;0  ;0",
        "Soma Z:  ;0  ;0",
        "Resultante:  ;0  ;0",
    ]
    return "\r\n".join(linhas).encode("cp1252")


def csv_tensoes() -> bytes:
    linhas = [
        "08:30; sexta-feira; outubro 09; 2026",
        "Nome do estudo:PP",
        "Unidades: N/m^2",
        "Referência selecionada: N/A",
        "Nó  ;X (mm)  ;Y (mm)  ;Z (mm)  ;VON (N/m^2)",
        "40849  ;3148,79  ;-1974,36  ;1200  ;4,07610e+07",
        "43035  ;3146,9  ;-1977,18  ;1200  ;4,01133e+07",
    ]
    return "\r\n".join(linhas).encode("cp1252")
