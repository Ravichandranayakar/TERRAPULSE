import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { AlertTriangle, Clock, Play, Pause, SkipForward, Timer, Shield, Database } from 'lucide-react';
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea
} from 'recharts';
import { useRegion } from '../contexts/RegionContext';

interface ReplayData {
  event: any;
  timeline: any[];
  lead_time: any;
  data_provenance: any;
}

export function EventReplay() {
  const { state: regionState } = useRegion();
  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [loading, setLoading] = useState(false);

  // Fetch replay data
  useEffect(() => {
    if (regionState.region !== 'nepal_case') return;
    setLoading(true);
    fetch('http://localhost:5000/api/event-replay')
      .then(res => res.json())
      .then(data => {
        setReplayData(data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch replay data:", err);
        setLoading(false);
      });
  }, [regionState.region]);

  // Playback timer
  useEffect(() => {
    if (!isPlaying || !replayData) return;
    const interval = setInterval(() => {
      setCurrentIdx(prev => {
        if (prev >= replayData.timeline.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 200);
    return () => clearInterval(interval);
  }, [isPlaying, replayData]);

  // Chart data
  const chartData = useMemo(() => {
    if (!replayData) return [];
    return replayData.timeline.map((point: any, idx: number) => {
      const d = new Date(point.timestamp);
      return {
        time: `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:00`,
        rainfall: point.rainfall_mm,
        risk: Math.round(point.predicted_risk * 100),
        cumRain: point.cumulative_24h_mm,
        eventOccurred: point.event_occurred,
        hoursToEvent: point.hours_to_event,
        idx,
      };
    });
  }, [replayData]);

  const currentPoint = replayData?.timeline?.[currentIdx];

  // If not Nepal mode, show a message
  if (regionState.region !== 'nepal_case') {
    return (
      <Card className="bg-card border-border/20 text-card-foreground">
        <CardContent className="p-8 flex flex-col items-center justify-center text-muted-foreground gap-3">
          <Timer className="w-8 h-8 text-slate-600" />
          <p className="text-sm">Event Replay is available in <strong>Real-World Case</strong> mode.</p>
          <p className="text-xs text-slate-600">Switch to Nepal mode using the header toggle to replay the Rasuwa event.</p>
        </CardContent>
      </Card>
    );
  }

  if (loading || !replayData) {
    return (
      <Card className="bg-card border-border/20">
        <CardContent className="p-8 flex items-center justify-center text-muted-foreground">
          Loading event replay data...
        </CardContent>
      </Card>
    );
  }

  const leadTime = replayData.lead_time;
  const eventIdx = replayData.timeline.findIndex((p: any) => p.event_occurred);

  return (
    <div className="space-y-4">

      {/* Event Context Banner */}
      <Card className="bg-card border-border/20">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-bold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              {replayData.event.event_name}
            </CardTitle>
            <Badge className="bg-amber-500/10 text-amber-400 border-amber-500/20 text-[10px]">
              HISTORICAL REPLAY
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">{replayData.event.description}</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">Event Date</div>
              <div className="text-sm font-bold text-white mt-1">{replayData.event.event_date}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">Type</div>
              <div className="text-sm font-bold text-amber-400 mt-1">{replayData.event.event_type}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">Districts</div>
              <div className="text-sm font-bold text-white mt-1">{replayData.event.affected_districts.join(', ')}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">Source</div>
              <div className="text-sm font-bold text-white mt-1">{replayData.event.source}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lead Time Result */}
      {leadTime.potential_lead_time_hours && (
        <Card className="bg-gradient-to-r from-emerald-500/10 to-teal-500/10 border-emerald-500/20">
          <CardContent className="p-4 flex items-center gap-6">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/20 border-2 border-emerald-500/40 flex-shrink-0">
              <Timer className="w-7 h-7 text-emerald-400" />
            </div>
            <div className="flex-1">
              <div className="text-[10px] text-emerald-400 uppercase tracking-widest font-bold">Potential Warning Lead Time</div>
              <div className="text-3xl font-black text-emerald-400 mt-1">
                {leadTime.potential_lead_time_hours}h
              </div>
              <div className="text-xs text-slate-400 mt-1">
                Warning threshold ({leadTime.warning_threshold_label}) crossed at{' '}
                <span className="text-white font-mono">{leadTime.warning_crossed_at ? new Date(leadTime.warning_crossed_at).toLocaleTimeString('en-US', { hour12: false }) : 'N/A'}</span>
                {' '}&bull;{' '}Event observed at{' '}
                <span className="text-white font-mono">{leadTime.event_occurred_at ? new Date(leadTime.event_occurred_at).toLocaleTimeString('en-US', { hour12: false }) : 'N/A'}</span>
              </div>
            </div>
            <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 text-[10px] self-start">
              COMPUTED FROM REANALYSIS
            </Badge>
          </CardContent>
        </Card>
      )}

      {/* Playback Controls */}
      <div className="flex items-center gap-3 bg-white/5 rounded-lg p-3 border border-white/10">
        <Button
          size="sm"
          onClick={() => { setCurrentIdx(0); setIsPlaying(true); }}
          className="bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs h-8"
        >
          <Play className="w-3 h-3 mr-1" /> REPLAY
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setIsPlaying(!isPlaying)}
          className="border-white/20 text-xs h-8"
        >
          {isPlaying ? <Pause className="w-3 h-3 mr-1" /> : <Play className="w-3 h-3 mr-1" />}
          {isPlaying ? 'PAUSE' : 'RESUME'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setCurrentIdx(Math.min(currentIdx + 5, (replayData?.timeline?.length || 1) - 1))}
          className="border-white/20 text-xs h-8"
        >
          <SkipForward className="w-3 h-3 mr-1" /> +5h
        </Button>
        <input
          type="range"
          min={0}
          max={(replayData?.timeline?.length || 1) - 1}
          value={currentIdx}
          onChange={e => setCurrentIdx(Number(e.target.value))}
          className="flex-1 h-1.5 accent-amber-500"
        />
        {currentPoint && (
          <div className="text-xs text-slate-400 font-mono min-w-[90px] text-right">
            {new Date(currentPoint.timestamp).toLocaleString('en-GB', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}
          </div>
        )}
      </div>

      {/* Current State Cards */}
      {currentPoint && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-white/5 rounded-lg p-3 border border-white/10">
            <div className="text-[9px] text-slate-500 uppercase tracking-wider">Rainfall (Hourly)</div>
            <div className="text-lg font-black text-blue-400 mt-1">{currentPoint.rainfall_mm} mm</div>
            <Badge className="text-[8px] mt-1 bg-blue-500/10 text-blue-400 border-blue-500/20">Reanalysis</Badge>
          </div>
          <div className="bg-white/5 rounded-lg p-3 border border-white/10">
            <div className="text-[9px] text-slate-500 uppercase tracking-wider">Cumulative 24h</div>
            <div className="text-lg font-black text-cyan-400 mt-1">{currentPoint.cumulative_24h_mm} mm</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3 border border-white/10">
            <div className="text-[9px] text-slate-500 uppercase tracking-wider">Predicted Risk</div>
            <div className={`text-lg font-black mt-1 ${
              currentPoint.risk_level === 'CRITICAL' ? 'text-red-500' :
              currentPoint.risk_level === 'HIGH' ? 'text-orange-500' :
              currentPoint.risk_level === 'MODERATE' ? 'text-yellow-500' : 'text-green-500'
            }`}>{(currentPoint.predicted_risk * 100).toFixed(0)}%</div>
            <Badge className="text-[8px] mt-1 bg-amber-500/10 text-amber-400 border-amber-500/20">ML Output</Badge>
          </div>
          <div className="bg-white/5 rounded-lg p-3 border border-white/10">
            <div className="text-[9px] text-slate-500 uppercase tracking-wider">Risk Level</div>
            <div className={`text-lg font-black mt-1 ${
              currentPoint.risk_level === 'CRITICAL' ? 'text-red-500' :
              currentPoint.risk_level === 'HIGH' ? 'text-orange-500' :
              currentPoint.risk_level === 'MODERATE' ? 'text-yellow-500' : 'text-green-500'
            }`}>{currentPoint.risk_level}</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3 border border-white/10">
            <div className="text-[9px] text-slate-500 uppercase tracking-wider">Event Status</div>
            <div className={`text-lg font-black mt-1 ${currentPoint.event_occurred ? 'text-red-500' : 'text-slate-400'}`}>
              {currentPoint.event_occurred ? 'OCCURRED' : `T-${Math.abs(currentPoint.hours_to_event).toFixed(0)}h`}
            </div>
            {currentPoint.event_occurred && <Badge className="text-[8px] mt-1 bg-red-500/10 text-red-400 border-red-500/20">Verified</Badge>}
          </div>
        </div>
      )}

      {/* Observed vs Predicted Chart */}
      <Card className="bg-card border-border/20">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-bold">Observed vs Predicted Timeline</CardTitle>
            <div className="flex items-center gap-3 text-[10px]">
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-blue-500 inline-block rounded"></span> Rainfall (Reanalysis)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-red-500 inline-block rounded"></span> Predicted Risk</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500/30 inline-block rounded"></span> Event Window</span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 9 }} interval={5} angle={-30} textAnchor="end" height={50} />
              <YAxis yAxisId="rain" orientation="left" tick={{ fill: '#3b82f6', fontSize: 9 }} domain={[0, 'auto']} label={{ value: 'mm/h', angle: -90, position: 'insideLeft', fill: '#3b82f6', fontSize: 9 }} />
              <YAxis yAxisId="risk" orientation="right" tick={{ fill: '#ef4444', fontSize: 9 }} domain={[0, 100]} label={{ value: 'Risk %', angle: 90, position: 'insideRight', fill: '#ef4444', fontSize: 9 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '11px' }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <ReferenceLine yAxisId="risk" y={55} stroke="#f97316" strokeDasharray="4 4" label={{ value: 'WARNING', fill: '#f97316', fontSize: 9, position: 'right' }} />
              {eventIdx >= 0 && (
                <ReferenceLine x={chartData[eventIdx]?.time} yAxisId="risk" stroke="#ef4444" strokeWidth={2} label={{ value: 'EVENT', fill: '#ef4444', fontSize: 10, position: 'top' }} />
              )}
              {currentIdx > 0 && (
                <ReferenceLine x={chartData[currentIdx]?.time} yAxisId="risk" stroke="#ffffff" strokeWidth={1} strokeDasharray="2 2" />
              )}
              <Area yAxisId="rain" type="monotone" dataKey="rainfall" fill="#3b82f6" fillOpacity={0.15} stroke="#3b82f6" strokeWidth={1.5} name="Rainfall (mm)" />
              <Line yAxisId="risk" type="monotone" dataKey="risk" stroke="#ef4444" strokeWidth={2} dot={false} name="Risk %" />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Data Provenance Footer */}
      <div className="flex items-center gap-4 text-[10px] text-slate-500 border-t border-border/10 pt-3">
        <Database className="w-3.5 h-3.5" />
        <span>Rainfall: <strong className="text-slate-400">{replayData.data_provenance.rainfall_type}</strong> ({replayData.data_provenance.rainfall_source})</span>
        <span>|</span>
        <span>Risk: <strong className="text-slate-400">{replayData.data_provenance.risk_type}</strong></span>
        <span>|</span>
        <span>Event: <strong className="text-slate-400">{replayData.data_provenance.event_type}</strong> ({replayData.data_provenance.event_source})</span>
        <span>|</span>
        <span>Data verified: <strong className="text-slate-400">{replayData.event.data_last_verified?.split('T')[0]}</strong></span>
      </div>
    </div>
  );
}
