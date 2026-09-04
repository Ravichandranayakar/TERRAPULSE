import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Activity, Play, Square, Loader2, Thermometer, Droplets, ArrowUpRight } from 'lucide-react';
import { streamCall } from '../api';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { cn } from '../lib/utils';

export function LiveMonitor() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamData, setStreamData] = useState<any[]>([]);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [currentStatus, setCurrentStatus] = useState('Standby');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [streamData]);

  const startStreaming = async () => {
    setIsStreaming(true);
    setStreamData([]);
    setCurrentProgress(0);
    setCurrentStatus('Initializing Simulation...');

    try {
      await streamCall({
        func: 'simulate_data_streaming',
        args: {},
        onChunk: (chunk) => {
          if (chunk.status) setCurrentStatus(chunk.status);
          if (chunk.progress) setCurrentProgress(chunk.progress);
          if (chunk.zone_id) {
            setStreamData(prev => [...prev, chunk]);
          }
          if (chunk.status === 'Complete') {
            setIsStreaming(false);
          }
        },
        onError: (err) => {
          console.error("Stream error:", err);
          setIsStreaming(false);
          setCurrentStatus('Error occurred');
        }
      });
    } catch (err) {
      setIsStreaming(false);
    }
  };

  const stopStreaming = () => {
    setIsStreaming(false);
    setCurrentStatus('Simulation Stopped');
  };

  const getRiskColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'critical': return 'text-red-500';
      case 'high': return 'text-orange-500';
      case 'medium': return 'text-amber-500';
      case 'low': return 'text-emerald-500';
      default: return 'text-muted-foreground';
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-6">
        <Card className="bg-card/60 backdrop-blur-sm border-border/40">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <CardTitle className="font-heading flex items-center gap-2 text-primary">
                  <Activity className="h-5 w-5" />
                  Live Sensor Stream
                </CardTitle>
                <CardDescription>Real-time displacement and vibration monitoring across active zones</CardDescription>
              </div>
              <div className="flex gap-2">
                {isStreaming ? (
                  <Button variant="destructive" size="sm" onClick={stopStreaming} className="font-bold">
                    <Square className="h-4 w-4 mr-2" /> Stop Simulation
                  </Button>
                ) : (
                  <Button variant="default" size="sm" onClick={startStreaming} className="font-bold bg-primary hover:bg-primary/90 text-primary-foreground">
                    <Play className="h-4 w-4 mr-2" /> Start Simulation
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="bg-muted/30 rounded-lg p-4 space-y-3 border border-border/20">
              <div className="flex items-center justify-between text-xs font-bold uppercase tracking-widest text-muted-foreground">
                <span>Simulation Status: <span className="text-primary">{currentStatus}</span></span>
                <span>{currentProgress}%</span>
              </div>
              <Progress value={currentProgress} className="h-2" />
            </div>

            <ScrollArea className="h-[500px] pr-4" ref={scrollRef}>
              <div className="space-y-3">
                {streamData.length === 0 && !isStreaming && (
                  <div className="flex flex-col items-center justify-center py-20 text-muted-foreground space-y-4">
                    <div className="p-4 rounded-full bg-muted/50">
                      <Activity className="h-8 w-8 opacity-20" />
                    </div>
                    <p className="text-sm font-medium">Click "Start Simulation" to begin real-time data flow</p>
                  </div>
                )}
                
                {streamData.map((data, i) => (
                  <div key={i} className="group flex items-start gap-4 p-4 rounded-lg bg-card border border-border/40 hover:border-primary/40 transition-all animate-in fade-in slide-in-from-left-2">
                    <div className={cn("h-10 w-10 rounded-full flex items-center justify-center bg-muted/50", getRiskColor(data.risk_level))}>
                      <Activity className="h-5 w-5" />
                    </div>
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="font-bold font-heading">{data.zone_id}</div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-muted-foreground font-mono">{new Date(data.readings.timestamp).toLocaleTimeString()}</span>
                          <Badge className={cn("text-[10px] font-bold uppercase", getRiskColor(data.risk_level))} variant="outline">
                            {data.risk_level} Risk
                          </Badge>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-1">
                         <div className="space-y-1">
                           <div className="text-[10px] uppercase font-bold text-muted-foreground">Displacement</div>
                           <div className="text-sm font-bold flex items-center gap-1">
                             <ArrowUpRight className="h-3 w-3 text-primary" />
                             {data.readings.displacement_mm.toFixed(2)} mm
                           </div>
                         </div>
                         <div className="space-y-1">
                           <div className="text-[10px] uppercase font-bold text-muted-foreground">Vibration</div>
                           <div className="text-sm font-bold flex items-center gap-1 text-amber-500">
                             <Activity className="h-3 w-3" />
                             {data.readings.vibration_mm_s.toFixed(2)} mm/s
                           </div>
                         </div>
                         <div className="space-y-1">
                           <div className="text-[10px] uppercase font-bold text-muted-foreground">Temp</div>
                           <div className="text-sm font-bold flex items-center gap-1 text-muted-foreground">
                             <Thermometer className="h-3 w-3" />
                             {data.readings.temp}°C
                           </div>
                         </div>
                         <div className="space-y-1">
                           <div className="text-[10px] uppercase font-bold text-muted-foreground">Humidity</div>
                           <div className="text-sm font-bold flex items-center gap-1 text-muted-foreground">
                             <Droplets className="h-3 w-3" />
                             {data.readings.humidity}%
                           </div>
                         </div>
                      </div>
                    </div>
                  </div>
                ))}
                {isStreaming && (
                  <div className="flex items-center justify-center p-4">
                    <Loader2 className="h-6 w-6 animate-spin text-primary opacity-50" />
                  </div>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        <Card className="bg-card/60 backdrop-blur-sm border-border/40 overflow-hidden">
          <div className="aspect-video relative overflow-hidden">
            <img src="./assets/hero-mine-1.jpg" alt="Mine Site" className="object-cover w-full h-full" />
            <div className="absolute inset-0 bg-gradient-to-t from-background to-transparent" />
            <div className="absolute bottom-4 left-4">
              <Badge className="bg-primary text-primary-foreground font-bold uppercase text-[10px]">Site Primary View</Badge>
            </div>
          </div>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold uppercase tracking-widest">Site Context</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Monitoring is active for the Western Sector open-pit excavations. Simulation mode runs 
              high-frequency risk re-calculations based on the Random Forest ensemble model.
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card/60 backdrop-blur-sm border-border/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold uppercase tracking-widest">Model Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-500">
                <Activity className="h-4 w-4" />
              </div>
              <div className="space-y-0.5">
                <div className="text-xs font-bold">Random Forest Classifier</div>
                <div className="text-[10px] text-muted-foreground">v2.4.1 - Production Ensemble</div>
              </div>
            </div>
            <div className="h-[1px] w-full bg-border/20" />
            <div className="grid grid-cols-2 gap-2 text-[10px] font-bold uppercase text-muted-foreground">
               <div>Precision: <span className="text-primary">94.2%</span></div>
               <div>Recall: <span className="text-primary">91.8%</span></div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
