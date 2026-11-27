# Estado del Proyecto y Hoja de Ruta MVP — Control Operativo Smart (Smart POS)

> **Propósito de este documento:** Servir como bitácora técnica, auditoría de UI/arquitectura y checklist vivo para retomar el desarrollo del MVP de **Smart POS** sin perder contexto entre sesiones.

---

## 1. Resumen del Estado Actual del Sistema

### Módulos Completados y Operativos (Frontend + Backend + Supabase)
- [x] **Catálogo / Productos (`catalogo` & `products-view.jsx`)**
  - CRUD completo conectado a Supabase (`managed = False`).
  - Soporte de categorías, SKU, código de barras, precios, márgenes y subida de imágenes.
- [x] **Inventario (`inventory-view.jsx`)**
  - Control de existencias, alertas de stock bajo / agotado, filtros por categoría y paginación.
- [x] **Clientes (`clientes` & `customers-view.jsx`)**
  - CRUD completo conectado a Supabase (`Cliente`, `ClienteSerializer`, `ClienteViewSet`).
  - Autogeneración blindada de `codigo_cliente` (`Cliente #001`, `#002`, ...) basada en el consecutivo máximo para evitar colisiones por eliminación.
  - Gestión de `total_compras`, ajuste de `saldo_pendiente` (créditos y abonos mediante `/ajustar-saldo/`), cambio de estado (`activo` / `inactivo`) y KPIs en tiempo real.
- [x] **Shell Principal (`dashboard-shell.jsx`)**
  - Navegación lateral colapsable, vista responsiva y fecha del sistema actualizada dinámicamente en tiempo real (`Intl.DateTimeFormat("es-CO")`).

---

## 2. Auditoría Crítica del Módulo de Ventas (`PosView`)

Antes de conectar el backend transaccional de **Ventas (POS)**, se realizó una revisión profesional de la interfaz actual (`pos-view.jsx`) para asegurar coherencia operativa con **Productos**, **Inventario**, **Clientes** y **Auditoría**.

### 2.1. Lo que YA está bien resuelto en la interfaz actual
- **Flujo de caja ágil e intuitivo:** Búsqueda por SKU/código de barras, filtros rápidos por categoría (*Todos*, *Bebidas*, *Abarrotes*, *Limpieza*) y cuadrícula de productos con badge de stock visible.
- **Gestión del Ticket de venta:** Lista clara de ítems seleccionados con controles de cantidad (`-` / `+`), eliminación individual y botón de reinicio (*Nueva venta*).
- **Cálculo financiero en pantalla:** Desglose de `Subtotal`, `IVA (16%)` y `Total` en tiempo real.
- **Modal de Procesar Pago:** Selección de `Método de pago`, campo de `Monto recibido` y cálculo automático de `Cambio a devolver` antes de confirmar el cierre de la venta.

### 2.2. Lo que cojea o requiere ajuste antes/durante la integración
- **Imágenes con placeholder estático (`IMG`):** Las tarjetas de productos muestran un recuadro gris `IMG` en lugar de renderizar la `imagen_url` real del catálogo (dejando `IMG` o ícono solo como fallback cuando el producto no tenga foto).
- **Validación de tope de stock en el carrito:** El botón `+` dentro del *Ticket de venta* debe impedir agregar más unidades de las disponibles en `stock_actual`, y los productos con stock `0` deben bloquearse o marcarse como agotados.
- **Unificación de estados visuales de stock:** Alinear los colores y umbrales de los badges (`Agotado`, `Stock bajo`, `Normal`) con los ya usados en **Inventario**.
- **Ícono de cámara en el buscador:** Evaluar si se oculta en el MVP para no generar expectativa de escaneo por webcam si solo se usará lector USB / teclado.
- **Switch "Imprimir comprobante / ticket":** Asegurar que al activarlo genere al menos un modal/vista de recibo imprimible (`window.print()`) tras confirmar la venta, evitando un control sin efecto real.
- **Coherencia en formato de moneda:** Unificar el formateo monetario en toda la aplicación (en *Clientes* se usa formato colombiano sin decimales innecesarios y en *Ventas* aparece con dos decimales `$19.72` / `$2,426.28`).

### 2.3. Componentes y Datos Faltantes para Conectar Ventas de Punta a Punta
1. **Selector / Vinculación de Cliente en el Ticket:**
   - Permitir seleccionar un cliente registrado (desde el módulo `clientes`) o dejar *"Consumidor final / Mostrador"*.
   - **Dato clave (`cliente_id`):** Necesario para incrementar `total_compras` en la tabla `clientes` y, si se habilita pago a crédito/fiado, sumar automáticamente al `saldo_pendiente` del cliente.
2. **Comprobante / Confirmación Post-Venta:**
   - Mostrar feedback con el consecutivo real de la venta (ej. `#POS-1049`), limpiar el carrito y ofrecer vista de ticket si el switch de impresión está activo.
3. **Contexto de Empresa / Sucursal (`empresa_id`):**
   - Vincular la venta a la `empresa` activa en backend/frontend para mantener integridad multiempresa en Supabase.
4. **Integridad Transaccional y Auditoría (`transaction.atomic()`):**
   - Al confirmar una venta (`POST /api/ventas/...`), el backend debe ejecutar en una sola transacción atómica:
     1. Crear cabecera y detalle de la venta.
     2. Descontar `stock_actual` de cada producto vendido en `catalogo`.
     3. Actualizar `total_compras` (y `saldo_pendiente` si aplica) en `clientes`.
     4. Registrar el movimiento de salida en `auditoria` para trazabilidad completa.

---

## 3. Checklist Maestro para Retomar el Desarrollo

### Fase A: Ventas (POS) — Siguiente Paso Inmediato
- [x] Revisar el código fuente actual de `pos-view.jsx` y esquema de tablas `ventas` en Supabase.
- [x] Conectar `pos-view.jsx` con el catálogo real (`fetchProductos` / `fetchCategorias`) y clientes reales (`fetchClientes`).
- [x] Añadir selector de cliente (o *Consumidor final*), validación de `stock_actual` máximo en carrito y renderizado de `imagenUrl` con fallback.
- [x] Implementar backend de `ventas` (`models.py`, `serializers.py`, `views.py`, `urls.py` y registro en `core/urls.py`) con transacción atómica para descontar stock y actualizar cliente.
- [x] Probar venta completa en local y verificar impacto en Supabase (`ventas`, `productos` e `inventario`, y `clientes`).

### Fase B: Auditoría (`MovementsView` & app `auditoria`)
- [ ] Conectar registro automático de movimientos (ventas POS, entradas, salidas y ajustes de inventario).
- [ ] Conectar la vista `MovementsView` al backend real con filtros por tipo de movimiento, fecha y búsqueda.

### Fase C: Dashboard Analítico y Configuración (`analitica` & `organizacion`)
- [ ] Reemplazar KPIs, gráfico semanal, predicción de agotamiento y transacciones recientes estáticas de `DashboardContent` por endpoints reales.
- [ ] Conectar `SettingsView` con los parámetros de la empresa/sucursal y gestión básica de usuarios/roles.

### Fase D: Despliegue Final y Entrega de Asignatura
- [ ] Hacer `commit` y `push` de todos los módulos hacia el repositorio remoto.
- [ ] Verificar build y funcionamiento en producción (Backend Docker/Cloud + Frontend Vercel + Supabase).
- [ ] Realizar prueba integral de extremo a extremo y actualizar documentación de entrega.
```

¡Buen provecho, mi hermano! Cuando regreses me avisas y arrancamos directo revisando `pos-view.jsx` y la estructura de tus tablas de `ventas` en Supabase.