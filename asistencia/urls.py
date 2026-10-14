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
]
