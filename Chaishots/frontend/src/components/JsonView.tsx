import { useState } from "react";
import { Check, Copy, Maximize2, X } from "lucide-react";
import type { JsonValue } from "../types";

export function JsonView({ value, empty = "No data captured" }: { value: JsonValue | Record<string, JsonValue> | undefined; empty?: string }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const isEmpty = value == null || (typeof value === "object" && Object.keys(value).length === 0);
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);

  if (isEmpty) return <div className="empty-value">{empty}</div>;

  const copy = async () => {
    await navigator.clipboard.writeText(text ?? "");
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };

  const content = (
    <div className={`json-view ${expanded ? "json-view--modal" : ""}`}>
      <div className="json-actions">
        {!expanded && <button aria-label="Expand JSON" onClick={() => setExpanded(true)}><Maximize2 size={14} /></button>}
        <button aria-label="Copy JSON" onClick={copy}>{copied ? <Check size={14} /> : <Copy size={14} />}</button>
        {expanded && <button aria-label="Close" onClick={() => setExpanded(false)}><X size={15} /></button>}
      </div>
      <pre>{text}</pre>
    </div>
  );

  return expanded ? <div className="modal-backdrop" onMouseDown={() => setExpanded(false)}><div onMouseDown={(event) => event.stopPropagation()}>{content}</div></div> : content;
}
