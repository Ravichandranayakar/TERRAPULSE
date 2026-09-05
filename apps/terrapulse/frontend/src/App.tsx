import React, { useState, useEffect, useCallback } from 'react';
import { rpcCall } from './api';
import { useRegion } from './contexts/RegionContext';
import { EventReplay } from './features/EventReplay';
import { cn } from './lib/utils';
import {
  LayoutDashboard,
  Map as MapIcon,
  Clock,
  AlertTriangle,
  Activity,
  ShieldCheck,
  Menu,
  ChevronRight,
  Database,
  Zap,
  Info,
  X,
  Shield,
  Settings,
  Timer,
  Globe,
  Layers,
} from 'lucide-react';
import { Button } from './components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Separator } from './components/ui/separator';
import { LandslideMap } from './features/LandslideMap';
import GeospatialViewer from './features/GeospatialViewer';
import { XAIPanel } from './features/XAIPanel';
import { ForecastDashboard } from './features/ForecastDashboard';
import { WarningsPanel } from './features/WarningsPanel';
import { StormSimulator } from './features/StormSimulator';
import {
  SiScikitlearn,
  SiPandas,
  SiFastapi,
  SiSqlite,
} from 'react-icons/si';

// ---------------------------------------------------------------------------
// TYPES
// ---------------------------------------------------------------------------
interface GeoCell {
  location_id: string;
  name: string;
  district: string;
  state: string;
  centroid_lat: number;
  centroid_lon: number;
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
  slope_angle: number;
  elevation_m: number;
  soil_type: string;
  near_nh10: boolean;
  historical_count: number;
  risk_level?: string;
  risk_score?: number;
  contributing_factors?: any[];
  rainfall?: any;
}

interface Warning {
  id: number;
  location_id: string;
  location_name: string;
  timestamp: string;
  risk_level: string;
  risk_score: number;
  trigger_factors: any[];
  affected_infrastructure: string[];
  status: string;
  centroid_lat: number;
  centroid_lon: number;
  near_nh10: number;
}

// ---------------------------------------------------------------------------
// HELPERS
// ---------------------------------------------------------------------------
const RISK_DOT: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  moderate: 'bg-amber-500',
  low: 'bg-emerald-500',
};

function getRiskDot(level: string | undefined) {
  return RISK_DOT[level?.toLowerCase() || 'low'] || RISK_DOT.low;
}

// ---------------------------------------------------------------------------
// APP
// ---------------------------------------------------------------------------
export default function App() {
  const { state: regionState, setMode } = useRegion();
  const [activeView, setActiveView] = useState<'overview' | 'simulation' | 'warnings' | 'curator'>('overview');
  const [geoData, setGeoData] = useState<any>(null);
  const [statusData, setStatusData] = useState<GeoCell[]>([]);
  const [routeSafety, setRouteSafety] = useState<string>('UNKNOWN');
  const [nh10Route, setNh10Route] = useState<any[]>([]);
  const [warnings, setWarnings] = useState<Warning[]>([]);
  const [selectedCellId, setSelectedCellId] = useState<string | null>(null);
  const [useMapLibre, setUseMapLibre] = useState(false);
  const [simulationCells, setSimulationCells] = useState<GeoCell[]>([]);
  const [forecastData, setForecastData] = useState<any>(null);
  const [forecastHourIdx, setForecastHourIdx] = useState(0);
  const [pendingVerifications, setPendingVerifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [modelInfo, setModelInfo] = useState<any>(null);
  const [now, setNow] = useState(new Date());

  // Live clock
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const [geo, status, activeWarnings] = await Promise.all([
        rpcCall({ func: 'get_geo_data', args: { region_id: regionState.region } }),
        rpcCall({ func: 'get_latest_status', args: { region_id: regionState.region } }),
        rpcCall({ func: 'get_active_warnings', args: { region_id: regionState.region } }),
      ]);
      setGeoData(geo);
      setForecastData(null); // Clear forecast when region changes so it re-fetches
      setSelectedCellId(null); // Clear selected cell when region changes
      setUseMapLibre(false); // Always reset to 2D when switching region
      // Normalize: Nepal returns {cells, route_safety, nh10_route}, NER returns flat array
      if (status && Array.isArray(status)) {
        setStatusData(status);
        setRouteSafety('UNKNOWN');
      } else if (status && status.cells) {
        setStatusData(status.cells);
        setRouteSafety(status.route_safety || 'UNKNOWN');
        setNh10Route(status.nh10_route || []);
      }
      setWarnings(activeWarnings);
      setLoading(false);
    } catch (err) {
      console.error('[TERRAPULSE] Failed to fetch initial data', err);
      setLoading(false);
    }
  }, [regionState.region]);

  const fetchWarnings = useCallback(async () => {
    try {
      const w = await rpcCall({ func: 'get_active_warnings', args: { region_id: regionState.region } });
      setWarnings(w);
    } catch (err) {
      console.error('[TERRAPULSE] Failed to fetch warnings', err);
    }
  }, [regionState.region]);

  const fetchPendingVerifications = useCallback(async () => {
    try {
      const v = await rpcCall({ func: 'get_pending_verifications', args: { region_id: regionState.region } });
      setPendingVerifications(v);
    } catch (err) {
      console.error('[TERRAPULSE] Failed to fetch verifications', err);
    }
  }, [regionState.region]);

  const fetchModelInfo = useCallback(async () => {
    try {
      const info = await rpcCall({ func: 'get_model_info' });
      setModelInfo(info);
    } catch (err) {
      console.error('[TERRAPULSE] Failed to fetch model info', err);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    fetchModelInfo();
    console.log('[TERRAPULSE] Dashboard mounted â€” SIH 2026 TerraPulse.ai');
  }, [fetchAll, fetchModelInfo]);

  useEffect(() => {
    if (activeView === 'curator') fetchPendingVerifications();
  }, [activeView, fetchPendingVerifications]);

  // Fetch forecast data when tab is opened
  useEffect(() => {
    if (activeView === 'forecast' && !forecastData) {
      fetch(`http://localhost:5000/api/forecast?region_id=${regionState.region}`)
        .then(res => res.json())
        .then(data => setForecastData(data))
        .catch(err => console.error("Failed to fetch forecast:", err));
    }
  }, [activeView, forecastData]);

  // Merge simulation cells with base status
  const displayCells: GeoCell[] = activeView === 'forecast' && forecastData && forecastData.cells ? 
    statusData.map(cell => {
      const fCell = forecastData.cells.find((c: any) => c.cell_id === cell.location_id);
      if (fCell && fCell.predictions && fCell.predictions[forecastHourIdx]) {
        return { 
          ...cell, 
          risk_score: fCell.predictions[forecastHourIdx].risk_score,
          risk_level: fCell.predictions[forecastHourIdx].risk_level,
          rainfall_24h: fCell.predictions[forecastHourIdx].precipitation_mm
        };
      }
      return cell;
    })
    : statusData.map(cell => {
      const simCell = simulationCells.find(s => s.location_id === cell.location_id);
      return simCell ? { ...cell, ...simCell } : cell;
    });

  const selectedCell = displayCells.find(c => c.location_id === selectedCellId);
  const criticalCount = warnings.filter(w => w.risk_level === 'critical').length;
  const highCount = warnings.filter(w => w.risk_level === 'high').length;
  const avgRisk = displayCells.length
    ? displayCells.reduce((s, c) => s + (c.risk_score || 0), 0) / displayCells.length
    : 0;

  const navItems = [
    { id: 'overview' as const, label: 'Risk Map', icon: MapIcon },
    { id: 'forecast' as const, label: '24h Forecast', icon: Clock },
      { id: 'simulation' as const, label: 'Storm Simulator', icon: Zap },
    { id: 'warnings' as const, label: 'Early Warnings', icon: AlertTriangle, badge: warnings.length },
    { id: 'curator' as const, label: 'Curator', icon: ShieldCheck, badge: pendingVerifications.length },
  ];

  const handleSimulationUpdate = useCallback((cells: GeoCell[]) => {
    setSimulationCells(cells);
  }, []);

  const handleSimulationWarnings = useCallback((newWarnings: Warning[]) => {
    fetchWarnings();
  }, [fetchWarnings]);

  const approveVerification = async (id: number) => {
    try {
      await rpcCall({ func: 'approve_for_training', args: { verification_id: id } });
      fetchPendingVerifications();
    } catch (e) {
      console.error(e);
    }
  };

  // ---------------------------------------------------------------------------
  // RENDER
  return (
    <div className="flex h-screen flex-col md:flex-row bg-[#09090b] text-foreground selection:bg-primary/30 overflow-hidden">
      <aside className="hidden md:flex w-72 border-r border-border/40 flex-col flex-shrink-0">
        <div className="flex items-center gap-3 px-6 py-6 mb-2">
          <div className="h-10 w-10 rounded-xl bg-primary flex items-center justify-center flex-shrink-0">
            <Shield className="h-6 w-6 text-primary-foreground fill-current" />
          </div>
          <div>
            <h1 className="font-heading text-lg font-black leading-none tracking-tight text-white">
              TERRAPULSE
            </h1>
            <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest mt-1">
              LANDSLIDE WARNING
            </p>
          </div>
        </div>

        <Separator className="bg-border/30 mb-6 mx-6 w-auto" />

        <nav className="flex-1 px-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveView(item.id)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-3 rounded-md text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
                )}
              >
                <div className="flex items-center gap-3">
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <Badge 
                    variant={isActive ? "secondary" : "destructive"} 
                    className={cn(
                      "px-1.5 py-0 text-[10px] min-w-[20px] justify-center rounded-sm",
                      isActive && "bg-black/20 text-black hover:bg-black/20"
                    )}
                  >
                    {item.badge}
                  </Badge>
                )}
              </button>
            );
          })}
        </nav>
      </aside>

      {/* â”€â”€ MOBILE HEADER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 py-3 border-b border-border/40 bg-[#09090b]/95 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-primary flex items-center justify-center">
            <Shield className="h-4 w-4 text-primary-foreground fill-current" />
          </div>
          <span className="font-heading font-black text-sm text-white">
            TERRAPULSE
          </span>
        </div>
        <Button variant="ghost" size="icon" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
          {mobileMenuOpen ? <X className="h-5 w-5 text-white" /> : <Menu className="h-5 w-5 text-white" />}
        </Button>
      </div>

      {/* Mobile menu drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed top-[57px] left-0 right-0 z-40 bg-[#09090b]/98 backdrop-blur-md border-b border-border/40 p-4 space-y-1">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => { setActiveView(item.id); setMobileMenuOpen(false); }}
              className={cn(
                "w-full flex items-center justify-between rounded-md px-3 py-3 text-sm font-medium transition-all",
                activeView === item.id ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-muted/30 hover:text-white"
              )}
            >
              <div className="flex items-center gap-3">
                <item.icon className="h-4 w-4" />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <Badge variant={activeView === item.id ? "secondary" : "destructive"} className={cn("px-1.5 py-0 text-[10px] min-w-[20px] justify-center rounded-sm", activeView === item.id && "bg-black/20 text-black hover:bg-black/20")}>
                  {item.badge}
                </Badge>
              )}
            </button>
          ))}
        </div>
      )}

      {/* â”€â”€ MAIN CONTENT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <main className="flex-1 overflow-y-auto flex flex-col relative pt-[57px] md:pt-0">
        
        {/* Header from Screenshot */}
        <header className="flex items-center justify-between px-5 md:px-8 py-4 border-b border-border/20 flex-shrink-0">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3 text-[11px] font-bold tracking-widest text-muted-foreground uppercase min-w-[250px]">
              <span className={regionState.mode === 'case-study' ? 'text-amber-500' : 'text-primary'}>
                {regionState.mode === 'sih-demo' ? 'SIH DEMO - NER / INDIA' : 'REAL-WORLD CASE - NEPAL'}
              </span>
              <ChevronRight className="h-3 w-3" />
              <span className="text-white">{navItems.find(i => i.id === activeView)?.label}</span>
            </div>
            <div className="hidden lg:flex items-center ml-2 border border-border/30 bg-card/20 px-2 py-0.5 rounded text-[9px] font-mono tracking-widest text-muted-foreground uppercase">
              DATA MODE: {regionState.data_status}
            </div>
            
                        {/* Glassmorphism Mode Switcher */}
            <div className="hidden md:flex items-center bg-white/5 backdrop-blur-md border border-white/10 rounded-full p-1 ml-4">
              <button
                onClick={() => setMode('sih-demo')}
                className={`px-4 py-1.5 rounded-full text-xs font-bold tracking-wider transition-all duration-300 ${
                  regionState.mode === 'sih-demo' 
                    ? 'bg-primary text-black shadow-[0_0_15px_rgba(249,115,22,0.4)]' 
                    : 'text-muted-foreground hover:text-white hover:bg-white/5'
                }`}
              >
                SIH DEMO
              </button>
              <button
                onClick={() => setMode('case-study')}
                className={`px-4 py-1.5 rounded-full text-xs font-bold tracking-wider transition-all duration-300 ${
                  regionState.mode === 'case-study' 
                    ? 'bg-amber-500 text-black shadow-[0_0_15px_rgba(245,158,11,0.4)]' 
                    : 'text-muted-foreground hover:text-white hover:bg-white/5'
                }`}
              >
                NEPAL (LIVE)
              </button>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-5">
            <div className="text-right flex flex-col items-end">
              <div className="text-[11px] font-bold text-white tracking-widest">
                {now.toLocaleDateString('en-CA')}
              </div>
              <div className="text-[10px] text-muted-foreground flex items-center gap-1 mt-0.5 font-mono">
                <Clock className="h-3 w-3" />
                {now.toLocaleTimeString('en-US', { hour12: false })} UTC
              </div>
            </div>
            <Button variant="outline" size="icon" className="h-8 w-8 rounded-md hover:bg-muted/30 border-border/20 bg-card/10">
              <Settings className="h-4 w-4 text-muted-foreground" />
            </Button>
          </div>
        </header>

        {/* Content area */}
        <div className="flex-1 p-4 md:p-6 space-y-6 animate-in fade-in duration-400 pt-[70px] md:pt-4">

          {/* â”€â”€ OVERVIEW â€” Risk Map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {(activeView === 'overview' || activeView === 'forecast') && (
            <div className="space-y-6">
              {/* Stats bar */}
              {activeView === 'overview' && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  {
                    label: 'Monitored Zones', value: displayCells.length || '--',
                    icon: MapIcon, color: 'text-blue-400', bg: 'bg-blue-950/30',
                  },
                  {
                    label: 'Active Warnings', value: warnings.length,
                    icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-950/30',
                    badge: criticalCount > 0 ? `${criticalCount} Critical` : undefined,
                  },
                  {
                    label: 'Avg Risk Score', value: avgRisk.toFixed(1),
                    icon: Activity, color: 'text-amber-400', bg: 'bg-amber-950/30',
                  },
                  {
                    label: 'Model Status', value: modelInfo?.model_name?.split(' ')[0] || 'Loading',
                    icon: ShieldCheck, color: 'text-emerald-400', bg: 'bg-emerald-950/30',
                    sub: modelInfo?.accuracy ? `Acc: ${(modelInfo.accuracy * 100).toFixed(1)}%` : 'Candidate model',
                  },
                ].map((stat, i) => (
                  <Card key={i} className="bg-card/40 border-border/40 hover:border-primary/30 transition-all">
                    <CardContent className="p-5">
                      <div className="flex items-center justify-between">
                        <div className={cn("p-2 rounded-lg", stat.bg, stat.color)}>
                          <stat.icon className="h-5 w-5" />
                        </div>
                        {stat.badge && (
                          <Badge variant="destructive" className="text-[10px] font-bold uppercase tracking-wider">
                            {stat.badge}
                          </Badge>
                        )}
                      </div>
                      <div className="mt-3">
                        <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">{stat.label}</div>
                        <div className="text-2xl font-heading font-black mt-0.5 tracking-tight">{stat.value}</div>
                        {stat.sub && <div className="text-[10px] text-muted-foreground mt-0.5">{stat.sub}</div>}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
              )}

              {/* Map + Detail Panel */}
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                {/* Map takes 2/3 */}
                <div className="xl:col-span-2 lg:h-[600px] min-h-[480px]">
                  {loading ? (
                    <Card className="h-full border-border/40 bg-card/40 flex items-center justify-center min-h-[480px]">
                      <div className="text-center space-y-3 text-muted-foreground">
                        <Activity className="h-8 w-8 animate-spin mx-auto opacity-30" />
                        <p className="text-sm">Loading geographic data...</p>
                      </div>
                    </Card>
                  ) : (
                    <div className="relative h-full w-full">
                    <div className="absolute bottom-6 left-6 z-[999] group">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => setUseMapLibre(!useMapLibre)}
                        className="bg-black/70 backdrop-blur h-8 w-8 p-0 flex items-center justify-center border-white/20 overflow-hidden transition-all duration-300 hover:w-auto hover:px-3"
                      >
                        {useMapLibre ? (
                          <>
                            <Layers className="h-4 w-4 shrink-0 text-slate-300" />
                            <span className="hidden group-hover:inline-block ml-2 text-[10px] whitespace-nowrap">Switch to 2D Fallback</span>
                          </>
                        ) : (
                          <>
                            <Globe className="h-4 w-4 shrink-0 text-teal-400" />
                            <span className="hidden group-hover:inline-block ml-2 text-[10px] whitespace-nowrap">Switch to 3D Engine</span>
                          </>
                        )}
                      </Button>
                    </div>
                    {useMapLibre ? (
                      <GeospatialViewer
                        cells={displayCells}
              routeSafety={routeSafety}
                        historicalEvents={geoData?.historical_landslides || geoData?.historical_events || []}
                        nh10Route={nh10Route || geoData?.nh10_route || (geoData?.infrastructure?.highways?.[0]?.route) || []}
                        onCellClick={(cell) => setSelectedCellId(cell.location_id)}
                        initialSelectedCellId={selectedCellId}
                      />
                    ) : (
                      <LandslideMap
                        cells={displayCells}
                        routeSafety={routeSafety}
                        nh10Route={nh10Route || geoData?.nh10_route || (geoData?.infrastructure?.highways?.[0]?.route) || []}
                        historicalLandslides={geoData?.historical_landslides || geoData?.historical_events || []}
                        selectedCellId={selectedCellId}
                        onCellSelect={(id) => {
                          setSelectedCellId(id);
                        }}
                        simulationCells={simulationCells}
                      />
                    )}
                  </div>
                  )}
                </div>

                {/* Right: XAI Panel or select prompt */}
                <div className="xl:col-span-1 lg:h-[600px]">

                  {selectedCell ? (
                    <Card className="h-full bg-card/60 backdrop-blur-sm border-border/40 overflow-hidden">
                      <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-sm font-bold uppercase tracking-widest">Cell Analysis</CardTitle>
                          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setSelectedCellId(null)}>
                            <X className="h-3.5 w-3.5 mr-1" /> Clear
                          </Button>
                        </div>
                      </CardHeader>
                      <CardContent className="overflow-y-auto max-h-[560px]">
                        <XAIPanel
                          locationName={selectedCell.name}
                          riskLevel={selectedCell.risk_level || 'low'}
                          riskScore={selectedCell.risk_score || 0}
                          contributingFactors={selectedCell.contributing_factors || []}
                          slopeAngle={selectedCell.slope_angle}
                          elevation={selectedCell.elevation_m}
                          soilType={selectedCell.soil_type}
                          nearNH10={selectedCell.near_nh10}
                          historicalCount={selectedCell.historical_count}
                        />
                      </CardContent>
                    </Card>
                  ) : (
                    <Card className="h-full border-2 border-dashed border-border/40 bg-muted/10 flex items-center justify-center min-h-[300px]">
                      <div className="text-center space-y-4 p-8">
                        <div className="h-16 w-16 rounded-full bg-primary/5 flex items-center justify-center text-primary/30 mx-auto">
                          <MapIcon className="h-8 w-8" />
                        </div>
                        <div>
                          <h3 className="font-heading text-base font-bold">Select a Zone</h3>
                          <p className="text-xs text-muted-foreground mt-1 max-w-[200px]">
                            Click any coloured cell on the map to view the XAI risk breakdown
                          </p>
                        </div>
                        {/* Quick zone shortcuts */}
                        <div className="flex flex-wrap gap-2 justify-center">
                          {displayCells.filter(c => c.risk_level === 'high' || c.risk_level === 'critical').slice(0, 3).map(cell => (
                            <Button
                              key={cell.location_id}
                              variant="outline"
                              size="sm"
                              className="text-xs h-7 border-border/40"
                              onClick={() => setSelectedCellId(cell.location_id)}
                            >
                              {cell.name.split(' ').slice(-1)[0]}
                            </Button>
                          ))}
                        </div>
                      </div>
                    </Card>
                  )}
                </div>
              </div>

              {activeView === 'forecast' && (
                <div className="mt-6 w-full">
                  <ForecastDashboard 
                    forecastData={forecastData}
                    onTimeScrub={setForecastHourIdx}
                    currentHourIndex={forecastHourIdx}
                    displayCells={displayCells}
                  />
                </div>
              )}

              {/* Historical Landslide Inventory Strip */}
              {activeView === 'overview' && (geoData?.historical_landslides || geoData?.historical_events)?.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                    <Info className="h-3.5 w-3.5" />
                    Historical Landslide Inventory (Reference â€” GSI/ISRO NER Records)
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {(geoData.historical_landslides || geoData.historical_events || []).slice(0, 3).map((ls: any) => (
                      <div key={ls.id} className="rounded-xl border border-border/30 bg-card/40 p-3 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <Badge variant="outline" className="text-[10px] font-mono">{ls.id}</Badge>
                          <span className="text-[10px] text-muted-foreground font-mono">{ls.date}</span>
                        </div>
                        <div className="text-xs font-bold">{ls.type}</div>
                        <div className="text-[11px] text-muted-foreground leading-relaxed">{ls.impact}</div>
                        <div className="text-[10px] text-blue-400/80">
                          {ls.lat.toFixed(3)}Â°N, {ls.lon.toFixed(3)}Â°E
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* â”€â”€ SIMULATION VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}


          {activeView === 'simulation' && (
            <StormSimulator
              onSimulationUpdate={handleSimulationUpdate}
              onWarningsUpdate={handleSimulationWarnings}
            />
          )}

          {/* â”€â”€ WARNINGS VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          {activeView === 'warnings' && (
            <div className="space-y-5">
              <div>
                <h2 className="font-heading text-xl font-bold">Early Warning Board</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Active landslide early warnings Â· Acknowledge â†’ Field Verification â†’ Curator Approval
                </p>
              </div>
              <WarningsPanel warnings={warnings} onResolved={fetchWarnings} />
            </div>
          )}

          {/* â”€â”€ CURATOR VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          
          {/* EVENT REPLAY */}
          {activeView === 'replay' && (
            <EventReplay />
          )}

          {activeView === 'curator' && (
            <div className="space-y-5">
              <div>
                <h2 className="font-heading text-xl font-bold">Human-in-the-Loop Curator</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Review field verifications before approving them for the ML training dataset
                </p>
              </div>

              {pendingVerifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 space-y-4 text-muted-foreground">
                  <div className="h-20 w-20 rounded-full bg-muted/30 flex items-center justify-center">
                    <ShieldCheck className="h-10 w-10 opacity-20" />
                  </div>
                  <p className="text-sm font-medium">No pending verifications</p>
                  <p className="text-xs text-center max-w-xs">
                    When field officers submit verifications from the Warnings board, they appear here for curator review.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {pendingVerifications.map(v => (
                    <Card key={v.id} className="border-border/40 bg-card/40">
                      <CardContent className="p-5 space-y-3">
                        <div className="flex items-start justify-between flex-wrap gap-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="text-[10px] font-mono">VER-{v.id}</Badge>
                              <Badge
                                variant={v.outcome === 'confirmed' ? 'destructive' : 'secondary'}
                                className="text-[10px] font-bold"
                              >
                                {v.outcome === 'confirmed' ? 'ðŸ”´ Confirmed' : 'ðŸŸ¢ False Alarm'}
                              </Badge>
                            </div>
                            <div className="font-bold">{v.location_name}</div>
                            <div className="text-xs text-muted-foreground">
                              Verified by: <strong>{v.verified_by}</strong> Â· {new Date(v.reported_at).toLocaleString()}
                            </div>
                          </div>
                          <Button
                            size="sm"
                            className="font-bold"
                            onClick={() => approveVerification(v.id)}
                          >
                            <ShieldCheck className="h-4 w-4 mr-1.5" />
                            Approve for Training
                          </Button>
                        </div>
                        {v.field_notes && (
                          <div className="rounded-lg bg-muted/30 p-3 text-xs text-muted-foreground italic border border-border/30">
                            "{v.field_notes}"
                          </div>
                        )}
                        <div className="text-[10px] text-muted-foreground/60">
                          Warning #{v.warning_id} Â· Risk Level: {v.risk_level} Â· Score: {v.risk_score?.toFixed(1)}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              {/* Curator process info */}
              <Card className="border-border/30 bg-muted/10">
                <CardContent className="p-4 space-y-3">
                  <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                    Why Curator Approval?
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    In production ML systems, unvalidated field reports can corrupt the training dataset.
                    The curator stage ensures a senior scientist reviews each field report before it enters
                    the training buffer â€” preventing noisy, incorrect, or politically-motivated false data
                    from degrading model performance.
                  </p>
                  <div className="text-[10px] text-muted-foreground/60">
                    This mirrors the <strong>Human-in-the-Loop (HITL)</strong> pattern recommended by 
                    Google, ISRO, and NDMA for AI systems in critical safety applications.
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </main>

      {/* â”€â”€ MOBILE BOTTOM NAV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 border-t border-border/40 bg-background/95 backdrop-blur-lg flex justify-around py-2 z-50">
        {navItems.map(item => (
          <button
            key={item.id}
            onClick={() => { setActiveView(item.id); setMobileMenuOpen(false); }}
            className={cn(
              "flex flex-col items-center gap-1 px-3 py-1 text-[10px] font-bold uppercase tracking-widest relative",
              activeView === item.id ? "text-primary" : "text-muted-foreground"
            )}
          >
            <item.icon className="h-5 w-5" />
            {item.label.split(' ')[0]}
            {item.badge !== undefined && item.badge > 0 && (
              <span className="absolute -top-0.5 right-2 h-4 w-4 rounded-full bg-destructive text-destructive-foreground text-[9px] font-black flex items-center justify-center">
                {item.badge}
              </span>
            )}
          </button>
        ))}
      </nav>
    </div>
  );
}

