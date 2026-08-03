/// <reference types="vitest/globals" />
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import type { IdentityContext, Thread, VisualizationBrief } from '../../types';
import { ChatPage } from './chat-page';
import { toTimeline } from './to-chat-message';

// The Thesys renderer is a third-party generative-UI SDK; the wiring under
// test is which branch VisualizationAnswer takes and what it hands the
// renderer, not Thesys's own rendering, so the module is replaced with a
// stand-in that surfaces its props for assertions.
vi.mock('./c1-answer', () => ({
  default: ({ c1Response }: { c1Response: string }) => (
    <div data-testid="c1-answer">{c1Response}</div>
  ),
}));

const getToken = async () => 'test-token';

const identity: IdentityContext = {
  user_id: '10000000-0000-0000-0000-000000000001',
  tenant_id: '20000000-0000-0000-0000-000000000002',
  email: 'owner@example.com',
  tenant_name: 'Acme Europe',
  role: 'owner',
};

const GROUP = {
  group_id: '41000000-0000-0000-0000-000000000001',
  name: 'Workspace',
  created_at: '2026-08-01T09:00:00Z',
  updated_at: '2026-08-01T09:00:00Z',
  archived_at: null,
  can_manage: true,
};

const PROJECT = {
  project_id: '42000000-0000-0000-0000-000000000001',
  group_id: GROUP.group_id,
  name: 'General',
  created_at: '2026-08-01T09:00:00Z',
  updated_at: '2026-08-01T09:00:00Z',
  latest_activity_at: '2026-08-01T09:00:00Z',
  archived_at: null,
  can_manage: true,
};

const USAGE = {
  input_tokens: 0,
  output_tokens: 0,
  total_cost_usd: '0',
  latency_ms: 0,
};

const ACTIONS = {
  can_append_message: true,
  can_archive: true,
  can_restore: false,
  can_delete: true,
  can_cancel: false,
  can_retry: false,
};

const clarifiedThread: Thread = {
  thread_id: '43000000-0000-0000-0000-000000000001',
  project_id: PROJECT.project_id,
  title: 'How is the business doing?',
  status: 'draft',
  created_at: '2026-08-01T09:00:00Z',
  updated_at: '2026-08-01T09:00:00Z',
  latest_activity_at: '2026-08-01T09:00:00Z',
  messages: [
    {
      message_id: '44000000-0000-0000-0000-000000000001',
      kind: 'user_question',
      content: 'How is the business doing?',
      created_at: '2026-08-01T09:00:00Z',
      authored_by_user: true,
    },
    {
      message_id: '44000000-0000-0000-0000-000000000002',
      kind: 'router_clarification',
      content: 'I could not map that message to a governed question.',
      created_at: '2026-08-01T09:00:01Z',
      authored_by_user: false,
    },
  ],
  investigation_id: null,
  investigations: [],
  event_cursor: 2,
  usage: USAGE,
  routing: {
    disposition: 'unsupported',
    scenario_key: null,
    canonical_question: null,
    clarification: 'I could not map that message to a governed question.',
    suggestions: ['Why did EU refunds increase from June to July 2026?'],
  },
  actions: ACTIONS,
};

/**
 * Answer each endpoint by URL, so ordering between them cannot matter.
 *
 * Keyed by method as well as path, because `/projects/{id}/threads` lists on
 * GET and creates on POST, and those return different shapes.
 */
const route = (handlers: Record<string, { status?: number; body: unknown }>) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    const method = (init?.method ?? 'GET').toUpperCase();
    const key = Object.keys(handlers)
      // Longest fragment wins, so '/threads' cannot shadow '/threads/{id}'.
      .sort((a, b) => b.length - a.length)
      .find((fragment) => {
        const [wanted, path] = fragment.includes(' ') ? fragment.split(' ') : [method, fragment];
        return wanted === method && url.includes(path);
      });
    const handler = key ? handlers[key] : undefined;
    if (!handler) throw new Error(`unhandled ${method}: ${url}`);
    return {
      ok: (handler.status ?? 200) < 400,
      status: handler.status ?? 200,
      // The work feed is read as a stream, never as JSON.
      body: { getReader: () => ({ read: async () => ({ done: true }) }) },
      json: async () => handler.body,
    } as unknown as Response;
  });

const baseRoutes = {
  '/v1/groups': { body: { items: [GROUP], next_cursor: null } },
  [`/v1/groups/${GROUP.group_id}/projects`]: {
    body: { items: [PROJECT], next_cursor: null },
  },
  '/v1/agents': { body: [] },
  '/v1/catalog': {
    body: {
      measures: [
        {
          name: 'Commerce.refundAmount',
          type: 'number',
          description: 'Value refunded to customers',
          values: [],
        },
      ],
      dimensions: [
        { name: 'Commerce.orderedAt', type: 'time', description: null, values: [] },
      ],
    },
  },
  [`GET /v1/projects/${PROJECT.project_id}/threads`]: {
    body: { items: [], next_cursor: null },
  },
};

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ChatPage getToken={getToken} identity={identity} />
      </QueryClientProvider>
    </MemoryRouter>,
  );
};

/** Type into the composer once the workspace has resolved and it is live. */
const ask = async (question: string) => {
  const composer = await screen.findByRole('textbox');
  await waitFor(() => expect(composer.hasAttribute('disabled')).toBe(false));
  await userEvent.type(composer, `${question}{Enter}`);
  return composer;
};

beforeEach(() => {
  vi.restoreAllMocks();
  // jsdom implements no layout, so it has no scrolling either.
  Element.prototype.scrollIntoView = () => undefined;
});

describe('Chat', () => {
  it('builds empty-thread suggestions from this tenant\'s own catalog', async () => {
    route(baseRoutes);
    renderPage();

    // The measure's description labels the card, and the prompt names the
    // measure — neither is copy written into the bundle.
    expect(
      await screen.findByText('Value refunded to customers'),
    ).toBeTruthy();
    expect(screen.getByText(/refund amount/i)).toBeTruthy();
  });

  it('creates a thread from the first message and renders the snapshot', async () => {
    route({
      ...baseRoutes,
      [`POST /v1/projects/${PROJECT.project_id}/threads`]: { body: clarifiedThread },
      [`/v1/threads/${clarifiedThread.thread_id}`]: { body: clarifiedThread },
    });
    renderPage();

    await ask('How is the business doing?');

    expect(
      await screen.findByText('I could not map that message to a governed question.'),
    ).toBeTruthy();
  });

  it('offers the supported questions when the router could not resolve one', async () => {
    route({
      ...baseRoutes,
      [`POST /v1/projects/${PROJECT.project_id}/threads`]: { body: clarifiedThread },
      [`/v1/threads/${clarifiedThread.thread_id}`]: { body: clarifiedThread },
    });
    renderPage();

    await ask('How is the business doing?');

    expect(
      await screen.findByRole('button', {
        name: 'Why did EU refunds increase from June to July 2026?',
      }),
    ).toBeTruthy();
  });

  it('closes the composer when the server says a follow-up is not yet legal', async () => {
    const running: Thread = {
      ...clarifiedThread,
      actions: { ...ACTIONS, can_append_message: false, can_cancel: true },
    };
    route({
      ...baseRoutes,
      [`POST /v1/projects/${PROJECT.project_id}/threads`]: { body: running },
      [`/v1/threads/${running.thread_id}`]: { body: running },
    });
    renderPage();

    await ask('How is the business doing?');

    await waitFor(() => expect(screen.getByRole('textbox').hasAttribute('disabled')).toBe(true));
  });

  it('explains a workspace it may not provision rather than looping on 403', async () => {
    route({
      ...baseRoutes,
      '/v1/groups': { status: 403, body: { code: 'permission_denied' } },
    });
    renderPage();

    expect(await screen.findByRole('alert')).toBeTruthy();
  });
});

describe('toTimeline', () => {
  const thread = (over: Partial<Thread>): Thread => ({ ...clarifiedThread, ...over });
  const investigations = (...ids: string[]) =>
    ids.map((investigation_id) => ({
      investigation_id,
    })) as unknown as Thread['investigations'];

  it('derives the role from who authored the message', () => {
    const [question, clarification] = toTimeline(clarifiedThread);
    expect(question.kind === 'message' && question.message.role).toBe('user');
    expect(clarification.kind === 'message' && clarification.message.role).toBe('assistant');
  });

  it('renders an answer the server never sent as a message', () => {
    // A resolved Thread holds only the question; the answer is on the
    // Investigation. Rendering messages alone would show nothing.
    const answered = thread({
      messages: [clarifiedThread.messages[0]],
      routing: null,
      investigations: investigations('i-1'),
    });

    const timeline = toTimeline(answered);
    expect(timeline.map((entry) => entry.kind)).toEqual(['message', 'answer']);
    expect(timeline[1].kind === 'answer' && timeline[1].investigation.investigation_id).toBe('i-1');
  });

  it('never gives a clarified question an answer', () => {
    const timeline = toTimeline(thread({ investigations: investigations('i-1') }));
    expect(timeline.some((entry) => entry.kind === 'answer')).toBe(false);
  });

  it('keeps each answer beside the question that produced it', () => {
    const followUp = thread({
      messages: [
        clarifiedThread.messages[0],
        {
          message_id: 'm-2',
          kind: 'user_question',
          content: 'And in August?',
          created_at: '2026-08-01T09:05:00Z',
          authored_by_user: true,
        },
      ],
      routing: null,
      investigations: investigations('i-1', 'i-2'),
    });

    const timeline = toTimeline(followUp);
    expect(timeline.map((entry) => entry.id)).toEqual([
      clarifiedThread.messages[0].message_id,
      'i-1',
      'm-2',
      'i-2',
    ]);
  });
});

describe('the brief a reader falls back to', () => {
  const brief: VisualizationBrief = {
    schema_version: '1.0',
    investigation_id: 'i-1',
    question: 'Why did EU refunds increase?',
    headline: 'EU refunds rose 12%',
    summary: 'Refunds increased across both months.',
    view: 'bar',
    metrics: [
      {
        label: 'refund_rate',
        exact_value: '0.12',
        display_value: '12 %',
        unit: '%',
        direction: 'up',
        citation_ids: ['c-1'],
      },
    ],
    comparisons: [],
    time_range: { start_label: 'June', end_label: 'July' },
    series: [
      {
        label: 'refund_rate',
        dimensions: [],
        unit: '%',
        points: [
          {
            position: 0,
            label: 'June',
            exact_value: '0.10',
            display_value: '10 %',
            citation_ids: ['c-1'],
          },
          {
            position: 1,
            label: 'July',
            exact_value: '0.12',
            display_value: '12 %',
            citation_ids: ['c-1'],
          },
        ],
      },
    ],
    claims: [{ kind: 'observed', text: 'Refunds rose.', citation_ids: ['c-1'] }],
    caveats: [],
    outcome_kind: 'confidence',
    confidence: 0.8,
    actions: [],
  };

  const withVisualization = (over: Record<string, unknown>) => {
    const answered: Thread = {
      ...clarifiedThread,
      messages: [
        clarifiedThread.messages[0],
        {
          message_id: 'm-2',
          kind: 'agent_answer',
          content: 'Refunds rose.',
          created_at: '2026-08-01T09:00:02Z',
          authored_by_user: false,
        },
      ],
      investigation_id: 'i-1',
      investigations: [{ investigation_id: 'i-1' }] as unknown as Thread['investigations'],
    };
    route({
      ...baseRoutes,
      [`POST /v1/projects/${PROJECT.project_id}/threads`]: { body: answered },
      [`/v1/threads/${answered.thread_id}`]: { body: answered },
      '/visualization': {
        body: {
          visualization_id: 'v-1',
          investigation_id: 'i-1',
          renderer_kind: 'thesys_c1',
          model: null,
          api_version: null,
          c1_response: null,
          input_tokens: 0,
          output_tokens: 0,
          cost_usd: '0',
          latency_ms: 0,
          failure_category: null,
          retry_of_visualization_id: null,
          fallback_brief: brief,
          created_at: '2026-08-01T09:00:00Z',
          updated_at: '2026-08-01T09:00:00Z',
          erased_at: null,
          erasure_category: null,
          ...over,
        },
      },
    });
  };

  it('carries the whole answer when the renderer produced nothing', async () => {
    withVisualization({ status: 'failed', failure_category: 'renderer_unavailable' });
    renderPage();

    await ask('Why did EU refunds increase?');

    expect(await screen.findByText('EU refunds rose 12%')).toBeTruthy();
    // Once in the agent's own message, once as a cited claim in the brief.
    expect(screen.getAllByText('Refunds rose.')).toHaveLength(2);
    // The metric and the claim each cite the same measurement.
    expect(screen.getAllByLabelText('Open supporting evidence 1')).toHaveLength(2);
    // The chart restates the same two governed points, and the current one
    // also stands alone as a metric card.
    expect(screen.getByText('10 %')).toBeTruthy();
    expect(screen.getAllByText('12 %')).toHaveLength(2);
    expect(screen.getByRole('img', { name: 'June: 10 %, July: 12 %' })).toBeTruthy();
    // A failed render is the one state a reader can act on.
    expect(await screen.findByRole('button', { name: 'Render again' })).toBeTruthy();
  });

  it('says why it is showing the brief while a render is still pending', async () => {
    withVisualization({ status: 'pending' });
    renderPage();

    await ask('Why did EU refunds increase?');

    expect(await screen.findByText(/Preparing the rendered view/, { exact: false })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Render again' })).toBeFalsy();
  });

  it('says why it is showing the brief while the renderer is still generating', async () => {
    withVisualization({ status: 'generating' });
    renderPage();

    await ask('Why did EU refunds increase?');

    expect(await screen.findByText(/Preparing the rendered view/, { exact: false })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Render again' })).toBeFalsy();
  });

  it('says the rendered view was erased when the visualization is tombstoned', async () => {
    withVisualization({ status: 'tombstoned' });
    renderPage();

    await ask('Why did EU refunds increase?');

    expect(await screen.findByText(/rendered view was erased/, { exact: false })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Render again' })).toBeFalsy();
  });

  it('renders what Thesys produced once a render is ready, not the brief fallback', async () => {
    withVisualization({ status: 'ready', c1_response: 'RENDERED_EU_REFUND_VIEW' });
    renderPage();

    await ask('Why did EU refunds increase?');

    expect((await screen.findByTestId('c1-answer')).textContent).toBe('RENDERED_EU_REFUND_VIEW');
    // The renderer's own output stands alone; the verified brief underneath
    // it is not also shown once a render exists.
    expect(screen.queryByText('10 %')).toBeFalsy();
    expect(screen.queryByRole('button', { name: 'Render again' })).toBeFalsy();
  });
});
