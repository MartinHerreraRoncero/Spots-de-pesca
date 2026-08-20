# 🎣 PescaMar Andalucía — Sistema Predictivo y Scoring de Pesca Marina (GIS + Solunar)

Aplicación interactiva construida en **Python**, **Streamlit**, **Folium** y **Ephem** para predecir, puntuar y visualizar las mejores condiciones de pesca deportiva y costera a lo largo de toda la costa de **Andalucía (España)**.

---

## 🌟 Características Principales

1. **Grid Costero Estratégico (20 Spots)**:
   - **Costa de la Luz / Golfo de Cádiz (Atlántico)**: Isla Cristina, Punta Umbría, Matalascañas, Sanlúcar de Barrameda, Chipiona, Cádiz Capital, Sancti Petri, Conil de la Frontera, Barbate.
   - **Estrecho de Gibraltar**: Punta de Tarifa / Isla de las Palomas.
   - **Costa del Sol (Málaga)**: Estepona, Marbella (Cabopino), Fuengirola, Málaga Capital (El Palo / Peñón del Cuervo), Nerja (Acantilados de Maro).
   - **Costa Tropical (Granada)**: La Herradura (Punta de la Mona), Motril / Calahonda (Cabo Sacratif).
   - **Costa de Almería y Cabo de Gata**: Roquetas de Mar (Punta Entinas), Cabo de Gata (San José / Sirenas), Carboneras (Playa de los Muertos).

2. **Ingesta de Datos Meteorológicos y Oceanográficos (Open-Meteo APIs Gratuitas)**:
   - **Marine API**: Altura de ola (\(m\)), periodo de ola (\(s\)), dirección de ola (\(^\circ\)), temperatura superficial del mar (SST, \(^\circ\text{C}\)), altura y periodo de mar de fondo (*swell*).
   - **Forecast API**: Presión a nivel de superficie (\(\text{hPa}\)), velocidad de viento a 10m (\(\text{km/h}\)), dirección de viento, cobertura nubosa (\(\%\)), precipitación (\(\text{mm}\)), temperatura ambiental.
   - **Caché en Memoria y Modo Resiliente**: Fallback automático y reintentos ante desconexiones de red.

3. **Cálculo Solunar Astronómico Riguroso (`ephem`)**:
   - Fase lunar exacta, porcentaje de iluminación y edad de la luna en días.
   - Identificación de **Mareas Vivas** (*spring tides*) en lunas nuevas y llenas vs **Mareas Muertas** (*neap tides*).
   - Cálculo de **Periodos Mayores** (Cenit lunar y Nadir lunar \(\pm 60\text{ min}\)).
   - Cálculo de **Periodos Menores** (Salida y Puesta de la Luna \(\pm 45\text{ min}\)).
   - Sincronización con el ciclo solar: Orto, Ocaso y Crepúsculos astronómicos/civiles (**Golden Window** solapada).

4. **Motor de Scoring Heurístico Ponderado (0 - 100)**:
   - **\(\Delta\) Presión Barométrica (lag de 3h y 6h)**: Premia descensos suaves pre-frente (\(-0.5\) a \(-1.8\text{ hPa}\)), penaliza caídas violentas de temporal (\(<-3.0\text{ hPa}\)) y estancamiento anticiclónico (\(>1026\text{ hPa}\)).
   - **Ventanas Solunares y Solares**: Bonificación por coincidencia con tránsitos y solapamiento crepuscular.
   - **Estado del Mar y Oleaje**: Rango óptimo costero (\(0.4\text{m} - 1.2\text{m}\)) y periodos largos (\(>7\text{s}\)).
   - **Viento Costero**: Brisa favorable (\(8 - 18\text{ km/h}\)) para rizado superficial y camuflaje de líneas.
   - **Ponderación Configurable**: Sliders interactivos en la interfaz para calibrar los pesos heurísticos.

5. **Visualización GIS e Interactiva**:
   - **Mapa Folium** con pines circulares con score numérico y código de color (🟢 Verde \(\ge 75\), 🟡 Amarillo \(60-74\), 🟠 Naranja \(45-59\), 🔴 Rojo \(<45\)).
   - **Popups Enriquecidos** con métricas en tiempo real, especies recomendadas, técnicas y diagnósticos biológicos.
   - **Gráficos Plotly Interactivos**: Evolución a 48h de presión barométrica vs score de pesca con bandas solunares sombreadas, dinámica de olas y viento, y radar polar de componentes.

---

## 📁 Estructura del Proyecto

```
d:\App pesca\
├── data/
│   ├── spots_andalucia.json           # 20 spots costeros con coordenadas y metadatos
│   └── spots_andalucia.geojson        # Geometría GeoJSON para capas GIS
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── spot.py                    # Modelos de datos tipados (Pydantic / Dataclasses)
│   ├── fetchers/
│   │   ├── __init__.py
│   │   └── open_meteo.py              # Ingesta Marine & Forecast con caché y fallback
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── solunar.py                 # Motor astronómico ephem (fases, tránsitos, crepúsculos)
│   │   └── scoring.py                 # Algoritmo de scoring heurístico 0-100
│   └── visualization/
│       ├── __init__.py
│       ├── map_view.py                # Visualización con Folium y marcadores HTML
│       └── charts.py                  # Gráficos de series temporales y radar con Plotly
├── app.py                             # Aplicación interactiva Streamlit
├── requirements.txt                   # Dependencias fijadas del proyecto
└── README.md                          # Documentación del sistema
```

---

## 🚀 Instalación y Ejecución

### 1. Clonar o acceder al directorio del proyecto:
```bash
cd "d:/App pesca"
```

### 2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

### 3. Ejecutar la aplicación en Streamlit:
```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador predeterminado en `http://localhost:8501`.

---

## 🧮 Fórmula del Algoritmo de Scoring

El score total \(S \in [0, 100]\) para una coordenada y hora específica se calcula como:

\[
S = \text{clamp}\left( w_P \cdot S_P + w_S \cdot S_S + w_M \cdot S_M + w_W \cdot S_W + w_L \cdot S_L, 0, 100 \right)
\]

Donde:
* \(S_P\): Subscore de presión barométrica y tendencia \(\Delta P_{3h}\).
* \(S_S\): Subscore solunar (tránsitos cenit/nadir y coincidencia crepuscular).
* \(S_M\): Subscore oceanográfico de altura de ola, periodo de ola y temperatura del agua.
* \(S_W\): Subscore de velocidad de viento costero.
* \(S_L\): Subscore de fuerza de marea según cercanía a Luna Nueva o Luna Llena.
* \(w_i\): Pesos normalizados configurables desde la barra lateral (por defecto: \(0.25, 0.30, 0.20, 0.15, 0.10\)).

---

## 🐟 Especies Diana Incluidas en el Modelo

* **Dorada (*Sparus aurata*)**: Surfcasting en arenales y canales de marea.
* **Lubina / Róbalo (*Dicentrarchus labrax*)**: Spinning en rompientes espumosas y desembocaduras.
* **Sargo (*Diplodus sargus*)**: Rockfishing en roquedos batidos por el oleaje.
* **Corvina (*Argyrosomus regius*)**: Golfo de Cádiz con corrientes de marea viva.
* **Dentón (*Dentex dentex*)**: Shore Jigging y pesca profunda en acantilados de Maro, Herradura y Cabo de Gata.
* **Calamar y Sepia (*Loligo vulgaris* / *Sepia officinalis*)**: Eging en puertos y ensenadas al atardecer.
