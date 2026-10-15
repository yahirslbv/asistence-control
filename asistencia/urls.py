from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', views.IniciarSesionView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # Grupos (RF-03)
    path('grupos/', views.GrupoListView.as_view(), name='grupos'),
    path('grupos/nuevo/', views.GrupoCrearView.as_view(), name='grupo_crear'),
    path('grupos/<int:grupo_id>/', views.GrupoDetalleView.as_view(), name='grupo_detalle'),
    path('grupos/<int:grupo_id>/editar/', views.GrupoEditarView.as_view(), name='grupo_editar'),
    path('grupos/<int:grupo_id>/eliminar/', views.GrupoEliminarView.as_view(), name='grupo_eliminar'),

    # Alumnos del grupo (RF-04, RF-05)
    path('grupos/<int:grupo_id>/alumnos/importar/', views.ImportarAlumnosView.as_view(), name='alumnos_importar'),
    path('grupos/<int:grupo_id>/alumnos/agregar/', views.InscribirAlumnoView.as_view(), name='alumno_agregar'),
    path('grupos/<int:grupo_id>/alumnos/<int:alumno_id>/baja/', views.BajaAlumnoView.as_view(), name='alumno_baja'),

    # Sesiones del grupo (RF-06, RF-07)
    path('grupos/<int:grupo_id>/sesiones/', views.SesionListView.as_view(), name='sesiones'),
    path('grupos/<int:grupo_id>/sesiones/generar/', views.GenerarSesionesView.as_view(), name='sesiones_generar'),
    path('sesiones/<int:sesion_id>/editar/', views.SesionEditarView.as_view(), name='sesion_editar'),
    path('sesiones/<int:sesion_id>/cancelar/', views.SesionCancelarView.as_view(), name='sesion_cancelar'),

    # Pase de lista (RF-08, RF-09, RF-11)
    path('pase-de-lista/', views.PaseDeListaInicioView.as_view(), name='pase_de_lista_inicio'),
    path('sesiones/<int:sesion_id>/asistencia/', views.PaseDeListaView.as_view(), name='pase_de_lista'),

    # Justificantes (RF-12)
    path('sesiones/<int:sesion_id>/asistencia/<int:alumno_id>/justificante/', views.JustificanteView.as_view(), name='justificante'),
    path('sesiones/<int:sesion_id>/asistencia/<int:alumno_id>/justificante/archivo/', views.DescargarJustificanteView.as_view(), name='justificante_archivo'),
    path('sesiones/<int:sesion_id>/asistencia/<int:alumno_id>/justificante/quitar/', views.QuitarJustificanteView.as_view(), name='justificante_quitar'),

    # Reportes (RF-13, RF-14)
    path('reportes/', views.ReportesInicioView.as_view(), name='reportes'),
    path('grupos/<int:grupo_id>/reporte/', views.ReporteGrupoView.as_view(), name='reporte_grupo'),
    path('grupos/<int:grupo_id>/reporte/alumnos/<int:alumno_id>/', views.ReporteAlumnoView.as_view(), name='reporte_alumno'),

    # Exportación de los reportes a PDF y Excel (RF-15)
    path('grupos/<int:grupo_id>/reporte/exportar/<slug:formato>/', views.ExportarReporteGrupoView.as_view(), name='reporte_grupo_exportar'),
    path('grupos/<int:grupo_id>/reporte/alumnos/<int:alumno_id>/exportar/<slug:formato>/', views.ExportarReporteAlumnoView.as_view(), name='reporte_alumno_exportar'),
]
