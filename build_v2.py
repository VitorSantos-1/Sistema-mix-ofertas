"""
build_v2.py — Compilador PyInstaller para o Mix de Ofertas 2.0 (Desktop Nativo)

A 2.0 é o mesmo aplicativo da 1.0 (FastAPI + Socket.IO + React), empacotado como
um programa desktop nativo que abre em uma janela própria (WebView2), sem
navegador. Por isso o build reaproveita as mesmas dependências da 1.0 (build_exe.py)
e acrescenta o pywebview/pythonnet para a janela nativa.

Modo --onedir (igual à 1.0): abertura instantânea e empacotamento confiável do
front-end (dist/) e dos componentes nativos do WebView2.
"""

import os
import sys
import subprocess
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_BIN_DIR = os.path.join(PROJECT_DIR, "dist_bin_v2")
ICON_PATH = os.path.join(PROJECT_DIR, "app_icon.ico")


def check_and_install_deps():
    deps = [
        "fastapi", "uvicorn", "pydantic", "pyinstaller",
        "passlib", "bcrypt", "mysql-connector-python",
        "python-socketio", "openpyxl", "websockets", "wsproto", "simple-websocket",
        "pywebview", "pythonnet",
    ]
    print("Verificando dependências Python para v2.0...")
    for dep in deps:
        try:
            mod_name = dep.replace("-", "_").split(">=")[0]
            if mod_name == "mysql_connector_python":
                mod_name = "mysql.connector"
            elif mod_name == "python_socketio":
                mod_name = "socketio"
            elif mod_name == "pywebview":
                mod_name = "webview"
            elif mod_name == "pythonnet":
                mod_name = "clr"
            __import__(mod_name)
            print(f"  OK: {dep}")
        except ImportError:
            print(f"  Instalando {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", dep], check=True)


def build_executable():
    os.chdir(PROJECT_DIR)
    print("\n--- Compilando Mix_Ofertas_v2 (Desktop Nativo WebView2) em modo Onedir ---")

    # Garante que dist_bin_v2 esteja limpo
    if os.path.exists(DIST_BIN_DIR):
        shutil.rmtree(DIST_BIN_DIR, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",  # sobrescreve dist_bin_v2 sem exigir pasta vazia (evita abortar se rmtree falhar)
        "--onedir",
        "--noconsole",
        "--distpath", "dist_bin_v2",
        # Empacota o front-end React (mesmo dist/ da 1.0) servido pelo main.py
        "--add-data", "dist;dist",
    ]

    if os.path.exists(ICON_PATH):
        cmd.extend(["--icon", "app_icon.ico"])

    hidden_imports = [
        # ── Servidor / API (idêntico à 1.0) ──
        "fastapi",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.protocols.websockets.websockets_impl",
        "socketio",
        "engineio",
        "engineio.async_drivers.asgi",
        "engineio.async_drivers.default",
        "simple_websocket",
        "wsproto",
        "passlib",
        "passlib.handlers",
        "passlib.handlers.bcrypt",
        "passlib.handlers.sha2_crypt",
        "bcrypt",
        "mysql.connector",
        "mysql.connector.plugins",
        "mysql.connector.plugins.mysql_native_password",
        "mysql.connector.plugins.caching_sha2_password",
        "openpyxl",
        # ── Módulos reaproveitados da 1.0 ──
        "main",
        "ofertas_mysql",
        "excel_export",
        # ── Janela desktop nativa (WebView2) ──
        "webview",
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "clr",
        "clr_loader",
    ]
    for h in hidden_imports:
        cmd.extend(["--hidden-import", h])

    collect_all = [
        "passlib", "bcrypt", "mysql.connector", "socketio", "engineio",
        "uvicorn", "openpyxl", "webview", "clr_loader",
    ]
    for c in collect_all:
        cmd.extend(["--collect-all", c])

    # A janela é WebView2 (edgechromium) — NÃO usamos Qt. Se o ambiente tiver PyQt6 e
    # PySide6 juntos, o PyInstaller aborta ("multiple Qt bindings"). Excluímos os bindings Qt.
    for qt in ("PyQt6", "PySide6", "PyQt5", "PySide2"):
        cmd.extend(["--exclude-module", qt])

    # O app só usa FastAPI/uvicorn/socketio/mysql/openpyxl/bcrypt/pywebview/pydantic.
    # Este ambiente (Anaconda) tem todo o stack científico/Jupyter, que NÃO é usado e
    # incha/quebra o build — o gmpy2 (via sympy) tem uma DLL que derruba o PyInstaller
    # (0xc0000139). Excluímos tudo isso para um build enxuto e estável.
    heavy_excludes = [
        "sympy", "gmpy2", "mpmath",
        "matplotlib", "pandas", "scipy", "sklearn", "skimage", "statsmodels",
        "numba", "llvmlite", "numexpr", "xarray", "patsy",
        "IPython", "ipykernel", "ipywidgets", "ipympl", "jedi", "parso",
        "notebook", "jupyter", "jupyterlab", "jupyter_client", "jupyter_core",
        "jupyter_server", "nbconvert", "nbformat", "nbclient", "qtconsole",
        "bokeh", "plotly", "altair", "panel", "holoviews", "datashader",
        "dask", "distributed", "tables", "h5py", "pyarrow", "sqlalchemy",
        "zmq", "tornado", "sphinx", "docutils", "pytest", "black", "yapf",
        "pygments",
    ]
    for m in heavy_excludes:
        cmd.extend(["--exclude-module", m])

    cmd.extend([
        "--name=Mix_Ofertas_v2",
        "app_desktop_v2.py",
    ])

    print("Executando PyInstaller...")
    res = subprocess.run(cmd)
    if res.returncode == 0:
        app_folder = os.path.join(DIST_BIN_DIR, "Mix_Ofertas_v2")
        print(f"\n✓ Pacote executável v2.0 gerado com sucesso em: {app_folder}")

        # Copia o app_icon.ico para a RAIZ do pacote. O atalho (Desktop/Menu
        # Iniciar) aponta o ícone para "<pasta instalada>\app_icon.ico"; sem este
        # arquivo o atalho fica em branco. Mantê-lo no pacote faz o deploy por
        # robocopy /MIR preservá-lo (o /MIR apaga o que não está na origem).
        if os.path.exists(ICON_PATH):
            try:
                shutil.copy2(ICON_PATH, os.path.join(app_folder, "app_icon.ico"))
                print("✓ app_icon.ico incluído na raiz do pacote.")
            except Exception as e:
                print(f"Aviso ao copiar app_icon.ico: {e}")

        # Limpeza de temporários do build
        build_folder = os.path.join(PROJECT_DIR, "build")
        if os.path.exists(build_folder):
            shutil.rmtree(build_folder, ignore_errors=True)
        spec_file = os.path.join(PROJECT_DIR, "Mix_Ofertas_v2.spec")
        if os.path.exists(spec_file):
            os.remove(spec_file)
        print("✓ Limpeza de temporários concluída.")
        return True
    else:
        print(f"\n❌ Erro durante a compilação (código {res.returncode})")
        return False


if __name__ == "__main__":
    check_and_install_deps()
    build_executable()
