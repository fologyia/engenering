"""A ponte entre o Montador térmico e o de fluidos: a corrente vira linha, e a linha devolve a perda.

Na página que liga os dois, os blocos térmicos (estado, bomba, troca de calor) e os de fluidos (trecho
de tubo, perdas, NPSH, velocidade) ficam na mesma prancheta. Dois blocos fazem a passagem:

- **Linha da corrente** lê o estado térmico e monta a linha de fluidos: ρ e μ na pressão e na
  entalpia da corrente, a pressão de vapor na temperatura dela, e a vazão em volume, ṁ/ρ. Daí em
  diante valem os blocos de fluidos como sempre.
- **Corrente depois da linha** devolve ao térmico o que o tubo fez: a pressão cai ρ·g·(h_L + Δz), e
  a entalpia cai g·Δz, que é a energia que virou altura. O atrito não muda a entalpia: ele troca
  pressão por temperatura dentro do próprio fluido.

As duas bases são o SI, e por isso nada se converte no caminho.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from core import montador_blocos as mb
from core import montador_fluidos as mfl
from core import montador_grandezas as g
from core import montador_propriedades as mp
from core import montador_termico as mte
from core.montador_blocos import CORRENTE, LINHA, PROCESSOS, Bloco, Contexto, ErroDeBloco, Porta
from core.montador_secoes import Validade


def _corrente(c: Contexto, porta: str = "entrada") -> mte.Corrente:
    corrente = c.ligados.get(porta)
    if not isinstance(corrente, mte.Corrente) or corrente.fluido < 0:
        raise ErroDeBloco(
            "Ligue aqui uma corrente: o estado do fluido ou a saída de um equipamento."
        )
    return corrente


def _linha_da_corrente(c: Contexto) -> dict[str, Any]:
    corrente = _corrente(c)
    fluido = corrente.fluido
    rho = mp.de(fluido, mp.RHO, mp.PH, corrente.p, corrente.h)
    mu = mp.de(fluido, mp.MU, mp.PH, corrente.p, corrente.h)
    temperatura = corrente.temperatura()
    validades = list(corrente.validade)
    if corrente.do_fluido.saturacao:
        pv = mp.de(fluido, mp.PV, mp.TX, temperatura, 0)
        titulo = corrente.titulo()
        validades.append(
            Validade(
                titulo * (titulo - 1),
                "A corrente chega com líquido e vapor misturados: a linha de fluidos é de uma fase "
                "só, e a perda de carga aqui não vale.",
                restringe=False,
            )
        )
    else:
        pv = c.letra(g.P_VAPOR)
    c.hipoteses.append(
        "Linha a partir da corrente: ρ e μ na pressão e na entalpia do ponto onde a linha começa, "
        "e a vazão em volume é ṁ/ρ. A linha continua incompressível e na mesma temperatura."
    )
    linha = mfl.Linha(
        rho,
        mu,
        pv,
        c.letra(g.GRAVIDADE),
        vazao=corrente.m / rho,
        validade=tuple(validades),
        temperatura=temperatura,
        pressao=corrente.p,
    )
    return {"saida": linha}


def _corrente_depois_da_linha(c: Contexto) -> dict[str, Any]:
    corrente = _corrente(c)
    linha = c.ligados.get("linha")
    if not isinstance(linha, mfl.Linha):
        raise ErroDeBloco("Ligue aqui a linha, depois dos trechos de tubo e das perdas.")
    if not linha.trechos:
        raise ErroDeBloco("Ponha um trecho de tubo na linha: sem ele não há perda para descontar.")
    desnivel = c.letra(g.DZ_LINHA)
    p2 = corrente.p - linha.rho * linha.gravidade * (linha.perda + desnivel)
    h2 = corrente.h - linha.gravidade * desnivel
    c.hipoteses.append(
        "Tubo adiabático entre os dois pontos: a pressão cai ρ·g·(h_L + Δz), e a entalpia cai g·Δz. "
        "O atrito não muda a entalpia."
    )
    validades = (
        *corrente.validade,
        *linha.validade,
        Validade(p2, "A perda de carga e o desnível passaram da pressão do começo da linha."),
    )
    return {"saida": replace(corrente, p=p2, h=h2, validade=validades)}


BLOCOS_DA_PONTE: tuple[Bloco, ...] = (
    Bloco(
        "linha_da_corrente",
        "Linha da corrente",
        mb.GRUPO_PONTE,
        "Do térmico para os fluidos: a corrente vira a linha, com ρ, μ e a vazão do estado dela.",
        "ρ(p, h) · μ(p, h) · Q = ṁ/ρ",
        (Porta("entrada", "Corrente", CORRENTE),),
        (Porta("saida", "Linha", LINHA),),
        _linha_da_corrente,
        dominio=PROCESSOS,
    ),
    Bloco(
        "corrente_depois_da_linha",
        "Corrente depois da linha",
        mb.GRUPO_PONTE,
        "Dos fluidos para o térmico: a corrente sai do tubo com a pressão descontada da perda.",
        "p₂ = p₁ − ρ·g·(h_L + Δz)",
        (Porta("entrada", "Corrente", CORRENTE), Porta("linha", "Linha", LINHA)),
        (Porta("saida", "Corrente", CORRENTE),),
        _corrente_depois_da_linha,
        numerar=True,
        dominio=PROCESSOS,
    ),
)

mb.registrar(BLOCOS_DA_PONTE)

__all__ = ["BLOCOS_DA_PONTE"]
