[English version](README.en.md)

# Clasificador de consultas con IA

Proyecto de portfolio de **Joaquin Alejandro Bobbio** (estudiante de la Licenciatura en Programación, UNAHUR). Todos los datos son **de ejemplo**: la tienda "Bazar La Esquina", los clientes, los pedidos y los mails son inventados.

Una pyme ficticia recibe consultas y reclamos por el **formulario web** y por **mail** (simulado importando archivos `.eml` o JSON). Cada consulta entra a una **cola en Redis**; un **worker** la toma y le pide a un **LLM (Claude)** que devuelva un **JSON validado con Pydantic** con categoría, urgencia, sentimiento, resumen, datos extraídos (nº de pedido, producto, monto…) y un borrador de respuesta. Después se aplican **reglas de negocio** deterministas (área asignada y SLA). Una persona revisa todo en un **panel React + TypeScript**: filtra la bandeja, edita el borrador, corrige la categoría y aprueba. Las correcciones quedan guardadas y alimentan una **métrica de precisión por categoría**.

> **Sin `ANTHROPIC_API_KEY` el sistema usa un clasificador simulado** (reglas y palabras clave, determinista). Así la demo, el worker y todos los tests funcionan sin clave y sin gastar. Con la clave cargada, el mismo flujo usa Claude. En el panel y en `/api/salud` siempre se ve cuál está activo.

![Bandeja](docs/capturas/01-bandeja.png)

## Por qué este proyecto

Lo armé apuntando a avisos de **desarrollador Python/FastAPI**, **full stack con IA** y **AI Automation Developer**, que piden Python, FastAPI, React, TypeScript, PostgreSQL, Redis, Docker, APIs REST y uso de LLMs. Mis otros proyectos ya cubren un ETL con pandas + FastAPI + Streamlit y un tutor con IA en Node; este se enfoca en otra cosa: **automatizar un proceso de negocio con un LLM**, con salida estructurada, cola de trabajos, revisión humana y medición de qué tan bien anda el modelo.

## Stack

| Parte | Tecnologías |
|---|---|
| API | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, JWT (PyJWT + bcrypt) |
| Cola / worker | Redis + RQ |
| LLM | Claude API con el SDK oficial `anthropic` (modelo por defecto `claude-sonnet-5-5`, configurable) |
| Base de datos | PostgreSQL 16 (JSONB para datos extraídos y reglas aplicadas) |
| Panel | React 19 + TypeScript + Vite, React Router |
| Calidad | pytest (unitarios + integración con Postgres y Redis reales), ruff, Vitest, oxlint |
| Infra | Docker, docker compose, GitHub Actions |

## Arquitectura

```
 Formulario web ─┐                                        ┌──────────────┐
 Import .eml/JSON┼─► FastAPI ──► PostgreSQL (consulta     │  Claude API  │
                 │      │         'pendiente')            │ (o simulado) │
                 │      └──► Redis (cola RQ) ──► Worker ──┤              │
                 │                                │       └──────────────┘
                 │                                ▼
                 │            JSON validado con Pydantic ──► Reglas de negocio
                 │                                            (área + SLA)
                 │                                │
 Panel React ◄───┴──── API REST (JWT) ◄───────────┘  consulta 'clasificada'
  (bandeja, detalle, corregir, aprobar, métricas)
```

Estados de una consulta: `pendiente` → `en_proceso` → `clasificada` → `aprobada` (o `error`, que se puede reprocesar).

## Cómo correrlo

### Opción 1: Docker (recomendada, también en Windows 10 con Docker Desktop)

```bash
cp .env.example .env          # en Windows: copy .env.example .env
docker compose up --build
```

- Panel: http://localhost:5174 (el nginx del contenedor también hace de proxy a la API)
- API: http://localhost:8083 — documentación interactiva en http://localhost:8083/docs
- Formulario público de la tienda: http://localhost:5174/contacto

Al arrancar, la API aplica las migraciones y carga la demo (usuarios + 14 consultas ya clasificadas, algunas revisadas). Para usar Claude, poné tu clave en `.env` (`ANTHROPIC_API_KEY=...`) antes de levantar. Ojo: con clave, la carga de la demo también clasifica esas 14 consultas con Claude.

En Windows 10: instalá Docker Desktop (con WSL 2), abrí PowerShell en la carpeta del proyecto y corré los mismos comandos. Si los puertos 8083 o 5174 están ocupados, cambialos en `docker-compose.yml`.

Para apagar: `docker compose down` (agregá `-v` para borrar también la base).

### Opción 2: sin Docker para la app

Necesitás PostgreSQL y Redis. Si no los tenés instalados, levantalos con Docker en puertos que no choquen con otros:

```bash
docker run -d --name consultas-pg -e POSTGRES_USER=consultas -e POSTGRES_PASSWORD=consultas \
  -e POSTGRES_DB=consultas_dev -p 54322:5432 postgres:16-alpine
docker run -d --name consultas-redis-dev -p 63792:6379 redis:7-alpine
docker exec consultas-pg psql -U consultas -c "create database consultas_test"
```

Backend (Linux / macOS):

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --port 8083 --reload
# en otra terminal, el worker:
rq worker --url redis://localhost:63792/0 consultas
```

En Windows (PowerShell): `py -3.11 -m venv .venv`, `.venv\Scripts\Activate.ps1` y el resto igual. **El worker de RQ no corre nativo en Windows** (usa `fork` y señales de Unix): en Windows corré el worker con `docker compose up worker` o desde WSL. No lo probé en una máquina Windows real.

Panel:

```bash
cd frontend
npm install
npm run dev      # http://localhost:5174 (redirige /api a localhost:8083)
```

### Usuarios demo

| Email | Contraseña | Rol |
|---|---|---|
| supervisor@demo.local | demo1234 | supervisor (ve métricas y puede reencolar) |
| operador@demo.local | demo1234 | operador (revisa, corrige y aprueba) |

## Pantallas

| Pantalla | Qué hace |
|---|---|
| **Bandeja** (`/`) | Lista ordenada por vencimiento de SLA. Filtros por estado, categoría, urgencia, área, búsqueda de texto y "SLA vencido". Se refresca sola cada 10 s porque el worker trabaja en segundo plano. |
| **Detalle** (`/consultas/:id`) | Mensaje original, borrador editable, corrección de categoría/urgencia, datos extraídos, reglas aplicadas, historial de correcciones, aprobar y reprocesar. |
| **Importar** (`/importar`) | Subida de `.eml` y de lotes JSON (simula la casilla de mail). |
| **Métricas** (`/metricas`, solo supervisor) | Exactitud global, precisión y recall por categoría, matriz de confusión y uso del LLM (tokens, costo estimado, duración). |
| **Formulario público** (`/contacto`) | El formulario de contacto de la tienda, sin login. |

![Detalle de una consulta](docs/capturas/02-detalle.png)

![Métricas](docs/capturas/03-metricas.png)

![Formulario público](docs/capturas/04-formulario-publico.png)

## Endpoints principales

| Método y ruta | Auth | Descripción |
|---|---|---|
| `POST /api/auth/login` | — | Devuelve el JWT y el usuario |
| `GET /api/auth/yo` | JWT | Usuario actual |
| `POST /api/consultas/formulario` | — | Formulario público: guarda y encola |
| `GET /api/consultas` | JWT | Bandeja con filtros (`estado`, `categoria`, `urgencia`, `area`, `canal`, `q`, `sla_vencido`) y paginado |
| `GET /api/consultas/{id}` | JWT | Detalle con correcciones |
| `PATCH /api/consultas/{id}` | JWT | Editar borrador, corregir categoría o urgencia (queda registrado) |
| `POST /api/consultas/{id}/aprobar` | JWT | Aprueba la respuesta final |
| `POST /api/consultas/{id}/reprocesar` | JWT | La vuelve a mandar a la cola |
| `POST /api/consultas/reencolar-pendientes` | supervisor | Reencola todo lo pendiente (por si Redis estuvo caído) |
| `POST /api/ingreso/eml` | JWT | Importa uno o varios `.eml` (multipart) |
| `POST /api/ingreso/json` | JWT | Importa un lote JSON (no duplica por `id_externo`) |
| `GET /api/metricas/resumen` | JWT | Conteos por estado/área, SLA vencidos y clasificador activo |
| `GET /api/metricas/precision` | supervisor | Precisión y recall por categoría + matriz de confusión (`?clasificador=` para filtrar) |
| `GET /api/metricas/uso-llm` | supervisor | Tokens, costo estimado y duración por modelo |
| `GET /api/salud` | — | Estado de la base, Redis y clasificador activo |

## Decisiones técnicas

- **RQ y no Celery ni arq.** Hay una sola tarea (clasificar una consulta), sincrónica. RQ solo necesita Redis, se levanta con un comando y se testea fácil con un worker en modo *burst*. Celery agrega configuración que acá no aporta; arq obliga a que todo sea async y el SDK y SQLAlchemy los uso sincrónicos. La contra de RQ: no corre nativo en Windows.
- **A la cola va solo el id.** El worker lee la consulta de la base, así un reintento siempre trabaja con datos actuales y no hay que serializar objetos.
- **Salida estructurada + Pydantic.** El JSON Schema se genera desde el mismo modelo Pydantic (`ResultadoClasificacion`) y se manda en `output_config.format`, así Claude responde con ese formato. Igual la respuesta se valida con Pydantic antes de guardarla; si no valida, cuenta como intento fallido y se reintenta. Uso salida estructurada y no "tool use forzado" porque los modelos actuales no aceptan `tool_choice` forzado y para pedir un JSON es lo más directo.
- **Reintentos propios con backoff exponencial + jitter** (429, 5xx, timeouts y JSON inválido). Los errores 400 y los rechazos del modelo (`refusal`) no se reintentan porque darían lo mismo. Desactivé los reintentos del SDK (`max_retries=0`) para no reintentar dos veces y poder contar los intentos.
- **Timeout configurable** (`LLM_TIMEOUT_SEGUNDOS`, 30 s por defecto).
- **Tokens y costo.** Cada llamada queda en la tabla `usos_llm` (tokens de entrada y salida de todos los intentos, costo estimado con precios de referencia por millón de tokens, duración, éxito o error). Si la API respondió con otro modelo por el *fallback*, el costo se calcula con ese modelo.
- **Fallback del lado del servidor** (`LLM_FALLBACK_SERVIDOR=true`): si el modelo rechaza una consulta por políticas de seguridad, la API la reintenta con otro modelo en la misma llamada. Se puede apagar.
- **Esfuerzo bajo** (`LLM_ESFUERZO=low`): clasificar no necesita razonamiento profundo y así baja el costo y la latencia. Es configurable.
- **Las reglas de negocio no las decide el LLM.** El modelo propone categoría y urgencia; el área y el SLA salen de reglas en Python, fáciles de auditar y testear (por ejemplo: si se menciona Defensa del Consumidor o una denuncia, escala a Supervisión con urgencia crítica; facturación con monto ≥ $500.000 es al menos alta). Cada consulta guarda la lista de reglas que se le aplicaron.
- **Prompt injection.** El texto del cliente va entre etiquetas `<consulta>` y el prompt aclara que es un dato a analizar, no instrucciones. El set de evaluación incluye un caso que intenta manipular la respuesta. Además, nada se manda solo: siempre hay aprobación humana.
- **Medir la precisión con el uso real.** Se guarda lo que dijo el modelo (`categoria_modelo`) y lo que quedó después de la revisión. Aprobar sin cambios cuenta como acierto; corregir, como error. Con eso salen precisión, recall y matriz de confusión. Cada corrección queda en la tabla `correcciones` con usuario y fecha.
- **Si Redis se cae** la consulta se guarda igual como `pendiente` y se puede reencolar después (endpoint de supervisor).
- **Dedupe de mails** por `Message-ID` (`id_externo` único).
- **Validación de mails simple a propósito**: `email-validator` rechaza dominios reservados como `.local` o `.example`, que justamente usa la demo.

## Tests

```bash
cd backend
pytest -v                 # 84 tests: unitarios + integración (necesita Postgres y Redis)
pytest -m "not integracion"   # solo los unitarios, sin base ni Redis
ruff check . && ruff format --check .

cd ../frontend
npm test                  # Vitest (funciones de formato)
npm run lint && npm run build
```

Por defecto los tests usan la base `consultas_test` en `localhost:54322` y la DB 15 de Redis en `localhost:63792`; se cambian con `TEST_DATABASE_URL` y `TEST_REDIS_URL`. Los tests de integración recrean el esquema corriendo las migraciones de Alembic.

Qué cubren:

- **Clasificador con Claude, con un cliente falso** (no hay clave ni red en los tests): parámetros enviados (modelo, schema, fallback), reintentos con backoff ante 429 y timeout, reintento por JSON inválido sumando tokens, agotar reintentos, 400 sin reintento, `refusal`, costo con el modelo que respondió.
- Clasificador simulado, extracción de datos, reglas de negocio, costos, lectura de `.eml`.
- API contra PostgreSQL real: login y roles, formulario, filtros, corrección, aprobación, reprocesar, importaciones, métricas.
- Worker real de RQ contra Redis real (modo *burst*), y el flujo con Claude mockeado guardando tokens y costo.
- El script de evaluación.

## Evaluación del clasificador

`backend/evaluacion/consultas_etiquetadas.json` tiene **40 consultas inventadas en castellano rioplatense**, etiquetadas a mano con categoría y urgencia (incluye casos ambiguos y uno de prompt injection).

```bash
cd backend
python evaluar.py --simulado            # línea de base por reglas
python evaluar.py                       # el clasificador activo (Claude si hay clave)
python evaluar.py --limite 10 --salida resultado.json
python evaluar.py --umbral 0.8          # devuelve código 1 si queda por debajo (lo usa el CI)
```

Resultado del **simulado**: 87,5 % de exactitud en categoría y 70 % en urgencia. Falla, por ejemplo, cuando un reclamo de envío no usa palabras de envío ("pedido incompleto") o cuando hay palabras de otra categoría ("estafadores… pagué por transferencia"). **Con Claude no lo pude medir** porque en el entorno donde lo desarrollé no había clave: es lo primero que haría con una.

## Qué NO incluye o no se probó

- **No se llamó nunca a la API real de Claude.** Todo el código del clasificador real está testeado con un cliente falso; la forma de los parámetros (salida estructurada, `fallbacks`, `effort`) sigue la documentación del SDK oficial `anthropic` 1.x, pero no la verifiqué contra el servicio. Tampoco hay resultados de `evaluar.py` con Claude.
- Los precios para estimar el costo son valores de referencia cargados a mano en `costos.py`; el costo real sale de la consola de Anthropic.
- No se envían mails de verdad: "aprobar" deja la respuesta final guardada. Tampoco hay conexión IMAP; el mail se simula con `.eml`/JSON.
- No hay rate limiting en el formulario público ni captcha.
- Sin refresh tokens: el JWT dura 8 horas y después hay que volver a entrar. El token se guarda en `localStorage` (simple para una demo; en producción evaluaría cookies httpOnly).
- `docker compose build` y `docker compose up` los verifiqué en Linux (panel, API, worker, Postgres y Redis funcionando, una consulta del formulario clasificada por el worker). En el entorno donde lo probé había un proxy con certificado propio y tuve que agregar ese certificado al build con un archivo aparte que no forma parte del proyecto. No lo probé en Windows ni corrí el workflow de GitHub Actions en GitHub.
- El worker de RQ no corre nativo en Windows (ver arriba).
- Los tests del frontend son pocos (funciones de formato); las pantallas las probé a mano y con las capturas de Playwright.

## Cómo contarlo en una entrevista

1. **El problema:** una pyme recibe reclamos por varios canales y alguien los tiene que leer, clasificar y derivar. Automaticé la primera pasada con un LLM, pero la decisión final la sigue tomando una persona.
2. **Salida estructurada:** el modelo no devuelve texto libre sino un JSON con un schema generado desde Pydantic, y lo valido otra vez antes de guardar. Si no valida, reintento.
3. **Cola y worker:** el formulario responde al toque y la clasificación (que puede tardar segundos o fallar) se hace en segundo plano con RQ sobre Redis. Si Redis no está, no se pierde nada.
4. **Robustez:** reintentos con backoff exponencial y jitter solo para errores transitorios, timeout, y registro de tokens y costo de cada llamada.
5. **Reglas de negocio fuera del LLM:** área y SLA salen de código determinista y testeable; el LLM propone, las reglas deciden.
6. **Medir:** guardo lo que dijo el modelo y lo que corrigió la persona, y con eso calculo precisión por categoría. Además tengo un set de 40 consultas etiquetadas y un script que mide cualquier clasificador.
7. **Demo sin clave:** sin `ANTHROPIC_API_KEY` usa un clasificador por reglas, así cualquiera lo puede correr y los tests no dependen de la red.
8. **Tests de verdad:** integración contra Postgres y Redis reales, con un worker de RQ procesando, y el cliente de Claude mockeado.

**Preguntas probables**

- *¿Por qué RQ y no Celery?* Una sola tarea sincrónica; RQ solo necesita Redis y es mucho más simple. Si necesitara workflows, prioridades complejas o tareas programadas, miraría Celery.
- *¿Qué pasa si el LLM devuelve cualquier cosa?* La salida estructurada fuerza el formato y además Pydantic valida; si falla, reintento, y si se agotan los intentos la consulta queda en `error` con el detalle y se puede reprocesar.
- *¿Cómo sabés si el modelo anda bien?* Con el set de evaluación antes de cambiar algo, y en producción con las correcciones de los operadores (precisión, recall y matriz de confusión).
- *¿Y el prompt injection?* El texto del cliente va delimitado y marcado como dato, el modelo no tiene herramientas que ejecuten acciones, y nada sale sin aprobación humana.
- *¿Cuánto cuesta?* Cada llamada registra tokens y costo estimado; con esfuerzo bajo y respuestas cortas la estimación da menos de un centavo de dólar por consulta (unos 1.500 tokens de entrada y 500 de salida), y se ve en el panel de métricas.
- *¿Qué mejorarías?* Medir con Claude real y ajustar el prompt contra el set de evaluación, envío real de mails, conexión IMAP, rate limiting en el formulario y más tests del frontend.
