"use client";

import { useCallback, useEffect, useState } from "react";
import { UNAUTHORIZED_EVENT, getToken, setToken } from "@/lib/api";
import { Button } from "./ui";

/**
 * Prompts for the bearer token when the service rejects a request.
 *
 * Deliberately reactive rather than a login screen. On loopback the Go service
 * runs with no --token and every request succeeds, so demanding a token up front
 * would add a step to the common case for nothing. Exposed on a routable address
 * it refuses to start without one, and then the first fetch 401s — which is the
 * signal this listens for.
 *
 * Saving reloads the page. Blunt, but it re-runs every SWR fetch and every
 * in-flight poll with the new header; selectively revalidating from outside the
 * SWR tree would mean threading a mutate handle through both dashboards to solve
 * a problem that happens once per browser.
 */
export function TokenGate() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [hadToken, setHadToken] = useState(false);

  useEffect(() => {
    const onUnauthorized = () => {
      setHadToken(getToken() !== "");
      setValue(getToken());
      setOpen(true);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const save = useCallback(() => {
    setToken(value.trim());
    window.location.reload();
  }, [value]);

  if (!open) return null;

  return (
    <div
      role="alertdialog"
      aria-labelledby="token-gate-title"
      className="border-b border-bad/50 bg-bad/10"
    >
      <div className="mx-auto flex w-full max-w-[80rem] flex-wrap items-end gap-3 px-5 py-3">
        <div className="min-w-0 flex-1">
          <p
            id="token-gate-title"
            className="text-[0.8125rem] font-semibold text-ink"
          >
            {hadToken
              ? "The stored token was rejected."
              : "This service requires a token."}
          </p>
          <p className="mt-0.5 text-[0.6875rem] leading-snug text-ink-3">
            The value of <code className="font-mono">MOCK_TOKEN</code> on the
            host, from <code className="font-mono">/etc/sonyliv/sonyliv.env</code>
            . Stored in this browser only.
          </p>
        </div>

        <input
          type="password"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && value.trim()) save();
          }}
          placeholder="bearer token"
          aria-label="Bearer token"
          className="w-full min-w-0 rounded border border-line bg-sunken px-2.5 py-2 font-mono text-[0.8125rem] text-ink outline-none focus:border-accent sm:w-[22rem]"
        />

        <Button variant="primary" onClick={save} disabled={!value.trim()}>
          Save and reload
        </Button>
      </div>
    </div>
  );
}
