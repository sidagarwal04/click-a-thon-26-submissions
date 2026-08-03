import { createPortal } from "react-dom";
import type { ReactNode } from "react";

type FloatingTooltipProps = {
  x: number;
  y: number;
  theme?: "light" | "dark";
  children: ReactNode;
};

const PAD = 8;
const EST_WIDTH = 200;
const EST_HEIGHT = 160;
const OFFSET = 12;

/**
 * Viewport-fixed tooltip via body portal so it never expands chat layout
 * or gets trapped by overflow/transform ancestors.
 * Anchors just below-right of the cursor (flips when near edges).
 */
export function FloatingTooltip({ x, y, theme = "light", children }: FloatingTooltipProps) {
  if (typeof document === "undefined") {
    return null;
  }

  let left = x + OFFSET;
  let top = y + OFFSET;

  if (left + EST_WIDTH > window.innerWidth - PAD) {
    left = x - EST_WIDTH - OFFSET;
  }
  if (left < PAD) {
    left = PAD;
  }
  if (top + EST_HEIGHT > window.innerHeight - PAD) {
    top = y - EST_HEIGHT - OFFSET;
  }
  if (top < PAD) {
    top = PAD;
  }

  const themeClass = theme === "dark" ? "da-theme-dark" : "da-theme-light";

  return createPortal(
    <div
      className={themeClass}
      style={{
        position: "fixed",
        left,
        top,
        zIndex: 9999,
        pointerEvents: "none",
      }}
    >
      {children}
    </div>,
    document.body,
  );
}
