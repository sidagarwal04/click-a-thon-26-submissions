import React, { useState, useEffect } from 'react';
import { ModuleType, AnomalyIncident } from './types';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { DashboardView } from './components/dashboard/DashboardView';
import { RcaView } from './components/rca/RcaView';
import { fetchAnomalies, approveRcaFinding } from './services/api';

export function App() {
  const [activeModule, setActiveModule] = useState<ModuleType>('rca');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [anomalies, setAnomalies] = useState<AnomalyIncident[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchAnomalies().then((data) => {
      if (data && data.length > 0) {
        setAnomalies(data);
      }
    });
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleApprove = (id: string) => {
    const targetAnomaly = anomalies.find((a) => a.id === id) || anomalies[0];
    if (targetAnomaly) {
      approveRcaFinding(targetAnomaly).then((res) => {
        if (res.stored_in_clickhouse) {
          showToast(`Finding ${id} APPROVED & vector saved in ClickHouse!`);
        } else {
          showToast(`Finding ${id} APPROVED by operator.`);
        }
      });
    }

    setAnomalies((prev) =>
      prev.map((a) => {
        if (a.id === id) {
          return {
            ...a,
            humanReview: {
              status: 'APPROVED',
              reviewedAt: new Date().toUTCString(),
              reviewedBy: 'Umesh (AdOps Lead)',
              feedbackNote: 'Human approved diagnosis & identity factor attribution.',
            },
          };
        }
        return a;
      })
    );
  };

  const handleFlagHallucination = (id: string, reason: string, feedback: string) => {
    setAnomalies((prev) =>
      prev.map((a) => {
        if (a.id === id) {
          return {
            ...a,
            humanReview: {
              status: 'HALLUCINATION',
              reviewedAt: new Date().toUTCString(),
              reviewedBy: 'Umesh (AdOps Lead)',
              hallucinationReason: reason,
              feedbackNote: feedback || 'Flagged model hallucination; recorded trace feedback.',
            },
          };
        }
        return a;
      })
    );
    showToast(`Anomaly ${id} FLAGGED as AI Hallucination! Feedback sent to Langfuse.`);
  };

  const handleUpdateAnomaly = (updated: AnomalyIncident) => {
    setAnomalies((prev) => {
      const idx = prev.findIndex((a) => a.id === updated.id);
      if (idx !== -1) {
        const next = [...prev];
        next[idx] = updated;
        return next;
      }
      return [updated, ...prev];
    });
  };

  const pendingCount = anomalies.filter((a) => a.humanReview.status === 'PENDING').length;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 text-slate-900 font-sans">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-4 right-4 z-50 px-3.5 py-2.5 rounded-lg bg-white border border-slate-200 text-[12px] font-semibold text-slate-900 shadow-xl animate-fade-in flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-brand-500 shrink-0" />
          {toastMessage}
        </div>
      )}

      {/* App Sidebar */}
      <Sidebar
        activeModule={activeModule}
        setActiveModule={setActiveModule}
        collapsed={sidebarCollapsed}
        setCollapsed={setSidebarCollapsed}
        anomaliesCount={anomalies.length}
        pendingCount={pendingCount}
      />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <Header
            activeModule={activeModule}
            anomaliesCount={anomalies.length}
            pendingCount={pendingCount}
          />

          <main className="flex-1 overflow-y-auto p-5 min-h-0 bg-slate-50">
            {activeModule === 'rca' ? (
              <RcaView
                anomalies={anomalies}
                onApprove={handleApprove}
                onFlagHallucination={handleFlagHallucination}
                onUpdateAnomaly={handleUpdateAnomaly}
              />
            ) : (
              <DashboardView
                onNavigateToRca={() => setActiveModule('rca')}
                pendingRcaCount={pendingCount}
              />
            )}
          </main>
        </div>
    </div>
  );
}

export default App;
