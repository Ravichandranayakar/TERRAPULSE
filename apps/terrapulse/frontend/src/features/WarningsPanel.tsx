import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { cn } from '../lib/utils';
import {
  AlertTriangle, CheckCircle, Clock, MapPin, Navigation,
  MessageSquare, ShieldCheck, Loader2, RadioTower
} from 'lucide-react';
import { rpcCall } from '../api';

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
  operator_notes?: string;
  resolved_at?: string;
  centroid_lat: number;
  centroid_lon: number;
  near_nh10: number;
}

interface WarningsPanelProps {
  warnings: Warning[];
  onResolved: () => void;
  onBroadcast?: (warning: Warning) => void;
}

const RISK_COLORS: Record<string, {
  bg: string;
  text: string;
  border: string;
  accent: string;
  bar: string;
}> = {
  critical: {
    bg: 'bg-card/70',
    text: 'text-red-400',
    border: 'border-red-800/50',
    accent: 'border-l-4 border-l-red-600/80',
    bar: 'bg-red-500',
  },
  high: {
    bg: 'bg-card/70',
    text: 'text-orange-400',
    border: 'border-orange-800/50',
    accent: 'border-l-4 border-l-orange-500/80',
    bar: 'bg-orange-500',
  },
  moderate: {
    bg: 'bg-card/70',
    text: 'text-amber-400',
    border: 'border-amber-800/50',
    accent: 'border-l-4 border-l-amber-500/80',
    bar: 'bg-amber-500',
  },
  low: {
    bg: 'bg-card/70',
    text: 'text-emerald-400',
    border: 'border-emerald-800/40',
    accent: 'border-l-4 border-l-emerald-500/80',
    bar: 'bg-emerald-500',
  },
};

const RECOMMENDED_ACTIONS: Record<string, string[]> = {
  critical: [
    'Alert NDMA — State Emergency Operations Centre (Gangtok)',
    'Notify BRO clearing crews for NH-10 corridor sections',
    'Issue NH-10 traffic advisory — suspend non-essential traffic',
    'Deploy SDRF field teams for ground survey',
    'Alert Mangan district DM office — initiate evacuation assessment',
    'Launch UAV/drone survey over critical sectors',
  ],
  high: [
    'Alert district disaster management cell — North Sikkim',
    'Increase vigilance monitoring frequency to 15-minute intervals',
    'Notify BRO maintenance teams of elevated risk on NH-10',
    'Dispatch field verification team to high-risk sector',
    'Issue public advisory for settlements in high-slope areas',
  ],
  moderate: [
    'Increase monitoring frequency',
    'Notify local panchayat and block officials of elevated conditions',
    'Review and prepare emergency response protocols',
    'Alert nearby settlement communities via local alert network',
  ],
  low: [
    'Continue routine monitoring',
    'Log for antecedent rainfall tracking',
  ],
};

function isCellBroadcastEligible(warning: Warning): boolean {
  return warning.risk_level?.toLowerCase() === 'high' || warning.risk_level?.toLowerCase() === 'critical';
}

function VerificationModal({ warning, onClose, onSubmit }: {
  warning: Warning;
  onClose: () => void;
  onSubmit: (data: any) => void;
}) {
  const [verifiedBy, setVerifiedBy] = useState('');
  const [outcome, setOutcome] = useState<'confirmed' | 'not_observed' | 'uncertain' | ''>('');
  const [hazardType, setHazardType] = useState<'landslide' | 'flood' | 'debris_flow' | 'other'>('landslide');
  const [observedAt, setObservedAt] = useState(new Date().toISOString().slice(0, 16));
  const [severity, setSeverity] = useState('');
  const [infrastructureImpact, setInfrastructureImpact] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!verifiedBy || !outcome) return;
    setLoading(true);
    try {
      await rpcCall({
        func: 'submit_field_verification',
        args: {
          warning_id: warning.id,
          location_id: warning.location_id,
          verified_by: verifiedBy,
          outcome,
          notes,
          hazard_type: hazardType,
          description: notes,
          source_type: 'field_officer',
          source_reference: `warning_${warning.id}`,
          reporter_role: 'field_officer',
          reporter_id: verifiedBy,
          observed_at: new Date(observedAt).toISOString(),
          event_presence: outcome,
          latitude: warning.centroid_lat,
          longitude: warning.centroid_lon,
          location_quality: 'approximate',
          severity: severity || undefined,
          infrastructure_impact: infrastructureImpact
            ? infrastructureImpact.split(',').map(item => item.trim()).filter(Boolean)
            : [],
        }
      });
      onSubmit({ outcome, notes, hazardType });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <Card className="w-full max-w-md border-border/60 bg-card shadow-2xl mx-4">
        <CardHeader>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            Field Verification Report
          </CardTitle>
          <p className="text-xs text-muted-foreground">{warning.location_name} · Warning #{warning.id}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Field Officer Name / ID</label>
            <input
              type="text"
              value={verifiedBy}
              onChange={e => setVerifiedBy(e.target.value)}
              placeholder="e.g. SDRF Inspector Sharma"
              className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border/40 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Outcome</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setOutcome('confirmed')}
                className={cn(
                  "p-3 rounded-lg border text-sm font-bold transition-all",
                  outcome === 'confirmed'
                    ? 'bg-red-950/60 border-red-600 text-red-300'
                    : 'border-border/40 text-muted-foreground hover:border-red-700'
                )}
              >
                🔴 Landslide Confirmed
              </button>
              <button
                onClick={() => setOutcome('not_observed')}
                className={cn(
                  "p-3 rounded-lg border text-sm font-bold transition-all",
                  outcome === 'not_observed'
                    ? 'bg-emerald-950/60 border-emerald-600 text-emerald-300'
                    : 'border-border/40 text-muted-foreground hover:border-emerald-700'
                )}
              >
                🟢 False Alarm
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Hazard Type</label>
            <select
              value={hazardType}
              onChange={e => setHazardType(e.target.value as typeof hazardType)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-900/95 border border-border/40 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option className="bg-zinc-900 text-zinc-100" value="landslide">Landslide</option>
              <option className="bg-zinc-900 text-zinc-100" value="flood">Flood</option>
              <option className="bg-zinc-900 text-zinc-100" value="debris_flow">Debris Flow</option>
              <option className="bg-zinc-900 text-zinc-100" value="other">Other</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Observed At</label>
              <input
                type="datetime-local"
                value={observedAt}
                onChange={e => setObservedAt(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border/40 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Severity</label>
            <select
              value={severity}
              onChange={e => setSeverity(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-900/95 border border-border/40 text-sm text-zinc-100 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option className="bg-zinc-900 text-zinc-100" value="">Not assessed</option>
              <option className="bg-zinc-900 text-zinc-100" value="low">Low</option>
              <option className="bg-zinc-900 text-zinc-100" value="moderate">Moderate</option>
              <option className="bg-zinc-900 text-zinc-100" value="high">High</option>
              <option className="bg-zinc-900 text-zinc-100" value="critical">Critical</option>
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Infrastructure Impact</label>
            <input
              type="text"
              value={infrastructureImpact}
              onChange={e => setInfrastructureImpact(e.target.value)}
              placeholder="e.g. NH-10, Dikchu bridge, Mangan settlement"
              className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border/40 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Field Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Describe on-ground observations, road conditions, visible slope movement..."
              rows={3}
              className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border/40 text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-none"
            />
          </div>

          <div className="text-[10px] text-muted-foreground/60 leading-relaxed border-t border-border/20 pt-2">
            Submitted verifications enter a curator review queue before being approved for ML training dataset.
          </div>

          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="flex-1" onClick={onClose}>Cancel</Button>
            <Button
              size="sm"
              className="flex-1 font-bold"
              disabled={!verifiedBy || !outcome || loading}
              onClick={handleSubmit}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <ShieldCheck className="h-4 w-4 mr-1" />}
              Submit Verification
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function WarningsPanel({ warnings, onResolved, onBroadcast }: WarningsPanelProps) {
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [verifyingWarning, setVerifyingWarning] = useState<Warning | null>(null);
  const [verifiedIds, setVerifiedIds] = useState<number[]>([]);
  const [loading, setLoading] = useState<Record<number, boolean>>({});

  const resolveWarning = async (id: number) => {
    setLoading(prev => ({ ...prev, [id]: true }));
    try {
      await rpcCall({
        func: 'resolve_warning',
        args: { warning_id: id, notes: notes[id] || '' }
      });
      onResolved();
      setResolvingId(null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  if (warnings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground space-y-4">
        <div className="h-20 w-20 rounded-full bg-emerald-950/30 border border-emerald-800/30 flex items-center justify-center">
          <ShieldCheck className="h-10 w-10 text-emerald-500/40" />
        </div>
        <div className="text-center space-y-1">
          <p className="text-sm font-bold">No Active Warnings</p>
          <p className="text-xs text-muted-foreground">All monitored locations are within safe parameters.</p>
          <p className="text-[10px] text-muted-foreground/60 mt-2">Run the storm simulation to generate warning events.</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-4">
        {/* Summary bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {(['critical', 'high', 'moderate', 'low'] as const).map(level => {
            const count = warnings.filter(w => w.risk_level === level).length;
            const col = RISK_COLORS[level];
            return (
              <div key={level} className={cn("rounded-xl p-3 border bg-card/60 border-border/60", col.accent)}>
                <div className={cn("text-[10px] font-bold uppercase tracking-wider", col.text)}>{level}</div>
                <div className={cn("text-3xl font-black font-mono", col.text)}>{count}</div>
              </div>
            );
          })}
        </div>

        {/* Warning Cards */}
        <div className="space-y-4">
          {warnings.map(w => {
            const level = w.risk_level?.toLowerCase() || 'low';
            const col = RISK_COLORS[level] || RISK_COLORS.low;
            const actions = RECOMMENDED_ACTIONS[level] || [];
            const isResolving = resolvingId === w.id;
            const isVerified = verifiedIds.includes(w.id);

            return (
              <Card key={w.id} className={cn("border overflow-hidden bg-card/70 border-border/60", col.accent)}>
                <CardContent className="p-5 space-y-4">
                  {/* Header */}
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge className={cn("font-bold uppercase text-[11px] px-2.5", col.text, col.border, "bg-black/20")} variant="outline">
                          ⚠ {w.risk_level} Risk
                        </Badge>
                        <Badge variant="outline" className="text-[10px] font-mono">
                          #{w.id}
                        </Badge>
                        {w.near_nh10 === 1 && (
                          <Badge className="text-[10px] font-bold text-blue-300 border-blue-700/60 bg-blue-950/30">
                            NH-10 Adjacent
                          </Badge>
                        )}
                      </div>
                      <h3 className="font-heading font-bold text-base">{w.location_name}</h3>
                      <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {new Date(w.timestamp).toLocaleString()}
                        </span>
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3" />
                          {w.centroid_lat?.toFixed(3)}°N, {w.centroid_lon?.toFixed(3)}°E
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={cn("text-3xl font-black font-mono", col.text)}>{w.risk_score?.toFixed(0)}</div>
                      <div className="text-[10px] text-muted-foreground">Risk Score</div>
                    </div>
                  </div>

                  {/* Trigger Factors */}
                  {w.trigger_factors?.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Trigger Factors</div>
                      <div className="space-y-1">
                        {w.trigger_factors.slice(0, 3).map((f: any, i: number) => (
                          <div key={i} className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">{f.factor}</span>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-[10px] text-muted-foreground/60">{f.raw} {f.raw_unit}</span>
                              <div className="w-20 h-1.5 bg-muted/40 rounded-full overflow-hidden">
                                <div className={cn("h-full rounded-full", col.bar)} style={{ width: `${Math.min(f.value, 100)}%` }} />
                              </div>
                              <span className={cn("font-bold text-[10px]", col.text)}>{f.value.toFixed(0)}%</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Affected Infrastructure */}
                  {w.affected_infrastructure?.length > 0 && (
                    <div className="flex items-center gap-2 rounded-lg bg-blue-950/30 border border-blue-800/40 p-2">
                      <Navigation className="h-3.5 w-3.5 text-blue-400 flex-shrink-0" />
                      <span className="text-xs font-bold text-blue-300">
                        At risk: {w.affected_infrastructure.join(', ')}
                      </span>
                    </div>
                  )}

                  {/* Recommended Actions */}
                  <div className="space-y-1.5">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Recommended Actions</div>
                    <div className="space-y-1">
                      {actions.slice(0, 3).map((action, i) => (
                        <div key={i} className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
                          <span className={cn("flex-shrink-0 font-bold", col.text)}>→</span>
                          {action}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Actions */}
                  {!isResolving ? (
                    <div className="flex gap-2 flex-wrap pt-1">
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs font-bold"
                        onClick={() => setResolvingId(w.id)}
                      >
                        <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
                        Acknowledge & Resolve
                      </Button>
                      {!isVerified && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-xs font-bold border-blue-700/50 text-blue-400 hover:bg-blue-950/30"
                          onClick={() => setVerifyingWarning(w)}
                        >
                          <ShieldCheck className="h-3.5 w-3.5 mr-1.5" />
                          Field Verification
                        </Button>
                      )}
                      {isVerified && (
                        <Badge variant="outline" className="text-emerald-400 border-emerald-700/50 text-[10px]">
                          <CheckCircle className="h-3 w-3 mr-1" /> Verification Submitted
                        </Badge>
                      )}
                      {isCellBroadcastEligible(w) && onBroadcast && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-xs font-bold border-amber-700/60 text-amber-300 hover:bg-amber-950/30"
                          onClick={() => onBroadcast(w)}
                        >
                          <RadioTower className="h-3.5 w-3.5 mr-1.5" />
                          Simulate Cell Broadcast
                        </Button>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-2 border-t border-border/30 pt-3">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                        Response Notes (required for audit log)
                      </label>
                      <textarea
                        value={notes[w.id] || ''}
                        onChange={e => setNotes(prev => ({ ...prev, [w.id]: e.target.value }))}
                        placeholder="Describe action taken — e.g. 'Alerted BRO team. NH-10 speed restriction issued at Dikchu.'"
                        rows={2}
                        className="w-full px-3 py-2 rounded-lg bg-muted/40 border border-border/40 text-xs focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                      />
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" className="text-xs" onClick={() => setResolvingId(null)}>Cancel</Button>
                        <Button
                          size="sm"
                          className="text-xs font-bold flex-1"
                          onClick={() => resolveWarning(w.id)}
                          disabled={loading[w.id]}
                        >
                          {loading[w.id]
                            ? <><Loader2 className="h-3 w-3 animate-spin mr-1" /> Resolving...</>
                            : <><CheckCircle className="h-3 w-3 mr-1" /> Mark Resolved</>
                          }
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Field Verification Modal */}
      {verifyingWarning && (
        <VerificationModal
          warning={verifyingWarning}
          onClose={() => setVerifyingWarning(null)}
          onSubmit={() => {
            setVerifiedIds(prev => [...prev, verifyingWarning.id]);
            setVerifyingWarning(null);
          }}
        />
      )}
    </>
  );
}
