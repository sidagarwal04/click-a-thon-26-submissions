"use client";

import HyperDX from "@hyperdx/browser";
import { useEffect } from "react";

let initialized = false;

function sameOriginPattern() {
  return new RegExp(
    `^${window.location.origin.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`,
  );
}

export function HyperDXProvider() {
  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_OTEL_EXPORTER_OTLP_ENDPOINT;
    const apiKey = process.env.NEXT_PUBLIC_HYPERDX_API_KEY;

    // Avoid sending telemetry until an ingest endpoint (local or hosted) has
    // explicitly been configured. This also makes the provider safe in CI.
    if (initialized || (!url && !apiKey)) return;

    HyperDX.init({
      apiKey: apiKey ?? "",
      service: "sentinel-web",
      url,
      tracePropagationTargets: [sameOriginPattern()],
      consoleCapture: false,
      advancedNetworkCapture: false,
      maskAllInputs: true,
      disableIntercom: true,
      disableReplay: process.env.NEXT_PUBLIC_HYPERDX_ENABLE_REPLAY !== "true",
      otelResourceAttributes: {
        "deployment.environment": process.env.NODE_ENV,
      },
    });
    initialized = true;
  }, []);

  return null;
}
