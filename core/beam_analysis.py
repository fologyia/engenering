"""Análise de vigas e eixos: cortante, momento, linha elástica e torção.

O módulo resolve uma barra reta (viga ou eixo) por rigidez direta com
elementos de Euler-Bernoulli e recupera os esforços internos de forma
**analítica** dentro de cada elemento. Como os nós são colocados em toda
descontinuidade (apoio, carga pontual, momento, início/fim de carga
distribuída), a carga distribuída dentro de um elemento é sempre uma única
função linear — logo ``V(x)`` é quadrática, ``M(x)`` é cúbica e a linha
elástica ``v(x)`` é um polinômio de quinto grau, todos exatos.

Com a segunda ordem ligada (``K = K_e + K_g``), a linha elástica continua
vindo da parcela elástica ``K_e·u`` — a única que, integrada, reproduz os
deslocamentos nodais — e os esforços internos vêm do conjunto em equilíbrio
``(K_e + K_g)·u`` mais o momento do esforço normal no braço da flecha,
``N̄·(v − v_i)``, com ``V = dM/dx = Q + N̄·θ``. É o que mantém ``M`` e ``V``
contínuos entre elementos e a menos de 0,02 % da solução fechada de
coluna-viga (ver ``docs/vigas_e_eixos.md``).

Convenções (todas em torno do eixo de flexão informado na seção):

* ``x`` cresce da esquerda para a direita; ``y`` é positivo para cima.
* Forças transversais e cargas distribuídas são **positivas para cima**.
* Momentos concentrados são positivos no sentido anti-horário (+z).
* Força axial é positiva em +x; o esforço normal interno ``N`` é positivo
  quando traciona a seção.
* ``V`` segue a convenção clássica (positivo quando gira o trecho à
  esquerda no sentido horário) e ``M`` é positivo quando comprime a fibra
  superior ("barriga para baixo").
* A flecha ``v`` é positiva para cima, coerente com ``E I v'' = M``.

Unidades internas: N, mm, MPa, N·mm.
"""

from __future__ import annotations

from collections.abc import Sequence

from core.beam_diagrams import (
    _EXTREMOS,
    _amostras,
    _calcular_extremos,
    _extremo_por_modulo,
    _grau_hiperestaticidade,
    _montar_ponto,
    _ponto_diagrama,
    _raizes_polinomio,
    amplitudes_de_fadiga,
    conferir_equilibrio,
    estado_no_ponto_critico,
    estado_plano_da_secao,
    ponto_em,
    resumo_reacoes,
    secoes_notaveis,
    tabela_diagramas,
    verificar_flecha,
)
from core.beam_envelope import (
    _GRANDEZAS_ENVOLTORIA,
    CombinacaoCarga,
    PontoEnvoltoria,
    ResultadoEnvoltoria,
    _analisar_envoltoria,
    _escalar,
    casos_declarados,
    resumo_governantes,
    tabela_envoltoria,
    viga_da_combinacao,
)
from core.beam_model import (
    CASO_PADRAO,
    DESCRICAO_APOIO,
    DIVISOES_SEGUNDA_ORDEM,
    ELEMENTOS_MAXIMOS,
    FRACAO_FUSAO_DE_NOS,
    GRAVIDADE_M_S2,
    PONTOS_TOTAIS_ALVO,
    TIPOS_APOIO,
    TOLERANCIA_POSICAO_MM,
    Apoio,
    CargaAxial,
    CargaAxialDistribuida,
    CargaDistribuida,
    CargaPontual,
    Extremo,
    MomentoConcentrado,
    PontoDiagrama,
    Reacao,
    ResultadoViga,
    Rotula,
    Torque,
    Viga,
)
from core.beam_numerics import (
    _ajustar_modelo_a_malha,
    _carga_no_elemento,
    _cargas_equivalentes_axial,
    _cargas_equivalentes_flexao,
    _distribuida_ajustada,
    _Elemento,
    _escala_de_jacobi,
    _fator_carga_critica,
    _inserir,
    _Malha,
    _mesmo_ponto,
    _normal_medio,
    _posicoes_nodais,
    _resolver_sistema,
    _rigidez_flexao,
    _rigidez_geometrica,
    _tolerancia_de_posicao,
    _validar_posicao,
)
from core.beam_sections import (
    _FAMILIAS_ABERTAS,
    MaterialViga,
    SecaoViga,
    _area_de_cisalhamento_em_y,
    _distancias_monossimetricas,
    _excentricidade_do_centro_de_cisalhamento,
    _familia_do_perfil,
    _familia_normalizada,
    _finito,
    _modulo_de_torcao_do_perfil,
    _nao_negativo,
    _positivo,
    secao_circular_macica,
    secao_de_perfil_catalogo,
    secao_i_simetrica,
    secao_retangular,
    secao_tubo_circular,
    secao_tubo_retangular,
)
from core.beam_solver import _avisos_de_material, analisar_viga
from core.load_to_stress import EstadoPlanoCalculado
from core.section_stress import EsforcosSecao, tensoes_combinadas
from core.steel_sections import centro_de_cisalhamento_do_perfil

__all__ = [
    "CASO_PADRAO",
    "DESCRICAO_APOIO",
    "DIVISOES_SEGUNDA_ORDEM",
    "ELEMENTOS_MAXIMOS",
    "FRACAO_FUSAO_DE_NOS",
    "GRAVIDADE_M_S2",
    "PONTOS_TOTAIS_ALVO",
    "TIPOS_APOIO",
    "TOLERANCIA_POSICAO_MM",
    "Apoio",
    "CargaAxial",
    "CargaAxialDistribuida",
    "CargaDistribuida",
    "CargaPontual",
    "CombinacaoCarga",
    "EsforcosSecao",
    "EstadoPlanoCalculado",
    "Extremo",
    "MaterialViga",
    "MomentoConcentrado",
    "PontoDiagrama",
    "PontoEnvoltoria",
    "Reacao",
    "ResultadoEnvoltoria",
    "ResultadoViga",
    "Rotula",
    "SecaoViga",
    "Torque",
    "Viga",
    "amplitudes_de_fadiga",
    "analisar_envoltoria",
    "analisar_viga",
    "casos_declarados",
    "centro_de_cisalhamento_do_perfil",
    "conferir_equilibrio",
    "estado_no_ponto_critico",
    "estado_plano_da_secao",
    "ponto_em",
    "resumo_governantes",
    "resumo_reacoes",
    "secao_circular_macica",
    "secao_de_perfil_catalogo",
    "secao_i_simetrica",
    "secao_retangular",
    "secao_tubo_circular",
    "secao_tubo_retangular",
    "secoes_notaveis",
    "tabela_diagramas",
    "tabela_envoltoria",
    "tensoes_combinadas",
    "verificar_flecha",
    "viga_da_combinacao",
    "_EXTREMOS",
    "_Elemento",
    "_FAMILIAS_ABERTAS",
    "_GRANDEZAS_ENVOLTORIA",
    "_Malha",
    "_ajustar_modelo_a_malha",
    "_amostras",
    "_area_de_cisalhamento_em_y",
    "_avisos_de_material",
    "_carga_no_elemento",
    "_cargas_equivalentes_axial",
    "_cargas_equivalentes_flexao",
    "_calcular_extremos",
    "_distancias_monossimetricas",
    "_distribuida_ajustada",
    "_escala_de_jacobi",
    "_escalar",
    "_excentricidade_do_centro_de_cisalhamento",
    "_extremo_por_modulo",
    "_familia_do_perfil",
    "_familia_normalizada",
    "_fator_carga_critica",
    "_finito",
    "_grau_hiperestaticidade",
    "_inserir",
    "_mesmo_ponto",
    "_modulo_de_torcao_do_perfil",
    "_montar_ponto",
    "_nao_negativo",
    "_normal_medio",
    "_ponto_diagrama",
    "_posicoes_nodais",
    "_positivo",
    "_raizes_polinomio",
    "_resolver_sistema",
    "_rigidez_flexao",
    "_rigidez_geometrica",
    "_tolerancia_de_posicao",
    "_validar_posicao",
]


def analisar_envoltoria(
    viga: Viga,
    combinacoes: Sequence[CombinacaoCarga],
    *,
    pontos_por_elemento: int = 61,
) -> ResultadoEnvoltoria:
    """Resolve a barra em cada combinação e monta a envoltória.

    O máximo de uma grandeza e o máximo de outra costumam vir de combinações
    diferentes; por isso a envoltória guarda, para cada extremo, **qual**
    combinação o governou — em vez de devolver um único número solto que
    ninguém sabe de onde veio.
    """
    return _analisar_envoltoria(viga, combinacoes, pontos_por_elemento, analisar_viga)
