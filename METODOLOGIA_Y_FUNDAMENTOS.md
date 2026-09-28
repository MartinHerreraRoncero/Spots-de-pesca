# 📚 Metodología y Fundamentos Científicos del Motor Predictivo

**PescaMar Andalucía** integra modelos de física atmosférica, hidrodinámica de fluidos, topografía submarina, astronomía orbital y etología marina para el pronóstico y optimización de jornadas de pesca en el litoral andaluz.

---

## 1. Dinámica Barométrica y Fisiología de la Vejiga Natatoria
* **Descenso Pre-Frontera ($\Delta P_{3h} \in [-0.5, -1.8]\text{ hPa}$):** Estimula la alimentación previa a la llegada de frentes fríos por descompresión somera.
* **Penalización por Caída Violenta ($<-3.0\text{ hPa}$):** Desplaza a los peces a zonas profundas para compensar el exceso de volumen en su vejiga natatoria.

---

## 2. Mareas Astronómicas, Coeficientes y Repuntes
* **Ciclo Semidiurno Andaluz:** Pleamares y bajamares cada ~12h 25m.
* **Coeficiente de Marea (20 a 120):** Las mareas vivas (>80) multiplican las corrientes en el Golfo de Cádiz y el Estrecho de Gibraltar, movilizando nutrientes e invertebrados bentónicos.
* **Repunte de Pleamar:** Momento óptimo para espáridos (dorada, sargo, herrera) al inundar nuevos bancos de moluscos en el escalón de orilla.

---

## 3. ⛰️ Relieve Submarino y Topografía EMODnet
* **Gradientes Batimétricos ($\nabla \text{Profundidad}$):** Caídas bruscas del fondo (*cantiles* y escalones) donde acechan los depredadores marinos.
* **Índice de Rugosidad:** Cuantifica la complejidad estructural del lecho (lajas de piedra, arrecifes vs arenales planos).

---

## 4. 🛰️ Frentes Térmicos Satelitales y Claridad del Agua
* **Frentes de Temperatura ($\nabla SST$):** Zonas de choque entre masas de agua atlánticas y mediterráneas donde se concentra el plancton y los peces pasto.
* **Disco de Secchi y Turbidez (NTU):** Clasificación bio-óptica de las aguas (aguas tomadas/chocolate vs aguas cristalinas) que determina si el escenario es propicio para pesca visual (calamar, spinning) o de rastreo olfativo (surfcasting).

---

## 5. 🏞️ Descarga Fluvial y Plumas de Salinidad
* **12 Cuencas Andaluzas:** Monitorización de las desembocaduras de los principales ríos (Guadalquivir, Guadiana, Guadalete, Guadalfeo, etc.).
* **Choque Osmótico:** Los aportes de agua dulce y sedimentos disparan la actividad de la lubina y la corvina, mientras que desplazan al calamar mar adentro.

---

## 6. 🛰️ Teledetección Satelital de Pozas y Canales de Surfcasting (Costa de Huelva)
Las playas arenosas del litoral onubense (Ayamonte, Isla Canela, Isla Cristina, La Redondela, Islantilla, El Terrón, El Portil, Punta Umbría, Mazagón y Matalascañas) son sistemas morfodinámicos expuestos al régimen atlántico donde el oleaje y la deriva litoral esculpen barras arenosas y fosos submarinos. En surfcasting, localizar estas depresiones (pozas y canales de resaca) es el factor determinante para el éxito, ya que retienen agua oxigenada, cangrejos, gusanas y moluscos, atrayendo a doradas, herreras, lubinas y corvinas. El sistema combina 3 metodologías avanzadas de detección:

* **1. Batimetría Satelital SDB Stumpf (Ratio Azul/Verde Sentinel-2 MSI):**
  Basada en la teoría de transferencia radiativa óptica en aguas someras limpias. La radiación en la longitud de onda azul (Banda 2, $\sim 490\text{ nm}$) posee un coeficiente de absorción muy bajo, penetrando en la columna de agua hasta 15-20 m, mientras que la banda verde (Banda 3, $\sim 560\text{ nm}$) se atenúa con mayor rapidez. Aplicando la ecuación logarítmica de Stumpf et al. (2003):
  $$
  Z = m_1 \frac{\ln(n \cdot R_{\text{B02}})}{\ln(n \cdot R_{\text{B03}})} - m_0
  $$
  donde $R_{\text{B02}}$ y $R_{\text{B03}}$ son las reflectancias de fondo en superficie (Sentinel-2 L2A), $n$ es la constante de escalado para garantizar logaritmos positivos, y $m_1, m_0$ son factores empíricos ajustados a las aguas arenosas del Golfo de Cádiz. Esta inversión permite cartografiar desniveles relativos de foso de $+0.8\text{m}$ a $+2.8\text{m}$ respecto a la barra contigua.

* **2. Brecha de Rompiente (Breaker Line Disruption):**
  Cuando los trenes de olas incidentes alcanzan aguas someras sobre una barra de arena, rompen por pérdida de estabilidad hidrodinámica al cumplirse el criterio de rotura ($\gamma = H_b / h \approx 0.78$). Sin embargo, en los puntos donde un canal de resaca o una poza corta transversalmente la barra, el calado local $h$ se incrementa bruscamente. En consecuencia, la relación $H / h$ disminuye por debajo del umbral de rotura, generando una "brecha" o discontinuidad nítida en la banda de espuma blanca (*foam line*), detectable automáticamente mediante análisis de discontinuidad textural en imágenes Sentinel-2 L2A a 10m de resolución espacial.

* **3. Fotogrametría Aérea de Máxima Resolución PNOA (IGN 25cm):**
  Verificación geométrica de alta fidelidad empleando las ortofotografías aéreas digitales del Plan Nacional de Ortofotografía Aérea (PNOA) del Instituto Geográfico Nacional, adquiridas con sensores aerotransportados de gran formato calibrados en condiciones de bajamar viva escorada. Proporciona una resolución de 25 cm por píxel que permite delinear el perímetro exacto de bermas, barras emergidas, canalizos intermareales y gargantas de desagüe con precisión submétrica.

---

## 7. 🏖️ Detección de Línea de Costa y Máscara Espectral Agua-Tierra (NDWI)
Para eliminar falsos positivos sobre tierra firme (dunas de Doñana, pinares de Enebrales, paseos marítimos o bermas secas), el sistema implementa una máscara espectral y vectorial georreferenciada:
* **Vector MHW (Mean High Water):** Traza continua de la orilla de pleamar desde la desembocadura del Guadiana (Ayamonte, frontera con Portugal) hasta la Punta del Boquerón y Doñana, contrastada con la cartografía base del IGN y OpenStreetMap Coastlines.
* **Índice NDWI (McFeeters, 1996):**
  $$
  \text{NDWI} = \frac{R_{\text{B03 (Verde)}} - R_{\text{B08 (NIR)}}}{R_{\text{B03 (Verde)}} + R_{\text{B08 (NIR)}}}
  $$
  Donde valores $> 0.0$ identifican masa de agua y valores $\le 0.0$ identifican arena seca y vegetación.
* **Enforcement Marino Obligatorio:** El 100% de las coordenadas y polígonos de las pozas son validados algorítmicamente para situarse estrictamente en la franja marina / intermareal (a una distancia perpendicular de $20\text{ a }130\text{ m}$ mar adentro respecto a la línea de pleamar).

---

## 8. 🛡️ Contraste Multitemporal y Persistencia Morfodinámica (Series de 5 Días)
Las pozas y canales de resaca verdaderos son estructuras geomorfológicas duraderas talladas en el lecho marino que resisten la oscilación mareal diurna, mientras que los artefactos transitorios (espuma efímera de trenes de olas aislados, sombras nubosas o bancos de algas flotantes) se disipan entre una pasada y otra.
* **Serie Multitemporal ($T_0, T_{-5\text{d}}, T_{-10\text{d}}$):** Consulta continua en Microsoft Planetary Computer STAC de las pasadas consecutivas del satélite Sentinel-2 sobre la cuadrícula MGRS `29SPB`.
* **Cálculo Determinista de Deriva Litoral (Formulación CERC & Longuet-Higgins):**
  La migración morfodinámica longitudinal de los canales y pozas se modela de manera estrictamente física y determinista a partir de las ecuaciones de flujo de energía del oleaje y tensiones de radiación ($S_{xy}$) en rotura oblicua (CERC / USACE 1984; Longuet-Higgins 1970; Ruessink et al. 2000):
  $$
  \alpha_b = \theta_{\text{oleaje}} - \theta_{\text{normal costera}}
  $$
  $$
  V_{\text{migración}} = K_{\text{morph}} \cdot \left(H_s^2 \sqrt{g \cdot H_s}\right) \cdot \sin(2\alpha_b) \quad [\text{m/día}]
  $$
  $$
  \Delta X_{\text{deriva}} = \left| V_{\text{migración}} \cdot \Delta t_{\text{días}} \right| \quad [\text{m}]
  $$
  donde:
  * $\theta_{\text{normal costera}}$ es el azimut del vector normal perpendicular a la línea de costa calculado por sectores (desde Ayamonte a Matalascañas, oscilando entre $165^\circ$ y $205^\circ$).
  * $\alpha_b$ es el ángulo de incidencia oblicua de la rompiente. En el Golfo de Cádiz, con trenes de fondo atlánticos dominantes de WSW ($\theta_{\text{oleaje}} \approx 235^\circ$), $\alpha_b \in [30^\circ, 70^\circ]$, lo que genera $\sin(2\alpha_b) > 0$.
  * $K_{\text{morph}} = 1.45$ es el coeficiente de movilidad morfodinámica para arenas de cuarzo medio ($d_{50} \approx 0.25\text{ mm}$).
  * La ecuación produce una velocidad de desplazamiento determinista neta hacia **Levante (E/SE)** de $1.5\text{ a }2.6\text{ m/día}$ ($8\text{ a }13\text{ m}$ por ciclo de 5 días de Sentinel-2), perfectamente acotada dentro del radio de tolerancia de lance ($\le 45\text{ m}$).
* **Índice de Persistencia (0 a 100%):**
  * **$\ge 90\%$ (3/3 pasadas confirmadas):** Foso submarino ultra-estable y permanente.
  * **$75-89\%$ (2/3 pasadas confirmadas):** Canal dinámico activo con migración moderada hacia Levante.
  * **$< 60\%$ (1 pasada):** Estructura transitoria o en periodo de validación.
