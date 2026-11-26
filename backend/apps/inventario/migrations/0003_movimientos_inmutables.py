"""La base rechaza UPDATE, DELETE y TRUNCATE sobre los movimientos de inventario:
el stock solo se corrige con un movimiento contrario."""
from django.db import migrations

CREAR = """
CREATE OR REPLACE FUNCTION movimientos_inventario_inmutables() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Los movimientos de inventario son de solo inserción (% no permitido)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER movimientos_inventario_sin_cambios
    BEFORE UPDATE OR DELETE ON movimientos_inventario
    FOR EACH ROW EXECUTE FUNCTION movimientos_inventario_inmutables();

CREATE TRIGGER movimientos_inventario_sin_truncate
    BEFORE TRUNCATE ON movimientos_inventario
    FOR EACH STATEMENT EXECUTE FUNCTION movimientos_inventario_inmutables();
"""

BORRAR = """
DROP TRIGGER IF EXISTS movimientos_inventario_sin_truncate ON movimientos_inventario;
DROP TRIGGER IF EXISTS movimientos_inventario_sin_cambios ON movimientos_inventario;
DROP FUNCTION IF EXISTS movimientos_inventario_inmutables();
"""


class Migration(migrations.Migration):
    dependencies = [("inventario", "0002_initial")]
    operations = [migrations.RunSQL("SET CONSTRAINTS ALL IMMEDIATE;" + CREAR, BORRAR)]
