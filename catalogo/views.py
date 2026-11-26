import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from organizacion.models import Sucursal
from .models import Categoria, InventarioSucursal, Producto
from .serializers import CategoriaSerializer, ProductoSerializer
import csv
import io
from decimal import Decimal, InvalidOperation

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/jfif": ".jfif",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

SUPABASE_URL = (
    getattr(settings, "SUPABASE_URL", None) or os.getenv("SUPABASE_URL", "")
).rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = getattr(
    settings, "SUPABASE_SERVICE_ROLE_KEY", None
) or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_PRODUCTOS_BUCKET = (
    getattr(settings, "SUPABASE_PRODUCTOS_BUCKET", None)
    or os.getenv("SUPABASE_PRODUCTOS_BUCKET", "imagenes-productos")
)


def _calcular_estado_stock(stock, minimo):
    if stock <= 0:
        return "agotado"
    if stock <= minimo:
        return "stock_bajo"
    return "normal"


def _extraer_ruta_bucket(imagen_url, bucket):
    if not imagen_url or not bucket:
        return None
    try:
        parsed = urlparse(imagen_url)
        marker = f"/storage/v1/object/public/{bucket}/"
        if marker not in parsed.path:
            return None
        raw_path = parsed.path.split(marker, 1)[1]
        return unquote(raw_path).lstrip("/")
    except Exception:
        return None


def _eliminar_imagen_storage(imagen_url):
    if not imagen_url or not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return

    object_path = _extraer_ruta_bucket(imagen_url, SUPABASE_PRODUCTOS_BUCKET)
    if not object_path:
        return

    delete_url = (
        f"{SUPABASE_URL}/storage/v1/object/"
        f"{quote(SUPABASE_PRODUCTOS_BUCKET)}/{quote(object_path)}"
    )
    req = Request(
        delete_url,
        method="DELETE",
        headers={
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
        },
    )
    try:
        with urlopen(req, timeout=15):
            pass
    except (HTTPError, URLError):
        pass


class CategoriaViewSet(viewsets.ModelViewSet):
    serializer_class = CategoriaSerializer

    def get_queryset(self):
        queryset = Categoria.objects.all().order_by("nombre")
        empresa_id = self.request.query_params.get("empresa_id")
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)
        return queryset


class ProductoViewSet(viewsets.ModelViewSet):
    serializer_class = ProductoSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = (
            Producto.objects.select_related("categoria")
            .prefetch_related("inventarios")
            .order_by("-creado_en")
        )
        params = self.request.query_params

        empresa_id = params.get("empresa_id")
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)

        categoria_id = params.get("categoria_id")
        if categoria_id and categoria_id.lower() != "todas":
            queryset = queryset.filter(categoria_id=categoria_id)

        activo = params.get("activo")
        if activo is not None:
            if activo.lower() in ("true", "1"):
                queryset = queryset.filter(activo=True)
            elif activo.lower() in ("false", "0"):
                queryset = queryset.filter(activo=False)

        search = params.get("search") or params.get("q")
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search)
                | Q(sku__icontains=search)
                | Q(codigo_barras__icontains=search)
            )

        return queryset

    def perform_update(self, serializer):
        old_url = serializer.instance.imagen_url
        instance = serializer.save()
        if old_url and old_url != instance.imagen_url:
            _eliminar_imagen_storage(old_url)

    def perform_destroy(self, instance):
        old_url = instance.imagen_url
        instance.delete()
        if old_url:
            _eliminar_imagen_storage(old_url)

    @action(detail=False, methods=["post"], url_path="subir-imagen")
    def subir_imagen(self, request):
        archivo = request.FILES.get("imagen") or request.FILES.get("file")
        if not archivo:
            return Response(
                {"detail": "Debes adjuntar un archivo en el campo 'imagen'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = (archivo.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            return Response(
                {"detail": "Formato no permitido. Usa JPEG, PNG, WEBP o JFIF."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if archivo.size > MAX_IMAGE_BYTES:
            return Response(
                {"detail": "La imagen supera el límite máximo de 5 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            return Response(
                {
                    "detail": "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el backend."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        ext = os.path.splitext(archivo.name or "")[1].lower()
        if ext not in ALLOWED_IMAGE_TYPES.values():
            ext = ALLOWED_IMAGE_TYPES[content_type]

        object_path = f"productos/{uuid.uuid4()}{ext}"
        upload_url = (
            f"{SUPABASE_URL}/storage/v1/object/"
            f"{quote(SUPABASE_PRODUCTOS_BUCKET)}/{quote(object_path)}"
        )
        public_url = (
            f"{SUPABASE_URL}/storage/v1/object/public/"
            f"{quote(SUPABASE_PRODUCTOS_BUCKET)}/{quote(object_path)}"
        )

        req = Request(
            upload_url,
            data=archivo.read(),
            method="POST",
            headers={
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Content-Type": content_type,
                "x-upsert": "true",
            },
        )

        try:
            with urlopen(req, timeout=20) as resp:
                if resp.status not in (200, 201):
                    return Response(
                        {"detail": "Error al subir la imagen a Supabase Storage."},
                        status=status.HTTP_502_BAD_GATEWAY,
                    )
        except HTTPError as exc:
            detail_msg = exc.read().decode("utf-8", errors="ignore")
            return Response(
                {"detail": f"Supabase Storage rechazó la subida: {detail_msg}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except URLError as exc:
            return Response(
                {"detail": f"Error de red con Supabase Storage: {exc.reason}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {"imagen_url": public_url, "path": object_path},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="ajustar-stock")
    def ajustar_stock(self, request, pk=None):
        producto = self.get_object()

        try:
            delta = int(request.data.get("delta", 1))
        except (TypeError, ValueError):
            return Response(
                {"detail": "El campo 'delta' debe ser un número entero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sucursal_id = request.data.get("sucursal_id")

        with transaction.atomic():
            inventario = (
                InventarioSucursal.objects.select_for_update()
                .filter(producto=producto)
                .order_by("id")
                .first()
            )

            if sucursal_id:
                inventario = (
                    InventarioSucursal.objects.select_for_update()
                    .filter(producto=producto, sucursal_id=sucursal_id)
                    .first()
                )
                if not inventario:
                    sucursal = Sucursal.objects.filter(pk=sucursal_id).first()
                    if not sucursal:
                        return Response(
                            {"detail": "La sucursal indicada no existe."},
                            status=status.HTTP_404_NOT_FOUND,
                        )
                    inventario = InventarioSucursal.objects.create(
                        producto=producto,
                        sucursal=sucursal,
                        stock_actual=0,
                        estado_stock="agotado",
                    )
            elif not inventario:
                sucursal = Sucursal.objects.filter(empresa_id=producto.empresa_id).first()
                if not sucursal:
                    return Response(
                        {
                            "detail": "No hay sucursal registrada para esta empresa en inventario_sucursal."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                inventario = InventarioSucursal.objects.create(
                    producto=producto,
                    sucursal=sucursal,
                    stock_actual=0,
                    estado_stock="agotado",
                )

            nuevo_stock = max(0, (inventario.stock_actual or 0) + delta)
            minimo = producto.stock_minimo if producto.stock_minimo is not None else 5
            inventario.stock_actual = nuevo_stock
            inventario.estado_stock = _calcular_estado_stock(nuevo_stock, minimo)
            inventario.save(update_fields=["stock_actual", "estado_stock", "actualizado_en"])

            producto.refresh_from_db()
            serializer = self.get_serializer(producto)
            return Response(serializer.data, status=status.HTTP_200_OK)


    
    #Parse del archivo CSV para importar productos

    @action(detail=False, methods=["post"], url_path="carga-masiva")
    def carga_masiva(self, request):
        archivo = (
            request.FILES.get("file")
            or request.FILES.get("archivo")
            or request.FILES.get("csv")
        )
        if not archivo:
            return Response(
                {"detail": "Debes adjuntar un archivo CSV en el campo 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        nombre_archivo = (archivo.name or "").lower()
        if not nombre_archivo.endswith(".csv"):
            return Response(
                {"detail": "El archivo debe tener extensión .csv."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        empresa_id = (
            request.data.get("empresa_id")
            or request.data.get("empresa")
            or Producto.objects.values_list("empresa_id", flat=True).first()
        )
        if not empresa_id:
            return Response(
                {"detail": "No se pudo determinar la empresa para la carga masiva."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sucursal_id = request.data.get("sucursal_id")
        if sucursal_id:
            sucursal = Sucursal.objects.filter(pk=sucursal_id, empresa_id=empresa_id).first()
            if not sucursal:
                return Response(
                    {"detail": "La sucursal indicada no existe para esta empresa."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            sucursal = Sucursal.objects.filter(empresa_id=empresa_id).order_by("id").first()

        try:
            raw_bytes = archivo.read()
            texto = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                texto = raw_bytes.decode("latin-1")
            except UnicodeDecodeError:
                return Response(
                    {"detail": "No se pudo leer el archivo CSV. Guárdalo en codificación UTF-8."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        muestra = texto[:2048]
        delimitador = ";" if muestra.count(";") > muestra.count(",") else ","
        reader = csv.DictReader(io.StringIO(texto), delimiter=delimitador)

        if not reader.fieldnames:
            return Response(
                {"detail": "El archivo CSV está vacío o no tiene encabezados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        headers_normalizados = {
            (col or "").strip().lower(): (col or "").strip()
            for col in reader.fieldnames
        }

        def get_col(row, *aliases):
            for alias in aliases:
                key = headers_normalizados.get(alias.lower())
                if key is not None and key in row:
                    val = row[key]
                    if val is not None:
                        return str(val).strip()
            return ""

        creados = 0
        actualizados = 0
        errores = []

        categorias_cache = {
            c.nombre.strip().lower(): c
            for c in Categoria.objects.filter(empresa_id=empresa_id)
        }

        for idx, row in enumerate(reader, start=2):
            if not row or all(not str(v or "").strip() for v in row.values()):
                continue

            sku = get_col(row, "sku")
            nombre = get_col(row, "nombre")
            precio_venta_raw = get_col(row, "precio_venta", "venta", "precio")

            if not sku or not nombre or not precio_venta_raw:
                errores.append(
                    {
                        "fila": idx,
                        "sku": sku or "-",
                        "error": "Faltan campos obligatorios (sku, nombre, precio_venta).",
                    }
                )
                continue

            try:
                precio_venta = Decimal(precio_venta_raw.replace(",", "."))
                if precio_venta < 0:
                    raise InvalidOperation()
            except InvalidOperation:
                errores.append(
                    {
                        "fila": idx,
                        "sku": sku,
                        "error": f"precio_venta inválido: '{precio_venta_raw}'.",
                    }
                )
                continue

            precio_costo_raw = get_col(row, "precio_costo", "costo")
            try:
                precio_costo = (
                    Decimal(precio_costo_raw.replace(",", "."))
                    if precio_costo_raw
                    else Decimal("0.00")
                )
                if precio_costo < 0:
                    raise InvalidOperation()
            except InvalidOperation:
                errores.append(
                    {
                        "fila": idx,
                        "sku": sku,
                        "error": f"precio_costo inválido: '{precio_costo_raw}'.",
                    }
                )
                continue

            minimo_raw = get_col(row, "stock_minimo", "minimo", "min")
            try:
                stock_minimo = int(float(minimo_raw)) if minimo_raw else 5
                if stock_minimo < 0:
                    raise ValueError()
            except ValueError:
                errores.append(
                    {
                        "fila": idx,
                        "sku": sku,
                        "error": f"stock_minimo inválido: '{minimo_raw}'.",
                    }
                )
                continue

            stock_raw = get_col(row, "stock_inicial", "stock_actual", "stock")
            tiene_stock = stock_raw != ""
            try:
                stock_inicial = int(float(stock_raw)) if tiene_stock else 0
                if stock_inicial < 0:
                    raise ValueError()
            except ValueError:
                errores.append(
                    {
                        "fila": idx,
                        "sku": sku,
                        "error": f"stock_inicial inválido: '{stock_raw}'.",
                    }
                )
                continue

            categoria_nombre = get_col(row, "categoria", "categoria_nombre")
            codigo_barras = get_col(row, "codigo_barras", "codigoBarras", "barcode") or None
            imagen_url = get_col(row, "imagen_url", "imagenUrl", "imagen") or None
            activo_raw = get_col(row, "activo").lower()
            activo = False if activo_raw in ("false", "0", "no", "inactivo") else True

            try:
                with transaction.atomic():
                    categoria_obj = None
                    if categoria_nombre:
                        cat_key = categoria_nombre.lower()
                        categoria_obj = categorias_cache.get(cat_key)
                        if not categoria_obj:
                            categoria_obj = Categoria.objects.create(
                                empresa_id=empresa_id,
                                nombre=categoria_nombre,
                            )
                            categorias_cache[cat_key] = categoria_obj

                    producto = Producto.objects.filter(
                        empresa_id=empresa_id,
                        sku__iexact=sku,
                    ).first()

                    if producto:
                        producto.nombre = nombre
                        producto.categoria = categoria_obj
                        producto.codigo_barras = codigo_barras
                        producto.imagen_url = imagen_url
                        producto.precio_costo = precio_costo
                        producto.precio_venta = precio_venta
                        producto.stock_minimo = stock_minimo
                        producto.activo = activo
                        producto.save()
                        actualizados += 1
                    else:
                        producto = Producto.objects.create(
                            empresa_id=empresa_id,
                            categoria=categoria_obj,
                            sku=sku,
                            codigo_barras=codigo_barras,
                            nombre=nombre,
                            imagen_url=imagen_url,
                            precio_costo=precio_costo,
                            precio_venta=precio_venta,
                            stock_minimo=stock_minimo,
                            activo=activo,
                        )
                        creados += 1

                    if sucursal and (tiene_stock or not producto.inventarios.exists()):
                        inv, _ = InventarioSucursal.objects.select_for_update().get_or_create(
                            producto=producto,
                            sucursal=sucursal,
                            defaults={
                                "stock_actual": stock_inicial,
                                "estado_stock": _calcular_estado_stock(
                                    stock_inicial, stock_minimo
                                ),
                            },
                        )
                        if tiene_stock:
                            inv.stock_actual = stock_inicial
                            inv.estado_stock = _calcular_estado_stock(
                                stock_inicial, stock_minimo
                            )
                            inv.save(
                                update_fields=[
                                    "stock_actual",
                                    "estado_stock",
                                    "actualizado_en",
                                ]
                            )
            except Exception as exc:
                errores.append(
                    {
                        "fila": idx,
                        "sku": sku,
                        "error": str(exc),
                    }
                )

        return Response(
            {
                "creados": creados,
                "actualizados": actualizados,
                "errores": errores,
                "total_procesadas": creados + actualizados + len(errores),
            },
            status=status.HTTP_200_OK,
        )    