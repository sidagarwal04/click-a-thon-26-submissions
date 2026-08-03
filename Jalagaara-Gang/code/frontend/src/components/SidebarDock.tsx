import { useCallback, useEffect, useRef, useState } from "react";
import type { InvestigationRow } from "../types";
import { sendChat, type ChatTurn } from "../api";
import { MarkdownLite } from "./MarkdownLite";

const ChatIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);
const CloseIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);
const EnvelopeIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="5" width="18" height="14" rx="2" /><polyline points="3 7 12 13 21 7" />
  </svg>
);
const RefreshIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 4v6h-6" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
  </svg>
);
const NewChatIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </svg>
);

type Panel = "none" | "history" | "chat";

// The sidebar's bottom dock: two compact buttons (Past investigations, Ask a follow-up)
// each opening a panel anchored above them — the history unfolds like an envelope,
// the assistant grows up into a built-in chat. Only one panel is open at a time.
//
// The chat talks to our own /v1/chat/completions rather than embedding LibreChat, because it
// must carry `bundleId` — the anomaly currently showcased on the dashboard — with every
// message, so "replay this anomaly end to end" and other under-specified questions resolve
// against what's on screen instead of asking the user to restate it.
export function SidebarDock({
  history,
  onOpenRun,
  onRefresh,
  segOf,
  bundleId,
}: {
  history: InvestigationRow[];
  onOpenRun: (id: string) => void;
  onRefresh: () => void;
  segOf: (row: InvestigationRow) => string;
  bundleId: string | null;
}) {
  const [open, setOpen] = useState<Panel>("none");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const scroller = useRef<HTMLDivElement>(null);

  const toggle = (p: Panel) => setOpen((o) => (o === p ? "none" : p));

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [turns, open]);

  // Start a brand-new chat thread: fresh (empty) conversation + a new session id, so the backend
  // opens a new chat rather than appending to the old one.
  const newChat = useCallback(() => {
    setTurns([]);
    setDraft("");
    setSessionId(crypto.randomUUID());
  }, []);

  // Selecting a different anomaly automatically opens a new chat scoped to it. Skip the first
  // assignment (initial bundle load) so we don't spin up a second session on mount.
  const firstBundle = useRef(true);
  useEffect(() => {
    if (firstBundle.current) {
      firstBundle.current = false;
      return;
    }
    newChat();
  }, [bundleId, newChat]);

  const send = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    const next: ChatTurn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setDraft("");
    setBusy(true);
    try {
      const reply = await sendChat(next, bundleId, sessionId);
      setTurns([...next, { role: "assistant", content: reply }]);
    } catch {
      setTurns([...next, { role: "assistant", content: "Backend unreachable — is :8000 up?" }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sidebar-dock">
      {/* Past investigations — unfolds like an envelope */}
      <div className={`dock-panel history-panel ${open === "history" ? "open" : ""}`} role="dialog" aria-label="Past investigations" aria-hidden={open !== "history"}>
        <div className="dock-panel-head">
          <span className="eyebrow">Past investigations</span>
          <div className="dph-actions">
            <button className="dock-icon" onClick={onRefresh} aria-label="Refresh history">{RefreshIcon}</button>
            <button className="dock-icon" onClick={() => setOpen("none")} aria-label="Close">{CloseIcon}</button>
          </div>
        </div>
        <div className="dock-panel-body history-scroll">
          {history.length === 0 ? (
            <div className="history-empty">No stored investigations yet — run one.</div>
          ) : (
            history.map((row) => (
              <button
                key={row.investigation_id}
                className="history-row"
                onClick={() => { onOpenRun(row.investigation_id); setOpen("none"); }}
              >
                <span className="hr-metric">{row.metric}</span>
                <span className={`hr-status ${row.detected ? "detected" : "flat"}`}>{row.detected ? "detected" : "flat"}</span>
                <span className="hr-seg">{segOf(row)}</span>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Ask a follow-up — built-in chat, bundle-aware */}
      <div className={`dock-panel assistant-pop ${open === "chat" ? "open" : ""}`} role="dialog" aria-label="RCA Assistant" aria-hidden={open !== "chat"}>
        <div className="assistant-pop-head">
          <div className="ap-title">
            <span className="ap-avatar">{ChatIcon}</span>
            <span className="ap-titles">
              <span className="ap-name">RCA Assistant</span>
              <span className="ap-status">
                <span className="ap-live" />
                {bundleId ? ` Context: ${bundleId.slice(0, 8)}` : " Online · ask about any metric"}
              </span>
            </span>
          </div>
          <div className="ap-actions">
            <button className="ap-close" onClick={newChat} aria-label="New chat" title="New chat">{NewChatIcon}</button>
            <button className="ap-close" onClick={() => setOpen("none")} aria-label="Close assistant">{CloseIcon}</button>
          </div>
        </div>
        <div className="assistant-pop-body chat-body" ref={scroller}>
          {turns.length === 0 && (
            <div className="chat-msg assistant">
              Ask me to <em>replay this anomaly incident end to end</em>, or anything about the
              investigation on screen.
            </div>
          )}
          {turns.map((t, i) => (
            <div key={i} className={`chat-msg ${t.role}`}>
              {t.role === "assistant" ? <MarkdownLite text={t.content} /> : t.content}
            </div>
          ))}
          {busy && <div className="chat-msg assistant chat-typing"><span /><span /><span /></div>}
        </div>
        <div className="chat-input-row">
          <input
            className="chat-input"
            value={draft}
            placeholder="Replay this anomaly end to end…"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            disabled={busy}
          />
          <button className="primary-btn" onClick={send} disabled={busy || !draft.trim()}>Send</button>
        </div>
      </div>

      {/* Button row: Past investigations (left) · Ask a follow-up (right) */}
      <div className="dock-buttons">
        <button
          className={`dock-btn history-btn ${open === "history" ? "is-open" : ""}`}
          onClick={() => toggle("history")}
          aria-expanded={open === "history"}
        >
          <span className="db-icon">{EnvelopeIcon}</span>
          <span>Past investigations</span>
        </button>
        <button
          className={`dock-btn chat-btn ${open === "chat" ? "is-open" : ""}`}
          onClick={() => toggle("chat")}
          aria-expanded={open === "chat"}
        >
          <span className="db-icon">{ChatIcon}</span>
          <span>Ask a follow-up</span>
        </button>
      </div>
    </div>
  );
}
