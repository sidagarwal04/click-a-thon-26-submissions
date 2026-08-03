import { useEffect, useMemo, useRef, useState } from 'react';

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { requestJson, type TokenSource } from '../../api';
import type { CatalogSummary, IdentityContext, ThreadEvent } from '../../types';
import { AgentProgress } from './agent-progress';
import { AnswerRow } from './answer-row';
import { appendMessage, createThread, getThread, listAgents, listThreads } from './api';
import { ChatComposer } from './chat-composer';
import { ChatEmptyState } from './chat-empty-state';
import { ChatHistory } from './chat-history';
import { ChatMessageRow } from './chat-message-row';
import { suggestionsFromCatalog } from './chat-suggestions';
import { InvestigationControls } from './investigation-controls';
import { latestInvestigation, toTimeline } from './to-chat-message';
import { useActiveProject } from './use-active-project';
import { useThreadEvents } from './use-thread-events';

/** The composer is open but no Thread exists yet — the first message makes one. */
const NEW_THREAD = null;

/**
 * The conversational surface.
 *
 * The shape of the loop is the one the Thread API asks for: read the snapshot,
 * then tail the Work Feed from the cursor it hands over. The stream drives
 * *progress* — which agent is working, what it just said — and the snapshot
 * remains the only source of *content*. That split is deliberate. An event
 * cannot be un-received, so treating the feed as state would mean a dropped
 * connection silently changing what the reader believes.
 */
export const ChatPage = ({
  identity,
  getToken,
}: {
  readonly identity: IdentityContext;
  readonly getToken: TokenSource;
}) => {
  const queryClient = useQueryClient();
  const [activeThreadId, setActiveThreadId] = useState<string | null>(NEW_THREAD);
  const [draft, setDraft] = useState('');
  const endOfThread = useRef<HTMLDivElement>(null);

  const project = useActiveProject(getToken);
  const projectId = project.data ?? null;

  const history = useInfiniteQuery({
    queryKey: ['threads', projectId],
    queryFn: ({ pageParam }) => listThreads(getToken, projectId as string, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor,
    enabled: Boolean(projectId),
  });

  const snapshot = useQuery({
    queryKey: ['thread', activeThreadId],
    queryFn: () => getThread(getToken, activeThreadId as string),
    enabled: Boolean(activeThreadId),
  });

  const agents = useQuery({
    queryKey: ['agents'],
    queryFn: () => listAgents(getToken),
    staleTime: 5 * 60 * 1000,
  });

  const catalog = useQuery({
    queryKey: ['catalog'],
    queryFn: () => requestJson<CatalogSummary>('/v1/catalog', getToken),
    staleTime: 5 * 60 * 1000,
  });

  const thread = snapshot.data ?? null;

  // A finished Finding, a rendered view, or a decided approval all mean the
  // snapshot is now behind what the feed already knows. Refetch rather than
  // patch: the server's version of the Thread is the one that counts.
  const onEvent = (event: ThreadEvent) => {
    const settles =
      event.kind === 'finding.published' ||
      event.kind === 'approval.requested' ||
      event.kind === 'approval.decided' ||
      event.kind === 'thread.message_added' ||
      event.kind === 'thread.routing_clarification' ||
      event.kind === 'thread.routing_resolved' ||
      event.kind.startsWith('visualization.') ||
      event.kind.startsWith('investigation.');
    if (!settles) return;
    void queryClient.invalidateQueries({ queryKey: ['thread', event.thread_id] });
    if (event.kind === 'visualization.completed' || event.kind === 'visualization.failed') {
      void queryClient.invalidateQueries({ queryKey: ['visualization'] });
    }
  };

  const feed = useThreadEvents(getToken, activeThreadId, thread?.event_cursor ?? 0, onEvent);

  const send = useMutation({
    mutationFn: (content: string) =>
      activeThreadId
        ? appendMessage(getToken, activeThreadId, content)
        : createThread(getToken, projectId as string, content),
    onSuccess: (created) => {
      setActiveThreadId(created.thread_id);
      queryClient.setQueryData(['thread', created.thread_id], created);
      void queryClient.invalidateQueries({ queryKey: ['threads', projectId] });
    },
  });

  const timeline = useMemo(() => (thread ? toTimeline(thread) : []), [thread]);

  useEffect(() => {
    endOfThread.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [timeline.length, feed.events.length]);

  const submit = (content: string) => {
    setDraft('');
    send.mutate(content);
  };

  const threads = history.data?.pages.flatMap((page) => page.items) ?? [];
  const investigation = thread ? latestInvestigation(thread) : null;
  // Before a Thread exists there is nothing to forbid; afterwards the server
  // says when a follow-up is legal, and it is the only thing that says so.
  const canSend = thread ? thread.actions.can_append_message : Boolean(projectId);

  if (project.error) {
    return (
      <section className="flex h-full items-center justify-center px-6">
        <p className="max-w-md text-sm text-foreground-muted" role="alert">
          {project.error.message}
        </p>
      </section>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      <ChatHistory
        threads={threads}
        activeThreadId={activeThreadId}
        loading={history.isFetching}
        onLoadMore={history.hasNextPage ? () => void history.fetchNextPage() : null}
        onSelect={(threadId) => {
          setActiveThreadId(threadId);
          setDraft('');
        }}
        onNewChat={() => {
          setActiveThreadId(NEW_THREAD);
          setDraft('');
        }}
      />

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-baseline gap-x-4 gap-y-2 border-b border-border px-6 py-5">
          <h1 className="font-serif text-2xl font-normal tracking-[-0.03em]">
            {thread?.title ?? 'Chat'}
          </h1>
          <p className="w-full text-sm text-foreground-muted">
            Ask a governed question and follow the evidence trace it produces.
          </p>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {timeline.length === 0 ? (
            <ChatEmptyState
              greetingName={identity.email.split('@')[0]}
              suggestions={suggestionsFromCatalog(catalog.data ?? null)}
              onChoose={setDraft}
            />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-8">
              {timeline.map((entry) =>
                entry.kind === 'message' ? (
                  <ChatMessageRow
                    key={entry.id}
                    message={entry.message}
                    suggestions={thread?.routing?.suggestions ?? []}
                    onChoose={setDraft}
                  />
                ) : (
                  <AnswerRow
                    key={entry.id}
                    investigation={entry.investigation}
                    getToken={getToken}
                    onFollowUp={submit}
                  />
                ),
              )}

              <AgentProgress events={feed.events} status={feed.status} agents={agents.data ?? []} />

              {thread && investigation ? (
                <InvestigationControls
                  getToken={getToken}
                  thread={thread}
                  investigation={investigation}
                />
              ) : null}

              {send.error ? (
                <p className="text-sm text-danger" role="alert">
                  {send.error.message}
                </p>
              ) : null}

              <div ref={endOfThread} />
            </div>
          )}
        </div>

        <ChatComposer
          draft={draft}
          onDraftChange={setDraft}
          onSend={submit}
          disabled={send.isPending || !canSend}
        />
      </section>
    </div>
  );
};
