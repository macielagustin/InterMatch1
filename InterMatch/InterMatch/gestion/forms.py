from django import forms
from .models import Usuario, EmpresaExportadora, Importador, Reunion, Certificacion, FechaDisponible, HorarioDisponible, PrefijoTelefono, Pais, Provincia, Localidad,Idioma, Rubro, TipoProveedor, TIPO_IMPORTADOR_CHOICES

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
            'rubro': forms.Select(attrs={'class': 'form-select'}),
            'prefijo_telefono': forms.Select(attrs={'class': 'form-select'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'brochure': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'paises_exporta': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'capacidad_productiva': forms.NumberInput(attrs={'class': 'form-control'}),
            'unidad_capacidad': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        capacidad = cleaned.get("capacidad_productiva")
        unidad = cleaned.get("unidad_capacidad")
        if capacidad is not None and not unidad:
            self.add_error("unidad_capacidad", "Selecciona una unidad de medida.")
        return cleaned

class ImportadorForm(forms.ModelForm):
    # OPCIÓN A (recomendada): usar checkbox por defecto para el booleano
    # → simplemente NO toques experiencia_proveedores_arg en widgets

    # OPCIÓN B (si querés select “Sí/No”):
    experiencia_proveedores_arg = forms.TypedChoiceField(
        choices=((True, 'Sí'), (False, 'No')),
        coerce=lambda v: v in ('True', 'true', True, '1', 1, 'on'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label='¿Experiencia con proveedores argentinos?'
    )

    class Meta:
        model = Importador
        exclude = ['usuario']
        widgets = {
            'pais_origen': forms.Select(attrs={'class': 'form-select', 'id': 'id_pais_origen'}),
            'provincia':   forms.Select(attrs={'class': 'form-select', 'id': 'id_provincia'}),
            'localidad':   forms.Select(attrs={'class': 'form-select', 'id': 'id_localidad'}),
            'empleados': forms.Select(attrs={'class': 'form-select'}),
            'prefijo_telefono': forms.Select(attrs={'class': 'form-select'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'idiomas': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'rubros': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'paises_comercializa': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'tipos_proveedor': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'cargo': forms.Select(attrs={'class': 'form-select'}),  # ← S mayúscula
            # Si usás OPCIÓN A (checkbox), comentá la línea de abajo:
            # 'experiencia_proveedores_arg': forms.Select(attrs={'class': 'form-select'}),
            'sitio_web': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'tipo_importador': forms.Select(attrs={'class': 'form-select'}),
            'presentacion_buscada': forms.Select(attrs={'class': 'form-select'}),
            'comentarios': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def _init_(self, *args, **kwargs):
        super()._init_(*args, **kwargs)

        # Catálogos M2M
        self.fields['idiomas'].queryset = Idioma.objects.all().order_by('nombre')
        self.fields['rubros'].queryset = Rubro.objects.all().order_by('nombre')
        self.fields['paises_comercializa'].queryset = Pais.objects.all().order_by('nombre')
        self.fields['tipos_proveedor'].queryset = TipoProveedor.objects.all().order_by('nombre')

        # FKs
        self.fields['pais_origen'].queryset = Pais.objects.all().order_by('nombre')
        # (opcional) ordenar prefijos
        # self.fields['prefijo_telefono'].queryset = PrefijoTelefono.objects.all().order_by('nombre')

        # Dependientes
        self.fields['provincia'].queryset = Provincia.objects.none()
        self.fields['localidad'].queryset = Localidad.objects.none()

        if 'pais_origen' in self.data:
            try:
                pais_id = int(self.data.get('pais_origen'))
                self.fields['provincia'].queryset = Provincia.objects.filter(pais_id=pais_id).order_by('nombre')
            except (ValueError, TypeError):
                pass

        if 'provincia' in self.data:
            try:
                provincia_id = int(self.data.get('provincia'))
                self.fields['localidad'].queryset = Localidad.objects.filter(provincia_id=provincia_id).order_by('nombre')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            if self.instance.pais_origen_id:
                self.fields['provincia'].queryset = Provincia.objects.filter(
                    pais_id=self.instance.pais_origen_id
                ).order_by('nombre')
            if self.instance.provincia_id:
                self.fields['localidad'].queryset = Localidad.objects.filter(
                    provincia_id=self.instance.provincia_id
                ).order_by('nombre')

def horarios_disponibles(fecha_date):
    ocupados = (Reunion.objects
                .filter(fecha=fecha_date)
                .exclude(estado='Cancelada')
                .values_list('horario_id', flat=True))
    return HorarioDisponible.objects.exclude(id__in=ocupados).order_by('hora')

class ReunionForm(forms.ModelForm):
    # campo “fecha” mostrado al usuario (elige una FechaDisponible habilitada)
    fecha = forms.ModelChoiceField(
        queryset=FechaDisponible.objects.filter(habilitada=True).order_by('fecha'),
        label="Seleccionar fecha",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Reunion
        fields = ['fecha', 'horario', 'mensaje']   # ahora incluye fecha (en el form)
        widgets = {
            'horario': forms.Select(attrs={'class': 'form-select'}),
            'mensaje': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        fecha_seleccionada = kwargs.pop('fecha_seleccionada', None)
        super().__init__(*args, **kwargs)

        # Poblamos horarios según la fecha elegida
        if fecha_seleccionada:
            self.fields['horario'].queryset = horarios_disponibles(fecha_seleccionada)
        elif self.data.get('fecha'):
            f = FechaDisponible.objects.get(pk=self.data['fecha']).fecha
            self.fields['horario'].queryset = horarios_disponibles(f)

def horarios_disponibles(fecha_date, excluir_reunion_id=None):
    qs = Reunion.objects.filter(fecha=fecha_date).exclude(estado='Cancelada')
    if excluir_reunion_id:
        qs = qs.exclude(pk=excluir_reunion_id)
    ocupados = qs.values_list('horario_id', flat=True)
    return HorarioDisponible.objects.exclude(id__in=ocupados).order_by('hora')

class CrearReunionForm(forms.Form):
    fecha = forms.ModelChoiceField(
        queryset=FechaDisponible.objects.filter(habilitada=True).order_by('fecha'),
        label="Seleccionar fecha",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    horario = forms.ModelChoiceField(
        queryset=HorarioDisponible.objects.none(),
        label="Seleccionar horario",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    mensaje = forms.CharField(
        label="Mensaje (opcional)", required=False,
        widget=forms.Textarea(attrs={'class':'form-control','rows':4})
    )

    def __init__(self, *args, **kwargs):
        fecha_sel = kwargs.pop('fecha_seleccionada', None)
        super().__init__(*args, **kwargs)
        if fecha_sel:
            self.fields['horario'].queryset = horarios_disponibles(fecha_sel)
        elif self.data.get('fecha'):
            f = FechaDisponible.objects.get(pk=self.data['fecha']).fecha
            self.fields['horario'].queryset = horarios_disponibles(f)

class FechaDisponibleForm(forms.ModelForm):
    class Meta:
        model = FechaDisponible
        fields = ['fecha', 'habilitada']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        }
    def clean(self):
        cleaned = super().clean()
        self.instance.fecha = cleaned.get('fecha', self.instance.fecha)
        self.instance.habilitada = cleaned.get('habilitada', self.instance.habilitada)
        self.instance.clean()
        return cleaned


class HorarioDisponibleForm(forms.ModelForm):
    class Meta:
        model = HorarioDisponible
        fields = ['hora']
        widgets = {
            'hora': forms.TimeInput(format='%H:%M', attrs={'class': 'form-control', 'type': 'time'})
        }

class UsuarioAdminForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['email','username','nombre','apellido','tipo_doc','num_doc','rol']
        widgets = {
            'email': forms.EmailInput(attrs={'class':'form-control'}),
            'username': forms.TextInput(attrs={'class':'form-control'}),
            'nombre': forms.TextInput(attrs={'class':'form-control'}),
            'apellido': forms.TextInput(attrs={'class':'form-control'}),
        }

class AdminReunionForm(forms.ModelForm):
    fecha = forms.ModelChoiceField(
        queryset=FechaDisponible.objects.all().order_by('fecha'),  # admin puede mover a cualquier fecha cargada
        label="Fecha",
        widget=forms.Select(attrs={'class':'form-select'})
    )

    class Meta:
        model = Reunion
        fields = ['fecha', 'horario', 'mensaje', 'estado']
        widgets = {
            'horario': forms.Select(attrs={'class':'form-select'}),
            'mensaje': forms.Textarea(attrs={'class':'form-control','rows':4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Poblar horarios según la fecha inicial o la elegida en POST
        fecha_val = None
        if self.is_bound and self.data.get('fecha'):
            fecha_val = self.data.get('fecha')  # viene como YYYY-MM-DD
        elif self.instance and self.instance.fecha:
            fecha_val = self.instance.fecha
        if fecha_val:
            if isinstance(fecha_val, str):
                from datetime import datetime
                fecha_val = datetime.strptime(fecha_val, "%Y-%m-%d").date()
            self.fields['horario'].queryset = horarios_disponibles(fecha_val, excluir_reunion_id=self.instance.pk)

    def clean(self):
        cleaned = super().clean()
        f = cleaned.get('fecha')
        h = cleaned.get('horario')
        if f and h:
            # verificar disponibilidad excluyéndome a mí mismo
            if not horarios_disponibles(f, excluir_reunion_id=self.instance.pk).filter(pk=h.pk).exists():
                raise forms.ValidationError("Ese horario ya no está disponible para la fecha seleccionada.")
        return cleaned
    
    # RECUPERAR CONTRASEÑA #

class PasswordResetRequestForm(forms.Form):
    identificador = forms.CharField(
        label="Email o Usuario",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingresá tu email o usuario'})
    )

class SetPasswordForm(forms.Form):
    password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label="Repetir contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned