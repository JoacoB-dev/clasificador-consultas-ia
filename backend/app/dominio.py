"""Valores de dominio compartidos (enums) entre la API, el worker y los clasificadores."""

from enum import StrEnum


class Categoria(StrEnum):
    ENVIO = "envio"  # demoras, seguimiento, paquete no llegó
    PRODUCTO_DEFECTUOSO = "producto_defectuoso"  # llegó roto, no funciona
    DEVOLUCION = "devolucion"  # cambios, arrepentimiento, devoluciones
    FACTURACION = "facturacion"  # facturas, cobros, pagos, reintegros
    CONSULTA_PRODUCTO = "consulta_producto"  # stock, precio, características
    CUENTA = "cuenta"  # acceso, datos personales, contraseña
    OTRO = "otro"


class Urgencia(StrEnum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class Sentimiento(StrEnum):
    NEGATIVO = "negativo"
    NEUTRO = "neutro"
    POSITIVO = "positivo"


class Canal(StrEnum):
    FORMULARIO = "formulario"
    EMAIL = "email"


class EstadoConsulta(StrEnum):
    PENDIENTE = "pendiente"  # recibida, esperando al worker
    EN_PROCESO = "en_proceso"  # el worker la está clasificando
    CLASIFICADA = "clasificada"  # lista para revisión humana
    APROBADA = "aprobada"  # un humano aprobó la respuesta
    ERROR = "error"  # falló la clasificación (se puede reprocesar)


class Rol(StrEnum):
    OPERADOR = "operador"
    SUPERVISOR = "supervisor"


ORDEN_URGENCIA = [Urgencia.BAJA, Urgencia.MEDIA, Urgencia.ALTA, Urgencia.CRITICA]
