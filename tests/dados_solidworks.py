"""Arquivos CSV no formato do SolidWorks Simulation em português, gerados para os testes.

O pórtico do mini exemplo (dois pilares W 200 × 35,9 de 4 m engastados e uma viga W 310 × 32,7 de
6 m) é resolvido pelo solver do programa para os casos PP, SC, W0 e W180; cada barra é dividida em
elementos, como a malha de vigas do SolidWorks, e as forças nas pontas de cada elemento são
escritas como "Listar forças da viga" (codificação cp1252, ponto de milhar, vírgula decimal). As
reações saem como "Listar forças resultantes", com Y vertical.
"""

from __future__ import annotations

import math
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


def csv_tensoes_da_viga(
    caso: str,
    *,
    estudo: str | None = None,
    fator_da_area: float = 1.0,
    com_pior: bool = True,
    unidade: str = "N/m^2",
) -> bytes:
    """O "Listar tensões da viga" do caso: σ = N/A e M/W de cada ponta (compressão negativa),
    com a mesma numeração de elementos do "Listar forças da viga". ``fator_da_area`` simula um
    Simulation que usou outra seção."""
    r = resolver(caso)
    por_id = {e["elemento"]: e for e in r.esforcos_elementos}
    pilar = sc.obter_perfil("W 200 x 35,9 (H)")
    viga = sc.obter_perfil("W 310 x 32,7")
    escala = {"N/m^2": 1e6, "MPa": 1.0, "N/mm^2": 1.0}[unidade]
    colunas = ["Axial", "Direção de curvatura1", "Direção de curvatura2", "Torcional"]
    if com_pior:
        colunas.append("Pior cenário")
    linhas = [
        "sep=;",
        "19:57; segunda-feira; outubro 12; 2026",
        f"Nome do estudo:{estudo or caso}",
        "",
        "Nome da viga  ;Elemento  ;Fim  ;" + ";".join(f"{c} ({unidade})  " for c in colunas),
    ]
    for nome, lista in BARRAS.items():
        perfil = viga if "C8" in nome else pilar
        area = perfil.area_mm2 * fator_da_area
        modulo = perfil.ix_mm4 / (perfil.altura_mm / 2)
        linhas.append(f"{nome}  ;" + "  ;" * (len(colunas) + 1))
        for ident, _, _ in lista:
            e = por_id[ident]
            for fim, n, m in (("1", -e["Ni_N"], -e["Mi_Nmm"]), ("2", e["Nj_N"], e["Mj_Nmm"])):
                axial, flexao = n / area * escala, m / modulo * escala
                valores = [axial, 0.0, flexao, 0.0]
                if com_pior:
                    valores.append(abs(axial) + abs(flexao))
                rotulo = f"{30000 + ident}" if fim == "1" else ""
                linhas.append(
                    f"  ;{rotulo}  ;{fim}  ;"
                    + ";".join(f"{v:.4e}".replace(".", ",") + "  " for v in valores)
                )
    linhas.append("  ;" * (len(colunas) + 3))
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


#: Corpo de cada barra no esqueleto da macro: item da lista de corte, descrição, pontas (mm) e o
#: perfil de onde sai o volume.
CORPOS = {
    "Aparar/Estender12[1]": ("W8x31<1>", "W8x31", (0, 0, 0), (0, H, 0), "W 200 x 35,9 (H)"),
    "Canal c C8X13.75(1)[2]": (
        "W 310 x 32,7<2>",
        "W 310 x 32,7",
        (0, H, 0),
        (L, H, 0),
        "W 310 x 32,7",
    ),
    "Aparar/Estender12[2]": ("W8x31<1>", "W8x31", (L, 0, 0), (L, H, 0), "W 200 x 35,9 (H)"),
}


def _campo(texto: str) -> str:
    """Como a macro escreve (Campo): entre aspas, com as aspas de dentro dobradas."""
    return '"' + texto.replace('"', '""') + '"'


def _texto_do_poligono(pontos, texto) -> str:
    return " | ".join(" ".join(texto(v) for v in ponto) for ponto in pontos)


def csv_esqueleto(
    *,
    corpos: dict | None = None,
    escala_do_volume: float = 1.0,
    com_volume: bool = True,
    decimal: str = ",",
    volumes_cm3: dict | None = None,
    formas: dict | None = None,
    versao: str = "v5",
    versao_antiga: bool = False,
    direcoes: dict | None = None,
    contornos: dict | None = None,
    aberturas: dict | None = None,
    linhas_extras: tuple[str, ...] = (),
) -> bytes:
    """O ``<peça>_esqueleto.csv`` da macro (cp1252; ``Format "0.0"``; mm e cm³).

    v5 (padrão): cabeçalho (macro, peça, configuração, data), forma, medidas e direção da seção
    (a medida maior: a alma) e, nas chapas, o contorno e as aberturas (``contornos`` e
    ``aberturas``: nome → pontos em mm). ``versao="v4"``: sem direção nem contorno.
    ``versao_antiga`` (v3): sem cabeçalho, forma nem seção.
    """

    def texto(valor: float) -> str:
        return f"{valor:.1f}".replace(".", decimal)

    if versao_antiga:
        versao = "v3"
    colunas = (
        "CORPO;ITEM DA LISTA;DESCRICAO;FORMA;X1 (mm);Y1 (mm);Z1 (mm);X2 (mm);Y2 (mm);Z2 (mm);"
        "COMPRIMENTO (mm);SECAO A (mm);SECAO B (mm);VOLUME (cm3)"
    )
    if versao == "v3":
        linhas = [
            "CORPO;ITEM DA LISTA;DESCRICAO;X1 (mm);Y1 (mm);Z1 (mm);X2 (mm);Y2 (mm);Z2 (mm);"
            "COMPRIMENTO (mm);VOLUME (cm3)"
        ]
    else:
        if versao == "v5":
            colunas += ";DIRECAO A X;DIRECAO A Y;DIRECAO A Z;CONTORNO (mm);ABERTURAS (mm)"
        linhas = [
            f'MACRO;"Mecanica Toolkit - exportar_lista_de_corte {versao}"',
            'PECA;"portico.SLDPRT"',
            'CONFIGURACAO;"Padrão"',
            'DATA;"2026-10-12 18:30"',
            colunas,
        ]
    for nome, (item, descricao, p1, p2, perfil) in (corpos or CORPOS).items():
        comprimento = sum((b - a) ** 2 for a, b in zip(p1, p2, strict=True)) ** 0.5
        secao = sc.obter_perfil(perfil)
        volume = secao.area_mm2 * comprimento / 1000 * escala_do_volume
        volume = (volumes_cm3 or {}).get(nome, volume)
        pontas = ";".join(texto(v) for v in (*p1, *p2))
        cauda = texto(volume) if com_volume else ""
        if versao == "v3":
            linhas.append(
                f"{_campo(nome)};{_campo(item)};{_campo(descricao)};{pontas};"
                f"{texto(comprimento)};{cauda}"
            )
            continue
        forma = (formas or {}).get(nome, "BARRA")
        medidas = f"{texto(secao.altura_mm)};{texto(secao.largura_mm)}"
        linha = (
            f"{_campo(nome)};{_campo(item)};{_campo(descricao)};{forma};{pontas};"
            f"{texto(comprimento)};{medidas};{cauda}"
        )
        if versao == "v5":
            # A alma: na horizontal (X) num pilar, na vertical (Y) numa barra deitada.
            vertical = abs(p2[1] - p1[1]) >= 0.97 * comprimento if comprimento else False
            direcao = (direcoes or {}).get(nome, (1.0, 0.0, 0.0) if vertical else (0.0, 1.0, 0.0))
            componentes = ";".join(f"{v:.4f}".replace(".", decimal) for v in direcao)
            contorno = _texto_do_poligono((contornos or {}).get(nome, ()), texto)
            furos = " || ".join(
                _texto_do_poligono(abertura, texto) for abertura in (aberturas or {}).get(nome, ())
            )
            linha += f';{componentes};"{contorno}";"{furos}"'
        linhas.append(linha)
    linhas.extend(linhas_extras)
    return "\r\n".join(linhas).encode("cp1252")


def peso_do_esqueleto_kN(escala_do_volume: float = 1.0) -> float:
    """O aço dos três corpos (7 850 kg/m³), para escolher a escala que faz o PP bater."""
    volume_m3 = sum(
        sc.obter_perfil(perfil).area_mm2 * math.dist(p1, p2) / 1e9
        for _, _, p1, p2, perfil in CORPOS.values()
    )
    return volume_m3 * escala_do_volume * 7850.0 * 9.80665 / 1e3


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
