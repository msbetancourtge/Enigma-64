"""python -m spl.traductor entrada.asm [-o salida.asm] [--verificar] [--ejecutar]"""

import sys

from .traductor import main

sys.exit(main())
