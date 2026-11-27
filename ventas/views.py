from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Venta
from .serializers import CrearVentaSerializer, VentaSerializer
from .services import registrar_venta


class VentaListCreateView(APIView):
    def get(self, request):
        queryset = (
            Venta.objects.select_related("sucursal", "cliente", "usuario")
            .prefetch_related("detalles__producto")
            .order_by("-creado_en")
        )

        sucursal_id = request.query_params.get("sucursal")
        cliente_id = request.query_params.get("cliente")
        if sucursal_id:
            queryset = queryset.filter(sucursal_id=sucursal_id)
        if cliente_id:
            queryset = queryset.filter(cliente_id=cliente_id)

        serializer = VentaSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CrearVentaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        venta = registrar_venta(validated_data=serializer.validated_data)
        output = VentaSerializer(venta)
        return Response(output.data, status=status.HTTP_201_CREATED)


class VentaDetailView(APIView):
    def get(self, request, pk):
        venta = (
            Venta.objects.select_related("sucursal", "cliente", "usuario")
            .prefetch_related("detalles__producto")
            .filter(pk=pk)
            .first()
        )
        if not venta:
            return Response(
                {"detail": "Venta no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(VentaSerializer(venta).data, status=status.HTTP_200_OK)