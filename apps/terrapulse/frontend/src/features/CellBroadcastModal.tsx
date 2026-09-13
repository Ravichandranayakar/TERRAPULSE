import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  prepareCellBroadcast,
  simulateCellBroadcast,
  type CellBroadcastPreparation,
  type CellBroadcastSimulation,
} from '../api';
import { Dialog, DialogContent } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import GeospatialViewer from './GeospatialViewer';
import { AlertTriangle, Loader2, RadioTower, X } from 'lucide-react';

type BroadcastPhase = 'targeting' | 'dispatching' | 'confirmed' | 'failed';

interface BroadcastWarning {
  id: number;
  location_id: string;
  location_name: string;
  timestamp: string;
  risk_level: string;
  risk_score: number;
  trigger_factors?: any[];
  affected_infrastructure?: string[];
  district?: string;
  state?: string;
}

interface CellBroadcastModalProps {
  warning: BroadcastWarning;
  cells: any[];
  historicalEvents?: any[];
  eventLayers?: any[];
  infrastructure?: any;
  nh10Route?: any[];
  routeSafety?: string;
  onClose: () => void;
}

const TARGET_SOURCE_LABELS: Record<string, string> = {
  warning_geometry: 'Warning geometry',
  risk_cells: 'Risk-cell aggregation',
  event_geometry: 'Observed event geometry',
  selected_cell: 'Selected risk cell',
  demo: 'Demo fallback',
};

const DISPATCH_LOGS = [
  '[00:00] Loading warning record...',
  '[00:01] Validating target geometry...',
  '[00:02] Generating CAP-compatible alert payload...',
  '[00:03] Preparing Cell Broadcast message...',
  '[00:04] Resolving target geographic cells...',
  '[00:05] Network integration mode: SIMULATION',
  '[00:06] Telecom gateway connection: NOT CONNECTED',
  '[00:07] Simulating cell targeting...',
  '[00:08] Simulating multilingual broadcast payload...',
  '[00:09] Simulating escalation workflow...',
  '[00:10] Dispatch simulation completed',
];

const ESCALATION_ENTITIES = [
  'District administration',
  'Road authority / control room',
  'Police / emergency response',
  'State disaster management authority',
];

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function formatDateTime(value?: string) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function CellBroadcastModal({
  warning,
  cells,
  historicalEvents = [],
  eventLayers = [],
  infrastructure = {},
  nh10Route = [],
  routeSafety = 'UNKNOWN',
  onClose,
}: CellBroadcastModalProps) {
  const [phase, setPhase] = useState<BroadcastPhase>('targeting');
  const [isPreparing, setIsPreparing] = useState(true);
  const [preparation, setPreparation] = useState<CellBroadcastPreparation | null>(null);
  const [simulationResult, setSimulationResult] = useState<CellBroadcastSimulation | null>(null);
  const [language, setLanguage] = useState('en');
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [reportToast, setReportToast] = useState(false);

  const activeResult = simulationResult || preparation;
  const target = activeResult?.target;
  const payload = activeResult?.payload;
  const selectedMessage = payload?.messages.find(message => message.language === language) || payload?.messages[0];
  const targetGeometry = target?.geometry
    ? { geometry: target.geometry, source: target.source, label: 'BROADCAST TARGET' }
    : null;
  const escalation = simulationResult?.escalation || ESCALATION_ENTITIES.map(entity => ({ entity, status: 'PENDING' }));

  const loadPreparation = useCallback(async () => {
    setIsPreparing(true);
    setPhase('targeting');
    setError('');
    setSimulationResult(null);
    setLogs([]);
    try {
      const result = await prepareCellBroadcast(warning.id);
      setPreparation(result);
      setIsPreparing(false);
    } catch (prepareError: any) {
      setPreparation(null);
      setIsPreparing(false);
      setPhase('failed');
      setError(prepareError?.message || 'Unable to prepare the broadcast simulation.');
    }
  }, [warning.id]);

  useEffect(() => {
    loadPreparation();
  }, [loadPreparation]);

  const runDispatch = useCallback(async () => {
    if (!preparation) return;
    setConfirming(false);
    setPhase('dispatching');
    setError('');
    setLogs([]);

    const simulationPromise = simulateCellBroadcast(warning.id);
    try {
      for (const log of DISPATCH_LOGS) {
        setLogs(previous => [...previous, log]);
        await delay(130);
      }
      const result = await simulationPromise;
      setSimulationResult(result);
      setPhase('confirmed');
    } catch (dispatchError: any) {
      setPhase('failed');
      setError(dispatchError?.message || 'Dispatch simulation failed.');
    }
  }, [preparation, warning.id]);

  const retry = useCallback(() => {
    if (preparation) {
      runDispatch();
    } else {
      loadPreparation();
    }
  }, [loadPreparation, preparation, runDispatch]);

  const statusTone = phase === 'confirmed'
    ? 'border-emerald-500/50 bg-emerald-950/40 text-emerald-300'
    : phase === 'failed'
      ? 'border-red-500/50 bg-red-950/40 text-red-300'
      : 'border-amber-500/50 bg-amber-950/40 text-amber-300';

  const mapSection = useMemo(() => (
    <div className="h-[320px] overflow-hidden rounded-xl border border-border/50 bg-slate-950">
      <GeospatialViewer
        cells={cells}
        historicalEvents={historicalEvents}
        eventLayers={eventLayers}
        infrastructure={infrastructure}
        nh10Route={nh10Route}
        routeSafety={routeSafety}
        targetGeometry={targetGeometry}
        highlightCellId={warning.location_id}
      />
    </div>
  ), [cells, eventLayers, historicalEvents, infrastructure, nh10Route, routeSafety, targetGeometry, warning.location_id]);

  return (
    <Dialog open onOpenChange={open => !open && onClose()}>
      <DialogContent
        className="w-screen h-screen max-w-none p-0 gap-0 overflow-y-auto rounded-none border-border/60 bg-[#08090c] text-white"
        aria-label="Cell Broadcast dispatch simulation"
      >
        <div className="sticky top-0 z-20 border-b border-red-900/60 bg-gradient-to-r from-red-950 via-amber-950 to-red-950">
          <div className="flex min-h-16 flex-col justify-center gap-2 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <RadioTower className="h-6 w-6 text-amber-300" />
              <div>
                <h2 className="text-lg font-black uppercase tracking-[0.18em]">⚠ Cell Broadcast Simulation</h2>
                <p className="text-[11px] font-bold uppercase tracking-widest text-amber-300">
                  Demo mode · No live network connection
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-widest ${statusTone}`}>
                {phase === 'targeting' ? 'Targeting' : phase === 'dispatching' ? 'Dispatching' : phase === 'confirmed' ? 'Simulation complete' : 'Simulation failed'}
              </span>
              <button
                onClick={onClose}
                aria-label="Close Cell Broadcast simulation"
                className="rounded-full border border-white/20 p-2 text-white/80 transition hover:bg-white/10 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-2 2xl:grid-cols-3">
          <section className="rounded-xl border border-border/50 bg-black/50 p-4" aria-labelledby="broadcast-targeting">
            <div className="flex items-center justify-between gap-3">
              <h3 id="broadcast-targeting" className="text-sm font-black uppercase tracking-widest text-amber-300">Geofence Targeting</h3>
              {isPreparing && <Loader2 className="h-4 w-4 animate-spin text-amber-300" />}
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
              <div><dt className="text-muted-foreground">Location</dt><dd className="font-bold">{warning.location_name}</dd></div>
              <div><dt className="text-muted-foreground">District</dt><dd className="font-bold">{target?.district || warning.district || '—'}</dd></div>
              <div><dt className="text-muted-foreground">State</dt><dd className="font-bold">{target?.state || warning.state || '—'}</dd></div>
              <div><dt className="text-muted-foreground">Warning type</dt><dd className="font-bold">Landslide risk</dd></div>
              <div><dt className="text-muted-foreground">Risk level</dt><dd className="font-bold uppercase text-amber-300">{warning.risk_level}</dd></div>
              <div><dt className="text-muted-foreground">Risk score</dt><dd className="font-mono font-bold">{warning.risk_score?.toFixed(1)}</dd></div>
            </dl>

            <div className="mt-3 rounded-lg border border-amber-700/50 bg-amber-950/30 p-3">
              <div className="text-[10px] font-black uppercase tracking-widest text-amber-300">Target source</div>
              <div className="mt-1 text-sm font-bold">{TARGET_SOURCE_LABELS[target?.source || 'demo'] || 'Demo fallback'}</div>
              <p className="mt-1 text-[10px] text-amber-200/80">
                {target?.geometry ? 'Boundary follows the available application geometry.' : 'No precise geometry is available; no synthetic footprint is drawn.'}
              </p>
            </div>

            <div className="mt-3">{mapSection}</div>

            <div className="mt-3 rounded-lg border border-blue-900/60 bg-blue-950/20 p-3">
              <div className="text-[10px] font-black uppercase tracking-widest text-blue-300">Affected infrastructure</div>
              <div className="mt-1 text-xs text-blue-100">
                {target?.affected_infrastructure?.length
                  ? target.affected_infrastructure.join(', ')
                  : 'No infrastructure exposure recorded'}
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-border/50 bg-black/50 p-4" aria-labelledby="broadcast-payload">
            <h3 id="broadcast-payload" className="text-sm font-black uppercase tracking-widest text-blue-300">Cell Broadcast Payload</h3>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground">3GPP TS 23.041 · CAP-COMPATIBLE ALERT</p>

            {payload ? (
              <>
                <Tabs value={language} onValueChange={setLanguage} className="mt-3">
                  <TabsList className="bg-black/60">
                    {payload.languages.map(code => (
                      <TabsTrigger key={code} value={code} className="text-xs font-bold uppercase">{code}</TabsTrigger>
                    ))}
                  </TabsList>
                  {payload.messages.map(message => (
                    <TabsContent key={message.language} value={message.language}>
                      <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/20 p-3 font-mono text-xs text-emerald-100">
                        <div className="whitespace-pre-line">{message.headline}</div>
                        <div className="mt-2 whitespace-pre-line text-emerald-50/90">{message.description}</div>
                        <div className="mt-2 whitespace-pre-line text-emerald-200/80">{message.instruction}</div>
                      </div>
                    </TabsContent>
                  ))}
                </Tabs>

                <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
                  <div><dt className="text-muted-foreground">Event</dt><dd className="font-bold">Landslide Risk Warning</dd></div>
                  <div><dt className="text-muted-foreground">Severity</dt><dd className="font-bold">{payload.severity}</dd></div>
                  <div><dt className="text-muted-foreground">Urgency</dt><dd className="font-bold">{payload.urgency}</dd></div>
                  <div><dt className="text-muted-foreground">Certainty</dt><dd className="font-bold">{payload.certainty}</dd></div>
                  <div><dt className="text-muted-foreground">Area</dt><dd className="font-bold">{payload.area}</dd></div>
                  <div><dt className="text-muted-foreground">Message ID</dt><dd className="font-mono font-bold">{simulationResult?.broadcast_id || 'DEMO-CBS-01'}</dd></div>
                  <div><dt className="text-muted-foreground">Effective</dt><dd className="font-mono">{formatDateTime(payload.effective)}</dd></div>
                  <div><dt className="text-muted-foreground">Expires</dt><dd className="font-mono">{formatDateTime(payload.expires)}</dd></div>
                </dl>

                <div className="mt-4 rounded-lg border border-border/50 bg-black/70 p-3">
                  <div className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Escalation workflow</div>
                  <div className="mt-2 space-y-2">
                    {escalation.map(item => (
                      <div key={item.entity} className="flex items-center justify-between gap-3 text-xs">
                        <span className="text-slate-200">{item.entity}</span>
                        <span className={`font-mono font-bold ${item.status === 'SIMULATED' ? 'text-emerald-300' : 'text-amber-300'}`}>{item.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Preparing warning payload...
              </div>
            )}
          </section>

          <section className="rounded-xl border border-border/50 bg-black/50 p-4" aria-labelledby="device-preview">
            <h3 id="device-preview" className="text-sm font-black uppercase tracking-widest text-emerald-300">Device Preview</h3>
            <div className="mt-4 mx-auto w-[280px] rounded-[2rem] border-4 border-slate-700 bg-black p-3 shadow-2xl">
              <div className="mx-auto mb-3 h-1.5 w-16 rounded-full bg-slate-700" />
              <div className="rounded-xl bg-white p-4 text-black">
                <div className="rounded-lg bg-red-600 p-3 text-white">
                  <div className="text-[10px] font-black uppercase tracking-widest">Emergency Alert</div>
                  <div className="mt-1 text-xs font-bold">SIMULATION PREVIEW</div>
                </div>
                <div className="mt-3 space-y-2 text-xs">
                  <p className="font-bold">{selectedMessage?.headline || 'Landslide Warning'}</p>
                  <p>{selectedMessage?.description || 'Preparing alert message...'}</p>
                  <p>{selectedMessage?.instruction || 'Follow instructions from local authorities.'}</p>
                </div>
                <div className="mt-4 border-t border-slate-200 pt-2 text-[10px] text-slate-600">
                  <div>Issued by: TerraPulse Emergency Warning System</div>
                  <div>Mode: SIMULATION</div>
                </div>
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-border/50 bg-black/70 p-3">
              <div className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Network simulation</div>
              <p className="mt-1 text-xs text-amber-300">
                Telecom delivery unavailable in prototype — network integration simulated.
              </p>
              <div className="mt-2 grid grid-cols-2 gap-2 font-mono text-[11px] text-slate-300">
                <div>Target cells: {simulationResult?.network_simulation.target_cells.length ?? 0}</div>
                <div>Devices: unavailable</div>
                <div>Population: unavailable</div>
                <div>Live network: NO</div>
              </div>
            </div>

            {phase === 'dispatching' || simulationResult ? (
              <div className="mt-4 rounded-lg border border-emerald-900/60 bg-black/80 p-3">
                <div className="text-[10px] font-black uppercase tracking-widest text-emerald-300">Simulation log</div>
                <div className="mt-2 max-h-44 space-y-1 overflow-y-auto font-mono text-[10px] text-emerald-200">
                  {(logs.length ? logs : simulationResult?.simulation_logs || []).map((log, index) => (
                    <div key={`${log}-${index}`}>{log}</div>
                  ))}
                </div>
              </div>
            ) : null}

            {phase === 'confirmed' && simulationResult && (
              <div className="mt-4 space-y-3">
                <div className="rounded-lg border border-emerald-800/60 bg-emerald-950/30 p-3">
                  <div className="text-[10px] font-black uppercase tracking-widest text-emerald-300">Simulation complete</div>
                  <div className="mt-1 font-mono text-sm font-bold text-emerald-200">{simulationResult.broadcast_id}</div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-emerald-100">
                    <div>1 target region</div>
                    <div>{simulationResult.payload.languages.length} languages</div>
                    <div>{simulationResult.escalation.length} escalation steps</div>
                    <div>1 warning processed</div>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setReportToast(true);
                    setTimeout(() => setReportToast(false), 2500);
                  }}
                  className="w-full rounded-lg border border-emerald-700/60 bg-emerald-950/40 px-4 py-2 text-xs font-bold uppercase tracking-widest text-emerald-300 transition hover:bg-emerald-900/40"
                >
                  View Dispatch Simulation Report
                </button>
                {reportToast && (
                  <div className="rounded-lg border border-emerald-700/60 bg-emerald-950/50 p-2 text-center text-xs text-emerald-200">
                    Simulation report generated
                  </div>
                )}
              </div>
            )}
          </section>
        </div>

        {phase === 'failed' && (
          <div className="mx-4 mb-4 rounded-xl border border-red-800/70 bg-red-950/40 p-4">
            <div className="flex items-center gap-2 text-sm font-black uppercase tracking-widest text-red-300">
              <AlertTriangle className="h-4 w-4" /> Dispatch simulation failed
            </div>
            <p className="mt-2 text-xs text-red-200">{error}</p>
            <div className="mt-3 flex gap-2">
              <button onClick={retry} className="rounded-lg border border-red-700/60 bg-red-950/50 px-4 py-2 text-xs font-bold uppercase text-red-200 hover:bg-red-900/40">Retry</button>
              <button onClick={onClose} className="rounded-lg border border-white/20 px-4 py-2 text-xs font-bold uppercase text-slate-200 hover:bg-white/10">Close</button>
            </div>
          </div>
        )}

        <div className="sticky bottom-0 border-t border-amber-900/60 bg-black/90 px-4 py-3 backdrop-blur">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-[11px] font-black uppercase tracking-widest text-amber-300">
              Demo only — no telecom broadcast will be transmitted
            </div>
            <div className="flex gap-2">
              <button onClick={onClose} className="rounded-lg border border-white/20 px-4 py-2 text-xs font-bold uppercase tracking-widest text-slate-200 hover:bg-white/10">Cancel</button>
              <button
                onClick={() => setConfirming(true)}
                disabled={phase !== 'targeting' || isPreparing || !preparation}
                className="flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-xs font-black uppercase tracking-widest text-black transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {phase === 'dispatching' ? <Loader2 className="h-4 w-4 animate-spin" /> : <RadioTower className="h-4 w-4" />}
                Simulate Cell Broadcast
              </button>
            </div>
          </div>
        </div>

        {confirming && phase === 'targeting' && preparation && (
          <div
            className="absolute inset-0 z-30 flex items-center justify-center bg-black/85 p-4"
            role="dialog"
            aria-modal="true"
            aria-labelledby="simulation-confirmation"
            onKeyDown={event => {
              if (event.key === 'Enter') runDispatch();
            }}
          >
            <div className="w-full max-w-md rounded-xl border border-amber-700/60 bg-[#0c0d10] p-5">
              <h3 id="simulation-confirmation" className="text-sm font-black uppercase tracking-widest text-amber-300">Simulation confirmation</h3>
              <dl className="mt-4 space-y-2 text-xs">
                <div className="flex justify-between"><dt className="text-muted-foreground">Target</dt><dd className="font-bold">{target?.district || warning.location_name} / {target?.state || warning.state || '—'}</dd></div>
                <div className="flex justify-between"><dt className="text-muted-foreground">Risk</dt><dd className="font-bold uppercase">{warning.risk_level}</dd></div>
                <div className="flex justify-between"><dt className="text-muted-foreground">Target source</dt><dd className="font-bold">{TARGET_SOURCE_LABELS[target?.source || 'demo']}</dd></div>
                <div className="flex justify-between"><dt className="text-muted-foreground">Infrastructure</dt><dd className="max-w-[220px] text-right font-bold">{target?.affected_infrastructure?.length || 0} recorded</dd></div>
              </dl>
              <p className="mt-4 rounded-lg border border-amber-800/60 bg-amber-950/30 p-3 text-xs text-amber-200">
                This is a simulation. No telecom broadcast will be transmitted.
              </p>
              <div className="mt-4 flex justify-end gap-2">
                <button onClick={() => setConfirming(false)} className="rounded-lg border border-white/20 px-4 py-2 text-xs font-bold uppercase text-slate-200 hover:bg-white/10">Cancel</button>
                <button onClick={runDispatch} className="rounded-lg bg-amber-500 px-4 py-2 text-xs font-black uppercase text-black hover:bg-amber-400">Simulate Dispatch</button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
