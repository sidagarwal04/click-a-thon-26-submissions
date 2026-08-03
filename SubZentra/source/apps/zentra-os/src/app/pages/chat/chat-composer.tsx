import { useState, type FormEvent, type KeyboardEvent } from 'react';

import { Button, IconButton } from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';

interface ChatComposerProps {
  readonly onSend: (message: string) => void;
  readonly disabled: boolean;
  /** Prefilled from a suggestion card. */
  readonly draft: string;
  readonly onDraftChange: (draft: string) => void;
}

/**
 * The message box.
 *
 * Enter sends and Shift+Enter breaks the line — the convention a chat surface
 * is judged by. The attachment controls are drawn but disabled: they say what
 * is coming without pretending to work.
 */
export const ChatComposer = ({ onSend, disabled, draft, onDraftChange }: ChatComposerProps) => {
  const [rows, setRows] = useState(1);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const message = draft.trim();
    if (!message || disabled) return;
    onSend(message);
    setRows(1);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      className="border-t border-border bg-card px-6 py-4"
      onSubmit={submit}
      aria-label="Send a message"
    >
      <div className="flex flex-col gap-3 rounded-sm border border-border bg-background p-3 focus-within:border-primary">
        <label className="sr-only" htmlFor="chat-message">
          Message
        </label>
        <textarea
          id="chat-message"
          className="max-h-48 w-full resize-none bg-transparent text-sm text-foreground outline-none placeholder:text-foreground-muted disabled:cursor-not-allowed"
          rows={rows}
          value={draft}
          // `submit` refuses while disabled either way. Saying so on the box
          // itself is the difference between a surface that declines and one
          // that lets someone type an answer it was never going to accept.
          disabled={disabled}
          placeholder={
            disabled
              ? 'Waiting for the current investigation to finish…'
              : 'Ask a governed question…'
          }
          onKeyDown={handleKeyDown}
          onChange={(event) => {
            onDraftChange(event.target.value);
            setRows(Math.min(6, event.target.value.split('\n').length));
          }}
        />

        <div className="flex items-center gap-1">
          <IconButton aria-label="Attach a file" intent="ghost" size="sm" disabled>
            <Icon name="clipboard" size="sm" />
          </IconButton>
          <IconButton aria-label="Mention a dataset" intent="ghost" size="sm" disabled>
            <Icon name="tag" size="sm" />
          </IconButton>
          <IconButton aria-label="Attach an image" intent="ghost" size="sm" disabled>
            <Icon name="image" size="sm" />
          </IconButton>

          <Button
            className="ml-auto"
            type="submit"
            size="sm"
            disabled={disabled || draft.trim().length === 0}
            end={<Icon name="send" size="sm" />}
          >
            Send
          </Button>
        </div>
      </div>

      <p className="mt-3 text-center font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
        Answers are drafts · every claim is rechecked before it becomes a Finding
      </p>
    </form>
  );
};
