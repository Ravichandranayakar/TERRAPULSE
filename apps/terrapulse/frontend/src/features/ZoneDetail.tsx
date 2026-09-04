import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { Activity, Thermometer, Droplets, ArrowUpRight, TrendingUp } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';

interface ZoneDetailProps {
  zone: any;
  status: any;
  trends: any[];
}

export function ZoneDetail({ zone, status, trends }: ZoneDetailProps) {
  if (!zone) return null;

  const currentReadings = status?.readings || {};

  const getRiskVariant = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'critical': return 'destructive';
      case 'high': return 'destructive';
      case 'medium': return 'default';
      case 'low': return 'secondary';
      default: return 'outline';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold font-heading tracking-tight">{zone.name}</h2>
            <Badge variant={getRiskVariant(status?.risk_level)} className="uppercase px-2 py-0.5 text-[10px] font-bold">
              {status?.risk_level || 'UNKNOWN'} RISK
            </Badge>
          </div>
          <p className="text-muted-foreground">{zone.description}</p>
        </div>
        
        <div className="flex gap-4">
          <div className="bg-card border border-border/40 rounded-lg p-3 flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Risk Score</div>
              <div className="text-xl font-bold font-heading">{status?.risk_score?.toFixed(2) || '0.00'}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Displacement', value: `${currentReadings.displacement_mm?.toFixed(2)} mm`, icon: ArrowUpRight, trend: '+0.2%' },
          { label: 'Vibration', value: `${currentReadings.vibration_mm_s?.toFixed(2)} mm/s`, icon: Activity, trend: '-1.5%' },
          { label: 'Temperature', value: `${currentReadings.temp?.toFixed(1)}°C`, icon: Thermometer },
          { label: 'Humidity', value: `${currentReadings.humidity?.toFixed(0)}%`, icon: Droplets },
        ].map((stat, i) => (
          <Card key={i} className="bg-card/40 border-border/40 overflow-hidden group">
            <CardContent className="p-4 relative">
              <stat.icon className="absolute top-4 right-4 h-5 w-5 text-muted-foreground/20 group-hover:text-primary/20 transition-colors" />
              <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider">{stat.label}</div>
              <div className="mt-1 text-xl font-bold font-heading">{stat.value}</div>
              {stat.trend && (
                <div className="mt-1 text-[10px] font-medium text-emerald-500 flex items-center gap-1">
                  {stat.trend} <span className="text-muted-foreground font-normal">vs prev hour</span>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-card/60 backdrop-blur-sm border-border/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold uppercase tracking-wider flex items-center gap-2">
              <ArrowUpRight className="h-4 w-4 text-primary" />
              Displacement Trend (7d)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trends}>
                  <defs>
                    <linearGradient id="colorDisp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border)/0.2)" />
                  <XAxis 
                    dataKey="timestamp" 
                    tickFormatter={(val) => new Date(val).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                    labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: 'bold' }}
                  />
                  <Area type="monotone" dataKey="displacement_mm" stroke="hsl(var(--primary))" strokeWidth={2} fillOpacity={1} fill="url(#colorDisp)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card/60 backdrop-blur-sm border-border/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold uppercase tracking-wider flex items-center gap-2">
              <Activity className="h-4 w-4 text-amber-500" />
              Vibration Profile (7d)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trends}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border)/0.2)" />
                  <XAxis 
                    dataKey="timestamp" 
                    tickFormatter={(val) => new Date(val).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                    labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: 'bold' }}
                  />
                  <Line type="monotone" dataKey="vibration_mm_s" stroke="#f59e0b" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
