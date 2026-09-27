"""
Interfaz grafica de Enigma-64 - Noctua Systems.

Organizacion (inspirada en la del proyecto guia, con un modelo propio):

    core/       sistema de diseno, bus de eventos y widgets reutilizables
    servicios/  contratos y adaptadores hacia los modulos de hardware
    paneles/    un panel independiente por modulo; ninguno importa a otro
    shell/      la ventana que compone los paneles
    mockups/    los bocetos de diseno previos a la implementacion

Arranque:

    python -m enigma64.ui                            ventana completa
    python -m enigma64.ui.paneles.panel_memoria      solo el modulo de RAM

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
