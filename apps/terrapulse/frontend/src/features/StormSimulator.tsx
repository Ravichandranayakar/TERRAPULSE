import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Activity, AlertTriangle, CheckCircle, CloudRain, Droplets, Loader2, Play, RefreshCw, RotateCcw, Shield, SlidersHorizontal, Square, TrendingUp } from 'lucide-react';
import { predictRiskBatch, rpcCall, RiskPredictionRequest } from '../api';
import { ScrollArea } from '../components/ui/scroll-area';
import { cn } from '../lib/utils';
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import GeospatialViewer from './GeospatialViewer';
import { XAIPanel } from './XAIPanel';

interface GeoCell {
  location_id: string;
  name: string;
  centroid_lat?: number;
  centroid_lon?: number;
  slope_angle?: number;
  elevation_m?: number;
  aspect?: string | number;
  base_susceptibility?: number;
}

interface ScenarioFeatures {
  rainfall_1h: number;
  rainfall_3h: number;
  rainfall_6h: number;
  rainfall_24h: number;
  antecedent_rainfall: number;
  soil_moisture: number;
}

interface ScenarioStep {
  time: string;
  description: string;
  inputs: ScenarioFeatures;
}

interface RiskPrediction {
  cell_id: string;
  risk_score: number;
  risk_class: string;
  risk_level: string;
  drivers: string[];
  contributing_factors: any[];
  warning_ready: boolean;
  predictor: string;
  predictor_type: string;
}

interface RiskStats {
  average: number;
  critical: number;
  high: number;
  moderate: number;
  low: number;
  warningReady: number;
}

interface SimulationEvent {
  id: string;
  time: string;
  description: string;
  type: 'scenario' | 'prediction' | 'error' | 'complete';
  stats?: RiskStats;
}

interface StormMonitorProps {
  cells?: GeoCell[];
  mapCells?: any[];
  historicalEvents?: any[];
  eventLayers?: any[];
  infrastructure?: any;
  nh10Route?: any[];
  routeSafety?: string;
  selectedCell?: any;
  selectedCellId?: string | null;
  onCellSelect?: (cellId: string | null) => void;
  onSimulationUpdate?: (cells: any[]) => void;
}

const RISK_COLORS: Record<string, string> = { critical: '#ef4444', high: '#f97316', moderate: '#f59e0b', low: '#10b981' };

const SCENARIO_STEPS: ScenarioStep[] = [
  { time: 'T+0', description: 'Baseline development scenario with low rainfall loading.', inputs: { rainfall_1h: 2, rainfall_3h: 8, rainfall_6h: 15, rainfall_24h: 25, antecedent_rainfall: 35, soil_moisture: 0.35 } },
  { time: 'T+10', description: 'Rainfall loading increases across monitored cells.', inputs: { rainfall_1h: 8, rainfall_3h: 25, rainfall_6h: 48, rainfall_24h: 80, antecedent_rainfall: 115, soil_moisture: 0.52 } },
  { time: 'T+20', description: 'Heavy scenario rainfall produces higher antecedent loading.', inputs: { rainfall_1h: 18, rainfall_3h: 64, rainfall_6h: 120, rainfall_24h: 180, antecedent_rainfall: 260, soil_moisture: 0.72 } },
  { time: 'T+30', description: 'Extreme demonstration scenario with high saturation inputs.', inputs: { rainfall_1h: 32, rainfall_3h: 110, rainfall_6h: 220, rainfall_24h: 320, antecedent_rainfall: 430, soil_moisture: 0.88 } },
];

const INPUT_FIELDS: { key: keyof ScenarioFeatures; label: string; unit: string; step: string; max?: number }[] = [
  { key: 'rainfall_1h', label: 'Rainfall 1h', unit: 'mm', step: '0.1' },
  { key: 'rainfall_3h', label: 'Rainfall 3h', unit: 'mm', step: '0.1' },
  { key: 'rainfall_6h', label: 'Rainfall 6h', unit: 'mm', step: '0.1' },
  { key: 'rainfall_24h', label: 'Rainfall 24h', unit: 'mm', step: '0.1' },
  { key: 'antecedent_rainfall', label: 'Antecedent Rain', unit: 'mm', step: '0.1' },
  { key: 'soil_moisture', label: 'Soil Moisture', unit: 'index', step: '0.01', max: 1 },
];

function aspectToDegrees(aspect: string | number | undefined): number | null {
  if (typeof aspect === 'number') return aspect;
  if (!aspect) return null;
  return ({ N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 } as Record<string, number>)[aspect.toUpperCase()] ?? null;
}

function calculateStats(predictions: RiskPrediction[]): RiskStats {
  const stats = predictions.reduce((result, prediction) => {
    const level = prediction.risk_class.toLowerCase() as 'critical' | 'high' | 'moderate' | 'low';
    result[level] += 1;
    result.average += prediction.risk_score;
    if (prediction.warning_ready) result.warningReady += 1;
    return result;
  }, { average: 0, critical: 0, high: 0, moderate: 0, low: 0, warningReady: 0 } as RiskStats);
  return { ...stats, average: predictions.length ? stats.average / predictions.length : 0 };
}

function buildCellPayload(cell: GeoCell, inputs: ScenarioFeatures): RiskPredictionRequest {
  return { cell_id: cell.location_id, lat: cell.centroid_lat ?? null, lon: cell.centroid_lon ?? null, ...inputs, elevation: cell.elevation_m ?? null, slope: cell.slope_angle ?? null, aspect: aspectToDegrees(cell.aspect), historical_susceptibility: cell.base_susceptibility ?? null };
}

function mergePredictions(cells: GeoCell[], predictions: RiskPrediction[], inputs: ScenarioFeatures): any[] {
  const byCellId = new Map(predictions.map(prediction => [prediction.cell_id, prediction]));
  return cells.map(cell => {
    const scenarioCell = JSON.parse(JSON.stringify(cell)) as GeoCell;
    const prediction = byCellId.get(cell.location_id);
    if (!prediction) return scenarioCell;
    return { ...scenarioCell, risk_score: prediction.risk_score, risk_level: prediction.risk_level, risk_class: prediction.risk_class, drivers: prediction.drivers, predictor: prediction.predictor, predictor_type: prediction.predictor_type, contributing_factors: prediction.contributing_factors, rainfall: { rainfall_1h: inputs.rainfall_1h, rainfall_3h: inputs.rainfall_3h, rainfall_6h: inputs.rainfall_6h, rainfall_24h_mm: inputs.rainfall_24h, antecedent_rainfall: inputs.antecedent_rainfall, soil_moisture_index: inputs.soil_moisture } };
  });
}

function getRiskClass(score: number): string {
  if (score >= 75) return 'CRITICAL';
  if (score >= 55) return 'HIGH';
  if (score >= 35) return 'MODERATE';
  return 'LOW';
}

export function StormSimulator({ cells = [], mapCells = [], historicalEvents = [], eventLayers = [], infrastructure = {}, nh10Route = [], routeSafety = 'UNKNOWN', selectedCell, selectedCellId, onCellSelect, onSimulationUpdate }: StormMonitorProps) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [scenarioIndex, setScenarioIndex] = useState(0);
  const [scenarioInputs, setScenarioInputs] = useState<ScenarioFeatures>(SCENARIO_STEPS[0].inputs);
  const [predictions, setPredictions] = useState<RiskPrediction[]>([]);
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [rainfallHistory, setRainfallHistory] = useState<{ time: string; rainfall24h: number; averageRisk: number }[]>([]);
  const [isPredicting, setIsPredicting] = useState(false);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState<RiskStats | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const runRef = useRef(false);
  const requestIdRef = useRef(0);
  const currentStep = SCENARIO_STEPS[scenarioIndex];
  const currentStats = useMemo(() => calculateStats(predictions), [predictions]);
  const highestRiskPrediction = useMemo(() => [...predictions].sort((left, right) => right.risk_score - left.risk_score)[0], [predictions]);
  const initialSimulationCellsRef = useRef<any[] | null>(null);

  const runPrediction = useCallback(async (inputs: ScenarioFeatures, time: string, recordEvent = true) => {
    const requestId = ++requestIdRef.current;
    if (!cells.length) { setError('No monitoring cells are available for this region.'); return null; }
    setIsPredicting(true);
    setError('');
    try {
      const response = await predictRiskBatch<RiskPrediction>(cells.map(cell => buildCellPayload(cell, inputs)));
      if (requestId !== requestIdRef.current) return null;
      const nextStats = calculateStats(response.predictions);
      const nextSimulationCells = mergePredictions(cells, response.predictions, inputs);
      if (!initialSimulationCellsRef.current) initialSimulationCellsRef.current = nextSimulationCells;
      setPredictions(response.predictions);
      setSummary(nextStats);
      onSimulationUpdate?.(nextSimulationCells);
      setRainfallHistory(previous => [...previous.filter(item => item.time !== time), { time, rainfall24h: inputs.rainfall_24h, averageRisk: Number(nextStats.average.toFixed(1)) }]);
      if (recordEvent) setEvents(previous => [...previous, { id: `${time}-${Date.now()}`, time, type: 'prediction', description: `Backend recalculated ${response.predictions.length} spatial cells from scenario inputs.`, stats: nextStats }]);
      return response.predictions;
    } catch (predictionError: any) {
      if (requestId !== requestIdRef.current) return null;
      setError(predictionError?.message || 'Risk prediction request failed.');
      setEvents(previous => [...previous, { id: `error-${Date.now()}`, time, type: 'error', description: 'The backend did not return a new risk result. The last valid map state was preserved.' }]);
      return null;
    } finally {
      if (requestId === requestIdRef.current) setIsPredicting(false);
    }
  }, [cells, onSimulationUpdate]);

  useEffect(() => { if (cells.length) runPrediction(SCENARIO_STEPS[0].inputs, 'T+0', false); }, [cells, runPrediction]);

  const updateInputs = (key: keyof ScenarioFeatures, value: number) => {
    runRef.current = false;
    setIsStreaming(false);
    const nextInputs = { ...scenarioInputs, [key]: value };
    setScenarioInputs(nextInputs);
    runPrediction(nextInputs, currentStep.time);
  };

  const selectScenario = (index: number) => {
    runRef.current = false;
    setIsStreaming(false);
    setScenarioIndex(index);
    setScenarioInputs(SCENARIO_STEPS[index].inputs);
    runPrediction(SCENARIO_STEPS[index].inputs, SCENARIO_STEPS[index].time);
  };

  const startSimulation = async () => {
    if (isStreaming || !cells.length) return;
    runRef.current = true;
    setIsStreaming(true);
    setEvents(previous => [...previous, { id: `start-${Date.now()}`, time: currentStep.time, type: 'scenario', description: 'Development scenario playback started. Every step is sent through the backend risk pipeline.' }]);
    for (let index = scenarioIndex; index < SCENARIO_STEPS.length && runRef.current; index += 1) {
      const step = SCENARIO_STEPS[index];
      setScenarioIndex(index);
      setScenarioInputs(step.inputs);
      await runPrediction(step.inputs, step.time);
      if (runRef.current && index < SCENARIO_STEPS.length - 1) await new Promise(resolve => setTimeout(resolve, 1800));
    }
    if (runRef.current) setEvents(previous => [...previous, { id: `complete-${Date.now()}`, time: 'COMPLETE', type: 'complete', description: 'Scenario playback complete. The final development risk state remains on the map.', stats: summary || currentStats }]);
    runRef.current = false;
    setIsStreaming(false);
  };

  const resetSimulation = async () => {
    runRef.current = false;
    setIsStreaming(false);
    setScenarioIndex(0);
    setScenarioInputs(SCENARIO_STEPS[0].inputs);
    setEvents([]);
    setRainfallHistory([]);
    setSummary(null);
    setPredictions([]);
    if (initialSimulationCellsRef.current) onSimulationUpdate?.(initialSimulationCellsRef.current);
    await runPrediction(SCENARIO_STEPS[0].inputs, 'T+0');
  };

  const handleSaveRecord = async () => {
    try {
      const response = await rpcCall({ func: 'save_simulation_record', args: { summary, events } });
      setToastMessage(response.message);
      setTimeout(() => setToastMessage(null), 3000);
    } catch (saveError) {
      console.error(saveError);
      setError('Unable to save the scenario record.');
    }
  };

  const progress = ((scenarioIndex + (predictions.length ? 1 : 0)) / SCENARIO_STEPS.length) * 100;
  const primaryRiskClass = getRiskClass(currentStats.average);
  const spatialCells = mapCells.length ? mapCells : cells;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 h-full p-2 relative">
      {toastMessage && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-[9999] animate-in fade-in slide-in-from-top-8 duration-300">
          <div className="flex items-center gap-3 rounded-full border border-emerald-500/40 bg-[#0c0c0e]/80 backdrop-blur-xl px-6 py-3.5 shadow-[0_0_40px_-10px_rgba(16,185,129,0.3)]">
            <CheckCircle className="h-5 w-5 text-emerald-400" />
            <span className="text-sm font-bold text-white tracking-wide">{toastMessage}</span>
          </div>
        </div>
      )}

      <div className="xl:col-span-2 space-y-6">
        <Card className="bg-[#131313] border-border/20 rounded-xl overflow-hidden shadow-xl">
          <CardHeader className="p-6 pb-4">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
              <div><CardTitle className="text-xl font-bold flex items-center gap-2 text-primary"><Activity className="h-5 w-5" /> Development Risk Scenario</CardTitle><CardDescription className="text-sm mt-1">Backend-calculated scenario inputs for spatial risk-state development</CardDescription></div>
              <div className="flex gap-2">{isStreaming ? <Button onClick={() => { runRef.current = false; setIsStreaming(false); }} variant="destructive" className="font-bold rounded-md flex items-center gap-2"><Square className="h-4 w-4" /> Pause</Button> : <Button onClick={startSimulation} disabled={isPredicting || !cells.length} className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold rounded-md flex items-center gap-2"><Play className="h-4 w-4 fill-current" /> Start</Button>}<Button onClick={resetSimulation} variant="outline" disabled={isPredicting && !predictions.length} className="font-bold rounded-md flex items-center gap-2"><RotateCcw className="h-4 w-4" /> Reset</Button></div>
            </div>
          </CardHeader>
          <CardContent className="p-6 pt-0 space-y-6">
            <div className="flex items-center justify-between gap-4 bg-black/40 rounded-lg p-4 border border-border/10"><div><div className="flex items-center gap-2 mb-1"><Badge className="bg-blue-500/15 text-blue-300 border border-blue-500/30">DEMO SCENARIO</Badge><span className="text-[11px] uppercase tracking-widest text-muted-foreground">Scenario Time</span></div><div className="text-xl font-black text-white">{currentStep.time}</div></div><div className="min-w-[160px] text-right"><div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-2">Pipeline Progress</div><Progress value={progress} className="h-2" /><div className="text-[10px] text-muted-foreground mt-1">{Math.round(progress)}%</div></div></div>
            <div className="grid grid-cols-4 gap-2">{SCENARIO_STEPS.map((step, index) => <button key={step.time} onClick={() => selectScenario(index)} disabled={isPredicting} className={cn('rounded-lg border px-3 py-2 text-left transition-all', scenarioIndex === index ? 'border-primary/70 bg-primary/10 text-primary' : 'border-border/30 bg-card/40 text-muted-foreground hover:border-primary/40')}><div className="text-xs font-bold">{step.time}</div><div className="text-[10px] mt-1 line-clamp-2">{step.description}</div></button>)}</div>
            <div className="rounded-xl border border-border/30 bg-black/25 p-4 space-y-4"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground"><SlidersHorizontal className="h-4 w-4 text-primary" /> Environmental Inputs</div><span className="text-[10px] text-blue-300 uppercase tracking-wider">Demo values, not observations</span></div><div className="grid grid-cols-2 md:grid-cols-3 gap-3">{INPUT_FIELDS.map(field => <label key={field.key} className="space-y-1.5"><span className="text-[10px] text-muted-foreground uppercase tracking-wider">{field.label}</span><div className="flex items-center gap-2"><input type="number" min="0" max={field.max} step={field.step} value={scenarioInputs[field.key]} onChange={event => updateInputs(field.key, Number(event.target.value))} className="w-full rounded-md border border-border/40 bg-background/50 px-2.5 py-2 text-sm text-white outline-none focus:border-primary/70" /><span className="text-[10px] text-muted-foreground min-w-fit">{field.unit}</span></div></label>)}</div><div className="text-[11px] text-muted-foreground">{currentStep.description} Changing any value sends the complete spatial feature payload to the backend again.</div></div>
            {error && <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-950/20 p-3 text-xs text-red-300"><AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" /><span>{error}</span><button onClick={() => runPrediction(scenarioInputs, currentStep.time)} className="ml-auto underline">Retry</button></div>}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">{(['critical', 'high', 'moderate', 'low'] as const).map(level => <div key={level} className="rounded-lg border border-border/20 bg-card/40 p-3"><div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-muted-foreground"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: RISK_COLORS[level] }} /> {level}</div><div className="text-2xl font-black mt-1">{currentStats[level]}</div></div>)}</div>
            <div className="rounded-xl border border-primary/30 bg-primary/5 p-4"><div className="flex items-start justify-between gap-4"><div><div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-primary"><Shield className="h-4 w-4" /> Calculated Development Risk</div><div className="flex items-baseline gap-3 mt-2"><span className="text-3xl font-black" style={{ color: RISK_COLORS[primaryRiskClass.toLowerCase()] }}>{primaryRiskClass}</span><span className="font-mono text-lg text-white">{currentStats.average.toFixed(1)}<span className="text-xs text-muted-foreground">/100</span></span></div></div><Badge variant="outline" className="border-blue-400/40 text-blue-300">DEVELOPMENT / RULE-BASED</Badge></div>{highestRiskPrediction?.drivers?.length ? <div className="mt-4 space-y-1.5"><div className="text-[10px] uppercase tracking-widest text-muted-foreground">Risk Drivers</div>{highestRiskPrediction.drivers.slice(0, 4).map(driver => <div key={driver} className="flex items-center gap-2 text-xs text-slate-300"><TrendingUp className="h-3 w-3 text-primary" />{driver}</div>)}</div> : null}</div>
            {rainfallHistory.length > 0 && <div className="space-y-2"><div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5"><CloudRain className="h-3 w-3 text-blue-400" /> Scenario Input and Risk Timeline</div><div className="h-[150px] bg-muted/10 rounded-lg p-2 border border-border/20"><ResponsiveContainer width="100%" height="100%"><LineChart data={rainfallHistory}><XAxis dataKey="time" tick={{ fontSize: 9, fill: '#64748b' }} /><YAxis tick={{ fontSize: 9, fill: '#64748b' }} width={35} /><Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '11px' }} /><Line type="monotone" dataKey="rainfall24h" name="Rainfall 24h (mm)" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} /><Line type="monotone" dataKey="averageRisk" name="Average development risk" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div></div>}
            <ScrollArea className="h-[250px]"><div className="space-y-2 pr-2">{events.map(event => <div key={event.id} className={cn('flex gap-3 p-3 rounded-lg border', event.type === 'error' ? 'border-red-800/50 bg-red-950/20' : event.type === 'complete' ? 'border-emerald-800/50 bg-emerald-950/20' : 'border-border/30 bg-card/40')}><div className="mt-0.5 shrink-0">{event.type === 'error' ? <AlertTriangle className="h-4 w-4 text-red-400" /> : event.type === 'complete' ? <CheckCircle className="h-4 w-4 text-emerald-400" /> : <Activity className="h-4 w-4 text-blue-400" />}</div><div className="min-w-0 flex-1"><div className="flex justify-between gap-2"><span className="text-xs font-bold text-slate-300">{event.time}</span>{event.stats && <span className="text-[10px] text-muted-foreground">Avg {event.stats.average.toFixed(1)}</span>}</div><p className="text-[11px] text-muted-foreground mt-1">{event.description}</p></div></div>)}{isPredicting && <div className="flex items-center justify-center p-4 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin mr-2" /> Sending spatial features to backend...</div>}</div></ScrollArea>
          </CardContent>
        </Card>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-[#131313] border-border/20 rounded-xl shadow-xl"><CardHeader className="p-5 pb-3"><CardTitle className="text-[13px] font-bold uppercase tracking-widest text-white">Risk Pipeline</CardTitle></CardHeader><CardContent className="p-5 pt-0 space-y-4">{['Scenario inputs', 'Feature construction and normalization', 'Development risk predictor', 'Shared spatial map state', 'Warning-ready output'].map((item, index) => <div key={item} className="flex items-center gap-3 text-xs text-slate-300"><span className="h-6 w-6 rounded-full bg-primary/15 text-primary flex items-center justify-center font-bold">{index + 1}</span>{item}</div>)}<div className="rounded-lg border border-blue-500/20 bg-blue-950/15 p-3 text-[11px] text-blue-200/80">The current predictor is a deterministic development heuristic. A future validated ML predictor can replace it behind the same API contract.</div></CardContent></Card>
          <Card className="bg-[#131313] border-border/20 rounded-xl shadow-xl"><CardHeader className="p-5 pb-3"><CardTitle className="text-[13px] font-bold uppercase tracking-widest text-white">Scenario Output</CardTitle></CardHeader><CardContent className="p-5 pt-0 space-y-4"><div className="flex items-center gap-3"><div className="h-10 w-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center"><Droplets className="h-5 w-5 text-blue-400" /></div><div><div className="text-sm font-bold text-white">{cells.length} spatial cells</div><div className="text-[10px] text-muted-foreground">Updated from the latest backend result</div></div></div><div className="grid grid-cols-2 gap-3 text-[11px]"><div className="rounded-lg bg-white/5 p-3"><div className="text-muted-foreground uppercase">Warning-ready</div><div className="text-lg font-black text-orange-400">{currentStats.warningReady}</div></div><div className="rounded-lg bg-white/5 p-3"><div className="text-muted-foreground uppercase">Predictor</div><div className="text-sm font-bold text-blue-300">Development</div></div></div><Button onClick={handleSaveRecord} variant="outline" className="w-full flex items-center gap-2"><RefreshCw className="h-4 w-4" /> Save Scenario Record</Button></CardContent></Card>
        </div>
      </div>
      <div className="space-y-6">
        <Card className="bg-[#131313] border-border/20 rounded-xl shadow-xl overflow-hidden">
          <CardHeader className="p-5 pb-3 border-b border-border/20">
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle className="text-[13px] font-bold uppercase tracking-widest text-white">Scenario Risk Map</CardTitle>
                <CardDescription className="text-[11px] mt-1">DEMO SCENARIO — SPATIAL RISK</CardDescription>
              </div>
              <Badge variant="outline" className="border-blue-400/40 text-blue-300 text-[10px]">RULE-BASED</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="relative h-[560px] min-h-[460px] w-full">
              <GeospatialViewer
                cells={spatialCells as any}
                historicalEvents={historicalEvents}
                eventLayers={eventLayers}
                infrastructure={infrastructure}
                nh10Route={nh10Route}
                routeSafety={routeSafety}
                initialSelectedCellId={selectedCellId}
                onCellClick={(cell) => onCellSelect?.(cell?.location_id || null)}
              />
              {isPredicting && (
                <div className="absolute inset-0 z-20 flex items-start justify-center pointer-events-none pt-4">
                  <div className="flex items-center gap-2 rounded-full border border-blue-400/30 bg-slate-950/85 px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-blue-200 shadow-xl">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Calculating scenario...
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {selectedCell && (
          <Card className="bg-[#131313] border-border/20 rounded-xl shadow-xl">
            <CardHeader className="p-5 pb-2"><CardTitle className="text-[13px] font-bold uppercase tracking-widest text-white">Selected Scenario Cell</CardTitle></CardHeader>
            <CardContent className="p-5 pt-2"><XAIPanel cell={selectedCell} onClose={() => onCellSelect?.(null)} /></CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
