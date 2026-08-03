// Custom dropdown, replacing the native <select>.
//
// WHY NOT A NATIVE SELECT
// Chrome on macOS renders the native option popup at the OS default size and
// in the OS light palette, ignoring the control's font-size and our dark-mode
// tokens entirely. The result is a menu visibly larger than the app that stays
// light while the rest of the page is dark. Options cannot be styled around it,
// so the control is rebuilt.
//
// The rebuild also buys what the native control could not: a type-to-filter box
// for long lists (content_id has 3,357 values), and keyboard navigation that
// matches the visual state.
//
// THE MENU IS PORTALLED TO document.body ON PURPOSE
// The filter bar scrolls horizontally, and overflow-x on an ancestor creates a
// clipping context that an absolutely-positioned child cannot escape -- the
// menu was being sliced off at the card's edge. A portal + fixed positioning
// takes the menu out of that subtree entirely, so it can never be clipped by
// whatever container it happens to live in.

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

// Module-level registry so opening one menu closes any other. The outside-click
// handler covers mouse use, but a keyboard-opened menu would otherwise leave a
// previously-opened one on screen.
let closeOpenMenu: (() => void) | null = null;

export interface Option {
  value: string;
  label: string;
}

interface Props {
  value: string;
  options: Option[];
  onChange: (v: string) => void;
  /** Show a filter box once the list is longer than this. */
  searchAfter?: number;
  minWidth?: number;
  ariaLabel?: string;
}

export function Select({ value, options, onChange, searchAfter = 12, minWidth = 108, ariaLabel }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [rect, setRect] = useState<{ top: number; left: number; width: number } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // Declared before the effects below: `const` is not hoisted, so referencing
  // this from an effect defined earlier is a temporal-dead-zone ReferenceError
  // at render time -- which the type-checker does not catch.
  const close = useCallback(() => setOpen(false), []);

  // Position the portalled menu against the trigger. Recomputed on open and on
  // scroll/resize, since fixed coordinates do not follow the trigger on their own.
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const r = btnRef.current?.getBoundingClientRect();
      if (r) setRect({ top: r.bottom + 4, left: r.left, width: r.width });
    };
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open]);

  const current = options.find((o) => o.value === value) ?? options[0];
  const searchable = options.length > searchAfter;

  const shown = useMemo(() => {
    if (!query) return options;
    const q = query.toLowerCase();
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  // Close on outside click or Escape -- both, since either alone leaves the
  // menu stuck open in the other case.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      // The menu lives outside rootRef now (portal), so both must be checked.
      if (!rootRef.current?.contains(t) && !menuRef.current?.contains(t)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (open) {
      if (closeOpenMenu && closeOpenMenu !== close) closeOpenMenu();
      closeOpenMenu = close;
    } else if (closeOpenMenu === close) {
      closeOpenMenu = null;
    }
  }, [open, close]);

  useEffect(() => {
    if (open && searchable) searchRef.current?.focus();
    if (!open) {
      setQuery("");
      setActive(0);
    }
  }, [open, searchable]);

  const pick = (v: string) => {
    onChange(v);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open && (e.key === "Enter" || e.key === " " || e.key === "ArrowDown")) {
      e.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, shown.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (shown[active]) pick(shown[active].value);
    }
  };

  return (
    <div ref={rootRef} style={{ position: "relative", minWidth }} onKeyDown={onKeyDown}>
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: "6px 9px",
          fontSize: 13,
          cursor: "pointer",
          textAlign: "left",
          color: "var(--text-primary)",
        }}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {current?.label ?? "--"}
        </span>
        <span aria-hidden style={{ color: "var(--text-muted)", fontSize: 10, flexShrink: 0 }}>
          &#9662;
        </span>
      </button>

      {open &&
        rect &&
        createPortal(
        <div
          ref={menuRef}
          role="listbox"
          className="card"
          onKeyDown={onKeyDown}
          style={{
            position: "fixed",
            zIndex: 1000,
            top: rect.top,
            // Keep the menu on screen when the trigger sits near the right edge.
            left: Math.min(rect.left, window.innerWidth - Math.max(rect.width, 180) - 12),
            minWidth: rect.width,
            maxWidth: 300,
            maxHeight: 300,
            overflowY: "auto",
            padding: 4,
            boxShadow: "0 8px 24px rgba(0,0,0,0.28)",
          }}
        >
          {searchable && (
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              placeholder="Filter…"
              style={{
                width: "100%",
                boxSizing: "border-box",
                background: "var(--page)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "5px 8px",
                fontSize: 12,
                color: "var(--text-primary)",
                marginBottom: 4,
                font: "inherit",
                fontVariantNumeric: "tabular-nums",
              }}
            />
          )}

          {shown.length === 0 && (
            <div style={{ padding: "6px 8px", fontSize: 12, color: "var(--text-muted)" }}>No matches</div>
          )}

          {shown.map((o, i) => {
            const selected = o.value === value;
            return (
              <button
                key={o.value}
                type="button"
                role="option"
                aria-selected={selected}
                onClick={() => pick(o.value)}
                onMouseEnter={() => setActive(i)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  width: "100%",
                  border: "none",
                  borderRadius: 6,
                  // Hover/active is a neutral wash, not a saturated fill -- the
                  // menu is chrome, and a series colour here would read as data.
                  background: i === active ? "var(--page)" : "transparent",
                  color: "var(--text-primary)",
                  padding: "5px 8px",
                  fontSize: 13,
                  textAlign: "left",
                  cursor: "pointer",
                }}
              >
                <span style={{ width: 12, flexShrink: 0, color: "var(--text-secondary)" }}>
                  {selected ? "✓" : ""}
                </span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {o.label}
                </span>
              </button>
            );
          })}
        </div>,
        document.body,
      )}
    </div>
  );
}
