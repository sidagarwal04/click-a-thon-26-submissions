# Foundation Metrics Library

`@open-zentra/foundation-metrics` is the frontend observability library for OpenZentra. It provides OpenTelemetry-based instrumentation for browser applications with first-class support for:

- Errors
- Performance signals (web vitals, page load, SPA navigation, long tasks)
- Network signals (Fetch, XHR, retries)
- User behavior signals (clicks, navigation, sessions, rage clicks)
- Compliance controls (PII scrubbing, field allowlists)

## Package goals

- Use OpenTelemetry as the canonical instrumentation layer.
- Provide safe defaults for enterprise environments.
- Keep SDK usage simple while allowing extensibility through plugins.
- Keep runtime dependencies focused on `foundation-data-model` and `foundation-utils`.

## Installation

From the monorepo, this package is consumed via workspace linking.

For external package consumers:

```bash
npm install @open-zentra/foundation-metrics
```

Peer/runtime expectations:

- Browser runtime (`window`, `document`) for full instrumentation features.
- OpenTelemetry collector endpoint available for OTLP HTTP exports.

## Quick start

```ts
import { COMPLIANCE_REGION, ENVIRONMENT } from '@open-zentra/foundation-data-model';
import { FoundationMetrics } from '@open-zentra/foundation-metrics';

FoundationMetrics.init({
  serviceName: 'insights-web',
  collectorEndpoint: 'https://otel.example.com',
  environment: ENVIRONMENT.PRODUCTION,
  version: '1.0.0',
  signals: {
    errors: true,
    performance: true,
    network: true,
    userBehavior: true,
  },
  sampling: {
    defaultRate: 1,
    errorRate: 1,
    traceRate: 0.1,
    userBehaviorRate: 0.1,
  },
  compliance: {
    piiFields: ['email', 'password', 'token'],
    allowedFields: [],
    region: COMPLIANCE_REGION.US,
    autoPiiDetection: true,
  },
});
```

## Core API

### SDK lifecycle

```ts
import {
  FoundationMetrics,
  getInstance,
  init,
  isInitialized,
} from '@open-zentra/foundation-metrics';

init(config);

if (isInitialized()) {
  const sdk: FoundationMetrics = getInstance();
  await sdk.flush();
  await sdk.shutdown();
}
```

### Manual instrumentation examples

```ts
const sdk = FoundationMetrics.getInstance();

sdk.captureError(new Error('Checkout failed'), {
  type: 'custom',
  componentName: 'CheckoutForm',
  metadata: { step: 'payment' },
});

sdk.captureMessage('Checkout clicked', 'info', {
  attributes: { page: '/checkout' },
});

const span = sdk.startSpan('cart.calculate.total', {
  kind: 'internal',
  attributes: { source: 'cart' },
});
// ...work
span.end();

sdk.trackInteraction({
  type: 'click',
  targetTag: 'button',
  targetOzid: 'checkout-submit',
  timestamp: Date.now(),
  route: '/checkout',
});
```

## Configuration reference

`FoundationMetricsConfig` fields:

- `serviceName` (`string`, required): logical service name emitted in OTel resource attributes.
- `collectorEndpoint` (`string`, required): OTLP collector base URL.
- `environment` (`Environment`, required): use values from `ENVIRONMENT`.
- `version` (`string`, required): app/release version.
- `signals` (`SignalsConfig`, required): enable booleans or per-signal config objects.
- `sampling` (`SamplingConfig`, required): sampling rates (`0..1`).
- `compliance` (`ComplianceConfig`, required): PII + regional compliance settings.
- `tenant` (`TenantConfig`, optional): tenant context metadata.
- `transport` (`Partial<TransportConfig>`, optional): queue/flush/retry tuning.
- `plugins` (`FoundationMetricsPlugin[]`, optional): plugin list.
- `debug` (`boolean`, optional): enables verbose diagnostics.
- `resourceAttributes` (`Record<string, string>`, optional): additional OTel resource attributes.

### Signal-specific controls

- Errors: global errors, unhandled rejections, stack depth, source-map flags.
- Performance: web vitals, page load, SPA navigation, long tasks threshold.
- Network: Fetch/XHR toggles, retry tracking, ignore URL patterns, trace propagation targets.
- User behavior: click/navigation/session/rage-click controls.

## Internal architecture

High-level flow:

1. `FoundationMetrics.init` validates and resolves config (`core/config-resolver.ts`).
2. OTel providers initialize via singleton `OTelProvider` (`core/otel-provider.ts`).
3. Context manager initializes browser/session/user/tenant context (`core/context-manager.ts`).
4. Instrumentation modules emit spans/metrics and enrich attributes.
5. Compliance modules scrub/redact sensitive data before export paths.

Key modules:

- `src/core`: SDK lifecycle, config resolution, OTel provider, context manager.
- `src/instrumentation`: errors/performance/network/user-behavior instrumentation.
- `src/compliance`: PII scrubbing and field filtering.
- `src/sampling`: head, priority, and consistent samplers + rate limiting.
- `src/plugins`: plugin manager + default singleton.
- `src/types`: public contracts and constants.
- `src/utils`: metrics-specific helpers only.

## Extensibility

### Plugin model

Plugins implement `FoundationMetricsPlugin` hooks and are registered through config (`plugins`).

Hook categories include:

- Lifecycle: `onInit`, `onShutdown`
- Pre/post data hooks: `beforeCaptureError`, `beforeRecordWebVital`, `beforeTrackInteraction`, etc.
- Context/export hooks: `onContextUpdate`, `beforeExport`

Use plugins for custom enrichment, filtering, routing, and integration behavior.

## Compliance and security

- Use `createPIIScrubber` for string/object redaction.
- Use `scrubUrl` and `scrubHeaders` for network-safe logging.
- Use field allowlist utilities to drop unapproved attributes.
- Tenant/user IDs are hashed through utilities before being attached to spans.

## Development and verification

Run strict typecheck for this library:

```bash
npx tsc -p libs/foundation/metrics/tsconfig.lib.json --noEmit
```

Run key package tests:

```bash
npx vitest run \
  libs/foundation/metrics/src/core/foundation-metrics.spec.ts \
  libs/foundation/metrics/src/sampling/head-sampler.spec.ts \
  libs/foundation/metrics/src/compliance/pii-scrubber.spec.ts
```

## Design notes and conventions

- Use constants from `src/types/constants.ts` for fixed-option values.
- Prefer imports from `foundation-data-model` and `foundation-utils` for shared primitives.
- Avoid duplicating shared utility logic in this package.
- Keep long-lived resources singleton-backed only where appropriate (`OTelProvider`, plugin manager).

## Contributing guidance

When extending this library:

1. Add/update types in `src/types` first.
2. Keep instrumentation modules stateless where possible; isolate mutable state.
3. Ensure cleanup paths remove listeners/timers and clear in-memory state.
4. Add or update tests for behavioral changes.
5. Run strict typecheck and package tests before opening a PR.
