import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { cn } from '../lib/utils';
import { MapPin } from 'lucide-react';

interface Zone {
  zone_id: string;
  name: string;
  geometry: {
    type: string;
    coordinates: number[][][];
  };
}

interface ZoneStatus {
  zone_id: string;
  zone_name: string;
  risk_level: string;
  risk_score: number;
  readings: any;
  timestamp: string;
}

interface RiskMapProps {
  zones: Zone[];
  latestStatus: ZoneStatus[];
  selectedZoneId: string | null;
  onZoneSelect: (zoneId: string) => void;
}

export function RiskMap({ zones, latestStatus, selectedZoneId, onZoneSelect }: RiskMapProps) {
  const width = 800;
  const height = 400;

  if (!zones || zones.length === 0) return null;

  // Extract all points to find bounding box
  const allPoints: number[][] = [];
  zones.forEach(z => {
    if (z.geometry?.coordinates) {
      z.geometry.coordinates[0].forEach(p => allPoints.push(p));
    }
  });

  const xCoords = allPoints.length > 0 ? allPoints.map(p => p[0]) : [0, 100];
  const yCoords = allPoints.length > 0 ? allPoints.map(p => p[1]) : [0, 100];
  
  const minX = Math.min(...xCoords) - 10;
  const maxX = Math.max(...xCoords) + 10;
  const minY = Math.min(...yCoords) - 10;
  const maxY = Math.max(...yCoords) + 10;

  const scaleX = (x: number) => ((x - minX) / (maxX - minX || 1)) * width;
  const scaleY = (y: number) => height - ((y - minY) / (maxY - minY || 1)) * height;

  const getRiskColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'critical': return 'text-red-500 fill-red-500';
      case 'high': return 'text-orange-500 fill-orange-500';
      case 'medium': return 'text-amber-500 fill-amber-500';
      case 'low': return 'text-emerald-500 fill-emerald-500';
      default: return 'text-muted-foreground fill-muted-foreground';
    }
  };

  return (
    <Card className="h-full flex flex-col overflow-hidden border-border/40 bg-card/60 backdrop-blur-sm">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="font-heading flex items-center gap-2">
            <MapPin className="h-5 w-5 text-primary" />
            Mine Site Risk Map
          </CardTitle>
          <div className="flex gap-2">
            {['Low', 'Medium', 'High', 'Critical'].map(level => (
              <div key={level} className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted/50 text-[10px] uppercase font-bold tracking-wider">
                <div className={cn("h-2 w-2 rounded-full", 
                  level === 'Low' ? 'bg-emerald-500' : 
                  level === 'Medium' ? 'bg-amber-500' : 
                  level === 'High' ? 'bg-orange-500' : 'bg-red-500'
                )} />
                {level}
              </div>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 p-0 relative bg-dot-grid overflow-hidden min-h-[400px]">
        <div className="absolute inset-0 flex items-center justify-center p-6">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full drop-shadow-2xl">
            <g className="text-muted/10">
              {[...Array(11)].map((_, i) => (
                <line key={`v-${i}`} x1={(width/10)*i} y1="0" x2={(width/10)*i} y2={height} stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
              ))}
              {[...Array(6)].map((_, i) => (
                <line key={`h-${i}`} x1="0" y1={(height/5)*i} x2={width} y2={(height/5)*i} stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
              ))}
            </g>

            {zones.map(zone => {
              const status = latestStatus.find(s => s.zone_id === zone.zone_id);
              const riskLevel = status?.risk_level || 'low';
              const isSelected = selectedZoneId === zone.zone_id;
              
              if (!zone.geometry?.coordinates?.[0]) return null;
              
              const points = zone.geometry.coordinates[0];
              const pathData = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${scaleX(p[0])} ${scaleY(p[1])}`).join(' ') + ' Z';

              // Calculate centroid for label
              const centroidX = points.reduce((acc, p) => acc + p[0], 0) / points.length;
              const centroidY = points.reduce((acc, p) => acc + p[1], 0) / points.length;

              return (
                <g 
                  key={zone.zone_id} 
                  className="cursor-pointer transition-all duration-300"
                  onClick={() => onZoneSelect(zone.zone_id)}
                >
                  <path 
                    d={pathData}
                    className={cn(
                      "transition-all duration-300 stroke-[2px]",
                      isSelected ? "stroke-primary fill-primary/20" : "stroke-background/50 fill-muted/20",
                      status ? getRiskColor(riskLevel).replace('text-', 'fill-').replace('fill-', 'fill-opacity-20 ') : ""
                    )}
                    stroke="currentColor"
                  />
                  
                  {/* Risk Indicator at Centroid */}
                  <circle 
                    cx={scaleX(centroidX)} 
                    cy={scaleY(centroidY)} 
                    r={isSelected ? "8" : "6"} 
                    className={cn("transition-all duration-300 shadow-xl", getRiskColor(riskLevel))} 
                  />

                  {(riskLevel === 'high' || riskLevel === 'critical') && (
                    <circle 
                      cx={scaleX(centroidX)} 
                      cy={scaleY(centroidY)} 
                      r="15" 
                      className={cn("animate-ping opacity-30", getRiskColor(riskLevel))} 
                    />
                  )}

                  <text 
                    x={scaleX(centroidX)} 
                    y={scaleY(centroidY) + 25} 
                    textAnchor="middle" 
                    className={cn(
                      "text-[10px] font-bold uppercase tracking-wider fill-foreground select-none",
                      isSelected ? "opacity-100 scale-110" : "opacity-60"
                    )}
                  >
                    {zone.name}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </CardContent>
    </Card>
  );
}
