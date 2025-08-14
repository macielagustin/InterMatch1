from django.contrib import admin
from .models import (
    Usuario,
    EmpresaExportadora,
    Importador,
    FechaDisponible,
    HorarioDisponible,
)

admin.site.register(HorarioDisponible)
class HorarioDisponibleAdmin(admin.ModelAdmin):
    list_display = ['hora']


admin.site.register(FechaDisponible)
admin.site.register(Usuario)
admin.site.register(EmpresaExportadora)
admin.site.register(Importador)
