import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { AlertTriangle, Clock, Map, TrendingUp, AlertCircle, Info } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

export function ForecastDashboard({ 
  forecastData, 
  onTimeScrub, 
  currentHourIndex,
  displayCells
}: { 
  forecastData: any, 
  onTimeScrub: (idx: number) => void,
  currentHourIndex: number,
  displayCells: any[]
}) {
  if (!forecastData || !forecastData.cells || forecastData.cells.length === 0) {
    return (
      <Card className="bg-slate-900 border-slate-800 text-slate-100 flex-1">
        <CardContent className="p-8 flex items-center justify-center text-slate-500">
          Loading 24-hour predictive forecast...
        </CardContent>
      </Card>
    );
  }

  // 1. Data Aggregation for Summary & Chart
  const chartData = useMemo(() => {
    const hours = forecastData.forecast_horizon_hours;
    const data = [];
    
    // Find peak risk across all cells for each hour
    for (let i = 0; i < hours; i++) {
      let maxRisk = 0;
      let timestamp = "";
      
      forecastData.cells.forEach((cell: any) => {
        if (cell.predictions && cell.predictions[i]) {
          timestamp = cell.predictions[i].timestamp;
          if (cell.predictions[i].risk_score > maxRisk) {
            maxRisk = cell.predictions[i].risk_score;
          }
        }
      });
      
      // Format time (e.g., '14:00')
      let timeLabel = "T+" + i;
      if (timestamp) {
        try {
          const d = new Date(timestamp);
          timeLabel = d.getHours().toString().padStart(2, '0') + ':00';
        } catch (e) {}
      }
      
      data.push({
        timeLabel,
        rawTime: timestamp,
        hourIndex: i,
        peakRisk: maxRisk
      });
    }
    return data;
  }, [forecastData]);

  // Calculate Peak Metrics
  let overallPeakRisk = 0;
  let peakTime = "N/A";
  
  chartData.forEach(d => {
    if (d.peakRisk > overallPeakRisk) {
      overallPeakRisk = d.peakRisk;
      peakTime = d.timeLabel;
    }
  });

  const getRiskLabel = (score: number) => {
    if (score >= 80) return { label: 'CRITICAL', color: 'bg-red-500/20 text-red-500 border-red-500/30' };
    if (score >= 60) return { label: 'HIGH', color: 'bg-orange-500/20 text-orange-500 border-orange-500/30' };
    if (score >= 40) return { label: 'MODERATE', color: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30' };
    return { label: 'LOW', color: 'bg-green-500/20 text-green-500 border-green-500/30' };
  };

  const peakBadge = getRiskLabel(overallPeakRisk);
  
  // Format the current selected time for the scrubber UI
  const currentScrubData = chartData[currentHourIndex];

  // Calculate NH-10 Route Safety dynamically based on the scrubber's current hour
  let nh10Critical = 0;
  let nh10High = 0;
  if (displayCells) {
    displayCells.forEach(cell => {
      if (cell.near_nh10) {
        if (cell.risk_level === 'critical' || cell.risk_level === 'CRITICAL') nh10Critical++;
        else if (cell.risk_level === 'high' || cell.risk_level === 'HIGH') nh10High++;
      }
    });
  }

  let routeSafety = "Safe Route";
  let routeColor = "text-green-400";
  if (nh10Critical > 0) {
    routeSafety = "Dangerous Route";
    routeColor = "text-red-500";
  } else if (nh10High > 0) {
    routeSafety = "Moderate Risk Route";
    routeColor = "text-orange-400";
  }

  return (
    <Card className="bg-slate-900 border-slate-800 text-slate-100 w-full">
      <CardHeader className="pb-4">
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-xl font-bold flex items-center gap-2">
              <Clock className="w-5 h-5 text-teal-500" />
              24-Hour Landslide Risk Forecast
            </CardTitle>
            <CardDescription className="text-slate-400 mt-1">
              Weather Data Source: {forecastData.forecast_source}
            </CardDescription>
          </div>
          <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/30">
            <Info className="w-3 h-3 mr-1"/>
            Development / Scenario Output
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="flex flex-col gap-6 p-6">
        
        {/* SUMMARY CARDS */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-500 mb-1 font-medium">PEAK FORECAST RISK</div>
            <div className="text-2xl font-bold">
               <span className={`text-sm px-2 py-0.5 rounded border ${peakBadge.color}`}>
                 {peakBadge.label}
               </span>
            </div>
          </div>
          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-500 mb-1 font-medium">PEAK TIME</div>
            <div className="text-2xl font-bold text-white">{peakTime}</div>
          </div>
          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-500 mb-1 font-medium">NH-10 FORECAST EXPOSURE</div>
            <div className={`text-lg font-bold ${routeColor}`}>{routeSafety}</div>
            <div className="text-[10px] text-slate-400 mt-1">{nh10Critical + nh10High} high-risk cells intersecting</div>
          </div>
          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
            <div className="text-xs text-slate-500 mb-1 font-medium">FORECAST CONFIDENCE</div>
            <div className="text-sm font-bold text-slate-400">Model Validation Pending</div>
          </div>
        </div>

        {/* TIME SCRUBBER */}
        <div className="bg-slate-950 p-5 rounded-lg border border-slate-800">
          <div className="flex justify-between items-center mb-4">
            <div className="text-sm font-medium text-slate-300 flex items-center gap-2">
              <Map className="w-4 h-4 text-teal-500" />
              Spatial Forecast Time Scrubber
            </div>
            <div className="text-lg font-bold text-teal-400">
              {currentScrubData ? currentScrubData.timeLabel : 'NOW'}
            </div>
          </div>
          
          <input 
            type="range" 
            min="0" 
            max={forecastData.forecast_horizon_hours - 1} 
            value={currentHourIndex}
            onChange={(e) => onTimeScrub(parseInt(e.target.value))}
            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-500"
          />
          <div className="flex justify-between text-xs text-slate-500 mt-2">
            <span>NOW</span>
            <span>+12h</span>
            <span>+24h</span>
          </div>
        </div>

        {/* RISK TIMELINE CHART */}
        <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 h-[400px]">
          <div className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-orange-500" />
            Regional Peak Risk Trajectory
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis dataKey="timeLabel" stroke="#475569" fontSize={12} tickMargin={10} />
              <YAxis stroke="#475569" fontSize={12} domain={[0, 100]} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f8fafc' }}
                itemStyle={{ color: '#2dd4bf' }}
              />
              <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'CRITICAL', fill: '#ef4444', fontSize: 10 }} />
              <ReferenceLine y={60} stroke="#f97316" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'HIGH', fill: '#f97316', fontSize: 10 }} />
              <Line 
                type="monotone" 
                dataKey="peakRisk" 
                stroke="#2dd4bf" 
                strokeWidth={3}
                dot={{ r: 4, fill: '#0f172a', stroke: '#2dd4bf', strokeWidth: 2 }}
                activeDot={{ r: 6, fill: '#2dd4bf' }}
                animationDuration={500}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        
      </CardContent>
    </Card>
  );
}
