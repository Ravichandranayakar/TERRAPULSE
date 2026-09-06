import React, { useState, useCallback, useRef } from "react";
import Map, { Source, Layer, MapRef, NavigationControl } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { MapPin, Navigation, Layers, Globe } from "lucide-react";

interface GeoCell {
  location_id: string;
  name: string;
  centroid_lat: number;
  centroid_lon: number;
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
  slope_angle: number;
  near_nh10: boolean;
  historical_count: number;
  risk_level?: string;
  risk_score?: number;
  contributing_factors?: any[];
  elevation_m?: number;
  soil_type?: string;
}

const MAPTILER_KEY = (import.meta as any).env?.VITE_MAPTILER_KEY || "get_your_own_key";
const MAP_STYLE_2D: any = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap Contributors"
    }
  },
  layers: [
    {
      id: "osm",
      type: "raster",
      source: "osm",
      minzoom: 0,
      maxzoom: 19
    }
  ]
};
const MAP_STYLE_3D = `https://api.maptiler.com/maps/hybrid/style.json?key=${MAPTILER_KEY}`;

function Compass({ bearing }: { bearing: number }) {
  return (
    <div className="absolute bottom-24 right-4 z-10 pointer-events-none select-none">
      <svg width="52" height="52" viewBox="0 0 52 52">
        <circle cx="26" cy="26" r="24" fill="rgba(0,0,0,0.60)" stroke="#6ee7b7" strokeWidth="1.2" />
        <text x="26" y="11" textAnchor="middle" fill="#6ee7b7" fontSize="9" fontWeight="bold" fontFamily="monospace">N</text>
        <text x="26" y="48" textAnchor="middle" fill="#94a3b8" fontSize="7" fontFamily="monospace">S</text>
        <text x="8"  y="29" textAnchor="middle" fill="#94a3b8" fontSize="7" fontFamily="monospace">W</text>
        <text x="44" y="29" textAnchor="middle" fill="#94a3b8" fontSize="7" fontFamily="monospace">E</text>
        <g transform={`rotate(${-bearing}, 26, 26)`}>
          <polygon points="26,9 23,26 29,26"  fill="#ef4444" />
          <polygon points="26,43 23,26 29,26" fill="#e2e8f0" opacity="0.7" />
          <circle cx="26" cy="26" r="2.8" fill="#ffffff" />
        </g>
      </svg>
    </div>
  );
}

export default function GeospatialViewer({
  cells = [],
  historicalEvents = [],
  nh10Route = [],
  routeSafety,
  onCellClick,
  initialSelectedCellId,
}: {
  cells?: GeoCell[];
  historicalEvents?: any[];
  nh10Route?: any[];
  onCellClick?: (cell: GeoCell | null) => void;
  initialSelectedCellId?: string | null;
  routeSafety?: string;
}) {
  const mapRef = useRef<MapRef>(null);
  const isNepal = cells && cells.length > 0 && cells[0].centroid_lon < 86;
  const defaultCenter = isNepal
    ? { lon: 85.3, lat: 28.1, zoom: 9 }
    : { lon: 88.5122, lat: 27.3314, zoom: 11 };

  const [viewState, setViewState] = useState({
    longitude: defaultCenter.lon,
    latitude: defaultCenter.lat,
    zoom: defaultCenter.zoom,
    pitch: 0,
    bearing: 0,
  });

  React.useEffect(() => {
    setViewState(prev => ({ ...prev, longitude: defaultCenter.lon, latitude: defaultCenter.lat, zoom: defaultCenter.zoom, pitch: 0, bearing: 0 }));
    setIs3D(false);
    setSelectedCell(null);
    setSaved2DState(null);
  }, [isNepal]);

  const [selectedCell, setSelectedCell] = useState<GeoCell | null>(null);
  const [is3D, setIs3D] = useState(false);
  const [saved2DState, setSaved2DState] = useState<any>(null);
  const resolvedRoute = nh10Route && nh10Route.length > 0 ? nh10Route : [];

  const riskGeoJSON = React.useMemo(() => ({
    type: "FeatureCollection",
    features: cells.map(cell => {
      let color = "#22c55e"; let opacity = 0.3;
      if (cell.risk_level === "moderate" || cell.risk_level === "MODERATE") { color = "#eab308"; opacity = 0.4; }
      if (cell.risk_level === "high"     || cell.risk_level === "HIGH")     { color = "#f97316"; opacity = 0.55; }
      if (cell.risk_level === "critical" || cell.risk_level === "CRITICAL") { color = "#ef4444"; opacity = 0.75; }
      return { type: "Feature", properties: { ...cell, color, opacity }, geometry: { type: "Polygon", coordinates: [[[cell.lon_min, cell.lat_min],[cell.lon_max, cell.lat_min],[cell.lon_max, cell.lat_max],[cell.lon_min, cell.lat_max],[cell.lon_min, cell.lat_min]]] } };
    }),
  }), [cells]);

  const riskCentroidsGeoJSON = React.useMemo(() => ({
    type: "FeatureCollection",
    features: cells.map(cell => {
      let color = "#22c55e";
      if (cell.risk_level === "moderate" || cell.risk_level === "MODERATE") color = "#eab308";
      if (cell.risk_level === "high"     || cell.risk_level === "HIGH")     color = "#f97316";
      if (cell.risk_level === "critical" || cell.risk_level === "CRITICAL") color = "#ef4444";
      return { type: "Feature", properties: { ...cell, color, shortName: cell.name.split(" ").slice(-1)[0] }, geometry: { type: "Point", coordinates: [cell.centroid_lon, cell.centroid_lat] } };
    }),
  }), [cells]);

  const nh10GeoJSON = React.useMemo(() => ({
    type: "Feature", properties: {},
    geometry: { type: "LineString", coordinates: nh10Route.map((c: any) => [c[1], c[0]]) },
  }), [nh10Route]);

  const historicalGeoJSON = React.useMemo(() => ({
    type: "FeatureCollection",
    features: historicalEvents.map(ev => ({ type: "Feature", properties: { ...ev }, geometry: { type: "Point", coordinates: [ev.lon, ev.lat] } })),
  }), [historicalEvents]);

  const handleExplore3D = useCallback((cell: GeoCell) => {
    if (!mapRef.current) return;
    setSaved2DState({ longitude: viewState.longitude, latitude: viewState.latitude, zoom: viewState.zoom });
    setIs3D(true);
    const rightPadding = window.innerWidth > 768 ? 380 : 40;
      mapRef.current.fitBounds(
        [[cell.lon_min, cell.lat_min], [cell.lon_max, cell.lat_max]],
        { padding: { top: 60, bottom: 60, left: 40, right: 40 }, pitch: 65, bearing: 15, duration: 2500 }
      );
  }, [viewState]);

  
  const handleResetMap = useCallback(() => {
    if (!mapRef.current) return;
    setSelectedCell(null);
    if (onCellClick) onCellClick(null);
    
    if (cells && cells.length > 0) {
      const minLon = Math.min(...cells.map(c => c.lon_min));
      const minLat = Math.min(...cells.map(c => c.lat_min));
      const maxLon = Math.max(...cells.map(c => c.lon_max));
      const maxLat = Math.max(...cells.map(c => c.lat_max));
      
      mapRef.current.fitBounds(
        [[minLon, minLat], [maxLon, maxLat]],
        { padding: 60, pitch: is3D ? 60 : 0, bearing: is3D ? 15 : 0, duration: 1500 }
      );
    } else {
      mapRef.current.flyTo({
        center: [defaultCenter.lon, defaultCenter.lat],
        zoom: defaultCenter.zoom,
        pitch: is3D ? 60 : 0,
        bearing: is3D ? 15 : 0,
        duration: 1500
      });
    }
  }, [cells, defaultCenter, is3D, onCellClick]);

  const handleReturnTo2D = useCallback(() => {
    if (!mapRef.current) return;
    setIs3D(false);
    mapRef.current.flyTo({
      center: saved2DState ? [saved2DState.longitude, saved2DState.latitude] : [defaultCenter.lon, defaultCenter.lat],
      zoom: saved2DState ? saved2DState.zoom : defaultCenter.zoom,
      pitch: 0, bearing: 0, duration: 2000,
    });
  }, [saved2DState, defaultCenter]);

  const handleMapLoad = useCallback(() => {
    if (initialSelectedCellId && !is3D) {
      const target = cells.find(c => c.location_id === initialSelectedCellId);
      if (target) { setSelectedCell(target); setTimeout(() => handleExplore3D(target), 300); }
    }
  }, [initialSelectedCellId, cells, is3D, handleExplore3D]);

  const routeColor = routeSafety === "CRITICAL" ? "#ef4444" : routeSafety === "HIGH_RISK" ? "#f97316" : routeSafety === "CAUTION" ? "#eab308" : "#3b82f6";
  const routeGeoJSON = resolvedRoute.length > 1 ? { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: resolvedRoute.map((p: any) => [p[1], p[0]]) } }] } : null;

  return (
    <div className="relative w-full h-full min-h-full bg-slate-900 rounded-xl overflow-hidden border border-border/20 shadow-2xl">
      <Map
        ref={mapRef}
        onLoad={handleMapLoad}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        mapStyle={is3D ? MAP_STYLE_3D : MAP_STYLE_2D}
        terrain={is3D ? { source: "terrain-source", exaggeration: 1.5 } : undefined}
        onClick={(e) => {
          if (e.features && e.features.length > 0) {
            const f = e.features[0];
            const clicked = cells.find(c => c.location_id === f.properties?.location_id);
            if (clicked) {
                setSelectedCell(clicked);
                if (onCellClick) onCellClick(clicked);
                if (!is3D) {
                  handleExplore3D(clicked);
                } else if (mapRef.current) {
                  const rightPadding = window.innerWidth > 768 ? 380 : 40;
                    mapRef.current.fitBounds(
                      [[clicked.lon_min, clicked.lat_min], [clicked.lon_max, clicked.lat_max]],
                      { padding: { top: 60, bottom: 60, left: 40, right: 40 }, pitch: 65, bearing: 15, duration: 1500 }
                    );
                }
              }
          }
        }}
        interactiveLayerIds={["risk-fill", "risk-circle-outer", "risk-circle-inner"]}
      >
        <Source id="terrain-source" type="raster-dem" url={`https://api.maptiler.com/tiles/terrain-rgb/tiles.json?key=${MAPTILER_KEY}`} tileSize={256} />
        <Source id="nh10-route" type="geojson" data={nh10GeoJSON as any}>
          <Layer id="nh10-line-glow" type="line" paint={{ "line-color": "#60a5fa", "line-width": 6, "line-opacity": 0.15 }} />
          <Layer id="nh10-line" type="line" paint={{ "line-color": "#3b82f6", "line-width": 2.5, "line-opacity": 0.7, "line-dasharray": [2, 2] }} />
        </Source>
        <Source id="risk-data" type="geojson" data={riskGeoJSON as any}>
          <Layer id="risk-fill" type="fill" layout={{ visibility: is3D ? "visible" : "none" }} paint={{ "fill-color": ["get", "color"], "fill-opacity": ["get", "opacity"] }} />
        </Source>
        <Source id="risk-centroids" type="geojson" data={riskCentroidsGeoJSON as any}>
          <Layer id="risk-circle-outer" type="circle" paint={{ "circle-radius": ["case", ["any", ["==", ["get", "risk_level"], "high"], ["==", ["get", "risk_level"], "critical"]], 10, 8], "circle-color": "#64748b", "circle-opacity": 0.9 }} />
          <Layer id="risk-circle-inner" type="circle" paint={{ "circle-radius": ["case", ["any", ["==", ["get", "risk_level"], "high"], ["==", ["get", "risk_level"], "critical"]], 7, 5.5], "circle-color": ["get", "color"], "circle-stroke-width": 0 }} />
          <Layer id="risk-labels" type="symbol" layout={{ "text-field": ["get", "shortName"], "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"], "text-size": 11, "text-offset": [0, 1.6], "text-anchor": "top" }} paint={{ "text-color": "#ffffff", "text-halo-color": "rgba(0,0,0,0.85)", "text-halo-width": 1.5 }} />
        </Source>
        <Source id="historical-data" type="geojson" data={historicalGeoJSON as any}>
          <Layer id="historical-points" type="circle" paint={{ "circle-radius": 4, "circle-color": "#71717a", "circle-opacity": 0.8, "circle-stroke-width": 1, "circle-stroke-color": "#a1a1aa" }} />
        </Source>
        {selectedCell && !is3D && (
          <Layer id="selected-highlight" type="line" source="risk-data" filter={["==", "location_id", selectedCell.location_id]} paint={{ "line-color": "#ffffff", "line-width": 3 }} />
        )}
        {routeGeoJSON && (
          <Source id="route-line-src" type="geojson" data={routeGeoJSON as any}>
            <Layer id="route-line-buffer" type="line" paint={{ "line-color": "#ef4444", "line-width": 45, "line-opacity": 0.15, "line-blur": 15 }} />
            <Layer id="route-line-shadow" type="line" paint={{ "line-color": "#000000", "line-width": 7, "line-opacity": 0.3, "line-blur": 3 }} />
            <Layer id="route-line" type="line" paint={{ "line-color": routeColor, "line-width": 3, "line-opacity": 0.9 }} />
          </Source>
        )}
        <NavigationControl position="top-right" showCompass={true} showZoom={true} visualizePitch={true} />
      </Map>

      <div className="absolute top-4 left-4 z-10 pointer-events-auto">
          <button 
            onClick={handleResetMap}
            title="Reset Map View"
            className="bg-black/80 hover:bg-black text-white backdrop-blur-sm border border-white/10 px-4 py-2 rounded-full text-[11px] font-bold uppercase tracking-widest shadow-lg transition-all flex items-center gap-2 group cursor-pointer"
          >
            {is3D ? (
              <span className="flex items-center text-blue-400 gap-1.5 group-hover:scale-105 transition-transform">
                <Navigation className="w-3.5 h-3.5" /> 3D Terrain Active
              </span>
            ) : (
              <span className="flex items-center text-teal-400 gap-1.5 group-hover:scale-105 transition-transform">
                <MapPin className="w-3.5 h-3.5" /> 2D Regional Overview
              </span>
            )}
          </button>
        </div>

      <div className="absolute bottom-6 left-6 z-[1001] flex gap-3 pointer-events-auto">
        {is3D ? (
          <button
            onClick={handleReturnTo2D}
            className="bg-emerald-600/90 hover:bg-emerald-500 backdrop-blur-md border border-emerald-400/60 text-white font-bold tracking-widest uppercase px-5 py-2.5 rounded-full text-[11px] flex items-center gap-2 transition-all shadow-xl shadow-emerald-900/30"
          >
            <Navigation className="w-3.5 h-3.5 rotate-180" />
            Return to 2D View
          </button>
        ) : (
          <button
            onClick={() => handleExplore3D(selectedCell || cells[0])}
            className="bg-slate-700/95 hover:bg-slate-600 backdrop-blur-md border border-slate-500/50 text-white font-bold tracking-widest uppercase px-5 py-2.5 rounded-full text-[11px] flex items-center gap-2 transition-all shadow-xl"
          >
            <Globe className="w-4 h-4" />
            Switch to 3D View
          </button>
        )}
      </div>
    </div>
  );
}
