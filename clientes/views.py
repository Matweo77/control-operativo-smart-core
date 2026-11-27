from decimal import Decimal, InvalidOperation
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Cliente
from .serializers import ClienteSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    serializer_class = ClienteSerializer

    def get_queryset(self):
        queryset = Cliente.objects.all().order_by("-creado_en")
        params = self.request.query_params

        empresa_id = params.get("empresa_id")
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)

        estado = params.get("estado")
        if estado and estado.lower() not in ("todos", "all"):
            queryset = queryset.filter(estado__iexact=estado)

        con_credito = params.get("con_credito")
        if con_credito and con_credito.lower() in ("true", "1"):
            queryset = queryset.filter(saldo_pendiente__gt=0)

        search = params.get("search") or params.get("q")
        if search:
            queryset = queryset.filter(
                Q(nombre_completo__icontains=search)
                | Q(documento__icontains=search)
                | Q(telefono__icontains=search)
                | Q(email__icontains=search)
                | Q(codigo_cliente__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"], url_path="ajustar-saldo")
    def ajustar_saldo(self, request, pk=None):
        cliente = self.get_object()
        try:
            monto = Decimal(str(request.data.get("monto", "0")))
        except (InvalidOperation, TypeError):
            return Response(
                {"detail": "El campo 'monto' debe ser un número válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tipo = (request.data.get("tipo") or "credito").strip().lower()
        if tipo == "abono":
            nuevo_saldo = max(Decimal("0.00"), (cliente.saldo_pendiente or Decimal("0.00")) - abs(monto))
        else:
            nuevo_saldo = max(Decimal("0.00"), (cliente.saldo_pendiente or Decimal("0.00")) + abs(monto))

        cliente.saldo_pendiente = nuevo_saldo
        cliente.save(update_fields=["saldo_pendiente"])
        serializer = self.get_serializer(cliente)
        return Response(serializer.data, status=status.HTTP_200_OK)