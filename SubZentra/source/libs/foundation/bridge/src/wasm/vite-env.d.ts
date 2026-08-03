/// <reference types="vite/client" />

/**
 * Type declarations for DuckDB-WASM asset imports via Vite's ?url suffix
 *
 * Note: vite/client.d.ts already provides generic ?url support.
 * These declarations are for specific module paths used in duckdb-init.ts.
 */

declare module '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url' {
  const url: string;
  export default url;
}

declare module '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url' {
  const url: string;
  export default url;
}

declare module '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url' {
  const url: string;
  export default url;
}

declare module '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url' {
  const url: string;
  export default url;
}
