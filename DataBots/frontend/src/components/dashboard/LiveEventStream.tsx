import React, { useState, useEffect } from 'react';
import { fetchDashboardEvents } from '../../services/api';
import { Radio, ShieldAlert, CheckCircle2 } from 'lucide-react';

export const LiveEventStream: React.FC = () => {
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    const loadEvents = () => {
      fetchDashboardEvents().then((data) => {
        if (data && data.length > 0) {
          setEvents(data);
        }
      });
    };

    loadEvents();
    const interval = setInterval(loadEvents, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Radio className="w-5 h-5 text-emerald-500 animate-pulse" />
          <h3 className="text-base font-bold text-slate-900">Live Ad Event Stream</h3>
          <span className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
            Realtime 9M Stream
          </span>
        </div>
        <span className="text-xs text-slate-400">ClickHouse ad_events fact table</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-600">
          <thead className="bg-slate-50 uppercase font-semibold text-slate-400 border-b border-slate-200">
            <tr>
              <th className="px-4 py-3">Event ID</th>
              <th className="px-4 py-3">App Name</th>
              <th className="px-4 py-3">Ad Format</th>
              <th className="px-4 py-3">Geo / Device Profile</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">eCPM ($)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {events.map((evt) => (
              <tr key={evt.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3 font-mono font-medium text-slate-400">{evt.id}</td>
                <td className="px-4 py-3 font-semibold text-slate-800">{evt.app}</td>
                <td className="px-4 py-3 text-slate-600">{evt.adFormat}</td>
                <td className="px-4 py-3 text-slate-500">{evt.geo}</td>
                <td className="px-4 py-3">
                  {evt.filled ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <CheckCircle2 className="w-3 h-3" /> Filled
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-red-50 text-red-700 border border-red-200">
                      <ShieldAlert className="w-3 h-3" /> {evt.status}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-mono font-bold text-slate-700">{evt.ecpm}</td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  Loading live event stream from ClickHouse...
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
