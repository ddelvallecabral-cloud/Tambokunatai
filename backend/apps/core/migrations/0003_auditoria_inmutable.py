"""La base de datos rechaza cualquier UPDATE, DELETE o TRUNCATE sobre la auditoría,
aunque se haga por fuera de la aplicación."""
from django.db import migrations

CREAR = """
CREATE OR REPLACE FUNCTION auditoria_inmutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'La tabla auditoria es de solo inserción (% no permitido)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auditoria_sin_cambios
    BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION auditoria_inmutable();

CREATE TRIGGER auditoria_sin_truncate
    BEFORE TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION auditoria_inmutable();
"""

BORRAR = """
DROP TRIGGER IF EXISTS auditoria_sin_truncate ON auditoria;
DROP TRIGGER IF EXISTS auditoria_sin_cambios ON auditoria;
DROP FUNCTION IF EXISTS auditoria_inmutable();
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0002_initial")]
    operations = [migrations.RunSQL(CREAR, BORRAR)]
