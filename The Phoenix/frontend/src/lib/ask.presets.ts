// The provider presets, split out so the Ask panel can import them in the BROWSER.
//
// lib/ask.ts is server-only: it imports lib/env.ts, which reads ../.env with node:fs at module
// scope. Importing it from a client component puts node:fs in the browser chunk and the
// production build fails. Same split, and the same reason, as lib/datasets.ts against
// lib/datasets.server.ts.
export type LlmProvider = 'anthropic' | 'google' | 'openai'

export interface LlmPreset {
  id: LlmProvider
  label: string
  /** Where to get a key, so the panel can link it rather than assuming the reader knows. */
  keyUrl: string
  /** The LibreChat endpoint this maps to; it must carry `userProvidedKey: true`. */
  endpoint: string
  /**
   * The model to request when the caller brings their own key.
   *
   * REQUIRED, not optional. The agent id alone is enough only on the server credential path,
   * where the stored agent already names a model. A user-provided key reaches the provider with
   * whatever `model` the request carries, and an agent id is not a model name at Anthropic,
   * Google or OpenAI, so the call fails before it reaches the tool.
   *
   * Deliberately the ENTRY-TIER model of each provider: the visitor is spending their own credit
   * on a question about a concurrency table, and the expensive tiers buy nothing here.
   */
  model: string
}

export const LLM_PRESETS: Record<LlmProvider, LlmPreset> = {
  anthropic: {
    id: 'anthropic',
    label: 'Claude',
    keyUrl: 'https://console.anthropic.com/settings/keys',
    endpoint: 'anthropic',
    model: 'claude-haiku-4-5-20251001',
  },
  google: {
    id: 'google',
    label: 'Gemini',
    keyUrl: 'https://aistudio.google.com/apikey',
    endpoint: 'google',
    model: 'gemini-2.5-flash',
  },
  openai: {
    id: 'openai',
    label: 'Codex (OpenAI)',
    keyUrl: 'https://platform.openai.com/api-keys',
    endpoint: 'openAI',
    model: 'gpt-4o-mini',
  },
}
