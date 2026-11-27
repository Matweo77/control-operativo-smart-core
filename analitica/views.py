import re
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from auditoria.models import MovimientoInventario
from catalogo.models import InventarioSucursal, Producto
from ventas.models import DetalleVenta, Venta
from .models import PrediccionAgotamiento


def _redondear_moneda(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class DashboardResumenView(APIView):
    def get(self, request):
        try:
            dias = int(request.query_params.get("dias", 7))
        except (TypeError, ValueError):
            dias = 7
        if dias not in (7, 14, 30):
            dias = 7

        sucursal_id = (request.query_params.get("sucursal") or "").strip()

        ahora_local = timezone.localtime(timezone.now())
        hoy = ahora_local.date()

        ventas_qs = Venta.objects.select_related(
            "sucursal", "cliente", "usuario"
        ).order_by("-creado_en")
        if sucursal_id:
            ventas_qs = ventas_qs.filter(sucursal_id=sucursal_id)

        ventas_lista = list(ventas_qs)

        # 1. Ventas del día y utilidad estimada
        ventas_hoy_total = Decimal("0.00")
        tickets_hoy = 0
        ventas_acumuladas_total = Decimal("0.00")
        venta_ids_hoy = []
        todos_venta_ids = []

        for v in ventas_lista:
            monto = Decimal(str(v.total or 0))
            ventas_acumuladas_total += monto
            todos_venta_ids.append(v.id)
            fecha_v = timezone.localtime(v.creado_en).date() if v.creado_en else None
            if fecha_v == hoy:
                ventas_hoy_total += monto
                tickets_hoy += 1
                venta_ids_hoy.append(v.id)

        ids_para_margen = venta_ids_hoy if venta_ids_hoy else todos_venta_ids
        utilidad_estimada = Decimal("0.00")
        subtotal_base_margen = Decimal("0.00")

        if ids_para_margen:
            detalles = DetalleVenta.objects.filter(venta_id__in=ids_para_margen)
            for det in detalles:
                cant = Decimal(str(det.cantidad or 0))
                p_unit = Decimal(str(det.precio_unitario or 0))
                c_unit = Decimal(str(det.costo_unitario or 0))
                utilidad_estimada += (p_unit - c_unit) * cant
                subtotal_base_margen += p_unit * cant

        utilidad_estimada = _redondear_moneda(utilidad_estimada)
        margen_porcentaje = (
            float(
                ((utilidad_estimada / subtotal_base_margen) * Decimal("100")).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
            )
            if subtotal_base_margen > 0
            else 0.0
        )

        # 2. Productos en catálogo
        productos_qs = Producto.objects.all()
        productos_total = productos_qs.count()
        productos_activos = productos_qs.filter(activo=True).count()

        # 3. Alertas de stock (agotado / stock_bajo)
        inv_qs = InventarioSucursal.objects.select_related("producto", "sucursal")
        if sucursal_id:
            inv_qs = inv_qs.filter(sucursal_id=sucursal_id)

        inventarios_lista = list(inv_qs)
        agotados_count = 0
        stock_bajo_count = 0
        for inv in inventarios_lista:
            actual = int(inv.stock_actual or 0)
            minimo = int(getattr(inv.producto, "stock_minimo", 5) or 5)
            estado = (inv.estado_stock or "").strip().lower()
            if actual <= 0 or estado == "agotado":
                agotados_count += 1
            elif actual <= minimo or estado in ("stock_bajo", "bajo"):
                stock_bajo_count += 1

        alertas_stock_count = agotados_count + stock_bajo_count

        # 4. Serie diaria de ventas (últimos N días)
        dias_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        totales_por_dia = {}
        for v in ventas_lista:
            if not v.creado_en:
                continue
            f_dia = timezone.localtime(v.creado_en).date()
            totales_por_dia[f_dia] = totales_por_dia.get(
                f_dia, Decimal("0.00")
            ) + Decimal(str(v.total or 0))

        inicio_rango = hoy - timedelta(days=dias - 1)
        ventas_diarias = []
        for offset in range(dias):
            dia_actual = inicio_rango + timedelta(days=offset)
            etiqueta = (
                dias_es[dia_actual.weekday()]
                if dias == 7
                else dia_actual.strftime("%d/%m")
            )
            monto_dia = _redondear_moneda(
                totales_por_dia.get(dia_actual, Decimal("0.00"))
            )
            ventas_diarias.append(
                {
                    "date": dia_actual.isoformat(),
                    "day": etiqueta,
                    "sales": float(monto_dia),
                }
            )

        # 5. Predicciones de agotamiento (BD primero; si está vacía, cálculo real por rotación)
        pred_qs = PrediccionAgotamiento.objects.select_related(
            "producto", "sucursal"
        ).order_by("dias_estimados", "unidades_restantes")
        if sucursal_id:
            pred_qs = pred_qs.filter(sucursal_id=sucursal_id)

        predicciones = [
            {
                "id": str(p.id),
                "name": getattr(p.producto, "nombre", "Producto"),
                "sku": getattr(p.producto, "sku", ""),
                "stock": int(p.unidades_restantes or 0),
                "days": int(p.dias_estimados or 0),
                "velocity": str(p.velocidad_rotacion or "Normal"),
            }
            for p in pred_qs[:5]
        ]

        if not predicciones and inventarios_lista:
            ventana_dias = 14
            hace_ventana = ahora_local - timedelta(days=ventana_dias)
            salidas_qs = MovimientoInventario.objects.filter(
                cantidad_delta__lt=0,
                creado_en__gte=hace_ventana,
            )
            if sucursal_id:
                salidas_qs = salidas_qs.filter(sucursal_id=sucursal_id)

            unidades_consumidas = {}
            for m in salidas_qs:
                clave = (str(m.sucursal_id), str(m.producto_id))
                unidades_consumidas[clave] = unidades_consumidas.get(
                    clave, 0
                ) + abs(int(m.cantidad_delta or 0))

            calculadas = []
            for inv in inventarios_lista:
                stock_act = int(inv.stock_actual or 0)
                if stock_act <= 0:
                    continue
                clave = (str(inv.sucursal_id), str(inv.producto_id))
                consumo_total = unidades_consumidas.get(clave, 0)
                if consumo_total <= 0:
                    continue

                consumo_diario = consumo_total / float(ventana_dias)
                dias_est = max(1, round(stock_act / consumo_diario))
                if dias_est > 30:
                    continue

                if consumo_diario >= 2.0 or dias_est <= 3:
                    velocidad = "Alta"
                elif consumo_diario >= 0.5 or dias_est <= 7:
                    velocidad = "Media"
                else:
                    velocidad = "Baja"

                calculadas.append(
                    {
                        "id": f"calc-{inv.id}",
                        "name": getattr(inv.producto, "nombre", "Producto"),
                        "sku": getattr(inv.producto, "sku", ""),
                        "stock": stock_act,
                        "days": dias_est,
                        "velocity": velocidad,
                    }
                )

            calculadas.sort(key=lambda x: (x["days"], x["stock"]))
            predicciones = calculadas[:4]

        # 6. Transacciones recientes (últimas 6 ventas) con responsable resuelto
        recientes_qs = ventas_lista[:6]
        tickets_recientes = {
            v.numero_ticket for v in recientes_qs if v.numero_ticket
        }
        responsables_por_ticket = {}
        if tickets_recientes:
            movs = MovimientoInventario.objects.filter(
                tipo_movimiento="venta_pos",
                responsable_nombre__isnull=False,
            ).exclude(responsable_nombre="")
            for m in movs:
                if not m.motivo:
                    continue
                match = re.search(r"(POS-\d+)", m.motivo)
                if match and match.group(1) in tickets_recientes:
                    responsables_por_ticket.setdefault(
                        (str(m.sucursal_id), match.group(1)),
                        m.responsable_nombre,
                    )

        transacciones_recientes = []
        for v in recientes_qs:
            hora_str = (
                timezone.localtime(v.creado_en).strftime("%H:%M")
                if v.creado_en
                else "—"
            )
            cliente_nombre = None
            if v.cliente is not None:
                cliente_nombre = getattr(
                    v.cliente, "nombre_completo", None
                ) or getattr(v.cliente, "nombre", None)

            responsable_nombre = None
            if v.usuario is not None:
                responsable_nombre = getattr(
                    v.usuario, "nombre_completo", None
                ) or getattr(v.usuario, "nombre", None)
            if not responsable_nombre:
                responsable_nombre = responsables_por_ticket.get(
                    (str(v.sucursal_id), v.numero_ticket),
                    "Mostrador / Caja",
                )

            transacciones_recientes.append(
                {
                    "id": str(v.id),
                    "ticket": v.numero_ticket or "—",
                    "hora": hora_str,
                    "cliente": cliente_nombre or "Consumidor final",
                    "responsable": responsable_nombre,
                    "metodo_pago": (v.metodo_pago or "—").capitalize(),
                    "total": float(_redondear_moneda(Decimal(str(v.total or 0)))),
                }
            )

        return Response(
            {
                "kpis": {
                    "ventas_hoy": float(_redondear_moneda(ventas_hoy_total)),
                    "tickets_hoy": tickets_hoy,
                    "ventas_acumuladas": float(
                        _redondear_moneda(ventas_acumuladas_total)
                    ),
                    "utilidad_estimada": float(utilidad_estimada),
                    "margen_porcentaje": margen_porcentaje,
                    "utilidad_es_de_hoy": len(venta_ids_hoy) > 0,
                    "productos_total": productos_total,
                    "productos_activos": productos_activos,
                    "alertas_stock": alertas_stock_count,
                    "agotados": agotados_count,
                    "stock_bajo": stock_bajo_count,
                },
                "dias_serie": dias,
                "ventas_diarias": ventas_diarias,
                "predicciones": predicciones,
                "transacciones_recientes": transacciones_recientes,
            },
            status=status.HTTP_200_OK,
        )