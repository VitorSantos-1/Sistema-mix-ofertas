"""
gerar_instalador_v2.py — Compilação Mestre e Geração do Instalador Mix de Ofertas 2.0
"""

import os
import sys
import subprocess
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
DIST_INSTALLER_DIR = os.path.join(PROJECT_DIR, "dist_installer")

def find_iscc():
    paths = [
        r"C:\Program Files\Inno Setup 7\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return shutil.which("iscc") or shutil.which("ISCC.exe")

def main():
    os.chdir(PROJECT_DIR)
    print("==================================================================")
    print("  COMPILAÇÃO MESTRE: MIX DE OFERTAS 2.0 (DESKTOP NATIVO)")
    print("==================================================================")

    # 1. Compilar executavel com PyInstaller
    import build_v2
    build_v2.check_and_install_deps()
    ok = build_v2.build_executable()
    if not ok:
        print("\n❌ Falha na geração do executável. Abortando.")
        sys.exit(1)

    # 2. Localizar Inno Setup Compiler
    iscc_path = find_iscc()
    if not iscc_path:
        print("\n⚠️ Compilador Inno Setup (ISCC.exe) não encontrado nos caminhos padrão.")
        print(f"O executável 'Mix_Ofertas_v2.exe' foi gerado em: {PROJECT_DIR}")
        sys.exit(1)

    print(f"\nISCC encontrado: {iscc_path}")
    print("Compilando instalador Inno Setup v2.0...")
    iss_file = os.path.join(PROJECT_DIR, "installer_v2.iss")

    res = subprocess.run([iscc_path, iss_file])
    if res.returncode != 0:
        print("\n❌ Erro durante a geração do instalador pelo Inno Setup.")
        sys.exit(1)

    installer_name = "Mix_Ofertas_Setup_v2.0.exe"
    src_installer = os.path.join(DIST_INSTALLER_DIR, installer_name)
    desktop_installer = os.path.join(DESKTOP_DIR, installer_name)

    if os.path.exists(src_installer):
        shutil.copy2(src_installer, desktop_installer)
        size_mb = os.path.getsize(desktop_installer) / (1024 * 1024)
        print("\n" + "="*66)
        print(" 🎉 SUCESSO TOTAL! INSTALADOR 2.0 GERADO COM ÊXITO!")
        print("="*66)
        print(f"📦 Instalador: {installer_name} ({size_mb:.1f} MB)")
        print(f"📍 Localização: {desktop_installer}")
        print("="*66 + "\n")
    else:
        print(f"\n⚠️ Instalador gerado em {DIST_INSTALLER_DIR}, mas não copiado para o Desktop.")

if __name__ == "__main__":
    main()
