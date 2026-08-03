import { Suspense } from "react";

import { BaselineApp } from "../../baseline/BaselineApp";
import { loadDashboardData } from "../../baseline/data";

export const dynamic = "force-dynamic";

interface IncidentPageProps {
  params: Promise<{ incidentId: string }>;
}

export default async function IncidentPage({ params }: IncidentPageProps) {
  const [{ incidentId }, data] = await Promise.all([params, loadDashboardData()]);

  return (
    <Suspense fallback={null}>
      <BaselineApp data={data} incidentId={incidentId} />
    </Suspense>
  );
}
