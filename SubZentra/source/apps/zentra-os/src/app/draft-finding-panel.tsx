import { useState } from 'react';

import { Badge } from '@open-zentra/foundation-design-system';
import { useAuthSession } from '@open-zentra/foundation-auth';
import { useQuery } from '@tanstack/react-query';

import { ApiError, requestJson } from './api';

import styles from './draft-finding-panel.module.scss';

export interface Claim {
  readonly claim_id: string;
  readonly kind: 'observed' | 'interpretation';
  readonly text: string;
  readonly position: number;
  // The measurement behind an observed claim. Null on an interpretation,
  // which is a reading of someone else's measurement.
  readonly metric: string | null;
  readonly value: string | null;
  readonly period: string | null;
  readonly citation_ids: readonly string[];
}

export interface CitationFilter {
  readonly member: string;
  readonly operator: string;
  readonly values: readonly string[];
}

export interface EvidenceCitation {
  readonly citation_id: string;
  readonly metric: string;
  readonly filters: readonly CitationFilter[];
  readonly period: string | null;
  readonly grain: string | null;
  readonly producing_execution_id: string | null;
  readonly aggregate_value: string;
  readonly state: 'active' | 'unavailable' | 'tombstoned';
}

export interface DraftFinding {
  readonly draft_finding_id: string;
  readonly version: number;
  readonly created_at: string;
  readonly produced_by_execution_id: string | null;
  readonly headline: string;
  readonly summary: string;
  readonly claims: readonly Claim[];
  readonly contradictions: readonly {
    readonly detail: string;
    readonly resolved: boolean;
  }[];
  readonly root_cause: 'unresolved';
  readonly confidence: {
    readonly score: number;
    readonly calibration_method: string;
  } | null;
  // Shared across claims, so they arrive once. A claim's `citation_ids` index
  // into these.
  readonly citations: readonly EvidenceCitation[];
}

const claimLabels: Record<Claim['kind'], string> = {
  observed: 'Measured',
  interpretation: 'Interpretation',
};

/**
 * Says, in as many words, that this Investigation predates structured claims.
 *
 * Silence would read as "no evidence here", which is a harsher and less true
 * statement than "this one ran before claims were separable".
 */
export function LegacyFindingNotice() {
  return (
    <p className={styles.legacyNotice} data-state="legacy">
      This Investigation ran before claims were recorded separately. Its
      conclusion is narrative, and it carries no Evidence Citations to follow
      to individual claims.
    </p>
  );
}

/**
 * The evidence behind one claim, resolved when the reader asks for it.
 *
 * A `<details>` because the reader is inspecting evidence, not navigating
 * away — and because it is keyboard-operable and announced without any
 * scripting to get wrong.
 *
 * It fetches on open rather than rendering what the Investigation payload
 * already carried. Following a citation is a Tenant-authorized read with its
 * own outcomes, and five of them have to stay apart: still loading, resolved
 * and readable, resolved but unreachable, not permitted, and broken. Rendering
 * the inline copy would collapse the last three into silence.
 */
function CitationDisclosure({
  investigationId,
  citationId,
  claimText,
}: {
  investigationId: string;
  citationId: string;
  claimText: string;
}) {
  const [open, setOpen] = useState(false);
  const { getAccessToken } = useAuthSession();

  const resolved = useQuery({
    queryKey: ['citation', investigationId, citationId],
    enabled: open,
    retry: false,
    queryFn: () =>
      requestJson<EvidenceCitation>(
        `/v1/investigations/${investigationId}/citations/${citationId}`,
        () => getAccessToken({ audience: 'first_party_http' }),
      ),
  });

  return (
    <details
      className={styles.evidence}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        Evidence
        <span className={styles.srOnly}> for: {claimText}</span>
      </summary>
      <div aria-live="polite">
        <CitationBody
          state={resolutionState(resolved.isPending, resolved.error, resolved.data)}
          citation={resolved.data}
        />
      </div>
    </details>
  );
}

type ResolutionState =
  | 'loading'
  | 'active'
  | 'unavailable'
  | 'tombstoned'
  | 'inaccessible'
  | 'failed';

function resolutionState(
  isPending: boolean,
  error: unknown,
  citation?: EvidenceCitation,
): ResolutionState {
  if (error) {
    // 404 is the deliberate invisible-resource answer, and covers another
    // Tenant's, another Investigation's, and nonexistent alike. Anything else
    // is a fault, and a reader should not be told it is a permission problem.
    return error instanceof ApiError && error.status === 404
      ? 'inaccessible'
      : 'failed';
  }
  if (isPending || !citation) return 'loading';
  return citation.state;
}

const stateCopy: Record<Exclude<ResolutionState, 'active'>, string> = {
  loading: 'Resolving evidence…',
  // Recorded, and not reachable. Deliberately not worded as a deletion: a
  // Tenant who erased something asked for that, and a reader told "deleted"
  // about data loss is being reassured wrongly.
  unavailable:
    'This evidence is unavailable. It was recorded, and cannot currently be reached.',
  tombstoned:
    'This evidence was deleted at the Tenant\u2019s request. What it supported is recorded; its values are not.',
  inaccessible: 'This evidence is not available to you.',
  failed: 'Evidence could not be loaded. Try again.',
};

function CitationBody({
  state,
  citation,
}: {
  state: ResolutionState;
  citation?: EvidenceCitation;
}) {
  if (state !== 'active' || !citation) {
    return (
      <p className={styles.evidenceState} data-state={state}>
        {stateCopy[state as Exclude<ResolutionState, 'active'>]}
      </p>
    );
  }

  return (
    <dl>
      <dt>Metric</dt>
      <dd>{citation.metric}</dd>
      <dt>Value</dt>
      <dd>{citation.aggregate_value}</dd>
      {citation.period ? (
        <>
          <dt>Period</dt>
          <dd>{citation.period}</dd>
        </>
      ) : null}
      {citation.grain ? (
        <>
          <dt>Grain</dt>
          <dd>{citation.grain}</dd>
        </>
      ) : null}
      {citation.filters.length > 0 ? (
        <>
          <dt>Filters</dt>
          <dd>
            {citation.filters
              .map(
                (filter) =>
                  `${filter.member} ${filter.operator} ${filter.values.join(', ')}`,
              )
              .join('; ')}
          </dd>
        </>
      ) : null}
    </dl>
  );
}

export function DraftFindingPanel({
  draft,
  investigationId,
}: {
  draft: DraftFinding;
  investigationId: string;
}) {
  const headingId = `draft-${draft.draft_finding_id}`;
  const unresolved = draft.contradictions.filter((c) => !c.resolved);

  return (
    <section
      className={styles.draft}
      data-state="structured"
      aria-labelledby={headingId}
    >
      <h3 id={headingId} className={styles.srOnly}>
        Draft finding claims
      </h3>

      <ol className={styles.claims}>
        {draft.claims.map((claim) => (
          <li key={claim.claim_id} className={styles.claim}>
            {/* The label is text, not a colour. A reader who cannot
                distinguish the two swatches still gets the distinction. */}
            <Badge
              intent={claim.kind === 'observed' ? 'success' : 'default'}
              size="sm"
            >
              {claimLabels[claim.kind]}
            </Badge>
            <div>
              <p>{claim.text}</p>
              {/* Shown, not implied. A reader should be able to see the
                  figure a claim rests on without following anything. */}
              {claim.metric && claim.value ? (
                <p className={styles.measurement}>
                  <span>{claim.metric}</span>
                  <span>{claim.value}</span>
                  {claim.period ? <span>{claim.period}</span> : null}
                </p>
              ) : null}
              {claim.citation_ids.map((citationId) => (
                <CitationDisclosure
                  key={citationId}
                  investigationId={investigationId}
                  citationId={citationId}
                  claimText={claim.text}
                />
              ))}
            </div>
          </li>
        ))}
      </ol>

      {unresolved.length > 0 ? (
        <div className={styles.contradictions} role="note">
          <span className={styles.contradictionLabel}>
            Unresolved contradiction{unresolved.length > 1 ? 's' : ''}
          </span>
          <ul>
            {unresolved.map((contradiction) => (
              <li key={contradiction.detail}>{contradiction.detail}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Unconditional. Phase 2 admits no other root-cause state, and
          ADR 0011 turns on the product saying this out loud rather than
          leaving causality to be assumed. */}
      <p className={styles.rootCause}>
        Root cause unresolved — the evidence shows what changed, not why.
      </p>
    </section>
  );
}
