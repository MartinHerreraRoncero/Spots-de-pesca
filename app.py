"""
Aplicación Principal Streamlit: Sistema de Predicción y Scoring de Pesca Marina en Andalucía.
Incluye:
- Modo de Scoring Especializado por Especie (Dorada, Lubina, Sargo, Calamar, Dentón, Corvina) + Score Global
- Mareas Astronómicas, Coeficientes y Repuntes Hidráulicos
- Corrientes Marinas Físicas en Nudos (Knots) y Dirección de Flujo
- Viento Relativo a la Costa (Onshore / Offshore / Upwelling)
- Asimilación de Datos y Calibración In-Situ con Boyas de Puertos del Estado (REDEXT / REDCOS)
- Modo Clic en el Mapa (análisis de cualquier coordenada GPS libre)
- ⛰️ Relieve Submarino y Gradientes Batimétricos (EMODnet Bathymetry & Rugosidad)
- 🛰️ Frentes Térmicos Satelitales (SST Gradients) y Claridad Bio-Óptica del Agua (Secchi & Turbidez NTU)
- 🏞️ Descarga de Ríos, Pluviosidad en Cuencas y Plumas de Salinidad (12 Cuencas Andaluzas)
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional, Dict, Any
import inspect
import importlib
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.models.spot import Spot, HourlySpotForecast, MarineBuoy, BuoyObservation, ScoringWeights
import src.models.poza
importlib.reload(src.models.poza)
from src.models.poza import DetectedPoza, SentinelPassMetadata
import src.analytics.coastline
importlib.reload(src.analytics.coastline)
from src.fetchers.open_meteo import (
    load_spots_from_json,
    load_marine_buoys_from_json,
    create_custom_spot_from_coords,
    get_spot_hourly_forecast,
    get_all_spots_snapshot,
    get_buoy_telemetry_snapshot,
)
import src.fetchers.sentinel_satellite
importlib.reload(src.fetchers.sentinel_satellite)
try:
    from src.fetchers.sentinel_satellite import (
        get_latest_huelva_sentinel_pass,
        get_huelva_sentinel_series,
    )
except (ImportError, AttributeError):
    from src.fetchers.sentinel_satellite import get_latest_huelva_sentinel_pass
    def get_huelva_sentinel_series(passes_count: int = 3, force_refresh: bool = False):
        return [get_latest_huelva_sentinel_pass(force_refresh=force_refresh)]
import src.analytics.scoring
importlib.reload(src.analytics.scoring)
try:
    from src.analytics.scoring import calculate_golden_bite_window
except (ImportError, AttributeError):
    def calculate_golden_bite_window(*args, **kwargs):
        return {
            "is_golden": False,
            "is_favorable": False,
            "golden_score": 50.0,
            "status_label": "Actividad Estándar",
            "status_tier": "STANDARD",
            "color": "#64748b",
            "factors_met": [],
            "summary": "Condiciones regulares.",
        }

from src.analytics.solunar import compute_daily_solunar
from src.analytics.river_runoff import load_rivers_catalog
from src.analytics.bathymetry import calculate_bathymetry_profile
import src.analytics.poza_detection
importlib.reload(src.analytics.poza_detection)
from src.analytics.poza_detection import (
    load_pozas_from_json,
    filter_pozas,
    sync_pozas_with_satellite_pass,
    contrast_multi_temporal_pozas,
    evaluate_poza_fishability,
    recommend_surfcasting_rig,
    calculate_optimal_time_window_today,
)
import src.visualization.map_view
importlib.reload(src.visualization.map_view)
from src.visualization.map_view import (
    create_andalucia_fishing_map,
    get_spot_type_icon,
    get_display_score_for_mode,
)
import src.visualization.charts
importlib.reload(src.visualization.charts)
try:
    from src.visualization.charts import (
        create_pressure_and_score_chart,
        create_marine_and_wind_chart,
        create_score_radar_chart,
        create_species_comparison_chart,
        create_top_spots_bar_chart,
        create_continuous_tide_chart,
    )
except (ImportError, AttributeError):
    from src.visualization.charts import (
        create_pressure_and_score_chart,
        create_marine_and_wind_chart,
        create_score_radar_chart,
        create_species_comparison_chart,
        create_top_spots_bar_chart,
    )
    import plotly.graph_objects as go
    def create_continuous_tide_chart(*args, **kwargs):
        return go.Figure()

# Page configuration
st.set_page_config(
    page_title="PescaMar Andalucía | GIS, Solunar, Mareas, Clic, Boyas & Batimetría",
    page_icon="🎣",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished ocean theme
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #f8fafc 0%, #edf2f7 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 12px;
    }
    .metric-title {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 22px;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.2;
    }
    .metric-subtitle {
        font-size: 12px;
        color: #0284c7;
        font-weight: 600;
        margin-top: 4px;
    }

    .badge-excellent {
        background-color: #10b981;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 13px;
        display: inline-block;
    }
    .badge-good {
        background-color: #84cc16;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 13px;
        display: inline-block;
    }
    .badge-moderate {
        background-color: #f59e0b;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 13px;
        display: inline-block;
    }
    .badge-bad {
        background-color: #ef4444;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 13px;
        display: inline-block;
    }

    .micro-tag {
        background: #f1f5f9;
        color: #334155;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
        margin-right: 4px;
        margin-bottom: 4px;
        border: 1px solid #e2e8f0;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 18px;
        border-radius: 8px 8px 0 0;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

if "custom_spot_coords" not in st.session_state:
    st.session_state["custom_spot_coords"] = None


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_spots() -> List[Spot]:
    return load_spots_from_json()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_buoys() -> List[MarineBuoy]:
    return load_marine_buoys_from_json()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_rivers() -> List[Dict[str, Any]]:
    return load_rivers_catalog()


def get_cached_pozas() -> List[DetectedPoza]:
    return load_pozas_from_json()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_sentinel_pass(force: bool = False) -> SentinelPassMetadata:
    return get_latest_huelva_sentinel_pass(force_refresh=force)


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_sentinel_series(force: bool = False) -> List[SentinelPassMetadata]:
    return get_huelva_sentinel_series(passes_count=3, force_refresh=force)


@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_spot_forecasts(spot_id: str, _spot_obj: Spot, w_press: float, w_sol: float, w_mar: float, w_wind: float, w_moon: float) -> List[HourlySpotForecast]:
    weights = ScoringWeights(
        weight_pressure=w_press,
        weight_solunar=w_sol,
        weight_marine=w_mar,
        weight_wind=w_wind,
        weight_moon_phase=w_moon,
    )
    return get_spot_hourly_forecast(_spot_obj, forecast_days=3, weights=weights)


def main():
    all_spots = get_cached_spots()
    all_buoys = get_cached_buoys()
    all_rivers = get_cached_rivers()
    raw_pozas = get_cached_pozas()

    if "sentinel_series" not in st.session_state:
        st.session_state["sentinel_series"] = get_cached_sentinel_series(force=False)

    sentinel_series: List[SentinelPassMetadata] = st.session_state["sentinel_series"]
    sentinel_meta: SentinelPassMetadata = sentinel_series[0] if sentinel_series else get_cached_sentinel_pass(force=False)
    st.session_state["sentinel_meta"] = sentinel_meta

    # Multi-temporal persistence contrast across consecutive Sentinel-2 passes
    synced_pozas = contrast_multi_temporal_pozas(raw_pozas, sentinel_series)


    # Sidebar Header
    st.sidebar.markdown("""
        <div style='text-align: center; padding-bottom: 10px;'>
            <h2 style='color:#0369a1; margin-bottom:0;'>🎣 PescaMar Andalucía</h2>
            <span style='font-size:12px; color:#64748b; font-weight:600;'>
                Scoring Científico, Mareas, Clic & Boyas
            </span>
        </div>
    """, unsafe_allow_html=True)
    st.sidebar.divider()

    # Temporal Control
    st.sidebar.markdown("### ⏱️ Control Temporal")
    now_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    
    forecast_hour_offset = st.sidebar.slider(
        "Horizonte de Predicción (Horas a futuro)",
        min_value=0,
        max_value=48,
        value=0,
        step=1,
        help="Avanza en el tiempo para evaluar las condiciones de pesca en las próximas 48 horas."
    )
    
    target_dt = now_utc + timedelta(hours=forecast_hour_offset)
    date_display_utc = target_dt.strftime("%d/%m/%Y %H:00 UTC")
    local_offset = 2
    local_dt = target_dt + timedelta(hours=local_offset)
    date_display_local = local_dt.strftime("%d/%m/%Y %H:00 (Hora Peninsular)")

    st.sidebar.info(f"📅 **Objetivo:** {date_display_local}\n\n🕒 `{date_display_utc}`")

    # Species-Specific Mode Selector (Preserves Global Score)
    st.sidebar.markdown("### 🎯 Modo de Scoring y Especie Diana")
    species_mode_options = {
        "GLOBAL": "🌟 Puntuación Global (Multiespecie)",
        "DORADA": "🐟 Dorada y Herrera (Surfcasting)",
        "LUBINA": "🐟 Lubina y Róbalo (Spinning en Rompiente)",
        "SARGO": "🐟 Sargo (Rockfishing en Roquedos)",
        "CALAMAR": "🦑 Calamar y Sepia (Eging en Aguas Claras)",
        "DENTON": "🐟 Dentón y Serviola (Shore Jigging Profundo)",
        "CORVINA": "🐟 Corvina (Grandes Corrientes de Marea)",
    }

    selected_species_mode = st.sidebar.selectbox(
        "Calibrar Puntuación Para:",
        options=list(species_mode_options.keys()),
        format_func=lambda k: species_mode_options[k],
        index=0,
        help="Elige una especie para que el mapa y los gráficos se adapten a sus requerimientos biológicos concretos, sin perder la puntuación global."
    )

    # Custom GPS Coordinates / Click on Map Expander
    st.sidebar.markdown("### 📍 Modo Clic / Coordenadas GPS")
    with st.sidebar.expander("📍 Introducir Coordenadas Manuales", expanded=False):
        c_lat = st.number_input("Latitud (°N)", min_value=35.5, max_value=38.0, value=36.5310, format="%.4f")
        c_lon = st.number_input("Longitud (°W)", min_value=-8.0, max_value=-1.5, value=-6.3090, format="%.4f")
        if st.button("Analizar Coordenadas Personalizadas"):
            st.session_state["custom_spot_coords"] = (c_lat, c_lon)
            st.rerun()

    if st.session_state["custom_spot_coords"] is not None:
        custom_lat, custom_lon = st.session_state["custom_spot_coords"]
        st.sidebar.success(f"🎯 **Punto Activo:** `{custom_lat:.4f}°N, {custom_lon:.4f}°W`")
        if st.sidebar.button("❌ Volver a Spots Predefinidos"):
            st.session_state["custom_spot_coords"] = None
            st.rerun()

    # Hierarchical Geographic Filters
    st.sidebar.markdown("### 📍 Navegación por Litoral")
    subzone_counts = {}
    for s in all_spots:
        subzone_counts[s.subzone] = subzone_counts.get(s.subzone, 0) + 1

    subzone_choices = ["Toda Andalucía"] + [
        "Costa de Huelva",
        "Bahía y Costa de Cádiz",
        "Estrecho de Gibraltar",
        "Costa del Sol Occidental",
        "Costa del Sol Oriental / Axarquía",
        "Costa Tropical de Granada",
        "Costa de Almería / Poniente",
        "Cabo de Gata y Levante Almeriense",
    ]

    subzone_labels = []
    for sz in subzone_choices:
        if sz == "Toda Andalucía":
            subzone_labels.append(f"🌊 Toda Andalucía ({len(all_spots)} spots)")
        else:
            cnt = subzone_counts.get(sz, 0)
            subzone_labels.append(f"📍 {sz} ({cnt} spots)")

    default_subzone_index = subzone_choices.index("Costa de Huelva") if "Costa de Huelva" in subzone_choices else 0

    if "subzone_select_idx" not in st.session_state:
        st.session_state["subzone_select_idx"] = default_subzone_index
    if st.session_state.get("forced_subzone"):
        target_name = st.session_state.pop("forced_subzone")
        if target_name in subzone_choices:
            st.session_state["subzone_select_idx"] = subzone_choices.index(target_name)

    selected_subzone_idx = st.sidebar.selectbox(
        "Litoral Costero:",
        range(len(subzone_choices)),
        format_func=lambda i: subzone_labels[i],
        key="subzone_select_idx",
    )
    selected_subzone_key = subzone_choices[selected_subzone_idx]

    if selected_subzone_key == "Toda Andalucía":
        filtered_spots = all_spots
    else:
        filtered_spots = [s for s in all_spots if s.subzone == selected_subzone_key]

    # Dedicated Section: Sentinel-2 & Surfcasting Pozas
    st.sidebar.markdown("### 🛰️ Satélite Sentinel-2 & Pozas de Surfcasting")
    pass_date_str = sentinel_meta.datetime.split("T")[0] if "T" in sentinel_meta.datetime else sentinel_meta.datetime[:10]
    col_sat1, col_sat2, col_sat3 = st.sidebar.columns(3)
    col_sat1.metric("Pasada T0", pass_date_str)
    col_sat2.metric("Nubes T0", f"{sentinel_meta.cloud_cover_pct:.1f}%")
    col_sat3.metric("Serie", f"{len(sentinel_series)} pasadas")

    if st.sidebar.button("🔄 Forzar Actualización Sentinel-2"):
        with st.spinner("Consultando Microsoft Planetary Computer STAC API para Sentinel-2..."):
            fresh_series = get_huelva_sentinel_series(passes_count=3, force_refresh=True)
            st.session_state["sentinel_series"] = fresh_series
            st.session_state["sentinel_meta"] = fresh_series[0] if fresh_series else get_latest_huelva_sentinel_pass(force_refresh=True)
            st.cache_data.clear()
            st.sidebar.success("🛰️ ¡Serie multitemporal Sentinel-2 actualizada con éxito!")
            st.rerun()

    show_pozas = st.sidebar.checkbox(
        "🌊 Mostrar Pozas y Canales en Mapa",
        value=True,
        help="Muestra u oculta las depresiones, canales de marea y pozas detectadas por satélite."
    )

    show_coastline = st.sidebar.checkbox(
        "🏖️ Línea de Costa Satelital (Pleamar MHW)",
        value=True,
        help="Delinea la orilla de pleamar del IGN y satélite que separa dunas y playa seca del agua marina."
    )

    only_confirmed_pozas = st.sidebar.checkbox(
        "🛡️ Solo Fosos de Alta Estabilidad (Persistencia ≥ 90% / 3 pasadas)",
        value=False,
        help="Muestra únicamente los 13 fosos estables confirmados en 3/3 pasadas consecutivas de Sentinel-2 (excluye canales dinámicos con 2 pasadas)."
    )

    method_choices = ["Todos los métodos", "SDB_STUMPF", "BREAKER_GAP", "PNOA_ORTHO"]
    method_labels = {
        "Todos los métodos": "Todos los métodos",
        "SDB_STUMPF": "🛰️ SDB Stumpf (Azul/Verde)",
        "BREAKER_GAP": "🌊 Brecha de Rompiente",
        "PNOA_ORTHO": "📸 Ortofoto PNOA 25cm",
    }
    selected_method = st.sidebar.selectbox(
        "Método de Detección Satelital:",
        method_choices,
        format_func=lambda m: method_labels.get(m, m),
        index=0,
    )

    cast_dist_range = st.sidebar.slider(
        "Rango de distancia de lance deseado (m):",
        min_value=20,
        max_value=130,
        value=(20, 130),
        step=5,
        help="Filtra pozas según la distancia de lance deseada (ej. 20-70m para caña corta o 90-130m para lances de surfcasting largo)."
    )
    min_cast_dist, max_cast_dist = cast_dist_range

    map_height_mode = st.sidebar.radio(
        "📐 Altura del Mapa:",
        options=["Estándar (580px)", "Ampliado (720px)", "Inmersivo (880px)"],
        index=0,
        horizontal=True,
        help="Ajusta la altura del mapa interactivo para adaptarse a pantallas grandes o dispositivos móviles."
    )
    map_height = 580 if "580" in map_height_mode else (720 if "720" in map_height_mode else 880)

    method_filter_val = None if selected_method == "Todos los métodos" else selected_method
    filtered_pozas = filter_pozas(
        synced_pozas,
        method=method_filter_val,
        min_distance=min_cast_dist,
        max_distance=max_cast_dist,
        min_persistence=90.0 if only_confirmed_pozas else None,
    )

    poza_focus_options = ["🔍 Vista General de Huelva (17 Pozas)"] + [
        f"{p.beach_name}: {p.name} ({p.distance_from_shore_m}m)" for p in filtered_pozas
    ]
    selected_poza_focus_idx = st.sidebar.selectbox(
        "🎯 Enfocar / Zoom en una Poza:",
        range(len(poza_focus_options)),
        format_func=lambda i: poza_focus_options[i],
        index=0,
        help="Selecciona una poza específica para que el mapa haga zoom inmediato (14x) sobre ella y muestre su foso submarino en detalle."
    )
    focused_poza_coords = None
    if selected_poza_focus_idx > 0 and (selected_poza_focus_idx - 1) < len(filtered_pozas):
        target_p = filtered_pozas[selected_poza_focus_idx - 1]
        focused_poza_coords = (target_p.latitude, target_p.longitude)

    # Micro-filters: Scenario Type & Bottom Type
    st.sidebar.markdown("### 🔍 Filtros de Escenario y Fondo")
    scenario_options = ["Todos los Escenarios", "Playa / Arenal", "Espigón / Estructura", "Ría / Estuario", "Roquedo / Acantilado", "Cala Mixta", "Desembocadura"]
    selected_scenario = st.sidebar.selectbox("Tipo de Escenario:", scenario_options)
    if selected_scenario != "Todos los Escenarios":
        filtered_spots = [s for s in filtered_spots if s.spot_type == selected_scenario]

    bottom_options = ["Todos los Fondos", "Arena fina", "Cascajo y grava", "Roca laminar / Laja", "Fango / Mixto", "Posidonia y arena"]
    selected_bottom = st.sidebar.selectbox("Fondo Submarino:", bottom_options)
    if selected_bottom != "Todos los Fondos":
        filtered_spots = [s for s in filtered_spots if s.bottom_type == selected_bottom]

    # Filter by Topographic Hotspots
    filter_hotspots_only = st.sidebar.checkbox(
        "⛰️ Solo Hotspots Topográficos",
        value=False,
        help="Muestra únicamente enclaves con caídas bruscas, cantiles pronunciados y bajos rocosos (Score Topográfico ≥ 68/100)."
    )
    if filter_hotspots_only:
        hotspots_subset = [s for s in filtered_spots if calculate_bathymetry_profile(s).topographic_hotspot_score >= 68.0]
        if hotspots_subset:
            filtered_spots = hotspots_subset
        else:
            st.sidebar.warning("No hay spots con relieve ≥ 68/100 en esta selección. Mostrando todos.")

    if not filtered_spots:
        filtered_spots = [s for s in all_spots if (selected_subzone_key == "Toda Andalucía" or s.subzone == selected_subzone_key)]

    # Spot Selector for Detail View
    st.sidebar.markdown("### 🎯 Micro-Spot Activo")
    spot_names = [f"{get_spot_type_icon(s.spot_type)} {s.name}" for s in filtered_spots]
    selected_spot_idx = st.sidebar.selectbox(
        "Seleccionar Spot para Análisis:",
        range(len(filtered_spots)),
        format_func=lambda i: spot_names[i],
        index=0,
    )
    selected_spot = filtered_spots[selected_spot_idx]

    # Algorithm Weights Configuration
    with st.sidebar.expander("⚙️ Calibración Fina de Pesos (Avanzado)", expanded=False):
        w_press = st.slider("Presión Barométrica (ΔP)", 0.05, 0.50, 0.25, 0.05)
        w_sol = st.slider("Ventanas Solunares y Crepúsculos", 0.05, 0.50, 0.30, 0.05)
        w_mar = st.slider("Estado del Mar (Oleaje y Periodo)", 0.05, 0.50, 0.20, 0.05)
        w_wind = st.slider("Viento Costero", 0.05, 0.40, 0.15, 0.05)
        w_moon = st.slider("Fase Lunar y Mareas Vivas", 0.05, 0.30, 0.10, 0.05)
        
        weights = ScoringWeights(
            weight_pressure=w_press,
            weight_solunar=w_sol,
            weight_marine=w_mar,
            weight_wind=w_wind,
            weight_moon_phase=w_moon,
        )

    # Refresh Cache
    if st.sidebar.button("🔄 Actualizar Datos en Vivo"):
        st.cache_data.clear()
        st.rerun()

    # Process Custom Spot if active
    custom_spot_forecast_tuple = None
    if st.session_state["custom_spot_coords"] is not None:
        c_lat, c_lon = st.session_state["custom_spot_coords"]
        custom_spot_obj = create_custom_spot_from_coords(c_lat, c_lon)
        c_fc_list = get_spot_hourly_forecast(custom_spot_obj, forecast_days=2, weights=weights)
        if c_fc_list:
            c_best = min(c_fc_list, key=lambda f: abs((f.timestamp - target_dt).total_seconds()))
            custom_spot_forecast_tuple = (custom_spot_obj, c_best)

    # Compute Buoys Telemetry Snapshot
    buoys_telemetry = get_buoy_telemetry_snapshot(all_buoys, target_dt)

    # Compute Snapshot for all filtered spots at target_dt
    spots_snapshot: List[Tuple[Spot, HourlySpotForecast]] = []
    with st.spinner(f"Calculando modelos oceanográficos, batimétricos y de especies en {selected_subzone_key}..."):
        for sp in filtered_spots:
            fc_list = get_cached_spot_forecasts(
                sp.id, sp,
                weights.weight_pressure, weights.weight_solunar,
                weights.weight_marine, weights.weight_wind, weights.weight_moon_phase
            )
            if fc_list:
                best_rec = min(fc_list, key=lambda f: abs((f.timestamp - target_dt).total_seconds()))
                spots_snapshot.append((sp, best_rec))

    # Sort descending by the active selected species mode score
    def _get_sort_key(item):
        val, _ = get_display_score_for_mode(item[1].score, selected_species_mode)
        return val

    spots_snapshot.sort(key=_get_sort_key, reverse=True)

    # --- TOP KPI METRIC CARDS ---
    if spots_snapshot:
        top_spot, top_fc = spots_snapshot[0]
        top_val, top_mode_label = get_display_score_for_mode(top_fc.score, selected_species_mode)
        avg_score = sum(_get_sort_key(it) for it in spots_snapshot) / len(spots_snapshot)
        solunar_ref = spots_snapshot[0][1].solunar_summary
        tide_ref = spots_snapshot[0][1].score.tide_state

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">🏆 TOP {top_mode_label.upper()}</div>
                <div class="metric-value">{top_spot.name.split('-')[0].strip()}</div>
                <div class="metric-subtitle">{top_val:.0f}/100 • ({top_spot.municipality or top_spot.province})</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">🌙 FASE LUNAR Y CICLO</div>
                <div class="metric-value">{solunar_ref.moon_illumination:.0f}% <span style='font-size:14px; font-weight:600;'>{solunar_ref.moon_phase_name.split()[0]}</span></div>
                <div class="metric-subtitle">{"🌊 Mareas Vivas (Spring)" if solunar_ref.is_spring_tide else "🌊 Mareas Muertas (Neap)"}</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">🌊 MAREA ASTRONÓMICA (ESTADO)</div>
                <div class="metric-value">Coeficiente {tide_ref.coefficient}</div>
                <div class="metric-subtitle">{tide_ref.state_name.split('(')[0]}</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">📊 PROMEDIO ({top_mode_label})</div>
                <div class="metric-value">{avg_score:.1f} <span style='font-size:14px; font-weight:500;'>/ 100</span></div>
                <div class="metric-subtitle">{len(spots_snapshot)} spots analizados</div>
            </div>
            """, unsafe_allow_html=True)

        # Calculate Golden Bite Window / Momento de Oro for top/reference spot
        ref_spot_kpi, ref_fc_kpi = spots_snapshot[0]
        golden_kpi = calculate_golden_bite_window(
            ref_fc_kpi.score,
            ref_fc_kpi.marine,
            ref_fc_kpi.weather,
            ref_fc_kpi.solunar_summary,
        )

        golden_bg = "linear-gradient(135deg, #fefce8 0%, #fef08a 100%)" if golden_kpi["is_golden"] else (
            "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)" if golden_kpi["is_favorable"] else "#f8fafc"
        )
        golden_border = "#eab308" if golden_kpi["is_golden"] else ("#22c55e" if golden_kpi["is_favorable"] else "#cbd5e1")
        golden_badge_bg = "#ca8a04" if golden_kpi["is_golden"] else ("#16a34a" if golden_kpi["is_favorable"] else "#64748b")
        golden_factors_html = "".join(
            f"<span style='background:rgba(255,255,255,0.85); color:#1e293b; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; border:1px solid {golden_border};'>{f}</span>"
            for f in golden_kpi["factors_met"]
        )

        st.markdown(f"""
        <div style='background: {golden_bg}; border: 1.5px solid {golden_border}; border-radius: 10px; padding: 12px 18px; margin: 12px 0 16px 0;'>
            <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>
                <div style='display:flex; align-items:center; gap:8px;'>
                    <span style='font-size:18px;'>{"🌟" if golden_kpi["is_golden"] else ("⚡" if golden_kpi["is_favorable"] else "🧭")}</span>
                    <span style='color: #0f172a; font-weight: 800; font-size: 14px;'>RADAR DE COINCIDENCIA BIOLÓGICA: {golden_kpi["status_label"]}</span>
                </div>
                <span style='background:{golden_badge_bg}; color:white; padding:3px 10px; border-radius:12px; font-size:11.5px; font-weight:700;'>
                    Alineación: {golden_kpi["golden_score"]:.0f}/100
                </span>
            </div>
            <div style='color: #334155; font-size: 12.5px; margin-top: 4px; line-height:1.4;'>
                {golden_kpi["summary"]}
            </div>
            {f"<div style='display:flex; flex-wrap:wrap; gap:5px; margin-top:8px;'>{golden_factors_html}</div>" if golden_factors_html else ""}
        </div>
        """, unsafe_allow_html=True)

    # --- MAIN TABS ---
    tab_map, tab_detail, tab_buoys = st.tabs([
        "🗺️ Mapa Interactivo & Clic",
        "📊 Detalle y Evolución del Spot",
        "⚓ Boyas Marinas Oficiales (REDEXT)",
    ])

    # 1. TAB: INTERACTIVE MAP & CLICK MODE
    with tab_map:
        st.markdown(f"#### Mapa Granular: **{selected_subzone_key}** — Modo: **{species_mode_options[selected_species_mode]}**")
        if filter_hotspots_only:
            st.success(f"⛰️ **Filtro de Hotspots Activo:** Mostrando {len(spots_snapshot)} enclaves con relieve submarino destacado (cantiles, caídas y bajos rocosos con halos y distintivos morados ⛰️).")
        else:
            st.info("💡 **Consejo:** Para ver los cantiles y bajos rocosos destacados, activa la capa **'⛰️ Hotspots Topográficos (Cantiles y Bajos)'** en el control de capas arriba a la derecha del mapa, o marca **'⛰️ Solo Hotspots Topográficos'** en la barra lateral.")

        # Reference environmental conditions for pozas fishability evaluation
        ref_fc = spots_snapshot[0][1] if spots_snapshot else None
        
        curr_tide_name = "Pleamar"
        if ref_fc and ref_fc.score and ref_fc.score.tide_state and ref_fc.score.tide_state.state_name:
            curr_tide_name = str(ref_fc.score.tide_state.state_name)

        curr_tide_coeff = 75.0
        if ref_fc and ref_fc.score and ref_fc.score.tide_state and ref_fc.score.tide_state.coefficient is not None:
            try:
                curr_tide_coeff = float(ref_fc.score.tide_state.coefficient)
            except (TypeError, ValueError):
                curr_tide_coeff = 75.0

        curr_wave_h = 0.8
        if ref_fc and ref_fc.marine and ref_fc.marine.wave_height is not None:
            try:
                curr_wave_h = float(ref_fc.marine.wave_height)
            except (TypeError, ValueError):
                curr_wave_h = 0.8

        curr_knots = 1.0
        if ref_fc and ref_fc.marine and ref_fc.marine.current_velocity_knots is not None:
            try:
                curr_knots = float(ref_fc.marine.current_velocity_knots)
            except (TypeError, ValueError):
                curr_knots = 1.0

        if selected_subzone_key != "Costa de Huelva":
            st.warning(
                f"📍 Tienes seleccionado el litoral **{selected_subzone_key}**. "
                f"Las **17 pozas detectadas por satélite** están cartografiadas en la **Costa de Huelva** (Ayamonte a Matalascañas). "
                f"Para visualizarlas con sus balizas cian en el mapa, selecciona **Costa de Huelva** en la barra lateral o pulsa el botón directo:"
            )
            if st.button("🌊 Cambiar Litoral a Costa de Huelva para Ver las Pozas"):
                st.session_state["forced_subzone"] = "Costa de Huelva"
                st.rerun()

        if show_pozas and selected_subzone_key == "Costa de Huelva":
            pass_date = sentinel_meta.datetime.split("T")[0] if "T" in sentinel_meta.datetime else sentinel_meta.datetime[:10]
            link_html = f" • [🔗 Ver Escena Sentinel-2 MSI en Planetary Computer]({sentinel_meta.visual_url})" if sentinel_meta.visual_url else ""
            focus_text = f" • 🎯 **Enfocando:** `{filtered_pozas[selected_poza_focus_idx - 1].name}`" if focused_poza_coords else ""
            st.success(
                f"🌊 **Pozas de Surfcasting Validadas y Contrastadas ({len(filtered_pozas)} enclaves en Costa de Huelva):** "
                f"Contrastadas a través de **{len(sentinel_series)} pasadas satelitales consecutivas** de Sentinel-2 L2A ({pass_date}, nubes {sentinel_meta.cloud_cover_pct:.1f}%). "
                f"**100% validadas mar adentro** mediante el módulo de detección de línea de costa MHW (a 20-130m de la orilla tras la rompiente). "
                f"💡 *Tip:* Cambia la capa base arriba a la derecha a **'🛰️ Satélite Esri'** o **'📸 Ortofoto PNOA'** para observar las barras de arena y la línea de costa dorada.{focus_text}{link_html}"
            )

        map_kwargs = {
            "spots_data": spots_snapshot,
            "selected_spot_id": selected_spot.id if selected_spot and not st.session_state["custom_spot_coords"] else None,
            "subzone_filter": selected_subzone_key,
            "custom_spot_data": custom_spot_forecast_tuple,
            "buoys_data": buoys_telemetry,
            "rivers_data": all_rivers,
            "score_mode": selected_species_mode,
            "highlight_hotspots": filter_hotspots_only,
            "pozas_data": filtered_pozas,
            "show_pozas": show_pozas,
            "show_coastline": show_coastline,
            "current_tide_name": curr_tide_name,
            "current_tide_coeff": curr_tide_coeff,
            "current_wave_h": curr_wave_h,
            "current_knots": curr_knots,
            "focused_poza_coords": focused_poza_coords,
        }

        # Filter kwargs defensively against module cache skew in Streamlit Cloud hot-reloads
        try:
            sig = inspect.signature(create_andalucia_fishing_map)
            has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            if not has_varkw:
                map_kwargs = {k: v for k, v in map_kwargs.items() if k in sig.parameters}
        except Exception:
            pass

        folium_map = create_andalucia_fishing_map(**map_kwargs)

        map_output = st_folium(
            folium_map,
            width=None,
            height=map_height,
            returned_objects=["last_clicked", "last_object_clicked"],
        )

        if map_output and map_output.get("last_clicked"):
            clicked = map_output["last_clicked"]
            clicked_lat = round(clicked["lat"], 4)
            clicked_lng = round(clicked["lng"], 4)

            if (35.5 <= clicked_lat <= 38.0) and (-8.0 <= clicked_lng <= -1.5):
                prev_coords = st.session_state.get("custom_spot_coords")
                if prev_coords is None or (abs(prev_coords[0] - clicked_lat) > 0.001 or abs(prev_coords[1] - clicked_lng) > 0.001):
                    st.session_state["custom_spot_coords"] = (clicked_lat, clicked_lng)
                    st.success(f"📍 ¡Coordenada seleccionada! Latitud: `{clicked_lat}°N`, Longitud: `{clicked_lng}°W`. Actualizando...")
                    st.rerun()



        if show_pozas and filtered_pozas and selected_subzone_key == "Costa de Huelva":
            with st.expander(f"📋 Ver Catálogo Completo de las {len(filtered_pozas)} Pozas Detectadas por Satélite en Huelva", expanded=False):
                pozas_rows = []
                ref_next_high = ref_fc.score.tide_state.next_high_tide if ref_fc and ref_fc.score and ref_fc.score.tide_state else None
                ref_next_low = ref_fc.score.tide_state.next_low_tide if ref_fc and ref_fc.score and ref_fc.score.tide_state else None
                ref_secchi = ref_fc.score.water_clarity.secchi_depth_m if ref_fc and ref_fc.score and ref_fc.score.water_clarity else 2.0
                for p in filtered_pozas:
                    p_eval = evaluate_poza_fishability(
                        poza=p,
                        tide_state_name=curr_tide_name,
                        tide_coeff=curr_tide_coeff,
                        wave_height_m=curr_wave_h,
                        current_speed_knots=curr_knots,
                        next_high_tide=ref_next_high,
                        next_low_tide=ref_next_low,
                        target_dt=target_dt,
                        secchi_depth_m=ref_secchi,
                    )
                    rig_dict = p_eval.get("recommended_rig", {})
                    pozas_rows.append({
                        "Playa / Sector": p.beach_name,
                        "Nombre del Foso / Poza": p.name,
                        "Lance": f"{p.distance_from_shore_m} m",
                        "Foso": f"+{p.relative_depth_m} m",
                        "Dimensiones": f"{p.width_m}x{p.length_m} m",
                        "Score Actual": f"{p_eval['fishability_score']:.0f}/100",
                        "Ventana Pico Hoy": p_eval.get("optimal_time_window_today", p.optimal_tide_stage),
                        "Montaje Sugerido": rig_dict.get("rig_name", "Urfe corto").split("(")[0].strip(),
                        "Plomo": rig_dict.get("lead_type", f"{p_eval['recommended_lead_g']}g").split("(")[0].strip(),
                        "Persistencia": f"{p.persistence_score:.0f}% ({p.temporal_passes_count}/3 pasadas)",
                        "Deriva Litoral": f"~{p.drift_offset_m:.1f} m",
                        "Estabilidad": p.morphodynamic_stability.split("(")[0].strip(),
                        "Línea de Costa": f"🌊 Mar ({p.distance_from_shore_m}m)",
                        "Especies": ", ".join(p.target_species[:3]),
                    })
                df_pozas = pd.DataFrame(pozas_rows)
                st.dataframe(df_pozas, use_container_width=True, hide_index=True)

    # 2. TAB: SPOT DETAIL & TIMELINE
    with tab_detail:
        if custom_spot_forecast_tuple is not None:
            active_spot_obj = custom_spot_forecast_tuple[0]
            st.warning(f"🎯 Visualizando **Punto Personalizado Clicado en el Mapa**: `{active_spot_obj.latitude:.4f}°N, {active_spot_obj.longitude:.4f}°W`")
        else:
            active_spot_obj = selected_spot

        st.markdown(f"### Ficha Táctica y Evolución: **{active_spot_obj.name}**")
        
        spot_forecasts = get_spot_hourly_forecast(active_spot_obj, forecast_days=3, weights=weights)

        current_spot_fc = min(spot_forecasts, key=lambda f: abs((f.timestamp - target_dt).total_seconds()))
        sc = current_spot_fc.score
        m = current_spot_fc.marine
        w = current_spot_fc.weather
        sol = current_spot_fc.solunar_summary
        tide = sc.tide_state
        wind_asp = sc.wind_aspect
        bathy = sc.bathymetry
        clarity = sc.water_clarity
        river = sc.river_runoff

        spec_val, spec_name = get_display_score_for_mode(sc, selected_species_mode)

        badge_class = (
            "badge-excellent" if spec_val >= 75 else
            "badge-good" if spec_val >= 60 else
            "badge-moderate" if spec_val >= 45 else "badge-bad"
        )

        st.markdown(f"""
        <div style='background:#f8fafc; border:1px solid #e2e8f0; border-left: 6px solid {sc.rating_color}; border-radius:10px; padding:16px 20px; margin-bottom:18px;'>
            <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>
                <div>
                    <h3 style='margin:0; color:#0f172a;'>{get_spot_type_icon(active_spot_obj.spot_type)} {active_spot_obj.name}</h3>
                    <div style='color:#64748b; font-size:13px; margin-top:2px;'>
                        📍 Municipio: <b>{active_spot_obj.municipality or active_spot_obj.province}</b> • Subzona: <b>{active_spot_obj.subzone}</b> • Coordenadas: <b>{active_spot_obj.latitude:.4f}°N, {active_spot_obj.longitude:.4f}°W</b>
                    </div>
                </div>
                <div style='text-align:right;'>
                    <span class='{badge_class}' style='font-size:16px; padding:6px 14px;'>
                        {spec_name}: {spec_val:.0f}/100
                    </span>
                    <div style='font-size:11px; color:#64748b; margin-top:3px;'>Score Global: <b>{sc.overall_score:.0f}/100</b> ({sc.rating_tier})</div>
                </div>
            </div>
            
            <div style='margin-top:10px;'>
                <span class='micro-tag'>🏖️ Escenario: {active_spot_obj.spot_type}</span>
                <span class='micro-tag'>🪨 Fondo: {active_spot_obj.bottom_type}</span>
                <span class='micro-tag'>🚶 Acceso: {active_spot_obj.accessibility}</span>
                <span class='micro-tag'>🌊 {tide.state_name} (Coef. {tide.coefficient})</span>
                <span class='micro-tag'>🧭 Corriente: {m.current_velocity_knots} kts ({m.current_direction:.0f}°) • {m.current_intensity_level.split()[0]}</span>
                <span class='micro-tag'>🍃 {wind_asp.wind_type}</span>
                {f"<span class='micro-tag' style='background:#eff6ff; color:#1e40af;'>📡 Calibrado con {sc.calibrating_buoy_name}</span>" if sc.buoy_calibration_applied else ""}
            </div>

            <div style='margin-top:10px; font-size:13px; color:#334155; line-height:1.5;'>
                {active_spot_obj.description}
            </div>
            
            <div style='margin-top:10px; display:flex; flex-wrap:wrap; gap:6px;'>
                {"".join(f"<span style='background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:12px; font-size:12px; font-weight:600;'>🐟 {sp}</span>" for sp in active_spot_obj.target_species)}
                {"".join(f"<span style='background:#f1f5f9; color:#475569; padding:3px 8px; border-radius:12px; font-size:12px; font-weight:500;'>🎣 {t}</span>" for t in active_spot_obj.recommended_techniques)}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Advanced Oceanographic Diagnostics Row: Bathymetry, Water Clarity, River Plumes
        if bathy and clarity and river:
            st.markdown("##### 🔬 Diagnóstico Oceanográfico Avanzado (Relieve, Claridad y Ríos):")
            c_bathy, c_clarity, c_river = st.columns(3)
            with c_bathy:
                st.markdown(f"""
                <div style='background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px;'>
                    <div style='font-size: 11px; font-weight: 700; color: #166534;'>⛰️ RELIEVE SUBMARINO (EMODNET)</div>
                    <div style='font-size: 15px; font-weight: 800; color: #0f172a; margin: 3px 0;'>{bathy.structure_type}</div>
                    <div style='font-size: 12px; color: #374151;'>
                        • Pendiente del fondo: <b>{bathy.depth_gradient_pct}%</b><br>
                        • Índice Rugosidad: <b>{bathy.rugosity_index}</b><br>
                        • Hotspot Estructural: <b>{bathy.topographic_hotspot_score:.0f}/100</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with c_clarity:
                st.markdown(f"""
                <div style='background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 12px;'>
                    <div style='font-size: 11px; font-weight: 700; color: #0369a1;'>👁️ CLARIDAD DEL AGUA SATELITAL</div>
                    <div style='font-size: 15px; font-weight: 800; color: #0f172a; margin: 3px 0;'>{clarity.clarity_class}</div>
                    <div style='font-size: 12px; color: #374151;'>
                        • Disco Secchi: <b>{clarity.secchi_depth_m} m</b> de visión<br>
                        • Turbidez: <b>{clarity.turbidity_ntu} NTU</b><br>
                        • Frente Térmico: <b>{"🌊 Activo (" + str(clarity.sst_gradient_c_km) + " °C/km)" if clarity.thermal_front_detected else "Estable"}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with c_river:
                plume_badge = "<span style='color:#b45309; font-weight:700;'>🌊 Pluma Activa</span>" if river.plume_active else "<span style='color:#64748b;'>Inactiva</span>"
                st.markdown(f"""
                <div style='background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 12px;'>
                    <div style='font-size: 11px; font-weight: 700; color: #b45309;'>🏞️ INFLUENCIA FLUVIAL Y CUENCA</div>
                    <div style='font-size: 15px; font-weight: 800; color: #0f172a; margin: 3px 0;'>{river.nearest_river_name}</div>
                    <div style='font-size: 12px; color: #374151;'>
                        • Distancia a desembocadura: <b>{river.distance_to_mouth_km} km</b><br>
                        • Estado de la pluma: {plume_badge}<br>
                        • Salinidad: <b>{f"-{river.salinity_drop_psu} PSU" if river.plume_active else "Oceánica (~37 PSU)"}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        if sc.tactical_tips:
            st.markdown("##### 💡 Diagnóstico Biológico y Consejos Tácticos:")
            tip_cols = st.columns(len(sc.tactical_tips))
            for i, tip in enumerate(sc.tactical_tips):
                with tip_cols[i]:
                    st.info(tip)

        # Tactical Rig and Terminal Recommendation Card
        spot_rig = recommend_surfcasting_rig(
            wave_height_m=m.wave_height,
            current_speed_knots=m.current_velocity_knots,
            secchi_depth_m=clarity.secchi_depth_m if clarity else 2.0,
            target_species=active_spot_obj.target_species,
        )

        st.markdown(f"""
        <div style='background: #f8fafc; border: 1.5px solid #cbd5e1; border-left: 6px solid #0284c7; border-radius: 8px; padding: 14px 18px; margin: 16px 0;'>
            <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-bottom: 6px;'>
                <span style='color: #0f172a; font-weight: 800; font-size: 13.5px;'>🎣 RECOMENDACIÓN DE MONTAJE Y TERMINAL (A Pie de Playa):</span>
                <b style='background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:10px; font-size:11px;'>Táctica Hidrodinámica</b>
            </div>
            <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; font-size: 12px; color: #334155; margin-top: 8px;'>
                <div>
                    <b>🔘 Tipo de Plomo:</b> {spot_rig['lead_type']}<br>
                    <span style='font-size:11px; color:#64748b;'>{spot_rig['lead_advice']}</span>
                </div>
                <div>
                    <b>🪢 Montaje / Bajo:</b> {spot_rig['rig_name']}<br>
                    <span style='font-size:11px; color:#64748b;'>{spot_rig['rig_desc']}</span>
                </div>
                <div>
                    <b>🧵 Cameta Fluorocarbono:</b> {spot_rig['fluorocarbon']}<br>
                    <span style='font-size:11px; color:#64748b;'>{spot_rig['fluoro_desc']}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Species Comparison Bar Chart
        fig_species = create_species_comparison_chart(sc.species_scores)
        st.plotly_chart(fig_species, use_container_width=True)

        # Dual Axis Pressure & Score Chart
        fig_pressure = create_pressure_and_score_chart(spot_forecasts, selected_time=target_dt, species_mode=selected_species_mode)
        st.plotly_chart(fig_pressure, use_container_width=True)

        # Marine & Wind Chart
        fig_marine = create_marine_and_wind_chart(spot_forecasts, selected_time=target_dt)
        st.plotly_chart(fig_marine, use_container_width=True)

        # Continuous Tidal Wave Chart
        fig_tide = create_continuous_tide_chart(spot_forecasts, selected_time=target_dt)
        st.plotly_chart(fig_tide, use_container_width=True)

        col_radar, col_solunar = st.columns([1, 1])

        with col_radar:
            fig_radar = create_score_radar_chart(sc)
            st.plotly_chart(fig_radar, use_container_width=True)

        with col_solunar:
            st.markdown(f"##### 🌙 Efemérides Solunares y Mareas (`{target_dt.strftime('%d/%m/%Y')}`)")
            high_str = tide.next_high_tide.strftime("%H:%M UTC") if tide.next_high_tide else "--:--"
            low_str = tide.next_low_tide.strftime("%H:%M UTC") if tide.next_low_tide else "--:--"

            solunar_rows = [
                {"Evento": "🌕 Fase Lunar", "Detalle": f"{sol.moon_phase_name} ({sol.moon_illumination:.1f}% ilum.)"},
                {"Evento": "🌊 Coeficiente de Marea", "Detalle": f"Coef. {tide.coefficient} ({'Mareas Vivas' if sol.is_spring_tide else 'Mareas Muertas'})"},
                {"Evento": "🌊 Próxima Pleamar (Alta)", "Detalle": f"{high_str} (en {tide.minutes_to_high_tide or 0} min)"},
                {"Evento": "🌊 Próxima Bajamar (Baja)", "Detalle": f"{low_str} (en {tide.minutes_to_low_tide or 0} min)"},
                {"Evento": "🌅 Salida / Puesta de Sol", "Detalle": f"🌅 {sol.sunrise.strftime('%H:%M') if sol.sunrise else '--:--'} • 🌇 {sol.sunset.strftime('%H:%M') if sol.sunset else '--:--'} UTC"},
                {"Evento": "⭐ Periodo Mayor 1 (Cenit)", "Detalle": sol.moon_zenith.strftime("%H:%M UTC (±1h)") if sol.moon_zenith else "--:--"},
                {"Evento": "⭐ Periodo Mayor 2 (Nadir)", "Detalle": sol.moon_nadir.strftime("%H:%M UTC (±1h)") if sol.moon_nadir else "--:--"},
                {"Evento": "🌙 Periodos Menores (Orto/Ocaso)", "Detalle": f"🌙 {sol.moonrise.strftime('%H:%M') if sol.moonrise else '--'} / {sol.moonset.strftime('%H:%M') if sol.moonset else '--'} UTC"},
            ]
            st.dataframe(pd.DataFrame(solunar_rows), hide_index=True, use_container_width=True)

        st.markdown("##### 📋 Tabla de Predicción Horaria Detallada")
        table_records = []
        for f in spot_forecasts[:24]:
            val_hour, _ = get_display_score_for_mode(f.score, selected_species_mode)
            clarity_val = f.score.water_clarity.clarity_class.split('(')[0].strip() if f.score.water_clarity else "—"
            gold_h = calculate_golden_bite_window(f.score, f.marine, f.weather, f.solunar_summary)
            gold_tag = "⭐ PICO" if gold_h["is_golden"] else ("⚡ Bueno" if gold_h["is_favorable"] else "—")
            table_records.append({
                "Hora (UTC)": f.timestamp.strftime("%d/%m %H:00"),
                "Ventana Oro": gold_tag,
                f"Score ({species_mode_options[selected_species_mode].split()[1]})": f"{val_hour:.0f}",
                "Score Global": f"{f.score.overall_score:.0f}",
                "Presión (hPa)": f"{f.weather.surface_pressure:.1f}",
                "ΔP (3h)": f"{f.score.pressure_delta_3h:+.1f}",
                "Ola (m)": f"{f.marine.wave_height:.2f}",
                "Periodo (s)": f"{f.marine.wave_period:.1f}",
                "Corriente": f"{f.marine.current_velocity_knots:.2f} kts ({f.marine.current_direction:.0f}°)",
                "Claridad": clarity_val,
                "Viento": f"{f.weather.wind_speed_10m:.1f} km/h ({f.score.wind_aspect.wind_type.split()[0]})",
                "Marea": f"{f.score.tide_state.state_name.split('(')[0]} (Coef. {f.score.tide_state.coefficient})",
                "Ventana Solunar": f.score.solunar_window_active or "—",
            })
        st.dataframe(pd.DataFrame(table_records), hide_index=True, use_container_width=True)

    # 3. TAB: MARINE BUOYS
    with tab_buoys:
        st.markdown("### ⚓ Red Oficial de Boyas Oceanográficas de Andalucía (Puertos del Estado)")
        st.markdown("<span style='font-size:13px; color:#64748b;'>Las boyas de la Red Exterior (REDEXT) y Red Costera (REDCOS) miden in-situ parámetros de oleaje espectral, periodos reales y temperatura marina.</span>", unsafe_allow_html=True)

        b_cols = st.columns(len(buoys_telemetry)) if len(buoys_telemetry) <= 4 else st.columns(4)
        for i, (buoy, obs) in enumerate(buoys_telemetry):
            col_idx = i % len(b_cols)
            with b_cols[col_idx]:
                st.markdown(f"""
                <div style='background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:12px; margin-bottom:12px;'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <span style='font-size:10px; font-weight:700; color:#166534;'>{buoy.network.split()[0]} • {buoy.code}</span>
                        <span style='background:#16a34a; color:white; padding:2px 6px; border-radius:8px; font-size:10px; font-weight:700;'>ONLINE</span>
                    </div>
                    <h4 style='margin:4px 0; color:#0f172a; font-size:13px;'>⚓ {buoy.name}</h4>
                    <div style='margin-top:6px; font-size:12px; color:#1e293b;'>
                        🌊 <b>Hs:</b> {obs.wave_height_hs}m &nbsp;|&nbsp; ⏱️ <b>Tp:</b> {obs.wave_period_tp}s<br>
                        🌡️ <b>Agua:</b> {obs.sea_surface_temperature}°C &nbsp;|&nbsp; 💨 <b>Viento:</b> {obs.wind_speed}km/h
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("##### 📋 Telemetría Detallada de Boyas Marinas")
        buoys_table_rows = []
        for buoy, obs in buoys_telemetry:
            buoys_table_rows.append({
                "Boya": buoy.name,
                "Código": buoy.code,
                "Red": buoy.network,
                "Provincia": buoy.province,
                "Profundidad (m)": f"{buoy.depth_m:.0f}m",
                "Ola Real Hs (m)": f"{obs.wave_height_hs:.2f} m",
                "Periodo Pico Tp (s)": f"{obs.wave_period_tp:.1f} s",
                "Temp. Agua (°C)": f"{obs.sea_surface_temperature:.1f} °C",
                "Presión (hPa)": f"{obs.surface_pressure:.1f} hPa" if obs.surface_pressure else "—",
                "Viento (km/h)": f"{obs.wind_speed:.1f} km/h" if obs.wind_speed else "—",
                "Estado": obs.status,
            })
        st.dataframe(pd.DataFrame(buoys_table_rows), hide_index=True, use_container_width=True)



if __name__ == "__main__":
    main()
