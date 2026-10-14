from .auth import IniciarSesionView, inicio
from .grupos import (
    BajaAlumnoView, GrupoCrearView, GrupoDetalleView, GrupoEditarView,
    GrupoEliminarView, GrupoListView, ImportarAlumnosView, InscribirAlumnoView,
)

__all__ = [
    'IniciarSesionView', 'inicio',
    'BajaAlumnoView', 'GrupoCrearView', 'GrupoDetalleView', 'GrupoEditarView',
    'GrupoEliminarView', 'GrupoListView', 'ImportarAlumnosView',
    'InscribirAlumnoView',
]
