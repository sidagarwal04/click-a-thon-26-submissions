/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig } from 'motion/react';
import { MemoryRouter } from 'react-router-dom';

import App from './app';

const authMocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useAuthSession: vi.fn(),
}));

vi.mock('@open-zentra/foundation-auth', () => authMocks);

const readyResponse = {
  status: 'ready',
  dependencies: {
    postgres: { status: 'ready' },
    clickhouse: { status: 'ready' },
    cube: { status: 'ready' },
  },
};

const contextResponse = {
  user_id: '10000000-0000-0000-0000-000000000001',
  tenant_id: '20000000-0000-0000-0000-000000000002',
  email: 'owner@example.com',
  tenant_name: 'Acme Europe',
  role: 'owner',
};

const investigation = {
  investigation_id: '30000000-0000-0000-0000-000000000003',
  canonical_question: 'Why did EU refunds increase from June to July 2026?',
  scenario_key: null,
  status: 'awaiting_approval',
  version: 5,
  evaluation_attempts: 1,
  created_at: '2026-07-29T00:00:00Z',
  updated_at: '2026-07-29T00:00:00Z',
  finished_at: null,
  finding: {
    headline: 'EU refunds rose $240 in July',
    summary:
      'Governed EU refund amount increased while order volume remained flat.',
    metrics: [
      {
        metric: 'refund_amount',
        previous_value: '20.00',
        previous_label: 'June 2026',
        current_value: '260.00',
        current_label: 'July 2026',
        unit: 'USD',
      },
      {
        metric: 'refund_rate',
        previous_value: '25',
        previous_label: null,
        current_value: '75',
        current_label: null,
        unit: 'percent',
      },
    ],
    evidence_references: [
      'artifact://semantic/eu-refund-spike/2026-06_2026-07',
    ],
  },
  // Legacy by default: every Investigation that ran before Insight has a
  // narrative Finding and no structured draft.
  draft_finding: null,
  outcome: {
    kind: 'confidence',
    score: 0.42,
    calibration_method: 'evaluator_independent_recheck',
  },
  pending_approval: {
    approval_id: '40000000-0000-0000-0000-000000000004',
    reason: 'low_confidence',
    requested_at: '2026-07-29T00:00:00Z',
    can_decide: true,
    failed_conditions: ['confident'],
  },
  timeline: [
    {
      entry_id: '50000000-0000-0000-0000-000000000005',
      event_type: 'investigation.created',
      status: 'pending',
      created_at: '2026-07-29T00:00:00Z',
      artifact_references: [],
      delivery: 'complete',
      agent_id: null,
      step: null,
      model: null,
      fallbacks: [],
      failed_conditions: [],
      latency_ms: null,
      total_cost_usd: null,
    },
    {
      entry_id: '50000000-0000-0000-0000-000000000007',
      event_type: 'agent.execution_completed',
      status: 'running',
      created_at: '2026-07-29T00:00:01Z',
      artifact_references: ['artifact://execution/60000000-0000-0000-0000-000000000006'],
      delivery: 'complete',
      agent_id: 'cube_analyst_v1',
      step: 2,
      model: 'cerebras/zai-glm-4.7',
      fallbacks: ['gemini/gemini-3.6-flash: circuit open'],
      failed_conditions: [],
      latency_ms: 1240,
      total_cost_usd: '0.0012',
    },
    {
      entry_id: '50000000-0000-0000-0000-000000000006',
      event_type: 'human_approval.requested',
      status: 'awaiting_approval',
      created_at: '2026-07-29T00:00:02Z',
      artifact_references: [],
      delivery: 'complete',
      agent_id: null,
      step: null,
      model: null,
      fallbacks: [],
      failed_conditions: [],
      latency_ms: null,
      total_cost_usd: null,
    },
  ],
  audit_delivery: 'complete',
} as const;

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const catalogResponse = {
  measures: [
    {
      name: 'Commerce.refundAmount',
      type: 'number',
      description: 'Value refunded to customers',
      values: [],
    },
  ],
  dimensions: [
    {
      name: 'Commerce.region',
      type: 'string',
      description: null,
      values: ['EU', 'NA'],
    },
  ],
};

const mockApi = (
  detail: unknown = investigation,
  citation?: { body: unknown; status?: number },
  context: unknown = contextResponse,
) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, options) => {
    const url = String(input);
    if (url.endsWith('/health/ready')) return response(readyResponse);
    if (url.endsWith('/v1/context')) return response(context);
    if (url.endsWith('/v1/catalog')) return response(catalogResponse);
    if (url.endsWith('/v1/investigations') && options?.method === 'POST') {
      return response(detail, 201);
    }
    // Following a citation is its own Tenant-authorized read, so it gets its
    // own stub: a test can make it succeed, deny, or break independently of
    // the Investigation it hangs off.
    if (url.includes('/citations/')) {
      return citation
        ? response(citation.body, citation.status ?? 200)
        : response({ detail: 'Evidence was not found' }, 404);
    }
    if (url.includes('/v1/investigations/')) return response(detail);
    return response({ detail: 'Not found' }, 404);
  });

const renderApp = (path = '/') => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <QueryClientProvider client={queryClient}>
        <MotionConfig reducedMotion="always">
          <App clerkConfigured />
        </MotionConfig>
      </QueryClientProvider>
    </MemoryRouter>,
  );
};

describe('App', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    authMocks.useAuthSession.mockReturnValue({
      getAccessToken: vi.fn().mockResolvedValue('valid-token'),
    });
  });

  it('renders an explicit Clerk setup state', () => {
    const queryClient = new QueryClient();
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <App clerkConfigured={false} />
        </QueryClientProvider>
      </MemoryRouter>,
    );
    expect(
      screen.getByRole('heading', { name: /connect clerk/i }),
    ).toBeTruthy();
    // The only home for this state. It is a build-time branch on
    // VITE_CLERK_PUBLISHABLE_KEY, so a browser journey cannot reach it from an
    // e2e build that has a key — `example.spec.ts` asserted it until the
    // authenticated harness landed and made its premise false.
  });

  it('renders the signed-out observatory entry', () => {
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: false,
      isInitializing: false,
      login: vi.fn(),
    });
    renderApp();
    expect(
      screen.getByRole('heading', { name: /trust is the product/i }),
    ).toBeTruthy();
  });

  it('denies access without an active organization', () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: null,
      user: { email: 'owner@example.com' },
    });
    renderApp();
    expect(
      screen.getByRole('heading', { name: /select a clerk organization/i }),
    ).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('orients the launcher with this tenant\'s own catalog', async () => {
    const fetchMock = mockApi();
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: { id: 'org_123', name: 'Acme' },
      user: { email: 'owner@example.com' },
    });
    renderApp();
    expect(await screen.findByText('Acme Europe')).toBeTruthy();

    // Orientation comes from this tenant's own catalog, not from a question
    // hardcoded in this bundle or in a fixed server-side list.
    expect(await screen.findByText(/refund amount/i)).toBeTruthy();
    expect(screen.getByText(/region/i)).toBeTruthy();

    const asked = 'Why did EU refunds increase from June to July 2026?';
    fireEvent.change(screen.getByLabelText(/ask/i), {
      target: { value: asked },
    });
    fireEvent.click(screen.getByRole('button', { name: /begin evidence trace/i }));

    expect(
      await screen.findByRole('heading', {
        name: /eu refunds rose \$240 in july/i,
      }),
    ).toBeTruthy();

    const posted = fetchMock.mock.calls.find(
      ([, options]) => (options as RequestInit | undefined)?.method === 'POST',
    );
    expect(JSON.parse(String((posted?.[1] as RequestInit).body))).toEqual({
      question: asked,
    });
  });

  it('sends the question verbatim and refuses to send an empty one', async () => {
    const fetchMock = mockApi();
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: { id: 'org_123', name: 'Acme' },
      user: { email: 'owner@example.com' },
    });
    renderApp();
    const field = await screen.findByLabelText(/ask/i);
    const launch = screen.getByRole('button', { name: /begin evidence trace/i });

    // Nothing typed yet: there is no question to investigate.
    expect((launch as HTMLButtonElement).disabled).toBe(true);

    const asked = 'Which warehouse absorbed the October backlog?';
    fireEvent.change(field, { target: { value: `  ${asked}  ` } });
    fireEvent.click(screen.getByRole('button', { name: /begin evidence trace/i }));

    await waitFor(() => {
      const posted = fetchMock.mock.calls.find(
        ([, options]) => (options as RequestInit | undefined)?.method === 'POST',
      );
      // Trimmed, but otherwise exactly what was typed — no rewriting.
      expect(JSON.parse(String((posted?.[1] as RequestInit).body))).toEqual({
        question: asked,
      });
    });
  });

  it('shows persisted evidence and owner approval controls on refresh', async () => {
    mockApi();
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: { id: 'org_123', name: 'Acme' },
      user: { email: 'owner@example.com' },
    });
    renderApp(
      '/investigations/30000000-0000-0000-0000-000000000003',
    );
    // The approve control rather than the heading: the outcome panel and the
    // approval now legitimately share the policy's wording, so a heading query
    // matches both.
    expect(
      await screen.findByRole('button', { name: /approve finding/i }),
    ).toBeTruthy();
    expect(screen.getByText('Question registered')).toBeTruthy();
    expect(screen.getByRole('button', { name: /approve finding/i })).toBeTruthy();
    // The agent that produced each step is named on the timeline.
    expect(screen.getByText('Cube Analyst · step 2')).toBeTruthy();
    // The provider and model that actually served the step are named.
    expect(screen.getByText('cerebras/zai-glm-4.7')).toBeTruthy();
    // A score below the tenant threshold gates on low confidence, not policy.
    expect(screen.getByText('42%')).toBeTruthy();
    // Both the outcome panel and the approval say why, in the policy's own
    // words — that agreement is the point, not a duplicate.
    expect(
      screen.getAllByRole('heading', {
        name: /confidence below the tenant threshold/i,
      }),
    ).toHaveLength(2);
  });

  it('renders read-only approval state for a viewer', async () => {
    mockApi({
      ...investigation,
      pending_approval: { ...investigation.pending_approval, can_decide: false },
    });
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: { id: 'org_123', name: 'Acme' },
      user: { email: 'viewer@example.com' },
    });
    renderApp(
      '/investigations/30000000-0000-0000-0000-000000000003',
    );
    expect(
      await screen.findByText(/owner or admin judgment is required/i),
    ).toBeTruthy();
    expect(screen.queryByRole('button', { name: /approve finding/i })).toBeNull();
  });

  it('announces a completed terminal state after approval', async () => {
    const completed = {
      ...investigation,
      status: 'completed' as const,
      pending_approval: null,
      finished_at: '2026-07-29T00:00:02Z',
    };
    mockApi(completed);
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: { id: 'org_123', name: 'Acme' },
      user: { email: 'owner@example.com' },
    });
    renderApp(
      '/investigations/30000000-0000-0000-0000-000000000003',
    );
    await waitFor(() =>
      expect(screen.getByText('Approved and complete')).toBeTruthy(),
    );
    expect(screen.getByText('completed')).toBeTruthy();
  });

  it('mints a fresh token for every request rather than reusing one', async () => {
    // Clerk session tokens expire after 60 seconds. Caching one in component
    // state meant a page left open sent a dead token on the next click, and the
    // API's "Invalid bearer token" read like a configuration fault.
    const getAccessToken = vi
      .fn()
      .mockResolvedValueOnce('token-1')
      .mockResolvedValueOnce('token-2')
      .mockResolvedValue('token-3');
    authMocks.useAuthSession.mockReturnValue({ getAccessToken });
    const fetchMock = mockApi();
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: { id: 'org_123', name: 'Acme' },
      user: { email: 'owner@example.com' },
    });

    renderApp();
    fireEvent.change(await screen.findByLabelText(/ask/i), {
      target: { value: 'Which sales channel grew fastest?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /begin evidence trace/i }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([, options]) => (options as RequestInit | undefined)?.method === 'POST',
        ),
      ).toBe(true),
    );

    // One call per authenticated request, not one for the whole session.
    expect(getAccessToken.mock.calls.length).toBeGreaterThan(1);
    const sent = fetchMock.mock.calls
      .map(([, options]) =>
        new Headers((options as RequestInit | undefined)?.headers).get(
          'Authorization',
        ),
      )
      .filter(Boolean);
    expect(new Set(sent).size).toBeGreaterThan(1);
  });

  it('captions a metric with the periods the metric itself reports', async () => {
    // Captions once read "June X -> July Y", hardcoded from the only scenario
    // that existed, and the first live run of the second scenario captioned an
    // October-to-November finding as June to July. So the labels here are
    // deliberately months this fixture's question does not mention: a caption
    // that still says June or July is reading something other than the data.
    mockApi({
      ...investigation,
      finding: {
        ...investigation.finding,
        metrics: [
          {
            metric: 'refund_amount',
            previous_value: '20.00',
            previous_label: 'October 2026',
            current_value: '260.00',
            current_label: 'November 2026',
            unit: 'USD',
          },
        ],
      },
    });
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: { id: 'org_123', name: 'Acme' },
      user: { email: 'owner@example.com' },
    });

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    const caption = screen.getByText(/20\.00 → November 2026 260\.00 USD/);
    expect(caption.textContent).toContain('October 2026');
    expect(caption.textContent).not.toMatch(/june|july/i);
  });

  it('captions no period when the metric names none', async () => {
    // A model may have no period to report, and the comparison may not be over
    // time at all. Showing nothing is correct; borrowing months from elsewhere
    // on the page is the original bug.
    mockApi();
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: { id: 'org_123', name: 'Acme' },
      user: { email: 'owner@example.com' },
    });

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    // refund_rate carries null labels in the fixture.
    const caption = screen.getByText(/25 → 75 percent/);
    expect(caption.textContent).not.toMatch(/june|july|2026/i);
  });

  const structuredDraft = {
    draft_finding_id: '70000000-0000-0000-0000-000000000001',
    version: 2,
    created_at: '2026-07-29T00:00:00Z',
    produced_by_execution_id: null,
    headline: 'EU refunds rose $240 in July',
    summary: 'Governed EU refund amount rose from $20 to $260.',
    claims: [
      {
        claim_id: '80000000-0000-0000-0000-000000000001',
        kind: 'observed',
        text: 'EU refund amount rose from $20.00 to $260.00.',
        position: 0,
        metric: 'refund_amount',
        value: '260.00',
        period: 'July 2026',
        citation_ids: ['cc000000-0000-0000-0000-000000000001'],
      },
      {
        claim_id: '80000000-0000-0000-0000-000000000002',
        kind: 'interpretation',
        text: 'The rise is concentrated in a single week.',
        position: 1,
        metric: null,
        value: null,
        period: null,
        citation_ids: [],
      },
    ],
    contradictions: [
      { detail: 'Recheck counted 8 rows, not 12.', resolved: false },
    ],
    root_cause: 'unresolved',
    confidence: { score: 0.42, calibration_method: 'capped_sample_size' },
    citations: [
      {
        citation_id: 'cc000000-0000-0000-0000-000000000001',
        metric: 'refund_amount',
        filters: [
          { member: 'Commerce.region', operator: 'equals', values: ['EU'] },
        ],
        period: 'July 2026',
        grain: 'month',
        producing_execution_id: '60000000-0000-0000-0000-000000000006',
        aggregate_value: '260.00',
        state: 'active',
      },
    ],
  };

  const signedIn = () => {
    authMocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      isInitializing: false,
      logout: vi.fn(),
      tenant: { id: 'org_123', name: 'Acme' },
      user: { email: 'owner@example.com' },
    });
  };

  it('says a legacy investigation predates structured claims', async () => {
    // Rendering nothing would read as "no evidence here", which is both
    // harsher and less true than "this one ran before claims were separable".
    mockApi();
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    expect(
      screen.getByText(/ran before claims were recorded separately/i),
    ).toBeTruthy();
    expect(screen.queryByText(/root cause unresolved/i)).toBeNull();
  });

  it('labels measured claims apart from interpreted ones', async () => {
    // The one distinction a reviewer most needs, carried as a visible word
    // rather than a colour — a reader who cannot tell the swatches apart
    // still gets it.
    mockApi({ ...investigation, draft_finding: structuredDraft });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    expect(screen.getByText('Measured')).toBeTruthy();
    expect(screen.getByText('Interpretation')).toBeTruthy();
    expect(
      screen.queryByText(/ran before claims were recorded separately/i),
    ).toBeNull();
  });

  it('renders claims in the order the draft recorded', async () => {
    mockApi({ ...investigation, draft_finding: structuredDraft });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    const claims = screen.getAllByRole('listitem').map((el) => el.textContent);
    const observed = claims.findIndex((t) => t?.includes('$260.00'));
    const interpreted = claims.findIndex((t) => t?.includes('single week'));
    expect(observed).toBeGreaterThanOrEqual(0);
    expect(observed).toBeLessThan(interpreted);
  });

  it('says root cause is unresolved out loud', async () => {
    // ADR 0011 turns on the product stating this rather than letting a reader
    // assume causality was established.
    mockApi({ ...investigation, draft_finding: structuredDraft });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    expect(screen.getByText(/root cause unresolved/i)).toBeTruthy();
  });

  it('surfaces an unresolved contradiction rather than smoothing it away', async () => {
    mockApi({ ...investigation, draft_finding: structuredDraft });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    // Twice, on purpose: once in the Draft Finding, once beside the
    // decision it bears on.
    expect(screen.getAllByText(/Recheck counted 8 rows, not 12\./)).toHaveLength(
      2,
    );
    expect(screen.getByText(/unresolved contradiction/i)).toBeTruthy();
  });

  it('offers an evidence affordance on every substantive claim', async () => {
    // A disclosure rather than a link: the reader is inspecting evidence, not
    // navigating away, and `<details>` is keyboard-operable and announced
    // without any scripting to get wrong.
    mockApi({ ...investigation, draft_finding: structuredDraft });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    const summaries = document.querySelectorAll('summary');
    expect(summaries).toHaveLength(1);
    // Named for the claim it belongs to, so a screen reader hearing several
    // "Evidence" toggles can tell them apart.
    expect(summaries[0].textContent).toContain('EU refund amount rose');
  });

  it('offers no evidence affordance on an interpretation', async () => {
    mockApi({ ...investigation, draft_finding: structuredDraft });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    // One disclosure, for the one observed claim. The interpretation has no
    // measurement of its own, so it has nothing to disclose.
    expect(document.querySelectorAll('summary')).toHaveLength(1);
  });

  const activeCitation = {
    citation_id: 'cc000000-0000-0000-0000-000000000001',
    metric: 'refund_amount',
    filters: [
      { member: 'Commerce.region', operator: 'equals', values: ['EU'] },
    ],
    period: 'July 2026',
    grain: 'month',
    producing_execution_id: '60000000-0000-0000-0000-000000000006',
    aggregate_value: '260.00',
    evaluator_outcome: null,
    state: 'active',
  };

  const openEvidence = async () => {
    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });
    // jsdom does not toggle `open` from a click on `summary`, so the state is
    // set the way a browser would and the event fired.
    const details = document.querySelector('details') as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event('toggle'));
  };

  it('shows the figure a measured claim rests on', async () => {
    // On the claim itself, without following anything.
    mockApi({ ...investigation, draft_finding: structuredDraft });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('heading', { name: /confidence below the tenant threshold/i, level: 2 });

    expect(screen.getByText('refund_amount')).toBeTruthy();
    expect(screen.getByText('260.00')).toBeTruthy();
    expect(screen.getByText('July 2026')).toBeTruthy();
  });

  it('resolves the governed context a citation carries', async () => {
    mockApi(
      { ...investigation, draft_finding: structuredDraft },
      { body: activeCitation },
    );
    signedIn();
    await openEvidence();

    expect(await screen.findByText('month')).toBeTruthy();
    expect(screen.getByText(/Commerce\.region equals EU/)).toBeTruthy();
  });

  it('says unavailable evidence is lost, not deleted', async () => {
    // A Tenant who erased something asked for that. A reader told "deleted"
    // about data loss is being reassured wrongly.
    mockApi(
      { ...investigation, draft_finding: structuredDraft },
      { body: { ...activeCitation, state: 'unavailable' } },
    );
    signedIn();
    await openEvidence();

    expect(await screen.findByText(/cannot currently be reached/i)).toBeTruthy();
    expect(screen.queryByText(/deleted/i)).toBeNull();
  });

  it('says evidence you may not see is not a failure', async () => {
    // 404 is the deliberate invisible-resource answer. Telling the reader the
    // system broke would be a different, and false, claim.
    mockApi({ ...investigation, draft_finding: structuredDraft });
    signedIn();
    await openEvidence();

    expect(await screen.findByText(/not available to you/i)).toBeTruthy();
    expect(screen.queryByText(/could not be loaded/i)).toBeNull();
  });

  it('says a server fault is a failure, not a permission problem', async () => {
    mockApi(
      { ...investigation, draft_finding: structuredDraft },
      { body: { detail: 'boom' }, status: 500 },
    );
    signedIn();
    await openEvidence();

    expect(await screen.findByText(/could not be loaded/i)).toBeTruthy();
    expect(screen.queryByText(/not available to you/i)).toBeNull();
  });

  it('announces resolution progress in a live region', async () => {
    mockApi(
      { ...investigation, draft_finding: structuredDraft },
      { body: activeCitation },
    );
    signedIn();
    await openEvidence();

    expect(document.querySelector('[aria-live="polite"]')).toBeTruthy();
  });

  it('lists every condition the policy found failing', async () => {
    // A reviewer told only the headline would be deciding on part of the
    // picture. The copy here used to describe one scenario's sample size
    // regardless of why the gate actually opened.
    mockApi({
      ...investigation,
      pending_approval: {
        ...investigation.pending_approval,
        reason: 'evidence_incomplete',
        failed_conditions: ['converged', 'confident', 'evidenced'],
      },
    });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('button', { name: /approve finding/i });

    expect(screen.getByText(/independent recheck did not agree/i)).toBeTruthy();
    expect(
      screen.getByText(/bounded confidence is below the tenant threshold/i),
    ).toBeTruthy();
    expect(
      screen.getByText(/no evidence that can be followed/i),
    ).toBeTruthy();
    // And the heading leads with the one that most stops a reviewer working.
    expect(
      screen.getAllByRole('heading', {
        name: /cannot be followed to its evidence/i,
      }).length,
    ).toBeGreaterThan(0);
  });

  const gated = (overrides = {}) => ({
    ...investigation,
    draft_finding: structuredDraft,
    pending_approval: { ...investigation.pending_approval, ...overrides },
  });

  it('shows what the decision turns on, beside the decision', async () => {
    // The Draft Finding panel is elsewhere on the page. A reviewer scrolling
    // back and forth between the decision and the evidence is a reviewer who
    // might not.
    mockApi(gated());
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('button', { name: /approve finding/i });

    expect(screen.getByText(/42% · capped sample size/i)).toBeTruthy();
    expect(screen.getByText('1 of 2')).toBeTruthy();
    expect(screen.getByText(/1 citations, all resolvable/i)).toBeTruthy();
    expect(
      screen.getAllByText(/Recheck counted 8 rows, not 12\./).length,
    ).toBeGreaterThan(0);
  });

  it('says when evidence cannot be followed, before the buttons', async () => {
    mockApi({
      ...gated(),
      draft_finding: {
        ...structuredDraft,
        citations: [{ ...structuredDraft.citations[0], state: 'unavailable' }],
      },
    });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('button', { name: /approve finding/i });

    expect(screen.getByText(/1 of 1 cannot be followed/i)).toBeTruthy();
  });

  it('explains what approving and rejecting do', async () => {
    // While deciding, not afterwards.
    mockApi(gated());
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('button', { name: /approve finding/i });

    const consequence = screen.getByText(/Approving publishes this finding/i);
    expect(consequence.textContent).toMatch(/rejecting records your reason/i);
    expect(consequence.textContent).toMatch(/stay in Replay/i);
  });

  it('offers a viewer no way to decide, and says why', async () => {
    mockApi({
      ...gated({ can_decide: false }),
    });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByText(/owner or admin judgment is required/i);

    expect(screen.queryByRole('button', { name: /approve finding/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /reject finding/i })).toBeNull();
    // But the evidence is still shown: read-only is not blind.
    expect(screen.getByText(/42% · capped sample size/i)).toBeTruthy();
  });

  it('counts erased evidence apart from lost evidence', async () => {
    // Collapsing them would tell a reviewer their data is missing when a
    // Tenant asked for it to go.
    mockApi({
      ...gated(),
      draft_finding: {
        ...structuredDraft,
        citations: [{ ...structuredDraft.citations[0], state: 'tombstoned' }],
      },
    });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('button', { name: /approve finding/i });

    expect(screen.getByText(/1 erased at the tenant's request/i)).toBeTruthy();
    expect(screen.queryByText(/cannot be followed/i)).toBeNull();
  });

  it('says when a legacy investigation has no claim-level evidence', async () => {
    // A reviewer seeing no evidence block would not know whether there is
    // nothing to show or whether it failed to load.
    mockApi({ ...investigation, draft_finding: null });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('button', { name: /approve finding/i });

    expect(screen.getByText(/predates structured claims/i)).toBeTruthy();
  });

  it('shows the chain degrading, not only what answered', async () => {
    // An outage that a fallback survived is invisible if Replay reports only
    // the provider that happened to answer.
    mockApi();
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('button', { name: /approve finding/i });

    expect(screen.getByText(/after 1 failed rung/i)).toBeTruthy();
  });

  it('explains a gate at the point in the timeline where it opened', async () => {
    mockApi({
      ...investigation,
      timeline: investigation.timeline.map((entry) =>
        entry.event_type === 'human_approval.requested'
          ? { ...entry, failed_conditions: ['confident', 'evidenced'] }
          : entry,
      ),
    });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('button', { name: /approve finding/i });

    expect(
      screen.getByText(
        /Bounded confidence is below the tenant threshold · A substantive claim has no evidence that can be followed/i,
      ),
    ).toBeTruthy();
  });

  it('names the version of the agent that ran, and what it cost in time', async () => {
    // The version was in `agent_id` all along and stripped for readability, so
    // Replay could not answer which build produced a Finding.
    mockApi();
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByRole('button', { name: /approve finding/i });

    expect(screen.getByText(/v1 · 1240 ms/)).toBeTruthy();
  });

  const terminal = {
    ...investigation,
    status: 'completed',
    pending_approval: null,
    can_delete_evidence: true,
  };

  it('offers no one-click path to an irreversible action', async () => {
    // A destructive action reachable by one click on a page a reader is
    // scrolling is an action that will happen by accident.
    mockApi(terminal);
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    const start = await screen.findByRole('button', { name: /delete evidence/i });

    expect(screen.queryByRole('alertdialog')).toBeNull();
    fireEvent.click(start);

    expect(screen.getByRole('alertdialog')).toBeTruthy();
    expect(screen.getByRole('button', { name: /erase this evidence/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /keep it/i })).toBeTruthy();
  });

  it('names what is being erased and what survives', async () => {
    mockApi(terminal);
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    fireEvent.click(await screen.findByRole('button', { name: /delete evidence/i }));

    const warning = screen.getByRole('alertdialog').textContent ?? '';
    expect(warning).toContain('Why did EU refunds increase');
    expect(warning).toMatch(/stays in Replay/i);
    expect(warning).toMatch(/cannot be undone/i);
  });

  it('offers no deletion on a live investigation', async () => {
    // Erasing under a running pipeline races every write still to come.
    mockApi({
      ...investigation,
      status: 'running',
      pending_approval: null,
      can_delete_evidence: false,
    });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByText(/EU refunds rose/i);

    expect(screen.queryByRole('button', { name: /delete evidence/i })).toBeNull();
  });

  it('offers no deletion to a member', async () => {
    mockApi({ ...terminal, can_delete_evidence: false });
    signedIn();

    renderApp('/investigations/30000000-0000-0000-0000-000000000003');
    await screen.findByText(/EU refunds rose/i);

    expect(screen.queryByRole('button', { name: /delete evidence/i })).toBeNull();
  });
});
