# gestion/management/commands/import_geo_min.py
import csv
from collections import defaultdict
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.apps import apps

CHUNK = 5000  # ajustá si querés

class Command(BaseCommand):
    help = "Importa Países, Provincias y Localidades (solo nombres y FKs) desde GeoNames."

    def add_arguments(self, parser):
        parser.add_argument("--countries", required=True, help="Ruta a countryInfo.txt")
        parser.add_argument("--adm1", required=True, help="Ruta a admin1CodesASCII.txt")
        parser.add_argument("--cities", required=True, help="Ruta a cities5000.txt o allCountries.txt (descomprimido)")
        parser.add_argument("--only", choices=["all", "countries", "provinces", "cities"], default="all")
        parser.add_argument("--filter-iso2", nargs="*", help="Limitar por países (ISO2). Ej: AR BR CL")

    def handle(self, *args, **opts):
        Pais = apps.get_model("gestion", "Pais")
        Provincia = apps.get_model("gestion", "Provincia")
        Localidad = apps.get_model("gestion", "Localidad")

        path_countries = opts["countries"]
        path_adm1 = opts["adm1"]
        path_cities = opts["cities"]
        only = opts["only"]
        filter_iso2 = set([x.upper() for x in (opts["filter_iso2"] or [])])

        if only in ("all", "countries"):
            self.stdout.write(self.style.NOTICE("→ Importando países..."))
            self._import_countries(Pais, path_countries, filter_iso2)

        # Mapa ISO2 → Pais (para provincias)
        iso2_to_pais = {}
        for p in Pais.objects.all():
            # Asumimos que en tu modelo solo existe 'nombre'. Buscaremos por nombre como fallback si falta iso2.
            # Para mapear ISO2 correctamente necesitamos countryInfo. Cargamos un map auxiliar rápido:
            pass

        # Construimos un map ISO2->nombre desde countryInfo para vincular al Pais por nombre:
        iso2_to_countryname = self._read_iso2_to_name(path_countries, filter_iso2)

        # Rellenamos iso2_to_pais buscando por nombre (tu esquema no tiene iso2):
        for iso2, cname in iso2_to_countryname.items():
            pais = Pais.objects.filter(nombre=cname).first()
            if pais:
                iso2_to_pais[iso2] = pais

        if only in ("all", "provinces"):
            self.stdout.write(self.style.NOTICE("→ Importando provincias/estados..."))
            self._import_provinces(Provincia, path_adm1, iso2_to_pais, filter_iso2)

        # Map para ciudades: (ISO2, admin1_code) → Provincia
        prov_index = self._build_admin1_index(Provincia, path_adm1, iso2_to_pais, filter_iso2)

        if only in ("all", "cities"):
            self.stdout.write(self.style.NOTICE("→ Importando localidades/ciudades... (puede tardar)"))
            self._import_cities(Localidad, path_cities, iso2_to_pais, prov_index, filter_iso2)

        self.stdout.write(self.style.SUCCESS("✅ Listo."))

    # ---------- Helpers ----------
    def _read_iso2_to_name(self, path_countries, filter_iso2):
        """Lee countryInfo.txt → {ISO2: country_name} (solo lo necesario)."""
        out = {}
        with open(path_countries, encoding="utf-8") as f:
            r = csv.reader(f, delimiter="\t")
            for row in r:
                if not row or row[0].startswith("#"):
                    continue
                iso2 = (row[0] or "").strip()
                name = (row[4] or "").strip() if len(row) > 4 else ""
                if not iso2 or not name:
                    continue
                if filter_iso2 and iso2.upper() not in filter_iso2:
                    continue
                out[iso2.upper()] = name
        return out

    @transaction.atomic
    def _import_countries(self, Pais, path_countries, filter_iso2):
        # Crea País solo por nombre (evita duplicados por nombre exacto)
        created = 0
        seen = set(Pais.objects.values_list("nombre", flat=True))
        with open(path_countries, encoding="utf-8") as f:
            r = csv.reader(f, delimiter="\t")
            for row in r:
                if not row or row[0].startswith("#"):
                    continue
                iso2 = (row[0] or "").strip().upper()
                name = (row[4] or "").strip() if len(row) > 4 else ""
                if not iso2 or not name:
                    continue
                if filter_iso2 and iso2 not in filter_iso2:
                    continue
                if name not in seen:
                    Pais.objects.create(nombre=name)
                    seen.add(name)
                    created += 1
        self.stdout.write(f"Países creados: {created}")

    def _import_provinces(self, Provincia, path_adm1, iso2_to_pais, filter_iso2):
        """
        admin1CodesASCII.txt: code \t name \t ASCIIname \t geonameid
        code = ISO2.admin1 (ej 'AR.C' o 'AR.07')
        Creamos Provincia por (pais, nombre) si no existe.
        """
        created = 0
        to_create = []
        # cache existentes por (pais_id, nombre)
        existentes = set(Provincia.objects.values_list("pais_id", "nombre"))

        with open(path_adm1, encoding="utf-8") as f:
            r = csv.reader(f, delimiter="\t")
            for row in r:
                if not row or row[0].startswith("#"):
                    continue
                code = (row[0] or "").strip()
                name = (row[1] or "").strip()
                if not code or not name:
                    continue
                parts = code.split(".")
                if len(parts) < 2:
                    continue
                iso2 = parts[0].upper()
                if filter_iso2 and iso2 not in filter_iso2:
                    continue
                pais = iso2_to_pais.get(iso2)
                if not pais:
                    continue
                key = (pais.id, name)
                if key in existentes:
                    continue
                to_create.append(Provincia(nombre=name, pais=pais))
                if len(to_create) >= CHUNK:
                    Provincia.objects.bulk_create(to_create, ignore_conflicts=True)
                    created += len(to_create)
                    to_create.clear()

        if to_create:
            Provincia.objects.bulk_create(to_create, ignore_conflicts=True)
            created += len(to_create)

        self.stdout.write(f"Provincias creadas: {created}")

    def _build_admin1_index(self, Provincia, path_adm1, iso2_to_pais, filter_iso2):
        """
        Devuelve dict: (ISO2, admin1_code) -> Provincia
        Para mapear ciudades a su provincia. Si hay provincias duplicadas de nombre,
        igual usamos el par (ISO2, admin1_code) del archivo adm1.
        """
        # Primero construimos (ISO2, admin1_code) -> nombre_prov desde el archivo
        code_to_name = {}
        with open(path_adm1, encoding="utf-8") as f:
            r = csv.reader(f, delimiter="\t")
            for row in r:
                if not row or row[0].startswith("#"):
                    continue
                code = (row[0] or "").strip()      # ej 'AR.C' o 'AR.07'
                name = (row[1] or "").strip()
                parts = code.split(".")
                if len(parts) < 2: 
                    continue
                iso2, adm1 = parts[0].upper(), parts[1]
                if filter_iso2 and iso2 not in filter_iso2:
                    continue
                code_to_name[(iso2, adm1)] = name

        # Ahora resolvemos a instancias Provincia (por nombre dentro del país)
        prov_by_key = {}
        # Preindexamos provincias por (pais_id, nombre)
        provs_by_pais_nombre = defaultdict(dict)
        for p in Provincia.objects.select_related("pais").all():
            if not getattr(p, "pais", None):
                continue
            provs_by_pais_nombre[p.pais.nombre][p.nombre] = p

        for (iso2, adm1), prov_name in code_to_name.items():
            pais = iso2_to_pais.get(iso2)
            if not pais:
                continue
            # Buscar la provincia por nombre dentro del país
            p = provs_by_pais_nombre.get(pais.nombre, {}).get(prov_name)
            if p:
                prov_by_key[(iso2, adm1)] = p

        return prov_by_key

    def _import_cities(self, Localidad, path_cities, iso2_to_pais, prov_index, filter_iso2):
        """
        GeoNames (cities5000/allCountries):
        idx: 0 id, 1 name, 4 lat, 5 lon, 6 fclass, 7 fcode, 8 country(ISO2), 10 admin1, 11 admin2, 14 population
        Creamos Localidad(nombre, provincia) si podemos resolver provincia; si no, saltamos.
        """
        created = 0
        to_create = []
        # cache existentes por (provincia_id, nombre) para evitar duplicados simples
        existentes = set(Localidad.objects.values_list("provincia_id", "nombre"))

        with open(path_cities, encoding="utf-8") as f:
            r = csv.reader(f, delimiter="\t")
            for row in r:
                if not row or len(row) < 12:
                    continue
                name = (row[1] or "").strip()
                iso2 = (row[8] or "").strip().upper()
                adm1 = (row[10] or "").strip()
                if not name or not iso2:
                    continue
                if filter_iso2 and iso2 not in filter_iso2:
                    continue

                prov = prov_index.get((iso2, adm1))
                if not prov:
                    # Si no podemos mapear a provincia, la saltamos (tu esquema requiere provincia_id)
                    continue

                key = (prov.id, name)
                if key in existentes:
                    continue

                to_create.append(Localidad(nombre=name, provincia=prov))
                if len(to_create) >= CHUNK:
                    Localidad.objects.bulk_create(to_create, ignore_conflicts=True)
                    created += len(to_create)
                    to_create.clear()

        if to_create:
            Localidad.objects.bulk_create(to_create, ignore_conflicts=True)
            created += len(to_create)

        self.stdout.write(f"Localidades creadas: {created}")
