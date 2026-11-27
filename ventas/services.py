import re
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from rest_framework.exceptions import ValidationError
from auditoria.models import MovimientoInventario
from catalogo.models import InventarioSucursal, Producto
from organizacion.models import Sucursal
from .models import DetalleVenta, Venta


def _resolver_nombre_responsable(usuario, responsable_extra: str | None = None) -> str:
    if usuario is not None:
        for attr in ("nombre_completo", "nombre", "full_name", "email"):
            valor = getattr(usuario, attr, None)
            if valor and str(valor).strip():
                return str(valor).strip()
    if responsable_extra and str(responsable_extra).strip():
        return str(responsable_extra).strip()
    return "Mostrador / Caja"


def _redondear_moneda(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _generar_numero_ticket(sucursal: Sucursal) -> str:
    tickets = Venta.objects.filter(sucursal=sucursal).values_list(
        "numero_ticket", flat=True
    )
    max_num = 1000
    for ticket in tickets:
        if not ticket:
            continue
        match = re.search(r"(\d+)$", str(ticket).strip())
        if match:
            max_num = max(max_num, int(match.group(1)))

    siguiente = max_num + 1
    while Venta.objects.filter(
        sucursal=sucursal, numero_ticket=f"POS-{siguiente}"
    ).exists():
        siguiente += 1

    return f"POS-{siguiente}"


def _calcular_estado_stock(stock_actual: int, stock_minimo: int) -> str:
    if stock_actual <= 0:
        return "agotado"
    if stock_actual <= max(0, int(stock_minimo or 0)):
        return "stock_bajo"  # <-- Ajustar si tu CHECK pide otro valor exacto
    return "normal"


@transaction.atomic
def registrar_venta(*, validated_data: dict) -> Venta:
    sucursal = validated_data.get("sucursal") or Sucursal.objects.first()
    if not sucursal:
        raise ValidationError(
            {"sucursal": "No hay ninguna sucursal registrada en el sistema."}
        )

    cliente = validated_data.get("cliente")
    usuario = validated_data.get("usuario")
    metodo_pago = validated_data["metodo_pago"]
    tasa_iva = Decimal(str(validated_data.get("tasa_iva", Decimal("0.16"))))
    items = validated_data["items"]

    product_ids = [item["producto_id"] for item in items]

    productos = {
        p.id: p for p in Producto.objects.filter(id__in=product_ids)
    }

    inventarios = {
        inv.producto_id: inv
        for inv in InventarioSucursal.objects.select_for_update().filter(
            sucursal=sucursal, producto_id__in=product_ids
        )
    }

    subtotal = Decimal("0.00")
    lineas_preparadas = []

    for item in items:
        pid = item["producto_id"]
        cantidad = int(item["cantidad"])
        producto = productos.get(pid)

        if not producto:
            raise ValidationError(
                {"items": f"El producto {pid} no existe en el catálogo."}
            )

        inventario = inventarios.get(pid)
        stock_actual = int(getattr(inventario, "stock_actual", 0) or 0)

        if not inventario or stock_actual < cantidad:
            raise ValidationError(
                {
                    "items": (
                        f"Stock insuficiente en '{sucursal.nombre}' para '{producto.nombre}': "
                        f"disponibles {stock_actual}, solicitados {cantidad}."
                    )
                }
            )

        precio_unitario = _redondear_moneda(
            Decimal(str(getattr(producto, "precio_venta", 0) or 0))
        )
        costo_unitario = _redondear_moneda(
            Decimal(str(getattr(producto, "precio_costo", 0) or 0))
        )
        subtotal_linea = _redondear_moneda(precio_unitario * Decimal(cantidad))

        subtotal += subtotal_linea
        lineas_preparadas.append(
            {
                "producto": producto,
                "inventario": inventario,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "costo_unitario": costo_unitario,
                "subtotal_linea": subtotal_linea,
                "nuevo_stock": stock_actual - cantidad,
            }
        )

    subtotal = _redondear_moneda(subtotal)
    impuesto_iva = _redondear_moneda(subtotal * tasa_iva)
    total = _redondear_moneda(subtotal + impuesto_iva)
    numero_ticket = _generar_numero_ticket(sucursal)

    venta = Venta.objects.create(
        sucursal=sucursal,
        cliente=cliente,
        usuario=usuario,
        numero_ticket=numero_ticket,
        subtotal=subtotal,
        impuesto_iva=impuesto_iva,
        total=total,
        metodo_pago=metodo_pago,
    )

    responsable_nombre = _resolver_nombre_responsable(
        usuario, validated_data.get("responsable_nombre")
    )

    for linea in lineas_preparadas:
        DetalleVenta.objects.create(
            venta=venta,
            producto=linea["producto"],
            cantidad=linea["cantidad"],
            precio_unitario=linea["precio_unitario"],
            costo_unitario=linea["costo_unitario"],
            subtotal_linea=linea["subtotal_linea"],
        )

        inventario = linea["inventario"]
        nuevo_stock = linea["nuevo_stock"]
        inventario.stock_actual = nuevo_stock
        inventario.estado_stock = _calcular_estado_stock(
            nuevo_stock, linea["producto"].stock_minimo
        )
        inventario.save(update_fields=["stock_actual", "estado_stock", "actualizado_en"])

        MovimientoInventario.objects.create(
            sucursal=sucursal,
            producto=linea["producto"],
            usuario=usuario,
            responsable_nombre=responsable_nombre,
            tipo_movimiento="venta_pos",
            cantidad_delta=-linea["cantidad"],
            motivo=f"Venta {venta.numero_ticket}",
        )

    if cliente is not None:
        compras_actuales = Decimal(str(getattr(cliente, "total_compras", 0) or 0))
        cliente.total_compras = _redondear_moneda(compras_actuales + total)
        campos_actualizar = ["total_compras"]

        if metodo_pago.strip().lower() in ("credito", "crédito", "fiado"):
            saldo_actual = Decimal(
                str(getattr(cliente, "saldo_pendiente", 0) or 0)
            )
            cliente.saldo_pendiente = _redondear_moneda(saldo_actual + total)
            campos_actualizar.append("saldo_pendiente")

        cliente.save(update_fields=campos_actualizar)

    return venta