"""Servidor local que imita o trecho da API de conteúdo do GitHub usado pelo espelho.

Os testes do espelho não podem falar com o GitHub de verdade (token, rede, limite de
requisições), e um dublê que só devolve respostas prontas não pegaria o que importa: o GitHub
recusa atualizar um arquivo que já existe se o ``sha`` não vier junto, recusa um ``sha`` velho e
responde 404 para repositório privado sem acesso. Este servidor guarda os arquivos de verdade e
repete essas regras, então o cliente é exercitado contra o mesmo contrato.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


def sha_de_blob(conteudo: bytes) -> str:
    """O mesmo ``sha`` que o Git calcula para o conteúdo de um arquivo."""
    return hashlib.sha1(b"blob %d\0" % len(conteudo) + conteudo).hexdigest()


class GitHubFalso:
    def __init__(
        self,
        repositorio: str = "dono/dados",
        token: str = "token-de-teste",
        ramo: str = "",
    ) -> None:
        self.repositorio = repositorio
        self.token = token
        self.ramo = ramo
        self.privado = True
        self.pode_gravar = True
        self.arquivos: dict[str, bytes] = {}
        self.requisicoes: list[dict[str, Any]] = []
        self.commits: list[tuple[str, str, str]] = []
        # Falhas a devolver nas próximas chamadas: (método, status); status 200 devolve uma
        # página HTML em vez de JSON. Cada uma vale uma vez.
        self.falhas: list[tuple[str, int]] = []
        # Arquivos cuja leitura falha sempre: caminho completo -> status.
        self.falhas_de_leitura: dict[str, int] = {}
        self._servidor = ThreadingHTTPServer(("127.0.0.1", 0), self._fabricar_manipulador())
        # poll_interval curto: o padrão (0,5 s) faz cada shutdown() esperar meio segundo.
        self._fio = threading.Thread(
            target=self._servidor.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._servidor.server_address[1]}"

    def iniciar(self) -> None:
        self._fio.start()

    def parar(self) -> None:
        self._servidor.shutdown()
        self._servidor.server_close()
        self._fio.join(5)

    def documento(self, caminho: str) -> Any:
        return json.loads(self.arquivos[caminho].decode("utf-8"))

    def caminhos(self, pasta: str = "") -> list[str]:
        return sorted(c for c in self.arquivos if c.startswith(pasta))

    # ------------------------------------------------------------------------------------------

    def _fabricar_manipulador(self) -> type[BaseHTTPRequestHandler]:
        falso = self

        class Manipulador(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                return

            def _responder(self, status: int, corpo: Any, bruto: bool = False) -> None:
                dados = corpo if bruto else json.dumps(corpo).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Length", str(len(dados)))
                self.send_header("Content-Type", "application/octet-stream" if bruto else "json")
                self.end_headers()
                self.wfile.write(dados)

            def _tratar(self, metodo: str) -> None:
                endereco = urlparse(self.path)
                consulta = {k: v[0] for k, v in parse_qs(endereco.query).items()}
                tamanho = int(self.headers.get("Content-Length") or 0)
                bruto_corpo = self.rfile.read(tamanho) if tamanho else b""
                corpo = json.loads(bruto_corpo) if bruto_corpo else {}
                caminho = unquote(endereco.path)
                falso.requisicoes.append(
                    {
                        "metodo": metodo,
                        "caminho": caminho,
                        "consulta": consulta,
                        "cabecalhos": {k.lower(): v for k, v in self.headers.items()},
                        "corpo": corpo,
                    }
                )
                if self.headers.get("Authorization") != f"Bearer {falso.token}":
                    return self._responder(401, {"message": "Bad credentials"})
                for indice, (metodo_falho, status) in enumerate(falso.falhas):
                    if metodo_falho == metodo:
                        del falso.falhas[indice]
                        if status == 200:  # resposta que não é JSON, como a de um portal de rede
                            return self._responder(200, b"<html>portal</html>", bruto=True)
                        return self._responder(status, {"message": "falha injetada pelo teste"})
                prefixo = f"/repos/{falso.repositorio}"
                if not caminho.startswith(prefixo):
                    return self._responder(404, {"message": "Not Found"})
                resto = caminho[len(prefixo) :]
                if resto == "":
                    return self._responder(
                        200,
                        {
                            "full_name": falso.repositorio,
                            "private": falso.privado,
                            "permissions": {"push": falso.pode_gravar},
                        },
                    )
                if not resto.startswith("/contents/"):
                    return self._responder(404, {"message": "Not Found"})
                alvo = resto[len("/contents/") :]
                ramo_pedido = consulta.get("ref") or corpo.get("branch") or ""
                if falso.ramo and ramo_pedido and ramo_pedido != falso.ramo:
                    return self._responder(404, {"message": f"Branch {ramo_pedido} not found"})
                if metodo == "GET":
                    return self._ler(alvo)
                if not falso.pode_gravar:
                    return self._responder(403, {"message": "Resource not accessible by token"})
                if metodo == "PUT":
                    return self._gravar(alvo, corpo)
                return self._apagar(alvo, corpo)

            def _ler(self, alvo: str) -> None:
                if alvo in falso.falhas_de_leitura:
                    return self._responder(
                        falso.falhas_de_leitura[alvo], {"message": "falha de leitura do teste"}
                    )
                if alvo in falso.arquivos:
                    conteudo = falso.arquivos[alvo]
                    if "raw" in (self.headers.get("Accept") or ""):
                        return self._responder(200, conteudo, bruto=True)
                    return self._responder(
                        200,
                        {
                            "name": alvo.rsplit("/", 1)[-1],
                            "path": alvo,
                            "sha": sha_de_blob(conteudo),
                            "size": len(conteudo),
                            "type": "file",
                            "content": base64.b64encode(conteudo).decode("ascii"),
                            "encoding": "base64",
                        },
                    )
                prefixo = alvo.rstrip("/") + "/"
                diretos = {
                    c[len(prefixo) :]: v
                    for c, v in falso.arquivos.items()
                    if c.startswith(prefixo) and "/" not in c[len(prefixo) :]
                }
                if not any(c.startswith(prefixo) for c in falso.arquivos):
                    return self._responder(404, {"message": "Not Found"})
                return self._responder(
                    200,
                    [
                        {
                            "name": nome,
                            "path": prefixo + nome,
                            "sha": sha_de_blob(conteudo),
                            "size": len(conteudo),
                            "type": "file",
                        }
                        for nome, conteudo in sorted(diretos.items())
                    ],
                )

            def _gravar(self, alvo: str, corpo: dict[str, Any]) -> None:
                novo = base64.b64decode(corpo["content"])
                if alvo in falso.arquivos:
                    if "sha" not in corpo:
                        return self._responder(422, {"message": '"sha" wasn\'t supplied.'})
                    if corpo["sha"] != sha_de_blob(falso.arquivos[alvo]):
                        return self._responder(
                            409, {"message": f"{alvo} does not match {corpo['sha']}"}
                        )
                    status = 200
                else:
                    status = 201
                falso.arquivos[alvo] = novo
                falso.commits.append(("PUT", alvo, str(corpo.get("message", ""))))
                self._responder(
                    status, {"content": {"path": alvo, "sha": sha_de_blob(novo)}, "commit": {}}
                )

            def _apagar(self, alvo: str, corpo: dict[str, Any]) -> None:
                if alvo not in falso.arquivos:
                    return self._responder(404, {"message": "Not Found"})
                if corpo.get("sha") != sha_de_blob(falso.arquivos[alvo]):
                    return self._responder(409, {"message": f"{alvo} does not match"})
                del falso.arquivos[alvo]
                falso.commits.append(("DELETE", alvo, str(corpo.get("message", ""))))
                self._responder(200, {"commit": {}})

            def do_GET(self) -> None:
                self._tratar("GET")

            def do_PUT(self) -> None:
                self._tratar("PUT")

            def do_DELETE(self) -> None:
                self._tratar("DELETE")

        return Manipulador
