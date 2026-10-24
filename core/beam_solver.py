"""Montagem e resolução completa de uma viga ou eixo."""

from __future__ import annotations

import math

import numpy as np

from core.beam_diagrams import (
    _amostras,
    _calcular_extremos,
    _grau_hiperestaticidade,
    _ponto_diagrama,
)
from core.beam_model import (
    ELEMENTOS_MAXIMOS,
    PONTOS_TOTAIS_ALVO,
    TOLERANCIA_POSICAO_MM,
    Apoio,
    MaterialViga,
    PontoDiagrama,
    Reacao,
    ResultadoViga,
    Viga,
)
from core.beam_numerics import (
    _ajustar_modelo_a_malha,
    _carga_no_elemento,
    _cargas_equivalentes_axial,
    _cargas_equivalentes_flexao,
    _Elemento,
    _fator_carga_critica,
    _normal_medio,
    _posicoes_nodais,
    _resolver_sistema,
    _rigidez_flexao,
    _rigidez_geometrica,
)


def _avisos_de_material(material: MaterialViga) -> list[str]:
    """Faixas físicas de E, G e Sy: fora delas o erro quase sempre é de unidade.

    São avisos, não erros — madeira, polímeros e ligas especiais existem —,
    mas E em MPa digitado como GPa (mil vezes maior) ou G maior que E/2
    (coeficiente de Poisson negativo) não acontecem em material nenhum.
    """
    avisos: list[str] = []
    e_gpa = material.modulo_elasticidade_MPa / 1_000.0
    g_gpa = material.modulo_cisalhamento_MPa / 1_000.0
    if not 0.5 <= e_gpa <= 1_000.0:
        avisos.append(
            f"E = {e_gpa:.4g} GPa está fora da faixa de qualquer material de "
            "engenharia (0,5 a 1 000 GPa). Confira as unidades: o modelo espera E em "
            "GPa (aço ≈ 200)."
        )
    if g_gpa > 0.5 * e_gpa * (1.0 + 1e-9):
        avisos.append(
            f"G = {g_gpa:.4g} GPa é maior que E/2 = {0.5 * e_gpa:.4g} GPa, o que "
            "corresponde a coeficiente de Poisson negativo. Para metais G ≈ E/2,6; "
            "confira as unidades de E e G."
        )
    if (
        material.escoamento_MPa
        and material.escoamento_MPa > 0.05 * material.modulo_elasticidade_MPa
    ):
        avisos.append(
            f"Sy = {material.escoamento_MPa:.4g} MPa corresponde a deformação de "
            f"escoamento acima de 5 % (Sy/E = {material.escoamento_MPa / material.modulo_elasticidade_MPa:.3g}), "
            "que nenhum material estrutural tem. Confira as unidades: Sy em MPa e E em GPa."
        )
    return avisos


def analisar_viga(viga: Viga, *, pontos_por_elemento: int = 61) -> ResultadoViga:
    """Resolve a viga e devolve diagramas, reações, tensões e extremos.

    ``pontos_por_elemento`` é um teto por elemento: em malhas grandes a
    amostragem é reduzida para o total ficar perto de
    :data:`PONTOS_TOTAIS_ALVO`, sem nunca cair abaixo de 3 pontos por
    elemento. Os extremos não dependem disso (as raízes de V, M e θ entram
    sempre); só a densidade do traçado muda.
    """
    if pontos_por_elemento < 3:
        raise ValueError("pontos_por_elemento deve ser pelo menos 3.")

    viga = viga.com_peso_proprio()
    secao, material = viga.secao, viga.material
    avisos: list[str] = _avisos_de_material(material)

    if not viga.apoios:
        raise ValueError("Informe pelo menos um apoio — sem apoio a viga não tem equilíbrio.")

    malha = _posicoes_nodais(viga)
    # Daqui em diante toda posição do modelo coincide exatamente com um nó:
    # o que a fusão de nós aproximou fica visível no resultado, e as buscas
    # por nó abaixo não dependem mais de tolerância.
    viga = _ajustar_modelo_a_malha(viga, malha)
    posicoes = malha.posicoes
    no_de = malha.no_de
    n_nos = len(posicoes)
    if n_nos < 2:
        raise ValueError("A viga precisa de pelo menos dois nós.")
    n_elementos = n_nos - 1
    amostras_por_elemento = max(3, min(pontos_por_elemento, PONTOS_TOTAIS_ALVO // n_elementos))
    if malha.divisoes_pedidas > malha.divisoes:
        avisos.append(
            f"Com {malha.trechos} trechos, a malha ficou limitada a {malha.divisoes} "
            f"divisão(ões) por trecho (máximo de {ELEMENTOS_MAXIMOS} elementos) em vez "
            f"das {malha.divisoes_pedidas} que a segunda ordem pede. O fator de carga "
            "crítica pode sair alguns por cento alto; V, M e a flecha de primeira ordem "
            "não são afetados."
        )

    # -- rótulas -----------------------------------------------------------
    nos_rotula: set[int] = set()
    for rotula in viga.rotulas:
        x = rotula.x_mm
        indice = no_de(x)
        if indice in (0, n_nos - 1):
            raise ValueError(
                f"A rótula em x = {x:.4g} mm coincide com a extremidade da viga. "
                "Numa extremidade a rotação já é livre, a menos que haja engaste — "
                "use um apoio do tipo rolete ou pino."
            )
        nos_rotula.add(indice)

    # -- apoios ------------------------------------------------------------
    apoios_por_no: dict[int, Apoio] = {}
    for apoio in viga.apoios:
        x = apoio.x_mm
        indice = no_de(x)
        if indice in apoios_por_no:
            raise ValueError(f"Há mais de um apoio em x = {x:.4g} mm.")
        if indice in nos_rotula and apoio.restringe_rotacao:
            raise ValueError(
                f"Em x = {x:.4g} mm há uma rótula e um apoio que impede a rotação. "
                "Escolha um dos dois: a rótula libera exatamente o que o engaste trava."
            )
        if indice in nos_rotula and apoio.rigidez_rotacional_Nmm_rad > 0:
            # Na rótula há duas rotações (uma de cada lado); uma mola kr
            # "para o solo" teria de escolher um lado em silêncio, e uma
            # ligação semirrígida (mola entre os dois lados) é outro modelo.
            raise ValueError(
                f"Em x = {x:.4g} mm há uma rótula e um apoio com rigidez rotacional kr. "
                "A rótula desconecta as rotações dos dois lados, então não há um único "
                "giro para a mola reagir. Use kv apenas, ou retire a rótula."
            )
        apoios_por_no[indice] = apoio

    # -- graus de liberdade -------------------------------------------------
    dof_v = list(range(0, 2 * n_nos, 2))
    dof_theta_esq: list[int] = []
    dof_theta_dir: list[int] = []
    proximo = 2 * n_nos
    for indice in range(n_nos):
        base = 2 * indice + 1
        dof_theta_esq.append(base)
        if indice in nos_rotula:
            dof_theta_dir.append(proximo)
            proximo += 1
        else:
            dof_theta_dir.append(base)
    n_dof_flexao = proximo

    # -- elementos ----------------------------------------------------------
    elementos: list[_Elemento] = []
    for indice in range(n_nos - 1):
        x_i, x_j = posicoes[indice], posicoes[indice + 1]
        l = x_j - x_i
        if l <= TOLERANCIA_POSICAO_MM:
            raise ValueError(f"Elemento de comprimento nulo em x = {x_i:.4g} mm.")
        w_i, w_j = _carga_no_elemento(viga.cargas_distribuidas, x_i, x_j)
        a_i, a_j = _carga_no_elemento(viga.cargas_axiais_distribuidas, x_i, x_j)
        elementos.append(
            _Elemento(
                indice=indice,
                no_i=indice,
                no_j=indice + 1,
                x_i=x_i,
                x_j=x_j,
                comprimento=l,
                w_i=w_i,
                w_j=w_j,
                a_i=a_i,
                a_j=a_j,
                dofs_flexao=(
                    dof_v[indice],
                    dof_theta_dir[indice],
                    dof_v[indice + 1],
                    dof_theta_esq[indice + 1],
                ),
                dofs_axial=(indice, indice + 1),
                dofs_torcao=(indice, indice + 1),
            )
        )

    ei = material.modulo_elasticidade_MPa * secao.inercia_mm4
    ea = material.modulo_elasticidade_MPa * secao.area_mm2
    gj = material.modulo_cisalhamento_MPa * secao.constante_torcao_mm4

    # O esforço normal é resolvido primeiro porque a rigidez geométrica da
    # flexão depende dele. Neste modelo o axial não depende da flecha, então
    # uma única passagem basta — não há iteração a fazer.
    # -- sistema axial -------------------------------------------------------
    k_axial = np.zeros((n_nos, n_nos))
    f_axial = np.zeros(n_nos)
    for elemento in elementos:
        dofs = list(elemento.dofs_axial)
        rigidez = ea / elemento.comprimento
        k_axial[np.ix_(dofs, dofs)] += rigidez * np.array([[1.0, -1.0], [-1.0, 1.0]])
        f_axial[dofs] += _cargas_equivalentes_axial(
            elemento.a_i, elemento.a_j, elemento.comprimento
        )
    for axial in viga.cargas_axiais:
        indice = no_de(axial.x_mm)
        f_axial[indice] += axial.fx_N

    restritos_axial = {
        indice for indice, apoio in apoios_por_no.items() if apoio.restringe_horizontal
    }
    if not restritos_axial:
        resultante = float(np.sum(f_axial))
        if abs(resultante) > 1e-6 * max(1.0, float(np.abs(f_axial).max(initial=0.0))):
            raise ValueError(
                "Há carga axial resultante mas nenhum apoio impede o deslocamento "
                "horizontal. Use um apoio do tipo pino, engaste ou trava axial."
            )
        ancora = min(apoios_por_no) if apoios_por_no else 0
        restritos_axial = {ancora}
        tem_axial = any(abs(item.fx_N) > 0 for item in viga.cargas_axiais)
        if tem_axial or viga.cargas_axiais_distribuidas:
            avisos.append(
                f"Nenhum apoio trava o eixo x: o deslocamento axial foi fixado em "
                f"x = {posicoes[ancora]:.4g} mm apenas como referência. Os esforços "
                "normais são autoequilibrados e não dependem dessa escolha."
            )

    deslocamentos_axiais, reacoes_axiais = _resolver_sistema(
        k_axial, f_axial, restritos_axial, "esforço axial"
    )

    # O esforço normal de cada elemento sai já aqui porque a rigidez
    # geométrica da flexão precisa dele antes da montagem.
    for elemento in elementos:
        dofs_axial = list(elemento.dofs_axial)
        u_axial = deslocamentos_axiais[dofs_axial]
        rigidez_axial = ea / elemento.comprimento
        forcas_axiais = rigidez_axial * np.array(
            [u_axial[0] - u_axial[1], u_axial[1] - u_axial[0]]
        ) - _cargas_equivalentes_axial(elemento.a_i, elemento.a_j, elemento.comprimento)
        elemento.esforco_axial_i = float(forcas_axiais[0])
        elemento.u_i = float(u_axial[0])

    # -- sistema de flexão ---------------------------------------------------
    k_flexao = np.zeros((n_dof_flexao, n_dof_flexao))
    k_geometrica = np.zeros((n_dof_flexao, n_dof_flexao))
    f_flexao = np.zeros(n_dof_flexao)
    for elemento in elementos:
        dofs = list(elemento.dofs_flexao)
        k_flexao[np.ix_(dofs, dofs)] += _rigidez_flexao(ei, elemento.comprimento)
        # Esforço normal médio do elemento, já disponível da solução axial.
        normal_medio = _normal_medio(elemento)
        if normal_medio != 0.0:
            k_geometrica[np.ix_(dofs, dofs)] += _rigidez_geometrica(
                normal_medio, elemento.comprimento
            )
        f_flexao[dofs] += _cargas_equivalentes_flexao(
            elemento.w_i, elemento.w_j, elemento.comprimento
        )
    for pontual in viga.cargas_pontuais:
        indice = no_de(pontual.x_mm)
        f_flexao[dof_v[indice]] += pontual.fy_N
    for momento in viga.momentos:
        indice = no_de(momento.x_mm)
        # Num nó com rótula o momento aplicado não tem trecho definido para
        # entrar; recusar é melhor do que escolher um lado silenciosamente.
        if indice in nos_rotula:
            raise ValueError(
                f"Há um momento concentrado exatamente sobre a rótula em "
                f"x = {momento.x_mm:.4g} mm. Desloque um dos dois."
            )
        f_flexao[dof_theta_esq[indice]] += momento.mz_Nmm

    restritos_flexao: set[int] = set()
    for indice, apoio in apoios_por_no.items():
        if apoio.restringe_vertical:
            restritos_flexao.add(dof_v[indice])
        if apoio.restringe_rotacao:
            restritos_flexao.add(dof_theta_esq[indice])
        if apoio.rigidez_vertical_N_mm > 0:
            k_flexao[dof_v[indice], dof_v[indice]] += apoio.rigidez_vertical_N_mm
        if apoio.rigidez_rotacional_Nmm_rad > 0:
            k_flexao[dof_theta_esq[indice], dof_theta_esq[indice]] += (
                apoio.rigidez_rotacional_Nmm_rad
            )

    fator_critico = _fator_carga_critica(k_flexao, k_geometrica, restritos_flexao)
    if viga.considerar_segunda_ordem:
        if fator_critico is not None and fator_critico <= 1.0:
            raise ValueError(
                "A compressão aplicada atinge ou ultrapassa a carga crítica de "
                f"flambagem do modelo (fator de carga crítica = {fator_critico:.3f}). "
                "A análise de segunda ordem não tem solução estável aqui: reduza a "
                "compressão, aumente a inércia ou reduza o comprimento destravado."
            )
        k_flexao_efetiva = k_flexao + k_geometrica
    else:
        k_flexao_efetiva = k_flexao

    deslocamentos_flexao, reacoes_flexao = _resolver_sistema(
        k_flexao_efetiva, f_flexao, restritos_flexao, "flexão (translação vertical / rotação)"
    )

    # -- sistema de torção ---------------------------------------------------
    tem_torque = any(abs(t.t_Nmm) > 0 for t in viga.torques)
    if gj <= 0 and tem_torque:
        raise ValueError(
            "A seção informada tem rigidez à torção nula (G·J = 0); não é possível "
            "analisar torques."
        )
    if tem_torque and secao.modulo_torcao_mm3 <= 0:
        raise ValueError(
            "Há torque aplicado, mas a seção não tem módulo de torção Wt. Sem ele "
            "a tensão de torção sairia zero sem aviso — informe Wt na seção."
        )
    k_torcao = np.zeros((n_nos, n_nos))
    f_torcao = np.zeros(n_nos)
    if gj > 0:
        for elemento in elementos:
            dofs = list(elemento.dofs_torcao)
            rigidez = gj / elemento.comprimento
            k_torcao[np.ix_(dofs, dofs)] += rigidez * np.array([[1.0, -1.0], [-1.0, 1.0]])
    for torque in viga.torques:
        indice = no_de(torque.x_mm)
        f_torcao[indice] += torque.t_Nmm

    restritos_torcao = {indice for indice, apoio in apoios_por_no.items() if apoio.restringe_torcao}
    if gj <= 0:
        deslocamentos_torcao = np.zeros(n_nos)
        reacoes_torcao = np.zeros(n_nos)
    else:
        if not restritos_torcao:
            resultante = float(np.sum(f_torcao))
            if abs(resultante) > 1e-6 * max(1.0, float(np.abs(f_torcao).max(initial=0.0))):
                raise ValueError(
                    "Há torque resultante mas nenhum apoio impede o giro em torno do "
                    "eixo da barra. Use um apoio do tipo pino ou engaste."
                )
            restritos_torcao = {min(apoios_por_no) if apoios_por_no else 0}
            if tem_torque:
                avisos.append(
                    "Nenhum apoio trava a torção: o giro foi fixado no primeiro apoio "
                    "apenas como referência."
                )
        deslocamentos_torcao, reacoes_torcao = _resolver_sistema(
            k_torcao, f_torcao, restritos_torcao, "torção"
        )

    # -- esforços de extremidade por elemento --------------------------------
    for elemento in elementos:
        dofs = list(elemento.dofs_flexao)
        u_local = deslocamentos_flexao[dofs]
        elemento.esforcos_flexao = _rigidez_flexao(
            ei, elemento.comprimento
        ) @ u_local - _cargas_equivalentes_flexao(elemento.w_i, elemento.w_j, elemento.comprimento)
        elemento.esforcos_equilibrio = elemento.esforcos_flexao
        if viga.considerar_segunda_ordem:
            # O mesmo N médio que entrou em K_g: só assim os esforços de
            # extremidade fecham o equilíbrio nodal na configuração deformada
            # e M(x) sai contínuo de um elemento para o outro.
            elemento.normal_geometrico = _normal_medio(elemento)
            elemento.esforcos_equilibrio = elemento.esforcos_flexao + (
                _rigidez_geometrica(elemento.normal_geometrico, elemento.comprimento) @ u_local
            )
        elemento.v_i = float(u_local[0])
        elemento.theta_i = float(u_local[1])

        if gj > 0:
            dofs_torcao = list(elemento.dofs_torcao)
            u_torcao = deslocamentos_torcao[dofs_torcao]
            rigidez_torcao = gj / elemento.comprimento
            elemento.esforco_torcao_i = float(rigidez_torcao * (u_torcao[1] - u_torcao[0]))
            elemento.phi_i = float(u_torcao[0])

    # -- amostragem dos diagramas -------------------------------------------
    pontos: list[PontoDiagrama] = []
    for elemento in elementos:
        for x_local in _amostras(elemento, amostras_por_elemento, ei):
            pontos.append(_ponto_diagrama(elemento, x_local, viga, ei, ea, gj))
    pontos.sort(key=lambda ponto: ponto.x_mm)

    # -- reações --------------------------------------------------------------
    reacoes: list[Reacao] = []
    for indice in sorted(apoios_por_no):
        apoio = apoios_por_no[indice]
        fy = float(reacoes_flexao[dof_v[indice]]) if apoio.restringe_vertical else 0.0
        if apoio.rigidez_vertical_N_mm > 0:
            # A mola reage contra o deslocamento: F = -k u.
            fy -= float(apoio.rigidez_vertical_N_mm * deslocamentos_flexao[dof_v[indice]])
        mz = 0.0
        if apoio.restringe_rotacao:
            # Um nó com rótula nunca chega aqui: apoio que trava rotação
            # sobre rótula é recusado acima, então há um único grau.
            mz = float(reacoes_flexao[dof_theta_esq[indice]])
        if apoio.rigidez_rotacional_Nmm_rad > 0:
            mz -= float(
                apoio.rigidez_rotacional_Nmm_rad * deslocamentos_flexao[dof_theta_esq[indice]]
            )
        fx = float(reacoes_axiais[indice]) if apoio.restringe_horizontal else 0.0
        mt = float(reacoes_torcao[indice]) if apoio.restringe_torcao and gj > 0 else 0.0
        reacoes.append(
            Reacao(
                x_mm=posicoes[indice],
                tipo=apoio.tipo,
                rotulo=apoio.rotulo
                or f"{apoio.tipo.capitalize()} em x = {posicoes[indice] / 1000:.3g} m",
                fy_N=fy,
                fx_N=fx,
                mz_Nmm=mz,
                mt_Nmm=mt,
            )
        )

    if fator_critico is not None and not viga.considerar_segunda_ordem:
        if fator_critico <= 1.0:
            avisos.append(
                "A compressão aplicada ultrapassa a carga crítica de flambagem "
                f"elástica deste modelo (fator de carga crítica = {fator_critico:.3f}): "
                "a barra flamba antes de chegar a essa carga, e os diagramas de "
                "primeira ordem abaixo não representam a resposta real. Reduza a "
                "compressão, aumente a inércia ou reduza o comprimento destravado."
            )
        elif fator_critico < 10.0:
            avisos.append(
                f"A compressão atinge 1/{fator_critico:.1f} da carga crítica de "
                "flambagem elástica deste modelo. Com essa ordem de grandeza, a "
                "flecha real é maior que a calculada: ligue a análise de segunda "
                "ordem para incluir o efeito P–Δ."
            )

    # O modelo é plano: a carga crítica acima é a da flambagem no plano da
    # flexão. Uma barra comprimida flamba em torno do eixo de MENOR inércia,
    # e um perfil I fletido em x tem Iy dez vezes menor que Ix. Com o mesmo
    # comprimento de flambagem nos dois planos, a carga crítica escala com a
    # inércia — é a estimativa que se faz à mão, e é o que se reporta aqui.
    fator_transversal: float | None = None
    if (
        fator_critico is not None
        and secao.inercia_transversal_mm4 > 0
        and secao.inercia_transversal_mm4 < secao.inercia_mm4
    ):
        fator_transversal = fator_critico * secao.inercia_transversal_mm4 / secao.inercia_mm4
        # Mesmo limiar do aviso no plano: com folga de dez vezes não há o
        # que avisar, e o número continua disponível no resultado.
        if fator_transversal < 10.0:
            avisos.append(
                f"Fora do plano da flexão a seção tem inércia menor (I⊥ = "
                f"{secao.inercia_transversal_mm4:.4g} mm⁴ contra I = {secao.inercia_mm4:.4g} mm⁴): "
                "se a barra não tiver travamento lateral, o fator de carga crítica "
                f"cai de {fator_critico:.2f} para cerca de {fator_transversal:.2f} "
                "(mesmo comprimento de flambagem nos dois planos). "
                + (
                    "A compressão já supera essa carga crítica transversal."
                    if fator_transversal <= 1.0
                    else "Confira a flambagem em torno do eixo fraco em Flambagem de colunas."
                )
            )

    extremos = _calcular_extremos(pontos)
    grau = _grau_hiperestaticidade(apoios_por_no.values(), len(nos_rotula))

    # Seção monossimétrica carregada fora do centro de cisalhamento (U/C em
    # x, T em y): o modelo plano não vê a torção, mas ela existe e vale
    # ≈ V·e nos apoios que travam o giro. Reportar a ordem de grandeza é o
    # que separa "não calculei" de "não existe".
    torque_excentrico = abs(extremos["cortante"].valor) * secao.excentricidade_cisalhamento_mm
    if torque_excentrico > 0:
        texto = (
            f"Seção monossimétrica ({secao.nome}): o centro de cisalhamento fica a "
            f"e = {secao.excentricidade_cisalhamento_mm:.1f} mm do centroide e o modelo "
            "plano aplica as cargas transversais no centroide. A barra torce com "
            f"T ≈ V·e ≈ {abs(extremos['cortante'].valor) / 1e3:.3g} kN × "
            f"{secao.excentricidade_cisalhamento_mm:.1f} mm ≈ {torque_excentrico / 1e6:.3g} kN·m "
            "(torção travada nos apoios)"
        )
        if secao.modulo_torcao_mm3 > 0:
            texto += (
                f"; τ_T ≈ T/Wt ≈ {torque_excentrico / secao.modulo_torcao_mm3:.3g} MPa por "
                "Saint-Venant, e em perfis abertos a parcela de empenamento pode superar essa"
            )
        texto += (
            ". Trave a torção nos apoios e nas ligações, aplique a carga pelo centro de "
            "cisalhamento ou some esse torque ao modelo (comando `torque`)."
        )
        avisos.append(texto)

    fator_seguranca = None
    if material.escoamento_MPa:
        maximo = extremos["von_mises"].valor
        fator_seguranca = math.inf if maximo <= 0 else material.escoamento_MPa / maximo

    return ResultadoViga(
        viga=viga,
        pontos=tuple(pontos),
        reacoes=tuple(reacoes),
        extremos=extremos,
        avisos=tuple(avisos),
        grau_hiperestaticidade=grau,
        fator_seguranca_escoamento=fator_seguranca,
        fator_carga_critica=fator_critico,
        segunda_ordem=viga.considerar_segunda_ordem,
        numero_elementos=n_elementos,
        fator_carga_critica_transversal=fator_transversal,
    )
