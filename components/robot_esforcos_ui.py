"""Seleção, prévia e aplicação de esforços do Robot nos módulos de detalhamento."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pandas as pd
import streamlit as st

from core import aberturas_alma as ab
from core import esforcos_modelo as em
from core import load_combinations as comb
from core import plano_de_cargas as pc
from core import robot
from core import robot_integracao as ri
from core.project_store import obter_projeto_ativo


def _projeto() -> dict[str, Any] | None:
    projeto = obter_projeto_ativo()
    return projeto if projeto and robot.ativo(projeto) else None


def _estado(chave: str) -> str:
    return st.selectbox("Estado-limite do Robot", comb.COMBINACOES_ULTIMAS, key=f"{chave}_estado")


def _barra(
    modelo: Mapping[str, Any], chave: str, opcoes: Sequence[str] | None = None
) -> str | None:
    fichas = modelo["barras"]
    return st.selectbox(
        "Barra no Robot",
        list(fichas) if opcoes is None else opcoes,
        format_func=lambda k: (
            f"{k} · {fichas[k]['secao']} · nós {'–'.join(map(str, fichas[k]['nos']))}"
        ),
        key=f"{chave}_barra",
        index=None,
    )


def _posicao(
    modelo: Mapping[str, Any],
    dados: em.EsforcosDoModelo,
    barra: str,
    chave: str,
    *,
    pontas: bool,
) -> tuple[str, str] | None:
    n1, n2 = modelo["barras"][barra]["nos"]
    if pontas:
        ponta = st.selectbox(
            "Extremidade da barra",
            ["0", "1"],
            key=f"{chave}_ponta",
            format_func=lambda x: f"Nó {n1 if x == '0' else n2} · x/L = {x}",
        )
    else:
        p1, p2 = (modelo["nos"][str(n)] for n in (n1, n2))
        comprimento = math.dist(p1, p2)
        no = st.selectbox("Nó de referência para a altura", [n1, n2], key=f"{chave}_referencia")
        altura = st.number_input(
            "Distância do nó ao corte (m)",
            min_value=0.0,
            max_value=comprimento,
            value=0.0,
            step=0.1,
            format="%.6f",
            key=f"{chave}_altura_{barra}",
        )
        x = altura / comprimento
        ponta = robot._posicao(
            x if no == n1 else 1 - x, robot.POSICOES[0], robot.Unidades(), comprimento
        )
    lados = sorted(
        {
            p.fim
            for caso in dados.casos.values()
            for p in caso.membros.get(barra, ())
            if p.elemento == ponta
        }
    )
    if not lados:
        st.info(f"Inclua x/L = {ponta} da barra {barra} na próxima exportação.")
        return None
    lado = (
        lados[0]
        if len(lados) == 1
        else st.selectbox(
            "Lado do corte",
            lados,
            format_func=lambda a: a or "Ponto único",
            key=f"{chave}_lado",
            index=None,
        )
    )
    return (ponta, lado) if lado is not None else None


def _mostrar(linhas: Sequence[ri.Solicitacao]) -> None:
    st.dataframe(
        pd.DataFrame(
            [[r.combinacao, r.posicao, *r.vetor, r.b2] for r in linhas],
            columns=["Combinação", "Posição", *ri.COMPONENTES, "B₂"],
        ),
        hide_index=True,
    )


def _salvar_origem(
    chave: str,
    projeto: Mapping[str, Any],
    origem: Mapping[str, Any],
    valores: Any,
) -> None:
    st.session_state[f"{chave}_fonte_aplicada"] = (projeto["id"], dict(origem), valores)


def registro(
    chave: str,
    item: Mapping[str, Any],
    valores: Any,
) -> dict[str, Any]:
    salvo = st.session_state.get(f"{chave}_fonte_aplicada")
    if salvo is None:
        return dict(item)
    projeto = obter_projeto_ativo()
    if projeto is None or salvo[0] != projeto["id"]:
        return dict(item)
    return ri.registrar(item, {**salvo[1], "editado": salvo[2] != valores})


def _eixos(cfg: em.ConfiguracaoDoMembro) -> tuple[int, int]:
    if cfg.eixo_forte not in (em.EIXO_M1, em.EIXO_M2):
        raise robot.ImportacaoRobotInvalida("Confirme o eixo forte da barra em Esforços do modelo.")
    return (2, 3) if cfg.eixo_forte == em.EIXO_M1 else (1, 4)


def ligacao(chave: str, campos: Mapping[str, str]) -> None:
    """Aplica os componentes que a tipologia consome às chaves de seus widgets."""
    projeto = _projeto()
    if not projeto:
        return
    modelo = robot.modelo_do_projeto(projeto)
    dados = robot.dados_do_modelo(modelo)
    with st.expander("Trazer do Robot"):
        barra = _barra(modelo, chave)
        if barra is None:
            return
        estado = _estado(chave)
        posicao = _posicao(modelo, dados, barra, chave, pontas=True)
        if posicao is None:
            return
        try:
            indices = _eixos(dados.membros[barra])
            solicitacoes = ri.selecionar(
                modelo, dados, pc.plano_do_projeto(projeto), barra, *posicao, estado
            )
        except robot.ImportacaoRobotInvalida as erro:
            st.warning(str(erro))
            return
        por_nome = {s.combinacao: s for s in solicitacoes}
        nome = st.selectbox("Combinação a aplicar", list(por_nome), key=f"{chave}_comb", index=None)
        if nome is None:
            return
        escolha = por_nome[nome]
        iv, im = indices
        usados = {"n": escolha.vetor[0], "v": abs(escolha.vetor[iv]), "m": abs(escolha.vetor[im])}
        valores = {campo: usados[tipo] for campo, tipo in campos.items()}
        _mostrar([escolha])
        st.caption(
            "Componentes utilizadas desta barra: "
            + ", ".join(
                {"n": "axial", "v": "cortante no plano da alma", "m": "momento no eixo forte"}[k]
                for k in campos.values()
            )
            + ". Confira as demais solicitações aplicáveis à ligação."
        )
        if "m" in campos.values() and usados["m"] < 0.1:
            st.warning(
                "Selecione uma combinação com momento de pelo menos 0,1 kN·m para esta tipologia."
            )
            return
        origem = ri.fonte(projeto, barra=barra, linhas=[escolha])

        def aplicar() -> None:
            st.session_state.update(valores)
            _salvar_origem(chave, projeto, origem, valores)

        st.button("Aplicar esforços do Robot", key=f"{chave}_aplicar", on_click=aplicar)


def emenda(chave: str, aplicar_casos: Callable[[list[dict[str, Any]], list[str]], None]) -> None:
    projeto = _projeto()
    if not projeto:
        return
    modelo = robot.modelo_do_projeto(projeto)
    dados = robot.dados_do_modelo(modelo)
    with st.expander("Trazer do Robot", expanded=True):
        barra = _barra(modelo, chave)
        if barra is None:
            return
        estado = _estado(chave)
        posicao = _posicao(modelo, dados, barra, chave, pontas=False)
        if posicao is None:
            return
        try:
            iv, im = _eixos(dados.membros[barra])
            solicitacoes = ri.selecionar(
                modelo, dados, pc.plano_do_projeto(projeto), barra, *posicao, estado
            )
        except robot.ImportacaoRobotInvalida as erro:
            st.warning(str(erro))
            return
        linhas = [
            {
                "Caso": s.combinacao,
                "N (kN)": -s.vetor[0],
                "M_x (kN·m)": s.vetor[im],
                "V (kN)": s.vetor[iv],
                "M_y (kN·m)": s.vetor[7 - im],
            }
            for s in solicitacoes
        ]
        _mostrar(solicitacoes)
        origem = ri.fonte(projeto, barra=barra, linhas=solicitacoes)
        if st.button("Aplicar combinações do Robot", key=f"{chave}_aplicar"):
            aplicar_casos(
                linhas, [f"Robot · barra {barra} · {solicitacoes[0].posicao} · {estado}."]
            )
            _salvar_origem(chave, projeto, origem, linhas)
            st.rerun()


def placa(chave: str, aplicar_casos: Callable[[str, list[dict[str, Any]]], None]) -> None:
    projeto = _projeto()
    if not projeto:
        return
    modelo = robot.modelo_do_projeto(projeto)
    dados = robot.dados_do_modelo(modelo)
    with st.expander("Trazer do Robot"):
        opcoes = [b for b, cfg in dados.membros.items() if cfg.tipo == "Pilar"]
        if not opcoes:
            st.info("Classifique as barras de pilar em Esforços do modelo.")
            return
        barra = _barra(modelo, chave, opcoes)
        if barra is None:
            return
        estado = _estado(chave)
        cfg = dados.membros[barra]
        nos = modelo["barras"][barra]["nos"]
        p1, p2 = (modelo["nos"][str(n)] for n in nos)
        if abs(p1[2] - p2[2]) < 1e-9 or math.dist(p1[:2], p2[:2]) > 1e-7:
            st.info("A transferência para a placa horizontal exige um pilar vertical.")
            return
        ponta = "0" if p1[2] < p2[2] else "1"
        no = nos[int(ponta)]
        exclusividade = sum(no in b["nos"] for b in modelo["barras"].values()) == 1
        tem_reacao = any(
            p[0] == no
            for c in modelo.get("reacoes", {}).get("casos", {}).values()
            for p in c["nos"]
        )
        fonte_reacao = (
            exclusividade
            and tem_reacao
            and st.checkbox(
                f"Usar a reação do nó {no}. Confirmo que a reação corresponde só à chapa deste pilar.",
                key=f"{chave}_usar_no",
            )
        )
        plano = pc.plano_do_projeto(projeto)
        try:
            _eixos(cfg)
            solicitacoes = ri.selecionar(modelo, dados, plano, barra, ponta, "", estado)
            if fonte_reacao:
                angulo = st.number_input(
                    "Ângulo do X global até o x da placa (°)", key=f"{chave}_angulo"
                )
                reacoes = ri.reacoes_combinadas(modelo, plano, no, estado)
                if reacoes.keys() != {s.combinacao for s in solicitacoes}:
                    raise robot.ImportacaoRobotInvalida(
                        "As reações do nó não cobrem as combinações selecionadas."
                    )
                entradas = [
                    {
                        "nome": s.combinacao,
                        **ri.placa_com_reacao(
                            tuple(v * s.b2 for v in reacoes[s.combinacao]),
                            angulo,
                        ),
                    }
                    for s in solicitacoes
                ]
            else:
                eixo = "z local" if cfg.eixo_forte == em.EIXO_M1 else "y local"
                st.caption(
                    f"A ação é extraída na face inferior do pilar, com +x da placa no +{eixo}."
                )
                entradas = [
                    {"nome": s.combinacao, **ri.placa_com_corte(s.vetor, ponta, cfg.eixo_forte)}
                    for s in solicitacoes
                ]
        except robot.ImportacaoRobotInvalida as erro:
            st.warning(str(erro))
            return
        st.dataframe(pd.DataFrame(entradas), hide_index=True)
        origem = ri.fonte(
            projeto,
            barra=barra,
            no=no,
            linhas=() if fonte_reacao else solicitacoes,
            tipos=("Reações",) if fonte_reacao else ("Esforços",),
        )

        def aplicar() -> None:
            aplicar_casos(cfg.perfil, entradas)
            st.session_state["pb_varias"] = "varias"
            _salvar_origem(chave, projeto, origem, entradas)

        st.button("Aplicar combinações do Robot", key=f"{chave}_aplicar", on_click=aplicar)


def aberturas(
    chave: str,
    entrada: ab.EntradaAberturas,
) -> tuple[ab.EsforcosImportados | None, dict[str, Any], bool]:
    """Usa o mesmo vetor no centro de cada abertura e em ambos os lados de um corte."""
    projeto = _projeto()
    if not projeto or not entrada.aberturas:
        return None, {}, True
    modelo = robot.modelo_do_projeto(projeto)
    dados = robot.dados_do_modelo(modelo)
    with st.expander("Trazer do Robot"):
        barra = _barra(modelo, chave)
        if barra is None:
            return None, {}, True
        estado = _estado(chave)
        n1, n2 = modelo["barras"][barra]["nos"]
        no = st.selectbox("Nó que corresponde ao apoio esquerdo", [n1, n2], key=f"{chave}_no")
        comprimento = 1000 * math.dist(modelo["nos"][str(n1)], modelo["nos"][str(n2)])
        confirma = st.checkbox(
            "A barra representa a viga biapoiada, com as aberturas sem reforço e flexão no plano da alma.",
            key=f"{chave}_confirmar",
        )
        ficha = modelo["barras"][barra]
        st.caption(
            f"Seção no Robot · {ficha['secao']} · {ficha['material']}. "
            "A verificação da abertura usa momento e cortante no plano da alma."
        )
        chave_aplicacao = f"{chave}_aplicacao"
        selecao = (projeto["id"], barra, estado, no, tuple(a.x for a in entrada.aberturas))
        aplicado = st.session_state.get(chave_aplicacao) == selecao
        try:
            if not math.isclose(entrada.L, comprimento, abs_tol=0.5):
                raise robot.ImportacaoRobotInvalida(
                    f"Use L = {comprimento:.2f} mm para a barra {barra}."
                )
            iv, im = _eixos(dados.membros[barra])
            nomes, por_ponto = ri.solicitacoes_da_barra(
                modelo,
                dados,
                pc.plano_do_projeto(projeto),
                barra,
                estado,
            )
            centros = []
            for a in entrada.aberturas:
                x = a.x / comprimento
                posicao = robot._posicao(
                    x if no == n1 else 1 - x, robot.POSICOES[0], robot.Unidades(), comprimento
                )
                rotulo = robot._rotulo_ponto((posicao, ""))
                solicitacoes = [
                    s
                    for p, linhas in por_ponto.items()
                    if p.split(" (")[0] == rotulo
                    for s in linhas
                ]
                if {s.combinacao for s in solicitacoes} != set(nomes) or not solicitacoes:
                    raise robot.ImportacaoRobotInvalida(
                        f"Inclua {a.nome}, {rotulo}, nas combinações exportadas."
                    )
                centros.append(solicitacoes)
        except (robot.ImportacaoRobotInvalida, ValueError) as erro:
            st.warning(str(erro))
            return None, {}, not aplicado
        todos = [s for linhas in por_ponto.values() for s in linhas]
        apoios = [s for s in todos if s.posicao.split(" (")[0] in {"x/L = 0", "x/L = 1"}]
        if not todos or not apoios:
            st.warning("Inclua as posições dos apoios nas combinações exportadas.")
            return None, {}, not aplicado
        for abertura, linhas in zip(entrada.aberturas, centros, strict=True):
            st.caption(abertura.nome)
            _mostrar(linhas)
        if st.button(
            "Aplicar esforços às aberturas", disabled=not confirma, key=f"{chave}_aplicar"
        ):
            st.session_state[chave_aplicacao] = selecao
            aplicado = True
        if not confirma or not aplicado:
            return None, {}, True
        if st.button("Usar a carga informada na viga", key=f"{chave}_voltar"):
            st.session_state.pop(chave_aplicacao, None)
            return None, {}, True
        st.success("A verificação usa os esforços do Robot nas posições mostradas.")
        esforcos = ab.EsforcosImportados(
            tuple(
                tuple(
                    ab.EsforcoNaAbertura(f"{s.combinacao} · {s.posicao}", s.vetor[im], s.vetor[iv])
                    for s in linhas
                )
                for linhas in centros
            ),
            max(abs(s.vetor[im]) for s in todos),
            max(abs(s.vetor[iv]) for s in todos),
            max(abs(s.vetor[iv]) for s in apoios),
        )
        origem = ri.fonte(projeto, barra=barra, linhas=[s for linhas in centros for s in linhas])
        return esforcos, origem, True
