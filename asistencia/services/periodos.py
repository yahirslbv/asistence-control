"""Periodos escolares: activar, desactivar y congelar (RF-17).

Reglas:
- solo un periodo está activo a la vez: activar uno desactiva el que lo estuviera
  (la base de datos lo garantiza con un índice único; aquí se serializa para que
  dos cambios simultáneos se atiendan de uno en uno);
- un periodo inactivo congela sus grupos: quedan en solo lectura, con sus
  reportes. Un grupo cuyo periodo no tiene fila en `periodo` no se congela;
- un periodo no se borra: se desactiva (como los usuarios, regla 9.5).
"""

from django.db import transaction

from ..models import Grupo, Periodo


class ErrorDePeriodo(Exception):
    """El cambio no se permite; el mensaje se puede mostrar tal cual."""


class PeriodoCerrado(ErrorDePeriodo):
    """El grupo es de un periodo inactivo y por eso está en solo lectura."""


def periodo_activo():
    """El periodo activo, o None si no hay ninguno."""
    return Periodo.objects.filter(activo=True).first()


def periodo_cerrado(clave):
    """True si el periodo existe y está inactivo. Una clave sin fila no cuenta."""
    return Periodo.objects.filter(clave=clave, activo=False).exists()


def asegurar_periodo_abierto(grupo):
    """Lanza PeriodoCerrado si el grupo es de un periodo inactivo."""
    if periodo_cerrado(grupo.periodo):
        raise PeriodoCerrado(
            f'El periodo {grupo.periodo} está inactivo: el grupo {grupo.clave} es de '
            'solo lectura. Si necesitas modificarlo, pide al administrador que '
            'active el periodo.')


def grupos_del_periodo(clave):
    """Cuántos grupos usan la clave de periodo."""
    return Grupo.objects.filter(periodo=clave).count()


def activar_periodo(periodo):
    """Deja activo este periodo y desactiva el que lo estuviera. Devuelve el
    periodo que se desactivó, o None si no había otro activo (o ya era este)."""
    with transaction.atomic():
        # Bloquea todas las filas: dos activaciones simultáneas se atienden de
        # una en una y la segunda ve el resultado de la primera.
        filas = list(Periodo.objects.select_for_update())
        if not any(f.pk == periodo.pk for f in filas):
            raise ErrorDePeriodo('El periodo ya no existe.')
        anterior = next((f for f in filas if f.activo and f.pk != periodo.pk), None)
        if anterior is not None:
            Periodo.objects.filter(pk=anterior.pk).update(activo=False)
        Periodo.objects.filter(pk=periodo.pk).update(activo=True)
    periodo.activo = True
    return anterior


def desactivar_periodo(periodo):
    """Deja inactivo este periodo: sus grupos quedan en solo lectura. Es seguro
    repetirlo."""
    with transaction.atomic():
        if not Periodo.objects.select_for_update().filter(pk=periodo.pk).exists():
            raise ErrorDePeriodo('El periodo ya no existe.')
        Periodo.objects.filter(pk=periodo.pk).update(activo=False)
    periodo.activo = False
