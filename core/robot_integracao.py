"""Comparação dos resultados e transferência rastreável de esforços do Robot."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import apoios_do_modelo as am
from core import esforcos_modelo as em
from core import exportacao_cargas as ex
from core import plano_de_cargas as pc
from core import robot

COMPONENTES = ("N (kN)", "Vy (kN)", "Vz (kN)", "My (kN·m)", "Mz (kN·m)", "T (kN·m)")
TOL_ABSOLUTA = 0.02
TOL_RELATIVA = 0.005


def ler_fatores(texto: str, casos: Mapping[str, Any]) -> dict[str, float]:
    """Lê fatores declarados pelo responsável no formato caso:fator."""
    fatores = {}
    for termo in texto.split(";"):
        if not termo.strip():
            continue
        caso, separador, fator = termo.partition(":")
        caso = caso.strip()
        if not separador or casos.get(caso, {}).get("tipo") != "Casos" or caso in fatores:
            raise robot.ImportacaoRobotInvalida(
                f"Termo inválido {termo!r}. Use caso:fator, com IDs dos casos simples."
            )
        try:
            valor = float(fator.strip().replace(",", "."))
        except ValueError as erro:
            raise robot.ImportacaoRobotInvalida(f"Fator inválido para o caso {caso}.") from erro
        if not math.isfinite(valor):
            raise robot.ImportacaoRobotInvalida(f"Fator não finito para o caso {caso}.")
        if valor:
            fatores[caso] = valor
    return fatores


def _chave(estado: str, fatores: Mapping[str, float]) -> tuple[str, tuple[tuple[str, float], ...]]:
    return estado, tuple(sorted((caso, round(f, 9)) for caso, f in fatores.items() if round(f, 9)))


def _vinculos(modelo: Mapping[str, Any]) -> dict[str, str]:
    vinculos = {}
    duplicados = set()
    for id_, metadados in modelo["casos"].items():
        codigo = metadados.get("codigo_plano")
        if metadados["tipo"] == "Casos" and metadados["analise"] == robot.LINEAR and codigo:
            if codigo in vinculos:
                duplicados.add(codigo)
            vinculos[codigo] = id_
    return {codigo: id_ for codigo, id_ in vinculos.items() if codigo not in duplicados}


@dataclass(frozen=True)
class Comparacao:
    pares: tuple[tuple[str, str], ...]
    sem_par: tuple[str, ...]
    sem_ponto: int
    pontos_sem_par: tuple[tuple[str, str, str, str], ...]
    pontos: int
    divergencias: tuple[tuple[Any, ...], ...]
    maior: tuple[Any, ...] | None

    def resumo(self) -> dict[str, Any]:
        return {
            "pares": [list(par) for par in self.pares],
            "sem_par": list(self.sem_par),
            "pontos": self.pontos,
            "sem_ponto": self.sem_ponto,
            "divergencias": len(self.divergencias),
            "maior": list(self.maior or ()),
        }


def comparar(
    modelo: Mapping[str, Any],
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    estados: Sequence[str],
) -> Comparacao:
    vinculos = _vinculos(modelo)
    combinacoes = pc.combinacoes(plano, estados)
    candidatos = {}
    sem_par = []
    for c in combinacoes:
        nome = ex.nome_da_combinacao(c, len(combinacoes))
        ativos = {codigo: f for codigo, f in c.fatores.items() if f}
        if ativos.keys() - vinculos.keys():
            sem_par.append(f"Toolkit {nome} · falta vínculo com caso linear")
            continue
        fatores = {vinculos[k]: f for k, f in ativos.items()}
        candidatos[_chave(c.estado_limite, fatores)] = (nome, fatores)
    usados = set()
    pares = []
    divergencias = []
    maior = None
    pontos_sem_par: list[tuple[str, str, str, str]] = []
    pontos = 0
    familias = {c.split("/")[0] for c in dados.casos if "/" in c}
    for codigo, caso in modelo["casos"].items():
        if caso["tipo"] != "Combinações" or caso["estado"] not in estados:
            continue
        if codigo not in dados.casos:
            if codigo not in familias:
                sem_par.append(f"Robot {codigo} · faltam esforços exportados")
            continue
        fatores = caso.get("componentes") or {}
        chave = _chave(caso["estado"], fatores)
        if caso["analise"] != robot.LINEAR or not fatores or chave not in candidatos:
            motivo = "confirme os fatores" if not fatores else "sem combinação linear equivalente"
            sem_par.append(f"Robot {codigo} · {motivo}")
            continue
        usados.add(chave)
        nome, fatores = candidatos[chave]
        pares.append((codigo, nome))
        for barra in modelo["barras"]:
            direto = {p.chave: p.vetor() for p in dados.casos[codigo].membros.get(barra, ())}
            base = {
                id_: {p.chave: p.vetor() for p in dados.casos[id_].membros.get(barra, ())}
                if id_ in dados.casos
                else {}
                for id_ in fatores
            }
            todos = set(direto).union(*(set(p) for p in base.values()))
            comuns = set(direto).intersection(*(set(p) for p in base.values()))
            pontos_sem_par.extend(
                (codigo, nome, barra, robot._rotulo_ponto(p))
                for p in sorted(todos - comuns, key=lambda p: (float(p[0]), p[1]))
            )
            if not todos:
                pontos_sem_par.append((codigo, nome, barra, "Barra sem pontos"))
            for posicao in sorted(comuns, key=lambda p: (float(p[0]), p[1])):
                pontos += 1
                for i, valor in enumerate(direto[posicao]):
                    calculado = math.fsum(f * base[id_][posicao][i] for id_, f in fatores.items())
                    delta = valor - calculado
                    tolerancia = max(TOL_ABSOLUTA, TOL_RELATIVA * max(abs(valor), abs(calculado)))
                    linha = (
                        codigo,
                        nome,
                        barra,
                        robot._rotulo_ponto(posicao),
                        COMPONENTES[i],
                        valor,
                        calculado,
                        delta,
                        tolerancia,
                    )
                    if maior is None or abs(delta) > abs(maior[7]):
                        maior = linha
                    if abs(delta) > tolerancia:
                        divergencias.append(linha)
    sem_par.extend(f"Toolkit {v[0]}" for k, v in candidatos.items() if k not in usados)
    divergencias.sort(key=lambda v: -abs(v[7]))
    return Comparacao(
        tuple(pares),
        tuple(sem_par),
        len(pontos_sem_par),
        tuple(pontos_sem_par),
        pontos,
        tuple(divergencias),
        maior,
    )


@dataclass(frozen=True)
class Solicitacao:
    combinacao: str
    vetor: tuple[float, ...]
    b2: float
    posicao: str


def solicitacoes_da_barra(
    modelo: Mapping[str, Any],
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    barra: str,
    estado: str,
) -> tuple[tuple[str, ...], dict[str, list[Solicitacao]]]:
    preparo = robot.preparar_combinacoes(
        {**modelo, "barras": {barra: modelo["barras"][barra]}},
        dados,
        plano,
        [estado],
    )
    b2 = dados.parametros_do_tipo(dados.membros[barra].tipo).b2
    pontos: dict[str, list[Solicitacao]] = {}
    for nome, ponto, vetor in em.combinados_do_membro(barra, preparo)[0]:
        fator = 1.0 if nome in preparo.segunda_ordem else b2
        pontos.setdefault(ponto, []).append(
            Solicitacao(nome, tuple(v * fator for v in vetor), fator, ponto)
        )
    return preparo.nomes, pontos


def selecionar(
    modelo: Mapping[str, Any],
    dados: em.EsforcosDoModelo,
    plano: pc.PlanoDeCargas,
    barra: str,
    posicao: str,
    lado: str,
    estado: str,
) -> list[Solicitacao]:
    nomes, pontos = solicitacoes_da_barra(modelo, dados, plano, barra, estado)
    rotulo = robot._rotulo_ponto((posicao, lado))
    selecionadas = pontos.get(rotulo, [])
    if {p.combinacao for p in selecionadas} != set(nomes) or not selecionadas:
        raise robot.ImportacaoRobotInvalida(
            f"Exporte a barra {barra} com {rotulo} em todas as combinações de {estado}."
        )
    return selecionadas


def reacoes_combinadas(
    modelo: Mapping[str, Any],
    plano: pc.PlanoDeCargas,
    no: int,
    estado: str,
) -> dict[str, tuple[float, ...]]:
    apoios = am.de_dicionario(modelo.get("reacoes"))
    valores = {
        codigo: tuple(u / 1000 for u in (*p.forca_N, *p.momento_Nm))
        for codigo, caso in apoios.casos.items()
        for p in caso.nos
        if p.no == no
    }
    if modelo["origem_combinacoes"] == robot.ROBOT:
        saida = {}
        filhos = {c.split("/")[0] for c in valores if "/" in c}
        esforcos = modelo["esforcos"]["casos"]
        for codigo, caso in modelo["casos"].items():
            if (
                caso["tipo"] != "Combinações"
                or caso["estado"] != estado
                or (codigo in filhos and codigo not in esforcos)
            ):
                continue
            if codigo not in valores:
                raise robot.ImportacaoRobotInvalida(
                    f"Falta a reação do nó {no} na combinação {codigo}."
                )
            nome = f"Robot {codigo}" + (f" · {caso['nome']}" if caso["nome"] else "")
            saida[nome] = valores[codigo]
        return saida
    vinculos = _vinculos(modelo)
    lista = pc.combinacoes(plano, [estado])
    saida = {}
    for c in lista:
        ativos = {k: f for k, f in c.fatores.items() if f}
        faltam = [k for k in ativos if vinculos.get(k) not in valores]
        if faltam:
            raise robot.ImportacaoRobotInvalida(
                f"Faltam reações no nó {no} para {', '.join(faltam)}."
            )
        saida[ex.nome_da_combinacao(c, len(lista))] = tuple(
            math.fsum(f * valores[vinculos[k]][i] for k, f in ativos.items()) for i in range(6)
        )
    return saida


def placa_com_reacao(reacao: Sequence[float], angulo: float) -> dict[str, float]:
    """Converte reação global para ação na placa, com Z para cima e x local na direção informada."""
    fx, fy, fz, mx, my, mz = reacao
    c, s = math.cos(math.radians(angulo)), math.sin(math.radians(angulo))
    vx, vy = -(c * fx + s * fy), -(-s * fx + c * fy)
    mx_placa, my_placa = -(c * mx + s * my), -(-s * mx + c * my)
    return {
        "n_sd_kN": fz,
        "m_sd_kNm": my_placa,
        "m_sd_y_kNm": -mx_placa,
        "vx_kN": vx,
        "vy_kN": vy,
        "v_sd_kN": math.hypot(vx, vy),
        "mz_kNm": -mz,
    }


def placa_com_corte(vetor: Sequence[float], ponta: str, eixo_forte: str) -> dict[str, float]:
    """Ação na placa de pilar vertical pela face correspondente ao nó inferior.

    O x da placa acompanha +z local para My forte e +y para Mz forte. O y da
    placa completa o sistema direto com Z global para cima. O motor da placa
    recebe os primeiros momentos da pressão nas direções x e y.
    """
    n, vy, vz, my, mz, t = vetor
    sentido = 1 if ponta == "0" else -1
    if eixo_forte == em.EIXO_M1:
        vx, vy_placa, mx_placa, my_placa = -sentido * vz, vy, my, sentido * mz
    else:
        vx, vy_placa, mx_placa, my_placa = -sentido * vy, -vz, -mz, sentido * my
    return {
        "n_sd_kN": -n,
        "m_sd_kNm": mx_placa,
        "m_sd_y_kNm": my_placa,
        "vx_kN": vx,
        "vy_kN": vy_placa,
        "v_sd_kN": math.hypot(vx, vy_placa),
        "mz_kNm": -t,
    }


def fonte(
    projeto: Mapping[str, Any],
    *,
    finalidade: str = "calculo",
    barra: str = "",
    no: int | None = None,
    linhas: Sequence[Solicitacao] = (),
    origem: str | None = None,
    tipos: Sequence[str] = ("Esforços",),
) -> dict[str, Any]:
    from core.project_dependencies import catalogar_fontes_projeto

    modelo = robot.modelo_do_projeto(projeto)
    if not modelo:
        return {}
    modo = origem or modelo["origem_combinacoes"]
    chaves = ["robot:remessa", f"robot:{finalidade}"]
    if barra and finalidade == "calculo":
        chaves = ["robot:remessa", "robot:combinacoes", f"robot:barra:{barra}"]
    if modo == robot.TOOLKIT or finalidade == "comparacao":
        chaves.append("robot:plano")
    catalogo = catalogar_fontes_projeto(projeto)
    return {
        "contexto": {**robot.contexto(modelo), "origem_combinacoes": modo},
        "documentos": {t: a["tabela"] for t, a in modelo["arquivos"].items() if t in tipos},
        "barra": barra,
        "no": no,
        "esforcos": [
            {"combinacao": l.combinacao, "posicao": l.posicao, "b2": l.b2, "vetor": list(l.vetor)}
            for l in linhas
        ],
        "dependencias": [catalogo[k] for k in chaves if k in catalogo],
    }


def registrar(registro: Mapping[str, Any], origem: Mapping[str, Any] | None) -> dict[str, Any]:
    if not origem:
        return dict(registro)
    entradas = {**registro.get("entradas", {}), **origem["contexto"]}
    if origem.get("barra"):
        entradas["barra_robot"] = origem["barra"]
    if origem.get("no") is not None:
        entradas["no_robot"] = origem["no"]
    if origem.get("documentos"):
        entradas["fonte_dos_esforcos_robot"] = ", ".join(origem["documentos"].values())
    if origem.get("editado"):
        entradas["ajuste_dos_esforcos"] = "Solicitações editadas após a transferência do Robot."
    resultados = dict(registro.get("resultados", {}))
    if origem["esforcos"]:
        tabela = {
            "legenda": "Esforços simultâneos transferidos do Robot, nos eixos locais da barra.",
            "cabecalhos": ["Combinação", "Posição", *COMPONENTES, "B₂"],
            "linhas": [
                [r["combinacao"], r["posicao"], *(f"{v:.4g}" for v in r["vetor"]), f"{r['b2']:.3g}"]
                for r in origem["esforcos"]
            ],
        }
        resultados["tabelas_memorial"] = [*resultados.get("tabelas_memorial", []), tabela]
    return {
        **registro,
        "entradas": entradas,
        "resultados": resultados,
        "dependencias": [*registro.get("dependencias", []), *origem["dependencias"]],
        "fonte_robot": {k: v for k, v in origem.items() if k not in {"dependencias", "esforcos"}},
    }


def tabelas_de_proveniencia(registros: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    fontes = {}
    calculos = []
    comparacoes = []
    for r in registros:
        entradas = r.get("entradas", {})
        if not isinstance(entradas, Mapping) or not entradas.get("assinatura_remessa_robot"):
            continue
        identificacao = str(entradas["assinatura_remessa_robot"])
        fontes[(identificacao, str(entradas.get("relatorio_robot") or ""))] = [
            str(entradas.get(k) or "—")
            for k in (
                "modelo_robot",
                "revisao_modelo_robot",
                "relatorio_robot",
                "tabelas_robot",
                "unidades_robot",
            )
        ]
        estado = r.get("estado_dependencias") or {}
        calculos.append(
            [
                str(r.get("titulo", "")),
                str(entradas.get("revisao_modelo_robot", "")),
                str(entradas.get("origem_combinacoes") or "Casos simples do Robot"),
                str(entradas.get("fonte_dos_esforcos_robot") or "Tabelas da remessa"),
                str(estado.get("status") or "—"),
            ]
        )
        resultados = r.get("resultados") or {}
        c = resultados.get("comparacao_robot") or {}
        if c:
            maior = c.get("maior") or []
            comparacoes.append(
                [
                    str(entradas.get("revisao_modelo_robot", "")),
                    str(len(c.get("pares", []))),
                    str(c.get("pontos", 0)),
                    str(c.get("divergencias", 0)),
                    str(c.get("sem_ponto", 0)),
                    ", ".join(c.get("sem_par", [])) or "—",
                    f"Barra {maior[2]}, {maior[3]}, {maior[4]} · Δ {maior[7]:.4g}"
                    if maior
                    else "—",
                ]
            )
    tabelas = []
    if fontes:
        tabelas.extend(
            [
                {
                    "legenda": "Remessas do Autodesk Robot usadas neste memorial.",
                    "cabecalhos": [
                        "Modelo",
                        "Revisão",
                        "Relatório do Robot",
                        "Tabelas usadas",
                        "Unidades",
                    ],
                    "linhas": list(fontes.values()),
                    "larguras": [1450, 750, 1800, 3850, 1510],
                },
                {
                    "legenda": "Origem dos esforços por cálculo.",
                    "cabecalhos": [
                        "Cálculo",
                        "Revisão",
                        "Combinações",
                        "Fonte dos esforços",
                        "Atualidade",
                    ],
                    "linhas": calculos,
                    "larguras": [2000, 800, 1900, 3100, 1560],
                },
            ]
        )
    if comparacoes:
        tabelas.append(
            {
                "legenda": "Comparação Robot e Toolkit.",
                "cabecalhos": [
                    "Revisão",
                    "Pares",
                    "Pontos",
                    "Divergências",
                    "Pontos sem par",
                    "Combinações sem par",
                    "Maior diferença",
                ],
                "linhas": comparacoes,
                "larguras": [820, 700, 820, 1020, 1000, 2600, 2400],
            }
        )
    return tabelas
