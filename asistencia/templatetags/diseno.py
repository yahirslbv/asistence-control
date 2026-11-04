"""Ayudas de presentación para las plantillas (solo texto, sin lógica de negocio)."""

from django import template

register = template.Library()


@register.filter
def iniciales(texto):
    """Iniciales de las dos primeras palabras: «María López Rivera» -> «ML».

    Sirve para los avatares. Una cadena vacía da «?» para que el avatar nunca
    quede sin contenido.
    """
    palabras = str(texto or '').replace('@', ' ').split()
    letras = ''.join(p[0] for p in palabras[:2])
    return letras.upper() or '?'
