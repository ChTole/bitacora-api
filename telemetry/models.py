import hashlib
import secrets
import uuid

from django.db import models
from django.utils import timezone
from django_mongodb_backend.fields import ArrayField, EmbeddedModelArrayField
from django_mongodb_backend.models import EmbeddedModel

from .contract import MAX_SESSION_EVENTS, MAX_TYPE_LENGTH

API_KEY_PREFIX = "bk_"


def hash_api_key(raw_key):
    """Hash con el que se guarda y se busca una clave de API."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def new_session_id():
    return str(uuid.uuid4())


class Simulation(models.Model):
    """Una simulación registrada, con su clave de API. Ver docs/modelo-de-datos.md."""

    simulation_id = models.SlugField("identificador", max_length=64, unique=True,
                                     help_text="El mismo que envía Bitácora (Simulation Id).")
    name = models.CharField("nombre", max_length=120)
    api_key_prefix = models.CharField("prefijo de la clave", max_length=12, editable=False)
    api_key_hash = models.CharField(max_length=64, unique=True, editable=False)
    allowed_origins = ArrayField(models.URLField(max_length=200), default=list, blank=True,
                                 verbose_name="orígenes permitidos",
                                 help_text="Dominios desde los que se publica, separados por coma.")
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        db_table = "simulations"
        ordering = ["simulation_id"]
        verbose_name = "simulación"
        verbose_name_plural = "simulaciones"

    def __str__(self):
        return self.simulation_id

    def issue_api_key(self):
        """Genera una clave nueva y devuelve su valor. Solo se guarda el hash."""
        raw_key = API_KEY_PREFIX + secrets.token_urlsafe(32)
        self.api_key_prefix = raw_key[:8]
        self.api_key_hash = hash_api_key(raw_key)
        return raw_key

    def save(self, *args, **kwargs):
        # Toda simulación tiene clave. El valor queda disponible una sola vez, para mostrarlo.
        if not self.api_key_hash:
            self.new_api_key = self.issue_api_key()
        super().save(*args, **kwargs)


class Event(EmbeddedModel):
    """Evento de una sesión. Se guarda dentro de la sesión (ver ADR 003)."""

    sequence = models.PositiveIntegerField()
    timestamp = models.DateTimeField()
    received_at = models.DateTimeField()
    type = models.CharField(max_length=MAX_TYPE_LENGTH)
    data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.sequence} · {self.type}"


class Session(models.Model):
    """Una sesión, con sus eventos y su resumen. Ver docs/modelo-de-datos.md."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Activa"
        COMPLETED = "completed", "Completada"
        ABANDONED = "abandoned", "Abandonada"

    class ClosedBy(models.TextChoices):
        CLIENT = "client", "Bitácora"
        SERVER = "server", "Servidor (inactividad)"

    session_id = models.CharField(max_length=36, unique=True, editable=False, default=new_session_id)
    simulation_id = models.SlugField("simulación", max_length=64)
    alias = models.CharField(max_length=80)
    participant = models.JSONField("participante", null=True, blank=True)
    status = models.CharField("estado", max_length=10, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField("inicio", default=timezone.now)
    finished_at = models.DateTimeField("cierre", null=True, blank=True)
    closed_by = models.CharField("cerrada por", max_length=10, choices=ClosedBy.choices,
                                 null=True, blank=True)
    last_activity_at = models.DateTimeField("última actividad", default=timezone.now)
    event_count = models.PositiveIntegerField("eventos", default=0)
    discarded_count = models.PositiveIntegerField("eventos descartados", default=0)
    context = models.JSONField("contexto", default=dict, blank=True)
    summary = models.JSONField("resumen", null=True, blank=True)
    summary_version = models.PositiveIntegerField("versión del resumen", null=True, blank=True)
    events = EmbeddedModelArrayField(Event, max_size=MAX_SESSION_EVENTS, default=list, blank=True)

    class Meta:
        db_table = "sessions"
        ordering = ["-started_at"]
        verbose_name = "sesión"
        verbose_name_plural = "sesiones"
        indexes = [
            models.Index(fields=["simulation_id", "-started_at"], name="session_sim_started"),
            models.Index(fields=["simulation_id", "status", "-started_at"], name="session_sim_status_started"),
            models.Index(fields=["simulation_id", "alias", "-started_at"], name="session_sim_alias_started"),
            models.Index(fields=["status", "last_activity_at"], name="session_status_activity"),
        ]

    def __str__(self):
        return f"{self.alias} ({self.simulation_id})"
