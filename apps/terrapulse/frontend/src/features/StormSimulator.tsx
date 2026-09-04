import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import {
  Activity, Play, Square, Loader2, CloudRain, Droplets,
  AlertTriangle, CheckCircle, RefreshCw, Zap, Wind
} from 'lucide-react';
import { streamCall, rpcCall } from '../api';
import { ScrollArea } from '../components/ui/scroll-area';
import { cn } from '../lib/utils';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface SimulationChunk {
  type: string;
  step: number;
  time_label: string;
  description?: string;
  progress: number;
  cells?: any[];
  warnings?: any[];
  summary?: any;
  recommended_actions?: string[];
  affected_cells?: string[];
}

interface StormMonitorProps {
  onSimulationUpdate?: (cells: any[]) => void;
  onWarningsUpdate?: (warnings: any[]) => void;
}

const STEP_COLOR: Record<string, string> = {
  scenario_start: 'text-emerald-400',
  scenario_event: 'text-amber-400',
  map_update: 'text-blue-400',
  infrastructure_alert: 'text-red-400',
  simulation_complete: 'text-emerald-400',
  error: 'text-red-500',
};

const RISK_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  moderate: '#f59e0b',
  low: '#10b981',
};

export function StormSimulator({ onSimulationUpdate, onWarningsUpdate }: StormMonitorProps) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [events, setEvents] = useState<SimulationChunk[]>([]);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState<SimulationChunk | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [rainfallHistory, setRainfallHistory] = useState<any[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  
  const handleSaveRecord = async () => {
    try {
      const res = await rpcCall({
        func: 'save_simulation_record',
        args: { summary, events }
      });
      alert(res.message);
    } catch (e) {
      console.error(e);
      alert('Failed to save record.');
    }
  };

  const startSimulation = async () => {
    setIsStreaming(true);
    setEvents([]);
    setProgress(0);
    setCurrentStep(null);
    setSummary(null);
    setRainfallHistory([]);

    // Reset previous simulation state
    try {
      await rpcCall({ func: 'reset_simulation' });
    } catch (e) { /* ignore */ }

    try {
      await streamCall({
        func: 'run_storm_simulation',
        args: {},
        onChunk: (chunk: SimulationChunk) => {
          setProgress(chunk.progress || 0);
          setCurrentStep(chunk);
          setEvents(prev => [...prev, chunk]);

          // Update map when we get cell data
          if (chunk.cells && onSimulationUpdate) {
            onSimulationUpdate(chunk.cells);
          }

          // Update warnings
          if (chunk.warnings && onWarningsUpdate) {
            onWarningsUpdate(chunk.warnings);
          }

          // Track rainfall accumulation for chart
          if (chunk.type === 'map_update' && chunk.cells) {
            const avgRain3d = chunk.cells.reduce((sum: number, c: any) =>
              sum + (c.rainfall?.rainfall_3d_mm || 0), 0) / chunk.cells.length;
            const avgIntensity = chunk.cells.reduce((sum: number, c: any) =>
              sum + (c.rainfall?.rainfall_intensity || 0), 0) / chunk.cells.length;
            const critCount = chunk.cells.filter((c: any) => c.risk_level === 'critical').length;
            const highCount = chunk.cells.filter((c: any) => c.risk_level === 'high').length;

            setRainfallHistory(prev => [...prev, {
              step: `T+${chunk.step}`,
              rainfall3d: Math.round(avgRain3d),
              intensity: Math.round(avgIntensity),
              critical: critCount,
              high: highCount,
            }]);
          }

          if (chunk.type === 'simulation_complete') {
            setSummary(chunk.summary);
            setIsStreaming(false);
          }
          if (chunk.type === 'error') {
            setIsStreaming(false);
          }
        },
        onError: (err) => {
          console.error('Storm simulation error:', err);
          setIsStreaming(false);
          setEvents(prev => [...prev, {
            type: 'error', step: 0, time_label: 'Error',
            description: `Simulation error: ${err.message}`, progress: 0
          }]);
        }
      });
    } catch (err) {
      setIsStreaming(false);
    }
  };

  const stopSimulation = () => {
    setIsStreaming(false);
  };

  const getRiskBadge = (level: string) => {
    const colors: Record<string, string> = {
      critical: 'bg-red-950/50 text-red-400 border-red-800/50',
      high: 'bg-orange-950/50 text-orange-400 border-orange-800/50',
      moderate: 'bg-amber-950/50 text-amber-400 border-amber-800/50',
      low: 'bg-emerald-950/50 text-emerald-400 border-emerald-800/50',
    };
    return colors[level?.toLowerCase()] || colors.low;
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 h-full p-2">
      {/* Left Panel — Main Simulator */}
      <div className="xl:col-span-2 space-y-6">
        
        {/* Main Card (Matches Screenshot) */}
        <Card className="bg-[#131313] border-border/20 rounded-xl overflow-hidden shadow-xl flex flex-col">
          <div className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
              <div>
                <h2 className="text-xl font-bold font-heading flex items-center gap-2 text-primary">
                  <Activity className="h-5 w-5" />
                  Live Sensor Stream
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Real-time displacement and vibration monitoring across active zones
                </p>
              </div>
              
              {isStreaming ? (
                <Button onClick={stopSimulation} variant="destructive" className="font-bold rounded-md px-6 flex items-center gap-2 transition-all">
                  <Square className="h-4 w-4" />
                  Stop Simulation
                </Button>
              ) : (
                <Button onClick={startSimulation} className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold rounded-md px-6 flex items-center gap-2 transition-all">
                  <Play className="h-4 w-4 fill-current" />
                  Start Simulation
                </Button>
              )}
            </div>

            <div className="bg-black/40 rounded-lg p-4 mb-6 border border-border/10">
              <div className="flex justify-between text-[11px] font-bold uppercase tracking-widest mb-3">
                <span className="text-muted-foreground">
                  SIMULATION STATUS: <span className="text-primary">{status === 'idle' ? 'STANDBY' : status === 'running' ? 'INITIALIZING SIMULATION...' : 'COMPLETE'}</span>
                </span>
                <span className="text-muted-foreground">{Math.round(progress)}%</span>
              </div>
              <div className="h-3 w-full bg-[#1c140a] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[#9c4b1d] transition-all duration-500 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {events.length === 0 && !isStreaming ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="h-16 w-16 rounded-full bg-white/5 flex items-center justify-center mb-6">
                  <Activity className="h-6 w-6 text-muted-foreground/50" />
                </div>
                <p className="text-muted-foreground text-sm">
                  Click "Start Simulation" to begin real-time data flow
                </p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Rainfall Accumulation Chart */}
                {rainfallHistory.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                      <CloudRain className="h-3 w-3 text-blue-400" />
                      Rainfall Accumulation Timeline
                    </div>
                    <div className="h-[140px] bg-muted/10 rounded-lg p-2 border border-border/20">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={rainfallHistory}>
                          <XAxis dataKey="step" tick={{ fontSize: 9, fill: '#64748b' }} />
                          <YAxis tick={{ fontSize: 9, fill: '#64748b' }} width={35} />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '11px' }}
                            labelStyle={{ color: '#94a3b8' }}
                          />
                          <ReferenceLine y={150} stroke="#f59e0b" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Warning', fontSize: 9, fill: '#f59e0b' }} />
                          <ReferenceLine y={280} stroke="#ef4444" strokeDasharray="4 2" strokeOpacity={0.5} label={{ value: 'Critical', fontSize: 9, fill: '#ef4444' }} />
                          <Line type="monotone" dataKey="rainfall3d" name="3-Day Rain (mm)" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
                          <Line type="monotone" dataKey="intensity" name="Intensity (mm/hr)" stroke="#22d3ee" strokeWidth={1.5} strokeDasharray="5 3" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {/* Event Stream Log */}
                <ScrollArea className="h-[300px]" ref={scrollRef as any}>
                  <div className="space-y-2.5 pr-2">

                {events.map((event, i) => (
                  <div
                    key={i}
                    className={cn(
                      "flex gap-3 p-3 rounded-lg border animate-in fade-in slide-in-from-left-2 duration-300",
                      event.type === 'infrastructure_alert'
                        ? 'border-red-800/50 bg-red-950/20'
                        : event.type === 'simulation_complete'
                          ? 'border-emerald-800/50 bg-emerald-950/20'
                          : event.type === 'error'
                            ? 'border-red-800/50 bg-red-950/30'
                            : 'border-border/30 bg-card/50'
                    )}
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      {event.type === 'map_update' && <Activity className="h-4 w-4 text-blue-400" />}
                      {event.type === 'scenario_start' && <CheckCircle className="h-4 w-4 text-emerald-400" />}
                      {event.type === 'scenario_event' && <CloudRain className="h-4 w-4 text-amber-400" />}
                      {event.type === 'infrastructure_alert' && <AlertTriangle className="h-4 w-4 text-red-400" />}
                      {event.type === 'simulation_complete' && <CheckCircle className="h-4 w-4 text-emerald-400" />}
                      {event.type === 'error' && <AlertTriangle className="h-4 w-4 text-red-500" />}
                    </div>

                    <div className="flex-1 space-y-1.5 min-w-0">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className={cn("text-xs font-bold", STEP_COLOR[event.type] || 'text-muted-foreground')}>
                          {event.time_label}
                        </span>
                        <span className="text-[10px] font-mono text-muted-foreground/60">{new Date().toLocaleTimeString()}</span>
                      </div>

                      {event.description && (
                        <p className="text-[11px] text-muted-foreground leading-relaxed">{event.description}</p>
                      )}

                      {/* Map update summary */}
                      {event.type === 'map_update' && event.cells && (
                        <div className="flex gap-2 flex-wrap mt-1">
                          {(['critical', 'high', 'moderate', 'low'] as const).map(lvl => {
                            const count = event.cells!.filter(c => c.risk_level === lvl).length;
                            if (!count) return null;
                            return (
                              <div key={lvl} className="flex items-center gap-1 text-[10px] font-bold"
                                style={{ color: RISK_COLORS[lvl] }}>
                                <span className="h-1.5 w-1.5 rounded-full inline-block" style={{ backgroundColor: RISK_COLORS[lvl] }} />
                                {count} {lvl}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* Infrastructure alert actions */}
                      {event.type === 'infrastructure_alert' && event.recommended_actions && (
                        <div className="space-y-1 mt-1">
                          {event.recommended_actions.slice(0, 3).map((action, j) => (
                            <div key={j} className="flex items-start gap-1.5 text-[10px] text-red-300">
                              <span className="flex-shrink-0 mt-0.5">→</span>
                              <span>{action}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* New warnings generated */}
                      {event.warnings && event.warnings.length > 0 && (
                        <div className="flex items-center gap-1.5 text-[10px] text-red-400 font-bold">
                          <AlertTriangle className="h-3 w-3" />
                          {event.warnings.length} early warning(s) triggered
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {isStreaming && (
                  <div className="flex items-center justify-center p-4">
                    <Loader2 className="h-5 w-5 animate-spin text-primary opacity-60 mr-2" />
                    <span className="text-xs text-muted-foreground">Processing through ML pipeline...</span>
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
          )}
          </div>
        </Card>
      </div>





      {/* Right Panel — Simulation Summary + Model Info */}
      <div className="space-y-6">
        
        {/* Site Context with Image */}
        <Card className="bg-[#131313] border-border/20 rounded-xl overflow-hidden shadow-xl">
          <div className="relative h-48 w-full">
            <img
              src="/assets/231854574217558.jpg"
              alt="Site View"
              className="absolute inset-0 w-full h-full object-cover"
            />
            {/* Dark gradient overlay at bottom for text contrast */}
            <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/80 to-transparent pointer-events-none" />
            
            <div className="absolute bottom-4 left-4">
              <Badge className="bg-primary text-black font-bold uppercase tracking-widest hover:bg-primary/90 rounded-[4px] px-2 py-0.5 text-[10px]">
                SITE PRIMARY VIEW
              </Badge>
            </div>
          </div>
          <CardContent className="p-5 space-y-3">
            <div className="text-[13px] font-bold uppercase tracking-widest text-white mt-1">
              Site Context
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Monitoring is active for the North Sikkim high-risk corridor (NH-10). Simulation mode runs high-frequency risk re-calculations based on the Gradient Boosting ensemble model.
            </p>
          </CardContent>
        </Card>

        {/* Model Information */}
        <Card className="bg-[#131313] border-border/20 rounded-xl shadow-xl">
          <CardHeader className="p-5 pb-3">
            <CardTitle className="text-[13px] font-bold uppercase tracking-widest text-white">Model Information</CardTitle>
          </CardHeader>
          <CardContent className="p-5 pt-0 space-y-6">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-[8px] bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                <Activity className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <div className="text-sm font-bold text-white">Gradient Boosting Classifier</div>
                <div className="text-[10px] text-muted-foreground mt-0.5">v2.4.1 - Production Ensemble</div>
              </div>
            </div>
            <div className="flex items-center justify-between pt-0 text-[11px] font-bold">
              <div className="text-muted-foreground uppercase tracking-widest">Precision: <span className="text-primary">94.2%</span></div>
              <div className="text-muted-foreground uppercase tracking-widest">Recall: <span className="text-primary">91.8%</span></div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
