"""
app_desktop_v2.py — Mix de Ofertas & Encartes 2.0 (Aplicativo Desktop Nativo)
Supermercados Opção

A versão 2.0 é EXATAMENTE o mesmo aplicativo da 1.0 (servidor FastAPI +
Socket.IO + front-end React), porém empacotado como um programa desktop nativo:
em vez de abrir o navegador, ele abre em uma janela própria (WebView2 do Windows,
sem abas e sem barra de endereços).

Como o back-end e a interface são reaproveitados de `main.py` (fonte única de
verdade), o layout, as funcionalidades e a disponibilidade são fielmente
idênticos aos da versão 1.0 — inclusive a colaboração em tempo real, a
exportação em Excel/PDF, os parâmetros, a equipe e as autorizações.
"""

import os
import sys

# ─── Correção crítica para PyInstaller --noconsole ────────────────────────────
class _SaidaNula:
    def write(self, *a, **k): return 0
    def writelines(self, *a, **k): pass
    def flush(self, *a, **k): pass
    def isatty(self, *a, **k): return False

if sys.stdout is None: sys.stdout = _SaidaNula()
if sys.stderr is None: sys.stderr = _SaidaNula()

import time
import socket
import threading
import traceback
import webbrowser

import uvicorn
import webview  # pywebview → janela nativa (WebView2 no Windows)


class JanelaApi:
    """API exposta ao front (window.pywebview.api).

    O WebView2 embutido não trata downloads de arquivo. Para o botão "Excel"
    funcionar na janela do app, o front chama `baixar(url)`, que abre a URL no
    navegador padrão do Windows — que baixa o arquivo normalmente.
    """
    def baixar(self, url):
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False

# Reaproveita 100% do servidor/rotas/React da versão 1.0 (fonte única de verdade).
# Importar como módulo NÃO executa o bloco __main__ de main.py, ou seja: não sobe
# o servidor nem abre o navegador — apenas disponibiliza o app ASGI e a camada DB.
import main as mix
import ofertas_mysql as om

APP_TITLE = "Mix de Ofertas & Encartes — Supermercados Opção"


# ─── Utilidades de rede ───────────────────────────────────────────────────────
def _porta_livre(preferida=3001):
    """Usa a porta padrão da 1.0 quando disponível; senão, acha uma livre."""
    candidatas = [preferida] + list(range(preferida + 1, preferida + 60))
    for port in candidatas:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            continue
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _servidor_no_ar(port, timeout=40.0):
    """Espera o servidor interno aceitar conexões antes de abrir a janela."""
    alvo = time.time() + timeout
    while time.time() < alvo:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1.0)
            s.close()
            return True
        except OSError:
            time.sleep(0.15)
    return False


def _iniciar_servidor(port):
    """Sobe o mesmo servidor ASGI da 1.0 (FastAPI + Socket.IO).

    Fica em 0.0.0.0 (igual à 1.0) para que os PCs compradores na mesma rede
    continuem acessando o servidor — mantendo a disponibilidade idêntica.
    """
    config = uvicorn.Config(mix.socket_app, host="0.0.0.0", port=port, log_level="warning")
    servidor = uvicorn.Server(config)
    servidor.run()


def _mostrar_erro(msg):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "Mix de Ofertas 2.0 — Erro", 0x10)
    except Exception:
        pass


# ─── Programa principal ───────────────────────────────────────────────────────
def main():
    # 1. Banco de dados MySQL (mesma inicialização/semeadura da 1.0).
    try:
        om.init_mysql()
    except Exception as e:
        _mostrar_erro(
            "O Mix de Ofertas 2.0 não conseguiu conectar ao banco de dados (MySQL).\n\n"
            "Este programa é o SERVIDOR e deve rodar no computador servidor, com o "
            "MySQL ligado.\n\n"
            f"Detalhe técnico:\n{e}"
        )
        # Segue mesmo assim: a própria tela do app informará o problema de conexão.

    # 2. Servidor interno em segundo plano (porta fixa 3001, igual à 1.0).
    port = int(os.environ.get("PORT", "3001"))
    try:
        threading.Thread(target=_iniciar_servidor, args=(port,), daemon=True).start()
    except Exception as e:
        _mostrar_erro(f"Falha ao iniciar o servidor interno do Mix de Ofertas 2.0:\n\n{e}")
        sys.exit(1)

    if not _servidor_no_ar(port):
        _mostrar_erro(
            "O servidor interno do Mix de Ofertas 2.0 não respondeu a tempo.\n\n"
            f"Verifique se a porta {port} não está bloqueada e tente novamente."
        )
        sys.exit(1)

    # 3. Janela desktop nativa (sem navegador) exibindo o app real da 1.0.
    webview.create_window(
        APP_TITLE,
        f"http://127.0.0.1:{port}",
        width=1440,
        height=900,
        min_size=(1100, 680),
        js_api=JanelaApi(),
    )

    # Armazenamento PERSISTENTE do WebView: por padrão o pywebview roda em modo
    # privado (private_mode=True), que APAGA o localStorage ao fechar — por isso o
    # tema (e o login) voltavam ao padrão a cada abertura. Com private_mode=False +
    # storage_path fixo, o último tema escolhido e a sessão permanecem salvos.
    _storage = os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
        "Mix de Ofertas 2.0", "webview_data",
    )
    try:
        os.makedirs(_storage, exist_ok=True)
    except Exception:
        _storage = None

    # Força o WebView2 (Edge Chromium) para renderizar o React fielmente.
    try:
        webview.start(gui="edgechromium", private_mode=False, storage_path=_storage)
    except Exception:
        # Ambiente sem WebView2: informa e cai para o motor padrão do pywebview.
        _mostrar_erro(
            "Para o visual completo, instale o \"Microsoft Edge WebView2 Runtime\" "
            "(gratuito da Microsoft) neste computador.\n\n"
            "O aplicativo tentará abrir mesmo assim."
        )
        try:
            webview.start(private_mode=False, storage_path=_storage)
        except Exception:
            webview.start()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        err_path = os.path.join(os.path.expanduser("~"), "Desktop", "mix_ofertas_v2_error.txt")
        try:
            with open(err_path, "w", encoding="utf-8") as f:
                f.write("Erro ao iniciar o Mix de Ofertas 2.0:\n\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        _mostrar_erro(f"Erro ao iniciar o Mix de Ofertas 2.0:\n\n{e}\n\nDetalhe salvo em:\n{err_path}")
        sys.exit(1)
