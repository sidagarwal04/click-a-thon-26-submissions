import { Icon } from '@open-zentra/foundation-icons';

import type { ChatSuggestion } from '../../types';

interface ChatEmptyStateProps {
  readonly greetingName: string;
  readonly suggestions: readonly ChatSuggestion[];
  readonly onChoose: (prompt: string) => void;
}

/**
 * What an empty thread offers: a greeting, and four questions this tenant is
 * actually allowed to ask.
 */
export const ChatEmptyState = ({ greetingName, suggestions, onChoose }: ChatEmptyStateProps) => (
  <div className="flex h-full flex-col items-center justify-center px-6 py-10">
    <span
      className="mb-6 flex h-12 w-12 items-center justify-center rounded-sm bg-accent text-accent-foreground"
      aria-hidden="true"
    >
      <Icon name="sparkles" size="lg" />
    </span>

    <h2 className="text-center font-serif text-[clamp(1.6rem,3vw,2.4rem)] font-normal tracking-[-0.03em]">
      How can I help, {greetingName}?
    </h2>
    <p className="mt-3 max-w-lg text-center text-sm leading-relaxed text-foreground-muted">
      Ask about a governed metric, an Investigation, or what is waiting on your judgment. Every
      answer is traceable to the evidence behind it.
    </p>

    <div className="mt-10 grid w-full max-w-2xl gap-3 sm:grid-cols-2">
      {suggestions.map((suggestion) => (
        <button
          key={suggestion.suggestion_id}
          type="button"
          onClick={() => onChoose(suggestion.prompt)}
          className="flex flex-col gap-2 rounded-sm border border-border bg-card p-4 text-left transition-colors hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
        >
          <span className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-primary">
            <Icon name={suggestion.icon} size="sm" />
            {suggestion.label}
          </span>
          <span className="text-sm text-foreground-muted">{suggestion.prompt}</span>
        </button>
      ))}
    </div>
  </div>
);
