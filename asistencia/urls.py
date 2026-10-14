from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', views.IniciarSesionView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
