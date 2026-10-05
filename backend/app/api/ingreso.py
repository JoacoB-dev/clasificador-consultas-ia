from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencias import cola_consultas
from app.cola import ColaConsultas
from app.db import obtener_sesion
from app.esquemas import ConsultaImportada, ResultadoImportacion
from app.ingreso.eml import ErrorEml, leer_eml
from app.modelos import Usuario
from app.seguridad import usuario_actual
from app.servicios import crear_consulta

router = APIRouter(prefix="/api/ingreso", tags=["ingreso"])

MAX_ARCHIVOS = 50
MAX_BYTES_EML = 1_000_000  # 1 MB por mail alcanza para texto


@router.post("/eml", response_model=ResultadoImportacion)
async def importar_eml(
    archivos: list[UploadFile] = File(...),
    sesion: Session = Depends(obtener_sesion),
    cola: ColaConsultas = Depends(cola_consultas),
    _: Usuario = Depends(usuario_actual),
) -> ResultadoImportacion:
    """Importa uno o varios archivos .eml (simula la casilla de mail)."""
    if len(archivos) > MAX_ARCHIVOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Máximo {MAX_ARCHIVOS} archivos")
    resultado = ResultadoImportacion(creadas=[], duplicadas=0, errores=[])
    for archivo in archivos:
        nombre = archivo.filename or "(sin nombre)"
        contenido = await archivo.read(MAX_BYTES_EML + 1)
        if len(contenido) > MAX_BYTES_EML:
            resultado.errores.append(f"{nombre}: supera 1 MB")
            continue
        try:
            datos = leer_eml(contenido)
        except ErrorEml as error:
            resultado.errores.append(f"{nombre}: {error}")
            continue
        _sumar(resultado, crear_consulta(sesion, datos, cola))
    return resultado


@router.post("/json", response_model=ResultadoImportacion)
def importar_json(
    consultas: list[ConsultaImportada],
    sesion: Session = Depends(obtener_sesion),
    cola: ColaConsultas = Depends(cola_consultas),
    _: Usuario = Depends(usuario_actual),
) -> ResultadoImportacion:
    """Importa un lote de consultas en JSON (validadas con Pydantic antes de entrar)."""
    if len(consultas) > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Máximo 500 consultas por lote")
    resultado = ResultadoImportacion(creadas=[], duplicadas=0, errores=[])
    for datos in consultas:
        _sumar(resultado, crear_consulta(sesion, datos, cola))
    return resultado


def _sumar(resultado: ResultadoImportacion, salida) -> None:
    if salida.duplicada:
        resultado.duplicadas += 1
    else:
        resultado.creadas.append(salida)
