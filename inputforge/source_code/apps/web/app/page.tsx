import { Suspense } from "react";

import { BaselineApp } from "./baseline/BaselineApp";
import { loadDashboardData } from "./baseline/data";

export const dynamic = "force-dynamic";

export default async function Home() {
  const data = await loadDashboardData();
  return (
    <Suspense fallback={null}>
      <BaselineApp data={data} />
    </Suspense>
  );
}
