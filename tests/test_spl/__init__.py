"""
Módulo de pruebas unitarias y de integración para el lenguaje SPL (Simple Programming Language).

Nota de arquitectura sobre el nombre del directorio (`test_spl/`):
    Este subdirectorio de pruebas se denomina explícitamente `test_spl` (en lugar de `spl`)
    para prevenir colisiones de espacio de nombres (namespace collision) en Python y pytest
    con el paquete de código fuente `spl/` ubicado en la raíz del repositorio.
    
    Al mantener este prefijo diferenciador, cualquier importación como:
        from spl.preprocesador import ...
    se resuelve de manera canónica y directa hacia el paquete de producción en la raíz,
    evitando que Python confunda este directorio de pruebas con el paquete del lenguaje.
"""
