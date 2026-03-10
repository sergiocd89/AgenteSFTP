# AgenteSFTP

![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![License](https://img.shields.io/badge/license-MIT-blue) ![IBM%20i](https://img.shields.io/badge/IBM%20i-compatible-green)

## 🚀 Identidad
Agente especializado en migración de código AS/400 que convierte comandos FTP a SFTP utilizando un modelo de lenguaje.

## 🏗️ Arquitectura Visual
```mermaid
graph TD
    User --> "Streamlit UI"
    "Streamlit UI" --> subgraph Agents[Agents]
        Analyst --> Architect --> Developer --> Auditor
    end
    Agents --> Output
```

## 🛠️ Instalación
1. Clona el repositorio:
   ```bash
git clone https://github.com/usuario/AgenteSFTP.git
cd AgenteSFTP
   ```
2. Crea y activa un entorno virtual:
   ```bash
python -m venv venv
# Windows PowerShell
env\Scripts\Activate.ps1
# (Linux/Mac: source venv/bin/activate)
   ```
3. Asegúrate de tener pip reciente:
   ```bash
python -m pip install --upgrade pip setuptools wheel
   ```
4. Instala dependencias:
   ```bash
pip install -r requirements.txt
   ```

## 🔐 Variables de Entorno
Crea un fichero `.env` en la raíz con:
```ini
OPENAI_API_KEY=sk-yourkey
OPENAI_MODEL=gpt-4o
``` 

| Variable          | Descripción                               | Ejemplo        |
|-------------------|-------------------------------------------|----------------|
| `OPENAI_API_KEY`  | Autenticación para OpenAI                 | `sk-...`       |
| `OPENAI_MODEL`    | Modelo por defecto                        | `gpt-4o`       |

## 📁 Estructura de Carpetas
```
AgenteSFTP/
├── app.py                # Streamlit + lógica principal
├── requirements.txt      # dependencias
├── README.md             # documentación
├── .env.example          # ejemplo de variables
├── tests/
│   └── test_app.py       # pruebas unitarias
└── RPG_Ejemplo/
    └── SEND_FTP.RPGLE    # código de ejemplo
```

## ▶️ Uso
```bash
streamlit run app.py
# Abre http://localhost:8501 en tu navegador
```
Carga un fichero con código AS/400 y observa la conversión a SFTP.

## ✅ Ejemplo como módulo Python
```python
from app import refactor_code

texto = "...código AS/400..."
resultado = refactor_code(texto, api_key="sk-...", model_name="gpt-4o")
print(resultado)
```

## 🧪 Testing
```bash
pip install -r requirements.txt
pytest -q
```

## 🤝 Contribuir
1. Haz *fork* del repositorio
2. Crea rama (`feature/nueva-funcion`)
3. Añade código/documentación
4. Envía *pull request*

Consulta `CONTRIBUTING.md` y el código de conducta.

## 📄 Licencia
MIT License – mira el fichero `LICENSE` para más detalles.
