"""
Configuracion global de la suite de pruebas para Enigma-64.

Garantiza la correcta localizacion del paquete enigma64 en sys.path y
de las bibliotecas Tcl/Tk en entornos Windows para la ejecucion de pytest.
"""

from __future__ import annotations

import os
import sys

# Asegurar que la raiz del repositorio este siempre en sys.path,
# permitiendo ejecutar tanto 'pytest' directamente como 'python -m pytest'.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# En Windows, si Python no tiene configuradas las variables de entorno de Tcl/Tk,
# se resuelven a partir de la instalacion base de Python para asegurar la ejecucion
# correcta de pruebas graficas (Tkinter).
if sys.platform == "win32":
    base_tcl = os.path.join(sys.base_prefix, "tcl")
    if os.path.isdir(base_tcl):
        tcl_dir = os.path.join(base_tcl, "tcl8.6")
        tk_dir = os.path.join(base_tcl, "tk8.6")
        if os.path.isdir(tcl_dir) and "TCL_LIBRARY" not in os.environ:
            os.environ["TCL_LIBRARY"] = tcl_dir
        if os.path.isdir(tk_dir) and "TK_LIBRARY" not in os.environ:
            os.environ["TK_LIBRARY"] = tk_dir
