from .auth import IniciarSesionView, inicio
from .asistencia import PaseDeListaInicioView, PaseDeListaView
from .grupos import (
    BajaAlumnoView, GrupoCrearView, GrupoDetalleView, GrupoEditarView,
    GrupoEliminarView, GrupoListView, ImportarAlumnosView, InscribirAlumnoView,
)
from .reportes import ReporteAlumnoView, ReporteGrupoView, ReportesInicioView
from .sesiones import (
    GenerarSesionesView, SesionCancelarView, SesionEditarView, SesionListView,
)

__all__ = [
    'IniciarSesionView', 'inicio',
    'BajaAlumnoView', 'GrupoCrearView', 'GrupoDetalleView', 'GrupoEditarView',
    'GrupoEliminarView', 'GrupoListView', 'ImportarAlumnosView',
    'InscribirAlumnoView',
    'GenerarSesionesView', 'SesionCancelarView', 'SesionEditarView',
    'SesionListView',
    'PaseDeListaInicioView', 'PaseDeListaView',
    'ReporteAlumnoView', 'ReporteGrupoView', 'ReportesInicioView',
]
