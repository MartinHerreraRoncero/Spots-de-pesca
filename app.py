"""
Aplicación Principal Streamlit: Sistema de Predicción y Scoring de Pesca Marina en Andalucía.
Incluye:
- Modo de Scoring Especializado por Especie (Dorada, Lubina, Sargo, Calamar, Dentón, Corvina) + Score Global
- Mareas Astronómicas, Coeficientes y Repuntes Hidráulicos
- Viento Relativo a la Costa (Onshore / Offshore / Upwelling)
- Asimilación de Datos y Calibración In-Situ con Boyas de Puertos del Estado (REDEXT / REDCOS)
- Modo Clic en el Mapa (análisis de cualquier coordenada GPS libre)
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.models.spot import Spot, HourlySpotForecast, MarineBuoy, BuoyObservation, ScoringWeights
from src.fetchers.open_meteo import (
    load_spots_from_json,
    load_marine_buoys_from_json,
    create_custom_spot_from_coords,
    get_spot_hourly_forecast,
    get_all_spots_snapshot,
    get_buoy_telemetry_snapshot,
)
from src.analytics.solunar import compute_daily_solunar
from src.visualization.map_view import (
    create_andalucia_fishing_map,
    get_spot_type_icon,
    get_display_score_for_mode,
)
from src.visualization.charts import (
    create_pressure_and_score_chart,
    create_marine_and_wind_chart,
    create_score_radar_chart,
    create_species_comparison_chart,
    create_top_spots_bar_chart,
)

# Page configuration
st.set_page_config(
    page_title="PescaMar Andalucía | GIS, Solunar, Mareas, Clic & Boyas",
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
        help="Elige una especie para que el mapa, los gráficos y el ranking se adapten a sus requerimientos biológicos concretos, sin perder la puntuación global."
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

    selected_subzone_idx = st.sidebar.selectbox(
        "Litoral Costero:",
        range(len(subzone_choices)),
        format_func=lambda i: subzone_labels[i],
        index=0,
    )
    selected_subzone_key = subzone_choices[selected_subzone_idx]

    if selected_subzone_key == "Toda Andalucía":
        filtered_spots = all_spots
    else:
        filtered_spots = [s for s in all_spots if s.subzone == selected_subzone_key]

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
    with st.spinner(f"Calculando modelos oceanográficos y de especies en {selected_subzone_key}..."):
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

    # --- MAIN TABS ---
    tab_map, tab_detail, tab_buoys, tab_ranking, tab_guide = st.tabs([
        "🗺️ Mapa Interactivo & Clic",
        "📊 Detalle y Evolución del Spot",
        "⚓ Boyas Marinas Oficiales (REDEXT)",
        "🏆 Ranking y Comparador de la Zona",
        "📖 Metodología y Fundamentos Científicos",
    ])

    # 1. TAB: INTERACTIVE MAP & CLICK MODE
    with tab_map:
        st.markdown(f"#### Mapa Granular: **{selected_subzone_key}** — Modo: **{species_mode_options[selected_species_mode]}**")
        st.info("💡 **Modo Clic en el Mapa:** Haz clic en cualquier cala, espigón o coordenada para analizarla. Los círculos reflejan la puntuación específica para la especie seleccionada.")

        folium_map = create_andalucia_fishing_map(
            spots_data=spots_snapshot,
            selected_spot_id=selected_spot.id if selected_spot and not st.session_state["custom_spot_coords"] else None,
            subzone_filter=selected_subzone_key,
            custom_spot_data=custom_spot_forecast_tuple,
            buoys_data=buoys_telemetry,
            score_mode=selected_species_mode,
        )

        map_output = st_folium(
            folium_map,
            width=None,
            height=580,
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

        leg1, leg2, leg3, leg4 = st.columns(4)
        with leg1:
            st.markdown("<span class='badge-excellent'>🟢 Excelente (Score ≥ 75)</span>", unsafe_allow_html=True)
        with leg2:
            st.markdown("<span class='badge-good'>🟡 Muy Bueno (Score 60 - 74)</span>", unsafe_allow_html=True)
        with leg3:
            st.markdown("<span class='badge-moderate'>🟠 Favorable (Score 45 - 59)</span>", unsafe_allow_html=True)
        with leg4:
            st.markdown("<span class='badge-bad'>🔴 Desfavorable (Score < 45)</span>", unsafe_allow_html=True)

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

        if sc.tactical_tips:
            st.markdown("##### 💡 Diagnóstico Biológico, Marea y Viento Relativo:")
            tip_cols = st.columns(len(sc.tactical_tips))
            for i, tip in enumerate(sc.tactical_tips):
                with tip_cols[i]:
                    st.info(tip)

        # Species Comparison Bar Chart
        fig_species = create_species_comparison_chart(sc.species_scores)
        st.plotly_chart(fig_species, use_container_width=True)

        # Dual Axis Pressure & Score Chart
        fig_pressure = create_pressure_and_score_chart(spot_forecasts, selected_time=target_dt, species_mode=selected_species_mode)
        st.plotly_chart(fig_pressure, use_container_width=True)

        # Marine & Wind Chart
        fig_marine = create_marine_and_wind_chart(spot_forecasts, selected_time=target_dt)
        st.plotly_chart(fig_marine, use_container_width=True)

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
            table_records.append({
                "Hora (UTC)": f.timestamp.strftime("%d/%m %H:00"),
                f"Score ({species_mode_options[selected_species_mode].split()[1]})": f"{val_hour:.0f}",
                "Score Global": f"{f.score.overall_score:.0f}",
                "Presión (hPa)": f"{f.weather.surface_pressure:.1f}",
                "ΔP (3h)": f"{f.score.pressure_delta_3h:+.1f}",
                "Ola (m)": f"{f.marine.wave_height:.2f}",
                "Periodo (s)": f"{f.marine.wave_period:.1f}",
                "Corriente": f"{f.marine.current_velocity_knots:.2f} kts ({f.marine.current_direction:.0f}°)",
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

    # 4. TAB: RANKING & COMPARATOR
    with tab_ranking:
        st.markdown(f"### 🏆 Clasificación en **{selected_subzone_key}** — Modo: **{species_mode_options[selected_species_mode]}**")
        
        fig_bar = create_top_spots_bar_chart(spots_snapshot, score_mode=selected_species_mode, top_n=min(12, len(spots_snapshot)))
        st.plotly_chart(fig_bar, use_container_width=True)

        ranking_data = []
        for rank, (sp, fc) in enumerate(spots_snapshot, 1):
            score_val, _ = get_display_score_for_mode(fc.score, selected_species_mode)
            ranking_data.append({
                "Posición": f"#{rank}",
                "Micro-Spot": sp.name,
                "Municipio": sp.municipality or sp.province,
                "Escenario": sp.spot_type,
                "Fondo": sp.bottom_type,
                f"Score ({selected_species_mode})": score_val,
                "Score Global": fc.score.overall_score,
                "Marea": f"Coef. {fc.score.tide_state.coefficient}",
                "Viento": f"{fc.weather.wind_speed_10m:.1f} km/h ({fc.score.wind_aspect.wind_type.split()[0]})",
                "Ola (m)": fc.marine.wave_height,
                "Periodo (s)": fc.marine.wave_period,
            })

        df_rank = pd.DataFrame(ranking_data)
        st.dataframe(
            df_rank,
            hide_index=True,
            use_container_width=True,
            column_config={
                f"Score ({selected_species_mode})": st.column_config.ProgressColumn(
                    "Score Específico",
                    help="Puntuación calibrada para la especie seleccionada",
                    format="%.0f",
                    min_value=0,
                    max_value=100,
                ),
                "Score Global": st.column_config.ProgressColumn(
                    "Score Global",
                    format="%.0f",
                    min_value=0,
                    max_value=100,
                ),
            }
        )

    # 5. TAB: METHODOLOGY & SCIENTIFIC GUIDE
    with tab_guide:
        st.markdown("""
        ### 📚 Fundamentos Científicos del Motor Predictivo Avanzado

        **PescaMar Andalucía** integra modelos de física atmosférica, hidrodinámica de fluidos, astronomía orbital y etología marina:

        ---

        #### 1. Dinámica Barométrica y Fisiología de la Vejiga Natatoria (25%)
        * **Descenso Pre-Frontera (\(\Delta P_{3h} \in [-0.5, -1.8]\text{ hPa}\)):** Estimula la alimentación previa a frentes fríos.
        * **Penalización por Caída Violenta (\(<-3.0\text{ hPa}\)):** Desplaza a los peces a zonas profundas.

        ---

        #### 2. Mareas Astronómicas, Coeficientes y Repuntes
        * **Ciclo Semidiurno Andaluz:** Pleamares y bajamares cada ~12h 25m.
        * **Coeficiente de Marea (20 a 120):** Las mareas vivas (>80) multiplican las corrientes en el Golfo de Cádiz y el Estrecho de Gibraltar, movilizando nutrientes.
        * **Repunte de Pleamar:** Momento óptimo para espáridos (dorada, sargo, herrera) al inundar nuevos bancos de moluscos.

        ---

        #### 3. Viento Relativo a la Costa (Onshore / Offshore / Upwelling)
        * **Onshore (De cara):** Oxigena la orilla, acerca alimento hacia la rompiente y enturbia el agua.
        * **Offshore (De espalda):** Aplana el mar y facilita el lance lejano. En Málaga y Granada, vientos persistentes de tierra generan **Upwelling** (afloramiento de aguas frías profundas).

        ---

        #### 4. Asimilación de Datos con Boyas de Puertos del Estado (REDEXT)
        * Calibra la altura y periodo de ola en tiempo real comparando las predicciones numéricas con las boyas oceanográficas más cercanas mediante interpolación espacial IDW.

        ---

        #### 5. Scoring Especializado Multi-Especie
        * **Dorada / Herrera:** Maximiza pleamares vivas, fondos arenosos y rompiente suave.
        * **Lubina / Robalo:** Maximiza rompientes fuertes (1.2-1.8m) con espuma y caídas barométricas.
        * **Sargo:** Maximiza roquedos batidos y periodos de ola largos.
        * **Calamar / Sepia:** Maximiza aguas transparentes, calma de viento (<8 km/h) y noches de pleamar.
        * **Dentón / Serviola:** Maximiza cantiles profundos (>15m) y corrientes de fondo.
        * **Corvina:** Maximiza estuarios y grandes coeficientes de marea en el Atlántico.
        """)

if __name__ == "__main__":
    main()
