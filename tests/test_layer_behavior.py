import folium
import os
from src.visualization.map_view import create_andalucia_fishing_map
from src.fetchers.open_meteo import load_spots_from_json, get_spot_hourly_forecast

def test_map_base_layers_and_layer_control():
    spots = load_spots_from_json()
    test_spot = spots[0]
    fc = get_spot_hourly_forecast(test_spot, forecast_days=1)[0]

    m = create_andalucia_fishing_map(
        spots_data=[(test_spot, fc)],
        selected_spot_id=test_spot.id,
        subzone_filter="Costa de Huelva",
        show_pozas=False,
    )

    html = m.get_root().render()

    # 1. Check all base layers are registered in base_layers (Esri Topo removed)
    assert "base_layers" in html
    assert "World Imagery" in html
    assert "Esri Topogr" not in html
    assert "OpenStreetMap" in html
    assert "PNOA" in html

    # 2. Check that only 1 base tile layer is added to map on initial render (.addTo(map_...))
    # Esri Satellite should be the only one active initially
    added_tile_layers = [
        line for line in html.splitlines()
        if (".addTo(map_" in line or ".addTo(" in line) and "tile_layer_" in line
    ]
    assert len(added_tile_layers) == 1, f"Expected exactly 1 tile layer added on init, got {len(added_tile_layers)}"

    # 3. Check that PNOA is in base_layers, NOT overlays
    base_idx = html.find("base_layers")
    overlay_idx = html.find("overlays")
    assert base_idx != -1 and overlay_idx != -1
    base_snippet = html[base_idx:overlay_idx]
    assert "PNOA" in base_snippet

    # 4. Check that spots are grouped in single 'Spots de Pesca' group and no score color legend groups exist
    assert "Spots de Pesca" in html
    assert "Spots Excelentes" not in html
    assert "Spots Favorables" not in html
    assert "Spots Desfavorables" not in html

    # 5. Check high-definition OpenStreetMap coastline vector
    from src.analytics.coastline import get_huelva_shoreline_folium_coords
    osm_coords = get_huelva_shoreline_folium_coords()
    assert len(osm_coords) >= 900, f"Expected >= 900 OSM coastline points, got {len(osm_coords)}"

    # 6. Check interactive Leaflet MeasureControl and GPS LocateControl are attached to map
    assert "measure" in html.lower(), "Expected MeasureControl in map HTML"
    assert "locate" in html.lower(), "Expected LocateControl in map HTML"

def test_app_and_methodology_file():
    # 1. METODOLOGIA_Y_FUNDAMENTOS.md exists and is populated
    md_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "METODOLOGIA_Y_FUNDAMENTOS.md")
    assert os.path.exists(md_path), f"File {md_path} does not exist"
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Fundamentos Científicos del Motor Predictivo" in content
    assert "Dinámica Barométrica" in content
    assert "Mareas Astronómicas" in content
    assert "Batimetría Satelital SDB Stumpf" in content
    assert "Brecha de Rompiente" in content
    assert "Contraste Multitemporal" in content

    # 2. app.py doesn't contain the ranking tab or methodology tab
    app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
    with open(app_path, "r", encoding="utf-8") as f:
        app_code = f.read()
    assert "tab_ranking" not in app_code
    assert "tab_guide" not in app_code
    assert "Ranking y Comparador de la Zona" not in app_code
    assert "Metodología y Fundamentos Científicos" not in app_code

    # 3. app.py doesn't contain the 4-column color badges under the map
    assert "badge-excellent'>🟢 Excelente" not in app_code
    assert "badge-bad'>🔴 Desfavorable" not in app_code

if __name__ == "__main__":
    test_map_base_layers_and_layer_control()
    test_app_and_methodology_file()
    print("ALL VERIFICATIONS PASSED!")
