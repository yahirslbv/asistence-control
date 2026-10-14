from .auth import IniciarSesionView, inicio
from .grupos import (
    GrupoCrearView, GrupoDetalleView, GrupoEditarView, GrupoEliminarView,
    GrupoListView, ImportarAlumnosView,
)

__all__ = [
    'IniciarSesionView', 'inicio',
    'GrupoCrearView', 'GrupoDetalleView', 'GrupoEditarView',
    'GrupoEliminarView', 'GrupoListView', 'ImportarAlumnosView',
]
