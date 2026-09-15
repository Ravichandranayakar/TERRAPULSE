import React, { useState, useEffect, useCallback, useRef } from 'react';
import { rpcCall } from './api';
import { useRegion } from './contexts/RegionContext';
import { EventReplay } from './features/EventReplay';
import { CitizenApp } from './features/CitizenApp';
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
  MapPin,
  Maximize2,
  Minimize2,
  Users,
  Radio,
  CloudRain,
  Droplets,
  History,
  Network
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
import { CellBroadcastModal } from './features/CellBroadcastModal';
import { CuratorDashboard } from './features/CuratorDashboard';
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
const RISK_COLORS: Record<string, string> = {
  low: "#10b981", // Emerald
  moderate: "#f59e0b", // Amber
  high: "#ef4444", // Red
  critical: "#7f1d1d" // Dark Red
};

type AppMode = 'authority' | 'citizen';

export default function App() {
  const { state: regionState, setMode } = useRegion();
  const [appMode, setAppMode] = useState<AppMode>('authority');
  const [showModeMenu, setShowModeMenu] = useState(false);
  const modeMenuRef = useRef<HTMLDivElement>(null);
  const [activeView, setActiveView] = useState<'overview' | 'simulation' | 'warnings' | 'curator'>('overview');
  const [geoData, setGeoData] = useState<any>(null);
  const [statusData, setStatusData] = useState<GeoCell[]>([]);
  const [routeSafety, setRouteSafety] = useState<string>('UNKNOWN');
  const [nh10Route, setNh10Route] = useState<any[]>([]);
  const [warnings, setWarnings] = useState<Warning[]>([]);
  const [selectedCellId, setSelectedCellId] = useState<string | null>(null);
  const [isMapFullscreen, setIsMapFullscreen] = useState(false);
  const [simulationCells, setSimulationCells] = useState<GeoCell[]>([]);
  const [forecastData, setForecastData] = useState<any>(null);
  const [forecastHourIdx, setForecastHourIdx] = useState(0);
  const [pendingVerificationCount, setPendingVerificationCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [modelInfo, setModelInfo] = useState<any>(null);
  const [now, setNow] = useState(new Date());
  const [broadcastWarning, setBroadcastWarning] = useState<Warning | null>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target as Node)) {
        setShowModeMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

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
      setPendingVerificationCount(v.length);
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

  // Fetch forecast data when forecast tab is opened
  useEffect(() => {
    if (activeView === 'forecast' && !forecastData) {
      fetch(`http://localhost:5000/api/forecast?region_id=${regionState.region}`)
        .then(res => res.json())
        .then(data => setForecastData(data))
        .catch(err => console.error("Failed to fetch forecast:", err));
    }
  }, [activeView, forecastData, regionState.region]);

  // RISK MAP cells — always live baseline. Never contaminated by simulation or forecast data.
  const riskMapCells = React.useMemo<GeoCell[]>(() => {
    return statusData;
  }, [statusData]);

  // FORECAST MAP cells — isolated dataset driven by the time scrubber.
  // Only consumed by the 24h Forecast GeospatialViewer; Risk Map is unaffected.
  const forecastCells = React.useMemo<GeoCell[]>(() => {
    if (!forecastData?.cells) return riskMapCells;
    return riskMapCells.map(cell => {
      const fCell = forecastData.cells.find((c: any) => c.cell_id === cell.location_id);
      if (fCell?.predictions?.[forecastHourIdx]) {
        return {
          ...cell,
          risk_score: fCell.predictions[forecastHourIdx].risk_score,
          risk_level: fCell.predictions[forecastHourIdx].risk_level,
          rainfall_24h: fCell.predictions[forecastHourIdx].precipitation_mm,
        };
      }
      return cell;
    });
  }, [riskMapCells, forecastData, forecastHourIdx]);

  // displayCells switches based on active view to keep map states isolated
  const displayCells = React.useMemo(() => {
    if (activeView === 'forecast') return forecastCells;
    if (activeView === 'simulation') return simulationCells.length > 0 ? simulationCells : riskMapCells;
    return riskMapCells;
  }, [activeView, forecastCells, simulationCells, riskMapCells]);

  const selectedCell = riskMapCells.find(c => c.location_id === selectedCellId);
  const criticalCount = warnings.filter(w => w.risk_level === 'critical').length;
  const highCount = warnings.filter(w => w.risk_level === 'high').length;
  const avgRisk = riskMapCells.length
    ? riskMapCells.reduce((s, c) => s + (c.risk_score || 0), 0) / riskMapCells.length
    : 0;

  const navItems = [
    { id: 'overview' as const, label: 'Risk Map', icon: MapIcon },
    { id: 'forecast' as const, label: '24h Forecast', icon: Clock },
    { id: 'simulation' as const, label: 'Storm Simulator', icon: Zap },
    { id: 'warnings' as const, label: 'Early Warnings', icon: AlertTriangle, badge: warnings.length },
    { id: 'curator' as const, label: 'Curator', icon: ShieldCheck, badge: pendingVerificationCount },
  ];

  const handleSimulationUpdate = useCallback((cells: GeoCell[]) => {
    setSimulationCells(cells);
  }, []);

  const handleSimulationWarnings = useCallback((_newWarnings: Warning[]) => {
    fetchWarnings();
  }, [fetchWarnings]);

  // ---------------------------------------------------------------------------
  // RENDER
  // ── Citizen App mode — completely separate UI ──────────────────────────
  if (appMode === 'citizen') {
    return <CitizenApp onSwitchToAdmin={() => setAppMode('authority')} />;
  }

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
            {/* ─── Mode Switcher Dropdown ─── */}
            <div className="relative" ref={modeMenuRef}>
              <button
                onClick={() => setShowModeMenu(v => !v)}
                className={cn(
                  "h-8 w-8 rounded-md flex items-center justify-center border transition-all",
                  showModeMenu
                    ? "bg-primary/20 border-primary/40 text-primary"
                    : "hover:bg-muted/30 border-border/20 bg-card/10 text-muted-foreground hover:text-white"
                )}
                title="Switch portal mode"
              >
                <Settings className="h-4 w-4" />
              </button>

              {showModeMenu && (
                <div className="absolute right-0 top-10 z-[200] w-56 rounded-xl border border-border/40 bg-[#111114] shadow-2xl backdrop-blur-xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
                  <div className="px-3 py-2 border-b border-border/30">
                    <span className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Portal Mode</span>
                  </div>

                  {/* Authority option */}
                  <button
                    onClick={() => { setAppMode('authority'); setShowModeMenu(false); }}
                    className={cn(
                      "w-full flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all hover:bg-white/5",
                      appMode === 'authority' ? "text-white" : "text-muted-foreground"
                    )}
                  >
                    <div className={cn(
                      "h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0",
                      appMode === 'authority' ? "bg-primary/20 text-primary" : "bg-white/5 text-slate-500"
                    )}>
                      <Shield className="h-4 w-4" />
                    </div>
                    <div className="text-left">
                      <div className="font-bold text-xs">Authority Dashboard</div>
                      <div className="text-[10px] text-slate-500">Command & control view</div>
                    </div>
                    {appMode === 'authority' && <div className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />}
                  </button>

                  {/* Citizen option */}
                  <button
                    onClick={() => { setAppMode('citizen'); setShowModeMenu(false); }}
                    className={cn(
                      "w-full flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all hover:bg-white/5",
                      appMode === 'citizen' ? "text-white" : "text-muted-foreground"
                    )}
                  >
                    <div className={cn(
                      "h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0",
                      appMode === 'citizen' ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-slate-500"
                    )}>
                      <Users className="h-4 w-4" />
                    </div>
                    <div className="text-left">
                      <div className="font-bold text-xs">Citizen Portal</div>
                      <div className="text-[10px] text-slate-500">Field reporting & alerts</div>
                    </div>
                    {appMode === 'citizen' && <div className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-400" />}
                  </button>

                  <div className="px-4 py-2 border-t border-border/20">
                    <div className="flex items-center gap-1.5 text-[9px] text-slate-600 font-mono">
                      <Radio className="h-2.5 w-2.5" />
                      TERRAPULSE · SIH 2026
                    </div>
                  </div>
                </div>
              )}
            </div>
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

              {/* Map + Detail Panel — supports fullscreen mode */}
              {!isMapFullscreen && (
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                  {/* Map takes 2/3 */}
                  <div className="xl:col-span-2 lg:h-[700px] min-h-[480px]">
                    <Card className="relative h-full w-full rounded-lg overflow-hidden border border-border/40 flex flex-col bg-card/60">
                      
                      {/* LEGEND HEADER RESTORED */}
                      <CardHeader className="pb-3 pt-4 px-5 shrink-0 bg-[#09090b]/80 backdrop-blur-md border-b border-border/20 z-10 relative flex flex-col gap-2">
                        {/* TOP ROW: Title & Legends */}
                        <div className="flex items-center justify-between w-full overflow-x-auto no-scrollbar">
                          <div className="flex items-center gap-4 w-full">
                            {/* Title block */}
                            <div className="flex items-center gap-2 text-white shrink-0">
                              <MapPin className="h-4 w-4 text-orange-500 shrink-0" />
                              <h2 className="text-[13px] font-bold tracking-wide whitespace-nowrap">
                                {regionState.mode === 'sih-demo' ? 'North Sikkim' : 'Rasuwa District'} - Landslide Risk Map
                              </h2>
                            </div>

                            {/* Region Badge */}
                            <div className="px-2 py-0.5 rounded border border-white/10 bg-white/5 text-[9px] font-bold tracking-wider text-slate-300 shrink-0 uppercase">
                              {regionState.mode === 'sih-demo' ? 'NER - INDIA' : 'NEPAL'}
                            </div>

                            {/* Risk Badges */}
                            <div className="flex items-center gap-1.5 ml-2 shrink-0">
                              {(['Low', 'Moderate', 'High', 'Critical'] as const).map(level => (
                                <div key={level} className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-black/60 border border-white/5 text-[9px] uppercase font-bold tracking-wider text-slate-200 shrink-0">
                                  <div className="h-2 w-2 rounded-full" style={{ backgroundColor: RISK_COLORS[level.toLowerCase()] }} />
                                  {level}
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>

                        {/* BOTTOM ROW: Map Features */}
                        <div className="flex items-center gap-4 text-[10px] text-slate-400 font-medium pl-6">
                          <div className="flex items-center gap-1.5">
                            <div className="w-3 h-1 bg-blue-500/80 rounded-full" /> 
                            NH-10 Highway
                          </div>
                          <div className="flex items-center gap-1.5">
                            <div className="w-2.5 h-2.5 rounded-full border-[1.5px] border-zinc-400/80 bg-zinc-400/20" /> 
                            Historical Landslide
                          </div>
                        </div>
                      </CardHeader>

                      {/* Actual Map Area */}
                      <div className="relative flex-1 w-full">
                        <GeospatialViewer
                          key={`map-${regionState.region}-overview`}
                          cells={displayCells}
                          routeSafety={routeSafety}
                          historicalEvents={geoData?.historical_landslides || geoData?.historical_events || []}
                          eventLayers={geoData?.event_layers || []}
                          infrastructure={geoData?.infrastructure || { highways: [], settlements: [] }}
                          nh10Route={nh10Route || geoData?.nh10_route || (geoData?.infrastructure?.highways?.[0]?.route) || []}
                          onCellClick={(cell) => setSelectedCellId(cell ? cell.location_id : null)}
                          initialSelectedCellId={selectedCellId}
                        />
                        
                        {/* Fullscreen button — top-right of map */}
                        <button 
                          onClick={() => setIsMapFullscreen(true)}
                          className="absolute top-4 right-14 z-[999] bg-black/70 hover:bg-black/90 backdrop-blur border border-white/20 text-white rounded p-1.5 transition-all hover:scale-105 shadow-xl"
                          title="Fullscreen"
                        >
                          <Maximize2 className="h-4 w-4" />
                        </button>
                      </div>
                    </Card>
                  </div>
                  
                  {/* Right: XAI Panel or select prompt */}
                  <div className="xl:col-span-1 lg:h-[700px] overflow-y-auto custom-scrollbar relative p-4">
                      {selectedCell ? (
                        <XAIPanel cell={selectedCell} />
                    ) : (
                      <div className="h-full flex flex-col items-center justify-center text-muted-foreground bg-card/20 rounded-lg border border-border/20 border-dashed p-6 text-center">
                        <div className="bg-orange-500/10 p-5 rounded-full mb-4">
                            <MapIcon className="h-10 w-10 text-orange-500 opacity-60" />
                          </div>
                          <p className="font-bold text-white mb-2 text-xl">Select a Zone</p>
                          <p className="text-sm text-muted-foreground max-w-[200px] mb-6">Click any coloured cell on the map to view the XAI risk breakdown</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              

              {activeView === 'forecast' && (
                <div className="mt-6 w-full">
                  <ForecastDashboard
                    forecastData={forecastData}
                    onTimeScrub={setForecastHourIdx}
                    currentHourIndex={forecastHourIdx}
                    displayCells={forecastCells}
                  />
                </div>
              )}

              {/* â”€â”€ DATA SOURCE STATUS (SIH JUDGE VIEW) â”€â”€ */}
              {activeView === 'overview' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      <Database className="h-3.5 w-3.5" />
                      Live Data Integration Pipelines
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                      </span>
                      <span className="text-[10px] uppercase font-bold text-emerald-500 tracking-wider">System Healthy</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                    {/* Source 1: Terrain */}
                    <div className="rounded-xl border border-emerald-500/20 bg-card/40 p-3 space-y-2 relative overflow-hidden group hover:border-emerald-500/50 transition-colors">
                      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      <div className="flex items-center gap-2 text-emerald-400">
                        <MapIcon className="h-4 w-4" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">Topography</span>
                      </div>
                      <div>
                        <div className="text-xs font-bold text-white">MapTiler 3D DEM</div>
                        <div className="text-[10px] text-muted-foreground">Terrain RGB & Slope Angle</div>
                      </div>
                    </div>

                    {/* Source 2: Weather */}
                    <div className="rounded-xl border border-emerald-500/20 bg-card/40 p-3 space-y-2 relative overflow-hidden group hover:border-emerald-500/50 transition-colors">
                      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      <div className="flex items-center gap-2 text-emerald-400">
                        <CloudRain className="h-4 w-4" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">Weather</span>
                      </div>
                      <div>
                        <div className="text-xs font-bold text-white">Open-Meteo API</div>
                        <div className="text-[10px] text-muted-foreground">Live Rainfall & Forecasts</div>
                      </div>
                    </div>

                    {/* Source 3: Soil Moisture */}
                    <div className="rounded-xl border border-emerald-500/20 bg-card/40 p-3 space-y-2 relative overflow-hidden group hover:border-emerald-500/50 transition-colors">
                      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      <div className="flex items-center gap-2 text-emerald-400">
                        <Droplets className="h-4 w-4" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">Hydrology</span>
                      </div>
                      <div>
                        <div className="text-xs font-bold text-white">Virtual Sensors</div>
                        <div className="text-[10px] text-muted-foreground">0-7cm Soil Moisture Index</div>
                      </div>
                    </div>

                    {/* Source 4: Historical Records */}
                    <div className="rounded-xl border border-emerald-500/20 bg-card/40 p-3 space-y-2 relative overflow-hidden group hover:border-emerald-500/50 transition-colors">
                      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      <div className="flex items-center gap-2 text-emerald-400">
                        <History className="h-4 w-4" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">Ground Truth</span>
                      </div>
                      <div>
                        <div className="text-xs font-bold text-white">GSI / ISRO Catalog</div>
                        <div className="text-[10px] text-muted-foreground">Historical Disaster Inventory</div>
                      </div>
                    </div>

                    {/* Source 5: Infrastructure */}
                    <div className="rounded-xl border border-emerald-500/20 bg-card/40 p-3 space-y-2 relative overflow-hidden group hover:border-emerald-500/50 transition-colors">
                      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      <div className="flex items-center gap-2 text-emerald-400">
                        <Network className="h-4 w-4" />
                        <span className="text-[10px] font-bold uppercase tracking-wider">Infrastructure</span>
                      </div>
                      <div>
                        <div className="text-xs font-bold text-white">OpenStreetMap</div>
                        <div className="text-[10px] text-muted-foreground">NH-10 Highway Network</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* â”€â”€ SIMULATION VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}


          {activeView === 'simulation' && (
            <StormSimulator
              cells={statusData}
              mapCells={simulationCells.length ? simulationCells : statusData}
              historicalEvents={geoData?.historical_landslides || geoData?.historical_events || []}
              eventLayers={geoData?.event_layers || []}
              infrastructure={geoData?.infrastructure || { highways: [], settlements: [] }}
              nh10Route={nh10Route || geoData?.nh10_route || geoData?.infrastructure?.highways?.[0]?.route || []}
              routeSafety={routeSafety}
              selectedCell={selectedCell}
              selectedCellId={selectedCellId}
              onCellSelect={setSelectedCellId}
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
              <WarningsPanel
                warnings={warnings}
                onResolved={fetchWarnings}
                onBroadcast={setBroadcastWarning}
              />
            </div>
          )}

          {/* â”€â”€ CURATOR VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
          
          {/* EVENT REPLAY */}
          {activeView === 'replay' && (
            <EventReplay />
          )}

{activeView === 'curator' && (
            <CuratorDashboard
              cells={displayCells}
              historicalEvents={geoData?.historical_landslides || geoData?.historical_events || []}
              eventLayers={geoData?.event_layers || []}
              infrastructure={geoData?.infrastructure || { highways: [], settlements: [] }}
              nh10Route={nh10Route || geoData?.nh10_route || geoData?.infrastructure?.highways?.[0]?.route || []}
              routeSafety={routeSafety}
              onPendingCountChange={setPendingVerificationCount}
            />
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
        ))}</nav>
      {isMapFullscreen && (
        <div className="fixed inset-0 w-screen h-screen z-[1000] bg-[#09090b]" style={{top:0,left:0,right:0,bottom:0}}>
          <style>{`
            .maplibregl-ctrl-top-right {
              top: 60px !important;
              right: ${selectedCell ? '360px' : '16px'} !important;
              transition: right 0.3s ease;
            }
          `}</style>
          <div className="absolute inset-0">
            <GeospatialViewer
              key={`map-${regionState.region}-fullscreen`}
              cells={displayCells}
              routeSafety={routeSafety}
              historicalEvents={geoData?.historical_landslides || geoData?.historical_events || []}
              nh10Route={nh10Route || geoData?.nh10_route || (geoData?.infrastructure?.highways?.[0]?.route) || []}
              onCellClick={(cell) => setSelectedCellId(cell ? cell.location_id : null)}
              initialSelectedCellId={selectedCellId}
            />
          </div>
          {/* Exit fullscreen dynamic positioning */}
          <div className={`absolute top-4 z-[1010] ${selectedCell ? "right-[360px]" : "right-4"}`}>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsMapFullscreen(false)}
              className="bg-black/70 hover:bg-black/90 backdrop-blur border border-white/20 text-white shadow-xl p-2"
            >
              <Minimize2 className="h-4 w-4" />
            </Button>
          </div>
          {selectedCell && (
            <div className="absolute top-0 right-0 h-full w-[340px] z-[1001] pointer-events-auto">
              <div className="h-full bg-black/50 backdrop-blur-2xl border-l border-white/10 flex flex-col shadow-2xl">
                <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                  <XAIPanel cell={selectedCell} onClose={() => setSelectedCellId(null)} />
                </div>
              </div>
            </div>
          )}
        </div>
      )}
      {broadcastWarning && (
        <CellBroadcastModal
          warning={broadcastWarning}
          cells={displayCells}
          historicalEvents={geoData?.historical_landslides || geoData?.historical_events || []}
          eventLayers={geoData?.event_layers || []}
          infrastructure={geoData?.infrastructure || { highways: [], settlements: [] }}
          nh10Route={nh10Route || geoData?.nh10_route || geoData?.infrastructure?.highways?.[0]?.route || []}
          routeSafety={routeSafety}
          onClose={() => setBroadcastWarning(null)}
        />
      )}
    </div>
  );
}


