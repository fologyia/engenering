"""Espelho remoto: o que o disco da hospedagem não guarda.

Por que existe
--------------
O Streamlit Community Cloud apaga o disco do aplicativo a cada reinício —
atualização do código, repouso por inatividade, manutenção. O banco de
projetos (SQLite) e os catálogos do usuário vivem nesse disco e sumiam
junto: "salvei e não ficou salvo". Este módulo copia cada documento para um
repositório *privado* do GitHub assim que ele é gravado no disco, e traz de
volta o que faltar quando o aplicativo sobe. O SQLite continua sendo a fonte
de trabalho (leituras rápidas, nada muda no uso local); o GitHub é só a
cópia que sobrevive ao reinício.

Só liga por configuração
------------------------
Nada sai do computador sem o usuário pedir. O espelho só existe quando as
variáveis abaixo estão definidas — no Streamlit Cloud, como segredos do
aplicativo (os segredos de primeiro nível viram variáveis de ambiente):

* ``MECANICA_TOOLKIT_GITHUB_REPO``  — ``dono/nome`` de um repositório privado
  *separado* do código (um commit no repositório do próprio aplicativo
  dispararia um novo deploy e apagaria o disco de novo);
* ``MECANICA_TOOLKIT_GITHUB_TOKEN`` — token de acesso com permissão de
  leitura e escrita de *Contents* só nesse repositório;
* ``MECANICA_TOOLKIT_GITHUB_BRANCH`` — opcional; vazio usa o ramo padrão;
* ``MECANICA_TOOLKIT_GITHUB_PASTA``  — opcional; pasta dentro do repositório
  (padrão ``mecanica_toolkit``);
* ``MECANICA_TOOLKIT_GITHUB_API``    — opcional; só os testes mudam.

Falha nunca derruba a gravação
------------------------------
O documento já foi gravado no disco quando o envio começa. Se o GitHub
estiver fora do ar, o token tiver vencido ou a rede cair, o erro vira
mensagem na tela (:func:`situacao`) e o conteúdo fica numa fila de
pendências, reenviada na próxima oportunidade — a gravação local nunca
falha por causa do espelho.

Só a biblioteca padrão é usada (``urllib``): nenhuma dependência nova para o
deploy, que roda numa versão de Python mais nova que a dos testes.
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
from collections.abc import Collection, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

VARIAVEL_REPOSITORIO = "MECANICA_TOOLKIT_GITHUB_REPO"
VARIAVEL_TOKEN = "MECANICA_TOOLKIT_GITHUB_TOKEN"
VARIAVEL_RAMO = "MECANICA_TOOLKIT_GITHUB_BRANCH"
VARIAVEL_PASTA = "MECANICA_TOOLKIT_GITHUB_PASTA"
VARIAVEL_API = "MECANICA_TOOLKIT_GITHUB_API"
VARIAVEIS = (
    VARIAVEL_REPOSITORIO,
    VARIAVEL_TOKEN,
    VARIAVEL_RAMO,
    VARIAVEL_PASTA,
    VARIAVEL_API,
)
PASTA_PADRAO = "mecanica_toolkit"
API_PADRAO = "https://api.github.com"
_VERSAO_API = "2022-11-28"
_JSON = "application/vnd.github+json"
_BRUTO = "application/vnd.github.raw+json"
_NOME_REPOSITORIO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HOSTS_SEM_TLS = {"127.0.0.1", "localhost", "[::1]"}


class EspelhoErro(RuntimeError):
    """Falha do espelho, já com a mensagem que o usuário precisa ler."""


class _ConflitoDeVersao(EspelhoErro):
    """O GitHub recusou a gravação por causa do ``sha`` do arquivo (409 ou 422)."""


@dataclass(frozen=True)
class ConfiguracaoGitHub:
    repositorio: str
    token: str = field(repr=False)
    ramo: str = ""
    pasta: str = PASTA_PADRAO
    api: str = API_PADRAO

    def __post_init__(self) -> None:
        if not _NOME_REPOSITORIO.match(self.repositorio):
            raise EspelhoErro(
                f"O repositório «{self.repositorio}» não está no formato dono/nome "
                f"(variável {VARIAVEL_REPOSITORIO})."
            )
        if not self.token.strip():
            raise EspelhoErro(f"Falta o token de acesso (variável {VARIAVEL_TOKEN}).")
        endereco = urlparse(self.api)
        if endereco.scheme != "https" and not (
            endereco.scheme == "http" and endereco.hostname in _HOSTS_SEM_TLS
        ):
            raise EspelhoErro(
                f"O endereço da API do GitHub precisa usar https (variável {VARIAVEL_API})."
            )


def configuracao_do_ambiente(
    ambiente: Mapping[str, str] | None = None,
) -> ConfiguracaoGitHub | None:
    """Configuração lida das variáveis de ambiente; ``None`` quando nada foi pedido.

    Levanta :class:`EspelhoErro` quando a configuração existe pela metade (só
    o repositório, só o token) ou está malformada — esse é o erro que o
    usuário comete ao colar os segredos, e precisa aparecer na tela em vez de
    o espelho simplesmente não ligar.
    """
    ambiente = os.environ if ambiente is None else ambiente
    repositorio = ambiente.get(VARIAVEL_REPOSITORIO, "").strip()
    token = ambiente.get(VARIAVEL_TOKEN, "").strip()
    if not repositorio and not token:
        return None
    if not repositorio:
        raise EspelhoErro(f"Falta o repositório de dados (variável {VARIAVEL_REPOSITORIO}).")
    pasta = ambiente.get(VARIAVEL_PASTA, "").strip().strip("/") or PASTA_PADRAO
    return ConfiguracaoGitHub(
        repositorio=repositorio,
        token=token,
        ramo=ambiente.get(VARIAVEL_RAMO, "").strip(),
        pasta=pasta,
        api=(ambiente.get(VARIAVEL_API, "").strip() or API_PADRAO).rstrip("/"),
    )


# ---------------------------------------------------------------------------
# Cliente da API de conteúdo do GitHub
# ---------------------------------------------------------------------------


def _mensagem_da_api(corpo: bytes) -> str:
    try:
        dados = json.loads(corpo.decode("utf-8", errors="replace"))
    except ValueError:
        return ""
    texto = str(dados.get("message", "")) if isinstance(dados, Mapping) else ""
    return texto.strip()[:200]


def _json(corpo: bytes, esperado: type) -> Any:
    """Interpreta a resposta do GitHub; uma página HTML de portal de rede vira erro claro."""
    try:
        dados = json.loads(corpo.decode("utf-8") or ("[]" if esperado is list else "{}"))
    except ValueError:
        raise EspelhoErro(
            "O GitHub devolveu uma resposta que não é a esperada (a rede pode estar "
            "interceptando a conexão)."
        ) from None
    if not isinstance(dados, esperado):
        raise EspelhoErro("O GitHub devolveu uma resposta em formato inesperado.")
    return dados


def _erro_http(codigo: int, corpo: bytes, repositorio: str) -> EspelhoErro:
    detalhe = _mensagem_da_api(corpo)
    if codigo in (409, 422):
        return _ConflitoDeVersao(f"O GitHub recusou a gravação ({codigo}): {detalhe}")
    if codigo == 401:
        texto = (
            "O GitHub recusou o token (inválido ou vencido). Gere outro e atualize o "
            f"segredo {VARIAVEL_TOKEN}."
        )
    elif codigo == 403 or codigo == 429:
        texto = (
            "O GitHub negou o acesso: confira se o token tem a permissão «Contents: Read and "
            "write» neste repositório, ou espere um pouco se o limite de requisições foi atingido."
        )
    elif codigo == 404:
        texto = (
            f"O GitHub não encontrou o repositório «{repositorio}» (ou o token não enxerga "
            "esse repositório privado). Confira o nome, o ramo e o acesso do token."
        )
    else:
        texto = f"O GitHub respondeu com o erro {codigo}."
    return EspelhoErro(
        f"{texto} ({detalhe})" if detalhe and codigo not in (401, 403, 404) else texto
    )


class EspelhoGitHub:
    """Grava, lê, lista e apaga arquivos de um repositório pela API de conteúdo.

    Os caminhos recebidos são relativos à pasta configurada. O ``sha`` de cada
    arquivo é guardado ao listar e ao gravar: o GitHub só aceita atualizar um
    arquivo que já existe se o ``sha`` atual vier junto.
    """

    def __init__(self, configuracao: ConfiguracaoGitHub, *, tempo_limite: float = 20.0) -> None:
        self.configuracao = configuracao
        self.tempo_limite = tempo_limite
        self._shas: dict[str, str] = {}

    # -- transporte --------------------------------------------------------

    def _url(self, caminho: str | None, consulta: Mapping[str, str] | None = None) -> str:
        base = f"{self.configuracao.api}/repos/{self.configuracao.repositorio}"
        if caminho is not None:
            completo = "/".join(p for p in (self.configuracao.pasta, caminho.strip("/")) if p)
            base += f"/contents/{quote(completo, safe='/')}"
        return base + (f"?{urlencode(consulta)}" if consulta else "")

    def _chamar(
        self,
        metodo: str,
        url: str,
        *,
        corpo: Mapping[str, Any] | None = None,
        aceitar: str = _JSON,
    ) -> tuple[int, bytes]:
        pedido = Request(
            url,
            data=json.dumps(corpo).encode("utf-8") if corpo is not None else None,
            method=metodo,
            headers={
                "Authorization": f"Bearer {self.configuracao.token}",
                "Accept": aceitar,
                "X-GitHub-Api-Version": _VERSAO_API,
                "User-Agent": "mecanica-toolkit",
                **({"Content-Type": "application/json"} if corpo is not None else {}),
            },
        )
        try:
            with urlopen(pedido, timeout=self.tempo_limite) as resposta:
                return resposta.status, resposta.read()
        except HTTPError as erro:
            try:
                conteudo = erro.read()
            finally:
                erro.close()
            if erro.code == 404 and metodo == "GET":
                return 404, conteudo
            raise _erro_http(erro.code, conteudo, self.configuracao.repositorio) from None
        except (URLError, TimeoutError, OSError) as erro:
            motivo = getattr(erro, "reason", erro)
            raise EspelhoErro(f"Sem conexão com o GitHub ({motivo}).") from None

    def _consulta_do_ramo(self) -> dict[str, str] | None:
        return {"ref": self.configuracao.ramo} if self.configuracao.ramo else None

    def _com_ramo(self, corpo: dict[str, Any]) -> dict[str, Any]:
        if self.configuracao.ramo:
            corpo["branch"] = self.configuracao.ramo
        return corpo

    # -- operações ---------------------------------------------------------

    def testar(self) -> str:
        """Confere repositório, ramo e permissão de escrita; devolve a frase de sucesso."""
        status, corpo = self._chamar("GET", self._url(None))
        if status == 404:
            raise _erro_http(404, corpo, self.configuracao.repositorio)
        dados = _json(corpo, dict)
        permissoes = dados.get("permissions")
        if isinstance(permissoes, Mapping) and permissoes.get("push") is False:
            raise EspelhoErro(
                "O token enxerga o repositório, mas não pode gravar nele: dê a permissão "
                "«Contents: Read and write» ao token."
            )
        privado = "privado" if dados.get("private") else "PÚBLICO — prefira um repositório privado"
        return f"Conectado a {self.configuracao.repositorio} ({privado})."

    def listar(self, pasta: str) -> dict[str, str]:
        """Arquivos diretamente dentro da pasta, como ``{nome: sha}``."""
        status, corpo = self._chamar(
            "GET", self._url(pasta, self._consulta_do_ramo()), aceitar=_JSON
        )
        if status == 404:
            return {}
        dados = _json(corpo, list)
        nomes: dict[str, str] = {}
        for item in dados:
            if isinstance(item, Mapping) and item.get("type") == "file":
                nome = str(item["name"])
                nomes[nome] = str(item["sha"])
                self._shas[f"{pasta.strip('/')}/{nome}"] = str(item["sha"])
        return nomes

    def ler(self, caminho: str) -> bytes | None:
        """Conteúdo bruto do arquivo, ou ``None`` se ele não existe."""
        status, corpo = self._chamar(
            "GET", self._url(caminho, self._consulta_do_ramo()), aceitar=_BRUTO
        )
        return None if status == 404 else corpo

    def _sha_atual(self, caminho: str) -> str | None:
        status, corpo = self._chamar(
            "GET", self._url(caminho, self._consulta_do_ramo()), aceitar=_JSON
        )
        if status == 404:
            self._shas.pop(caminho, None)
            return None
        dados = _json(corpo, dict)
        sha = str(dados.get("sha", ""))
        if sha:
            self._shas[caminho] = sha
        return sha or None

    def gravar(self, caminho: str, conteudo: bytes, mensagem: str) -> None:
        """Cria o arquivo ou o atualiza, conferindo o ``sha`` uma vez se o GitHub recusar."""
        sha = self._shas.get(caminho)
        for tentativa in (1, 2):
            corpo: dict[str, Any] = {
                "message": mensagem,
                "content": base64.b64encode(conteudo).decode("ascii"),
            }
            if sha:
                corpo["sha"] = sha
            try:
                _, resposta = self._chamar("PUT", self._url(caminho), corpo=self._com_ramo(corpo))
            except _ConflitoDeVersao:
                if tentativa == 2:
                    raise
                sha = self._sha_atual(caminho)
                continue
            # A gravação já aconteceu: se a resposta vier ilegível, só se perde o atalho do sha
            # (o próximo envio o consulta de novo).
            try:
                novo = _json(resposta, dict).get("content", {}).get("sha")
            except EspelhoErro:
                novo = None
            if novo:
                self._shas[caminho] = str(novo)
            else:
                self._shas.pop(caminho, None)
            return

    def apagar(self, caminho: str, mensagem: str) -> None:
        """Apaga o arquivo; quem já não existe conta como apagado."""
        sha = self._shas.get(caminho) or self._sha_atual(caminho)
        if not sha:
            return
        for tentativa in (1, 2):
            try:
                self._chamar(
                    "DELETE",
                    self._url(caminho),
                    corpo=self._com_ramo({"message": mensagem, "sha": sha}),
                )
            except _ConflitoDeVersao:
                if tentativa == 2:
                    raise
                novo = self._sha_atual(caminho)
                if not novo:
                    return
                sha = novo
                continue
            self._shas.pop(caminho, None)
            return


# ---------------------------------------------------------------------------
# Estado do processo: espelho em uso, fila de pendências, última mensagem
# ---------------------------------------------------------------------------

_NAO_DEFINIDO: Any = object()
_TRAVA = threading.RLock()
_substituto: Any = _NAO_DEFINIDO
_cliente: EspelhoGitHub | None = None
_ultimo_envio = ""
_ultimo_erro = ""
_enviados = 0
_pendentes: dict[str, tuple[bytes | None, str]] = {}


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _texto_do_erro(erro: Exception) -> str:
    if isinstance(erro, EspelhoErro):
        return str(erro)
    return f"Erro inesperado no espelho do GitHub ({type(erro).__name__}: {erro})."


def definir_espelho(espelho: EspelhoGitHub | None) -> None:
    """Fixa o espelho (ou ``None`` para desligá-lo), ignorando o ambiente. Uso dos testes."""
    global _substituto
    _substituto = espelho


def redefinir() -> None:
    """Volta ao comportamento normal (ambiente) e zera o estado. Uso dos testes."""
    global _substituto, _cliente, _ultimo_envio, _ultimo_erro, _enviados
    with _TRAVA:
        _substituto = _NAO_DEFINIDO
        _cliente = None
        _ultimo_envio = ""
        _ultimo_erro = ""
        _enviados = 0
        _pendentes.clear()


def _problema_de_configuracao() -> str:
    if _substituto is not _NAO_DEFINIDO:
        return ""
    try:
        configuracao_do_ambiente()
    except EspelhoErro as erro:
        return str(erro)
    return ""


def obter_espelho() -> EspelhoGitHub | None:
    """O espelho configurado, ou ``None`` quando ninguém o pediu (ou a config é inválida)."""
    global _cliente
    if _substituto is not _NAO_DEFINIDO:
        return _substituto
    try:
        configuracao = configuracao_do_ambiente()
    except EspelhoErro:
        return None
    if configuracao is None:
        return None
    with _TRAVA:
        if _cliente is None or _cliente.configuracao != configuracao:
            _cliente = EspelhoGitHub(configuracao)
        return _cliente


@dataclass(frozen=True)
class SituacaoEspelho:
    configurado: bool
    destino: str
    ultimo_envio: str
    ultimo_erro: str
    pendentes: int
    enviados: int
    problema_de_configuracao: str


def situacao() -> SituacaoEspelho:
    espelho = obter_espelho()
    problema = _problema_de_configuracao()
    with _TRAVA:
        return SituacaoEspelho(
            configurado=espelho is not None,
            destino=espelho.configuracao.repositorio if espelho is not None else "",
            ultimo_envio=_ultimo_envio,
            ultimo_erro=_ultimo_erro or problema,
            pendentes=len(_pendentes),
            enviados=_enviados,
            problema_de_configuracao=problema,
        )


def registrar_erro(texto: str) -> None:
    """Guarda uma falha de outra etapa (a restauração) para a tela mostrar."""
    global _ultimo_erro
    with _TRAVA:
        _ultimo_erro = texto


def limpar_erro() -> None:
    registrar_erro("")


# ---------------------------------------------------------------------------
# Operações que nunca levantam: o disco local já foi gravado
# ---------------------------------------------------------------------------


def enviar(caminho: str, conteudo: bytes, mensagem: str) -> bool:
    """Copia o documento para o espelho. ``False`` se falhou — e fica na fila."""
    espelho = obter_espelho()
    if espelho is None:
        return False
    global _ultimo_envio, _ultimo_erro, _enviados
    with _TRAVA:
        try:
            espelho.gravar(caminho, conteudo, mensagem)
        except Exception as erro:  # o disco já foi gravado: nada daqui pode derrubar quem salva
            _pendentes[caminho] = (conteudo, mensagem)
            _ultimo_erro = _texto_do_erro(erro)
            return False
        _pendentes.pop(caminho, None)
        _ultimo_envio = _agora()
        _ultimo_erro = ""
        _enviados += 1
    reenviar_pendentes()
    return True


def apagar(caminho: str, mensagem: str) -> bool:
    """Apaga o documento do espelho. ``False`` se falhou — e fica na fila."""
    espelho = obter_espelho()
    if espelho is None:
        return False
    global _ultimo_envio, _ultimo_erro
    with _TRAVA:
        try:
            espelho.apagar(caminho, mensagem)
        except Exception as erro:  # idem: a exclusão local já foi confirmada
            _pendentes[caminho] = (None, mensagem)
            _ultimo_erro = _texto_do_erro(erro)
            return False
        _pendentes.pop(caminho, None)
        _ultimo_envio = _agora()
        _ultimo_erro = ""
    reenviar_pendentes()
    return True


def reenviar_pendentes() -> int:
    """Tenta de novo o que falhou antes, uma vez cada. Devolve quantos ainda faltam."""
    espelho = obter_espelho()
    global _ultimo_envio, _ultimo_erro, _enviados
    with _TRAVA:
        if espelho is None or not _pendentes:
            return len(_pendentes)
        for caminho, (conteudo, mensagem) in list(_pendentes.items()):
            try:
                if conteudo is None:
                    espelho.apagar(caminho, mensagem)
                else:
                    espelho.gravar(caminho, conteudo, mensagem)
            except Exception as erro:
                _ultimo_erro = _texto_do_erro(erro)
                continue
            del _pendentes[caminho]
            _ultimo_envio = _agora()
            _ultimo_erro = ""
            _enviados += 1
        return len(_pendentes)


def listar(pasta: str) -> dict[str, str]:
    espelho = obter_espelho()
    if espelho is None:
        return {}
    with _TRAVA:
        return espelho.listar(pasta)


def ler(caminho: str) -> bytes | None:
    espelho = obter_espelho()
    return None if espelho is None else espelho.ler(caminho)


def baixar(
    pasta: str,
    *,
    extensao: str = ".json",
    trabalhadores: int = 6,
    ignorar: Collection[str] = (),
) -> tuple[dict[str, bytes], dict[str, str]]:
    """Baixa os arquivos de uma pasta em paralelo: ``(conteúdos, erros)`` por nome.

    Um arquivo que falha não impede os outros: o nome vai para ``erros`` e a
    restauração segue com o que veio.
    """
    espelho = obter_espelho()
    if espelho is None:
        return {}, {}
    nomes = [nome for nome in listar(pasta) if nome.endswith(extensao) and nome not in ignorar]
    conteudos: dict[str, bytes] = {}
    erros: dict[str, str] = {}

    def _ler(nome: str) -> tuple[str, bytes | None, str]:
        try:
            return nome, espelho.ler(f"{pasta.strip('/')}/{nome}"), ""
        except EspelhoErro as erro:
            return nome, None, str(erro)

    if nomes:
        with ThreadPoolExecutor(max_workers=max(1, min(trabalhadores, len(nomes)))) as piscina:
            for nome, conteudo, erro in piscina.map(_ler, nomes):
                if conteudo is not None:
                    conteudos[nome] = conteudo
                elif erro:
                    erros[nome] = erro
    return conteudos, erros


def testar_conexao() -> str:
    """Mensagem de sucesso ou :class:`EspelhoErro` com a causa."""
    espelho = obter_espelho()
    if espelho is None:
        problema = _problema_de_configuracao()
        raise EspelhoErro(
            problema
            or (
                "O espelho no GitHub não está configurado "
                f"(defina {VARIAVEL_REPOSITORIO} e {VARIAVEL_TOKEN})."
            )
        )
    return espelho.testar()
