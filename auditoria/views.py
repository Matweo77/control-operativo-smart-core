import re
from collections import defaultdict
from rest_framework import generics
from catalogo.models import InventarioSucursal
from ventas.models import Venta
from .models import MovimientoInventario
from .serializers import MovimientoInventarioSerializer


class MovimientoInventarioListView(generics.ListAPIView):
    serializer_class = MovimientoInventarioSerializer

    def get_queryset(self):
        queryset = (
            MovimientoInventario.objects.select_related(
                "sucursal", "producto", "usuario"
            )
            .all()
            .order_by("-creado_en")
        )

        tipo = (self.request.query_params.get("tipo_movimiento") or "").strip()
        if tipo and tipo != "all":
            queryset = queryset.filter(tipo_movimiento=tipo)

        responsable = (self.request.query_params.get("responsable") or "").strip()
        if responsable and responsable != "all":
            queryset = queryset.filter(responsable_nombre__iexact=responsable)

        fecha_inicio = (self.request.query_params.get("fecha_inicio") or "").strip()
        if fecha_inicio:
            queryset = queryset.filter(creado_en__date__gte=fecha_inicio)

        fecha_fin = (self.request.query_params.get("fecha_fin") or "").strip()
        if fecha_fin:
            queryset = queryset.filter(creado_en__date__lte=fecha_fin)

        movimientos = list(queryset)

        # 1. Resolver cliente_nombre para movimientos venta_pos
        tickets = set()
        for mov in movimientos:
            if mov.tipo_movimiento == "venta_pos" and mov.motivo:
                match = re.search(r"(POS-\d+)", mov.motivo)
                if match:
                    tickets.add(match.group(1))

        clientes_por_ticket = {}
        if tickets:
            ventas = Venta.objects.select_related("cliente").filter(
                numero_ticket__in=tickets, cliente__isnull=False
            )
            for v in ventas:
                nombre_cli = getattr(v.cliente, "nombre_completo", None) or getattr(
                    v.cliente, "nombre", None
                )
                if nombre_cli:
                    clientes_por_ticket[(str(v.sucursal_id), v.numero_ticket)] = (
                        nombre_cli
                    )

        # 2. Reconstruir stock_antes y stock_despues por (sucursal_id, producto_id)
        pares = {
            (mov.sucursal_id, mov.producto_id)
            for mov in movimientos
            if mov.sucursal_id and mov.producto_id
        }
        stocks_actuales = {}
        if pares:
            sucursal_ids = {s_id for s_id, _ in pares}
            producto_ids = {p_id for _, p_id in pares}
            inventarios = InventarioSucursal.objects.filter(
                sucursal_id__in=sucursal_ids, producto_id__in=producto_ids
            )
            for inv in inventarios:
                stocks_actuales[(inv.sucursal_id, inv.producto_id)] = int(
                    inv.stock_actual or 0
                )

        # Solo calculamos cadena exacta si no hay filtros activos que oculten movimientos intermedios
        sin_filtros_parciales = not any(
            [
                bool(tipo and tipo != "all"),
                bool(responsable and responsable != "all"),
                bool(fecha_inicio),
                bool(fecha_fin),
            ]
        )

        cursor_stock = dict(stocks_actuales)
        for mov in movimientos:
            cliente_nombre = None
            if mov.tipo_movimiento == "venta_pos" and mov.motivo:
                match = re.search(r"(POS-\d+)", mov.motivo)
                if match:
                    cliente_nombre = clientes_por_ticket.get(
                        (str(mov.sucursal_id), match.group(1))
                    )
            mov._cliente_nombre_resuelto = cliente_nombre

            par = (mov.sucursal_id, mov.producto_id)
            if sin_filtros_parciales and par in cursor_stock:
                despues = cursor_stock[par]
                delta = int(mov.cantidad_delta or 0)
                antes = despues - delta
                mov._stock_despues_resuelto = despues
                mov._stock_antes_resuelto = antes
                cursor_stock[par] = antes
            else:
                mov._stock_despues_resuelto = None
                mov._stock_antes_resuelto = None

        return movimientos