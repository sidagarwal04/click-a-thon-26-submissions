import { Icon } from '@open-zentra/foundation-icons';

import { Markdown } from '../../components/markdown';
import type { ChatMessage } from '../../types';

/**
 * One message in the conversation.
 *
 * The question is shown as written — plain text in a bubble. A published answer
 * is *not* a message and is not rendered here; it lives on the Investigation
 * and is rendered by `AnswerRow`.
 *
 * That leaves the `router_clarification`: the server saying it could not map
 * the question to governed work. It is rendered with the supported questions as
 * chips, because telling someone "no" without telling them what "yes" looks
 * like is a dead end.
 */
export const ChatMessageRow = ({
  message,
  suggestions,
  onChoose,
}: {
  readonly message: ChatMessage;
  /** Supported canonical questions, present only on a clarification. */
  readonly suggestions: readonly string[];
  readonly onChoose: (prompt: string) => void;
}) => {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-2xl whitespace-pre-wrap rounded-sm border border-border bg-background-muted px-4 py-3 text-sm text-foreground">
          {message.content}
        </p>
      </div>
    );
  }

  const clarification = message.kind === 'router_clarification';

  return (
    <div className="flex gap-4">
      <span
        className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-sm bg-accent text-accent-foreground"
        aria-hidden="true"
      >
        <Icon name={clarification ? 'help_circle' : 'sparkles'} size="sm" />
      </span>

      <div className="min-w-0 flex-1">
        <Markdown>{message.content}</Markdown>

        {clarification && suggestions.length > 0 ? (
          <ul className="mt-4 flex list-none flex-wrap gap-2 p-0">
            {suggestions.map((prompt) => (
              <li key={prompt}>
                <button
                  type="button"
                  className="cursor-pointer rounded-sm border border-border bg-background px-3 py-1.5 text-left text-sm text-foreground-muted transition-colors hover:bg-secondary hover:text-foreground"
                  onClick={() => onChoose(prompt)}
                >
                  {prompt}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
};
