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
const mapStyle = `https://api.maptiler.com/maps/satellite/style.json?key=${MAPTILER_KEY}`;

export default function GeospatialViewer({ 
  cells = [], 
  historicalEvents = [],
  nh10Route = [],
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
  const [viewState, setViewState] = useState({
    longitude: 88.5122,
    latitude: 27.3314, // North Sikkim Center
    zoom: 9,
    pitch: 0,
    bearing: 0
  });

  const [selectedCell, setSelectedCell] = useState<GeoCell | null>(null);
  const [is3D, setIs3D] = useState(false);
  const [saved2DState, setSaved2DState] = useState<any>(null);

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
        zoom: 9,
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
        interactiveLayerIds={['risk-fill']}
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

      {/* MOCK UI FOR CANDIDATE SLOPE SCANNING (matches user image) */}
      {routeSafety && routeSafety !== 'UNKNOWN' && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 pointer-events-none flex flex-col items-center gap-2">
          {/* Main Candidate details */}
          <div className="bg-black/80 backdrop-blur-md border border-white/10 rounded-full pl-3 pr-1 py-1 flex items-center gap-3 shadow-xl shadow-red-900/20">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <div className="text-[10px] font-bold tracking-wide text-white leading-tight">
                Candidate slope near {regionState.region === 'nepal_case' ? 'Langtang Corridor' : 'NH-10'}<br/>
                <span className="text-red-400">HIGH - 85/100 - {regionState.region === 'nepal_case' ? '528.4' : '112.5'} km path</span>
              </div>
            </div>
            <div className="bg-white/10 hover:bg-white/20 text-white text-[10px] font-bold px-3 py-1.5 rounded-full cursor-pointer pointer-events-auto transition-colors">
              Details
            </div>
            <div className="bg-transparent hover:bg-white/10 text-white w-6 h-6 flex items-center justify-center rounded-full cursor-pointer pointer-events-auto">
              <span className="text-xs text-slate-400">&times;</span>
            </div>
          </div>
          
          {/* Scan this area button */}
          <div className="bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 backdrop-blur-md px-4 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 cursor-pointer pointer-events-auto hover:bg-emerald-500/30 transition-colors shadow-lg shadow-emerald-900/20">
            <span className="w-2.5 h-2.5 border-2 border-emerald-400 rounded-[2px]" /> Scan this area
          </div>
          
          {/* Detected count */}
          <div className="bg-black/60 backdrop-blur-sm px-3 py-1 rounded-full text-[9px] font-bold text-white tracking-widest mt-1">
            25 candidate slopes detected in view
          </div>
        </div>
      )}

      <div className="absolute top-4 left-4 z-10 space-y-2 pointer-events-none">
        <Badge className="bg-black/80 text-white backdrop-blur-sm border-white/10 px-3 py-1.5 text-xs font-medium uppercase tracking-wider">
          {is3D ? (
            <span className="flex items-center text-blue-400 gap-1.5"><Navigation className="w-3.5 h-3.5" /> 3D Drill-Down Active</span>
          ) : (
            <span className="flex items-center text-teal-400 gap-1.5"><MapPin className="w-3.5 h-3.5" /> Regional 2D Overview</span>
          )}
        </Badge>
      </div>

      {/* SELECTED CELL DETAILS PANEL */}
      {selectedCell && (
        <Card className="absolute bottom-6 right-6 w-80 bg-black/90 border-border/30 backdrop-blur-md shadow-2xl z-10 animate-in slide-in-from-right-8 pointer-events-auto">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold text-white flex items-center justify-between">
              {selectedCell.name}
              <Badge className={cn(
                "font-bold",
                selectedCell.risk_level === 'CRITICAL' ? "bg-red-500/20 text-red-500" :
                selectedCell.risk_level === 'HIGH' ? "bg-orange-500/20 text-orange-500" :
                selectedCell.risk_level === 'MODERATE' ? "bg-yellow-500/20 text-yellow-500" :
                "bg-green-500/20 text-green-500"
              )}>
                {selectedCell.risk_level || 'LOW'}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2 text-xs text-slate-300">
              <div className="bg-white/5 p-2 rounded">
                <div className="text-slate-500 mb-1">Slope Angle</div>
                <div className="font-mono text-white">{selectedCell.slope_angle.toFixed(1)}?</div>
              </div>
              <div className="bg-white/5 p-2 rounded">
                <div className="text-slate-500 mb-1">History</div>
                <div className="font-mono text-white">{selectedCell.historical_count} Events</div>
              </div>
            </div>
            
            {selectedCell.near_nh10 && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-xs p-2 rounded flex items-start gap-2">
                <div className="mt-0.5">??</div>
                <div>Critical Infrastructure (NH-10) intersecting this risk cell.</div>
              </div>
            )}

            {!is3D ? (
              <Button 
                onClick={() => handleExplore3D(selectedCell)}
                className="w-full bg-teal-600 hover:bg-teal-500 text-white font-medium text-xs h-8"
              >
                <Navigation className="w-3.5 h-3.5 mr-2" />
                EXPLORE 3D TERRAIN
              </Button>
            ) : (
              <Button 
                onClick={handleReturnTo2D}
                variant="outline"
                className="w-full border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white font-medium text-xs h-8"
              >
                RETURN TO 2D OVERVIEW
              </Button>
            )}
          </CardContent>
        </Card>
      )}

    </div>
  );
}
