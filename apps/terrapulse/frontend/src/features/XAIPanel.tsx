import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { cn } from '../lib/utils';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import { Brain, AlertTriangle, TrendingUp, Mountain, Droplets, Wind } from 'lucide-react';

interface ContributingFactor {
  factor: string;
  value: number;
  unit: string;
  raw: number;
  raw_unit: string;
  weight: number;
}

interface XAIPanelProps {
  cell: any;
  onClose?: () => void;
}

const FACTOR_COLORS: Record<string, string> = {
  '3-Day Accumulated Rainfall': '#3b82f6',
  'Antecedent Rainfall (7-Day)': '#6366f1',
  'Slope Angle': '#f97316',
  'Soil Moisture': '#0ea5e9',
  'Recent Rainfall (24h)': '#38bdf8',
  'Rainfall Intensity': '#22d3ee',
  'Geological Susceptibility': '#a855f7',
  'Historical Landslide Activity': '#ef4444',
};

const FACTOR_ICONS: Record<string, React.ComponentType<any>> = {
  'Slope Angle': Mountain,
  '3-Day Accumulated Rainfall': Droplets,
  'Antecedent Rainfall (7-Day)': Droplets,
  'Soil Moisture': Droplets,
  'Recent Rainfall (24h)': Droplets,
  'Rainfall Intensity': Wind,
  'Geological Susceptibility': Mountain,
  'Historical Landslide Activity': AlertTriangle,
};

const RISK_BADGE_VARIANT: Record<string, string> = {
  critical: 'destructive',
  high: 'destructive',
  moderate: 'outline',
  low: 'secondary',
};

const RISK_BG: Record<string, string> = {
  critical: 'from-red-950/60 to-red-900/20',
  high: 'from-orange-950/60 to-orange-900/20',
  moderate: 'from-amber-950/50 to-amber-900/10',
  low: 'from-emerald-950/40 to-emerald-900/10',
};

const RISK_RING: Record<string, string> = {
  critical: 'ring-red-500/40',
  high: 'ring-orange-500/40',
  moderate: 'ring-amber-500/40',
  low: 'ring-emerald-500/40',
};

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border border-border/60 rounded-lg p-3 shadow-xl text-xs">
      <div className="font-bold text-foreground mb-1">{d.factor}</div>
      <div className="text-muted-foreground">Contribution: <span className="text-primary font-bold">{d.value.toFixed(1)}%</span></div>
      <div className="text-muted-foreground">Measured: <span className="font-bold">{d.raw} {d.raw_unit}</span></div>
    </div>
  );
}

import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function XAIPanel({ cell, onClose }: XAIPanelProps) {
  if (!cell) return null;
  const { 
    name: locationName,
    risk_level: riskLevel,
    risk_score: riskScore,
    contributing_factors: contributingFactors,
    slope_angle: slopeAngle,
    elevation_m: elevation,
    soil_type: soilType,
    near_nh10: nearNH10,
    historical_count: historicalCount,
  } = cell;
  const level = riskLevel?.toLowerCase() || 'low';

  // Normalize display values so bars don't exceed 100
  const chartData = (contributingFactors || []).map(f => ({
    ...f,
    displayValue: Math.min(f.value, 100),
    fill: FACTOR_COLORS[f.factor] || '#6366f1',
  }));

  return (
    <div className="space-y-5">
      {/* Risk Level Header */}
      <div className={cn(
        "rounded-xl p-4 bg-gradient-to-br ring-1",
        RISK_BG[level] || RISK_BG.low,
        RISK_RING[level] || RISK_RING.low
      )}>
        {onClose && (
          <button 
            onClick={onClose}
            className="absolute top-3 right-3 text-white/60 hover:text-white transition-colors bg-black/40 hover:bg-black/60 rounded-full p-1"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Brain className="h-4 w-4 text-primary" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">AI Risk Assessment</span>
            </div>
            <h3 className="font-heading text-lg font-bold leading-tight">{locationName}</h3>
          </div>
          <Badge
            variant={RISK_BADGE_VARIANT[level] as any || 'secondary'}
            className="text-xs font-bold uppercase tracking-wider px-3 py-1"
          >
            {riskLevel}
          </Badge>
        </div>

        {/* Risk Score Gauge */}
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs font-bold mb-1.5">
            <span className="text-muted-foreground uppercase tracking-wider">Risk Score</span>
            <span className="font-mono text-lg font-black">{(riskScore || 0).toFixed(1)}<span className="text-[10px] text-muted-foreground font-normal">/100</span></span>
          </div>
          <div className="h-2.5 bg-background/40 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{
                width: `${Math.min(riskScore, 100)}%`,
                background: level === 'critical' ? 'linear-gradient(90deg, #dc2626, #ef4444)' :
                  level === 'high' ? 'linear-gradient(90deg, #ea580c, #f97316)' :
                  level === 'moderate' ? 'linear-gradient(90deg, #d97706, #f59e0b)' :
                  'linear-gradient(90deg, #059669, #10b981)',
              }}
            />
          </div>
        </div>
      </div>

      {/* Terrain Profile */}
      <div className="rounded-xl border border-border/40 bg-muted/20 p-3 space-y-2">
        <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <Mountain className="h-3 w-3" /> Terrain Profile
        </div>
        <div className="grid grid-cols-2 gap-3">
          {slopeAngle !== undefined && (
            <div className="space-y-0.5">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Slope Angle</div>
              <div className="text-sm font-bold">{slopeAngle}°</div>
            </div>
          )}
          {elevation !== undefined && (
            <div className="space-y-0.5">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Elevation</div>
              <div className="text-sm font-bold">{elevation.toLocaleString()} m</div>
            </div>
          )}
          {soilType && (
            <div className="space-y-0.5 col-span-2">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Soil / Rock Type</div>
              <div className="text-sm font-bold">{soilType}</div>
            </div>
          )}
          {historicalCount !== undefined && (
            <div className="space-y-0.5">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Historical Events</div>
              <div className="text-sm font-bold">{historicalCount} recorded</div>
            </div>
          )}
          {nearNH10 !== undefined && (
            <div className="space-y-0.5">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">NH-10 Proximity</div>
              <div className={cn("text-sm font-bold", nearNH10 ? "text-blue-400" : "text-muted-foreground")}>
                {nearNH10 ? '⚠ Adjacent' : 'Remote'}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* XAI — Contributing Factors Chart */}
      {(contributingFactors || []).length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Top Risk Drivers</span>
          </div>

          {/* Horizontal bar chart */}
          <div className="space-y-2">
            {(contributingFactors || []).slice(0, 5).map((f, i) => {
              const Icon = FACTOR_ICONS[f.factor] || TrendingUp;
              const barColor = FACTOR_COLORS[f.factor] || '#6366f1';
              const pct = Math.min(f.value, 100);
              return (
                <div key={i} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-1.5 font-medium">
                      <Icon className="h-3 w-3" style={{ color: barColor }} />
                      <span className="text-foreground/80">{f.factor}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground font-mono text-[10px]">{f.raw} {f.raw_unit}</span>
                      <span className="font-bold" style={{ color: barColor }}>{pct.toFixed(0)}%</span>
                    </div>
                  </div>
                  <div className="h-1.5 bg-muted/50 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${pct}%`,
                        background: barColor,
                        opacity: 0.85,
                        transitionDelay: `${i * 100}ms`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Infrastructure Impact Alert */}
      {nearNH10 && (riskLevel === 'high' || riskLevel === 'critical') && (
        <div className="rounded-xl border border-blue-500/40 bg-blue-950/30 p-3 space-y-2">
          <div className="flex items-center gap-2 text-blue-400 text-xs font-bold uppercase tracking-wider">
            <AlertTriangle className="h-3.5 w-3.5" />
            Infrastructure Exposure
          </div>
          <p className="text-xs text-blue-200/80">
            This location is adjacent to the <strong>NH-10 highway corridor</strong>. 
            A landslide event could disrupt Sikkim's primary road lifeline connecting Rangpo to Mangan.
          </p>
          <div className="text-[10px] font-bold text-blue-300 uppercase tracking-wider">
            Recommended: Alert BRO clearing teams · Issue NH-10 traffic advisory
          </div>
        </div>
      )}

      {/* Scientific disclaimer */}
      <div className="text-[9px] text-muted-foreground/50 leading-relaxed border-t border-border/20 pt-2">
        ⚠ Risk assessment based on candidate ML model trained on synthetic NER-style simulation dataset.
        For operational use, validate with GSI/ISRO historical landslide records and IMD rainfall data.
      </div>
    </div>
  );
}
