from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Empresa, PerfilUsuario, Sucursal
from .serializers import (
    EmpresaSerializer,
    PerfilUsuarioSerializer,
    SucursalSerializer,
)


def _obtener_o_crear_empresa_principal() -> Empresa:
    empresa = Empresa.objects.order_by("id").first()
    if empresa is None:
        empresa = Empresa.objects.create(nombre_negocio="Smart POS")
    return empresa


class EmpresaDetalleView(APIView):
    def get(self, request):
        empresa = _obtener_o_crear_empresa_principal()
        serializer = EmpresaSerializer(empresa)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _actualizar(self, request, partial: bool):
        empresa = _obtener_o_crear_empresa_principal()
        serializer = EmpresaSerializer(empresa, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        return self._actualizar(request, partial=True)

    def put(self, request):
        return self._actualizar(request, partial=False)


class SucursalListView(generics.ListAPIView):
    serializer_class = SucursalSerializer

    def get_queryset(self):
        qs = Sucursal.objects.select_related("empresa").order_by("creado_en", "nombre")
        activa_param = (self.request.query_params.get("activa") or "").strip().lower()
        if activa_param in ("true", "1"):
            qs = qs.filter(activa=True)
        elif activa_param in ("false", "0"):
            qs = qs.filter(activa=False)
        return qs


class PerfilUsuarioListCreateView(generics.ListCreateAPIView):
    serializer_class = PerfilUsuarioSerializer

    def get_queryset(self):
        qs = PerfilUsuario.objects.select_related("empresa", "sucursal").order_by(
            "-creado_en", "nombre_completo"
        )
        rol = (self.request.query_params.get("rol") or "").strip()
        if rol and rol.lower() != "all":
            qs = qs.filter(rol__iexact=rol)
        return qs

    def perform_create(self, serializer):
        empresa = serializer.validated_data.get("empresa")
        if empresa is None:
            empresa = _obtener_o_crear_empresa_principal()
        sucursal = serializer.validated_data.get("sucursal")
        if sucursal is None:
            sucursal = Sucursal.objects.filter(empresa=empresa, activa=True).first()
        serializer.save(
            empresa=empresa,
            sucursal=sucursal,
            activo=serializer.validated_data.get("activo", True),
        )


class PerfilUsuarioDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PerfilUsuario.objects.select_related("empresa", "sucursal").all()
    serializer_class = PerfilUsuarioSerializer