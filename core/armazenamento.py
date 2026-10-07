"""Onde os dados ficam e se sobrevivem a um reinício da hospedagem.

Reúne o que as telas precisam saber para não prometer o que o disco não cumpre:

* o **ambiente** — num computador o disco é do usuário; no Streamlit Community
  Cloud ele é descartado a cada reinício do aplicativo;
* o **espelho remoto** (:mod:`core.espelho_remoto`) — a cópia no GitHub que
  faz os dados sobreviverem a esse reinício, quando configurada;
* a **restauração** na partida, que traz do espelho o que o disco perdeu.

Streamlit não entra aqui: as funções devolvem dados simples, e
``components/armazenamento_ui.py`` decide como mostrá-los.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core import espelho_remoto, material_catalog, project_store, section_catalog
from core.espelho_remoto import EspelhoErro

VARIAVEL_AMBIENTE = "MECANICA_TOOLKIT_AMBIENTE"
AMBIENTE_NUVEM = "nuvem"
AMBIENTE_LOCAL = "local"
# O Streamlit Community Cloud clona o repositório do aplicativo em /mount/src/<repositório>.
_RAIZ_DA_NUVEM = "/mount/src/"
PASTA_CATALOGOS = "catalogos"

NIVEL_LOCAL = "local"
NIVEL_PROTEGIDO = "protegido"
NIVEL_TEMPORARIO = "temporario"
NIVEL_FALHA = "falha"

# Depois de uma restauração que falhou, a próxima tentativa só vem depois deste intervalo: cada
# clique do usuário reexecuta a página, e sem isso um GitHub fora do ar travaria todas elas.
INTERVALO_NOVA_TENTATIVA_S = 30.0


def ambiente(raiz: Path | None = None) -> str:
    """``"nuvem"`` quando o programa roda no Streamlit Cloud; ``"local"`` no mais.

    ``MECANICA_TOOLKIT_AMBIENTE=nuvem|local`` força a resposta (para outra
    hospedagem de disco descartável, ou para um servidor próprio com disco
    permanente).
    """
    forcado = os.environ.get(VARIAVEL_AMBIENTE, "").strip().casefold()
    if forcado in (AMBIENTE_NUVEM, AMBIENTE_LOCAL):
        return forcado
    base = Path(raiz if raiz is not None else project_store.RAIZ_PROJETO).as_posix()
    return AMBIENTE_NUVEM if f"{base}/".startswith(_RAIZ_DA_NUVEM) else AMBIENTE_LOCAL


@dataclass(frozen=True)
class SituacaoArmazenamento:
    ambiente: str
    caminho_banco: Path
    espelho: espelho_remoto.SituacaoEspelho
    nivel: str
    titulo: str
    detalhe: str

    @property
    def disco_descartavel(self) -> bool:
        return self.ambiente == AMBIENTE_NUVEM

    @property
    def exige_atencao(self) -> bool:
        """Os dados corriam risco: sem espelho na nuvem, ou com o espelho falhando."""
        return self.nivel in (NIVEL_TEMPORARIO, NIVEL_FALHA)


def _hora(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def situacao() -> SituacaoArmazenamento:
    local = ambiente()
    espelho = espelho_remoto.situacao()
    banco = project_store.caminho_banco_atual()
    if espelho.configurado or espelho.problema_de_configuracao:
        if espelho.ultimo_erro or espelho.pendentes:
            nivel = NIVEL_FALHA
            titulo = "Sincronização com o GitHub com problema"
            detalhe = espelho.ultimo_erro or "Há gravações aguardando envio."
            if espelho.pendentes:
                detalhe += (
                    f" {espelho.pendentes} gravação(ões) ainda não chegou(aram) ao GitHub: "
                    "baixe a carteira antes de fechar."
                )
        else:
            nivel = NIVEL_PROTEGIDO
            titulo = "Projetos sincronizados com o GitHub"
            detalhe = f"Cada gravação é copiada para {espelho.destino}. " + (
                f"Último envio: {_hora(espelho.ultimo_envio)}."
                if espelho.ultimo_envio
                else "Nenhuma gravação nesta sessão ainda."
            )
    elif local == AMBIENTE_NUVEM:
        nivel = NIVEL_TEMPORARIO
        titulo = "Versão web: dados temporários"
        detalhe = (
            "O disco desta hospedagem é apagado quando o aplicativo reinicia (atualização do "
            "código, inatividade ou manutenção), e os projetos salvos aqui somem junto. Baixe a "
            "carteira (arquivo JSON) ao terminar e restaure-a quando voltar — ou ligue o espelho "
            "no GitHub para os projetos ficarem guardados de verdade."
        )
    else:
        nivel = NIVEL_LOCAL
        titulo = "Dados neste computador"
        detalhe = f"Os projetos ficam em {banco}. Faça cópia dessa pasta de vez em quando."
    return SituacaoArmazenamento(
        ambiente=local,
        caminho_banco=banco,
        espelho=espelho,
        nivel=nivel,
        titulo=titulo,
        detalhe=detalhe,
    )


def texto_de_confirmacao() -> str:
    """Frase curta e verdadeira para depois de salvar, conforme onde o dado foi parar.

    Sem sujeito de propósito ("Salvo…"): serve tanto para "Projeto" quanto para
    "Registro" ou "Alteração", sem concordância para acertar.
    """
    estado = situacao()
    if estado.nivel == NIVEL_PROTEGIDO:
        return "Salvo e copiado para o GitHub."
    if estado.nivel == NIVEL_TEMPORARIO:
        return "Salvo — mas só temporariamente (versão web): baixe a carteira ao terminar."
    if estado.nivel == NIVEL_FALHA:
        motivo = estado.espelho.ultimo_erro[:160] or "veja o aviso na barra lateral"
        return f"Salvo neste servidor, mas a cópia no GitHub falhou: {motivo}"
    return "Salvo no banco local."


def frase_de_persistencia() -> str:
    """O que dizer, nas telas de apresentação, sobre o projeto "ficar salvo"."""
    nivel = situacao().nivel
    if nivel == NIVEL_PROTEGIDO:
        return "Cada gravação é copiada para o GitHub e volta quando o aplicativo reinicia."
    if nivel == NIVEL_TEMPORARIO:
        return "Atenção: na versão web os dados são temporários — baixe a carteira ao terminar."
    if nivel == NIVEL_FALHA:
        return "Atenção: a cópia no GitHub está com problema — veja o aviso na barra lateral."
    return "O banco local mantém dados, registros e revisões entre sessões."


# ---------------------------------------------------------------------------
# Restauração na partida
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultadoRestauracao:
    ok: bool
    projetos: list[str] = field(default_factory=list)
    catalogos: list[str] = field(default_factory=list)
    falhas: dict[str, str] = field(default_factory=dict)
    erro: str = ""


_TRAVA = threading.Lock()
_restaurado = False
_ultima_tentativa = 0.0
_ultimo_reenvio = 0.0


def redefinir() -> None:
    """Esquece que já restaurou. Uso dos testes."""
    global _restaurado, _ultima_tentativa, _ultimo_reenvio
    with _TRAVA:
        _restaurado = False
        _ultima_tentativa = 0.0
        _ultimo_reenvio = 0.0


def restauracao_pendente() -> bool:
    """Há espelho configurado e ainda não se trouxe dele o que faltava neste processo."""
    return espelho_remoto.obter_espelho() is not None and not _restaurado


def _catalogos_do_usuario() -> list[tuple[str, Path]]:
    arquivos = (section_catalog.ARQUIVO_USUARIO, material_catalog.ARQUIVO_USUARIO)
    return [(f"{PASTA_CATALOGOS}/{arquivo.name}", arquivo) for arquivo in arquivos]


def _restaurar_catalogos() -> list[str]:
    """Baixa os catálogos do usuário que o disco não tem. Nunca sobrescreve um que existe."""
    restaurados: list[str] = []
    for remoto, local in _catalogos_do_usuario():
        if local.exists():
            continue
        conteudo = espelho_remoto.ler(remoto)
        if conteudo is None:
            continue
        try:
            json.loads(conteudo.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            continue  # um arquivo corrompido no espelho não pode virar o catálogo do programa
        local.parent.mkdir(parents=True, exist_ok=True)
        temporario = local.with_suffix(local.suffix + ".tmp")
        temporario.write_bytes(conteudo)
        temporario.replace(local)
        restaurados.append(local.name)
    return restaurados


def restaurar_do_espelho(*, forcar: bool = False) -> ResultadoRestauracao | None:
    """Traz do espelho o que o disco perdeu: projetos e catálogos do usuário.

    Chamada a cada execução do aplicativo, mas só trabalha uma vez por processo
    (``None`` nas demais). Se falha — token vencido, GitHub fora do ar — a
    mensagem vai para a situação do espelho e uma nova tentativa só acontece
    depois de :data:`INTERVALO_NOVA_TENTATIVA_S`. ``forcar`` ignora os dois
    limites (botão "Recarregar do GitHub"). Nunca sobrescreve o que já está
    no disco.
    """
    global _restaurado, _ultima_tentativa
    if espelho_remoto.obter_espelho() is None:
        return None
    with _TRAVA:
        if not forcar:
            if _restaurado:
                return None
            if (
                _ultima_tentativa
                and time.monotonic() - _ultima_tentativa < INTERVALO_NOVA_TENTATIVA_S
            ):
                return None
        _ultima_tentativa = time.monotonic()
        try:
            do_banco = project_store.restaurar_projetos_do_espelho()
            catalogos = _restaurar_catalogos()
        except Exception as erro:  # roda na abertura do app: não pode impedi-lo de abrir
            texto = str(erro) if isinstance(erro, EspelhoErro) else f"{type(erro).__name__}: {erro}"
            espelho_remoto.registrar_erro(f"Não foi possível carregar os dados do GitHub: {texto}")
            return ResultadoRestauracao(ok=False, erro=texto)
        _restaurado = True
    falhas: dict[str, str] = dict(do_banco["falhas"])
    if falhas:
        nomes = ", ".join(sorted(falhas)[:3])
        espelho_remoto.registrar_erro(
            f"{len(falhas)} arquivo(s) do GitHub não puderam ser lidos ({nomes}…): "
            f"{next(iter(falhas.values()))}"
        )
    else:
        espelho_remoto.limpar_erro()
    return ResultadoRestauracao(
        ok=not falhas, projetos=list(do_banco["importados"]), catalogos=catalogos, falhas=falhas
    )


def reenviar_pendencias(*, intervalo_s: float = 20.0) -> int:
    """Tenta de novo o que não chegou ao espelho; a cada execução, mas no máximo a cada ``intervalo_s``."""
    global _ultimo_reenvio
    if espelho_remoto.obter_espelho() is None or espelho_remoto.situacao().pendentes == 0:
        return 0
    with _TRAVA:
        if time.monotonic() - _ultimo_reenvio < intervalo_s:
            return espelho_remoto.situacao().pendentes
        _ultimo_reenvio = time.monotonic()
    return espelho_remoto.reenviar_pendentes()


def enviar_tudo() -> dict[str, int]:
    """Copia para o espelho todos os projetos e catálogos do usuário que existem no disco."""
    resumo = project_store.enviar_projetos_ao_espelho()
    catalogos = 0
    for remoto, local in _catalogos_do_usuario():
        if local.exists():
            espelho_remoto.enviar(remoto, local.read_bytes(), f"Catálogo do usuário: {local.name}")
            catalogos += 1
    return {
        "projetos": resumo["projetos"],
        "catalogos": catalogos,
        "pendentes": espelho_remoto.situacao().pendentes,
    }
