import { useEffect, useRef, useState } from 'react';

import { Button, Select, SelectContent, SelectItem, SelectTrigger } from '@open-zentra/foundation-design-system';
import { motion } from 'motion/react';

import { approvalHeadings, conditionLabels } from '../../constants/labels';
import type { Investigation, RejectionReason } from '../../types';

/**
 * What the reviewer is being asked to judge, in the place they judge it.
 *
 * The Draft Finding panel is elsewhere on the page; a reviewer scrolling back
 * and forth between the decision and the evidence is a reviewer who might not.
 * These are the four things a decision turns on — how far the evidence can be
 * trusted, whether anything is still disputed, how many claims are followable,
 * and whether any of them are not.
 */
const ApprovalEvidence = ({ investigation }: { readonly investigation: Investigation }) => {
  const draft = investigation.draft_finding;
  if (!draft) {
    // Said, not omitted. A reviewer seeing no evidence block would not know
    // whether there is nothing to show or whether it failed to load.
    return (
      <p className="mt-4 text-sm leading-relaxed text-foreground-muted">
        This investigation predates structured claims. There is no claim-level evidence to
        review; judge it from the narrative finding above.
      </p>
    );
  }

  const observed = draft.claims.filter((claim) => claim.kind === 'observed');
  // Resolved from the payload the page already holds, not fetched on demand:
  // a reviewer must not be able to decide before the evidence has answered.
  //
  // Lost and deliberately erased are counted apart. Collapsing them would tell
  // a reviewer their data is missing when a Tenant asked for it to go.
  const unavailable = draft.citations.filter((c) => c.state === 'unavailable');
  const tombstoned = draft.citations.filter((c) => c.state === 'tombstoned');

  return (
    <dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
      <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
        Confidence
      </dt>
      <dd className="m-0 text-foreground">
        {draft.confidence
          ? `${Math.round(draft.confidence.score * 100)}% · ${draft.confidence.calibration_method.replace(/_/g, ' ')}`
          : 'Not reported'}
      </dd>
      <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
        Measured claims
      </dt>
      <dd className="m-0 text-foreground">
        {observed.length} of {draft.claims.length}
      </dd>
      <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
        Evidence
      </dt>
      <dd className="m-0 text-foreground">
        {unavailable.length === 0 && tombstoned.length === 0
          ? `${draft.citations.length} citations, all resolvable`
          : [
              unavailable.length > 0
                ? `${unavailable.length} of ${draft.citations.length} cannot be followed`
                : null,
              tombstoned.length > 0
                ? `${tombstoned.length} erased at the tenant's request`
                : null,
            ]
              .filter(Boolean)
              .join(' · ')}
      </dd>
      <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
        Contradictions
      </dt>
      <dd className="m-0 text-foreground">
        {draft.contradictions.filter((c) => !c.resolved).length === 0
          ? 'None open'
          : draft.contradictions
              .filter((c) => !c.resolved)
              .map((c) => c.detail)
              .join('; ')}
      </dd>
      <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
        Root cause
      </dt>
      {/* Read from the draft rather than asserted. The API's literal is
          `unresolved` today; hardcoding the copy would make this row lie the
          day a causal-evidence standard widens it. */}
      <dd className="m-0 text-foreground">
        {draft.root_cause === 'unresolved'
          ? 'Unresolved — the evidence shows what changed, not why'
          : draft.root_cause}
      </dd>
    </dl>
  );
};

const rejectionReasons: readonly { value: RejectionReason; label: string }[] = [
  { value: 'insufficient_evidence', label: 'Insufficient evidence' },
  { value: 'incorrect_interpretation', label: 'Incorrect interpretation' },
  { value: 'policy_mismatch', label: 'Policy mismatch' },
  { value: 'needs_more_analysis', label: 'Needs more analysis' },
];

/**
 * The human gate: why it opened, what it rests on, and the decision itself.
 */
export const ApprovalInspector = ({
  investigation,
  onDecision,
  pending,
}: {
  readonly investigation: Investigation;
  readonly onDecision: (
    decision: 'approve' | 'reject',
    reason: RejectionReason | null,
  ) => void;
  readonly pending: boolean;
}) => {
  const approval = investigation.pending_approval;
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [reason, setReason] = useState<RejectionReason>('insufficient_evidence');

  useEffect(() => {
    if (approval) {
      headingRef.current?.focus();
    }
  }, [approval]);

  if (!approval) {
    return (
      <aside
        className="flex flex-col gap-3 border border-border bg-card p-5"
        aria-live="polite"
      >
        <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
          Resolution
        </p>
        <h2 className="text-xl font-medium">
          {investigation.status === 'completed'
            ? 'Approved and complete'
            : investigation.status === 'rejected'
              ? 'Rejected with cause'
              : 'No decision required'}
        </h2>
        <p className="text-sm leading-relaxed text-foreground-muted">
          The persisted evidence beam has reached a terminal state. No hidden rationale was
          recorded.
        </p>
      </aside>
    );
  }

  return (
    <motion.aside
      className="flex flex-col border border-primary bg-card p-5"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 12 }}
      transition={{ duration: 0.24 }}
      aria-labelledby="approval-heading"
    >
      <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
        Human Approval · required
      </p>
      <h2
        id="approval-heading"
        ref={headingRef}
        tabIndex={-1}
        className="mt-2 text-xl font-medium focus-visible:outline-none"
      >
        {approvalHeadings[approval.reason] ?? 'Human judgment required'}
      </h2>

      {/* Every condition the policy found failing, not just the heading's.
          Deciding on the headline alone is deciding on part of the picture —
          and the copy here used to describe one scenario's sample size
          regardless of why the gate actually opened. */}
      {approval.failed_conditions.length > 0 ? (
        <ul className="mt-4 flex list-none flex-col gap-2 p-0 text-sm text-warning">
          {approval.failed_conditions.map((condition) => (
            <li key={condition}>{conditionLabels[condition] ?? condition.replace(/_/g, ' ')}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-foreground-muted">
          Tenant policy requires a human to accept or reject this finding.
        </p>
      )}

      <ApprovalEvidence investigation={investigation} />

      {/* Said before the buttons, not after. A reviewer should know what
          approving does while deciding, not discover it afterwards. */}
      <p className="mt-5 text-sm leading-relaxed text-foreground-muted">
        Approving publishes this finding to everyone in the tenant. Rejecting records your
        reason and closes the investigation without publishing. Either way the evidence, the
        decision and who made it stay in Replay.
      </p>

      {approval.can_decide ? (
        <div className="mt-5 flex flex-col gap-3">
          <Button fullWidth loading={pending} onClick={() => onDecision('approve', null)}>
            Approve finding
          </Button>
          <label className="flex flex-col gap-2 text-sm text-foreground-muted">
            If rejecting, record a structured reason
            <Select
              value={reason}
              onValueChange={(value) => setReason(value as RejectionReason)}
            >
              {/* The trigger renders the raw value unless it is given the
                  label: the items it would read one from are unmounted while
                  the list is closed. */}
              <SelectTrigger aria-label="Rejection reason">
                {rejectionReasons.find((option) => option.value === reason)?.label}
              </SelectTrigger>
              <SelectContent>
                {rejectionReasons.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <Button
            fullWidth
            intent="danger"
            disabled={pending}
            onClick={() => onDecision('reject', reason)}
          >
            Reject finding
          </Button>
        </div>
      ) : (
        <p className="mt-5 text-sm text-foreground-muted">
          Owner or admin judgment is required. Your membership is read only for this gate.
        </p>
      )}
    </motion.aside>
  );
};
