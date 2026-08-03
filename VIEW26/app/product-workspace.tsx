"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  MessageCircle, Inbox, LayoutGrid, Rows3, Plus, Activity, CircleDot,
  Search, RotateCcw, ChevronDown, ArrowUp, ArrowUpRight, Flag, Sparkles,
  ExternalLink, X, AlertCircle, Check, RefreshCw, Braces, Boxes,
} from "lucide-react";

import ContextGraph from "./context-graph";
import { Chart, type AnalyticsChart } from "./charts";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";

const API = process.env.NEXT_PUBLIC_FEATURELENS_API ?? "http://localhost:8080";
const LIBRECHAT_URL = process.env.NEXT_PUBLIC_LIBRECHAT_URL ?? "";

function powerChatURL() {
  if (LIBRECHAT_URL) return LIBRECHAT_URL;
  if (typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return "http://localhost:3080";
  }
  return "";
}

type View = "ask" | "decisions" | "dashboards" | "releases" | "pipeline" | "context" | "trace";
type RuntimeStatus = { enabled: boolean; model?: string; prompt_version?: string; provider?: string };
type EventPreflight = { rows: number; eventTypes: string[]; fields: number; firstEvent: string; lastEvent: string };
type UploadFile = { name: string; size: number; text: string };
type RunEvent = { run_id: string; stage: string; message: string; timestamp: string };

type AnalysisTraceStep = {
  id: string;
  observation_id?: string;
  kind: string;
  status: string;
  duration_ms: number;
  input?: Record<string, unknown>;
  output?: unknown;
  error?: string;
};

type AnalysisTrace = {
  trace_id: string;
  role: string;
  feature: string;
  question: string;
  context_version: number;
  schema_version: string;
  dataset_rows: number;
  steps: AnalysisTraceStep[];
};

type LangfuseObservation = {
  id: string;
  trace_id: string;
  parent_observation_id?: string;
  name?: string;
  type?: string;
  level?: string;
  status_message?: string;
  version?: string;
  environment?: string;
  start_time?: string;
  end_time?: string;
  input?: unknown;
  output?: unknown;
  metadata?: Record<string, unknown>;
  model?: string;
  usage?: Record<string, unknown>;
  cost?: number;
  latency?: number;
  trace_name?: string;
  tags?: string[];
  release?: string;
};

type LangfuseScore = {
  id: string;
  name: string;
  value: unknown;
  data_type: "NUMERIC" | "BOOLEAN" | "CATEGORICAL" | "TEXT" | "CORRECTION";
  source: "API" | "ANNOTATION" | "EVAL";
  timestamp?: string;
  comment?: string;
  author_user_id?: string;
  subject: { kind: "trace" | "observation" | "session" | "experiment"; id: string; trace_id?: string };
};

type LangfuseTraceInsights = {
  enabled: boolean;
  status: "disabled" | "pending" | "synced";
  trace_id: string;
  url?: string;
  observations: LangfuseObservation[];
  scores: LangfuseScore[];
  summary: { observation_count: number; score_count: number; generation_count: number; total_cost: number; total_tokens: number; latency: number };
};

type KeyFinding = {
  point: string;
  why: string;
  evidence?: string;
  severity?: string;
};

type Insight = {
  headline: string;
  summary: string;
  why: string;
  confidence: number;
  recommended_action: string;
  key_findings?: KeyFinding[];
  sql?: string;
  trace_id?: string;
  provenance?: { generator: string; provider?: string; model?: string; prompt_version: string };
  trace?: AnalysisTrace;
};

type Contract = {
  feature: string;
  role: string;
  playbook: string;
  answerability: string;
  context_version: number;
  schema_versions: string[];
  limitations?: string[];
};

type AnalyticsKPI = {
  key: string;
  label: string;
  formatted_value: string;
  confidence: number;
  sample_size?: number;
  source_playbook?: string;
};
type ReleaseKPI = AnalyticsKPI & { evidence_label: string };
type RankedInsight = { rank: number; headline: string; summary: string; why?: string; recommended_action: string; confidence: number; playbook: string };
type FeatureAnalyticsBundle = {
  feature: string;
  status: string;
  context_version: number;
  schema_version: string;
  generated_at?: string;
  kpis: AnalyticsKPI[];
  charts: AnalyticsChart[];
  insights: RankedInsight[];
  playbooks: string[];
  limitations?: string[];
};

type Run = {
  id: string;
  stage: string;
  execution_mode: string;
  input?: { name: string; schema_version?: number; use_existing_data?: boolean };
  trace_id?: string;
  error?: string;
  profile?: { rows: number; event_counts: Record<string, number>; fields: { path: string }[] };
  schema?: {
    version: number;
    database: string;
    table: string;
    ddl: string;
    status: string;
    partition_by: string;
    order_by: string[];
  };
  validation?: { passed: boolean; checks: { name: string; passed: boolean; details: string }[] };
  context?: {
    version: number;
    parent_version: number;
    feature: string;
    summary: string;
    state: string;
    schema_versions: string[];
    nodes: { key: string; type: string; name: string; status: string; confidence: number; properties?: Record<string, unknown> }[];
    edges: { from: string; relation: string; to: string }[];
    conflicts: { key: string; severity: string; description: string; status: string }[];
  };
  insight?: Insight;
  analysis_contract?: Contract;
  analytics_bundle?: FeatureAnalyticsBundle;
  created_at?: string;
  updated_at?: string;
};

function preferNewerRun(current: Run | undefined, incoming: Run) {
  if (!current || current.id !== incoming.id) return incoming;
  const currentUpdated = Date.parse(current.updated_at ?? "");
  const incomingUpdated = Date.parse(incoming.updated_at ?? "");
  if (Number.isFinite(currentUpdated) && Number.isFinite(incomingUpdated) && incomingUpdated < currentUpdated) return current;
  return incoming;
}

function reconcileRuns(current: Run[], incoming: Run[]) {
  const currentByID = new Map(current.map((item) => [item.id, item]));
  return incoming.map((item) => preferNewerRun(currentByID.get(item.id), item));
}

type ConversationResponse = {
  resolved_question: string;
  feature_scope: string[];
  context_version: number;
  mode: "dashboard" | "single";
  contract: Contract;
  insight: Insight;
  kpis?: AnalyticsKPI[];
  charts: AnalyticsChart[];
  sources: { contract: Contract; insight: Insight }[];
  follow_up_prompts: string[];
};

type ConversationTurn = {
  id: string;
  role: "user" | "assistant";
  content: string;
  featureScope?: string[];
  response?: ConversationResponse;
};

type Chat = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  turns: ConversationTurn[];
};

type CatalogTable = {
  database: string;
  name: string;
  category: "source" | "agent_created" | "governance" | "supporting";
  engine: string;
  rows: number;
  context_registered: boolean;
};

type DataCatalog = { source_database: string; control_database: string; tables: CatalogTable[] };

const featurePackages = [
  {
    id: "express",
    order: "01",
    name: "Express Checkout",
    schemaVersion: 1,
    rows: "5,507",
    outcome: "Conversion lift · OTP friction · time to pay",
    description: "One-tap checkout for returning travellers using a saved payment method and OTP.",
    spec: "# Express Checkout\n\nOne-tap checkout for returning travellers.\n\n## Product questions\n- Does Express lift checkout completion?\n- Where does OTP or payment fail?\n- Which cities and devices perform best?",
  },
  {
    id: "group",
    order: "02",
    name: "Group / Family",
    schemaVersion: 2,
    rows: "4,412",
    outcome: "Group creation · member completion · payment conversion",
    description: "Coordinate multi-traveller applications and shared payment completion.",
    spec: "# Group / Family\n\nCoordinate multi-traveller applications.\n\n## Product questions\n- Where do groups drop before payment?\n- Which group sizes complete best?",
  },
  {
    id: "sharing",
    order: "03",
    name: "Status Sharing",
    schemaVersion: 2,
    rows: "3,108",
    outcome: "Share adoption · recipient engagement · support deflection",
    description: "Share a live visa application status with trusted recipients.",
    spec: "# Status Sharing\n\nShare live application status.\n\n## Product questions\n- Who shares and who engages?\n- Does sharing reduce support demand?",
  },
  {
    id: "recovery",
    order: "04",
    name: "Abandoned Checkout Recovery",
    schemaVersion: 2,
    rows: "4,902",
    outcome: "Recovery reach · resumed checkout · recovered revenue",
    description: "Bring travellers back after they leave an incomplete checkout.",
    spec: "# Abandoned Checkout Recovery\n\nRecover incomplete checkout journeys.\n\n## Product questions\n- Which channels recover the most users?\n- How much revenue is recovered?",
  },
  {
    id: "forex",
    order: "05",
    name: "Instant Forex",
    schemaVersion: 2,
    rows: "3,955",
    outcome: "Quote adoption · price certainty · currency-pair performance",
    description: "Show and lock a local-currency visa price before purchase.",
    spec: "# Instant Forex\n\nShow and lock a local-currency price.\n\n## Product questions\n- Does price certainty improve completion?\n- Which currency pairs have strongest adoption?",
  },
] as const;

type FeatureID = (typeof featurePackages)[number]["id"] | "unseen" | `custom:${string}`;

const stageOrder = ["received", "profiling", "schema_proposed", "awaiting_approval", "schema_verified", "context_published", "analytics_complete", "completed"];
const fallbackStarterPrompts = [
  "Which cities and devices show the strongest Express Checkout completion, and how wide is the gap between segments?",
  "Which published feature has the highest end-to-end completion rate, and which one is lagging furthest behind?",
  "Where is the largest mobile or OS performance gap, and how much completion is it costing us?",
];

// PM-voiced expansions of each question intent. The wording is deliberate:
// the conversation endpoint re-classifies submitted text with the same keyword
// rules the Context Agent used (ClassifyIntent / recoveryIntent), so every
// template keeps its intent's trigger words while framing the decision a PM
// actually has to make.
const pmPromptByIntent: Record<string, (feature: string) => string> = {
  conversion_comparison: (feature) => `Is ${feature} actually lifting end-to-end conversion versus the standard flow, and how many percentage points is it worth?`,
  platform_failure: (feature) => `Where are ${feature} users failing at OTP or payment, and which device and OS cohorts should engineering prioritise first?`,
  completion_trend: (feature) => `How has ${feature} completion trended week over week since launch — is momentum building or flattening out?`,
  segment_comparison: (feature) => `Which cities and devices show the strongest ${feature} completion, and how wide is the gap between the best and weakest segments?`,
  feature_adoption: (feature) => `Which traveller segments are adopting ${feature} the most, and where is adoption still lagging behind?`,
  funnel_diagnosis: (feature) => `Where in the ${feature} funnel are we losing the most users before payment, and which drop should we fix first?`,
  latency_performance: (feature) => `Is ${feature} actually faster for returning travellers, and how much time does it save at checkout?`,
  customer_geography: (feature) => `Where are our ${feature} customers coming from — which cities and locations drive the most volume?`,
  group_size_completion: (feature) => `Which group sizes complete best for ${feature}, and where do larger groups fall off before payment?`,
  group_traveller_churn: (feature) => `How often are travellers removed from ${feature} applications before completion, and what is that churn costing us?`,
  group_document_bottleneck: (feature) => `Is document completion the biggest bottleneck for ${feature} groups, and which step stalls them the longest?`,
  group_segments: (feature) => `Which destinations drive the most group demand for ${feature}, and how do those segments differ in completion?`,
  recovery_channel: (feature) => `Which channels recover the most abandoned checkouts for ${feature}, and how strong is their open → click follow-through?`,
  recovery_timing: (feature) => `Which reminder timing recovers the most ${feature} checkouts — within 1h, 24h, or 48h of drop-off?`,
  recovery_drop_step: (feature) => `Which checkout step is the largest recoverable revenue opportunity for ${feature}?`,
  recovery_segments: (feature) => `Which device and geo segments respond best to ${feature} outreach, and where is it wasted?`,
};

// The Context Agent publishes each feature's spec questions as business_question
// nodes (key "question:<feature-slug>:<n>") carrying their classified intent, so
// the welcome prompts can be generated from the latest published context instead
// of a hardcoded list.
function starterPromptsFromContext(context: Run["context"] | null): string[] {
  const nodes = context?.nodes ?? [];
  const questions = nodes.filter((node) => node.type === "business_question");
  if (questions.length === 0) return fallbackStarterPrompts;
  const featureNames = new Map(nodes.filter((node) => node.type === "feature").map((node) => [node.key.replace("feature:", ""), node.name]));
  const byFeature = new Map<string, string[]>();
  for (const node of questions) {
    const slug = node.key.split(":")[1] ?? node.key;
    const feature = featureNames.get(slug) ?? slug.replaceAll(/[_-]/g, " ");
    const intent = typeof node.properties?.intent === "string" ? node.properties.intent : "";
    const prompt = pmPromptByIntent[intent]?.(feature) ?? node.name;
    byFeature.set(slug, [...(byFeature.get(slug) ?? []), prompt]);
  }
  const groups = [...byFeature.values()];
  const picked = new Set<string>();
  for (let round = 0; picked.size < 4; round++) {
    const before = picked.size;
    for (const group of groups) {
      if (round < group.length && picked.size < 4) picked.add(group[round]);
    }
    if (picked.size === before) break;
  }
  return [...picked];
}
const knownFeatureNames = new Set(featurePackages.map((item) => item.name.toLowerCase()));
const maxIntakeBytes = 15 * 1024 * 1024;

function normalize(value?: string) {
  return (value ?? "").trim().toLowerCase();
}

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function customFeatureID(run: Pick<Run, "id">): FeatureID {
  return `custom:${run.id}`;
}

function featureSelectionForRun(run: Run): FeatureID {
  return featurePackages.find((feature) => normalize(feature.name) === normalize(run.input?.name))?.id ?? customFeatureID(run);
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(value?: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

const chatStorageKey = "featurelens.chats.v1";

function createChat(): Chat {
  const now = Date.now();
  return { id: `chat-${now}-${Math.random().toString(36).slice(2, 8)}`, title: "New chat", createdAt: now, updatedAt: now, turns: [] };
}

function chatTitleFrom(question: string) {
  const clean = question.replace(/\s+/g, " ").trim();
  return clean.length > 48 ? `${clean.slice(0, 48).trimEnd()}…` : clean;
}

function loadStoredChats(): Chat[] {
  try {
    const raw = window.localStorage.getItem(chatStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Chat[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((chat) => chat && typeof chat.id === "string" && typeof chat.title === "string" && Array.isArray(chat.turns));
  } catch {
    return [];
  }
}

function compactID(value?: string) {
  if (!value) return "pending";
  return value.length > 18 ? `${value.slice(0, 10)}…${value.slice(-5)}` : value;
}

function inspectNDJSON(text: string): EventPreflight {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length === 0) throw new Error("Event file is empty");
  const eventTypes = new Set<string>();
  const fields = new Set<string>();
  const events: string[] = [];
  lines.forEach((line, index) => {
    let row: Record<string, unknown>;
    try { row = JSON.parse(line) as Record<string, unknown>; } catch { throw new Error(`Line ${index + 1} is not valid JSON`); }
    const event = row.event ?? row.event_name;
    if (typeof event !== "string" || !event.trim()) throw new Error(`Line ${index + 1} needs event or event_name`);
    if (!row.timestamp) throw new Error(`Line ${index + 1} needs timestamp`);
    eventTypes.add(event);
    events.push(event);
    Object.keys(row).forEach((field) => fields.add(field));
  });
  return { rows: lines.length, eventTypes: [...eventTypes], fields: fields.size, firstEvent: events[0], lastEvent: events.at(-1) ?? events[0] };
}

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex items-center justify-center rounded-md bg-primary text-primary-foreground",
        compact ? "size-6" : "size-7"
      )}
    >
      <Boxes className={compact ? "size-3.5" : "size-4"} />
    </span>
  );
}

// Small helper: a labelled statistic block used across dashboards and detail panes.
function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2.5">
      <span className="block text-xs text-muted-foreground">{label}</span>
      <strong className="mt-1 block text-lg font-semibold leading-tight tabular-nums">{value}</strong>
      {hint ? <small className="mt-0.5 block text-xs text-muted-foreground">{hint}</small> : null}
    </div>
  );
}

function sentenceCase(value: string) {
  const clean = value.replaceAll("_", " ").replace(/\s+/g, " ").trim();
  return clean ? clean[0].toUpperCase() + clean.slice(1) : clean;
}

function uniqueSegmentLabel(value: string) {
  const values = value.split("/").map((item) => item.trim()).filter(Boolean);
  return values.filter((item, index) => values.findIndex((candidate) => candidate.toLowerCase() === item.toLowerCase()) === index).join(" / ");
}

function compactFunnelStage(stage: string, feature: string) {
  const featureWords = new Set(feature.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean));
  const stageWords = stage.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
  const compact = stageWords.filter((word) => !featureWords.has(word));
  return sentenceCase((compact.length > 0 ? compact : stageWords).join(" "));
}

function releaseDecisionKPIs(bundle: FeatureAnalyticsBundle): ReleaseKPI[] {
  const byKey = new Map(bundle.kpis.map((kpi) => [kpi.key, { ...kpi }]));
  const funnel = bundle.charts.find((chart) => chart.key === "feature_funnel")?.series[0]?.points ?? [];
  let largestLoss: { from: string; to: string; rate: number; sample: number } | undefined;
  for (let index = 1; index < funnel.length; index++) {
    const previous = funnel[index - 1];
    const current = funnel[index];
    if (previous.value <= 0) continue;
    const rate = Math.max(0, (previous.value - current.value) / previous.value);
    if (!largestLoss || rate > largestLoss.rate) largestLoss = { from: previous.label, to: current.label, rate, sample: previous.value };
  }
  if (largestLoss) {
    const existing = byKey.get("largest_funnel_loss");
    byKey.set("largest_funnel_loss", {
      key: "largest_funnel_loss",
      label: `Largest drop-off · ${compactFunnelStage(largestLoss.from, bundle.feature)} → ${compactFunnelStage(largestLoss.to, bundle.feature)}`,
      formatted_value: `${(largestLoss.rate * 100).toFixed(1)}%`,
      confidence: existing?.confidence ?? .95,
      sample_size: existing?.sample_size ?? largestLoss.sample,
      source_playbook: existing?.source_playbook,
    });
  }

  const segmentChart = bundle.charts.find((chart) => chart.key === "segment_completion");
  const preferredDimension = bundle.playbooks.some((playbook) => playbook.includes("instant-forex")) ? ["destination", "target_currency", "to_currency", "city", "device_type"] : ["city", "device_type", "os"];
  const segmentSeries = preferredDimension.map((key) => segmentChart?.series.find((series) => series.key === key)).find(Boolean) ?? segmentChart?.series[0];
  if (segmentSeries?.points.length) {
    const strongest = segmentSeries.points.reduce((highest, point) => point.value > highest.value ? point : highest);
    byKey.set("strongest_segment", {
      key: "strongest_segment",
      label: `Strongest ${sentenceCase(segmentSeries.label).toLowerCase()} · ${sentenceCase(strongest.label)}`,
      formatted_value: `${strongest.value.toFixed(1)}%`,
      confidence: .9,
      sample_size: strongest.sample_size,
      source_playbook: "dashboard:feature-segments:v1",
    });
  }

  const dashboard = bundle.playbooks.find((playbook) => playbook.startsWith("dashboard:") && !playbook.includes("completion-trend") && !playbook.includes("feature-segments")) ?? "";
  const priority = dashboard.includes("express-checkout")
    ? ["lift_vs_standard", "weakest_otp_segment", "p95_latency", "largest_funnel_loss"]
    : dashboard.includes("group-family")
      ? ["completion_rate", "largest_funnel_loss", "weakest_group_size", "document_bottleneck"]
      : dashboard.includes("checkout-recovery")
        ? ["completion_rate", "best_recovery_channel", "best_recovery_timing", "recoverable_drop_step"]
        : dashboard.includes("status-sharing")
          ? ["completion_rate", "largest_funnel_loss", "strongest_segment", "segment_opportunity_gap"]
          : dashboard.includes("instant-forex")
            ? ["completion_rate", "largest_funnel_loss", "strongest_segment", "segment_opportunity_gap"]
            : ["completion_rate", "largest_funnel_loss", "strongest_segment", "segment_opportunity_gap"];

  const completionLabels: Record<string, string> = {
    "dashboard:express-checkout:v1": "Shown → paid completion",
    "dashboard:group-family:v1": "Group submission rate",
    "dashboard:status-sharing-engagement:v1": "Link → recipient action",
    "dashboard:checkout-recovery:v1": "Recovered checkout rate",
    "dashboard:instant-forex:v1": "Offer → purchase attach rate",
  };
  const relabel = (kpi: AnalyticsKPI): AnalyticsKPI => {
    if (kpi.key === "completion_rate") return { ...kpi, label: completionLabels[dashboard] ?? "End-to-end completion" };
    if (kpi.key === "lift_vs_standard") return { ...kpi, label: "Incremental conversion vs standard" };
    if (kpi.key === "p95_latency") return { ...kpi, label: "Slowest 5% time to pay" };
    if (kpi.key === "weakest_otp_segment") {
      const segment = uniqueSegmentLabel(kpi.label.split("·").at(-1)?.trim() ?? "platform cohort");
      return { ...kpi, label: `Weakest OTP cohort · ${segment}` };
    }
    if (kpi.key === "weakest_group_size") return { ...kpi, label: kpi.label.replace("Weakest group size", "At-risk group size") };
    if (kpi.key === "document_bottleneck") return { ...kpi, label: kpi.label.replace("Document bottleneck", "Document completion") };
    if (kpi.key === "best_recovery_channel") return { ...kpi, label: kpi.label.replace("Best recovery", "Best recovery channel") };
    if (kpi.key === "recoverable_drop_step") return { ...kpi, label: kpi.label.replace("Recovery ·", "Best recoverable step ·") };
    return kpi;
  };

  const chosen: AnalyticsKPI[] = [];
  const add = (kpi?: AnalyticsKPI) => {
    if (kpi && !chosen.some((item) => item.key === kpi.key)) chosen.push(relabel(kpi));
  };
  priority.forEach((key) => add(byKey.get(key)));
  bundle.kpis.forEach((kpi) => add(byKey.get(kpi.key)));
  ["completion_rate", "largest_funnel_loss", "strongest_segment"].forEach((key) => add(byKey.get(key)));

  return chosen.slice(0, 4).map((kpi) => ({
    ...kpi,
    evidence_label: `${kpi.sample_size ? `n=${Math.round(kpi.sample_size).toLocaleString()} · ` : ""}${Math.round(kpi.confidence * 100)}% confidence`,
  }));
}

const findingSeverity: Record<string, { dot: string; label: string }> = {
  high: { dot: "bg-rose-500", label: "High impact" },
  medium: { dot: "bg-amber-500", label: "Medium impact" },
  low: { dot: "bg-emerald-500", label: "Context" },
};

function KeyFindingsList({ findings }: { findings: KeyFinding[] }) {
  if (!findings.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <strong className="text-sm font-semibold">Key findings</strong>
      <ol className="flex flex-col gap-2.5">
        {findings.map((finding, index) => {
          const severity = findingSeverity[finding.severity ?? ""] ?? findingSeverity.medium;
          return (
            <li key={`${index}-${finding.point.slice(0, 24)}`} className="flex gap-3 rounded-lg border bg-muted/30 p-3">
              <span className="mt-1 flex size-5 shrink-0 items-center justify-center rounded-full bg-background text-xs font-semibold tabular-nums text-muted-foreground ring-1 ring-border">{index + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <p className="text-sm font-medium leading-snug">{finding.point}</p>
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground"><span className={cn("size-1.5 rounded-full", severity.dot)} />{severity.label}</span>
                </div>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{finding.why}</p>
                {finding.evidence && <p className="mt-1 text-xs text-muted-foreground/80">Grounded in {finding.evidence}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function AnswerCard({ response, onFollowUp, onTrace }: { response: ConversationResponse; onFollowUp: (value: string) => void; onTrace: () => void }) {
  const generated = response.insight.provenance?.generator === "llm";
  const dashboard = response.mode === "dashboard";
  const kpis = response.kpis ?? [];
  const confidencePct = Math.round(response.insight.confidence * 100);
  const confidenceVariant = confidencePct >= 75 ? "secondary" : confidencePct >= 55 ? "outline" : "destructive";
  return (
    <Card className={cn("gap-4", dashboard ? "w-full" : "max-w-3xl")}>
      <CardContent className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <BrandMark compact />
          <div className="min-w-0 flex-1">
            <strong className="block text-sm font-semibold">FeatureLens AI</strong>
            <span className="text-xs text-muted-foreground">{generated ? "LLM synthesis" : "Governed synthesis"} · context v{response.context_version}</span>
          </div>
          <Badge variant={confidenceVariant}>{confidencePct}% confidence</Badge>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {dashboard && <Badge variant="outline"><LayoutGrid className="size-3" /> Dashboard</Badge>}
          {response.feature_scope.map((feature) => <Badge key={feature} variant="secondary">{feature}</Badge>)}
        </div>

        <div>
          <h2 className="text-xl font-semibold leading-snug">{response.insight.headline}</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{response.insight.summary}</p>
        </div>

        {dashboard ? (
          <>
            {kpis.length > 0 && <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{kpis.map((kpi) => <Stat key={kpi.key} label={kpi.label} value={kpi.formatted_value} hint={`${Math.round(kpi.confidence * 100)}% confidence`} />)}</div>}
            {response.charts?.length > 0 && <div className="grid gap-3 lg:grid-cols-2">{response.charts.map((chart) => <Chart key={`${response.insight.trace_id}-${chart.key}`} chart={chart} />)}</div>}
          </>
        ) : response.charts?.length > 0 && <div className="grid gap-3 lg:grid-cols-2 [&>*:first-child:nth-last-child(odd)]:lg:col-span-2">{response.charts.map((chart) => <Chart key={`${response.insight.trace_id}-${chart.key}`} chart={chart} />)}</div>}

        {(response.insight.key_findings?.length ?? 0) > 0 && <KeyFindingsList findings={response.insight.key_findings!} />}

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex gap-2.5 rounded-lg border bg-muted/40 p-3">
            <ArrowUpRight className="size-4 shrink-0 text-muted-foreground" />
            <span><strong className="block text-sm font-medium">Why it matters</strong><p className="mt-0.5 text-sm text-muted-foreground">{response.insight.why}</p></span>
          </div>
          <div className="flex gap-2.5 rounded-lg border bg-muted/40 p-3">
            <Flag className="size-4 shrink-0 text-muted-foreground" />
            <span><strong className="block text-sm font-medium">Recommended next step</strong><p className="mt-0.5 text-sm text-muted-foreground">{response.insight.recommended_action}</p></span>
          </div>
        </div>

        {(response.contract.limitations?.length ?? 0) > 0 && (
          <p className="rounded-lg border border-dashed bg-muted/30 p-3 text-sm text-muted-foreground"><strong className="mr-1.5 font-medium text-foreground">Evidence boundary</strong>{response.contract.limitations?.[0]}</p>
        )}

        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-1.5 text-muted-foreground"><CircleDot className="size-3.5" /> {response.sources.length} governed source{response.sources.length === 1 ? "" : "s"}</span>
          <Button variant="ghost" size="sm" onClick={onTrace}>View trace <ExternalLink className="size-3.5" /></Button>
        </div>

        <Collapsible className="rounded-lg border">
          <CollapsibleTrigger className="group flex w-full items-center justify-between px-3 py-2.5 text-sm font-medium">
            How this answer was generated
            <ChevronDown className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
          </CollapsibleTrigger>
          <CollapsibleContent className="flex flex-col gap-2 border-t p-3">
            {response.sources.map((source) => (
              <div key={`${source.contract.feature}-${source.insight.trace_id}`} className="rounded-md border bg-muted/30 p-2.5">
                <span className="text-xs font-medium text-muted-foreground">{source.contract.feature}</span>
                <strong className="mt-0.5 block text-sm">{source.insight.headline}</strong>
                <small className="text-xs text-muted-foreground">{source.contract.playbook} · {source.contract.answerability}</small>
                {source.insight.sql && (
                  <details className="mt-1.5 text-xs">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">View ClickHouse query</summary>
                    <pre className="mt-1.5 overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs">{source.insight.sql}</pre>
                  </details>
                )}
              </div>
            ))}
          </CollapsibleContent>
        </Collapsible>

        <div className="flex flex-wrap gap-2">
          {response.follow_up_prompts.map((prompt) => (
            <Button key={prompt} variant="outline" size="sm" className="h-auto whitespace-normal py-1.5 text-left" onClick={() => onFollowUp(prompt)}>
              <Sparkles className="size-3.5 shrink-0" /> {prompt}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

const observationNames: Record<string, string> = {
  "tool.clickhouse.query": "analytics.clickhouse_query",
  "evidence.validate": "analytics.evidence_validate",
  "llm.synthesize": "analytics.llm_synthesize",
  "answer.compose": "analytics.portfolio_conversation",
};

const evaluationTargetSteps = new Set(["llm.synthesize", "answer.compose"]);
const finalAnswerStepID = "answer.compose";

function scoreDisplay(score: LangfuseScore) {
  if (typeof score.value === "boolean") return score.value ? "Passed" : "Needs review";
  if (typeof score.value === "number") return score.value >= 0 && score.value <= 1 ? `${Math.round(score.value * 100)}%` : score.value.toFixed(2);
  return String(score.value ?? "—").replaceAll("_", " ");
}

function TraceWorkspace({ insight, tracing }: { insight?: Insight; tracing: RuntimeStatus | null }) {
  const trace = insight?.trace;
  const [selected, setSelected] = useState(trace?.steps?.[0]?.id ?? "");
  const [tab, setTab] = useState<"io" | "evaluations" | "metadata">("io");
  const [langfuse, setLangfuse] = useState<LangfuseTraceInsights | null>(null);
  const [syncState, setSyncState] = useState<"local" | "syncing" | "pending" | "synced" | "unavailable">(tracing?.enabled ? "syncing" : "local");
  const [syncError, setSyncError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [helpful, setHelpful] = useState<boolean | null>(null);
  const [issue, setIssue] = useState("");
  const [comment, setComment] = useState("");
  const [feedbackState, setFeedbackState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [feedbackMessage, setFeedbackMessage] = useState("");

  useEffect(() => {
    if (!trace || !tracing?.enabled) {
      setLangfuse(null); setSyncState("local"); setSyncError("");
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    async function load(attempt: number) {
      if (attempt === 0) setSyncState("syncing");
      try {
        const response = await fetch(`${API}/api/traces/${trace!.trace_id}/langfuse`, { signal: controller.signal });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error ?? "Langfuse insights unavailable");
        if (cancelled) return;
        setLangfuse(payload as LangfuseTraceInsights); setSyncError("");
        const waitingForScores = payload.status === "pending" || (payload.observations?.length > 0 && payload.scores?.length === 0);
        if (waitingForScores && attempt < 3) {
          setSyncState("pending");
          timer = setTimeout(() => void load(attempt + 1), 1500 * (attempt + 1));
        } else setSyncState(payload.status === "synced" ? "synced" : "pending");
      } catch (cause) {
        if (cancelled || controller.signal.aborted) return;
        setSyncState("unavailable"); setSyncError(cause instanceof Error ? cause.message : "Langfuse insights unavailable");
      }
    }
    void load(0);
    return () => { cancelled = true; controller.abort(); if (timer) clearTimeout(timer); };
  }, [trace, tracing?.enabled, refresh]);

  useEffect(() => {
    const helpfulScore = langfuse?.scores.find((score) => score.name === "user_helpful" && typeof score.value === "boolean");
    const issueScore = langfuse?.scores.find((score) => score.name === "issue_category" && typeof score.value === "string");
    if (helpfulScore) { setHelpful(helpfulScore.value as boolean); setComment(helpfulScore.comment ?? ""); }
    if (issueScore) setIssue(String(issueScore.value));
  }, [langfuse]);

  if (!trace) return <EmptyState icon={<Search className="size-6" />} title="No analytical trace selected" body="Ask a question or select a completed feature insight to inspect user input, context resolution, ClickHouse queries, and synthesis." />;

  const step = trace.steps.find((item) => item.id === selected) ?? trace.steps[0];
  const observationFor = (item?: AnalysisTraceStep) => {
    if (!item) return undefined;
    return langfuse?.observations.find((observation) => observation.id === item.observation_id)
      ?? langfuse?.observations.find((observation) => observation.name === observationNames[item.id]);
  };
  const scoresFor = (item?: AnalysisTraceStep) => {
    if (!item) return [];
    const observation = observationFor(item);
    return langfuse?.scores.filter((score) => (score.subject.kind === "observation" && score.subject.id === observation?.id)
      || (item.id === "answer.compose" && score.subject.kind === "trace" && score.subject.id === trace.trace_id)) ?? [];
  };
  const observation = observationFor(step);
  const scores = scoresFor(step);
  const isEvaluationTarget = evaluationTargetSteps.has(step?.id ?? "");
  const isFinalAnswerStep = step?.id === finalAnswerStepID;
  const helpfulScore = langfuse?.scores.find((score) => score.name === "user_helpful" && typeof score.value === "boolean");
  const qualityLabel = helpfulScore ? (helpfulScore.value ? "Helpful" : "Review") : langfuse?.scores.length ? `${langfuse.scores.length} signals` : syncState === "synced" ? "No scores" : "Pending";
  const costLabel = langfuse?.summary.total_cost ? `$${langfuse.summary.total_cost.toFixed(4)}` : "—";
  const statusLabel = syncState === "local" ? "Local trace" : syncState === "syncing" ? "Syncing" : syncState === "pending" ? "Evaluating" : syncState === "synced" ? "Synced" : "Unavailable";
  const finalAnswerStep = trace.steps.find((item) => item.id === finalAnswerStepID);
  const finalAnswerObservationID = observationFor(finalAnswerStep)?.id ?? finalAnswerStep?.observation_id;

  async function submitFeedback() {
    if (helpful === null) return;
    setFeedbackState("saving"); setFeedbackMessage("");
    try {
      const response = await fetch(`${API}/api/traces/${trace!.trace_id}/feedback`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ helpful, issue: helpful ? "" : issue, comment, observation_id: finalAnswerObservationID }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Feedback could not be saved");
      setFeedbackState("saved"); setFeedbackMessage("Feedback added to this Langfuse trace."); setRefresh((value) => value + 1);
    } catch (cause) {
      setFeedbackState("error"); setFeedbackMessage(cause instanceof Error ? cause.message : "Feedback could not be saved");
    }
  }

  const remoteInput = observation?.input ?? step?.input ?? {};
  const remoteOutput = observation?.output ?? step?.output ?? {};

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        <Stat label="Trace" value={<code className="text-sm font-mono">{compactID(trace.trace_id)}</code>} />
        <Stat label="Role" value={<span className="text-sm capitalize">{trace.role.replaceAll("_", " ")}</span>} />
        <Stat label="Context" value={`v${trace.context_version}`} />
        <Stat label="Schema" value={<span className="text-sm">{trace.schema_version}</span>} />
        <Stat label="Rows" value={trace.dataset_rows.toLocaleString()} />
        <Stat label="Quality" value={<span className={cn("text-sm", helpfulScore?.value === false && "text-amber-600 dark:text-amber-400")}>{qualityLabel}</span>} />
        <Stat label="LLM cost" value={<span className="text-sm">{costLabel}</span>} />
        <Stat label="Langfuse" value={<span className="text-sm">{statusLabel}</span>} />
      </div>
      {syncError && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm">
          <span className="text-muted-foreground">Langfuse is temporarily unavailable.</span>
          <Button variant="outline" size="sm" onClick={() => setRefresh((value) => value + 1)}>Retry</Button>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <nav className="flex flex-col gap-1.5">
          {trace.steps.map((item, index) => {
            const signalCount = scoresFor(item).length;
            return (
              <button key={item.id} onClick={() => setSelected(item.id)} className={cn("flex items-center gap-3 rounded-lg border p-2.5 text-left transition-colors", item.id === step?.id ? "border-primary bg-accent" : "hover:bg-accent")}>
                <i className="grid size-7 shrink-0 place-items-center rounded-md bg-muted font-mono text-xs not-italic">{String(index + 1).padStart(2, "0")}</i>
                <span className="min-w-0 flex-1"><strong className="block truncate text-sm font-medium">{item.id.replaceAll(".", " / ")}</strong><small className="text-xs text-muted-foreground">{item.kind} · {item.duration_ms}ms{item.observation_id ? " · linked" : ""}</small></span>
                {signalCount
                  ? <Badge variant="secondary" className="shrink-0">{signalCount}</Badge>
                  : <b className={cn("text-sm", item.status === "completed" ? "text-emerald-600 dark:text-emerald-400" : item.status === "skipped" ? "text-muted-foreground" : "text-destructive")}>{item.status === "completed" ? "✓" : item.status === "skipped" ? "–" : "!"}</b>}
              </button>
            );
          })}
        </nav>
        <Card>
          <CardContent className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0"><span className="text-xs text-muted-foreground">{step?.kind}{observation?.type ? ` · ${observation.type.toLowerCase()}` : ""}</span><h3 className="truncate text-base font-semibold">{step?.id.replaceAll(".", " / ")}</h3></div>
              <div className="flex items-center gap-2">
                <code className="shrink-0 rounded-md bg-muted px-2 py-1 font-mono text-xs">{step?.duration_ms ?? 0} ms</code>
                {tracing?.enabled && <Button variant="outline" size="sm" onClick={() => setRefresh((value) => value + 1)} disabled={syncState === "syncing"}>Refresh</Button>}
                {langfuse?.url && <Button asChild variant="ghost" size="sm"><a href={langfuse.url} target="_blank" rel="noreferrer">Open in Langfuse <ExternalLink className="size-3.5" /></a></Button>}
              </div>
            </div>
            {step?.error && <p className="rounded-md border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive">{step.error}</p>}

            <Tabs value={tab} onValueChange={(value) => setTab(value as typeof tab)}>
              <TabsList>
                <TabsTrigger value="io">Input / output</TabsTrigger>
                <TabsTrigger value="evaluations">Evaluations {scores.length > 0 && <Badge variant="secondary" className="ml-1 h-4 min-w-4 justify-center px-1">{scores.length}</Badge>}</TabsTrigger>
                <TabsTrigger value="metadata">Metadata</TabsTrigger>
              </TabsList>
            </Tabs>

            {tab === "io" && (
              <div className="grid gap-3 lg:grid-cols-2">
                <div><span className="text-xs font-medium text-muted-foreground">Input</span><pre className="mt-1.5 max-h-72 overflow-auto rounded-md bg-muted p-2.5 font-mono text-xs">{JSON.stringify(remoteInput, null, 2)}</pre></div>
                <div><span className="text-xs font-medium text-muted-foreground">Output</span><pre className="mt-1.5 max-h-72 overflow-auto rounded-md bg-muted p-2.5 font-mono text-xs">{JSON.stringify(remoteOutput, null, 2)}</pre></div>
              </div>
            )}

            {tab === "evaluations" && (
              <div className={cn("grid gap-3", isFinalAnswerStep && "lg:grid-cols-[1fr_320px]")}>
                <div className="flex flex-col gap-2">
                  {scores.length ? scores.map((score) => (
                    <div key={score.id} className={cn("rounded-lg border p-3", typeof score.value === "boolean" && (score.value ? "border-emerald-500/40 bg-emerald-500/5" : "border-amber-500/40 bg-amber-500/5"))}>
                      <div className="flex items-center justify-between gap-3">
                        <div><span className="text-xs text-muted-foreground">{score.source}</span><strong className="block text-sm font-medium capitalize">{score.name.replaceAll("_", " ")}</strong></div>
                        <b className="text-sm font-semibold">{scoreDisplay(score)}</b>
                      </div>
                      {score.comment && <p className="mt-1.5 text-sm text-muted-foreground">{score.comment}</p>}
                      <footer className="mt-1.5 text-xs text-muted-foreground">{score.data_type.toLowerCase()}{score.timestamp ? ` · ${formatTime(score.timestamp)}` : ""}{score.author_user_id ? " · human annotation" : ""}</footer>
                    </div>
                  )) : isEvaluationTarget ? (
                    <div className="rounded-lg border border-dashed p-4 text-center"><strong className="block text-sm font-medium">Evaluation pending</strong><p className="mt-1 text-sm text-muted-foreground">This step is eligible for Langfuse evaluation. Scores will appear when its configured judge or reviewer completes.</p></div>
                  ) : (
                    <div className="rounded-lg border border-dashed p-4 text-center"><strong className="block text-sm font-medium">No evaluation configured for this step</strong><p className="mt-1 text-sm text-muted-foreground">Evaluations currently run on the generated insight and final answer.</p></div>
                  )}
                </div>
                {isFinalAnswerStep && (
                  <aside className="flex flex-col gap-2 rounded-lg border bg-muted/40 p-3">
                    <span className="text-xs text-muted-foreground">Product feedback</span>
                    <h4 className="text-sm font-semibold">Was the final answer useful?</h4>
                    <div className="flex gap-2">
                      <Button variant={helpful === true ? "default" : "outline"} size="sm" aria-pressed={helpful === true} onClick={() => { setHelpful(true); setIssue(""); setFeedbackState("idle"); }}>↑ Yes</Button>
                      <Button variant={helpful === false ? "destructive" : "outline"} size="sm" aria-pressed={helpful === false} onClick={() => { setHelpful(false); setFeedbackState("idle"); }}>↓ No</Button>
                    </div>
                    {helpful === false && (
                      <label className="flex flex-col gap-1.5 text-sm">
                        <span className="font-medium">What needs attention?</span>
                        <select value={issue} onChange={(event) => setIssue(event.target.value)} className="h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50">
                          <option value="">Choose a category</option>
                          <option value="wrong_answer">Wrong answer</option>
                          <option value="missing_context">Missing context</option>
                          <option value="bad_sql">Incorrect SQL or evidence</option>
                          <option value="unclear">Unclear explanation</option>
                          <option value="other">Other</option>
                        </select>
                      </label>
                    )}
                    <label className="flex flex-col gap-1.5 text-sm">
                      <span className="flex items-center justify-between font-medium">Comment <small className="font-normal text-muted-foreground">{comment.length}/500</small></span>
                      <Textarea maxLength={500} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add evidence or context for the reviewer…" />
                    </label>
                    <Button size="sm" onClick={() => void submitFeedback()} disabled={!tracing?.enabled || syncState !== "synced" || helpful === null || feedbackState === "saving"}>{feedbackState === "saving" ? "Saving…" : "Save feedback"}</Button>
                    {feedbackMessage && <p className={cn("text-xs", feedbackState === "error" ? "text-destructive" : "text-muted-foreground")}>{feedbackMessage}</p>}
                    {!tracing?.enabled && <p className="text-xs text-muted-foreground">Connect Langfuse to enable feedback.</p>}
                  </aside>
                )}
              </div>
            )}

            {tab === "metadata" && (observation ? (
              <div className="flex flex-col gap-3">
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
                  {([
                    ["Observation ID", <code key="id" className="font-mono text-xs">{observation.id}</code>],
                    ["Observation", observation.name ?? "—"],
                    ["Type", observation.type?.toLowerCase() ?? "—"],
                    ["Status", observation.level?.toLowerCase() ?? "default"],
                    ["Model", observation.model ?? "—"],
                    ["Environment", observation.environment ?? "default"],
                    ["Version", observation.version ?? "—"],
                    ["Release", observation.release ?? "—"],
                    ["Latency", observation.latency ? `${observation.latency.toFixed(2)}s` : "—"],
                    ["Cost", observation.cost ? `$${observation.cost.toFixed(5)}` : "—"],
                  ] as const).map(([dt, dd], index) => (
                    <div key={index} className="flex flex-col"><dt className="text-xs text-muted-foreground">{dt}</dt><dd className="font-medium">{dd}</dd></div>
                  ))}
                </dl>
                <div><span className="text-xs font-medium text-muted-foreground">Usage</span><pre className="mt-1.5 max-h-60 overflow-auto rounded-md bg-muted p-2.5 font-mono text-xs">{JSON.stringify(observation.usage ?? {}, null, 2)}</pre></div>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed p-4 text-center"><strong className="block text-sm font-medium">Remote metadata is not available</strong><p className="mt-1 text-sm text-muted-foreground">The local execution path remains available while this observation syncs to Langfuse.</p></div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Shared empty-state used across every view when there's nothing to show yet.
function EmptyState({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed py-16 text-center">
      <div className="grid size-12 place-items-center rounded-full bg-muted text-muted-foreground">{icon}</div>
      <strong className="text-base font-semibold">{title}</strong>
      <p className="max-w-md text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

// Scrollable page container shared by every non-chat view.
function PageScroll({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 p-6">{children}</div>
    </div>
  );
}

function PageTitle({ title, subtitle, action }: { title: string; subtitle: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-1 text-sm text-muted-foreground">{subtitle}</p></div>
      {action}
    </div>
  );
}

function SectionTitle({ label, count }: { label: string; count?: number }) {
  return (
    <div className="flex items-center gap-2">
      <h2 className="text-sm font-semibold">{label}</h2>
      {count !== undefined && <Badge variant="secondary" className="h-5 min-w-5 justify-center px-1.5">{count}</Badge>}
    </div>
  );
}


// The Context Agent, when it evolves the graph for a feature, records exactly
// what a dashboard should watch: the completion metric (numerator/denominator
// events + grain), the governed dimensions the metric can be segmented by, and
// the analysis playbooks that resolve each PM question. FeatureDashboard reads
// those learnings straight off the published context so a new feature gets a
// meaningful realtime dashboard with no per-feature configuration.
type FeatureLearnings = {
  metricLabel?: string;
  numerator?: string;
  denominator?: string;
  grain?: string;
  dimensions: string[];
  playbooks: string[];
  questionCount: number;
  eventCount: number;
};

function learningsFor(run: Run): FeatureLearnings {
  const nodes = run.context?.nodes ?? [];
  // The backend's Slug() uses underscores (e.g. "express_checkout") while the
  // frontend slugify() uses hyphens, so derive the feature slug from the actual
  // feature node in the published context rather than guessing it from the name.
  const featureNode = nodes.find((node) => node.type === "feature" && normalize(node.name) === normalize(run.input?.name));
  const slugProp = (featureNode?.properties as Record<string, unknown> | undefined)?.slug;
  const slug = typeof slugProp === "string" && slugProp ? slugProp : (featureNode?.key.replace("feature:", "") ?? slugify(run.input?.name ?? ""));
  const metric = nodes.find((node) => node.type === "metric" && node.key.startsWith(`metric:${slug}`));
  const props = (metric?.properties ?? {}) as Record<string, unknown>;
  let dims = nodes
    .filter((node) => node.type === "dimension" && node.key.startsWith(`dimension:${slug}:`))
    .map((node) => String((node.properties as Record<string, unknown> | undefined)?.field ?? node.key.split(":").at(-1)))
    .filter(Boolean);
  // Some context versions record the metric's segmentable dimensions inline on
  // the metric node rather than as standalone dimension nodes — fall back to that.
  if (dims.length === 0 && Array.isArray(props.dimensions)) {
    dims = (props.dimensions as unknown[]).map(String).filter(Boolean);
  }
  const playbooks = [...new Set((run.analytics_bundle?.playbooks ?? []).map((p) => p.replace(/^playbook:/, "").replace(/:v\d+$/, "").replaceAll("-", " ")))];
  return {
    metricLabel: metric?.name,
    numerator: typeof props.numerator_event === "string" ? props.numerator_event : undefined,
    denominator: typeof props.denominator_event === "string" ? props.denominator_event : undefined,
    grain: typeof props.grain === "string" ? props.grain : undefined,
    dimensions: dims,
    playbooks,
    questionCount: nodes.filter((node) => node.type === "business_question" && node.key.startsWith(`question:${slug}:`)).length,
    eventCount: Object.keys(run.profile?.event_counts ?? {}).length,
  };
}

function FeatureDashboard({ run, lastRefreshed, refreshing, onManualRefresh }: { run: Run; lastRefreshed: number | null; refreshing: boolean; onManualRefresh: () => void }) {
  const bundle = run.analytics_bundle;
  const learnings = useMemo(() => learningsFor(run), [run]);
  if (!bundle) {
    return <EmptyState icon={<Sparkles className="size-6" />} title="Dashboard is being assembled" body="Once the Analytics Agent finishes querying the published context, this feature's realtime dashboard appears here automatically." />;
  }
  const kpis = releaseDecisionKPIs(bundle);
  const topInsight = bundle.insights?.[0];
  const statusLabel = bundle.status === "ready" ? "Live metrics" : bundle.status === "partial" ? "Partial data" : bundle.status === "simulation" ? "Simulated" : "No data";
  const statusDot = bundle.status === "ready" ? "bg-emerald-500" : bundle.status === "partial" ? "bg-amber-500" : bundle.status === "simulation" ? "bg-violet-500" : "bg-muted-foreground";
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="text-xs text-muted-foreground">{run.input?.name} · context v{bundle.context_version} · {bundle.schema_version}</span>
          <h2 className="text-lg font-semibold">{learnings.metricLabel ?? `${run.input?.name} performance`}</h2>
          {learnings.numerator && learnings.denominator && <p className="mt-0.5 text-sm text-muted-foreground">Auto-derived by the Context Agent: <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">{learnings.numerator.replaceAll("_", " ")}</code> over <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">{learnings.denominator.replaceAll("_", " ")}</code>{learnings.grain ? ` per ${learnings.grain}` : ""}.</p>}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="gap-1.5"><span className={cn("size-1.5 rounded-full", statusDot)} />{statusLabel}</Badge>
          <Button variant="outline" size="sm" onClick={onManualRefresh} disabled={refreshing}><RefreshCw className={cn("size-3.5", refreshing && "animate-spin")} />{refreshing ? "Refreshing…" : "Refresh"}</Button>
          <small className="text-xs text-muted-foreground">{lastRefreshed ? `updated ${formatTime(new Date(lastRefreshed).toISOString())}` : bundle.generated_at ? `generated ${formatTime(bundle.generated_at)}` : "live"}</small>
        </div>
      </div>

      {kpis.length > 0 && <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{kpis.map((kpi) => <Stat key={kpi.key} label={kpi.label} value={kpi.formatted_value} hint={`${Math.round(kpi.confidence * 100)}% confidence${kpi.sample_size ? ` · n=${Math.round(kpi.sample_size).toLocaleString()}` : ""}`} />)}</div>}

      <Card>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div><span className="text-xs font-medium text-muted-foreground">Segmentable by</span><div className="mt-1.5 flex flex-wrap gap-1">{learnings.dimensions.length ? learnings.dimensions.map((dim) => <Badge key={dim} variant="secondary">{dim.replaceAll("_", " ")}</Badge>) : <em className="text-sm text-muted-foreground">No governed dimensions</em>}</div></div>
          <div><span className="text-xs font-medium text-muted-foreground">Analysis playbooks</span><div className="mt-1.5 flex flex-wrap gap-1">{learnings.playbooks.length ? learnings.playbooks.map((p) => <Badge key={p} variant="outline">{p}</Badge>) : <em className="text-sm text-muted-foreground">—</em>}</div></div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div><strong className="block text-lg font-semibold tabular-nums">{learnings.eventCount}</strong><span className="text-xs text-muted-foreground">events</span></div>
            <div><strong className="block text-lg font-semibold tabular-nums">{learnings.questionCount}</strong><span className="text-xs text-muted-foreground">questions</span></div>
            <div><strong className="block text-lg font-semibold tabular-nums">{run.profile?.rows?.toLocaleString() ?? "—"}</strong><span className="text-xs text-muted-foreground">rows</span></div>
          </div>
        </CardContent>
      </Card>

      {bundle.charts.length > 0 && <div className="grid gap-3 lg:grid-cols-2">{bundle.charts.map((chart) => <Chart key={chart.key} chart={chart} />)}</div>}

      {topInsight && (
        <Card>
          <CardContent className="flex flex-col gap-2">
            <div className="flex items-center justify-between"><span className="text-xs font-medium text-muted-foreground">Lead recommendation</span><Badge variant="secondary">{Math.round(topInsight.confidence * 100)}%</Badge></div>
            <h3 className="text-base font-semibold">{topInsight.headline}</h3>
            <p className="text-sm text-muted-foreground">{topInsight.summary}</p>
            {topInsight.why && <div className="flex gap-2.5 rounded-lg border bg-muted/40 p-3"><ArrowUpRight className="size-4 shrink-0 text-muted-foreground" /><span><strong className="block text-sm font-medium">Why it matters</strong><p className="mt-0.5 text-sm text-muted-foreground">{topInsight.why}</p></span></div>}
            <div className="rounded-lg border bg-muted/40 p-3 text-sm"><strong className="mr-1.5 font-medium">Recommended next step</strong><span className="text-muted-foreground">{topInsight.recommended_action}</span></div>
          </CardContent>
        </Card>
      )}

      {(bundle.limitations?.length ?? 0) > 0 && <p className="rounded-lg border border-dashed bg-muted/30 p-3 text-sm text-muted-foreground"><strong className="mr-1.5 font-medium text-foreground">Evidence boundary</strong>{bundle.limitations?.[0]}</p>}
    </div>
  );
}


export default function ProductWorkspace() {
  const [view, setView] = useState<View>("ask");
  const [connected, setConnected] = useState<boolean | null>(null);
  const [analyticsRuntime, setAnalyticsRuntime] = useState<RuntimeStatus | null>(null);
  const [tracingRuntime, setTracingRuntime] = useState<RuntimeStatus | null>(null);
  const [contextVersion, setContextVersion] = useState(0);
  const [latestContext, setLatestContext] = useState<Run["context"] | null>(null);
  const [catalog, setCatalog] = useState<DataCatalog | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [selection, setSelection] = useState<FeatureID>("express");
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [approvedRunIds, setApprovedRunIds] = useState<Set<string>>(() => new Set());
  const [busyChatId, setBusyChatId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const role = "product_manager";
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [chatsHydrated, setChatsHydrated] = useState(false);
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [dashboardRunId, setDashboardRunId] = useState<string | null>(null);
  const [dashboardRefreshedAt, setDashboardRefreshedAt] = useState<number | null>(null);
  const [dashboardRefreshing, setDashboardRefreshing] = useState(false);
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [powerChatOpen, setPowerChatOpen] = useState(false);
  const [resetConfirmation, setResetConfirmation] = useState("");
  const [intakeName, setIntakeName] = useState("New product feature");
  const [intakeSlug, setIntakeSlug] = useState("new-product-feature");
  const [schemaVersion, setSchemaVersion] = useState(1);
  const [specFile, setSpecFile] = useState<UploadFile | null>(null);
  const [eventFile, setEventFile] = useState<UploadFile | null>(null);
  const [preflight, setPreflight] = useState<EventPreflight | null>(null);
  const [intakeError, setIntakeError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const approvalsInFlight = useRef<Set<string>>(new Set());

  const activeChat = chats.find((chat) => chat.id === activeChatId) ?? chats[0] ?? null;
  const conversation = useMemo(() => activeChat?.turns ?? [], [activeChat]);
  const chatBusy = busyChatId !== null;
  const activeChatBusy = busyChatId !== null && busyChatId === activeChat?.id;
  const pendingRuns = useMemo(() => runs.filter((item) => item.stage === "awaiting_approval" && !approvedRunIds.has(item.id)), [approvedRunIds, runs]);
  const publishedRuns = useMemo(() => runs.filter((item) => item.stage === "completed" && item.context), [runs]);
  const dashboardRuns = useMemo(() => publishedRuns.filter((item) => item.analytics_bundle), [publishedRuns]);
  const dashboardRun = useMemo(() => dashboardRuns.find((item) => item.id === dashboardRunId) ?? dashboardRuns[0] ?? null, [dashboardRuns, dashboardRunId]);
  const customRuns = useMemo(() => runs.filter((item) => !knownFeatureNames.has(normalize(item.input?.name))), [runs]);
  const selectedPackage = featurePackages.find((item) => item.id === selection);
  const selectedCustomRun = customRuns.find((item) => customFeatureID(item) === selection);
  const selectedRun = selectedPackage ? runs.find((item) => normalize(item.input?.name) === normalize(selectedPackage.name)) : selectedCustomRun;
  const selectedCustomIndex = selectedCustomRun ? customRuns.findIndex((item) => item.id === selectedCustomRun.id) : -1;
  const selectedReleaseOrder = selectedPackage?.order ?? (selectedCustomIndex >= 0 ? String(featurePackages.length + selectedCustomIndex + 1).padStart(2, "0") : String(featurePackages.length + customRuns.length + 1).padStart(2, "0"));
  const selectedFeatureName = selectedRun?.input?.name ?? selectedPackage?.name ?? (selection === "unseen" ? intakeName : "Feature release");
  const activeInsight = [...conversation].reverse().find((turn) => turn.response)?.response?.insight ?? run?.insight;
  const sourceTables = catalog?.tables?.filter((table) => table.category === "source") ?? [];
  const agentTables = catalog?.tables?.filter((table) => table.category === "agent_created") ?? [];
  const starterPrompts = useMemo(() => starterPromptsFromContext(latestContext), [latestContext]);
  const nodeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const node of latestContext?.nodes ?? []) counts[node.type] = (counts[node.type] ?? 0) + 1;
    return counts;
  }, [latestContext]);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/health`).then(async (response) => ({ ok: response.ok, body: response.ok ? await response.json() : {} })),
      fetch(`${API}/api/context/latest`).then((response) => response.json()),
      fetch(`${API}/api/runs`).then((response) => response.json()),
      fetch(`${API}/api/catalog`).then((response) => response.ok ? response.json() : null),
    ]).then(([health, context, recent, liveCatalog]) => {
      const nextRuns: Run[] = recent.runs ?? [];
      setConnected(health.ok);
      setAnalyticsRuntime(health.body.analytics_agent ?? null);
      setTracingRuntime(health.body.tracing ?? null);
      setContextVersion(context.version ?? 0);
      setLatestContext(context);
      setCatalog(liveCatalog);
      setRuns(nextRuns);
      const preferred = nextRuns.find((item) => normalize(item.input?.name) === "express checkout") ?? nextRuns.find((item) => item.stage === "completed") ?? nextRuns[0];
      if (preferred) setRun(preferred);
    }).catch(() => setConnected(false));
  }, []);

  useEffect(() => {
    const stored = loadStoredChats();
    const initial = stored.length ? stored : [createChat()];
    setChats(initial);
    setActiveChatId(initial[0].id);
    setChatsHydrated(true);
  }, []);

  useEffect(() => {
    if (!chatsHydrated) return;
    try { window.localStorage.setItem(chatStorageKey, JSON.stringify(chats)); } catch { /* storage unavailable or full */ }
  }, [chats, chatsHydrated]);

  useEffect(() => {
    if (!run?.id) return;
    const runID = run.id;
    let disposed = false;
    let refreshTimer: ReturnType<typeof setTimeout> | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    const source = new EventSource(`${API}/api/runs/${runID}/events`);

    async function refreshRun() {
      try {
        const response = await fetch(`${API}/api/runs/${runID}`, { cache: "no-store" });
        if (!response.ok || disposed) return;
        const next = await response.json() as Run;
        if (disposed) return;
        setRun((current) => current?.id === next.id ? preferNewerRun(current, next) : current);
        setRuns((current) => {
          const existing = current.find((item) => item.id === next.id);
          const newest = preferNewerRun(existing, next);
          return [newest, ...current.filter((item) => item.id !== next.id)];
        });
        if (next.context) {
          const publishedContext = next.context;
          setContextVersion((current) => Math.max(current, publishedContext.version));
          setLatestContext((current) => !current || publishedContext.version >= current.version ? publishedContext : current);
        }
        if (["completed", "failed"].includes(next.stage)) {
          source.close();
          if (pollTimer) clearInterval(pollTimer);
        }
      } catch { /* the polling fallback will retry without discarding the last good snapshot */ }
    }

    function scheduleRefresh() {
      if (refreshTimer) clearTimeout(refreshTimer);
      refreshTimer = setTimeout(() => void refreshRun(), 100);
    }

    source.addEventListener("stage", (raw) => {
      const event = JSON.parse((raw as MessageEvent).data) as RunEvent;
      setEvents((current) => current.some((item) => item.stage === event.stage && item.timestamp === event.timestamp) ? current : [...current, event]);
      scheduleRefresh();
    });
    source.onerror = () => void refreshRun();
    pollTimer = setInterval(() => void refreshRun(), 3_000);
    void refreshRun();
    return () => {
      disposed = true;
      source.close();
      if (refreshTimer) clearTimeout(refreshTimer);
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [run?.id]);

  // Reconcile the complete control-plane snapshot while the Inbox is open.
  // This keeps approvals and recommendations current even if an SSE connection
  // is interrupted by a deploy, laptop sleep, proxy timeout, or tab suspension.
  useEffect(() => {
    if (view !== "decisions") return;
    let disposed = false;
    let refreshing = false;
    async function refreshDecisionInbox() {
      if (refreshing) return;
      refreshing = true;
      try {
        const [runsResponse, contextResponse] = await Promise.all([
          fetch(`${API}/api/runs`, { cache: "no-store" }),
          fetch(`${API}/api/context/latest`, { cache: "no-store" }),
        ]);
        if (disposed || !runsResponse.ok || !contextResponse.ok) return;
        const recent = await runsResponse.json() as { runs?: Run[] };
        const context = await contextResponse.json() as NonNullable<Run["context"]>;
        if (disposed) return;
        const nextRuns = recent.runs ?? [];
        setRuns((current) => reconcileRuns(current, nextRuns));
        setRun((current) => {
          if (!current) return current;
          const next = nextRuns.find((item) => item.id === current.id);
          return next ? preferNewerRun(current, next) : current;
        });
        setContextVersion(context.version ?? 0);
        setLatestContext(context);
        setConnected(true);
      } catch { /* keep the last good Inbox snapshot and retry */ } finally {
        refreshing = false;
      }
    }
    void refreshDecisionInbox();
    const timer = setInterval(() => void refreshDecisionInbox(), 5_000);
    return () => {
      disposed = true;
      clearInterval(timer);
    };
  }, [view]);

  useEffect(() => {
    if (conversation.length || chatBusy) endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [conversation, chatBusy]);

  // Realtime dashboard: while the dashboards view is open, re-fetch the selected
  // feature's analytics bundle every 20s so KPIs, funnel, and trend stay live.
  useEffect(() => {
    if (view !== "dashboards" || !dashboardRun?.id) return;
    const id = dashboardRun.id;
    const timer = setInterval(() => void refreshDashboard(id), 20_000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, dashboardRun?.id]);

  function updateChatById(id: string, updater: (chat: Chat) => Chat) {
    setChats((current) => current.map((chat) => (chat.id === id ? updater(chat) : chat)));
  }

  function startNewChat(switchToAsk = true) {
    const chat = createChat();
    setChats((current) => [chat, ...current]);
    setActiveChatId(chat.id);
    setRenamingChatId(null);
    if (switchToAsk) {
      setQuestion("");
      setView("ask");
    }
    return chat;
  }

  function selectChat(id: string) {
    setActiveChatId(id);
    setRenamingChatId(null);
  }

  function deleteChat(id: string) {
    const remaining = chats.filter((chat) => chat.id !== id);
    const next = remaining.length ? remaining : [createChat()];
    setChats(next);
    if (renamingChatId === id) setRenamingChatId(null);
    if (!next.some((chat) => chat.id === activeChatId)) setActiveChatId(next[0].id);
  }

  function beginRename(chat: Chat) {
    setRenamingChatId(chat.id);
    setRenameDraft(chat.title);
  }

  function commitRename(id: string) {
    const title = renameDraft.trim();
    if (title) updateChatById(id, (chat) => ({ ...chat, title }));
    setRenamingChatId(null);
  }

  function chooseFeature(id: FeatureID, nextView: View = "releases") {
    setSelection(id);
    const item = featurePackages.find((feature) => feature.id === id);
    const matching = item ? runs.find((candidate) => normalize(candidate.input?.name) === normalize(item.name)) : runs.find((candidate) => customFeatureID(candidate) === id);
    setRun(matching ?? null);
    setEvents([]);
    setView(nextView);
    setError("");
  }

  function askAboutSelectedFeature() {
    if (!selectedRun || selectedRun.stage !== "completed") return;
    startNewChat(false);
    setRun(selectedRun);
    setQuestion(`How is ${selectedFeatureName} performing, and what should I prioritize next?`);
    setView("ask");
    setError("");
  }

  async function launchFeature() {
    if (selection === "unseen") {
      setIntakeOpen(true);
      return;
    }
    if (selectedRun) { setRun(selectedRun); setView("pipeline"); return; }
    if (!selectedPackage) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: selectedPackage.name, schema_version: selectedPackage.schemaVersion, spec_markdown: selectedPackage.spec, use_existing_data: true, role, auto_approve: false }) });
      const payload = await response.json() as Run & { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "Could not start feature analysis");
      setRun(payload);
      setRuns((current) => [payload, ...current.filter((item) => item.id !== payload.id)]);
      setEvents([]);
      setView("pipeline");
      setConnected(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Backend unavailable"); } finally { setBusy(false); }
  }

  async function refreshDashboard(id: string, manual = false) {
    if (manual) setDashboardRefreshing(true);
    try {
      const response = await fetch(`${API}/api/runs/${id}`);
      if (!response.ok) return;
      const next = await response.json() as Run;
      setRuns((current) => current.map((item) => (item.id === next.id ? next : item)));
      if (run?.id === next.id) setRun(next);
      setDashboardRefreshedAt(Date.now());
      setConnected(true);
    } catch { /* keep the last good snapshot; the live badge will show the stale time */ } finally {
      if (manual) setDashboardRefreshing(false);
    }
  }

  async function approveRun(target: Run) {
    if (approvalsInFlight.current.has(target.id) || approvedRunIds.has(target.id)) return;
    approvalsInFlight.current.add(target.id);
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/runs/${target.id}/approve`, { method: "POST" });
      const payload = await response.json() as { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "Approval failed");
      setApprovedRunIds((current) => new Set(current).add(target.id));
      setView("pipeline");
      const latestResponse = await fetch(`${API}/api/runs/${target.id}`, { cache: "no-store" });
      if (latestResponse.ok) {
        const latest = await latestResponse.json() as Run;
        setRun(latest);
        setRuns((current) => [latest, ...current.filter((item) => item.id !== latest.id)]);
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Approval failed"); } finally {
      approvalsInFlight.current.delete(target.id);
      setBusy(false);
    }
  }

  async function ask(prompt?: string) {
    const submitted = (prompt ?? question).trim();
    if (!submitted || chatBusy || publishedRuns.length === 0) return;
    const target = activeChat ?? startNewChat(false);
    const before = target.turns;
    const lastAssistant = [...before].reverse().find((turn) => turn.response);
    updateChatById(target.id, (chat) => ({
      ...chat,
      title: chat.turns.length === 0 ? chatTitleFrom(submitted) : chat.title,
      updatedAt: Date.now(),
      turns: [...chat.turns, { id: `u-${Date.now()}`, role: "user", content: submitted }],
    }));
    setQuestion("");
    setBusyChatId(target.id);
    setError("");
    try {
      const response = await fetch(`${API}/api/conversations`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        role,
        question: submitted,
        active_features: lastAssistant?.response?.feature_scope,
        context_version: contextVersion || undefined,
        history: before.map((turn) => ({ role: turn.role, content: turn.response?.insight.summary ?? turn.content, feature_scope: turn.response?.feature_scope ?? turn.featureScope })),
      }) });
      const payload = await response.json() as ConversationResponse & { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "Question failed");
      updateChatById(target.id, (chat) => ({
        ...chat,
        updatedAt: Date.now(),
        turns: [...chat.turns, { id: `a-${Date.now()}`, role: "assistant", content: payload.insight.summary, featureScope: payload.feature_scope, response: payload }],
      }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Question failed"); } finally { setBusyChatId(null); }
  }

  async function loadSpec(file?: File) {
    setIntakeError("");
    if (!file) return setSpecFile(null);
    if (file.size > maxIntakeBytes) return setIntakeError("Specification exceeds the 15 MB limit");
    const text = await file.text();
    if (!text.trim()) return setIntakeError("Specification file is empty");
    setSpecFile({ name: file.name, size: file.size, text });
  }

  async function loadEvents(file?: File) {
    setIntakeError("");
    setPreflight(null);
    if (!file) return setEventFile(null);
    if (file.size > maxIntakeBytes) return setIntakeError("Event file exceeds the 15 MB limit");
    const text = await file.text();
    try { setPreflight(inspectNDJSON(text)); setEventFile({ name: file.name, size: file.size, text }); } catch (cause) { setEventFile(null); setIntakeError(cause instanceof Error ? cause.message : "Event package is invalid"); }
  }

  async function submitUnseen() {
    if (!intakeName.trim() || !specFile || !eventFile || !preflight) return setIntakeError("Add a feature name, specification, and valid NDJSON events");
    setBusy(true);
    setIntakeError("");
    try {
      const response = await fetch(`${API}/api/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: intakeName.trim(), slug: intakeSlug || slugify(intakeName), schema_version: schemaVersion, spec_markdown: specFile.text, events_ndjson: eventFile.text, role, auto_approve: false }) });
      const payload = await response.json() as Run & { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "Could not submit the feature");
      setSelection(customFeatureID(payload));
      setRun(payload);
      setRuns((current) => [payload, ...current.filter((item) => item.id !== payload.id)]);
      setEvents([]);
      startNewChat(false);
      setIntakeOpen(false);
      setView("pipeline");
    } catch (cause) { setIntakeError(cause instanceof Error ? cause.message : "Backend unavailable"); } finally { setBusy(false); }
  }

  async function resetBaseline() {
    if (resetConfirmation !== "RESET") return;
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/admin/reset`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmation: "RESET_CONTEXT" }) });
      const payload = await response.json() as { error?: string; context_version?: number; context?: Run["context"] };
      if (!response.ok) throw new Error(payload.error ?? "Reset failed");
      const freshChat = createChat();
      setRuns([]); setRun(null); setEvents([]); setChats([freshChat]); setActiveChatId(freshChat.id); setRenamingChatId(null); setSelection("express"); setContextVersion(payload.context_version ?? 0); setLatestContext(payload.context ?? null); setResetOpen(false); setResetConfirmation(""); setView("ask");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Reset failed"); setResetOpen(false); } finally { setBusy(false); }
  }

  function openPowerChat() {
    const url = powerChatURL();
    if (url) window.open(url, "_blank", "noopener,noreferrer");
    else setPowerChatOpen(true);
  }

  const featureStatus = (name: string) => runs.find((item) => normalize(item.input?.name) === normalize(name));
  const rank = run ? Math.max(0, stageOrder.indexOf(run.stage)) : 0;

  const navItems: { id: View; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: "ask", label: "Ask FeatureLens", icon: <MessageCircle className="size-4" /> },
    { id: "decisions", label: "Decision inbox", icon: <Inbox className="size-4" />, badge: pendingRuns.length },
    { id: "dashboards", label: "Realtime dashboards", icon: <LayoutGrid className="size-4" />, badge: dashboardRuns.length },
    { id: "releases", label: "Feature releases", icon: <Rows3 className="size-4" /> },
  ];
  const systemItems: { id: View; label: string; icon: React.ReactNode }[] = [
    { id: "pipeline", label: "Pipeline activity", icon: <Activity className="size-4" /> },
    { id: "context", label: "Context & schemas", icon: <CircleDot className="size-4" /> },
    { id: "trace", label: "Trace explorer", icon: <Search className="size-4" /> },
  ];
  const NavButton = ({ id, label, icon, badge }: { id: View; label: string; icon: React.ReactNode; badge?: number }) => (
    <button
      onClick={() => setView(id)}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors",
        view === id ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
      )}
    >
      <span className="shrink-0">{icon}</span>
      <span className="flex-1 text-left">{label}</span>
      {badge ? <Badge variant="secondary" className="h-5 min-w-5 justify-center px-1.5">{badge}</Badge> : null}
    </button>
  );

  return <main className="grid min-h-screen grid-cols-[240px_minmax(0,1fr)] bg-background text-foreground">
    <aside className="sticky top-0 flex h-screen flex-col gap-1 border-r bg-sidebar p-3">
      <div className="flex items-center gap-2.5 px-1.5 py-2">
        <BrandMark />
        <strong className="text-base font-semibold tracking-tight">FeatureLens</strong>
      </div>
      <nav aria-label="Primary navigation" className="flex flex-col gap-0.5">
        {navItems.map((item) => <NavButton key={item.id} {...item} />)}
      </nav>
      <Button variant="outline" size="sm" className="mt-1 justify-start" onClick={() => setIntakeOpen(true)}><Plus className="size-4" /> Add feature</Button>
      <Separator className="my-2" />
      <p className="px-2.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">System</p>
      <nav aria-label="System navigation" className="flex flex-col gap-0.5">
        {systemItems.map((item) => <NavButton key={item.id} {...item} />)}
      </nav>
      <div className="mt-auto flex flex-col gap-2">
        <Button variant="ghost" size="sm" className="justify-start text-muted-foreground" onClick={() => setResetOpen(true)} disabled={busy}><RotateCcw className="size-4" /> Reset baseline</Button>
        <Separator />
        <div className="flex items-center gap-2.5 px-1 py-1">
          <Avatar className="size-8"><AvatarFallback>AM</AvatarFallback></Avatar>
          <div className="min-w-0"><strong className="block text-sm font-medium">Ajay</strong><small className="text-xs text-muted-foreground">Product Manager</small></div>
        </div>
      </div>
    </aside>

    <section className="flex min-h-screen flex-col">
      <div role="status" aria-label="Context snapshot" className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b bg-muted/40 px-6 py-2 text-xs text-muted-foreground">
        <b className="font-normal"><em className="not-italic">context</em> <strong className="font-semibold text-foreground">v{contextVersion}</strong></b>
        <b className="font-normal"><em className="not-italic">nodes</em> <strong className="font-semibold text-foreground">{latestContext?.nodes?.length ?? 0}</strong></b>
        <b className="font-normal"><em className="not-italic">relationships</em> <strong className="font-semibold text-foreground">{latestContext?.edges?.length ?? 0}</strong></b>
        <b className="font-normal"><em className="not-italic">tables</em> <strong className="font-semibold text-foreground">{sourceTables.length}</strong></b>
        <b className={cn("font-normal", (latestContext?.conflicts?.length ?? 0) > 0 && "text-amber-600 dark:text-amber-400")}><em className="not-italic">{(latestContext?.conflicts?.length ?? 0) > 0 ? "⚠ contradictions" : "contradictions"}</em> <strong className="font-semibold">{latestContext?.conflicts?.length ?? 0}</strong></b>
        <b className="ml-auto flex items-center gap-1.5 font-normal"><span className={cn("size-1.5 rounded-full", connected ? "bg-emerald-500" : "bg-muted-foreground")} />{connected ? "live" : "offline"}</b>
      </div>
      <header className="flex items-center justify-between gap-3 border-b px-6 py-3">
        <Button variant="ghost" size="sm" className="gap-2"><Boxes className="size-4" /> Atlys Product <ChevronDown className="size-3.5 text-muted-foreground" /></Button>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setView("context")}>Context v{contextVersion}</Button>
          <Button size="sm" onClick={openPowerChat}><CircleDot className="size-3.5" /> Open Power Chat <ExternalLink className="size-3.5" /></Button>
          <Avatar className="size-8"><AvatarFallback>AM</AvatarFallback></Avatar>
        </div>
      </header>
      {error && (
        <div className="flex items-center gap-3 border-b border-destructive/30 bg-destructive/10 px-6 py-2.5 text-sm text-destructive">
          <AlertCircle className="size-4 shrink-0" />
          <p className="flex-1">{error}</p>
          <button onClick={() => setError("")} className="rounded p-1 hover:bg-destructive/10"><X className="size-4" /></button>
        </div>
      )}

      {view === "ask" && <section className="grid min-h-0 flex-1 grid-cols-[260px_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col gap-2 border-r p-3" aria-label="Saved chats">
          <Button variant="outline" size="sm" className="justify-start" onClick={() => startNewChat()}><Plus className="size-4" /> New chat</Button>
          <p className="px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Chats</p>
          <ScrollArea className="min-h-0 flex-1">
            <div className="flex flex-col gap-1 pr-2">
              {chats.map((chat) => <div key={chat.id} className={cn("group flex items-center gap-1 rounded-md pr-1 transition-colors", chat.id === activeChat?.id ? "bg-accent" : "hover:bg-accent/50")}>
                {renamingChatId === chat.id
                  ? <Input autoFocus value={renameDraft} className="h-8" onChange={(event) => setRenameDraft(event.target.value)} onBlur={() => commitRename(chat.id)} onKeyDown={(event) => { if (event.key === "Enter") commitRename(chat.id); if (event.key === "Escape") setRenamingChatId(null); }} aria-label="Rename chat" />
                  : <button className="min-w-0 flex-1 px-2 py-1.5 text-left" onClick={() => selectChat(chat.id)} onDoubleClick={() => beginRename(chat)} title={`${chat.title} — double-click to rename`}><strong className="block truncate text-sm font-medium">{chat.title}</strong><small className="block truncate text-xs text-muted-foreground">{chat.id === busyChatId ? "Thinking…" : chat.turns.length === 0 ? "No messages yet" : `${chat.turns.length} message${chat.turns.length === 1 ? "" : "s"} · ${formatTime(new Date(chat.updatedAt).toISOString())}`}</small></button>}
                <button className="shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-background hover:text-foreground group-hover:opacity-100" aria-label={`Delete chat ${chat.title}`} onClick={() => deleteChat(chat.id)}><X className="size-3.5" /></button>
              </div>)}
            </div>
          </ScrollArea>
        </aside>
        <div className="flex min-h-0 flex-1 flex-col">
          <ScrollArea className="min-h-0 flex-1">
            <div className="mx-auto flex max-w-4xl flex-col gap-5 p-6" aria-live="polite">
              {conversation.length === 0 ? (
                <div className="flex flex-col items-center gap-4 py-16 text-center">
                  <BrandMark />
                  <div><h2 className="text-2xl font-semibold">How can I help?</h2><p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">Ask across every published feature. FeatureLens resolves the latest business context, runs governed ClickHouse queries, and shows the evidence behind every answer.</p></div>
                  <div className="mt-2 grid w-full max-w-2xl gap-2 sm:grid-cols-2">
                    {starterPrompts.map((prompt) => (
                      <button key={prompt} onClick={() => void ask(prompt)} disabled={!publishedRuns.length || chatBusy} className="group flex items-center gap-2 rounded-lg border p-3 text-left text-sm transition-colors hover:bg-accent disabled:opacity-50">
                        <span className="text-muted-foreground">›</span>
                        <em className="flex-1 not-italic">{prompt}</em>
                        <span className="text-xs text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">run ↵</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : conversation.map((turn) => turn.role === "user"
                ? <div className="flex items-start justify-end gap-2.5" key={turn.id}>
                    <p className="max-w-xl rounded-2xl rounded-tr-sm bg-primary px-3.5 py-2 text-sm text-primary-foreground">{turn.content}</p>
                    <Avatar className="size-7"><AvatarFallback className="text-xs">AM</AvatarFallback></Avatar>
                  </div>
                : turn.response ? <AnswerCard key={turn.id} response={turn.response} onFollowUp={(prompt) => void ask(prompt)} onTrace={() => setView("trace")} /> : null)}
              {activeChatBusy && <div className="flex items-center gap-2.5 text-sm text-muted-foreground"><BrandMark compact /><span className="flex gap-1">{[0, 1, 2].map((i) => <span key={i} className="size-1.5 animate-bounce rounded-full bg-muted-foreground" style={{ animationDelay: `${i * 0.15}s` }} />)}</span><span>Resolving context and querying ClickHouse…</span></div>}
              <div ref={endRef} />
            </div>
          </ScrollArea>
          <form className="border-t p-4" onSubmit={(event) => { event.preventDefault(); void ask(); }}>
            <div className="mx-auto max-w-4xl rounded-xl border bg-card p-2 shadow-sm focus-within:ring-2 focus-within:ring-ring/50">
              <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void ask(); } }} placeholder="Ask about a feature, segment, trend, or opportunity…" rows={2} aria-label="Ask FeatureLens" className="min-h-0 border-0 bg-transparent p-1.5 shadow-none focus-visible:ring-0" />
              <div className="flex items-center justify-between px-1.5 pt-1">
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground"><span className={cn("size-1.5 rounded-full", connected ? "bg-emerald-500" : "bg-muted-foreground")} /> Governed data</span>
                <Button type="submit" size="icon" className="size-8" aria-label="Send question" disabled={chatBusy || !question.trim() || !publishedRuns.length}><ArrowUp className="size-4" /></Button>
              </div>
            </div>
          </form>
        </div>
      </section>}

      {view === "decisions" && <PageScroll>
        <PageTitle title="Decision inbox" subtitle="Approvals and evidence-backed recommendations that need your attention." />
        {pendingRuns.length > 0 && <section className="flex flex-col gap-3">
          <SectionTitle label="Needs approval" count={pendingRuns.length} />
          <div className="grid gap-3 md:grid-cols-2">{pendingRuns.map((item) => (
            <Card key={item.id}><CardContent className="flex flex-col gap-3">
              <div><Badge variant="outline">Schema approval</Badge><h3 className="mt-2 text-base font-semibold">{item.input?.name}</h3><p className="mt-1 text-sm text-muted-foreground">The Instrumentation Agent has verified the proposed ClickHouse contract. Context publication is waiting for your decision.</p></div>
              <dl className="grid grid-cols-3 gap-2 rounded-lg border bg-muted/40 p-3 text-center">
                <div><dt className="text-xs text-muted-foreground">Table</dt><dd className="text-sm font-medium">{item.schema?.table ?? "Preparing"}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Rows</dt><dd className="text-sm font-medium tabular-nums">{item.profile?.rows?.toLocaleString() ?? "—"}</dd></div>
                <div><dt className="text-xs text-muted-foreground">Checks</dt><dd className="text-sm font-medium tabular-nums">{item.validation?.checks.filter((check) => check.passed).length ?? 0}/{item.validation?.checks.length ?? 0}</dd></div>
              </dl>
              <Button onClick={() => void approveRun(item)} disabled={busy}>Review &amp; approve →</Button>
            </CardContent></Card>
          ))}</div>
        </section>}
        <section className="flex flex-col gap-3">
          <SectionTitle label="Latest recommendations" count={publishedRuns.length} />
          <div className="grid gap-3 md:grid-cols-2">
            {publishedRuns.flatMap((item) => (item.analytics_bundle?.insights ?? []).slice(0, 1).map((insight) => (
              <Card key={`${item.id}-${insight.rank}`}><CardContent className="flex flex-col gap-2">
                <Badge variant="secondary" className="w-fit">{item.input?.name}</Badge>
                <h3 className="text-base font-semibold">{insight.headline}</h3>
                <p className="text-sm text-muted-foreground">{insight.summary}</p>
                <div className="rounded-lg border bg-muted/40 p-3 text-sm"><strong className="mr-1.5 font-medium">Next action</strong><span className="text-muted-foreground">{insight.recommended_action}</span></div>
                <div className="flex items-center justify-between pt-1"><span className="text-xs text-muted-foreground">{Math.round(insight.confidence * 100)}% confidence</span><Button variant="ghost" size="sm" onClick={() => { setRun(item); setSelection(featureSelectionForRun(item)); setView("releases"); }}>Open feature →</Button></div>
              </CardContent></Card>
            )))}
            {publishedRuns.length === 0 && <div className="md:col-span-2"><EmptyState icon={<Sparkles className="size-6" />} title="No recommendations yet" body="Publish the first feature context to create a decision-ready analytics bundle." /></div>}
          </div>
        </section>
      </PageScroll>}

      {view === "dashboards" && <PageScroll>
        <PageTitle title="Realtime dashboards" subtitle="Every published feature gets a live dashboard, generated from what the Context Agent learned — no per-feature setup." action={<Badge variant="outline" className="gap-1.5"><span className="size-1.5 animate-pulse rounded-full bg-emerald-500" />Auto-refreshing every 20s</Badge>} />
        {dashboardRuns.length === 0
          ? <EmptyState icon={<LayoutGrid className="size-6" />} title="No feature dashboards yet" body="Publish a feature's context and the Analytics Agent will assemble its realtime dashboard here automatically." />
          : <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
              <aside className="flex flex-col gap-1.5">{dashboardRuns.map((item, index) => (
                <button key={item.id} onClick={() => { setDashboardRunId(item.id); setDashboardRefreshedAt(Date.now()); }} className={cn("flex items-center gap-3 rounded-lg border p-2.5 text-left transition-colors", dashboardRun?.id === item.id ? "border-primary bg-accent" : "hover:bg-accent")}>
                  <span className="font-mono text-xs text-muted-foreground">{String(index + 1).padStart(2, "0")}</span>
                  <div className="min-w-0 flex-1"><strong className="block truncate text-sm font-medium">{item.input?.name}</strong><small className="text-xs text-muted-foreground capitalize">{item.analytics_bundle?.status === "ready" ? "Live" : item.analytics_bundle?.status ?? "published"}</small></div>
                  <span className="size-2 rounded-full bg-emerald-500" />
                </button>
              ))}</aside>
              <Card><CardContent>{dashboardRun ? <FeatureDashboard run={dashboardRun} lastRefreshed={dashboardRefreshedAt} refreshing={dashboardRefreshing} onManualRefresh={() => dashboardRun && void refreshDashboard(dashboardRun.id, true)} /> : null}</CardContent></Card>
            </div>}
      </PageScroll>}

      {view === "releases" && <PageScroll>
        <PageTitle title="Feature releases" subtitle="Explore the product intelligence available for each release." action={<Button onClick={() => setIntakeOpen(true)}><Plus className="size-4" /> Add feature</Button>} />
        <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
          <aside className="flex flex-col gap-1.5">
            {featurePackages.map((feature) => { const item = featureStatus(feature.name); return (
              <button key={feature.id} onClick={() => chooseFeature(feature.id)} className={cn("flex items-center gap-3 rounded-lg border p-2.5 text-left transition-colors", selection === feature.id ? "border-primary bg-accent" : "hover:bg-accent")}>
                <span className="font-mono text-xs text-muted-foreground">{feature.order}</span>
                <div className="min-w-0 flex-1"><strong className="block truncate text-sm font-medium">{feature.name}</strong><small className="text-xs text-muted-foreground capitalize">{item?.stage === "completed" ? "Published" : item ? item.stage.replaceAll("_", " ") : "Not analyzed"}</small></div>
                <span className={cn("size-2 rounded-full", item?.stage === "completed" ? "bg-emerald-500" : "bg-muted")} />
              </button>
            ); })}
            {customRuns.map((item, index) => { const id = customFeatureID(item); return (
              <button key={item.id} onClick={() => chooseFeature(id)} className={cn("flex items-center gap-3 rounded-lg border p-2.5 text-left transition-colors", selection === id ? "border-primary bg-accent" : "hover:bg-accent")}>
                <span className="font-mono text-xs text-muted-foreground">{String(featurePackages.length + index + 1).padStart(2, "0")}</span>
                <div className="min-w-0 flex-1"><strong className="block truncate text-sm font-medium">{item.input?.name ?? "Custom release"}</strong><small className="text-xs text-muted-foreground capitalize">{item.stage === "completed" ? "Published" : item.stage.replaceAll("_", " ")}</small></div>
                <span className={cn("size-2 rounded-full", item.stage === "completed" ? "bg-emerald-500" : "bg-muted")} />
              </button>
            ); })}
            <button onClick={() => chooseFeature("unseen")} className={cn("flex items-center gap-3 rounded-lg border border-dashed p-2.5 text-left transition-colors", selection === "unseen" ? "border-primary bg-accent" : "hover:bg-accent")}>
              <span className="font-mono text-xs text-muted-foreground">{String(featurePackages.length + customRuns.length + 1).padStart(2, "0")}</span>
              <div className="min-w-0 flex-1"><strong className="block truncate text-sm font-medium">Add another release</strong><small className="text-xs text-muted-foreground">Upload spec and events</small></div>
              <span className="size-2 rounded-full bg-muted" />
            </button>
          </aside>
          <Card><CardContent className="flex flex-col gap-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><span className="text-xs text-muted-foreground capitalize">{selectedReleaseOrder} · {selectedRun?.stage === "completed" ? "Published" : selectedRun ? selectedRun.stage.replaceAll("_", " ") : "Ready to analyze"}</span><h2 className="text-lg font-semibold">{selectedFeatureName}</h2><p className="mt-1 max-w-2xl text-sm text-muted-foreground">{selectedPackage?.description ?? "A new product release that will evolve instrumentation, context, and analytics without feature-specific code."}</p></div>
              <Button onClick={() => selectedRun?.stage === "completed" ? askAboutSelectedFeature() : void launchFeature()} disabled={busy}>{selectedRun?.stage === "completed" ? "Ask about this release" : selectedRun ? "View pipeline" : selection === "unseen" ? "Add release" : "Analyze release"} →</Button>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Event rows" value={selectedRun?.profile?.rows?.toLocaleString() ?? selectedPackage?.rows ?? "Unknown"} />
              <Stat label="Decision focus" value={<span className="text-sm">{selectedPackage?.outcome ?? "Adaptive measurement"}</span>} />
              <Stat label="Context" value={<span className="text-sm">{selectedRun?.context ? `v${selectedRun.context.version}` : "Not published"}</span>} />
              <Stat label="Schema" value={<span className="text-sm">{selectedRun?.schema ? `v${selectedRun.schema.version}` : `Proposed v${selectedPackage?.schemaVersion ?? schemaVersion}`}</span>} />
            </div>
            {selectedRun?.analytics_bundle ? (
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{releaseDecisionKPIs(selectedRun.analytics_bundle).map((kpi) => <Stat key={kpi.key} label={kpi.label} value={kpi.formatted_value} hint={kpi.evidence_label} />)}</div>
                <div className="grid gap-3 lg:grid-cols-2">{selectedRun.analytics_bundle.charts.slice(0, 2).map((chart) => <Chart key={chart.key} chart={chart} />)}</div>
              </div>
            ) : <EmptyState icon={<Sparkles className="size-6" />} title="Feature intelligence is not published yet" body="Start the release to profile events, review the schema, publish its context, and generate actionable insights." />}
          </CardContent></Card>
        </div>
      </PageScroll>}

      {view === "pipeline" && <PageScroll>
        <PageTitle title="Pipeline activity" subtitle="The governed agent workflow behind the selected feature release." action={run ? <Badge variant="outline" className="capitalize">{run.stage.replaceAll("_", " ")}</Badge> : undefined} />
        {!run ? <EmptyState icon={<Activity className="size-6" />} title="No feature run selected" body="Choose a release to inspect its instrumentation, context, and analytics activity." /> : <>
          <div className="grid items-stretch gap-3 md:grid-cols-3">
            {([
              { key: "I", agent: "Instrumentation Agent", role: "Schema and event contract", detail: run.schema ? `${run.schema.database}.${run.schema.table}` : "Waiting to profile the release", done: rank >= 4, active: rank >= 1, status: rank >= 4 ? "✓" : rank >= 1 ? "Working" : "Queued" },
              { key: "C", agent: "Context Agent", role: "Business meaning and ontology", detail: run.context?.summary ?? "Publishes only after schema approval", done: rank >= 5, active: rank >= 5, status: rank >= 5 ? "✓" : "Queued" },
              { key: "A", agent: "Analytics Agent", role: "Evidence and recommendations", detail: run.insight?.headline ?? "Queries the latest published context", done: rank >= 6, active: rank >= 6, status: rank >= 6 ? "✓" : "Queued" },
            ]).map((stage) => (
              <Card key={stage.key} className={cn(stage.done && "border-primary/40")}><CardContent className="flex items-start gap-3">
                <span className={cn("grid size-8 shrink-0 place-items-center rounded-md font-mono text-sm font-semibold", stage.done ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{stage.key}</span>
                <div className="min-w-0 flex-1"><span className="text-xs text-muted-foreground">{stage.agent}</span><strong className="block text-sm font-medium">{stage.role}</strong><p className="mt-0.5 truncate text-xs text-muted-foreground">{stage.detail}</p></div>
                <Badge variant={stage.done ? "secondary" : "outline"} className="shrink-0">{stage.status}</Badge>
              </CardContent></Card>
            ))}
          </div>
          {run.stage === "awaiting_approval" && !approvedRunIds.has(run.id) && (
            <Card className="border-amber-500/40 bg-amber-500/5"><CardContent className="flex flex-wrap items-center justify-between gap-3">
              <div><Badge variant="outline" className="border-amber-500/50 text-amber-700 dark:text-amber-400">Decision required</Badge><h3 className="mt-2 text-base font-semibold">Approve the ClickHouse contract for {run.input?.name}</h3><p className="mt-1 text-sm text-muted-foreground">Nothing is executed or published until this schema passes your review.</p></div>
              <Button onClick={() => void approveRun(run)} disabled={busy}>Approve &amp; continue →</Button>
            </CardContent></Card>
          )}
          <div className="grid gap-3 lg:grid-cols-2">
            <Card><CardContent className="flex flex-col gap-3">
              <SectionTitle label="Release contract" />
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
                {[["Table", run.schema?.table ?? "Preparing"], ["Rows profiled", run.profile?.rows?.toLocaleString() ?? "—"], ["Event types", Object.keys(run.profile?.event_counts ?? {}).length], ["Validation", run.validation?.passed ? "Passed" : "Pending"], ["Context", run.context ? `v${run.context.version}` : "Pending"], ["Trace", compactID(run.trace_id)]].map(([dt, dd]) => (
                  <div key={String(dt)} className="flex flex-col"><dt className="text-xs text-muted-foreground">{dt}</dt><dd className="font-medium">{dd}</dd></div>
                ))}
              </dl>
              {run.schema?.ddl && <details className="text-sm"><summary className="cursor-pointer text-muted-foreground hover:text-foreground">Inspect proposed DDL</summary><pre className="mt-2 max-h-72 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">{run.schema.ddl}</pre></details>}
            </CardContent></Card>
            <Card><CardContent className="flex flex-col gap-3">
              <SectionTitle label="Activity" count={events.length} />
              <div className="flex flex-col gap-3">{events.length ? [...events].reverse().map((event) => (
                <div key={`${event.stage}-${event.timestamp}`} className="flex gap-3 text-sm">
                  <time className="shrink-0 pt-0.5 font-mono text-xs text-muted-foreground">{formatTime(event.timestamp)}</time>
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
                  <span><strong className="block font-medium capitalize">{event.stage.replaceAll("_", " ")}</strong><p className="text-muted-foreground">{event.message}</p></span>
                </div>
              )) : <p className="text-sm text-muted-foreground capitalize">No new activity. The selected run is {run.stage.replaceAll("_", " ")}.</p>}</div>
            </CardContent></Card>
          </div>
        </>}
      </PageScroll>}

      {view === "context" && <PageScroll>
        <PageTitle title="Context & schemas" subtitle="The living business model that keeps every analytics answer aligned with the latest feature landscape." action={<Badge variant="outline">Context v{contextVersion}</Badge>} />
        <Card><CardContent className="grid gap-4 md:grid-cols-[1fr_auto] md:items-center">
          <div><span className="text-xs text-muted-foreground">Latest published context</span><h2 className="text-lg font-semibold">{latestContext?.summary ?? "Baseline context is ready"}</h2><p className="mt-1 max-w-2xl text-sm text-muted-foreground">Features, entities, metrics, dimensions, relationships, and known issues are versioned together. Analytics can only query tables registered in this contract.</p></div>
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Nodes" value={latestContext?.nodes?.length ?? 0} />
            <Stat label="Relationships" value={latestContext?.edges?.length ?? 0} />
            <Stat label="Source tables" value={sourceTables.length} />
            <Stat label="Agent schemas" value={agentTables.length} />
          </div>
        </CardContent></Card>
        {(latestContext?.nodes?.length ?? 0) > 0 && <ContextGraph nodes={latestContext?.nodes ?? []} edges={latestContext?.edges ?? []} />}
        <div className="grid gap-3 lg:grid-cols-2">
          <Card><CardContent className="flex flex-col gap-3">
            <div className="flex items-center justify-between"><SectionTitle label="Business ontology" /><b className="text-xs font-normal text-muted-foreground">{Object.keys(nodeCounts).length} types</b></div>
            <div className="flex flex-col gap-1.5">{Object.entries(nodeCounts).map(([type, count]) => (
              <div key={type} className="flex items-center gap-3 rounded-md border p-2">
                <i className="grid size-7 shrink-0 place-items-center rounded-md bg-muted text-xs font-semibold not-italic">{type.slice(0, 1).toUpperCase()}</i>
                <span className="min-w-0 flex-1"><strong className="block text-sm font-medium capitalize">{type.replaceAll("_", " ")}</strong><small className="text-xs text-muted-foreground">Published semantic objects</small></span>
                <b className="text-sm font-semibold tabular-nums">{count}</b>
              </div>
            ))}</div>
          </CardContent></Card>
          <Card><CardContent className="flex flex-col gap-3">
            <div className="flex items-center justify-between"><SectionTitle label="ClickHouse source catalog" /><b className="text-xs font-normal text-muted-foreground">{sourceTables.filter((table) => table.context_registered).length}/{sourceTables.length} registered</b></div>
            <div className="flex flex-col gap-1.5">{sourceTables.map((table) => (
              <div key={`${table.database}.${table.name}`} className="flex items-center gap-3 rounded-md border p-2">
                <i className={cn("grid size-7 shrink-0 place-items-center rounded-md text-xs font-semibold not-italic", table.context_registered ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" : "bg-amber-500/15 text-amber-600 dark:text-amber-400")}>{table.context_registered ? "✓" : "!"}</i>
                <span className="min-w-0 flex-1"><strong className="block truncate text-sm font-medium">{table.name}</strong><small className="text-xs text-muted-foreground">{table.database} · {table.engine}</small></span>
                <b className="text-sm font-medium tabular-nums">{table.rows.toLocaleString()}</b>
              </div>
            ))}</div>
          </CardContent></Card>
        </div>
        {(latestContext?.conflicts?.length ?? 0) > 0 && (
          <Collapsible className="rounded-xl border border-amber-500/40 bg-amber-500/5">
            <CollapsibleTrigger className="group flex w-full items-center gap-2 px-4 py-3 text-left text-sm">
              <span className="font-medium text-muted-foreground">Context health</span>
              <strong className="font-semibold">{latestContext?.conflicts?.length ?? 0} issue{latestContext?.conflicts?.length === 1 ? "" : "s"} require review</strong>
              <ChevronDown className="ml-auto size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
            </CollapsibleTrigger>
            <CollapsibleContent className="flex flex-col gap-2 border-t border-amber-500/30 p-4">
              {latestContext?.conflicts?.map((conflict) => <p key={conflict.key} className="flex items-start gap-2 text-sm"><Badge variant="outline" className="shrink-0 capitalize">{conflict.severity}</Badge><span className="text-muted-foreground">{conflict.description}</span></p>)}
            </CollapsibleContent>
          </Collapsible>
        )}
      </PageScroll>}

      {view === "trace" && <PageScroll>
        <PageTitle title="Trace explorer" subtitle="Follow the complete path from user question to context, SQL, evidence, and final synthesis." action={<Badge variant="outline" className="gap-1.5"><span className={cn("size-1.5 rounded-full", tracingRuntime?.enabled ? "bg-emerald-500" : "bg-muted-foreground")} />Langfuse {tracingRuntime?.enabled ? "connected" : "local trace"}</Badge>} />
        <TraceWorkspace key={activeInsight?.trace?.trace_id ?? "empty"} insight={activeInsight} tracing={tracingRuntime} />
      </PageScroll>}
    </section>

    <Dialog open={intakeOpen} onOpenChange={(open) => { if (!busy) setIntakeOpen(open); }}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <span className="text-xs text-muted-foreground">New feature release</span>
          <DialogTitle>Create feature intelligence</DialogTitle>
          <DialogDescription>Upload the product brief and observed events. FeatureLens will propose the ClickHouse contract before anything is executed.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5"><Label>Feature name</Label><Input value={intakeName} onChange={(event) => { setIntakeName(event.target.value); setIntakeSlug(slugify(event.target.value)); }} /></div>
          <div className="flex flex-col gap-1.5"><Label>Schema version</Label><Input type="number" min={1} value={schemaVersion} onChange={(event) => setSchemaVersion(Math.max(1, Number(event.target.value) || 1))} /></div>
          <div className="flex flex-col gap-1.5 sm:col-span-2"><Label>Release slug</Label><Input value={intakeSlug} onChange={(event) => setIntakeSlug(slugify(event.target.value))} /></div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className={cn("flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-accent", specFile && "border-emerald-500/40 bg-emerald-500/5")}>
            <input type="file" accept=".md,.markdown,text/plain" className="sr-only" onChange={(event) => void loadSpec(event.target.files?.[0])} />
            <b className={cn("grid size-9 shrink-0 place-items-center rounded-md text-xs font-semibold", specFile ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" : "bg-muted text-muted-foreground")}>{specFile ? <Check className="size-4" /> : "MD"}</b>
            <span className="min-w-0"><strong className="block truncate text-sm font-medium">{specFile?.name ?? "Feature specification"}</strong><small className="text-xs text-muted-foreground">{specFile ? formatBytes(specFile.size) : "Choose spec.md"}</small></span>
          </label>
          <label className={cn("flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-accent", eventFile && "border-emerald-500/40 bg-emerald-500/5")}>
            <input type="file" accept=".ndjson,.jsonl,application/json,text/plain" className="sr-only" onChange={(event) => void loadEvents(event.target.files?.[0])} />
            <b className={cn("grid size-9 shrink-0 place-items-center rounded-md text-xs font-semibold", eventFile ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" : "bg-muted text-muted-foreground")}>{eventFile ? <Check className="size-4" /> : <Braces className="size-4" />}</b>
            <span className="min-w-0"><strong className="block truncate text-sm font-medium">{eventFile?.name ?? "Observed events"}</strong><small className="text-xs text-muted-foreground">{eventFile ? formatBytes(eventFile.size) : "Choose events.ndjson"}</small></span>
          </label>
        </div>
        {intakeError && <p className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-2.5 text-sm text-destructive"><AlertCircle className="size-4" /> {intakeError}</p>}
        {preflight && (
          <div className="rounded-lg border bg-muted/40 p-3">
            <div className="flex items-center justify-between"><span className="text-xs font-medium text-muted-foreground">Event package</span><Badge variant="secondary">Ready ✓</Badge></div>
            <div className="mt-2 grid grid-cols-3 gap-2 text-center">
              <span><small className="block text-xs text-muted-foreground">Rows</small><strong className="text-sm tabular-nums">{preflight.rows.toLocaleString()}</strong></span>
              <span><small className="block text-xs text-muted-foreground">Event types</small><strong className="text-sm tabular-nums">{preflight.eventTypes.length}</strong></span>
              <span><small className="block text-xs text-muted-foreground">Fields</small><strong className="text-sm tabular-nums">{preflight.fields}</strong></span>
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">{preflight.firstEvent} → {preflight.lastEvent}</p>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {["Instrumentation", "Human approval", "Context", "Analytics"].map((step, i, arr) => <span key={step} className="flex items-center gap-1.5"><Badge variant="outline">{step}</Badge>{i < arr.length - 1 && <span>→</span>}</span>)}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setIntakeOpen(false)}>Cancel</Button>
          <Button onClick={() => void submitUnseen()} disabled={busy || !specFile || !eventFile || !preflight}>Submit release →</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog open={resetOpen} onOpenChange={(open) => { if (!busy) setResetOpen(open); }}>
      <DialogContent>
        <DialogHeader>
          <span className="text-xs text-muted-foreground">Reset demo</span>
          <DialogTitle>Return the context layer to v0?</DialogTitle>
          <DialogDescription>Agent runs and context versions will be cleared. Raw Atlys and generated feature tables remain untouched.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label>Type <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">RESET</code> to confirm</Label>
          <Input value={resetConfirmation} onChange={(event) => setResetConfirmation(event.target.value)} placeholder="RESET" />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setResetOpen(false)}>Keep versions</Button>
          <Button variant="destructive" onClick={() => void resetBaseline()} disabled={busy || resetConfirmation !== "RESET"}>Reset baseline</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog open={powerChatOpen} onOpenChange={setPowerChatOpen}>
      <DialogContent>
        <DialogHeader className="items-center text-center sm:text-center">
          <BrandMark />
          <span className="mt-1 text-xs text-muted-foreground">FeatureLens Power Chat</span>
          <DialogTitle>LibreChat is ready to connect.</DialogTitle>
          <DialogDescription>Power Chat runs as a separate conversational client through the same governed FeatureLens MCP tools. Configure its public URL to open it from this workspace.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2 rounded-lg border bg-muted/40 p-3 text-sm">
          {["Shared ClickHouse evidence", "Context-aware follow-ups", "Langfuse trace IDs"].map((feature) => <span key={feature} className="flex items-center gap-2"><Check className="size-4 text-emerald-600 dark:text-emerald-400" /> {feature}</span>)}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setPowerChatOpen(false)}>Continue in FeatureLens</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </main>;
}
