# IBM i Legacy Agent Migrator

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-Not%20Specified-lightgrey)
![IBM i Compatibility](https://img.shields.io/badge/IBM%20i-Compatible-success)

Plataforma agéntica en Streamlit para modernización de sistemas legacy IBM i con tres rutas de trabajo:

- FTP a SFTP con salida nativa IBM i
- COBOL a Python para escenarios de modernización asistida
- COBOL a DTSX para empaquetado SSIS con SQL Server y Sybase

## Arquitectura Visual

```mermaid
graph TD
    User[User] --> UI[Streamlit UI]
    UI --> SFTP[FTP to SFTP]
    UI --> Py[COBOL to Python]
    UI --> DTSX[COBOL to DTSX]
    SFTP --> Analyst[Analyst]
    Py --> Analyst
    DTSX --> Analyst
    Analyst --> Architect[Architect]
    Architect --> Developer[Developer]
    Developer --> Auditor[Auditor]
    Auditor --> Output[Output]
```

## Guía de Instalación

```bash
git clone <url-del-repositorio>
cd AgenteSFTP
```

```bash
copy env.example .env
python -m venv venv
```

```bash
# Windows PowerShell
venv\Scripts\Activate.ps1

# Linux/macOS
# source venv/bin/activate
```

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto (puedes usar `.env.example` como base).

| Variable | Requerida | Descripción | Ejemplo |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Sí | API key para llamadas al modelo LLM | `sk-...` |
| `SECRET_KEY` | No | Variable presente en ejemplo de entorno, no usada en el flujo actual | `your_secret_key_here` |
| `DATABASE_URL` | No | Variable presente en ejemplo de entorno, no usada en el flujo actual | `sqlite:///db.sqlite3` |

Ejemplo mínimo:

```ini
OPENAI_API_KEY=sk-...
```

## Contenedores y Kubernetes

Esta solución puede ejecutarse en dos niveles de despliegue:

- Contenedor local con Docker o Docker Compose.
- Orquestación en clúster con Kubernetes usando manifiestos base o productivos.

### Relación Entre Archivos

| Archivo | Qué realiza | Cómo se relaciona |
| --- | --- | --- |
| `.dockerignore` | Excluye archivos innecesarios del contexto de build (venv, cachés, `.env`, etc.). | Reduce tamaño y tiempo de construcción del `Dockerfile`. |
| `Dockerfile` | Construye la imagen de la app Streamlit e instala dependencias desde `requirements.txt`. | Es la base para `docker compose` y también para la imagen que consume Kubernetes. |
| `docker-compose.yml` | Levanta la app como servicio local, publica el puerto `8501` y carga variables desde `.env`. | Usa el `Dockerfile` para build y sirve para pruebas o ambientes locales. |
| `k8s/app.yaml` | Manifiesto base de Kubernetes (Namespace, Secret, ConfigMap, Deployment, Service, Ingress). | Lleva la misma app a clúster en modo estándar (no productivo endurecido). |
| `k8s/app.prod.yaml` | Manifiesto productivo con 2 réplicas, rolling update y seguridad non-root. | Variante recomendada para operación estable en clúster. |

### Flujo Docker y Kubernetes

```mermaid
flowchart TD
    A[Codigo fuente + requirements.txt] --> B[Dockerfile]
    B --> C[Imagen agentesftp-app]
    C --> D[docker-compose.yml]
    C --> E[k8s/app.yaml]
    C --> F[k8s/app.prod.yaml]
    D --> G[Ejecucion local en puerto 8501]
    E --> H[Despliegue base en Kubernetes]
    F --> I[Despliegue productivo en Kubernetes]
```

### Ejecución Local con Docker

```bash
docker build -t agentesftp-app:latest .
docker run --rm -p 8501:8501 --env-file .env agentesftp-app:latest
```

Abrir en navegador:

```text
http://localhost:8501
```

### Ejecución Local con Docker Compose

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f app
```

Detener servicios:

```bash
docker compose down
```

### Despliegue en Kubernetes (Base)

```bash
kubectl apply -f k8s/app.yaml
kubectl get pods,svc,ingress -n agentesftp
```

### Despliegue en Kubernetes (Producción)

```bash
kubectl apply -f k8s/app.prod.yaml
kubectl rollout status deployment/agentesftp-app -n agentesftp
kubectl get pods,svc,ingress -n agentesftp
```

Características de `k8s/app.prod.yaml`:

- `replicas: 2` para alta disponibilidad básica.
- Estrategia `RollingUpdate` con `maxSurge: 1` y `maxUnavailable: 0`.
- `securityContext` non-root a nivel de pod y contenedor.
- Probes de liveness/readiness para despliegues y recuperación controlada.

Si quieres exportarla a archivo:

```bash
docker save -o agentesftp-app.tar agentesftp-app:latest
```

Y luego podrías importarla en otra máquina con:

```bash
docker load -i agentesftp-app.tar
```

## Estructura de Carpetas

```text
AgenteSFTP/
├── .dockerignore
├── .github/
│   └── agents/
│       ├── 00_documentator_readme.md
│       ├── 01_analyst_AS400SFTP.md
│       ├── 01_analyst_CobolToPython.md
│       ├── 01_analyst_CobolToDtsx.md
│       ├── 02_architect_AS400SFTP.md
│       ├── 02_architect_CobolToPython.md
│       ├── 02_architect_CobolToDtsx.md
│       ├── 03_developer_AS400SFTP.md
│       ├── 03_developer_CobolToPython.md
│       ├── 03_developer_CobolToDtsx.md
│       ├── 04_auditor_AS400SFTP.md
│       ├── 04_auditor_CobolToPython.md
│       └── 04_auditor_CobolToDtsx.md
├── assets/
│   ├── dark_mode.css
│   └── light_mode.css
├── RPG_Ejemplo/
│   └── SEND_FTP.RPGLE
├── tests/
│   ├── test_app.py
│   └── test_dtsx_generator.py
├── dtsx_generator.py
├── docker-compose.yml
├── Dockerfile
├── k8s/
│   ├── app.yaml
│   └── app.prod.yaml
├── main.py
├── modulo_cobol.py
├── modulo_dtsx.py
├── modulo_sftp.py
├── utils.py
├── requirements.txt
└── README.md
```

## Uso

```bash
streamlit run main.py
```

Al iniciar, la UI permite elegir uno de tres flujos de migración y ejecutar el pipeline completo hasta auditoría y entrega.

## Flujo COBOL a DTSX

El nuevo módulo COBOL a DTSX está orientado a programas COBOL con SQL embebido y acceso a SQL Server o Sybase. El flujo:

1. Carga el fuente COBOL y detecta conexiones y bloques `EXEC SQL`.
2. Ejecuta análisis y diseño del paquete SSIS.
3. Genera un `.dtsx` base con connection managers, variables y tareas SQL inferidas.
4. Expone una auditoría técnica y permite descargar el paquete XML.
