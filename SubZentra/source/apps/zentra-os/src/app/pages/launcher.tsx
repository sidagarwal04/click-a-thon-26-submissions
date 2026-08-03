import { useState } from 'react';

import { Button } from '@open-zentra/foundation-design-system';
import { useMutation, useQuery } from '@tanstack/react-query';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';

import { requestJson, type TokenSource } from '../api';
import type { CatalogSummary, IdentityContext, Investigation } from '../types';

interface LauncherProps {
  readonly getToken: TokenSource;
  readonly identity: IdentityContext;
}

/** How many governed members to name before the list stops being orienting. */
const SHOWN_MEMBERS = 8;

const readable = (member: string): string =>
  (member.includes('.') ? member.slice(member.indexOf('.') + 1) : member)
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .toLowerCase();

/**
 * Ask this tenant's data a question.
 *
 * This was a fixed list of two governed questions the deployment would answer.
 * A question is free text now (ADR-0023), so what the page owes the user is no
 * longer a menu but an orientation: the vocabulary their own data actually
 * carries, read from `/v1/catalog`.
 */
export const Launcher = ({ getToken, identity }: LauncherProps) => {
  const navigate = useNavigate();
  const [question, setQuestion] = useState('');

  const catalog = useQuery({
    queryKey: ['catalog'],
    queryFn: () => requestJson<CatalogSummary>('/v1/catalog', getToken),
    staleTime: 5 * 60 * 1000,
  });

  const mutation = useMutation({
    mutationFn: (asked: string) =>
      requestJson<Investigation>('/v1/investigations', getToken, {
        method: 'POST',
        body: JSON.stringify({ question: asked }),
      }),
    onSuccess: (investigation) =>
      navigate(`/investigations/${investigation.investigation_id}`, {
        state: { investigation },
      }),
  });

  const isViewer = identity.role === 'viewer';
  const trimmed = question.trim();
  const members = [
    ...(catalog.data?.measures ?? []),
    ...(catalog.data?.dimensions ?? []),
  ].slice(0, SHOWN_MEMBERS);

  return (
    <section className="px-8 py-10">
      <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em]">
        <span className="text-foreground-muted">Evidence inquiries</span>
        <span className="text-primary">Your governed data</span>
      </div>

      <form
        className="mt-10 max-w-4xl"
        onSubmit={(event) => {
          event.preventDefault();
          if (trimmed) mutation.mutate(trimmed);
        }}
      >
        <label
          className="font-mono text-xs tracking-[0.2em] text-foreground-muted"
          htmlFor="launcher-question"
        >
          ASK
        </label>
        <motion.textarea
          id="launcher-question"
          className="mt-3 w-full resize-none border-0 border-b border-border bg-transparent pb-4 font-serif text-[clamp(1.5rem,3.2vw,2.5rem)] font-normal leading-[1.15] tracking-[-0.035em] outline-none focus:border-primary"
          layoutId="investigation-question"
          rows={2}
          value={question}
          placeholder="Why did refunds increase last month?"
          disabled={isViewer || mutation.isPending}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            // Enter asks; Shift+Enter is a newline. A question is usually one
            // line, and reaching for the button every time gets old.
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              if (trimmed) mutation.mutate(trimmed);
            }
          }}
        />

        <Button
          className="mt-7"
          size="lg"
          type="submit"
          loading={mutation.isPending}
          disabled={isViewer || mutation.isPending || !trimmed}
        >
          {isViewer ? 'Viewer access · read only' : 'Begin evidence trace'}
        </Button>
      </form>

      {members.length > 0 ? (
        <div className="mt-10 max-w-4xl">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
            Your data can answer about
          </span>
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
            {members.map((member) => (
              <span className="flex items-center gap-2" key={member.name}>
                <i className="h-1 w-1 rounded-full bg-primary" aria-hidden="true" />
                {readable(member.name)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {catalog.error ? (
        <p className="mt-8 text-sm text-danger" role="alert">
          {catalog.error.message}
        </p>
      ) : null}
      {mutation.error ? (
        <p className="mt-8 text-sm text-danger" role="alert">
          {mutation.error.message}
        </p>
      ) : null}

      <div className="mt-16 flex items-center gap-4 border-t border-border pt-5">
        <span className="h-1 w-1 rounded-full bg-primary" aria-hidden="true" />
        <strong className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-foreground-muted">
          Every claim rechecked before you see it
        </strong>
      </div>
    </section>
  );
};
