from django import forms
from .models import Usuario, EmpresaExportadora, Importador, Reunion, Certificacion, FechaDisponible, HorarioDisponible

class UsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'tipo_doc', 'num_doc', 'email', 'username', 'password']
        widgets = {
            'password': forms.PasswordInput(),
        }


class EmpresaExportadoraForm(forms.ModelForm):
    certificaciones = forms.ModelMultipleChoiceField(
        queryset=Certificacion.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = EmpresaExportadora
        exclude = ['usuario']
        widgets = {
            'brochure': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'paises_exporta': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }

class ImportadorForm(forms.ModelForm):
    class Meta:
        model = Importador
        exclude = ['usuario']  # Se asigna manualmente desde la vista
        widgets = {
            'idiomas': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'rubros': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'paises_comercializa': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'tipos_proveedor': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class ReunionForm(forms.ModelForm):
    class Meta:
        model = Reunion
        fields = ['horario', 'mensaje']
        widgets = {
            'horario': forms.Select(attrs={'class': 'form-select'}),
            'mensaje': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class FechaDisponibleForm(forms.ModelForm):
    class Meta:
        model = FechaDisponible
        fields = ['fecha']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        }

class HorarioDisponibleForm(forms.ModelForm):
    class Meta:
        model = HorarioDisponible
        fields = ['hora']
        widgets = {
            'hora': forms.TimeInput(format='%H:%M', attrs={'class': 'form-control', 'type': 'time'})
        }
