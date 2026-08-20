"""
Interactive Folium map visualization for Andalusian fishing spots, custom clicked points,
and Puertos del Estado oceanographic buoy stations with dynamic multi-species coloring and auto-zoom.
"""

from __future__ import annotations
from typing import List, Tuple, Optional, Dict
import folium
from folium import plugins

from src.models.spot import Spot, HourlySpotForecast, MarineBuoy, BuoyObservation


ZONE_VIEWPORTS: Dict[str, Tuple[float, float, int]] = {
    "Toda Andalucía": (36.75, -4.50, 8),
    "Costa de Huelva": (37.14, -6.98, 10),
    "Bahía y Costa de Cádiz": (36.48, -6.22, 10),
    "Estrecho de Gibraltar": (36.08, -5.50, 11),
    "Costa del Sol Occidental": (36.48, -4.88, 10),
    "Costa del Sol Oriental / Axarquía": (36.72, -4.15, 11),
    "Costa Tropical de Granada": (36.72, -3.55, 11),
    "Costa de Almería / Poniente": (36.72, -2.75, 11),
    "Cabo de Gata y Levante Almeriense": (36.80, -2.15, 10),
}


def get_score_color(score: float) -> str:
    """Returns hexadecimal color code matching score tiers."""
    if score >= 75.0:
        return "#10b981"  # Emerald Green (Excelente)
    elif score >= 60.0:
        return "#84cc16"  # Lime Green (Muy Bueno)
    elif score >= 45.0:
        return "#f59e0b"  # Amber Orange (Favorable)
    else:
        return "#ef4444"  # Red (Desfavorable)


def get_spot_type_icon(spot_type: str) -> str:
    """Returns an appropriate emoji icon for the scenario."""
    mapping = {
        "Playa / Arenal": "🏖️",
        "Espigón / Estructura": "🏗️",
        "Ría / Estuario": "🌊",
        "Roquedo / Acantilado": "🪨",
        "Cala Mixta": "🏝️",
        "Desembocadura": "🏞️",
        "Punto Personalizado": "📍",
    }
    return mapping.get(spot_type, "📍")


def calculate_optimal_viewport(
    spots_data: List[Tuple[Spot, HourlySpotForecast]],
    subzone_filter: str = "Toda Andalucía"
) -> Tuple[float, float, int]:
    """Calculates center (lat, lon) and zoom level dynamically."""
    if subzone_filter in ZONE_VIEWPORTS:
        return ZONE_VIEWPORTS[subzone_filter]

    if not spots_data:
        return (36.75, -4.50, 8)

    lats = [s.latitude for s, _ in spots_data]
    lons = [s.longitude for s, _ in spots_data]

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    lat_span = max(lats) - min(lats)
    lon_span = max(lons) - min(lons)
    max_span = max(lat_span, lon_span)

    if max_span < 0.15:
        zoom = 12
    elif max_span < 0.4:
        zoom = 11
    elif max_span < 0.8:
        zoom = 10
    elif max_span < 1.8:
        zoom = 9
    else:
        zoom = 8

    return (center_lat, center_lon, zoom)


def get_display_score_for_mode(sc_breakdown, score_mode: str = "GLOBAL") -> Tuple[float, str]:
    """Extracts numeric score and label according to active species mode."""
    sp = sc_breakdown.species_scores
    if score_mode == "DORADA":
        return sp.dorada_score, "Dorada / Herrera"
    elif score_mode == "LUBINA":
        return sp.lubina_score, "Lubina / Róbalo"
    elif score_mode == "SARGO":
        return sp.sargo_score, "Sargo"
    elif score_mode == "CALAMAR":
        return sp.calamar_score, "Calamar / Sepia"
    elif score_mode == "DENTON":
        return sp.denton_score, "Dentón / Serviola"
    elif score_mode == "CORVINA":
        return sp.corvina_score, "Corvina"
    else:
        return sc_breakdown.overall_score, "Score Global"


def render_spot_popup_html(spot: Spot, forecast: HourlySpotForecast, score_mode: str = "GLOBAL") -> str:
    """Creates a beautifully styled HTML popup card for a spot marker."""
    sc = forecast.score
    m = forecast.marine
    w = forecast.weather
    sol = forecast.solunar_summary
    tide = sc.tide_state
    wind_asp = sc.wind_aspect

    spot_icon = get_spot_type_icon(spot.spot_type)
    active_val, active_label = get_display_score_for_mode(sc, score_mode)
    active_color = get_score_color(active_val)

    species_badges = "".join(
        f"<span style='background-color:#e0f2fe; color:#0369a1; padding:2px 7px; border-radius:10px; font-size:11px; margin-right:4px; display:inline-block; margin-bottom:3px;'>🐟 {s}</span>"
        for s in spot.target_species[:4]
    )

    tech_badges = "".join(
        f"<span style='background-color:#f1f5f9; color:#334155; padding:2px 7px; border-radius:10px; font-size:11px; margin-right:4px; display:inline-block; margin-bottom:3px;'>🎣 {t}</span>"
        for t in spot.recommended_techniques[:3]
    )

    window_badge = ""
    if sc.solunar_window_active:
        window_badge = f"""
        <div style='background-color:#fef3c7; color:#92400e; padding:4px 8px; border-radius:6px; font-size:11px; margin-top:6px; font-weight:600;'>
            ⭐ {sc.solunar_window_active}
        </div>
        """

    buoy_calib_html = ""
    if sc.buoy_calibration_applied:
        buoy_calib_html = f"""
        <div style='background-color:#eff6ff; color:#1e40af; padding:3px 6px; border-radius:4px; font-size:10px; margin-top:4px;'>
            📡 Calibrado in-situ con {sc.calibrating_buoy_name}
        </div>
        """

    tips_html = "".join(
        f"<li style='margin-bottom:3px; font-size:11px; color:#475569;'>{tip}</li>"
        for tip in sc.tactical_tips[:2]
    )

    html = f"""
    <div style='font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; width: 300px; padding: 2px;'>
        <div style='border-bottom: 2px solid {active_color}; padding-bottom: 6px; margin-bottom: 8px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; font-weight: 700;'>
                    {spot.municipality or spot.province} • {spot.subzone}
                </span>
                <span style='background-color: {active_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 700;'>
                    {active_label}: {active_val:.0f}/100
                </span>
            </div>
            <h4 style='margin: 4px 0 0 0; color: #0f172a; font-size: 14px; font-weight: 700; line-height: 1.2;'>
                {spot_icon} {spot.name}
            </h4>
        </div>

        <div style='display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px;'>
            <span style='background: #f1f5f9; color: #334155; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;'>
                Escenario: {spot.spot_type}
            </span>
            <span style='background: #f1f5f9; color: #334155; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;'>
                Fondo: {spot.bottom_type}
            </span>
            <span style='background: #f1f5f9; color: #334155; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;'>
                Marea: Coef. {tide.coefficient}
            </span>
        </div>

        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px; font-size: 11px;'>
            <div style='background: #f8fafc; padding: 6px; border-radius: 6px;'>
                <span style='color: #64748b; display: block; font-size: 10px;'>🌊 OLEAJE</span>
                <b style='color: #0f172a; font-size: 13px;'>{m.wave_height}m</b> ({m.wave_period}s)
            </div>
            <div style='background: #f8fafc; padding: 6px; border-radius: 6px;'>
                <span style='color: #64748b; display: block; font-size: 10px;'>💨 VIENTO ({wind_asp.wind_type.split()[0]})</span>
                <b style='color: #0f172a; font-size: 13px;'>{w.wind_speed_10m} km/h</b>
            </div>
            <div style='background: #f8fafc; padding: 6px; border-radius: 6px;'>
                <span style='color: #64748b; display: block; font-size: 10px;'>🧭 CORRIENTE MARINA</span>
                <b style='color: #0f172a; font-size: 13px;'>{m.current_velocity_knots} kts</b> ({m.current_direction:.0f}°)
            </div>
            <div style='background: #f8fafc; padding: 6px; border-radius: 6px;'>
                <span style='color: #64748b; display: block; font-size: 10px;'>🌊 ESTADO MAREA</span>
                <b style='color: #0f172a; font-size: 11px;'>{tide.state_name.split('(')[0]}</b>
            </div>
        </div>

        {window_badge}
        {buoy_calib_html}

        <div style='margin-top: 8px;'>
            <div style='font-size: 10px; font-weight: 700; color: #475569; margin-bottom: 3px;'>ESPECIES CLAVE:</div>
            {species_badges}
        </div>

        <div style='margin-top: 6px;'>
            <div style='font-size: 10px; font-weight: 700; color: #475569; margin-bottom: 3px;'>TÉCNICAS:</div>
            {tech_badges}
        </div>

        {f"<div style='margin-top: 8px; border-top: 1px dashed #e2e8f0; padding-top: 6px;'><ul style='margin:0; padding-left:14px;'>{tips_html}</ul></div>" if tips_html else ""}
    </div>
    """
    return html


def render_buoy_popup_html(buoy: MarineBuoy, obs: BuoyObservation) -> str:
    """Creates an HTML popup card for an oceanographic buoy station."""
    sensors_html = "".join(
        f"<span style='background:#f1f5f9; color:#0f172a; padding:2px 6px; border-radius:4px; font-size:10px; margin-right:3px; display:inline-block; margin-bottom:3px;'>📡 {s}</span>"
        for s in buoy.sensors
    )

    html = f"""
    <div style='font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; width: 280px; padding: 2px;'>
        <div style='border-bottom: 2px solid #0284c7; padding-bottom: 6px; margin-bottom: 8px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 10px; text-transform: uppercase; color: #0284c7; font-weight: 700;'>
                    {buoy.network} • Código {buoy.code}
                </span>
                <span style='background-color: #0284c7; color: white; padding: 2px 7px; border-radius: 10px; font-size: 11px; font-weight: 700;'>
                    {obs.status.split()[0]}
                </span>
            </div>
            <h4 style='margin: 4px 0 0 0; color: #0f172a; font-size: 14px; font-weight: 700;'>
                ⚓ {buoy.name}
            </h4>
            <span style='font-size:11px; color:#64748b;'>Operador: {buoy.operator}</span>
        </div>

        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px; font-size: 11px;'>
            <div style='background: #eff6ff; padding: 6px; border-radius: 6px;'>
                <span style='color: #1e40af; display: block; font-size: 10px; font-weight:700;'>🌊 OLA REAL (Hs)</span>
                <b style='color: #1e3a8a; font-size: 14px;'>{obs.wave_height_hs} m</b>
            </div>
            <div style='background: #eff6ff; padding: 6px; border-radius: 6px;'>
                <span style='color: #1e40af; display: block; font-size: 10px; font-weight:700;'>⏱️ PERIODO PICO (Tp)</span>
                <b style='color: #1e3a8a; font-size: 14px;'>{obs.wave_period_tp} s</b>
            </div>
            <div style='background: #eff6ff; padding: 6px; border-radius: 6px;'>
                <span style='color: #1e40af; display: block; font-size: 10px; font-weight:700;'>🌡️ AGUA DEL MAR</span>
                <b style='color: #1e3a8a; font-size: 14px;'>{obs.sea_surface_temperature} °C</b>
            </div>
            <div style='background: #eff6ff; padding: 6px; border-radius: 6px;'>
                <span style='color: #1e40af; display: block; font-size: 10px; font-weight:700;'>🧭 PROFUNDIDAD</span>
                <b style='color: #1e3a8a; font-size: 14px;'>{buoy.depth_m:.0f} m</b>
            </div>
        </div>

        <div style='margin-top: 6px; font-size: 11px; color: #475569;'>
            <b>Sensores In-Situ:</b><br>
            {sensors_html}
        </div>
        <div style='margin-top: 6px; font-size: 11px; color: #64748b; line-height:1.3;'>
            {buoy.description}
        </div>
    </div>
    """
    return html


def create_andalucia_fishing_map(
    spots_data: List[Tuple[Spot, HourlySpotForecast]],
    selected_spot_id: Optional[str] = None,
    subzone_filter: str = "Toda Andalucía",
    custom_spot_data: Optional[Tuple[Spot, HourlySpotForecast]] = None,
    buoys_data: Optional[List[Tuple[MarineBuoy, BuoyObservation]]] = None,
    score_mode: str = "GLOBAL",
) -> folium.Map:
    """
    Generates Folium map of Andalusia with multi-species score coloring,
    custom clicked GPS points, and oceanographic buoys layer.
    """
    center_lat, center_lon, zoom = calculate_optimal_viewport(spots_data, subzone_filter)

    if custom_spot_data and not selected_spot_id:
        center_lat = custom_spot_data[0].latitude
        center_lon = custom_spot_data[0].longitude
        zoom = 11

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,
    )

    # Base tile layers
    folium.TileLayer(
        tiles="CartoDB positron",
        name="🗺️ CartoDB Claro (Recomendado)",
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="🌍 OpenStreetMap",
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="🛰️ Satélite Esri (Máximo Detalle)",
        control=True,
    ).add_to(m)

    # Feature groups
    fg_excelente = folium.FeatureGroup(name="🟢 Spots Excelentes (> 75)", show=True)
    fg_muy_bueno = folium.FeatureGroup(name="🟡 Spots Favorables (50 - 74)", show=True)
    fg_desfavorable = folium.FeatureGroup(name="🔴 Spots Desfavorables (< 50)", show=True)
    fg_buoys = folium.FeatureGroup(name="⚓ Boyas Oceanográficas (Puertos del Estado)", show=True)

    # Add standard spots
    for spot, forecast in spots_data:
        disp_score, _ = get_display_score_for_mode(forecast.score, score_mode)
        color = get_score_color(disp_score)
        is_selected = (spot.id == selected_spot_id)

        border_style = "3px solid #facc15" if is_selected else f"2px solid {color}"
        shadow_style = "0 0 14px rgba(250, 204, 21, 0.95)" if is_selected else "0 2px 5px rgba(0,0,0,0.3)"
        size = 38 if is_selected else 30
        font_size = 13 if is_selected else 10

        icon_html = f"""
        <div style='
            background-color: {color};
            color: white;
            width: {size}px;
            height: {size}px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-weight: 800;
            font-size: {font_size}px;
            border: {border_style};
            box-shadow: {shadow_style};
            cursor: pointer;
            transition: transform 0.2s;
        '>
            {disp_score:.0f}
        </div>
        """

        marker_icon = folium.DivIcon(
            icon_size=(size, size),
            icon_anchor=(size // 2, size // 2),
            html=icon_html,
        )

        popup_content = render_spot_popup_html(spot, forecast, score_mode=score_mode)
        popup = folium.Popup(popup_content, max_width=340)
        tooltip_text = f"<b>{spot.name}</b> ({spot.spot_type})<br>Score: <b>{disp_score:.0f}/100</b><br>Ola: {forecast.marine.wave_height}m | Marea: Coef. {forecast.score.tide_state.coefficient}"

        marker = folium.Marker(
            location=[spot.latitude, spot.longitude],
            icon=marker_icon,
            popup=popup,
            tooltip=tooltip_text,
        )

        if is_selected:
            folium.CircleMarker(
                location=[spot.latitude, spot.longitude],
                radius=25,
                color="#facc15",
                weight=3,
                fill=True,
                fill_color="#fef08a",
                fill_opacity=0.3,
            ).add_to(m)

        if disp_score >= 75.0:
            marker.add_to(fg_excelente)
        elif disp_score >= 50.0:
            marker.add_to(fg_muy_bueno)
        else:
            marker.add_to(fg_desfavorable)

    # Render Custom Clicked Spot if present
    if custom_spot_data:
        c_spot, c_fc = custom_spot_data
        c_score, _ = get_display_score_for_mode(c_fc.score, score_mode)

        custom_icon_html = f"""
        <div style='
            background-color: #0284c7;
            color: white;
            width: 42px;
            height: 42px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-weight: 900;
            font-size: 14px;
            border: 3px solid #facc15;
            box-shadow: 0 0 16px rgba(2, 132, 199, 0.9);
            cursor: pointer;
        '>
            🎯
        </div>
        """
        c_marker = folium.Marker(
            location=[c_spot.latitude, c_spot.longitude],
            icon=folium.DivIcon(icon_size=(42, 42), icon_anchor=(21, 21), html=custom_icon_html),
            popup=folium.Popup(render_spot_popup_html(c_spot, c_fc, score_mode=score_mode), max_width=340),
            tooltip=f"<b>📍 Punto Clicado / Personalizado</b><br>Score: <b>{c_score:.0f}/100</b>",
        )
        folium.CircleMarker(
            location=[c_spot.latitude, c_spot.longitude],
            radius=30,
            color="#0284c7",
            weight=3,
            fill=True,
            fill_color="#bae6fd",
            fill_opacity=0.4,
        ).add_to(m)
        c_marker.add_to(m)

    # Render Marine Buoys Layer
    if buoys_data:
        for buoy, obs in buoys_data:
            buoy_icon_html = f"""
            <div style='
                background: linear-gradient(135deg, #0284c7 0%, #1e40af 100%);
                color: white;
                width: 32px;
                height: 32px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
                border: 2px solid white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.4);
                cursor: pointer;
            '>
                ⚓
            </div>
            """
            buoy_marker = folium.Marker(
                location=[buoy.latitude, buoy.longitude],
                icon=folium.DivIcon(icon_size=(32, 32), icon_anchor=(16, 16), html=buoy_icon_html),
                popup=folium.Popup(render_buoy_popup_html(buoy, obs), max_width=320),
                tooltip=f"<b>⚓ {buoy.name}</b><br>Ola Real: <b>{obs.wave_height_hs}m</b> ({obs.wave_period_tp}s)<br>Agua: {obs.sea_surface_temperature}°C",
            )
            buoy_marker.add_to(fg_buoys)

    fg_excelente.add_to(m)
    fg_muy_bueno.add_to(m)
    fg_desfavorable.add_to(m)
    fg_buoys.add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    return m
