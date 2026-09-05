import React, { useState, useCallback, useRef } from 'react';
import Map, { Source, Layer, MapRef, NavigationControl } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { MapPin, Navigation } from 'lucide-react';
import { cn } from '../lib/utils';

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
}

// Temporary Free MapTiler DEM & Basemap Source for Prototype
const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY || 'get_your_own_key'; // We will need to replace this if it hits limits, or use a public style
const mapStyle = `https://api.maptiler.com/maps/hybrid/style.json?key=${MAPTILER_KEY}`;

export default function GeospatialViewer({ 
  cells = [], 
  historicalEvents = [],
  nh10Route = [],
  routeSafety,
  onCellClick,
  initialSelectedCellId
}: { 
  cells?: GeoCell[],
  historicalEvents?: any[],
  nh10Route?: any[],
  onCellClick?: (cell: GeoCell) => void,
  initialSelectedCellId?: string | null,
  nh10Route?: any[],
  routeSafety?: string,
}) {
  const mapRef = useRef<MapRef>(null);
  const isNepal = cells && cells.length > 0 && cells[0].centroid_lon < 86;
  const defaultCenter = isNepal ? { lon: 85.3, lat: 28.1, zoom: 9 } : { lon: 88.5122, lat: 27.3314, zoom: 11 };

  const [viewState, setViewState] = useState({
    longitude: defaultCenter.lon,
    latitude: defaultCenter.lat,
    zoom: defaultCenter.zoom,
    pitch: 0,
    bearing: 0
  });
  
  // Re-center map if region changes
  React.useEffect(() => {
    setViewState(prev => ({
      ...prev,
      longitude: defaultCenter.lon,
      latitude: defaultCenter.lat,
      zoom: defaultCenter.zoom
    }));
  }, [isNepal]);


  const [selectedCell, setSelectedCell] = useState<GeoCell | null>(null);
  const [is3D, setIs3D] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [saved2DState, setSaved2DState] = useState<any>(null);
  const resolvedRoute = nh10Route && nh10Route.length > 0 ? nh10Route : [];
  const regionState = { region: cells[0]?.centroid_lon < 86 ? 'nepal_case' : 'sih_demo' };

  // Convert risk cells to GeoJSON
  const riskGeoJSON = React.useMemo(() => {
    return {
      type: 'FeatureCollection',
      features: cells.map(cell => {
        let color = '#22c55e'; // LOW (Green)
        let opacity = 0.3;
        if (cell.risk_level === 'moderate' || cell.risk_level === 'MODERATE') { color = '#eab308'; opacity = 0.4; }
        if (cell.risk_level === 'high' || cell.risk_level === 'HIGH') { color = '#f97316'; opacity = 0.55; }
        if (cell.risk_level === 'critical' || cell.risk_level === 'CRITICAL') { color = '#ef4444'; opacity = 0.75; }

        const lon_min = cell.lon_min;
        const lon_max = cell.lon_max;
        const lat_min = cell.lat_min;
        const lat_max = cell.lat_max;

        return {
          type: 'Feature',
          properties: { ...cell, color, opacity },
          geometry: {
            type: 'Polygon',
            coordinates: [[
              [lon_min, lat_min],
              [lon_max, lat_min],
              [lon_max, lat_max],
              [lon_min, lat_max],
              [lon_min, lat_min]
            ]]
          }
        };
      })
    };
  }, [cells]);


  const riskCentroidsGeoJSON = React.useMemo(() => {
    return {
      type: 'FeatureCollection',
      features: cells.map(cell => {
        let color = '#22c55e';
        if (cell.risk_level === 'moderate' || cell.risk_level === 'MODERATE') color = '#eab308';
        if (cell.risk_level === 'high' || cell.risk_level === 'HIGH') color = '#f97316';
        if (cell.risk_level === 'critical' || cell.risk_level === 'CRITICAL') color = '#ef4444';

        const shortName = cell.name.split(' ').slice(-1)[0];

        return {
          type: 'Feature',
          properties: { ...cell, color, shortName },
          geometry: {
            type: 'Point',
            coordinates: [cell.centroid_lon, cell.centroid_lat]
          }
        };
      })
    };
  }, [cells]);

  const nh10GeoJSON = React.useMemo(() => {
    return {
      type: 'Feature',
      properties: {},
      geometry: {
        type: 'LineString',
        coordinates: nh10Route.map(coord => [coord[1], coord[0]]) // [lng, lat]
      }
    };
  }, [nh10Route]);

  const historicalGeoJSON = React.useMemo(() => {
    return {
      type: 'FeatureCollection',
      features: historicalEvents.map(event => ({
        type: 'Feature',
        properties: { ...event },
        geometry: {
          type: 'Point',
          coordinates: [event.lon, event.lat]
        }
      }))
    };
  }, [historicalEvents]);

  const handleExplore3D = (cell: GeoCell) => {
    if (!mapRef.current) return;
    
    // Cache the exact 2D geographic camera state before drill-down
    setSaved2DState({
      longitude: viewState.longitude,
      latitude: viewState.latitude,
      zoom: viewState.zoom
    });

    setIs3D(true);
    mapRef.current.flyTo({
      center: [cell.centroid_lon, cell.centroid_lat],
      zoom: 12.5,
      pitch: 75,
      bearing: 25,
      duration: 2500,
    });
  };

  const handleReturnTo2D = () => {
    if (!mapRef.current) return;
    
    setIs3D(false);
    
    // Restore the exact 2D camera state
    if (saved2DState) {
      mapRef.current.flyTo({
        center: [saved2DState.longitude, saved2DState.latitude],
        zoom: saved2DState.zoom,
        pitch: 0,
        bearing: 0,
        duration: 2000,
      });
    } else {
      mapRef.current.flyTo({
        center: [88.5122, 27.3314],
        zoom: 11,
        pitch: 0,
        bearing: 0,
        duration: 2000,
      });
    }
  };

  const handleMapLoad = () => {
    if (initialSelectedCellId && !is3D) {
      const targetCell = cells.find(c => c.location_id === initialSelectedCellId);
      if (targetCell) {
        setSelectedCell(targetCell);
        
        // Slight delay to ensure map canvas is fully sized before flying
        setTimeout(() => {
          handleExplore3D(targetCell);
        }, 300);
      }
    }
  };

  return (
    <div className="relative w-full h-[600px] bg-slate-900 rounded-xl overflow-hidden border border-border/20 shadow-2xl">
      
      
      {is3D && (
        <div className="absolute top-4 right-4 z-10">
          <Button 
            onClick={handleReturnTo2D}
            variant="outline"
            className="bg-black/80 backdrop-blur-md border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white font-medium text-xs h-8 shadow-lg"
          >
            <Navigation className="w-3.5 h-3.5 mr-2 rotate-180" />
            RETURN TO 2D OVERVIEW
          </Button>
        </div>
      )}

      {/* MAPLIBRE GL CANVAS */}
      <Map
        ref={mapRef}
        onLoad={handleMapLoad}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        mapStyle={mapStyle}
        terrain={is3D ? { source: 'terrain-source', exaggeration: 1.5 } : undefined}
        onClick={(e) => {
          if (e.features && e.features.length > 0) {
            const feature = e.features[0];
            const clickedCell = cells.find(c => c.location_id === feature.properties.location_id);
            if (clickedCell) {
              setSelectedCell(clickedCell);
              if (onCellClick) onCellClick(clickedCell);
              
              // Automatically trigger the 3D drill-down when clicked in 2D overview
              if (!is3D) {
                handleExplore3D(clickedCell);
              }
            }
          }
        }}
        interactiveLayerIds={['risk-fill', 'risk-circle-outer', 'risk-circle-inner']}
      >
        {/* TERRAIN SOURCE (DEM) */}
        <Source
          id="terrain-source"
          type="raster-dem"
          url={`https://api.maptiler.com/tiles/terrain-rgb/tiles.json?key=${MAPTILER_KEY}`}
          tileSize={256}
        />

        {/* NH-10 ROUTE */}
        <Source id="nh10-route" type="geojson" data={nh10GeoJSON as any}>
          <Layer
            id="nh10-line-glow"
            type="line"
            paint={{
              'line-color': '#60a5fa',
              'line-width': 6,
              'line-opacity': 0.15
            }}
          />
          <Layer
            id="nh10-line"
            type="line"
            paint={{
              'line-color': '#3b82f6',
              'line-width': 2.5,
              'line-opacity': 0.7,
              'line-dasharray': [2, 2]
            }}
          />
        </Source>

        {/* RISK GRID (GeoJSON) */}
        <Source id="risk-data" type="geojson" data={riskGeoJSON as any}>
          <Layer
            id="risk-fill"
            type="fill"
            paint={{
              'fill-color': ['get', 'color'],
              'fill-opacity': ['get', 'opacity'],
            }}
          />
        </Source>

        {/* RISK CENTROIDS & LABELS */}
        <Source id="risk-centroids" type="geojson" data={riskCentroidsGeoJSON as any}>
          <Layer
            id="risk-points"
            type="circle"
            paint={{
              'circle-radius': ['case', ['any', ['==', ['get', 'risk_level'], 'high'], ['==', ['get', 'risk_level'], 'critical']], 5, 3.5],
              'circle-color': ['get', 'color'],
              'circle-stroke-width': 1,
              'circle-stroke-color': '#ffffff'
            }}
          />
          <Layer
            id="risk-labels"
            type="symbol"
            layout={{
              'text-field': ['get', 'shortName'],
              'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
              'text-size': 11,
              'text-offset': [0, 1.5],
              'text-anchor': 'top'
            }}
            paint={{
              'text-color': '#ffffff',
              'text-halo-color': 'rgba(0,0,0,0.8)',
              'text-halo-width': 1
            }}
          />
        </Source>

        {/* HISTORICAL MARKERS */}
        <Source id="historical-data" type="geojson" data={historicalGeoJSON as any}>
          <Layer
            id="historical-points"
            type="circle"
            paint={{
              'circle-radius': 4,
              'circle-color': '#71717a',
              'circle-opacity': 0.8,
              'circle-stroke-width': 1,
              'circle-stroke-color': '#a1a1aa'
            }}
          />
        </Source>

        {/* Selected Cell Marker */}
        {selectedCell && !is3D && (
          <Layer
            id="selected-highlight"
            type="line"
            source="risk-data"
            filter={['==', 'location_id', selectedCell.location_id]}
            paint={{
              'line-color': '#ffffff',
              'line-width': 3,
            }}
          />
        )}

        {/* ROUTE SAFETY LAYER: colored line on map */}
        {resolvedRoute.length > 1 && (() => {
          const routeColor = routeSafety === 'CRITICAL' ? '#ef4444' :
            routeSafety === 'HIGH_RISK' ? '#f97316' :
            routeSafety === 'CAUTION' ? '#eab308' : '#3b82f6'; // use blue if safe instead of green for realistic look
            
          const routeGeoJSON = {
            type: 'FeatureCollection',
            features: [{
              type: 'Feature',
              properties: { safety: routeSafety },
              geometry: {
                type: 'LineString',
                coordinates: resolvedRoute.map((p: any) => [p[1], p[0]])
              }
            }]
          };
          
          // Generate a candidate slope buffer polygon (a wide path around the line) to replicate the UI requested
          // For visual purposes, we just render a thick line under it
          
          return (
            <>
              <Source id="route-line-src" type="geojson" data={routeGeoJSON}>
                <Layer
                  id="route-line-buffer"
                  type="line"
                  paint={{
                    'line-color': '#ef4444',
                    'line-width': 45,
                    'line-opacity': 0.15,
                    'line-blur': 15,
                  }}
                />
                <Layer
                  id="route-line-shadow"
                  type="line"
                  paint={{
                    'line-color': '#000000',
                    'line-width': 7,
                    'line-opacity': 0.3,
                    'line-blur': 3,
                  }}
                />
                <Layer
                  id="route-line"
                  type="line"
                  paint={{
                    'line-color': routeColor,
                    'line-width': 3,
                    'line-opacity': 0.9,
                  }}
                />
              </Source>
            </>
          );
        })()}
      </Map>

      {/* OVERLAY UI */}

      {/* SELECTED CELL DETAILS PANEL */}
      

    </div>
  );
}
