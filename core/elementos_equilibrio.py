"""Caso Equilíbrio de uma peça: as tabelas da tela viram problema e a solução vira resultado.

A conta mora em :mod:`core.equilibrio_corpo`. Aqui ficam só a leitura do resultado (quem empurra,
quem puxa, quem descola, o que a estática não separa) e o que vai para o desenho da tela.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from core import equilibrio_corpo as eq
from core.desenho_estatica import figura_do_equilibrio
from core.elementos_base import (
    Campo,
    Caso,
    Coluna,
    Envio,
    Figura,
    Metrica,
    Resultado,
    Tabela,
    Valores,
    informativo,
    limite,
)
from core.equilibrio_modelos import MODELO_INICIAL
from core.verificacao import Verificacao

GRUPO = "Peças, seções e chapas"
HIBBELER = "Hibbeler, Estática"
HIBBELER_RM = "Hibbeler, Resistência dos Materiais"
_RAZAO_SUSPEITA = 50.0

HIPOTESES = (
    "Peça rígida no plano: a deformação não muda a posição dos apoios nem das cargas.",
    "Pino segura as duas direções e deixa girar. Rolete segura uma direção, para os dois lados. "
    "Apoio simples só empurra. Cabo só puxa. Biela puxa e empurra ao longo da haste. Guia segura "
    "o giro e o lado, e deixa correr. Engaste segura tudo.",
    "Fora do apoio com atrito, os apoios não têm atrito.",
    "No apoio distribuído a peça é rígida e a pressão varia em linha reta ao longo do trecho. Com "
    "base ou peça flexível, a pressão se concentra perto da carga e passa da mostrada aqui.",
    "A carga distribuída vale por unidade de comprimento da peça, ao longo do trecho desenhado.",
    "Peso usa g = 9,80665 m/s².",
)


def _numero(valor: float) -> str:
    """Número curto para o desenho: quatro algarismos e vírgula."""
    return f"{valor:.4g}".replace(".", ",")


def _posicao(valor: float) -> str:
    """Texto, e não número: a linha da soma não tem posição, e a coluna precisa aceitar o traço."""
    return f"{valor:.6g}".replace(".", ",")


def _como_trabalha(r: eq.Reacao) -> str:
    tipo = r.apoio.tipo
    texto = "Segura a peça"
    if tipo == eq.DISTRIBUIDO and not r.apoio.preso:
        p = eq.pressao_do_apoio(r)
        if p.tomba:
            texto = "Não segura: a peça tomba ou descola"
        elif p.fracao < 1.0:
            texto = f"Encostado em {p.fracao * 100:.0f} % do trecho"
        else:
            texto = "Encostado no trecho inteiro"
    elif tipo == eq.CABO:
        texto = "Tracionado" if r.n > 0.0 else "Precisaria empurrar: afrouxa"
        texto = texto if r.n != 0.0 else "Sem força"
    elif tipo == eq.BIELA:
        texto = "Tracionada" if r.n > 0.0 else "Comprimida"
        texto = texto if r.n != 0.0 else "Sem força"
    elif tipo in (eq.SIMPLES, eq.ATRITO):
        texto = "Empurra a peça" if r.n >= 0.0 else "Precisaria puxar: a peça descola"
    if r.soltas:
        return f"{texto} (divisão possível)"
    return texto


def _linha_da_reacao(r: eq.Reacao, u: eq.Unidades) -> dict[str, Any]:
    return {
        "Apoio": r.apoio.nome,
        "Tipo": r.apoio.tipo,
        f"Rx ({u.forca})": r.fx / u.newton,
        f"Ry ({u.forca})": r.fy / u.newton,
        f"Momento ({u.momento})": r.m / u.newton,
        f"Resultante ({u.forca})": r.modulo / u.newton,
        "Direção (°)": round(r.angulo, 2),
        "Como trabalha": _como_trabalha(r),
    }


def _conta(solucao: eq.Solucao, u: eq.Unidades) -> list[dict[str, Any]]:
    """Cada força, com a parte dela em cada equação. Dá para refazer na calculadora."""
    primeiro = solucao.reacoes[0].apoio
    xo, yo = primeiro.x, primeiro.y
    rotulo = f"Momento em {primeiro.nome} ({u.momento})"
    linhas: list[dict[str, Any]] = []

    def somar(nome: str, x: float, y: float, fx: float, fy: float, m: float) -> None:
        linhas.append(
            {
                "Item": nome,
                f"x ({u.comprimento})": _posicao(x / u.metro),
                f"y ({u.comprimento})": _posicao(y / u.metro),
                f"Fx ({u.forca})": fx / u.newton,
                f"Fy ({u.forca})": fy / u.newton,
                rotulo: ((x - xo) * fy - (y - yo) * fx + m) / u.newton,
            }
        )

    for a in solucao.acoes:
        somar(f"Carga {a.nome}", a.x, a.y, a.fx, a.fy, a.m)
    for r in solucao.reacoes:
        somar(f"Reação {r.apoio.nome}", *r.apoio.ponto, r.fx, r.fy, r.m)
    soma: dict[str, Any] = {
        "Item": "Soma (precisa dar zero)",
        f"x ({u.comprimento})": "—",
        f"y ({u.comprimento})": "—",
    }
    for chave in (f"Fx ({u.forca})", f"Fy ({u.forca})", rotulo):
        soma[chave] = round(sum(linha[chave] for linha in linhas), 9)
    linhas.append(soma)
    return linhas


def _linha_do_corte(e: eq.Esforco, u: eq.Unidades) -> dict[str, Any]:
    return {
        "Seção": e.corte.nome,
        f"Normal N ({u.forca})": e.n / u.newton,
        f"Cortante V ({u.forca})": e.v / u.newton,
        f"Momento M ({u.momento})": e.m / u.newton,
    }


def _checagens(solucao: eq.Solucao, u: eq.Unidades) -> list[Verificacao]:
    """Cabo não empurra, apoio não puxa, atrito tem limite. Sem separar, a linha só pede atenção."""
    folga = 1e-9 * solucao.referencia
    certeza = solucao.grau_hiperestatico <= 1
    linhas: list[Verificacao] = []
    for r in solucao.reacoes:
        apoio = r.apoio
        encostado = apoio.tipo == eq.DISTRIBUIDO and not apoio.preso
        if apoio.tipo not in eq.SO_UM_LADO and not encostado:
            continue
        ruim = "NÃO OK" if certeza or not r.soltas else "ALERTA"
        n = r.n / u.newton
        if encostado:
            nome, formula = f"Apoio {apoio.nome} encostado", "R ≥ 0: a peça só encosta, não puxa"
        elif apoio.tipo == eq.CABO:
            nome, formula = f"Cabo {apoio.nome} tracionado", "T ≥ 0: cabo não empurra"
        else:
            nome, formula = f"Apoio {apoio.nome} encostado", "N ≥ 0: apoio simples não puxa"
        linhas.append(
            Verificacao(
                nome,
                n,
                0.0,
                u.forca,
                HIBBELER,
                formula,
                status="OK" if r.n >= -folga else ruim,
                tipo="limite",
            )
        )
        if encostado:
            p = eq.pressao_do_apoio(r)
            meia = apoio.comprimento / 2.0 / u.metro
            desvio = abs(p.excentricidade) / u.metro
            linhas.append(
                Verificacao(
                    f"Resultante dentro do apoio {apoio.nome}",
                    desvio if r.n > 0.0 else 2.0 * meia,
                    meia,
                    u.comprimento,
                    HIBBELER,
                    "|e| ≤ L/2: com a resultante fora do trecho, a peça tomba",
                    status=ruim if p.tomba else "OK",
                    tipo="limite",
                )
            )
        if apoio.tipo == eq.ATRITO or (encostado and apoio.mu > 0.0):
            usado = abs(r.t) / u.newton
            maximo = max(apoio.mu * n, 0.0)
            if usado <= maximo + folga / u.newton:
                maximo = max(maximo, usado)
            linhas.append(
                limite(
                    f"Atrito em {apoio.nome}",
                    usado,
                    maximo if maximo > 0.0 else 1e-12,
                    u.forca,
                    f"|T| ≤ μ·N, μ = {apoio.mu:g}",
                    HIBBELER,
                )
            )
    return linhas


def _tabela_das_pressoes(solucao: eq.Solucao, u: eq.Unidades) -> Tabela | None:
    """A pressão que a peça faz em cada apoio distribuído, para dimensionar a base."""
    linhas: list[dict[str, Any]] = []
    k = u.metro / u.newton  # de N/m para a unidade da tela
    for r in solucao.reacoes:
        if r.apoio.tipo != eq.DISTRIBUIDO:
            continue
        p = eq.pressao_do_apoio(r)
        inicio, fim = p.nas_pontas()
        linhas.append(
            {
                "Apoio": r.apoio.nome,
                f"Trecho ({u.comprimento})": _posicao(r.apoio.comprimento / u.metro),
                f"Resultante ({u.forca})": r.n / u.newton,
                f"Posição da resultante ({u.comprimento})": _posicao(
                    (r.apoio.comprimento / 2.0 + p.excentricidade) / u.metro
                ),
                f"No início ({u.distribuida})": inicio * k,
                f"No fim ({u.distribuida})": fim * k,
                f"Maior ({u.distribuida})": p.maior * k,
                "Em contato (%)": round(p.fracao * 100.0, 1),
            }
        )
    if not linhas:
        return None
    return Tabela(
        "Pressão nos apoios distribuídos",
        tuple(linhas),
        "A posição é medida do início do trecho. Divida a pressão pela largura de contato para "
        "comparar com o limite da base.",
    )


def _resultado_sem_equilibrio(solucao: eq.Solucao, u: eq.Unidades) -> Resultado:
    movimento = solucao.movimento
    fuga = movimento.texto(u) if movimento else "anda"
    conselho = (
        "Um apoio que segure esse giro resolve: um rolete ou um cabo longe do ponto de giro, ou "
        "um engaste no lugar do pino."
        if movimento and movimento.giro
        else "Um apoio que segure essa direção resolve."
    )
    figura = figura_do_equilibrio(solucao, u)
    return Resultado(
        resumo=f"A peça não fica parada: {fuga}. Faltam apoios.",
        metricas=(
            Metrica("Situação", "Falta apoio"),
            Metrica("Reações disponíveis", solucao.incognitas, "", 0),
        ),
        verificacoes=(
            Verificacao(
                "A peça fica parada",
                3.0,
                float(solucao.posto),
                "equações",
                HIBBELER,
                "Os apoios precisam fechar ΣFx, ΣFy e ΣM: as três equações",
                status="NÃO OK",
                tipo="limite",
            ),
        ),
        figuras=(Figura("Peça", figura.png, "A peça não fecha o equilíbrio com estes apoios."),),
        alertas=(f"A peça {fuga}. {conselho}",),
        hipoteses=HIPOTESES,
        referencias=(HIBBELER,),
    )


def _situacao(solucao: eq.Solucao) -> str:
    if solucao.livres:
        return "Parada só com esta carga"
    if solucao.grau_hiperestatico:
        return f"Hiperestática, grau {solucao.grau_hiperestatico}"
    return "Isostática"


def _alertas(solucao: eq.Solucao, esforcos: Sequence[eq.Esforco], u: eq.Unidades) -> list[str]:
    alertas: list[str] = []
    if solucao.livres and solucao.movimento:
        alertas.append(
            f"Faltam apoios: a peça só fica parada porque esta carga não empurra para o lado "
            f"livre. Uma força diferente e ela {solucao.movimento.texto(u)}."
        )
    if solucao.grau_hiperestatico:
        soltas = sorted({r.apoio.nome for r in solucao.reacoes if not r.determinada})
        alertas.append(
            f"A estática não separa as reações de {', '.join(soltas)}: há mais apoios que o "
            "necessário. O valor mostrado é uma divisão possível, e a soma é certa. A divisão real "
            "depende da rigidez e das folgas. Dimensione para o pior caso ou modele em Vigas e "
            "eixos ou em Barras, treliças e pórticos."
        )
    if not solucao.divisao_viavel:
        alertas.append(
            "Nenhuma divisão das reações respeita cabo, contato e atrito ao mesmo tempo: a peça "
            "não fica parada assim."
        )
    for r in solucao.reacoes:
        if r.apoio.tipo != eq.DISTRIBUIDO or r.apoio.preso:
            continue
        if solucao.grau_hiperestatico > 1 and r.soltas:
            continue  # a divisão é só uma das possíveis: outra pode não tombar
        p = eq.pressao_do_apoio(r)
        if p.tomba:
            alertas.append(
                f"O apoio {r.apoio.nome} não segura a peça: a resultante cai fora do trecho, e ela "
                "tomba. Aumente o trecho, aproxime a carga, ou prenda a peça ao longo do apoio."
            )
        elif p.fracao < 1.0:
            alertas.append(
                f"No apoio {r.apoio.nome} a resultante saiu do terço central: só "
                f"{p.fracao * 100:.0f} % do trecho fica encostado, e o resto descola."
            )
    maior = max(r.modulo for r in solucao.reacoes)
    if maior > _RAZAO_SUSPEITA * solucao.referencia:
        alertas.append(
            f"A maior reação saiu {maior / solucao.referencia:.0f} vezes maior que a maior carga: "
            "os apoios estão muito perto ou quase alinhados. Confira a geometria."
        )
    for e in esforcos:
        if e.trechos_cortados > 1:
            alertas.append(
                f"A seção {e.corte.nome} atravessa {e.trechos_cortados} trechos da peça: N, V e M "
                "são a soma dos pedaços cortados."
            )
        elif e.trechos_cortados == 0 and solucao.problema.trechos:
            alertas.append(f"A seção {e.corte.nome} não passa por nenhum trecho da peça.")
        if e.carga_na_linha:
            alertas.append(
                f"Há carga ou apoio exatamente na seção {e.corte.nome}: o valor é o de logo depois "
                "dela, no sentido do eixo."
            )
    return alertas


def _envios(solucao: eq.Solucao, esforcos: Sequence[eq.Esforco], u: eq.Unidades) -> list[Envio]:
    envios: list[Envio] = []
    pinos = [r for r in solucao.reacoes if r.apoio.tipo == eq.PINO]
    if pinos:
        pior = max(pinos, key=lambda r: r.modulo)
        envios.append(
            Envio(
                "pino_articulacao",
                f"Dimensionar o pino {pior.apoio.nome}",
                {"forca_kN": round(pior.modulo / 1000.0, 3)},
            )
        )
    for r in solucao.reacoes:
        if r.apoio.tipo == eq.ENGASTE:
            envios.append(
                Envio(
                    "grupo_parafusos",
                    f"Parafusos do engaste {r.apoio.nome}, com a chapa no plano da peça",
                    {
                        "vx_kN": round(r.fx / 1000.0, 3),
                        "vy_kN": round(r.fy / 1000.0, 3),
                        "t_kNm": round(r.m / 1000.0, 4),
                    },
                )
            )
    if esforcos:
        pior_corte = max(esforcos, key=lambda e: abs(e.m))
        envios.append(
            Envio(
                "flexao_secao",
                f"Verificar a flexão na seção {pior_corte.corte.nome}",
                {
                    "m_kNm": round(abs(pior_corte.m) / 1000.0, 4),
                    "v_kN": round(abs(pior_corte.v) / 1000.0, 3),
                    "n_kN": round(pior_corte.n / 1000.0, 3),
                },
            )
        )
    return envios


def _problema(v: Valores) -> tuple[eq.Problema, eq.Unidades]:
    unidades = eq.Unidades(str(v["comprimento"]), str(v["forca"]))
    problema = eq.problema_das_tabelas(
        v["trechos"], v["apoios"], v["cargas"], v["cortes"], unidades
    )
    return problema, unidades


def calcular_equilibrio(v: Valores) -> Resultado:
    problema, u = _problema(v)
    solucao = eq.resolver(problema)
    if not solucao.para:
        return _resultado_sem_equilibrio(solucao, u)

    esforcos = tuple(eq.esforco_no_corte(solucao, c) for c in problema.cortes)
    residuo_f, residuo_m = eq.residuos(solucao)
    verificacoes = [
        Verificacao(
            "A peça fica parada",
            3.0,
            3.0,
            "equações",
            HIBBELER,
            "ΣFx, ΣFy e ΣM fecham com estes apoios",
            status="OK",
            tipo="limite",
        ),
        informativo(
            "Soma das forças com as reações",
            round(residuo_f / u.newton, 6),
            u.forca,
            "ΣF = 0: deve dar zero",
            HIBBELER,
        ),
        informativo(
            "Soma dos momentos com as reações",
            round(residuo_m / u.newton, 6),
            u.momento,
            "ΣM = 0: deve dar zero",
            HIBBELER,
        ),
        *_checagens(solucao, u),
    ]
    if solucao.grau_hiperestatico or solucao.livres:
        verificacoes.append(
            Verificacao(
                "Reações que a estática define",
                float(solucao.posto),
                float(solucao.incognitas),
                "",
                HIBBELER,
                "Três equações no plano: posto da matriz de equilíbrio",
                status="ALERTA",
                tipo="limite",
            )
        )

    forca_total = math.hypot(sum(a.fx for a in solucao.acoes), sum(a.fy for a in solucao.acoes))
    maior = max(solucao.reacoes, key=lambda r: r.modulo)
    metricas = [Metrica("Situação", _situacao(solucao))]
    metricas += [
        Metrica(f"Reação em {r.apoio.nome}", r.modulo / u.newton, u.forca)
        for r in solucao.reacoes[:5]
    ]
    metricas += [
        Metrica(f"Momento em {r.apoio.nome}", r.m / u.newton, u.momento)
        for r in solucao.reacoes
        if r.apoio.tipo in (eq.ENGASTE, eq.GUIA)
    ]
    metricas.append(Metrica("Resultante das cargas", forca_total / u.newton, u.forca))

    tabelas = [
        Tabela(
            "Reações nos apoios",
            tuple(_linha_da_reacao(r, u) for r in solucao.reacoes),
            "Rx para a direita, Ry para cima e momento anti-horário.",
        ),
        Tabela(
            "Conta passo a passo",
            tuple(_conta(solucao, u)),
            "Cada linha é uma força com a parte dela em cada equação. Momento anti-horário "
            "positivo. A carga distribuída entra pela resultante, no centro dela.",
        ),
    ]
    pressoes = _tabela_das_pressoes(solucao, u)
    if pressoes:
        tabelas.insert(1, pressoes)
    if esforcos:
        tabelas.append(
            Tabela(
                "Esforços nas seções",
                tuple(_linha_do_corte(e, u) for e in esforcos),
                "N positivo é tração. M positivo traciona a fibra de baixo na barra deitada, ou a "
                "da direita na barra em pé.",
            )
        )
    figura = figura_do_equilibrio(solucao, u)
    return Resultado(
        resumo=(
            f"Maior reação de {maior.modulo / u.newton:.2f} {u.forca} no apoio {maior.apoio.nome}. "
            f"Resultante das cargas: {forca_total / u.newton:.2f} {u.forca}."
        ),
        metricas=tuple(metricas),
        verificacoes=tuple(verificacoes),
        tabelas=tuple(tabelas),
        figuras=(Figura("Peça", figura.png, "Cargas em laranja e reações em verde."),),
        alertas=tuple(_alertas(solucao, esforcos, u)),
        hipoteses=HIPOTESES,
        referencias=(HIBBELER, HIBBELER_RM) if esforcos else (HIBBELER,),
        envios=tuple(_envios(solucao, esforcos, u)),
    )


def marcas_para_a_tela(v: Valores) -> dict[str, Any]:
    """O que a prancheta desenha por cima da peça: reações, esforços e para onde ela foge."""
    problema, u = _problema(v)
    solucao = eq.resolver(problema)

    def pressao(r: eq.Reacao) -> dict[str, Any]:
        """A prancheta desenha a pressão ao longo do trecho, no lugar de uma seta só."""
        p = eq.pressao_do_apoio(r)
        k = u.metro / u.newton
        cx, cy = r.apoio.direcao
        return {
            "x1": p.x1 / u.metro,
            "y1": p.y1 / u.metro,
            "x2": p.x2 / u.metro,
            "y2": p.y2 / u.metro,
            "w1": p.w1 * k,
            "w2": p.w2 * k,
            "cx": cx,
            "cy": cy,
            "tomba": p.tomba,
            "texto": (f"{r.apoio.nome}: {_numero(p.w1 * k)} a {_numero(p.w2 * k)} {u.distribuida}"),
        }

    def reacao(r: eq.Reacao) -> dict[str, Any]:
        x, y = r.apoio.ponto
        certa = solucao.grau_hiperestatico <= 1 or not r.soltas
        tomba = certa and r.apoio.tipo == eq.DISTRIBUIDO and eq.pressao_do_apoio(r).tomba
        return {
            "nome": r.apoio.nome,
            "x": x / u.metro,
            "y": y / u.metro,
            "fx": r.fx / u.newton,
            "fy": r.fy / u.newton,
            "m": r.m / u.newton,
            "texto": f"{r.apoio.nome} = {_numero(r.modulo / u.newton)} {u.forca}",
            "texto_m": f"M{r.apoio.nome} = {_numero(abs(r.m) / u.newton)} {u.momento}",
            "puxa": r.apoio.tipo == eq.CABO,
            "ruim": tomba or (r.apoio.tipo in eq.SO_UM_LADO and r.n < -1e-9 * solucao.referencia),
            "pressao": pressao(r) if r.apoio.tipo == eq.DISTRIBUIDO else None,
        }

    movimento = solucao.movimento
    cortes = []
    if solucao.para:
        for corte in problema.cortes:
            e = eq.esforco_no_corte(solucao, corte)
            cortes.append(
                f"N {_numero(e.n / u.newton)} · V {_numero(e.v / u.newton)} {u.forca} · "
                f"M {_numero(e.m / u.newton)} {u.momento}"
            )
    return {
        "para": solucao.para,
        "reacoes": [reacao(r) for r in solucao.reacoes] if solucao.para else [],
        "cortes": cortes,
        "movimento": (
            None
            if movimento is None or solucao.para
            else {
                "giro": movimento.giro,
                "x": movimento.x / u.metro,
                "y": movimento.y / u.metro,
                "angulo": movimento.angulo,
                "sentido": movimento.sentido,
                "texto": movimento.texto(u),
            }
        ),
    }


def _linhas(chave: str) -> tuple[Mapping[str, Any], ...]:
    return tuple(dict(linha) for linha in getattr(MODELO_INICIAL, chave))


_X = "Posição horizontal, na unidade escolhida. Vale qualquer origem."
_Y = "Posição vertical, na unidade escolhida, com y para cima."

CAMPOS_EQUILIBRIO: tuple[Campo, ...] = (
    Campo(
        "comprimento",
        "Unidade de comprimento",
        "Vale para todas as posições. Trocar a unidade converte os números: a peça é a mesma.",
        MODELO_INICIAL.comprimento,
        opcoes=tuple(eq.COMPRIMENTOS),
        secao="Unidades",
    ),
    Campo(
        "forca",
        "Unidade de força",
        "Vale para forças e reações. Momento sai em força vezes metro.",
        MODELO_INICIAL.forca,
        opcoes=tuple(eq.FORCAS),
        secao="Unidades",
    ),
    Campo(
        "trechos",
        "Peça",
        "Os trechos retos da peça. Servem para o desenho e para achar as seções cortadas: as "
        "reações não dependem deles.",
        _linhas("trechos"),
        secao="Peça",
        colunas=(
            Coluna("x1", "x inicial", _X),
            Coluna("y1", "y inicial", _Y),
            Coluna("x2", "x final", _X),
            Coluna("y2", "y final", _Y),
        ),
    ),
    Campo(
        "apoios",
        "Apoios",
        "O que segura a peça. Ângulo é para onde o apoio empurra: 90° empurra para cima, 180° "
        "empurra para a esquerda. Cabo e biela usam a outra ponta (x₂, y₂). O apoio distribuído vai "
        "de (x, y) até (x₂, y₂).",
        _linhas("apoios"),
        secao="Apoios",
        colunas=(
            Coluna(
                "nome",
                "Nome",
                "Letra do apoio. Em branco, o programa dá a próxima.",
                "",
                opcional=True,
            ),
            Coluna(
                "tipo",
                "Tipo",
                "Pino segura as duas direções. Rolete uma direção. Apoio simples só empurra. "
                "Apoio distribuído segura ao longo de um trecho. Engaste segura tudo. Guia deixa "
                "correr. Cabo só puxa. Biela puxa e empurra.",
                eq.PINO,
                opcoes=eq.TIPOS_DE_APOIO,
            ),
            Coluna("x", "x", _X),
            Coluna("y", "y", _Y),
            Coluna(
                "angulo",
                "Ângulo",
                "Para onde o apoio empurra, em graus a partir da direita, anti-horário.",
                90.0,
                "°",
            ),
            Coluna(
                "x2",
                "x₂",
                "Outra ponta do cabo, da biela ou do apoio distribuído.",
                None,
                opcional=True,
            ),
            Coluna(
                "y2",
                "y₂",
                "Outra ponta do cabo, da biela ou do apoio distribuído.",
                None,
                opcional=True,
            ),
            Coluna(
                "mu",
                "μ",
                "Coeficiente de atrito. Aço com aço seco: 0,15 a 0,5. No apoio distribuído que só "
                "encosta, sem μ ele não segura nada ao longo do trecho.",
                None,
                minimo=0.0,
                opcional=True,
            ),
            Coluna(
                "fixacao",
                "Fixação",
                "No apoio distribuído. Só encosta: empurra, e a peça pode descolar e tombar. Preso "
                "ao longo: soldado ou parafusado, empurra, puxa e segura ao longo do trecho.",
                None,
                opcoes=eq.FIXACOES,
                opcional=True,
            ),
        ),
    ),
    Campo(
        "cargas",
        "Cargas",
        "Força: valor e ângulo, com −90° para baixo. Momento: anti-horário positivo. Distribuída: "
        "valor por comprimento, de (x, y) até (x₂, y₂). Peso: massa em kg.",
        _linhas("cargas"),
        secao="Cargas",
        colunas=(
            Coluna(
                "nome",
                "Nome",
                "Nome da carga. Em branco, o programa dá o próximo.",
                "",
                opcional=True,
            ),
            Coluna(
                "tipo",
                "Tipo",
                "Peso pede a massa em kg, e o programa multiplica por g.",
                eq.FORCA,
                opcoes=eq.TIPOS_DE_CARGA,
            ),
            Coluna("x", "x", _X),
            Coluna("y", "y", _Y),
            Coluna("valor", "Valor", "Força, momento, carga por comprimento ou massa.", 1.0),
            Coluna(
                "angulo",
                "Ângulo",
                "Para onde a força aponta, em graus. −90° é para baixo.",
                -90.0,
                "°",
            ),
            Coluna("x2", "x₂", "Onde a carga distribuída termina.", None, opcional=True),
            Coluna("y2", "y₂", "Onde a carga distribuída termina.", None, opcional=True),
            Coluna(
                "valor2",
                "Valor final",
                "Valor no fim da carga distribuída. Em branco, é igual ao inicial.",
                None,
                opcional=True,
            ),
        ),
    ),
    Campo(
        "cortes",
        "Seções de corte",
        "Pontos da peça onde você quer N, V e M. Ângulo é a direção da barra nesse ponto: 0° na "
        "barra deitada, 90° na barra em pé.",
        _linhas("cortes"),
        secao="Seções de corte",
        colunas=(
            Coluna(
                "nome",
                "Nome",
                "Nome da seção. Em branco, o programa dá o próximo.",
                "",
                opcional=True,
            ),
            Coluna("x", "x", _X),
            Coluna("y", "y", _Y),
            Coluna("angulo", "Ângulo", "Direção da barra no ponto do corte.", 0.0, "°"),
        ),
    ),
)

CASO_EQUILIBRIO = Caso(
    "equilibrio_peca",
    "Equilíbrio de uma peça",
    GRUPO,
    "Desenhe a peça, ponha apoios e cargas e veja as reações na hora.",
    "Peça, suporte, alavanca ou máquina com qualquer número de apoios: pino, rolete, cabo, biela, "
    "engaste, atrito. Diz se a peça para, se descola e se a estática basta.",
    CAMPOS_EQUILIBRIO,
    calcular_equilibrio,
    r"\sum F_x=0,\quad \sum F_y=0,\quad \sum M=0",
)
