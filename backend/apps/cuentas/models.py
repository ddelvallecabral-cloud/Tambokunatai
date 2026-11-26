import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class Permiso(models.Model):
    codigo = models.CharField(max_length=80, unique=True)
    modulo = models.CharField(max_length=40)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "permisos"
        ordering = ["codigo"]

    def __str__(self):
        return self.codigo


class Rol(models.Model):
    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=80)
    descripcion = models.CharField(max_length=255, blank=True)
    es_sistema = models.BooleanField(default=False, help_text="Rol base definido en el código; no se borra.")
    permisos = models.ManyToManyField(Permiso, related_name="roles", db_table="rol_permisos", blank=True)

    class Meta:
        db_table = "roles"
        ordering = ["nombre"]
        verbose_name_plural = "roles"

    def __str__(self):
        return self.nombre


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, usuario, password=None, **extra):
        if not usuario:
            raise ValueError("El nombre de usuario es obligatorio")
        user = self.model(usuario=usuario.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, usuario, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(usuario, password, **extra)

    def get_by_natural_key(self, usuario):
        return self.get(usuario=usuario.strip().lower())


class Usuario(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField("acceso al panel /admin", default=False)
    debe_cambiar_clave = models.BooleanField(default=False)
    fecha_alta = models.DateTimeField(default=timezone.now)
    roles = models.ManyToManyField(Rol, through="UsuarioRol", related_name="usuarios", blank=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "usuario"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        db_table = "usuarios"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.usuario})"

    # Permisos del ERP (independientes de los permisos internos de Django).
    def roles_codigos(self) -> set[str]:
        if not hasattr(self, "_roles_cache"):
            self._roles_cache = set(self.roles.values_list("codigo", flat=True))
        return self._roles_cache

    def permisos_codigos(self) -> set[str]:
        if not self.is_active:
            return set()
        if not hasattr(self, "_permisos_cache"):
            self._permisos_cache = set(
                Permiso.objects.filter(roles__usuarios=self).values_list("codigo", flat=True).distinct()
            )
        return self._permisos_cache

    def tiene_permiso(self, *codigos: str) -> bool:
        """True si el usuario tiene TODOS los permisos indicados."""
        return set(codigos) <= self.permisos_codigos()

    def tiene_rol(self, *codigos: str) -> bool:
        """True si el usuario tiene AL MENOS UNO de los roles indicados."""
        return bool(self.roles_codigos() & set(codigos))

    def limpiar_cache_permisos(self):
        for attr in ("_roles_cache", "_permisos_cache"):
            if hasattr(self, attr):
                delattr(self, attr)


class UsuarioRol(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT)
    establecimiento = models.ForeignKey("core.Establecimiento", null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        db_table = "usuario_roles"
        constraints = [
            models.UniqueConstraint(fields=["usuario", "rol", "establecimiento"], name="usuario_rol_unico")
        ]
