/**
 * CitizenApp.tsx — TerraPulse Citizen & Field Reporter Portal
 *
 * Ground-truth layer of the Risk Intelligence Fusion architecture.
 * Clean, mobile-first, user-friendly design.
 */

import React, { useState, useRef, useEffect } from 'react';
import {
  Camera,
  MapPin,
  AlertTriangle,
  ChevronRight,
  Send,
  Clock,
  CheckCircle2,
  Radio,
  Navigation,
  X,
  FileText,
  Phone,
  Shield,
  Wifi,
  WifiOff,
  Upload,
  Eye,
  ArrowLeft,
  Users,
  Mountain,
  Droplets,
  Truck,
  Zap,
  Home,
  Settings,
} from 'lucide-react';
import { rpcCall } from '../api';
import { useRegion } from '../contexts/RegionContext';
import { cn } from '../lib/utils';

// ---------------------------------------------------------------------------
// TYPES
// ---------------------------------------------------------------------------
type ReportType = 'landslide' | 'road_crack' | 'flooding' | 'slope_movement' | 'blocked_road' | 'infrastructure_damage';
type ReportStatus = 'pending' | 'under_review' | 'verified' | 'false_alarm';

interface Report {
  id: string;
  type: ReportType;
  description: string;
  lat: number;
  lon: number;
  timestamp: string;
  status: ReportStatus;
  zone_name?: string;
  risk_level?: string;
  photo?: string;
}

// ---------------------------------------------------------------------------
// CONSTANTS — neutral, friendly icons & colors (not all red!)
// ---------------------------------------------------------------------------
const REPORT_TYPES: { id: ReportType; label: string; icon: React.ComponentType<any>; accent: string; bg: string; }[] = [
  { id: 'landslide',            label: 'Landslide',       icon: Mountain,  accent: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/25' },
  { id: 'road_crack',           label: 'Road Crack',      icon: Zap,       accent: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/25' },
  { id: 'slope_movement',       label: 'Slope Movement',  icon: Mountain,  accent: 'text-amber-400',  bg: 'bg-amber-500/10  border-amber-500/25'  },
  { id: 'flooding',             label: 'Flooding',        icon: Droplets,  accent: 'text-blue-400',   bg: 'bg-blue-500/10   border-blue-500/25'   },
  { id: 'blocked_road',         label: 'Blocked Road',    icon: Truck,     accent: 'text-slate-400',  bg: 'bg-slate-500/10  border-slate-500/25'  },
  { id: 'infrastructure_damage',label: 'Infrastructure',  icon: Home,      accent: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/25' },
];

// Risk level — subtle palette, no blazing full-screen red
const RISK_CONFIG: Record<string, { pill: string; bar: string; label: string }> = {
  critical: { pill: 'bg-red-500/15 text-red-300 border-red-500/30',    bar: 'bg-red-500',    label: 'Critical' },
  high:     { pill: 'bg-orange-500/15 text-orange-300 border-orange-500/30', bar: 'bg-orange-400', label: 'High' },
  moderate: { pill: 'bg-amber-500/15 text-amber-300 border-amber-500/30',   bar: 'bg-amber-400',  label: 'Moderate' },
  low:      { pill: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', bar: 'bg-emerald-400', label: 'Low' },
};

const STATUS_STYLE: Record<ReportStatus, string> = {
  pending:      'bg-amber-500/15 text-amber-300 border-amber-500/25',
  under_review: 'bg-blue-500/15 text-blue-300 border-blue-500/25',
  verified:     'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
  false_alarm:  'bg-slate-500/15 text-slate-400 border-slate-500/25',
};

// ---------------------------------------------------------------------------
// COMPONENT
// ---------------------------------------------------------------------------
interface CitizenAppProps {
  onSwitchToAdmin: () => void;
}

type Screen = 'home' | 'report' | 'my_reports' | 'emergency';

export function CitizenApp({ onSwitchToAdmin }: CitizenAppProps) {
  const { state: regionState } = useRegion();

  const [screen, setScreen]     = useState<Screen>('home');
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  const [gps, setGps]           = useState<{ lat: number; lon: number } | null>(null);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [gpsError, setGpsError] = useState('');
  const [nearbyZone, setNearbyZone] = useState<any>(null);

  const [selectedType, setSelectedType] = useState<ReportType | null>(null);
  const [description, setDescription]   = useState('');
  const [photo, setPhoto]               = useState<string | null>(null);
  const [reporterName, setReporterName] = useState('');
  const [submitting, setSubmitting]     = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const [myReports, setMyReports] = useState<Report[]>(() => {
    try { return JSON.parse(sessionStorage.getItem('citizen_reports') || '[]'); }
    catch { return []; }
  });

  const [showModeMenu, setShowModeMenu] = useState(false);
  const modeMenuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target as Node)) {
        setShowModeMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  useEffect(() => {
    const on  = () => setIsOnline(true);
    const off = () => setIsOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);

  useEffect(() => { acquireGPS(); }, []);

  // ── GPS ──────────────────────────────────────────────────────────────────
  function acquireGPS() {
    if (!navigator.geolocation) { setGpsError('Geolocation not supported.'); return; }
    setGpsLoading(true); setGpsError('');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const loc = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        setGps(loc); setGpsLoading(false); fetchNearbyZone(loc);
      },
      () => {
        const fallback = regionState.mode === 'case-study'
          ? { lat: 28.0, lon: 85.2 }
          : { lat: 27.6, lon: 88.4 };
        setGps(fallback); setGpsLoading(false);
        setGpsError('Using approximate location (GPS unavailable).');
        fetchNearbyZone(fallback);
      },
      { timeout: 8000, maximumAge: 60000 }
    );
  }

  async function fetchNearbyZone(loc: { lat: number; lon: number }) {
    try {
      const status = await rpcCall({ func: 'get_latest_status', args: { region_id: regionState.region } });
      const cells: any[] = status?.cells || (Array.isArray(status) ? status : []);
      if (!cells.length) return;
      const closest = cells.reduce((best: any, cell: any) => {
        const d = Math.hypot(cell.centroid_lat - loc.lat, cell.centroid_lon - loc.lon);
        const bd = best ? Math.hypot(best.centroid_lat - loc.lat, best.centroid_lon - loc.lon) : Infinity;
        return d < bd ? cell : best;
      }, null);
      setNearbyZone(closest);
    } catch (_) {}
  }

  function handlePhotoSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setPhoto(ev.target?.result as string);
    reader.readAsDataURL(file);
  }

  async function handleSubmitReport() {
    if (!selectedType || !gps) return;
    setSubmitting(true);
    const report: Report = {
      id: `RPT-${Date.now()}`,
      type: selectedType,
      description,
      lat: gps.lat,
      lon: gps.lon,
      timestamp: new Date().toISOString(),
      status: 'pending',
      zone_name: nearbyZone?.name,
      risk_level: nearbyZone?.risk_level,
      photo: photo ?? undefined,
    };
    try {
      if (nearbyZone) {
        await rpcCall({
          func: 'submit_field_verification',
          args: {
            warning_id: 0,
            location_id: nearbyZone.location_id,
            verified_by: reporterName || 'Citizen Reporter',
            outcome: 'unverified',
            notes: `[CITIZEN REPORT] Type: ${selectedType} — ${description}`,
          },
        });
      }
    } catch (_) {}
    const updated = [report, ...myReports];
    setMyReports(updated);
    sessionStorage.setItem('citizen_reports', JSON.stringify(updated));
    setSubmitting(false);
    setSubmitSuccess(true);
    setTimeout(() => {
      setSubmitSuccess(false);
      setSelectedType(null);
      setDescription('');
      setPhoto(null);
      setScreen('home');
    }, 2500);
  }

  function resetForm() {
    setSelectedType(null);
    setDescription('');
    setPhoto(null);
    setSubmitSuccess(false);
    setScreen('home');
  }

  const riskKey = nearbyZone?.risk_level?.toLowerCase() || 'low';
  const riskCfg = RISK_CONFIG[riskKey] ?? RISK_CONFIG.low;

  // ── SHARED HEADER ────────────────────────────────────────────────────────
  const TopBar = ({ title, subtitle, onBack }: { title: string; subtitle: string; onBack?: () => void }) => (
    <div className="flex items-center gap-3 px-4 py-3.5 border-b border-white/5 flex-shrink-0">
      {onBack && (
        <button onClick={onBack} className="h-8 w-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition-all flex-shrink-0">
          <ArrowLeft className="h-4 w-4 text-slate-300" />
        </button>
      )}
      <div>
        <div className="font-bold text-[15px] text-white">{title}</div>
        <div className="text-[11px] text-slate-500">{subtitle}</div>
      </div>
    </div>
  );

  // ────────────────────────────────────────────────────────────────────────
  // RENDER
  // ────────────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-screen bg-[#0c0c0e] text-white overflow-hidden">

      {/* ── STATUS BAR ── */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-black/50 border-b border-white/5 flex-shrink-0">
        {/* Left: connection status */}
        <div className="flex items-center gap-1.5">
          {isOnline
            ? <><Wifi className="h-3.5 w-3.5 text-emerald-400" /><span className="text-[10px] text-emerald-400 font-bold tracking-wider">CONNECTED</span></>
            : <><WifiOff className="h-3.5 w-3.5 text-red-400" /><span className="text-[10px] text-red-400 font-bold tracking-wider">OFFLINE</span></>
          }
        </div>

        {/* Centre: app name */}
        <span className="text-[10px] font-bold tracking-widest text-slate-600 uppercase">TerraPulse Citizen</span>

        {/* Right: gear dropdown — same as Authority Dashboard */}
        <div className="relative" ref={modeMenuRef}>
          <button
            onClick={() => setShowModeMenu(v => !v)}
            className={cn(
              'h-7 w-7 rounded-md flex items-center justify-center border transition-all',
              showModeMenu
                ? 'bg-primary/20 border-primary/40 text-primary'
                : 'bg-white/5 border-white/10 text-slate-400 hover:text-white hover:border-white/20'
            )}
            title="Switch portal mode"
          >
            <Settings className="h-3.5 w-3.5" />
          </button>

          {showModeMenu && (
            <div className="absolute right-0 top-9 z-[200] w-52 rounded-xl border border-border/40 bg-[#111114] shadow-2xl backdrop-blur-xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="px-3 py-2 border-b border-white/5">
                <span className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Portal Mode</span>
              </div>

              {/* Authority option */}
              <button
                onClick={() => { onSwitchToAdmin(); setShowModeMenu(false); }}
                className="w-full flex items-center gap-3 px-3 py-3 text-sm font-medium transition-all hover:bg-white/5 text-slate-400"
              >
                <div className="h-7 w-7 rounded-lg bg-white/5 text-slate-500 flex items-center justify-center flex-shrink-0">
                  <Shield className="h-3.5 w-3.5" />
                </div>
                <div className="text-left">
                  <div className="font-bold text-[12px] text-slate-300">Authority Dashboard</div>
                  <div className="text-[10px] text-slate-600">Command &amp; control view</div>
                </div>
              </button>

              {/* Citizen option — active */}
              <button
                onClick={() => setShowModeMenu(false)}
                className="w-full flex items-center gap-3 px-3 py-3 text-sm font-medium transition-all hover:bg-white/5 text-white bg-white/[0.03]"
              >
                <div className="h-7 w-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center flex-shrink-0">
                  <Users className="h-3.5 w-3.5" />
                </div>
                <div className="text-left">
                  <div className="font-bold text-[12px]">Citizen Portal</div>
                  <div className="text-[10px] text-slate-500">Field reporting &amp; alerts</div>
                </div>
                <div className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
              </button>

              <div className="px-3 py-2 border-t border-white/5">
                <div className="flex items-center gap-1.5 text-[9px] text-slate-700 font-mono">
                  <Radio className="h-2.5 w-2.5" />
                  TERRAPULSE · SIH 2026
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════
          HOME SCREEN
      ══════════════════════════════════════════════════════════ */}
      {screen === 'home' && (
        <div className="flex-1 overflow-y-auto">
          
          {/* Greeting section */}
          <div className="px-5 pt-6 pb-2">
            <p className="text-slate-400 text-sm">Good day 👋</p>
            <h1 className="text-2xl font-black text-white mt-0.5">Citizen Portal</h1>
            <p className="text-xs text-slate-500 mt-1">Your ground observations help protect communities</p>
          </div>

          {/* GPS + Zone Card */}
          <div className="px-4 pt-3 pb-2">
            <div className="rounded-2xl bg-white/[0.04] border border-white/10 p-4 space-y-3">
              
              {/* Card header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-7 w-7 rounded-lg bg-primary/15 flex items-center justify-center">
                    <MapPin className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Your Zone</span>
                </div>
                <button
                  onClick={acquireGPS}
                  className="flex items-center gap-1.5 text-[10px] font-bold text-slate-400 hover:text-white border border-white/10 hover:border-white/20 px-2.5 py-1 rounded-full transition-all bg-white/5"
                >
                  <Navigation className="h-3 w-3" />
                  Refresh
                </button>
              </div>

              {/* GPS status */}
              {gpsLoading && (
                <div className="flex items-center gap-2 animate-pulse">
                  <div className="h-2 w-2 rounded-full bg-primary animate-ping" />
                  <span className="text-xs text-slate-400">Locating you…</span>
                </div>
              )}
              {gpsError && (
                <div className="text-[11px] text-amber-400/80 flex items-center gap-1.5">
                  <AlertTriangle className="h-3 w-3 flex-shrink-0" />
                  {gpsError}
                </div>
              )}

              {/* Zone info */}
              {nearbyZone ? (
                <div className="space-y-2.5">
                  <div>
                    <div className="text-[11px] text-slate-500 mb-1">Nearest monitoring zone</div>
                    <div className="font-bold text-white text-sm">{nearbyZone.name}</div>
                    {gps && (
                      <div className="text-[10px] text-slate-600 font-mono mt-0.5">
                        {gps.lat.toFixed(4)}°N, {gps.lon.toFixed(4)}°E
                      </div>
                    )}
                  </div>

                  {/* Risk pill + bar */}
                  <div className="flex items-center gap-3">
                    <span className={cn('text-[11px] font-bold px-3 py-1 rounded-full border', riskCfg.pill)}>
                      {riskCfg.label} Risk
                    </span>
                    <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className={cn('h-full rounded-full transition-all duration-700', riskCfg.bar)}
                        style={{ width: `${Math.min(nearbyZone.risk_score ?? 30, 100)}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-slate-500">
                      {nearbyZone.risk_score?.toFixed(0) ?? '—'}/100
                    </span>
                  </div>

                  <div className="flex gap-4 text-[10px] text-slate-500">
                    <span>Slope {nearbyZone.slope_angle}°</span>
                    <span>·</span>
                    <span>Elev {nearbyZone.elevation_m}m</span>
                    <span>·</span>
                    <span>{nearbyZone.district}</span>
                  </div>
                </div>
              ) : !gpsLoading ? (
                <div className="space-y-1.5">
                  <div className="h-3 w-32 bg-white/5 rounded animate-pulse" />
                  <div className="h-2 w-48 bg-white/5 rounded animate-pulse" />
                </div>
              ) : null}
            </div>
          </div>

          {/* Advisory banner — only shows for high/critical, subtle not alarming */}
          {(riskKey === 'critical' || riskKey === 'high') && nearbyZone && (
            <div className="mx-4 mt-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 flex items-start gap-2.5">
              <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-bold text-amber-300 mb-0.5">Safety Advisory</div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Elevated risk detected near you. Avoid steep slopes and riverbanks.
                  Report any ground movement immediately.
                </p>
              </div>
            </div>
          )}

          {/* Action cards */}
          <div className="px-4 pt-4 space-y-2.5 pb-6">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-1 mb-3">Quick Actions</p>

            {/* Report Hazard */}
            <button
              onClick={() => setScreen('report')}
              className="w-full flex items-center gap-4 bg-primary/10 hover:bg-primary/15 border border-primary/25 hover:border-primary/40 rounded-2xl px-4 py-4 transition-all group text-left"
            >
              <div className="h-11 w-11 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
                <Camera className="h-5 w-5 text-primary" />
              </div>
              <div className="flex-1">
                <div className="font-bold text-[14px] text-white">Report a Hazard</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Geo-tagged photo + description</div>
              </div>
              <ChevronRight className="h-4 w-4 text-slate-500 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
            </button>

            {/* My Reports */}
            <button
              onClick={() => setScreen('my_reports')}
              className="w-full flex items-center gap-4 bg-white/[0.03] hover:bg-white/[0.06] border border-white/10 hover:border-white/20 rounded-2xl px-4 py-4 transition-all group text-left"
            >
              <div className="h-11 w-11 rounded-xl bg-blue-500/15 flex items-center justify-center flex-shrink-0 relative">
                <FileText className="h-5 w-5 text-blue-400" />
                {myReports.length > 0 && (
                  <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-blue-500 text-[9px] font-black text-white flex items-center justify-center">
                    {myReports.length}
                  </span>
                )}
              </div>
              <div className="flex-1">
                <div className="font-bold text-[14px] text-white">My Reports</div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  {myReports.length > 0 ? `${myReports.length} submission${myReports.length !== 1 ? 's' : ''} this session` : 'No reports yet'}
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-slate-500 group-hover:text-blue-400 group-hover:translate-x-0.5 transition-all" />
            </button>

            {/* Emergency */}
            <button
              onClick={() => setScreen('emergency')}
              className="w-full flex items-center gap-4 bg-white/[0.03] hover:bg-white/[0.06] border border-white/10 hover:border-white/20 rounded-2xl px-4 py-4 transition-all group text-left"
            >
              <div className="h-11 w-11 rounded-xl bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
                <Phone className="h-5 w-5 text-emerald-400" />
              </div>
              <div className="flex-1">
                <div className="font-bold text-[14px] text-white">Emergency Contacts</div>
                <div className="text-[11px] text-slate-400 mt-0.5">NDMA, SDRF, BRO & Nepal helplines</div>
              </div>
              <ChevronRight className="h-4 w-4 text-slate-500 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
            </button>
          </div>

          {/* Bottom info */}
          <div className="text-center pb-5 text-[10px] text-slate-700 font-mono">
            TERRAPULSE.AI · SIH 2026
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════
          REPORT SCREEN
      ══════════════════════════════════════════════════════════ */}
      {screen === 'report' && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <TopBar title="Report Hazard" subtitle="Submit to Authority Dashboard for verification" onBack={resetForm} />

          {submitSuccess ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 p-8">
              <div className="h-20 w-20 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
                <CheckCircle2 className="h-10 w-10 text-emerald-400" />
              </div>
              <div className="text-center">
                <h3 className="font-bold text-lg text-white">Report Submitted!</h3>
                <p className="text-sm text-slate-400 mt-1">Sent to the Authority Dashboard for field verification</p>
              </div>
              <div className="flex items-center gap-2 text-[11px] text-emerald-400 font-mono bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20">
                <Radio className="h-3 w-3 animate-pulse" />
                Pending authority verification
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto p-4 space-y-5">

              {/* GPS tag */}
              <div className="flex items-center gap-2.5 bg-emerald-500/5 border border-emerald-500/20 rounded-xl px-4 py-3">
                <MapPin className="h-4 w-4 text-emerald-400 flex-shrink-0" />
                {gps ? (
                  <div>
                    <span className="text-xs font-mono text-slate-300">{gps.lat.toFixed(5)}°N, {gps.lon.toFixed(5)}°E</span>
                    {nearbyZone && <span className="text-[10px] text-slate-500 ml-1.5">· {nearbyZone.name}</span>}
                  </div>
                ) : (
                  <span className="text-xs text-amber-400">GPS unavailable — using approximate location</span>
                )}
              </div>

              {/* Reporter name */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 block">
                  Your Name <span className="normal-case font-normal text-slate-600">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Field Officer / Citizen"
                  value={reporterName}
                  onChange={e => setReporterName(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/10 focus:border-primary/40 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600 outline-none transition-all"
                />
              </div>

              {/* Observation type */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2 block">
                  What did you observe? <span className="text-primary">*</span>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {REPORT_TYPES.map(rt => {
                    const Icon = rt.icon;
                    const active = selectedType === rt.id;
                    return (
                      <button
                        key={rt.id}
                        onClick={() => setSelectedType(rt.id)}
                        className={cn(
                          'flex items-center gap-2.5 px-3 py-3.5 rounded-xl border text-xs font-semibold text-left transition-all',
                          active
                            ? `${rt.bg} ${rt.accent} ring-1 ring-current`
                            : 'border-white/8 bg-white/[0.03] text-slate-400 hover:border-white/15 hover:bg-white/[0.05]'
                        )}
                      >
                        <Icon className={cn('h-4 w-4 flex-shrink-0', active ? rt.accent : 'text-slate-600')} />
                        <span className="leading-tight">{rt.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 block">
                  Description
                </label>
                <textarea
                  rows={3}
                  placeholder="Describe what you see — e.g. crack across road, water seeping, debris on slope…"
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/10 focus:border-primary/40 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600 outline-none resize-none transition-all"
                />
              </div>

              {/* Photo upload */}
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 block">
                  Photo Evidence <span className="normal-case font-normal text-slate-600">(recommended)</span>
                </label>
                <input ref={fileInputRef} type="file" accept="image/*" capture="environment" onChange={handlePhotoSelect} className="hidden" />
                {photo ? (
                  <div className="relative rounded-xl overflow-hidden border border-white/10">
                    <img src={photo} alt="Evidence" className="w-full h-36 object-cover" />
                    <button
                      onClick={() => setPhoto(null)}
                      className="absolute top-2 right-2 h-7 w-7 rounded-full bg-black/70 flex items-center justify-center hover:bg-black/90 transition-all"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                    <div className="absolute bottom-0 left-0 right-0 px-3 py-2 bg-gradient-to-t from-black/80 to-transparent text-[10px] text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3" /> Photo attached
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full flex flex-col items-center gap-2 border border-dashed border-white/15 hover:border-primary/40 bg-white/[0.02] hover:bg-primary/5 rounded-xl py-7 transition-all"
                  >
                    <div className="h-10 w-10 rounded-xl bg-white/5 flex items-center justify-center">
                      <Upload className="h-5 w-5 text-slate-500" />
                    </div>
                    <span className="text-xs text-slate-500">Tap to take photo or upload from gallery</span>
                  </button>
                )}
              </div>

              {/* Submit */}
              <button
                onClick={handleSubmitReport}
                disabled={!selectedType || submitting}
                className={cn(
                  'w-full flex items-center justify-center gap-2 py-4 rounded-xl font-bold text-sm transition-all',
                  selectedType && !submitting
                    ? 'bg-primary text-black hover:opacity-90'
                    : 'bg-white/5 text-slate-600 cursor-not-allowed border border-white/10'
                )}
              >
                {submitting
                  ? <><Radio className="h-4 w-4 animate-spin" /> Submitting…</>
                  : <><Send className="h-4 w-4" /> Submit to Authority Dashboard</>
                }
              </button>

              <p className="text-[10px] text-center text-slate-600 leading-relaxed pb-2">
                Your report will appear under "Pending Verifications" in the Authority Dashboard
                for expert review before being used for model improvement.
              </p>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════
          MY REPORTS SCREEN
      ══════════════════════════════════════════════════════════ */}
      {screen === 'my_reports' && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <TopBar
            title="My Reports"
            subtitle={`${myReports.length} submission${myReports.length !== 1 ? 's' : ''} this session`}
            onBack={() => setScreen('home')}
          />
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {myReports.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-20 text-center gap-3">
                <div className="h-14 w-14 rounded-2xl bg-white/5 flex items-center justify-center">
                  <Eye className="h-7 w-7 text-slate-700" />
                </div>
                <p className="font-bold text-slate-500">No reports yet</p>
                <p className="text-xs text-slate-600 max-w-[220px]">Go back and submit your first hazard observation to help protect the community</p>
                <button onClick={() => setScreen('report')} className="mt-2 text-xs font-bold text-primary hover:opacity-80 transition-opacity">
                  + Submit a Report
                </button>
              </div>
            ) : (
              myReports.map(r => {
                const rt = REPORT_TYPES.find(t => t.id === r.type);
                const Icon = rt?.icon ?? FileText;
                return (
                  <div key={r.id} className="bg-white/[0.04] border border-white/10 rounded-2xl p-4 space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3">
                        <div className={cn('h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0', rt?.bg || 'bg-white/5')}>
                          <Icon className={cn('h-4 w-4', rt?.accent || 'text-slate-400')} />
                        </div>
                        <div>
                          <div className="text-sm font-bold text-white">{rt?.label || r.type}</div>
                          {r.zone_name && <div className="text-[10px] text-slate-500">{r.zone_name}</div>}
                        </div>
                      </div>
                      <span className={cn('text-[9px] font-bold uppercase tracking-wider px-2 py-1 rounded-full border', STATUS_STYLE[r.status])}>
                        {r.status.replace('_', ' ')}
                      </span>
                    </div>
                    {r.description && (
                      <p className="text-[12px] text-slate-400 leading-relaxed pl-12">"{r.description}"</p>
                    )}
                    {r.photo && (
                      <img src={r.photo} alt="Evidence" className="w-full h-28 object-cover rounded-xl" />
                    )}
                    <div className="flex items-center justify-between text-[10px] text-slate-600 font-mono pl-12">
                      <span>{r.id}</span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(r.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════
          EMERGENCY SCREEN
      ══════════════════════════════════════════════════════════ */}
      {screen === 'emergency' && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <TopBar title="Emergency Contacts" subtitle="Landslide response helplines — NER & Nepal" onBack={() => setScreen('home')} />
          <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
            {[
              { name: 'NDMA National Helpline', number: '1078',           desc: 'National Disaster Management Authority',       icon: '🇮🇳', accent: 'border-white/10' },
              { name: 'Sikkim State EOC',        number: '1070',           desc: 'State Emergency Operations Centre',             icon: '🏢', accent: 'border-white/10' },
              { name: 'SDRF North Sikkim',       number: '+91-3592-234567',desc: 'State Disaster Response Force',                 icon: '🛡️', accent: 'border-white/10' },
              { name: 'BRO Mangan Division',     number: '+91-3592-234222',desc: 'Border Roads Organisation — NH-10 Corridor',   icon: '🚧', accent: 'border-white/10' },
              { name: 'Nepal NDRRMA',            number: '1155',           desc: 'National Disaster Risk Reduction Authority',   icon: '🇳🇵', accent: 'border-white/10' },
              { name: 'Rasuwa District DCC',     number: '+977-10-540203', desc: 'Rasuwa District Coordination Committee',       icon: '🏔️', accent: 'border-white/10' },
            ].map(c => (
              <a
                key={c.name}
                href={`tel:${c.number}`}
                className="flex items-center gap-4 bg-white/[0.04] hover:bg-white/[0.07] border border-white/10 hover:border-white/20 rounded-2xl px-4 py-4 transition-all group"
              >
                <div className="h-10 w-10 rounded-xl bg-white/5 flex items-center justify-center text-xl flex-shrink-0">
                  {c.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-sm text-white">{c.name}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5 truncate">{c.desc}</div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-sm font-mono font-bold text-white">{c.number}</span>
                  <div className="h-7 w-7 rounded-full bg-emerald-500/15 flex items-center justify-center group-hover:bg-emerald-500/25 transition-all">
                    <Phone className="h-3.5 w-3.5 text-emerald-400" />
                  </div>
                </div>
              </a>
            ))}

            <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-4 mt-2">
              <p className="text-[11px] text-slate-600 leading-relaxed text-center">
                In an active emergency, call the nearest number above immediately.
                Your location and reports have been shared with the system.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
