"""Crea el disparador de la bitacora de correcciones (RF-11 y RNF-06).

Se implementa en la base de datos y no en una senal de Django para que la
constancia quede registrada aunque alguien modifique la tabla de asistencia
desde fuera del sistema.
"""

from django.db import migrations


CREAR_DISPARADOR = """
CREATE TRIGGER trg_asistencia_bitacora
AFTER UPDATE ON asistencia
FOR EACH ROW
BEGIN
    IF NEW.estado <> OLD.estado THEN
        INSERT INTO bitacora_cambio
            (id_asistencia, id_usuario, valor_anterior, valor_nuevo, fecha_cambio)
        VALUES
            (NEW.id_asistencia, NEW.id_usuario, OLD.estado, NEW.estado, NOW());
    END IF;
END
"""

BORRAR_DISPARADOR = "DROP TRIGGER IF EXISTS trg_asistencia_bitacora"


class Migration(migrations.Migration):

    dependencies = [
        ('asistencia', '0001_initial'),
    ]

    operations = [
        # Se pasa como lista de un elemento para que Django no parta el
        # cuerpo del disparador por los ";" internos.
        migrations.RunSQL(
            sql=[CREAR_DISPARADOR],
            reverse_sql=BORRAR_DISPARADOR,
        ),
    ]
