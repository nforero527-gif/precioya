# PrecioYa — Comparador de Precios en E-commerce

Proyecto académico — Universidad El Bosque, IX Semestre 2026-1  
Curso: Fundamentos de computación en la nube y arquitectura Serverless

---

## Estructura del proyecto

```
price-comparator/
├── frontend/
│   └── index.html          ← SPA completa (HTML + CSS + JS)
└── functions/
    ├── host.json
    ├── requirements.txt
    ├── local.settings.json  ← NO subir a Git (contiene claves)
    ├── products/            ← CRUD de productos
    │   ├── __init__.py
    │   └── function.json
    ├── stores/              ← CRUD de tiendas
    │   ├── __init__.py
    │   └── function.json
    ├── history/             ← Historial / comparación de precios
    │   ├── __init__.py
    │   └── function.json
    └── scraper/             ← Timer Trigger cada 6 horas
        ├── __init__.py
        └── function.json
```

---

## Paso a paso para desplegar en Azure

### 1. Crear recursos en Azure Portal

1. **Azure Cosmos DB** (Free Tier)
   - API: Core (SQL)
   - Database: `PriceComparatorDB`
   - Containers: `productos`, `tiendas`, `precios` (partition key: `/id`)

2. **Azure Function App**
   - Runtime: Python 3.11
   - Plan: Consumption (Serverless)
   - Region: East US (o la más cercana)
   - Deshabilitar Application Insights o configurar al 5%

3. **Azure Static Web Apps** (Free Tier)
   - Conectar a tu repositorio GitHub con la carpeta `frontend/`

---

### 2. Configurar variables de entorno en la Function App

En Azure Portal → Function App → Configuration → Application Settings:

| Nombre          | Valor                                      |
|-----------------|--------------------------------------------|
| `COSMOS_ENDPOINT` | `https://TU_CUENTA.documents.azure.com:443/` |
| `COSMOS_KEY`      | Tu clave primaria de Cosmos DB             |

---

### 3. Desplegar las Functions (VS Code)

```bash
# Instalar Azure Functions Core Tools
npm install -g azure-functions-core-tools@4 --unsafe-perm true

# Instalar extensión Azure Functions en VS Code
# Luego: clic derecho en la carpeta functions/ → Deploy to Function App
```

O con Azure CLI:
```bash
cd functions/
func azure functionapp publish TU_FUNCTION_APP_NAME
```

---

### 4. Configurar las URLs en el frontend

En `frontend/index.html`, busca el objeto `API` y reemplaza con tus URLs reales:

```javascript
const API = {
  products : 'https://TU_FUNCTION_APP.azurewebsites.net/api/products',
  stores   : 'https://TU_FUNCTION_APP.azurewebsites.net/api/stores',
  history  : 'https://TU_FUNCTION_APP.azurewebsites.net/api/history',
};
```

---

### 5. Configurar CORS en la Function App

Azure Portal → Function App → CORS → Agregar `*` (o el dominio de tu Static Web App)

---

### 6. Subir el frontend a Static Web Apps

Opción A — GitHub Actions (automático al hacer push a main)  
Opción B — Arrastrar `frontend/index.html` al portal de Azure Static Web Apps

---

## Alerta de costos

Configurar en **Azure Cost Management**:
- Budget: $1 USD mensual
- Alert: 80% del presupuesto

---

## Notas sobre el scraper

- El Timer Trigger se activa **cada 6 horas** (`0 0 */6 * * *`)
- Soporta Alkosto y Falabella
- Para agregar una tienda nueva: crear una función `scrape_TIENDA(url)` en `scraper/__init__.py` y registrarla en el diccionario `STORE_SCRAPERS`
- Si el scraping falla (código de bloqueo 403), considera usar Azure Cognitive Services o un proxy rotativo

---

## Modo demo

El frontend funciona sin Azure con datos de ejemplo predefinidos.  
Útil para mostrar el proyecto antes de desplegar.
