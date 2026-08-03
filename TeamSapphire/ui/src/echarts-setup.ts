// Modular import: ~755KB vs ~1.4MB for the full barrel (`echarts`).
import * as echarts from "echarts/core";
import { BarChart, FunnelChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  GraphicComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import EChartsCoreImport from "echarts-for-react/lib/core";

echarts.use([
  BarChart,
  FunnelChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  GraphicComponent,
  CanvasRenderer,
]);

// Vite's CJS interop double-wraps this package's default export
// (`{ default: EChartsReactCore }` instead of the class itself) — unwrap
// defensively rather than importing the raw default in every chart file.
export const EChartsReactCore: typeof EChartsCoreImport =
  (EChartsCoreImport as any).default ?? EChartsCoreImport;

export default echarts;
