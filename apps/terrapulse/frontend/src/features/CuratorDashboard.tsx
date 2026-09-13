import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  buildTrainingDataset,
  getTrainingBuffer,
  getVerificationReports,
  getVerificationStats,
  reviewVerificationReport,
  rpcCall,
  type TrainingBuffer,
  type VerificationReport,
  type VerificationStats,
} from '../api';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import GeospatialViewer from './GeospatialViewer';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Database,
  Loader2,
  MapPin,
  ShieldCheck,
  X,
} from 'lucide-react';

type ReviewTab = 'pending_review' | 'approved' | 'rejected' | 'needs_more_evidence' | 'buffer';

const HAZARD_LABELS: Record<string, string> = {
  landslide: 'Landslide',
  flood: 'Flood',
  debris_flow: 'Debris Flow',
  other: 'Other Hazard',
  unknown: 'Unknown Hazard',
};

const REJECTION_REASONS = [
  { value: 'incorrect_hazard', label: 'Incorrect hazard' },
  { value: 'incorrect_location', label: 'Incorrect location' },
  { value: 'insufficient_evidence', label: 'Insufficient evidence' },
  { value: 'duplicate', label: 'Duplicate' },
  { value: 'invalid_report', label: 'Invalid report' },
  { value: 'outside_study_area', label: 'Outside study area' },
  { value: 'other', label: 'Other' },
];

function formatTime(value?: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function CuratorDashboard({
  cells,
  historicalEvents,
  eventLayers,
  infrastructure,
  nh10Route,
  routeSafety,
  onPendingCountChange,
}: {
  cells: any[];
  historicalEvents?: any[];
  eventLayers?: any[];
  infrastructure?: any;
  nh10Route?: any[];
  routeSafety?: string;
  onPendingCountChange?: (count: number) => void;
}) {
  const [tab, setTab] = useState<ReviewTab>('pending_review');
  const [reports, setReports] = useState<VerificationReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<VerificationReport | null>(null);
  const [stats, setStats] = useState<VerificationStats | null>(null);
  const [buffers, setBuffers] = useState<TrainingBuffer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [action, setAction] = useState<'approve' | 'reject' | 'evidence' | null>(null);
  const [rejectionReason, setRejectionReason] = useState('insufficient_evidence');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [datasetMessage, setDatasetMessage] = useState('');
  const [creatingDemo, setCreatingDemo] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [nextReports, nextStats, nextBuffers] = await Promise.all([
        tab === 'buffer' ? Promise.resolve([]) : getVerificationReports(tab),
        getVerificationStats(),
        getTrainingBuffer(),
      ]);
      setReports(nextReports);
      setStats(nextStats);
      setBuffers(nextBuffers);
      setSelectedReport(current => current && nextReports.some(report => report.id === current.id)
        ? current
        : nextReports[0] || null);
      onPendingCountChange?.(nextStats.pending_review);
    } catch (loadError: any) {
      setError(loadError?.message || 'Unable to load verification workspace.');
    } finally {
      setLoading(false);
    }
  }, [onPendingCountChange, tab]);

  useEffect(() => {
    load();
  }, [load]);

  const reportPoints = useMemo(() => reports
    .filter(report => report.latitude != null && report.longitude != null)
    .map(report => ({
      id: report.id,
      lat: report.latitude as number,
      lon: report.longitude as number,
      hazardType: report.hazard_type,
      status: report.status,
    })), [reports]);

  const submitDecision = async () => {
    if (!selectedReport || !action) return;
    setSaving(true);
    setError('');
    try {
      await reviewVerificationReport(selectedReport.id, {
        decision: action === 'approve'
          ? 'approved'
          : action === 'reject'
            ? 'rejected'
            : 'needs_more_evidence',
        curator_id: 'admin_operator',
        curator_role: 'admin',
        hazard_type: selectedReport.hazard_type,
        event_presence: selectedReport.event_presence || 'confirmed',
        evidence_quality: selectedReport.evidence_quality || 'medium',
        location_quality: selectedReport.location_quality || 'approximate',
        reason: action === 'reject' ? rejectionReason : undefined,
        notes,
      });
      setAction(null);
      setNotes('');
      await load();
    } catch (decisionError: any) {
      setError(decisionError?.message || 'Curator decision failed.');
    } finally {
      setSaving(false);
    }
  };

  const buildDataset = async (hazardType: string) => {
    setSaving(true);
    setError('');
    try {
      const manifest = await buildTrainingDataset(hazardType, 'admin_operator');
      setDatasetMessage(
        manifest.record_count
          ? `${manifest.dataset_version} created with ${manifest.record_count} records. Training is not automatically run.`
          : `${manifest.dataset_version} created with 0 eligible records.`
      );
      await load();
    } catch (datasetError: any) {
      setError(datasetError?.message || 'Dataset build failed.');
    } finally {
      setSaving(false);
    }
  };

  const createDemoVerification = async () => {
    setCreatingDemo(true);
    setError('');
    try {
      const demoCell = cells[0];
      await rpcCall({
        func: 'submit_field_verification',
        args: {
          warning_id: 0,
          location_id: demoCell?.location_id,
          verified_by: 'demo_operator',
          outcome: 'uncertain',
          notes: 'DEMO DATA — synthetic landslide observation for curator workflow testing.',
          description: 'DEMO DATA — synthetic landslide observation for curator workflow testing.',
          hazard_type: 'landslide',
          source_type: 'demo',
          source_reference: 'curator_demo',
          reporter_role: 'demo',
          reporter_id: 'demo_operator',
          observed_at: new Date().toISOString(),
          event_presence: 'uncertain',
          latitude: demoCell?.centroid_lat ?? 27.645,
          longitude: demoCell?.centroid_lon ?? 88.585,
          location_quality: 'uncertain',
        },
      });
      await load();
    } catch (demoError: any) {
      setError(demoError?.message || 'Demo verification could not be created.');
    } finally {
      setCreatingDemo(false);
    }
  };

  const tabs: { id: ReviewTab; label: string; count?: number }[] = [
    { id: 'pending_review', label: 'Pending Review', count: stats?.pending_review },
    { id: 'approved', label: 'Approved' },
    { id: 'rejected', label: 'Rejected' },
    { id: 'needs_more_evidence', label: 'Needs Evidence', count: stats?.needs_more_evidence },
    { id: 'buffer', label: 'Training Buffer', count: stats?.training_buffer },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="font-heading text-xl font-bold">Human-in-the-Loop Data Curation</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Review, label, and route verified observations into future curated training datasets.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <ShieldCheck className="h-4 w-4 mr-2" />}
          Refresh Queue
        </Button>
        {import.meta.env.DEV && (
          <Button
            variant="outline"
            size="sm"
            onClick={createDemoVerification}
            disabled={creatingDemo || loading}
            className="border-amber-600/50 text-amber-300"
          >
            {creatingDemo ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <AlertTriangle className="h-4 w-4 mr-2" />}
            Create Demo Verification
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          { label: 'Pending Review', value: stats?.pending_review },
          { label: 'Approved Today', value: stats?.approved_today },
          { label: 'Needs Evidence', value: stats?.needs_more_evidence },
          { label: 'Rejected Today', value: stats?.rejected_today },
          { label: 'Training Buffer', value: stats?.training_buffer },
        ].map(item => (
          <Card key={item.label} className="border-border/40 bg-card/40">
            <CardContent className="p-4">
              <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{item.label}</div>
              <div className="mt-1 font-mono text-2xl font-black">{item.value ?? '—'}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map(item => (
          <button
            key={item.id}
            onClick={() => setTab(item.id)}
            className={`rounded-full border px-4 py-2 text-xs font-bold uppercase tracking-widest transition ${
              tab === item.id
                ? 'border-primary bg-primary/15 text-primary'
                : 'border-border/50 bg-card/40 text-muted-foreground hover:text-foreground'
            }`}
          >
            {item.label}{item.count !== undefined ? ` · ${item.count}` : ''}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-red-800/60 bg-red-950/30 p-3 text-xs text-red-300">
          {error}
        </div>
      )}

      {tab === 'buffer' ? (
        <Card className="border-border/40 bg-card/40">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-primary" />
              <div className="font-bold">Curated Training Buffer</div>
            </div>
            <p className="text-xs text-muted-foreground">
              These counts come from approved and eligible reports. Dataset building snapshots records;
              it does not automatically train or deploy a model.
            </p>
            <div className="grid gap-3 md:grid-cols-3">
              {buffers.length ? buffers.map(buffer => (
                <div key={buffer.hazard_type} className="rounded-xl border border-border/50 bg-black/40 p-4">
                  <div className="text-xs font-black uppercase tracking-widest text-primary">
                    {HAZARD_LABELS[buffer.hazard_type] || buffer.hazard_type} Model
                  </div>
                  <div className="mt-2 font-mono text-2xl font-black">{buffer.count}</div>
                  <div className="text-[10px] text-muted-foreground">approved observations</div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-3 w-full text-xs"
                    disabled={!buffer.count || saving}
                    onClick={() => buildDataset(buffer.hazard_type)}
                  >
                    Build Dataset Snapshot
                  </Button>
                </div>
              )) : (
                <div className="text-sm text-muted-foreground">No eligible observations yet.</div>
              )}
            </div>
            {datasetMessage && (
              <div className="rounded-lg border border-emerald-800/60 bg-emerald-950/30 p-3 text-xs text-emerald-300">
                {datasetMessage}
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[360px_1fr]">
          <Card className="border-border/40 bg-card/40 max-h-[760px] overflow-hidden">
            <CardContent className="p-0">
              <div className="border-b border-border/30 p-4 text-xs font-black uppercase tracking-widest text-muted-foreground">
                Verification Queue
              </div>
              <div className="max-h-[700px] overflow-y-auto p-3 space-y-2">
                {loading ? (
                  <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading reports...
                  </div>
                ) : reports.length ? reports.map(report => (
                  <button
                    key={report.id}
                    onClick={() => setSelectedReport(report)}
                    className={`w-full rounded-xl border p-3 text-left transition ${
                      selectedReport?.id === report.id
                        ? 'border-primary bg-primary/10'
                        : 'border-border/40 bg-black/30 hover:border-primary/50'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[10px] text-muted-foreground">REPORT #{report.id}</span>
                      <Badge variant="outline" className="text-[9px] uppercase">{HAZARD_LABELS[report.hazard_type] || report.hazard_type}</Badge>
                    </div>
                    <div className="mt-1 text-sm font-bold">{report.location_name || report.location_id || 'Geospatial report'}</div>
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      {report.source_type.replace('_', ' ')} · {formatTime(report.observed_at || report.reported_at)}
                    </div>
                  </button>
                )) : (
                  <div className="p-4 space-y-2 text-center">
                    <CheckCircle className="mx-auto h-8 w-8 text-emerald-500/60" />
                    <div className="text-sm font-bold">No Pending Verifications</div>
                    <div className="text-xs text-muted-foreground">
                      All submitted reports in this view are currently processed. Training buffer contains{' '}
                      {stats?.training_buffer ?? 0} eligible observations.
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card className="border-border/40 bg-card/40 overflow-hidden">
              <CardContent className="p-0">
                <div className="h-[420px]">
                  <GeospatialViewer
                    cells={cells}
                    historicalEvents={historicalEvents}
                    eventLayers={eventLayers}
                    infrastructure={infrastructure}
                    nh10Route={nh10Route}
                    routeSafety={routeSafety}
                    reportPoints={reportPoints}
                    selectedReportId={selectedReport?.id || null}
                    highlightCellId={selectedReport?.location_id || null}
                  />
                </div>
              </CardContent>
            </Card>

            {selectedReport ? (
              <Card className="border-border/40 bg-card/40">
                <CardContent className="p-5 space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="font-mono text-[10px] text-muted-foreground">REPORT #{selectedReport.id}</div>
                      <div className="text-lg font-bold">{HAZARD_LABELS[selectedReport.hazard_type] || selectedReport.hazard_type}</div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center text-[10px] font-bold uppercase">
                      <div className="rounded-lg border border-border/50 bg-black/40 p-2">
                        <div className="text-muted-foreground">Evidence</div>
                        <div className="mt-1 text-primary">{selectedReport.evidence_quality || '—'}</div>
                      </div>
                      <div className="rounded-lg border border-border/50 bg-black/40 p-2">
                        <div className="text-muted-foreground">Location</div>
                        <div className="mt-1 text-blue-300">{selectedReport.location_quality || '—'}</div>
                      </div>
                      <div className="rounded-lg border border-border/50 bg-black/40 p-2">
                        <div className="text-muted-foreground">Time</div>
                        <div className="mt-1 text-emerald-300">{selectedReport.temporal_quality || '—'}</div>
                      </div>
                    </div>
                  </div>

                  {selectedReport.possible_duplicate_ids?.length ? (
                    <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 p-3 text-xs text-amber-300">
                      <AlertTriangle className="mr-2 inline h-3.5 w-3.5" />
                      Possible duplicate of report(s): {selectedReport.possible_duplicate_ids.join(', ')}. Curator review required.
                    </div>
                  ) : null}

                  <dl className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
                    <div><dt className="text-muted-foreground">Source</dt><dd className="font-bold">{selectedReport.source_type.replace('_', ' ')}</dd></div>
                    <div><dt className="text-muted-foreground">Reporter</dt><dd className="font-bold">{selectedReport.reporter_id || '—'}</dd></div>
                    <div><dt className="text-muted-foreground">Observed</dt><dd className="font-bold">{formatTime(selectedReport.observed_at)}</dd></div>
                    <div><dt className="text-muted-foreground">Reported</dt><dd className="font-bold">{formatTime(selectedReport.reported_at)}</dd></div>
                    <div><dt className="text-muted-foreground">Coordinates</dt><dd className="font-mono">{selectedReport.latitude?.toFixed(5) || '—'}, {selectedReport.longitude?.toFixed(5) || '—'}</dd></div>
                    <div><dt className="text-muted-foreground">Warning</dt><dd className="font-bold">#{selectedReport.warning_id || '—'}</dd></div>
                    <div><dt className="text-muted-foreground">Event presence</dt><dd className="font-bold">{selectedReport.event_presence?.replace('_', ' ') || 'uncertain'}</dd></div>
                    <div><dt className="text-muted-foreground">Target model</dt><dd className="font-bold">{selectedReport.model_target?.replace('_', ' ') || '—'}</dd></div>
                  </dl>

                  {selectedReport.description && (
                    <div className="rounded-lg border border-border/50 bg-black/40 p-3">
                      <div className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Description</div>
                      <p className="mt-2 text-sm text-slate-200">{selectedReport.description}</p>
                    </div>
                  )}

                  {selectedReport.photo_reference && (
                    <div className="space-y-2">
                      <div className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Field Evidence</div>
                      <img src={selectedReport.photo_reference} alt="Field evidence" className="max-h-64 rounded-xl border border-border/50" />
                      <p className="text-[10px] text-muted-foreground">Curator review required. Imagery is not automatically treated as verified ground truth.</p>
                    </div>
                  )}

                  {selectedReport.audit_events?.length ? (
                    <div className="rounded-lg border border-border/50 bg-black/40 p-3">
                      <div className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Audit Trail</div>
                      <div className="mt-2 space-y-1 font-mono text-[10px] text-slate-400">
                        {selectedReport.audit_events.map(event => (
                          <div key={event.id}>
                            {event.previous_status} → {event.new_status} · {event.curator_id} · {formatTime(event.timestamp)}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {selectedReport.status === 'pending_review' && (
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" className="border-red-800/60 text-red-300" onClick={() => setAction('reject')}>
                        <X className="h-4 w-4 mr-1.5" /> Reject
                      </Button>
                      <Button variant="outline" size="sm" className="border-amber-700/60 text-amber-300" onClick={() => setAction('evidence')}>
                        <AlertTriangle className="h-4 w-4 mr-1.5" /> Need More Evidence
                      </Button>
                      <Button size="sm" className="font-bold" onClick={() => setAction('approve')}>
                        <CheckCircle className="h-4 w-4 mr-1.5" /> Approve for Training
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card className="border-border/40 bg-card/40">
                <CardContent className="p-8 text-center text-sm text-muted-foreground">
                  Select a report to review geospatial evidence and training eligibility.
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {action && selectedReport && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 p-4">
          <div className="w-full max-w-md rounded-xl border border-border/60 bg-background p-5">
            <h3 className="text-sm font-black uppercase tracking-widest">
              {action === 'approve' ? 'Confirm Dataset Eligibility' : action === 'reject' ? 'Reject Report' : 'Request More Evidence'}
            </h3>
            <div className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between"><span className="text-muted-foreground">Hazard</span><span className="font-bold">{HAZARD_LABELS[selectedReport.hazard_type]}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Evidence</span><span className="font-bold uppercase">{selectedReport.evidence_quality}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Location</span><span className="font-bold uppercase">{selectedReport.location_quality}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Observed time</span><span className="font-bold uppercase">{selectedReport.temporal_quality}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Target model</span><span className="font-bold">{selectedReport.model_target?.replace('_', ' ')}</span></div>
            </div>

            {action === 'reject' && (
              <div className="mt-4 space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Reason</label>
                <select
                  value={rejectionReason}
                  onChange={event => setRejectionReason(event.target.value)}
                  className="w-full rounded-lg border border-border/50 bg-black/40 p-2 text-sm"
                >
                  {REJECTION_REASONS.map(reason => (
                    <option key={reason.value} value={reason.value}>{reason.label}</option>
                  ))}
                </select>
              </div>
            )}

            <div className="mt-4 space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Curator notes</label>
              <textarea
                value={notes}
                onChange={event => setNotes(event.target.value)}
                rows={3}
                className="w-full rounded-lg border border-border/50 bg-black/40 p-2 text-sm"
              />
            </div>

            {action === 'approve' && (
              <p className="mt-4 rounded-lg border border-emerald-800/60 bg-emerald-950/30 p-3 text-xs text-emerald-300">
                This report will enter the curated training buffer. It will NOT modify the deployed ML model immediately.
              </p>
            )}
            {action === 'evidence' && (
              <p className="mt-4 rounded-lg border border-amber-800/60 bg-amber-950/30 p-3 text-xs text-amber-300">
                The report remains out of the training buffer until additional evidence is reviewed.
              </p>
            )}

            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setAction(null)}>Cancel</Button>
              <Button size="sm" onClick={submitDecision} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                {action === 'approve' ? 'Approve for Training' : action === 'reject' ? 'Reject Report' : 'Request Evidence'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
