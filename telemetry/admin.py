from django.contrib import admin, messages

from .models import Session, Simulation

admin.site.site_header = "Bitácora API"
admin.site.site_title = "Bitácora API"
admin.site.index_title = "Administración"


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display = ("simulation_id", "name", "api_key_prefix", "is_active", "created_at")
    list_filter = ("is_active",)
    fields = ("simulation_id", "name", "allowed_origins", "is_active", "api_key_prefix", "created_at")
    readonly_fields = ("api_key_prefix", "created_at")
    actions = ["regenerate_api_key"]

    def get_readonly_fields(self, request, obj=None):
        # El identificador no se cambia: las sesiones y la configuración de Bitácora lo usan
        if obj is not None:
            return (*self.readonly_fields, "simulation_id")
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        new_key = getattr(obj, "new_api_key", None)
        if new_key:
            self._show_key(request, obj, new_key)

    @admin.action(description="Generar una clave nueva (la anterior deja de funcionar)")
    def regenerate_api_key(self, request, queryset):
        for simulation in queryset:
            new_key = simulation.issue_api_key()
            simulation.save(update_fields=["api_key_prefix", "api_key_hash"])
            self._show_key(request, simulation, new_key)

    def _show_key(self, request, simulation, key):
        self.message_user(
            request,
            f"Clave de API de «{simulation.simulation_id}»: {key}  —  Copiala ahora: no se vuelve a mostrar.",
            messages.WARNING,
        )


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    """Solo lectura: las sesiones las crea Bitácora. Se pueden borrar, por ejemplo las de prueba."""

    list_display = ("alias", "simulation_id", "status", "started_at", "event_count", "closed_by")
    list_filter = ("simulation_id", "status")
    search_fields = ("alias", "session_id")
    exclude = ("events",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
