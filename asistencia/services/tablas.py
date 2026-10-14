"""Objeto tabular genérico que comparten los reportes y sus exportaciones.

Los reportes (services/reportes.py) producen una TablaDeReporte; los
exportadores (services/exportar.py) la convierten a PDF y a Excel. Así la
pantalla y los archivos muestran exactamente los mismos números.
"""

from dataclasses import dataclass, field


@dataclass
class TablaDeReporte:
    titulo: str
    subtitulo: str
    columnas: list[str]
    filas: list[list]              # cada celda es un str o un int
    notas: list[str] = field(default_factory=list)   # pie de la tabla
    marcadas: frozenset = frozenset()   # índices de las filas que se resaltan
    con_totales: bool = False      # la última fila es de totales
    nombre_base: str = 'reporte'   # base del nombre del archivo (se sanea al exportar)
