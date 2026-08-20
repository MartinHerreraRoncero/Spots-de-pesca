"""
Interactive Plotly charts for hourly time-series, pressure trends, solunar windows,
and species-specific scoring comparisons.
"""

from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Dict, Tuple
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.models.spot import HourlySpotForecast, ScoreBreakdown, Spot, SpeciesScores


def create_pressure_and_score_chart(
    forecasts: List[HourlySpotForecast],
    selected_time: Optional[datetime] = None,
    species_mode: str = "GLOBAL",
    height: int = 420
) -> go.Figure:
    """
    Creates a dual-axis chart showing Barometric Pressure evolution vs Overall Fishing Score
    and Species-Specific Score, with solunar window highlight bands.
    """
    if not forecasts:
        return go.Figure()

    def _get_spec_score(f, mode):
        sp = f.score.species_scores
        if mode == "DORADA":
            return sp.dorada_score, "Dorada / Herrera"
        elif mode == "LUBINA":
            return sp.lubina_score, "Lubina / Róbalo"
        elif mode == "SARGO":
            return sp.sargo_score, "Sargo"
        elif mode == "CALAMAR":
            return sp.calamar_score, "Calamar / Sepia"
        elif mode == "DENTON":
            return sp.denton_score, "Dentón / Serviola"
        elif mode == "CORVINA":
            return sp.corvina_score, "Corvina"
        return f.score.overall_score, "Score Global"

    records = []
    spec_label = "Score Global"
    for f in forecasts:
        val, spec_label = _get_spec_score(f, species_mode)
        records.append({
            "timestamp": f.timestamp,
            "pressure": f.weather.surface_pressure,
            "global_score": f.score.overall_score,
            "species_score": val,
            "delta_3h": f.score.pressure_delta_3h,
        })
    df = pd.DataFrame(records)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 1. Global Fishing Score (Secondary Y-axis, dashed or filled)
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["global_score"],
            name="Score Global (0-100)",
            line=dict(color="#10b981", width=2.5, dash="dot", shape="spline"),
            hovertemplate="Score Global: <b>%{y:.1f}/100</b><extra></extra>",
        ),
        secondary_y=True,
    )

    # 2. Species-Specific Score if distinct from global
    if species_mode != "GLOBAL":
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["species_score"],
                name=f"Score {spec_label}",
                line=dict(color="#f59e0b", width=3.5, shape="spline"),
                fill="tozeroy",
                fillcolor="rgba(245, 158, 11, 0.12)",
                hovertemplate=f"Score {spec_label}: <b>%{{y:.1f}}/100</b><extra></extra>",
            ),
            secondary_y=True,
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["global_score"],
                name="Score Global",
                line=dict(color="#10b981", width=3, shape="spline"),
                fill="tozeroy",
                fillcolor="rgba(16, 185, 129, 0.15)",
                showlegend=False,
                hoverinfo="skip",
            ),
            secondary_y=True,
        )

    # 3. Barometric Pressure (Primary Y-axis, solid blue line)
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["pressure"],
            name="Presión Barométrica (hPa)",
            line=dict(color="#0284c7", width=2.5),
            mode="lines+markers",
            marker=dict(size=5, color="#0284c7"),
            hovertemplate="Presión: <b>%{y:.1f} hPa</b> (Δ3h: %{customdata:+.1f} hPa)<extra></extra>",
            customdata=df["delta_3h"],
        ),
        secondary_y=False,
    )

    # Add Solunar Major/Minor windows highlight annotations/shapes
    solunar_summary = forecasts[0].solunar_summary
    for w in solunar_summary.windows:
        is_major = (w.window_type == "MAJOR")
        fill_col = "rgba(234, 179, 8, 0.15)" if is_major else "rgba(59, 130, 246, 0.10)"
        line_col = "rgba(234, 179, 8, 0.5)" if is_major else "rgba(59, 130, 246, 0.3)"
        
        fig.add_shape(
            type="rect",
            x0=w.start_time,
            x1=w.end_time,
            y0=0,
            y1=1,
            yref="paper",
            fillcolor=fill_col,
            layer="below",
            line=dict(color=line_col, width=1, dash="dot"),
        )
        fig.add_annotation(
            x=w.start_time,
            y=1.0,
            yref="paper",
            text="⭐ Mayor" if is_major else "🌙 Menor",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=10, color="#b45309" if is_major else "#1d4ed8"),
        )

    if selected_time:
        fig.add_shape(
            type="line",
            x0=selected_time,
            x1=selected_time,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="#ef4444", width=2, dash="dash"),
        )
        fig.add_annotation(
            x=selected_time,
            y=0.05,
            yref="paper",
            text="📍 Hora seleccionada",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font=dict(size=11, color="#ef4444", family="sans-serif"),
        )

    min_p = df["pressure"].min() - 2.0
    max_p = df["pressure"].max() + 2.0

    fig.update_layout(
        title=dict(
            text=f"<b>Evolución Temporal: Presión Barométrica (hPa) vs Score ({spec_label})</b>",
            font=dict(size=14, color="#0f172a"),
        ),
        xaxis=dict(
            title="Fecha y Hora (UTC)",
            showgrid=True,
            gridcolor="#f1f5f9",
            tickformat="%d/%m %H:%M",
        ),
        yaxis=dict(
            title=dict(text="Presión (hPa)", font=dict(color="#0284c7")),
            range=[min_p, max_p],
            showgrid=True,
            gridcolor="#f1f5f9",
        ),
        yaxis2=dict(
            title=dict(text="Score de Pesca (0-100)", font=dict(color="#10b981")),
            range=[0, 105],
            showgrid=False,
        ),
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        hovermode="x unified",
    )

    return fig


def create_marine_and_wind_chart(
    forecasts: List[HourlySpotForecast],
    selected_time: Optional[datetime] = None,
    height: int = 380
) -> go.Figure:
    """Creates subplots showing Wave Height & Period and Wind Speed & Aspect."""
    if not forecasts:
        return go.Figure()

    df = pd.DataFrame([
        {
            "timestamp": f.timestamp,
            "wave_height": f.marine.wave_height,
            "wave_period": f.marine.wave_period,
            "current_knots": f.marine.current_velocity_knots,
            "current_dir": f.marine.current_direction,
            "wind_speed": f.weather.wind_speed_10m,
            "wind_dir": f.weather.wind_direction_10m,
            "wind_aspect": f.score.wind_aspect.wind_type,
        }
        for f in forecasts
    ])

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=(
            "<b>🌊 Estado del Mar: Altura de Ola (m) y Corriente Marina (Nudos)</b>",
            "<b>💨 Viento Costero: Velocidad (km/h) e Incidencia</b>"
        ),
    )

    # 1. Wave Height
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["wave_height"],
            name="Altura de Ola (m)",
            line=dict(color="#0284c7", width=2.5),
            hovertemplate="Ola: <b>%{y:.2f} m</b><extra></extra>",
        ),
        row=1, col=1,
    )

    # Ocean Current (Knots)
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["current_knots"],
            name="Corriente (Nudos)",
            line=dict(color="#059669", width=2.2, dash="dash"),
            hovertemplate="Corriente: <b>%{y:.2f} kts</b> (%{customdata:.0f}°)<extra></extra>",
            customdata=df["current_dir"],
        ),
        row=1, col=1,
    )

    # Wave Period
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["wave_period"],
            name="Periodo (s)",
            line=dict(color="#6366f1", width=1.5, dash="dot"),
            hovertemplate="Periodo: <b>%{y:.1f} s</b><extra></extra>",
        ),
        row=1, col=1,
    )

    # 2. Wind Speed
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["wind_speed"],
            name="Viento (km/h)",
            line=dict(color="#f59e0b", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(245, 158, 11, 0.12)",
            hovertemplate="Viento: <b>%{y:.1f} km/h</b> (%{customdata})<extra></extra>",
            customdata=df["wind_aspect"],
        ),
        row=2, col=1,
    )

    fig.add_hrect(
        y0=0.4, y1=1.2,
        fillcolor="rgba(16, 185, 129, 0.10)",
        line_width=0,
        row=1, col=1,
        annotation_text="Zona Óptima de Rompiente (0.4 - 1.2m)",
        annotation_position="top left",
        annotation_font=dict(size=9, color="#059669"),
    )

    if selected_time:
        for r in [1, 2]:
            fig.add_shape(
                type="line",
                x0=selected_time,
                x1=selected_time,
                y0=0,
                y1=1,
                yref=f"y{r} domain" if r > 1 else "y domain",
                line=dict(color="#ef4444", width=1.5, dash="dash"),
                row=r, col=1,
            )

    fig.update_layout(
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="right", x=1),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#f1f5f9", tickformat="%d/%m %H:%M")
    fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9")

    return fig


def create_species_comparison_chart(species_scores: SpeciesScores, height: int = 340) -> go.Figure:
    """Creates a horizontal bar chart comparing conditions for all 6 target species."""
    species_labels = [
        "Dorada / Herrera (Surfcasting)",
        "Lubina / Róbalo (Spinning)",
        "Sargo (Rockfishing)",
        "Calamar / Sepia (Eging)",
        "Dentón / Serviola (Jigging)",
        "Corvina (Corrientes Cádiz)",
    ]

    scores = [
        species_scores.dorada_score,
        species_scores.lubina_score,
        species_scores.sargo_score,
        species_scores.calamar_score,
        species_scores.denton_score,
        species_scores.corvina_score,
    ]

    colors = [
        "#10b981" if s >= 75 else "#84cc16" if s >= 60 else "#f59e0b" if s >= 45 else "#ef4444"
        for s in scores
    ]

    fig = go.Figure(go.Bar(
        x=scores,
        y=species_labels,
        orientation="h",
        marker=dict(color=colors),
        text=[f"<b>{s:.0f}</b>/100" for s in scores],
        textposition="outside",
        hovertemplate="Especie: <b>%{y}</b><br>Score Específico: <b>%{x:.1f}/100</b><extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text="<b>🎯 Puntuación por Especie y Modalidad de Pesca</b>",
            font=dict(size=13, color="#0f172a"),
        ),
        xaxis=dict(
            title="Score Específico (0-100)",
            range=[0, 115],
            showgrid=True,
            gridcolor="#f1f5f9",
        ),
        yaxis=dict(autorange="reversed", tickfont=dict(size=11, color="#334155")),
        height=height,
        margin=dict(l=20, r=30, t=40, b=40),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )

    return fig


def create_score_radar_chart(breakdown: ScoreBreakdown, height: int = 340) -> go.Figure:
    """Creates a radar chart illustrating the 5 heuristic scoring dimensions."""
    categories = [
        "Dinámica Presión (ΔP)",
        "Ventana Solunar",
        "Estado del Mar (Ola)",
        "Viento Costero",
        "Fuerza Marea (Coef)",
    ]

    values = [
        breakdown.pressure_score,
        breakdown.solunar_score,
        breakdown.marine_score,
        breakdown.wind_score,
        breakdown.moon_phase_score,
    ]

    cat_closed = categories + [categories[0]]
    val_closed = values + [values[0]]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=val_closed,
        theta=cat_closed,
        fill="toself",
        fillcolor="rgba(16, 185, 129, 0.25)",
        line=dict(color="#10b981", width=2.5),
        name="Score Componentes",
        hovertemplate="%{theta}: <b>%{r:.1f}/100</b><extra></extra>",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=9, color="#64748b"),
                gridcolor="#e2e8f0",
            ),
            angularaxis=dict(
                tickfont=dict(size=10, color="#1e293b", family="sans-serif"),
                gridcolor="#e2e8f0",
            ),
        ),
        title=dict(
            text=f"<b>Desglose Heurístico ({breakdown.overall_score:.0f}/100 - {breakdown.rating_tier})</b>",
            font=dict(size=13, color="#0f172a"),
            x=0.5,
            xanchor="center",
        ),
        height=height,
        margin=dict(l=30, r=30, t=40, b=30),
        paper_bgcolor="#ffffff",
        showlegend=False,
    )

    return fig


def create_top_spots_bar_chart(
    snapshot: List[Tuple[Spot, HourlySpotForecast]],
    score_mode: str = "GLOBAL",
    top_n: int = 8,
    height: int = 340
) -> go.Figure:
    """Creates a horizontal ranking bar chart of top spots."""
    def _get_val(fc):
        sp = fc.score.species_scores
        if score_mode == "DORADA":
            return sp.dorada_score
        elif score_mode == "LUBINA":
            return sp.lubina_score
        elif score_mode == "SARGO":
            return sp.sargo_score
        elif score_mode == "CALAMAR":
            return sp.calamar_score
        elif score_mode == "DENTON":
            return sp.denton_score
        elif score_mode == "CORVINA":
            return sp.corvina_score
        return fc.score.overall_score

    # Sort by the active mode score
    sorted_snapshot = sorted(snapshot, key=lambda item: _get_val(item[1]), reverse=True)
    top_items = sorted_snapshot[:top_n]

    names = [f"{s.name.split('-')[0].strip()} ({s.municipality or s.province})" for s, _ in reversed(top_items)]
    scores = [_get_val(f) for _, f in reversed(top_items)]
    colors = [
        "#10b981" if sc >= 75 else "#84cc16" if sc >= 60 else "#f59e0b" if sc >= 45 else "#ef4444"
        for sc in scores
    ]

    fig = go.Figure(go.Bar(
        x=scores,
        y=names,
        orientation="h",
        marker=dict(color=colors),
        text=[f"<b>{sc:.0f}</b>/100" for sc in scores],
        textposition="outside",
        hovertemplate="Spot: <b>%{y}</b><br>Score: <b>%{x:.1f}/100</b><extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"<b>🏆 Top {min(top_n, len(snapshot))} Spots para: {score_mode}</b>",
            font=dict(size=13, color="#0f172a"),
        ),
        xaxis=dict(
            title="Score (0-100)",
            range=[0, 115],
            showgrid=True,
            gridcolor="#f1f5f9",
        ),
        yaxis=dict(autorange=True, tickfont=dict(size=11, color="#334155")),
        height=height,
        margin=dict(l=20, r=30, t=40, b=40),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )

    return fig
