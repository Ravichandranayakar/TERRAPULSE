import React, { useState, useCallback, useMemo, useRef } from "react";
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

type DisasterEventType = 'landslide' | 'flood' | 'debris_flow' | 'mixed';
type DisasterEventRole = 'observed_extent' | 'source' | 'runout' | 'deposit';

interface DisasterEventLayer {
  id: string;
  event_id?: string;
  eventType: DisasterEventType;
  geometry: any;
  source: string;
  observedAt?: string;
  confidence?: string;
  role: DisasterEventRole;
  area_sq_km?: number;
}

interface ExposureInfrastructure {
  highways?: { name: string; route?: number[][] }[];
  settlements?: { name: string; lat: number; lon: number; population?: number }[];
}

interface TargetGeometry {
  geometry: any;
  source: string;
  label?: string;
}

interface ReportPoint {
  id: number | string;
  lat: number;
  lon: number;
  hazardType: string;
  status?: string;
}

const EVENT_COLORS: Record<DisasterEventType, string> = {
  landslide: '#f97316',
  flood: '#38bdf8',
  debris_flow: '#a855f7',
  mixed: '#f43f5e',
};

const EVENT_ROLE_COLORS: Record<DisasterEventRole, string> = {
  observed_extent: '#38bdf8',
  source: '#ef4444',
  runout: '#f59e0b',
  deposit: '#a855f7',
};

function getEventType(value: any): DisasterEventType {
  return value === 'flood' || value === 'debris_flow' || value === 'mixed' ? value : 'landslide';
}

function collectCoordinates(value: any): number[][] {
  if (!Array.isArray(value)) return [];
  if (typeof value[0] === 'number' && typeof value[1] === 'number') return [value];
  return value.flatMap(collectCoordinates);
}

function distanceKm(left: number[], right: number[]): number {
  const radiansLat = ((left[1] - right[1]) * Math.PI) / 180;
  const radiansLon = ((left[0] - right[0]) * Math.PI) / 180;
  const lat1 = (left[1] * Math.PI) / 180;
  const lat2 = (right[1] * Math.PI) / 180;
  const a = Math.sin(radiansLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(radiansLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const MAPTILER_KEY = (import.meta as any).env?.VITE_MAPTILER_KEY || "get_your_own_key";
const MAP_STYLE_2D = `https://api.maptiler.com/maps/streets-v2/style.json?key=${MAPTILER_KEY}`;
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
  eventLayers = [],
  infrastructure = {},
  targetGeometry = null,
  highlightCellId = null,
  reportPoints = [],
  selectedReportId = null,
  nh10Route = [],
  routeSafety,
  onCellClick,
  initialSelectedCellId,
}: {
  cells?: GeoCell[];
  historicalEvents?: any[];
  eventLayers?: DisasterEventLayer[];
  infrastructure?: ExposureInfrastructure;
  targetGeometry?: TargetGeometry | null;
  highlightCellId?: string | null;
  reportPoints?: ReportPoint[];
  selectedReportId?: string | number | null;
  nh10Route?: any[];
  onCellClick?: (cell: GeoCell | null) => void;
  initialSelectedCellId?: string | null;
  routeSafety?: string;
}) {
  const mapRef = useRef<MapRef>(null);
  const isNepal = cells && cells.length > 0 && cells[0].centroid_lon < 86;

  // Compute the correct center based on actual loaded cells (not a stale empty-array check)
  const defaultCenter = useMemo(() => {
    if (cells && cells.length > 0) {
      const lats = cells.map(c => c.centroid_lat);
      const lons = cells.map(c => c.centroid_lon);
      const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
      const centerLon = (Math.min(...lons) + Math.max(...lons)) / 2;
      const zoom = isNepal ? 9 : 10.5;
      return { lon: centerLon, lat: centerLat, zoom };
    }
    // Fallback before cells load (NER India default)
    return { lon: 88.5122, lat: 27.3314, zoom: 10.5 };
  }, [cells, isNepal]);

  const [viewState, setViewState] = useState({
    longitude: defaultCenter.lon,
    latitude: defaultCenter.lat,
    zoom: defaultCenter.zoom,
    pitch: 0,
    bearing: 0,
  });

  // Fly to correct region center whenever cells load or region switches
  React.useEffect(() => {
    if (!cells || cells.length === 0) return;
    setViewState(prev => ({
      ...prev,
      longitude: defaultCenter.lon,
      latitude: defaultCenter.lat,
      zoom: defaultCenter.zoom,
      pitch: 0,
      bearing: 0,
    }));
    setIs3D(false);
    setSelectedCell(null);
    setSaved2DState(null);
  }, [isNepal, defaultCenter.lon, defaultCenter.lat]);

  const [selectedCell, setSelectedCell] = useState<GeoCell | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [is3D, setIs3D] = useState(false);
  const [saved2DState, setSaved2DState] = useState<any>(null);
  const resolvedRoute = nh10Route && nh10Route.length > 0 ? nh10Route : [];

  const riskGeoJSON = React.useMemo(() => ({
    type: "FeatureCollection",
    features: cells.map(cell => {
      let color = "#22c55e"; let opacity = 0.14;
      if (cell.risk_level === "moderate" || cell.risk_level === "MODERATE") { color = "#eab308"; opacity = 0.20; }
      if (cell.risk_level === "high"     || cell.risk_level === "HIGH")     { color = "#f97316"; opacity = 0.26; }
      if (cell.risk_level === "critical" || cell.risk_level === "CRITICAL") { color = "#ef4444"; opacity = 0.32; }
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
      const SKIP_WORDS = new Set(['Section', 'HQ', 'Zone', 'Basin', 'Entry', 'Reach', 'Confluence', 'Crossing', 'Junction', 'Corridor', 'Ridge', 'Slope', 'Floor', 'Area', 'Upper', 'Lower', 'North', 'South', 'East', 'West']);
      const nameParts = cell.name.split(' ');
      const shortName = nameParts.find(w => !SKIP_WORDS.has(w)) || nameParts[0];
      return { type: "Feature", properties: { ...cell, color, shortName }, geometry: { type: "Point", coordinates: [cell.centroid_lon, cell.centroid_lat] } };
    }),
  }), [cells]);

  const nh10GeoJSON = React.useMemo(() => ({
    type: "Feature", properties: {},
    geometry: { type: "LineString", coordinates: nh10Route.map((c: any) => [c[1], c[0]]) },
  }), [nh10Route]);

  const historicalGeoJSON = React.useMemo(() => ({
    type: "FeatureCollection",
    features: historicalEvents.map(ev => ({ type: "Feature", properties: { ...ev, event_type: getEventType(ev.event_type), color: EVENT_COLORS[getEventType(ev.event_type)] }, geometry: { type: "Point", coordinates: [ev.lon, ev.lat] } })),
  }), [historicalEvents]);

  const eventFootprintGeoJSON = React.useMemo(() => ({
    type: "FeatureCollection",
    features: eventLayers.map(layer => ({
      type: "Feature",
      properties: {
        ...layer,
        eventType: getEventType(layer.eventType),
        color: EVENT_COLORS[getEventType(layer.eventType)],
        roleColor: EVENT_ROLE_COLORS[layer.role],
      },
      geometry: layer.geometry,
    })),
  }), [eventLayers]);

  const exposureRoadsGeoJSON = React.useMemo(() => ({
    type: "FeatureCollection",
    features: (infrastructure.highways || [])
      .filter(road => Array.isArray(road.route) && road.route.length > 1)
      .map(road => ({ type: "Feature", properties: { name: road.name }, geometry: { type: "LineString", coordinates: road.route.map((point: number[]) => [point[1], point[0]]) } })),
  }), [infrastructure]);

  const exposureSettlementsGeoJSON = React.useMemo(() => ({
    type: "FeatureCollection",
    features: (infrastructure.settlements || []).map(settlement => ({
      type: "Feature",
      properties: settlement,
      geometry: { type: "Point", coordinates: [settlement.lon, settlement.lat] },
    })),
  }), [infrastructure]);

  const targetGeometryGeoJSON = React.useMemo(() => targetGeometry ? ({
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      properties: { source: targetGeometry.source, label: targetGeometry.label || "BROADCAST TARGET" },
      geometry: targetGeometry.geometry,
    }],
  }) : null, [targetGeometry]);

  const reportPointsGeoJSON = React.useMemo(() => ({
    type: "FeatureCollection",
    features: reportPoints.map(report => ({
      type: "Feature",
      properties: {
        id: String(report.id),
        hazardType: report.hazardType,
        status: report.status || "pending_review",
        color: report.hazardType === "flood"
          ? "#38bdf8"
          : report.hazardType === "debris_flow"
            ? "#a855f7"
            : report.hazardType === "landslide"
              ? "#f97316"
              : "#94a3b8",
      },
      geometry: { type: "Point", coordinates: [report.lon, report.lat] },
    })),
  }), [reportPoints]);

  const selectedEventLayer = useMemo(
    () => eventLayers.find(layer => layer.event_id === selectedEventId || layer.id === selectedEventId),
    [eventLayers, selectedEventId]
  );
  const selectedEventRecord = useMemo(
    () => historicalEvents.find(event => event.id === selectedEventId),
    [historicalEvents, selectedEventId]
  );
  const selectedEventCoordinates = useMemo(
    () => selectedEventLayer ? collectCoordinates(selectedEventLayer.geometry) : [],
    [selectedEventLayer]
  );
  const nearbyRoads = useMemo(() => {
    if (!selectedEventCoordinates.length) return [];
    return (infrastructure.highways || []).map(road => ({
      name: road.name,
      distanceKm: Math.min(...(road.route || []).map((point: number[]) => Math.min(
        ...selectedEventCoordinates.map(coordinate => distanceKm([point[1], point[0]], coordinate))
      ))),
    })).filter(road => road.distanceKm <= 25);
  }, [infrastructure, selectedEventCoordinates]);
  const nearbySettlements = useMemo(() => {
    if (!selectedEventCoordinates.length) return [];
    return (infrastructure.settlements || []).map(settlement => ({
      name: settlement.name,
      distanceKm: Math.min(...selectedEventCoordinates.map(coordinate => distanceKm([settlement.lon, settlement.lat], coordinate))),
    })).filter(settlement => settlement.distanceKm <= 25);
  }, [infrastructure, selectedEventCoordinates]);
  const nearestRiskCell = useMemo(() => {
    if (!selectedEventRecord) return null;
    return cells.reduce((nearest, cell) => {
      const distance = distanceKm(
        [selectedEventRecord.lon, selectedEventRecord.lat],
        [cell.centroid_lon, cell.centroid_lat]
      );
      return !nearest || distance < nearest.distance ? { cell, distance } : nearest;
    }, null as { cell: GeoCell; distance: number } | null)?.cell;
  }, [cells, selectedEventRecord]);

  const handleExplore3D = useCallback((cell?: GeoCell | null) => {
    if (!mapRef.current) return;
    setSaved2DState({ longitude: viewState.longitude, latitude: viewState.latitude, zoom: viewState.zoom });
    setIs3D(true);

    if (cell) {
      mapRef.current.fitBounds(
        [[cell.lon_min, cell.lat_min], [cell.lon_max, cell.lat_max]],
        { padding: { top: 60, bottom: 60, left: 40, right: 40 }, pitch: 65, bearing: 15, duration: 2500 }
      );
    } else if (cells && cells.length > 0) {
      const minLon = Math.min(...cells.map(c => c.lon_min));
      const minLat = Math.min(...cells.map(c => c.lat_min));
      const maxLon = Math.max(...cells.map(c => c.lon_max));
      const maxLat = Math.max(...cells.map(c => c.lat_max));
      mapRef.current.fitBounds(
        [[minLon, minLat], [maxLon, maxLat]],
        { padding: { top: 60, bottom: 60, left: 40, right: 40 }, pitch: 65, bearing: 15, duration: 2500 }
      );
    }
  }, [viewState, cells]);

  
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
            const featureLayerId = (f as any).layer?.id || '';
            if (featureLayerId === 'event-footprint-fill' || featureLayerId === 'event-footprint-outline' || featureLayerId === 'historical-points') {
              const eventId = f.properties?.event_id || f.properties?.id;
              if (eventId) {
                setSelectedEventId(String(eventId));
                return;
              }
            }
            setSelectedEventId(null);
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
        interactiveLayerIds={["risk-fill", "risk-circle-outer", "risk-circle-inner", "event-footprint-fill", "event-footprint-outline", "historical-points"]}
      >
        <Source id="terrain-source" type="raster-dem" url={`https://api.maptiler.com/tiles/terrain-rgb/tiles.json?key=${MAPTILER_KEY}`} tileSize={256} />
        <Source id="maptiler-v3" type="vector" url={`https://api.maptiler.com/tiles/v3/tiles.json?key=${MAPTILER_KEY}`}>
          {is3D && (
            <>
              <Layer
                id="detailed-roads"
                source="maptiler-v3"
                source-layer="transportation"
                type="line"
                minzoom={12}
                paint={{
                  "line-color": "#ffffff",
                  "line-width": 1.2,
                  "line-opacity": 0.4
                }}
              />
              <Layer
                id="3d-buildings"
                source="maptiler-v3"
                source-layer="building"
                type="fill-extrusion"
                minzoom={14}
                paint={{
                  "fill-extrusion-color": "#e2e8f0",
                  "fill-extrusion-height": ["get", "render_height"],
                  "fill-extrusion-base": ["case", ["has", "render_min_height"], ["get", "render_min_height"], 0],
                  "fill-extrusion-opacity": 0.7
                }}
              />
            </>
          )}
        </Source>
        <Source id="nh10-route" type="geojson" data={nh10GeoJSON as any}>
          <Layer id="nh10-line-glow" type="line" paint={{ "line-color": "#60a5fa", "line-width": 6, "line-opacity": 0.15 }} />
          <Layer id="nh10-line" type="line" paint={{ "line-color": "#3b82f6", "line-width": 2.5, "line-opacity": 0.7, "line-dasharray": [2, 2] }} />
        </Source>
        {routeGeoJSON && (
          <Source id="route-line-src" type="geojson" data={routeGeoJSON as any}>
            <Layer id="route-line-buffer" type="line" paint={{ "line-color": "#ef4444", "line-width": 45, "line-opacity": 0.15, "line-blur": 15 }} />
            <Layer id="route-line-shadow" type="line" paint={{ "line-color": "#000000", "line-width": 7, "line-opacity": 0.3, "line-blur": 3 }} />
            <Layer id="route-line" type="line" paint={{ "line-color": routeColor, "line-width": 3, "line-opacity": 0.9 }} />
          </Source>
        )}
        <Source id="exposure-roads" type="geojson" data={exposureRoadsGeoJSON as any}>
          <Layer id="exposure-roads-line" type="line" minzoom={7} paint={{ "line-color": "#94a3b8", "line-width": 1.5, "line-opacity": 0.65 }} />
        </Source>
        <Source id="exposure-settlements" type="geojson" data={exposureSettlementsGeoJSON as any}>
          <Layer id="exposure-settlement-points" type="circle" minzoom={7} paint={{ "circle-radius": 4, "circle-color": "#e2e8f0", "circle-opacity": 0.85, "circle-stroke-width": 1, "circle-stroke-color": "#0f172a" }} />
          <Layer id="exposure-settlement-labels" type="symbol" minzoom={9} layout={{ "text-field": ["get", "name"], "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"], "text-size": 10, "text-offset": [0, 1.2], "text-anchor": "top" }} paint={{ "text-color": "#f8fafc", "text-halo-color": "rgba(0,0,0,0.9)", "text-halo-width": 1.4 }} />
        </Source>
        <Source id="risk-data" type="geojson" data={riskGeoJSON as any}>
          <Layer id="risk-fill" type="fill" paint={{ "fill-color": ["get", "color"], "fill-opacity": ["get", "opacity"] }} />
          <Layer id="risk-outline" type="line" paint={{ "line-color": ["get", "color"], "line-width": 0.8, "line-opacity": 0.45 }} />
        </Source>
        <Source id="risk-centroids" type="geojson" data={riskCentroidsGeoJSON as any}>
          <Layer id="risk-circle-outer" type="circle" paint={{ "circle-radius": ["case", ["any", ["==", ["get", "risk_level"], "high"], ["==", ["get", "risk_level"], "critical"]], 10, 8], "circle-color": "#64748b", "circle-opacity": 0.9 }} />
          <Layer id="risk-circle-inner" type="circle" paint={{ "circle-radius": ["case", ["any", ["==", ["get", "risk_level"], "high"], ["==", ["get", "risk_level"], "critical"]], 7, 5.5], "circle-color": ["get", "color"], "circle-stroke-width": 0 }} />
          <Layer id="risk-labels" type="symbol" layout={{ "text-field": ["get", "shortName"], "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"], "text-size": 11, "text-offset": [0, 1.6], "text-anchor": "top" }} paint={{ "text-color": "#ffffff", "text-halo-color": "rgba(0,0,0,0.85)", "text-halo-width": 1.5 }} />
        </Source>
        <Source id="event-footprints" type="geojson" data={eventFootprintGeoJSON as any}>
          <Layer id="event-footprint-fill" type="fill" paint={{ "fill-color": ["get", "color"], "fill-opacity": 0.38 }} />
          <Layer id="event-footprint-outline" type="line" minzoom={7} paint={{ "line-color": ["get", "roleColor"], "line-width": ["interpolate", ["linear"], ["zoom"], 7, 1.0, 14, 3.5], "line-opacity": 0.95 }} />
          <Layer id="event-footprint-labels" type="symbol" minzoom={7} layout={{ "text-field": ["concat", ["upcase", ["get", "eventType"]], " \u00b7 OBSERVED"], "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"], "text-size": ["interpolate", ["linear"], ["zoom"], 7, 9, 14, 13], "text-offset": [0, 1.4], "text-anchor": "top" }} paint={{ "text-color": "#f8fafc", "text-halo-color": "rgba(0,0,0,0.95)", "text-halo-width": 1.6 }} />
        </Source>
        {targetGeometryGeoJSON && (
          <Source id="broadcast-target" type="geojson" data={targetGeometryGeoJSON as any}>
            <Layer id="broadcast-target-fill" type="fill" paint={{ "fill-color": "#fbbf24", "fill-opacity": 0.12 }} />
            <Layer id="broadcast-target-outline" type="line" paint={{ "line-color": "#fbbf24", "line-width": 3, "line-opacity": 0.95, "line-dasharray": [3, 1] }} />
            <Layer id="broadcast-target-label" type="symbol" layout={{ "text-field": ["get", "label"], "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"], "text-size": 10, "text-offset": [0, 1.6], "text-anchor": "top" }} paint={{ "text-color": "#fde68a", "text-halo-color": "rgba(0,0,0,0.95)", "text-halo-width": 1.5 }} />
          </Source>
        )}
        {reportPoints.length > 0 && (
          <Source id="verification-reports" type="geojson" data={reportPointsGeoJSON as any}>
            <Layer id="verification-report-points" type="circle" paint={{ "circle-radius": 6, "circle-color": ["get", "color"], "circle-opacity": 0.95, "circle-stroke-width": 1.5, "circle-stroke-color": "#0f172a" }} />
            <Layer id="verification-selected-report" type="circle" filter={selectedReportId ? ["==", "id", String(selectedReportId)] : ["==", "id", ""]} paint={{ "circle-radius": 12, "circle-color": "#ffffff", "circle-opacity": 0.18, "circle-stroke-width": 2.5, "circle-stroke-color": "#ffffff" }} />
          </Source>
        )}
        <Source id="historical-data" type="geojson" data={historicalGeoJSON as any}>
          <Layer id="historical-points" type="circle" minzoom={8} paint={{ "circle-radius": 5, "circle-color": ["get", "color"], "circle-opacity": 0.9, "circle-stroke-width": 1.5, "circle-stroke-color": "#f8fafc" }} />
          <Layer id="historical-selected" type="circle" filter={selectedEventId ? ["==", "id", selectedEventId] : ["==", "id", ""]} paint={{ "circle-radius": 9, "circle-color": "#ffffff", "circle-opacity": 0.25, "circle-stroke-width": 2, "circle-stroke-color": "#ffffff" }} />
        </Source>
        {selectedEventLayer && (
          <Layer id="selected-event-outline" type="line" source="event-footprints" filter={selectedEventId ? ["==", "event_id", selectedEventId] : ["==", "event_id", ""]} paint={{ "line-color": "#ffffff", "line-width": 3, "line-opacity": 1 }} />
        )}
        {selectedCell && !is3D && (
          <Layer id="selected-highlight" type="line" source="risk-data" filter={["==", "location_id", selectedCell.location_id]} paint={{ "line-color": "#ffffff", "line-width": 3 }} />
        )}
        {highlightCellId && (
          <Layer id="operator-selected-highlight" type="line" source="risk-data" filter={["==", "location_id", highlightCellId]} paint={{ "line-color": "#ffffff", "line-width": 3.5, "line-opacity": 1 }} />
        )}
        <NavigationControl position="top-right" showCompass={true} showZoom={true} visualizePitch={true} />
      </Map>

      {selectedEventRecord && (
        <div className="absolute top-20 left-4 z-20 w-[320px] max-h-[calc(100%-8rem)] overflow-y-auto rounded-xl border border-white/15 bg-black/80 p-4 text-white shadow-2xl backdrop-blur-md">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[10px] font-black uppercase tracking-widest text-sky-300">Observed Event Extent</div>
              <div className="mt-1 text-sm font-bold capitalize">{selectedEventRecord.event_type}</div>
            </div>
            <button
              onClick={() => setSelectedEventId(null)}
              className="rounded border border-white/20 px-2 py-0.5 text-xs text-slate-300 hover:bg-white/10"
            >
              ✕
            </button>
          </div>

          <dl className="mt-3 space-y-2 text-[11px]">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Observed at</dt>
              <dd className="font-semibold">{selectedEventRecord.date || selectedEventLayer?.observedAt || 'Unknown'}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Source</dt>
              <dd className="max-w-[190px] text-right font-semibold">{selectedEventLayer?.source || selectedEventRecord.source}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Confidence</dt>
              <dd className="font-semibold capitalize">{selectedEventLayer?.confidence || (selectedEventRecord.verified ? 'verified' : 'unverified')}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Geometry</dt>
              <dd className="font-semibold">
                {selectedEventLayer ? `${selectedEventLayer.geometry.type}${selectedEventLayer.area_sq_km ? ` · ${selectedEventLayer.area_sq_km} km²` : ''}` : 'Point record only'}
              </dd>
            </div>
          </dl>

          <div className="mt-4 rounded-lg border border-amber-400/30 bg-amber-950/30 p-3">
            <div className="text-[10px] font-black uppercase tracking-widest text-amber-300">Predicted Risk</div>
            <div className="mt-1 text-[11px] text-slate-200">
              {nearestRiskCell ? `${nearestRiskCell.name}: ${nearestRiskCell.risk_level || 'UNKNOWN'}${nearestRiskCell.risk_score ? ` · ${nearestRiskCell.risk_score.toFixed(1)}/100` : ''}` : 'No nearby model cell'}
            </div>
            <div className="mt-1 text-[10px] text-slate-400">Separate model surface; not the observed footprint.</div>
          </div>

          <div className="mt-3">
            <div className="text-[10px] font-black uppercase tracking-widest text-slate-300">Exposure</div>
            <div className="mt-2 space-y-1 text-[11px]">
              {nearbyRoads.length ? nearbyRoads.map(road => (
                <div key={road.name} className="flex justify-between gap-3">
                  <span className="text-slate-200">{road.name}</span>
                  <span className="text-slate-400">{road.distanceKm.toFixed(1)} km</span>
                </div>
              )) : <div className="text-slate-400">No mapped roads within 25 km</div>}
              {nearbySettlements.length ? nearbySettlements.map(settlement => (
                <div key={settlement.name} className="flex justify-between gap-3">
                  <span className="text-slate-200">{settlement.name}</span>
                  <span className="text-slate-400">{settlement.distanceKm.toFixed(1)} km</span>
                </div>
              )) : <div className="text-slate-400">No mapped settlements within 25 km</div>}
            </div>
          </div>

          {selectedEventRecord.impact && (
            <div className="mt-3 border-t border-white/10 pt-3 text-[11px] text-slate-300">
              <span className="font-semibold text-white">Reported impact: </span>{selectedEventRecord.impact}
            </div>
          )}
        </div>
      )}

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
            onClick={() => handleExplore3D(selectedCell)}
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
