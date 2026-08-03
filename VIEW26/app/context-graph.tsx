"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type ContextGraphNode = { key: string; type: string; name: string; status: string; confidence: number };
export type ContextGraphEdge = { from: string; relation: string; to: string };

const TYPE_COLORS: Record<string, string> = {
  feature: "#0c66e4",
  event: "#e56910",
  metric: "#6e5dc6",
  table: "#253858",
  dimension: "#1f845a",
  business_question: "#cf3f6e",
  analysis_playbook: "#00a3bf",
  role_profile: "#946f00",
  entity: "#8590a2",
  business_domain: "#101214",
  funnel: "#8270db",
  known_issue: "#c9372c",
  operating_principle: "#6b778c",
};

function typeColor(type: string) {
  return TYPE_COLORS[type] ?? "#44546f";
}

function hashString(value: string) {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function mulberry32(seed: number) {
  let state = seed || 1;
  return () => {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Box = { x: number; y: number; w: number; h: number };

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export default function ContextGraph({ nodes, edges }: { nodes: ContextGraphNode[]; edges: ContextGraphEdge[] }) {
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [box, setBox] = useState<Box | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ id: number; startX: number; startY: number; box: Box; moved: boolean } | null>(null);

  const layout = useMemo(() => {
    const index = new Map(nodes.map((node, i) => [node.key, i]));
    const count = nodes.length;
    const x = new Float64Array(count);
    const y = new Float64Array(count);
    const rand = mulberry32(hashString(nodes.map((node) => node.key).join("|")));
    const types = [...new Set(nodes.map((node) => node.type))];
    nodes.forEach((node, i) => {
      const angle = (types.indexOf(node.type) / Math.max(1, types.length)) * Math.PI * 2 + (rand() - 0.5) * 0.9;
      const radius = 60 + rand() * 160;
      x[i] = Math.cos(angle) * radius;
      y[i] = Math.sin(angle) * radius;
    });
    const links: [number, number][] = [];
    const degree = new Array<number>(count).fill(0);
    for (const edge of edges) {
      const a = index.get(edge.from);
      const b = index.get(edge.to);
      if (a === undefined || b === undefined || a === b) continue;
      links.push([a, b]);
      degree[a]++;
      degree[b]++;
    }
    const ticks = 280;
    for (let tick = 0; tick < ticks; tick++) {
      const alpha = 1 - tick / ticks;
      const heat = 14 * alpha * alpha + 0.4;
      const dx = new Float64Array(count);
      const dy = new Float64Array(count);
      for (let i = 0; i < count; i++) {
        for (let j = i + 1; j < count; j++) {
          let ax = x[i] - x[j];
          let ay = y[i] - y[j];
          let d2 = ax * ax + ay * ay;
          if (d2 < 1) {
            ax = rand() - 0.5;
            ay = rand() - 0.5;
            d2 = ax * ax + ay * ay + 0.01;
          }
          if (d2 > 32000) continue;
          const force = 620 / d2;
          dx[i] += ax * force;
          dy[i] += ay * force;
          dx[j] -= ax * force;
          dy[j] -= ay * force;
        }
      }
      for (const [a, b] of links) {
        const ax = x[b] - x[a];
        const ay = y[b] - y[a];
        const d = Math.sqrt(ax * ax + ay * ay) || 1;
        const rest = 42 + Math.min(26, (degree[a] + degree[b]) * 1.1);
        const force = ((d - rest) / d) * 0.045;
        dx[a] += ax * force;
        dy[a] += ay * force;
        dx[b] -= ax * force;
        dy[b] -= ay * force;
      }
      for (let i = 0; i < count; i++) {
        dx[i] -= x[i] * 0.012;
        dy[i] -= y[i] * 0.012;
        const len = Math.sqrt(dx[i] * dx[i] + dy[i] * dy[i]) || 1;
        const step = Math.min(len, heat);
        x[i] += (dx[i] / len) * step;
        y[i] += (dy[i] / len) * step;
      }
    }
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let i = 0; i < count; i++) {
      minX = Math.min(minX, x[i]);
      minY = Math.min(minY, y[i]);
      maxX = Math.max(maxX, x[i]);
      maxY = Math.max(maxY, y[i]);
    }
    if (count === 0) { minX = minY = -100; maxX = maxY = 100; }
    const pad = 46;
    const fit: Box = { x: minX - pad, y: minY - pad, w: maxX - minX + pad * 2, h: maxY - minY + pad * 2 };
    return { x, y, degree, index, fit };
  }, [nodes, edges]);

  useEffect(() => setBox(layout.fit), [layout]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      setBox((prev) => {
        if (!prev) return prev;
        const rect = svg.getBoundingClientRect();
        const scale = Math.exp(event.deltaY * 0.0016);
        const w = clamp(prev.w * scale, 60, 6000);
        const h = prev.h * (w / prev.w);
        const px = prev.x + ((event.clientX - rect.left) / rect.width) * prev.w;
        const py = prev.y + ((event.clientY - rect.top) / rect.height) * prev.h;
        return { x: px - (px - prev.x) * (w / prev.w), y: py - (py - prev.y) * (h / prev.h), w, h };
      });
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, []);

  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const edge of edges) {
      if (!map.has(edge.from)) map.set(edge.from, new Set());
      if (!map.has(edge.to)) map.set(edge.to, new Set());
      map.get(edge.from)!.add(edge.to);
      map.get(edge.to)!.add(edge.from);
    }
    return map;
  }, [edges]);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const node of nodes) counts[node.type] = (counts[node.type] ?? 0) + 1;
    return counts;
  }, [nodes]);

  const visibleKeys = useMemo(() => new Set(nodes.filter((node) => !hiddenTypes.has(node.type)).map((node) => node.key)), [nodes, hiddenTypes]);
  const visibleEdges = useMemo(() => edges.filter((edge) => visibleKeys.has(edge.from) && visibleKeys.has(edge.to)), [edges, visibleKeys]);

  const selected = selectedKey && visibleKeys.has(selectedKey) ? nodes.find((node) => node.key === selectedKey) ?? null : null;
  const neighborSet = selected ? adjacency.get(selected.key) : undefined;

  function radiusOf(key: string) {
    const i = layout.index.get(key);
    if (i === undefined) return 5;
    return 4.5 + Math.min(7, layout.degree[i] * 0.8) + (nodes[i]?.type === "feature" ? 1.5 : 0);
  }

  function toggleType(type: string) {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  function onPointerDown(event: React.PointerEvent<SVGSVGElement>) {
    if (!box) return;
    dragRef.current = { id: event.pointerId, startX: event.clientX, startY: event.clientY, box, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    const svg = svgRef.current;
    if (!drag || !svg || drag.id !== event.pointerId) return;
    const rect = svg.getBoundingClientRect();
    const dx = ((event.clientX - drag.startX) / rect.width) * drag.box.w;
    const dy = ((event.clientY - drag.startY) / rect.height) * drag.box.h;
    if (Math.abs(event.clientX - drag.startX) + Math.abs(event.clientY - drag.startY) > 4) drag.moved = true;
    setBox({ ...drag.box, x: drag.box.x - dx, y: drag.box.y - dy });
  }

  function onPointerUp(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    dragRef.current = null;
    if (drag && !drag.moved && event.target === event.currentTarget) setSelectedKey(null);
  }

  if (nodes.length === 0) return null;

  const selectedConnections = selected
    ? edges
        .filter((edge) => edge.from === selected.key || edge.to === selected.key)
        .map((edge) => {
          const outbound = edge.from === selected.key;
          const otherKey = outbound ? edge.to : edge.from;
          return { relation: edge.relation, outbound, other: nodes.find((node) => node.key === otherKey) };
        })
        .filter((connection) => connection.other)
    : [];

  return (
    <Card className="gap-3 py-4 overflow-hidden">
      <div className="flex items-center justify-between gap-3 px-4">
        <span className="text-sm font-semibold">Context graph</span>
        <div className="flex items-center gap-3">
          <b className="text-xs font-normal text-muted-foreground">{visibleKeys.size} nodes · {visibleEdges.length} edges</b>
          <Button variant="outline" size="sm" onClick={() => setBox(layout.fit)}>Fit view</Button>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5 px-4">
        {Object.entries(typeCounts).map(([type, count]) => (
          <button key={type} className={cn("inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors hover:bg-accent", hiddenTypes.has(type) && "opacity-40 line-through")} onClick={() => toggleType(type)}>
            <i className="size-2.5 rounded-[3px]" style={{ background: typeColor(type) }} />
            {type.replaceAll("_", " ")}
            <b className="font-semibold text-muted-foreground">{count}</b>
          </button>
        ))}
      </div>
      <div className="relative mx-4 rounded-lg border bg-muted/30 [&_svg]:block [&_svg]:h-[420px] [&_svg]:w-full [&_svg]:cursor-grab [&_svg]:touch-none active:[&_svg]:cursor-grabbing">
        <svg
          ref={svgRef}
          viewBox={box ? `${box.x} ${box.y} ${box.w} ${box.h}` : undefined}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Context graph of features, events, metrics, and relationships"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          <defs>
            <marker id="fl-graph-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M0,0.6 L7.4,4 L0,7.4 Z" fill="var(--foreground)" />
            </marker>
          </defs>
          {visibleEdges.map((edge, i) => {
            const a = layout.index.get(edge.from);
            const b = layout.index.get(edge.to);
            if (a === undefined || b === undefined) return null;
            const highlighted = selected ? edge.from === selected.key || edge.to === selected.key : false;
            const dimmed = selected ? !highlighted : false;
            let x1 = layout.x[a], y1 = layout.y[a], x2 = layout.x[b], y2 = layout.y[b];
            if (highlighted) {
              const dx = x2 - x1, dy = y2 - y1;
              const d = Math.sqrt(dx * dx + dy * dy) || 1;
              const trimA = radiusOf(edge.from) + 1.5;
              const trimB = radiusOf(edge.to) + 2.5;
              x1 += (dx / d) * trimA; y1 += (dy / d) * trimA;
              x2 -= (dx / d) * trimB; y2 -= (dy / d) * trimB;
            }
            return (
              <g key={`${edge.from}-${edge.relation}-${edge.to}-${i}`}>
                <line
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={highlighted ? "var(--foreground)" : "var(--border)"}
                  strokeWidth={highlighted ? 1.2 : 0.7}
                  opacity={dimmed ? 0.1 : highlighted ? 0.95 : 0.55}
                  markerEnd={highlighted ? "url(#fl-graph-arrow)" : undefined}
                />
                {highlighted && (
                  <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 1.6} fill="var(--muted-foreground)" fontSize={3.4} textAnchor="middle">
                    {edge.relation.replaceAll("_", " ").toLowerCase()}
                  </text>
                )}
              </g>
            );
          })}
          {nodes.map((node) => {
            if (!visibleKeys.has(node.key)) return null;
            const i = layout.index.get(node.key);
            if (i === undefined) return null;
            const isSelected = selected?.key === node.key;
            const isNeighbor = neighborSet?.has(node.key) ?? false;
            const dimmed = selected ? !isSelected && !isNeighbor : false;
            const r = radiusOf(node.key);
            const contradicted = node.status === "contradicted";
            const dashed = contradicted || node.status === "inferred";
            return (
              <g
                key={node.key}
                className="cursor-pointer"
                opacity={dimmed ? 0.16 : 1}
                onPointerDown={(event) => event.stopPropagation()}
                onClick={() => setSelectedKey((prev) => (prev === node.key ? null : node.key))}
              >
                <title>{`${node.name}\n${node.type.replaceAll("_", " ")} · ${node.status} · ${Math.round(node.confidence * 100)}% confidence`}</title>
                {isSelected && <circle cx={layout.x[i]} cy={layout.y[i]} r={r + 3.5} fill="none" stroke={typeColor(node.type)} strokeWidth={1} opacity={0.45} />}
                <circle
                  cx={layout.x[i]}
                  cy={layout.y[i]}
                  r={r}
                  fill={typeColor(node.type)}
                  stroke={contradicted ? "var(--destructive)" : "var(--card)"}
                  strokeWidth={contradicted ? 1.6 : node.status === "verified" ? 1.4 : 1}
                  strokeDasharray={dashed ? "2.4 1.7" : undefined}
                  strokeOpacity={node.status === "declared" ? 0.55 : 1}
                />
                <text x={layout.x[i]} y={layout.y[i] + r + 5.4} fill="var(--foreground)" fontSize={3.6} textAnchor="middle" opacity={selected && !isSelected && !isNeighbor ? 0.4 : 0.9}>
                  {node.name.length > 26 ? `${node.name.slice(0, 25)}…` : node.name}
                </text>
              </g>
            );
          })}
        </svg>
        {selected && (
          <aside className="absolute top-3 right-3 w-64 max-h-[calc(100%-1.5rem)] overflow-y-auto rounded-lg border bg-popover text-popover-foreground p-3 shadow-md">
            <span className="inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium text-white" style={{ background: typeColor(selected.type) }}>{selected.type.replaceAll("_", " ")}</span>
            <h3 className="mt-2 text-sm font-semibold leading-tight">{selected.name}</h3>
            <code className="mt-1 block text-[11px] text-muted-foreground break-all">{selected.key}</code>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              <div><small className="block text-[10px] uppercase tracking-wide text-muted-foreground">Status</small><strong className="text-xs capitalize">{selected.status}</strong></div>
              <div><small className="block text-[10px] uppercase tracking-wide text-muted-foreground">Confidence</small><strong className="text-xs">{Math.round(selected.confidence * 100)}%</strong></div>
              <div><small className="block text-[10px] uppercase tracking-wide text-muted-foreground">Links</small><strong className="text-xs">{selectedConnections.length}</strong></div>
            </div>
            <p className="mt-3 text-xs font-medium text-muted-foreground">Relationships</p>
            <div className="mt-1.5 flex flex-col gap-1">
              {selectedConnections.map((connection, i) => (
                <button key={`${connection.relation}-${connection.other!.key}-${i}`} className="rounded-md border px-2 py-1.5 text-left transition-colors hover:bg-accent" onClick={() => setSelectedKey(connection.other!.key)}>
                  <small className="block text-[10px] text-muted-foreground">{connection.outbound ? "→" : "←"} {connection.relation.replaceAll("_", " ").toLowerCase()}</small>
                  <strong className="mt-0.5 flex items-center gap-1.5 text-xs font-medium"><i className="size-2 rounded-[2px] shrink-0" style={{ background: typeColor(connection.other!.type) }} />{connection.other!.name}</strong>
                </button>
              ))}
            </div>
            <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={() => setSelectedKey(null)}>Clear selection</Button>
          </aside>
        )}
      </div>
      <p className="px-4 text-xs text-muted-foreground">Scroll to zoom · drag to pan · click a node to inspect its relationships · click a legend chip to filter a type</p>
    </Card>
  );
}
