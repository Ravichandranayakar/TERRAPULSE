import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/table';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { AlertTriangle, CheckCircle2, MessageSquare, Clock, Filter } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { rpcCall } from '../api';

interface Alert {
  id: number;
  timestamp: string;
  zone_id: string;
  alert_level: string;
  risk_score: number;
  reason: string;
  status: string;
}

interface AlertsListProps {
  alerts: Alert[];
  onResolved: () => void;
}

export function AlertsList({ alerts, onResolved }: AlertsListProps) {
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleResolve = async () => {
    if (!resolvingId) return;
    setIsSubmitting(true);
    try {
      await rpcCall({ func: 'resolve_alert', args: { alert_id: resolvingId, notes } });
      setResolvingId(null);
      setNotes('');
      onResolved();
    } catch (err) {
      console.error("Failed to resolve alert", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getLevelColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'critical': return 'bg-red-500/10 text-red-500 border-red-500/20';
      case 'high': return 'bg-orange-500/10 text-orange-500 border-orange-500/20';
      case 'medium': return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
      default: return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
    }
  };

  return (
    <Card className="bg-card/60 backdrop-blur-sm border-border/40">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="font-heading flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              Active Safety Alerts
            </CardTitle>
            <CardDescription>View and manage critical landslide risk alerts requiring operator resolution</CardDescription>
          </div>
          <Badge variant="outline" className="gap-1 px-3">
            <Filter className="h-3 w-3" /> Filters
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center space-y-3">
            <div className="h-12 w-12 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-500">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <div className="space-y-1">
              <h3 className="font-heading font-bold">All Clear</h3>
              <p className="text-sm text-muted-foreground">No active alerts detected across the site.</p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent border-border/40">
                  <TableHead className="w-[180px]">Timestamp</TableHead>
                  <TableHead>Zone</TableHead>
                  <TableHead>Level</TableHead>
                  <TableHead className="max-w-[300px]">Reason</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alerts.map((alert) => (
                  <TableRow key={alert.id} className="border-border/40 hover:bg-muted/30 group">
                    <TableCell className="font-mono text-[11px] text-muted-foreground">
                      <div className="flex items-center gap-2">
                        <Clock className="h-3 w-3" />
                        {new Date(alert.timestamp).toLocaleString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </div>
                    </TableCell>
                    <TableCell className="font-bold">{alert.zone_id}</TableCell>
                    <TableCell>
                      <Badge className={getLevelColor(alert.alert_level)} variant="outline">
                        {alert.alert_level.toUpperCase()}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{alert.reason}</TableCell>
                    <TableCell className="text-right">
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="h-8 border-border/40 hover:border-primary hover:text-primary transition-colors"
                            onClick={() => setResolvingId(alert.id)}
                          >
                            Resolve
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-card border-border/40">
                          <DialogHeader>
                            <DialogTitle className="font-heading flex items-center gap-2">
                              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                              Resolve Alert #{alert.id}
                            </DialogTitle>
                            <DialogDescription>
                              Provide a brief report on the resolution steps taken for Zone {alert.zone_id}.
                            </DialogDescription>
                          </DialogHeader>
                          <div className="py-4 space-y-4">
                            <div className="space-y-2">
                              <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase tracking-widest">
                                <MessageSquare className="h-3 w-3" /> Resolution Notes
                              </div>
                              <Textarea 
                                placeholder="E.g., Visual inspection complete, debris cleared..." 
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                className="min-h-[100px] border-border/40 focus:border-primary transition-colors"
                              />
                            </div>
                          </div>
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setResolvingId(null)}>Cancel</Button>
                            <Button 
                              onClick={handleResolve} 
                              disabled={isSubmitting || !notes.trim()}
                              className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold"
                            >
                              Confirm Resolution
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
