import React, { useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
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

interface HistoricalLandslide {
  id: string;
  lat: number;
  lon: number;
  date: string;
  type: string;
  trigger: string;
  impact: string;
}

interface LandslideMapProps {
  cells: GeoCell[];
  nh10Route: number[][];
  routeSafety?: string;
  historicalLandslides: HistoricalLandslide[];
  selectedCellId: string | null;
  onCellSelect: (id: string) => void;
  simulationCells?: GeoCell[];
}

const RISK_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  moderate: '#f59e0b',
  low: '#10b981',
};

const RISK_FILL_OPACITY: Record<string, number> = {
  critical: 0.75,
  high: 0.60,
  moderate: 0.45,
  low: 0.30,
};

// ---------------------------------------------------------------------------
// Pure SVG-based geographic projection map
// We use a simple Mercator-style projection on actual lat/lon coordinates
// This gives real geographic positions without requiring a Leaflet tile server
// ---------------------------------------------------------------------------

const SVG_W = 900;
const SVG_H = 550;

function projectLon(lon: number, bounds: any): number {
  if (!bounds || bounds.lon_max === bounds.lon_min) return SVG_W / 2;
  return ((lon - bounds.lon_min) / (bounds.lon_max - bounds.lon_min)) * SVG_W;
}

function projectLat(lat: number, bounds: any): number {
  if (!bounds || bounds.lat_max === bounds.lat_min) return SVG_H / 2;
  return SVG_H - ((lat - bounds.lat_min) / (bounds.lat_max - bounds.lat_min)) * SVG_H;
}

function getRiskColor(level: string | undefined): string {
  return RISK_COLORS[level?.toLowerCase() || 'low'] || RISK_COLORS.low;
}

function getRiskFillOpacity(level: string | undefined): number {
  return RISK_FILL_OPACITY[level?.toLowerCase() || 'low'] || 0.30;
}

export function LandslideMap({
  cells,
  nh10Route,
  routeSafety,
  historicalLandslides,
  selectedCellId,
  onCellSelect,
  simulationCells,
}: LandslideMapProps) {

  const isNepal = cells && cells.length > 0 && cells[0].centroid_lon < 86;
  const mapTitle = isNepal ? "Rasuwa District - Landslide Risk Map" : "North Sikkim - Landslide Risk Map";
  const mapSubtitle = isNepal ? "HIMALAYAS - NEPAL" : "NER - INDIA";
  const svgOverlayTitle = isNepal ? "Langtang Region, Rasuwa" : "Mangan District, North Sikkim";

  const activeCells = simulationCells && simulationCells.length > 0 ? simulationCells : cells;

  const MAP_BOUNDS = React.useMemo(() => {
    if (!cells || cells.length === 0) return { lat_min: 27.10, lat_max: 27.75, lon_min: 88.25, lon_max: 88.70 };
    const lats = cells.map(c => c.centroid_lat);
    const lons = cells.map(c => c.centroid_lon);
    
    // Calculate precise bounding box
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    
    // Add margin (roughly 10% of the range)
    const latMargin = Math.max(0.05, (maxLat - minLat) * 0.15);
    const lonMargin = Math.max(0.05, (maxLon - minLon) * 0.15);
    
    return { 
      lat_min: minLat - latMargin, 
      lat_max: maxLat + latMargin, 
      lon_min: minLon - lonMargin, 
      lon_max: maxLon + lonMargin 
    };
  }, [cells]);
  
  // Dynamic grid lines based on bounds
  const latLines = React.useMemo(() => {
    const lines = [];
    const step = (MAP_BOUNDS.lat_max - MAP_BOUNDS.lat_min) / 5;
    for(let i=1; i<5; i++) lines.push(MAP_BOUNDS.lat_min + (step * i));
    return lines;
  }, [MAP_BOUNDS]);

  const lonLines = React.useMemo(() => {
    const lines = [];
    const step = (MAP_BOUNDS.lon_max - MAP_BOUNDS.lon_min) / 5;
    for(let i=1; i<5; i++) lines.push(MAP_BOUNDS.lon_min + (step * i));
    return lines;
  }, [MAP_BOUNDS]);


  // Merge risk data from simulationCells into cells when simulation is running
  const mergedCells = cells.map(cell => {
    const simCell = simulationCells?.find(s => s.location_id === cell.location_id);
    return simCell ? { ...cell, ...simCell } : cell;
  });

  return (
    <Card className="h-full flex flex-col overflow-hidden border-border/40 bg-card/60 backdrop-blur-sm">
      <CardHeader className="pb-2 flex-shrink-0">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="font-heading flex items-center gap-2 text-base">
            <MapPin className="h-5 w-5 text-primary" />
            {mapTitle}
            <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider ml-1">
              {mapSubtitle}
            </Badge>
          </CardTitle>
          <div className="flex gap-2 flex-wrap">
            {(['Low', 'Moderate', 'High', 'Critical'] as const).map(level => (
              <div key={level} className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted/50 text-[10px] uppercase font-bold tracking-wider">
                <div className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: RISK_COLORS[level.toLowerCase()] }} />
                {level}
              </div>
            ))}
          </div>
        </div>
        <div className="flex gap-3 mt-1 text-[10px] font-medium text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-4 border border-blue-400/60 bg-blue-400/20" />
            {isNepal ? 'H01 Trishuli Highway' : 'NH-10 Highway'}
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-zinc-400/50 border border-zinc-400" />
            Historical Landslide
          </span>
        </div>
      </CardHeader>

      <CardContent className="flex-1 p-0 relative overflow-hidden min-h-[420px]">

        {/* Terrain background */}
        <div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(160deg, #1a2035 0%, #0f1929 50%, #111827 100%)',
          }}
        />

        {/* Grid lines (subtle geographic reference) */}
        <svg
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          className="absolute inset-0 w-full h-full"
          preserveAspectRatio="xMidYMid meet"
        >
          <g>
          {/* Reference grid */}
          <g opacity="0.07">
            {latLines.map(lat => (
              <line key={lat}
                x1={0} y1={projectLat(lat, MAP_BOUNDS)}
                x2={SVG_W} y2={projectLat(lat, MAP_BOUNDS)}
                stroke="#6ee7b7" strokeWidth="1" />
            ))}
            {lonLines.map(lon => (
              <line key={lon}
                x1={projectLon(lon, MAP_BOUNDS)} y1={0}
                x2={projectLon(lon, MAP_BOUNDS)} y2={SVG_H}
                stroke="#6ee7b7" strokeWidth="1" />
            ))}
          </g>

          {/* Coordinate labels */}
          <g fill="#6ee7b7" opacity="0.25" fontSize="9" fontFamily="monospace">
            {latLines.map(lat => (
              <text key={lat} x={4} y={projectLat(lat, MAP_BOUNDS) - 2}>{lat.toFixed(2)}°N</text>
            ))}
            {lonLines.map(lon => (
              <text key={lon} x={projectLon(lon, MAP_BOUNDS) + 2} y={SVG_H - 4}>{lon.toFixed(2)}°E</text>
            ))}
          </g>

          {/* NH-10 Highway Route */}
          {nh10Route && nh10Route.length > 1 && (
            <>
              {/* Glow effect */}
              <polyline
                points={nh10Route.map(([lat, lon]) => `${projectLon(lon, MAP_BOUNDS)},${projectLat(lat, MAP_BOUNDS)}`).join(' ')}
                fill="none"
                stroke={routeSafety === 'CRITICAL' ? '#ef4444' : routeSafety === 'HIGH_RISK' ? '#f97316' : routeSafety === 'CAUTION' ? '#eab308' : '#60a5fa'}
                strokeWidth="3"
                strokeOpacity="0.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* Main route */}
              <polyline
                points={nh10Route.map(([lat, lon]) => `${projectLon(lon, MAP_BOUNDS)},${projectLat(lat, MAP_BOUNDS)}`).join(' ')}
                fill="none"
                stroke={routeSafety === 'CRITICAL' ? '#b91c1c' : routeSafety === 'HIGH_RISK' ? '#c2410c' : routeSafety === 'CAUTION' ? '#a16207' : '#3b82f6'}
                strokeWidth="3.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={routeSafety === 'CRITICAL' ? '4 4' : '0'}
              />
              {/* Route label */}
              <text
                x={projectLon(nh10Route[Math.floor(nh10Route.length/2)][1], MAP_BOUNDS)}
                y={projectLat(nh10Route[Math.floor(nh10Route.length/2)][0], MAP_BOUNDS) - 6}
                fill="#93c5fd"
                fontSize="8"
                fontWeight="bold"
                opacity="0.8"
              >
                Regional Route
              </text>
            </>
          )}

          {/* Risk Surface — Geographic Grid Cells */}
          {mergedCells.map(cell => {
            const x1 = projectLon(cell.lon_min ?? cell.centroid_lon - 0.02, MAP_BOUNDS);
            const x2 = projectLon(cell.lon_max ?? cell.centroid_lon + 0.02, MAP_BOUNDS);
            const y1 = projectLat(cell.lat_max ?? cell.centroid_lat + 0.02, MAP_BOUNDS);
            const y2 = projectLat(cell.lat_min ?? cell.centroid_lat - 0.02, MAP_BOUNDS);
            const cx = projectLon(cell.centroid_lon, MAP_BOUNDS);
            const cy = projectLat(cell.centroid_lat, MAP_BOUNDS);
            const w = Math.abs(x2 - x1);
            const h = Math.abs(y2 - y1);
            const color = getRiskColor(cell.risk_level);
            const opacity = getRiskFillOpacity(cell.risk_level);
            const isSelected = selectedCellId === cell.location_id;
            const isCritical = cell.risk_level === 'critical';
            const isHighRisk = cell.risk_level === 'high' || isCritical;

            return (
              <g
                key={cell.location_id}
                className="cursor-pointer"
                onClick={() => onCellSelect(cell.location_id)}
              >
                {isSelected ? (
                  <>
                    {/* Risk fill rectangle */}
                    <rect
                      x={Math.min(x1, x2)}
                      y={Math.min(y1, y2)}
                      width={w}
                      height={h}
                      fill={color}
                      fillOpacity={Math.min(opacity + 0.25, 0.95)}
                      rx="3"
                      stroke="#ffffff"
                      strokeOpacity="0.9"
                      strokeWidth="2"
                    />

                    {/* Pulsing ring for critical cells */}
                    {isCritical && (
                      <rect
                        x={Math.min(x1, x2) - 3}
                        y={Math.min(y1, y2) - 3}
                        width={w + 6}
                        height={h + 6}
                        fill="none"
                        stroke={color}
                        strokeOpacity="0.4"
                        strokeWidth="2"
                        rx="5"
                      >
                        <animate attributeName="stroke-opacity" values="0.5;0.0;0.5" dur="2s" repeatCount="indefinite" />
                        <animate attributeName="stroke-width" values="2;4;2" dur="2s" repeatCount="indefinite" />
                      </rect>
                    )}

                    {/* Center dot for selected */}
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isHighRisk ? 5 : 3.5}
                      fill="#ffffff"
                    />
                  </>
                ) : (
                  <>
                    {/* Unselected circle shape with gray outer ring and risk color inner fill */}
                    <circle 
                      cx={cx} 
                      cy={cy} 
                      r={9} 
                      fill={color} 
                      fillOpacity="0.85"
                      stroke="#64748b" 
                      strokeWidth="2.5" 
                    />
                    
                    {/* Pulsing ring for critical cells even when unselected */}
                    {isCritical && (
                      <circle cx={cx} cy={cy} r={13} fill="none" stroke={color} strokeOpacity="0.5" strokeWidth="2">
                        <animate attributeName="r" values="13;17;13" dur="2s" repeatCount="indefinite" />
                        <animate attributeName="stroke-opacity" values="0.5;0.0;0.5" dur="2s" repeatCount="indefinite" />
                      </circle>
                    )}
                  </>
                )}

                {/* NH-10 warning indicator */}
                {cell.near_nh10 && isHighRisk && (
                  <text x={cx + 7} y={cy - 5} fill="#60a5fa" fontSize="7" fontWeight="bold" opacity="0.9">⚠ NH10</text>
                )}

                {/* Zone label */}
                <text
                  x={cx}
                  y={cy + 16}
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize={isSelected ? "9.5" : "8"}
                  fontWeight={isSelected ? "700" : "500"}
                  opacity={isSelected ? 0.95 : 0.65}
                  fontFamily="system-ui, sans-serif"
                >
                  {cell.name.split(' ').slice(-1)[0]}
                </text>

                {/* Risk score badge on selected */}
                {isSelected && (
                  <>
                    <rect x={cx - 16} y={cy + 20} width={32} height={12} rx="2" fill={color} fillOpacity="0.85" />
                    <text x={cx} y={cy + 29} textAnchor="middle" fill="#ffffff" fontSize="7.5" fontWeight="bold">
                      {cell.risk_score?.toFixed(0) ?? '--'}
                    </text>
                  </>
                )}
              </g>
            );
          })}

          {/* Historical Landslide Markers */}
          {historicalLandslides?.map(ls => {
            const cx = projectLon(ls.lon, MAP_BOUNDS);
            const cy = projectLat(ls.lat, MAP_BOUNDS);
            return (
              <g key={ls.id} className="cursor-pointer" title={ls.type}>
                <circle cx={cx} cy={cy} r="5" fill="#71717a" fillOpacity="0.5" stroke="#a1a1aa" strokeWidth="1" />
                
              </g>
            );
          })}

          {/* Compass rose */}
          <g transform={`translate(${SVG_W - 35}, 30)`} opacity="0.5">
            <circle cx={0} cy={0} r="14" fill="none" stroke="#6ee7b7" strokeWidth="0.5" />
            <text x={0} y={-17} textAnchor="middle" fill="#6ee7b7" fontSize="8" fontWeight="bold">N</text>
            <line x1={0} y1={-12} x2={0} y2={12} stroke="#6ee7b7" strokeWidth="0.8" />
            <line x1={-12} y1={0} x2={12} y2={0} stroke="#6ee7b7" strokeWidth="0.8" />
            <polygon points="0,-12 -3,-5 3,-5" fill="#6ee7b7" />
          </g>

          {/* Map title overlay */}
          <text x={10} y={18} fill="#e2e8f0" fontSize="11" fontWeight="bold" fontFamily="system-ui" opacity="0.8">
            {svgOverlayTitle}
          </text>
          <text x={10} y={30} fill="#94a3b8" fontSize="8" fontFamily="system-ui" opacity="0.7">
            Landslide Risk Surface - Click any cell to inspect
          </text>
          </g>
        </svg>
      </CardContent>
    </Card>
  );
}
