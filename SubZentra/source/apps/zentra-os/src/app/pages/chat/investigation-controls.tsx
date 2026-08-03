/**
 * Cancel, retry, and the approval a Finding is waiting on.
 *
 * Every affordance here is gated on a flag the server put in the snapshot —
 * `can_cancel`, `can_retry`, `can_decide`. None of it is derived from the
 * Investigation's status or the reader's role. A client that worked out for
 * itself when cancelling was legal would be a second copy of a rule that only
 * one place is allowed to own.
 *
 * Cancellation is cooperative: the request records an intent and returns. The
 * button says "Stop", not "Stopped", and the snapshot is what reports the end.
 */

import { useState } from 'react';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Badge, Button, Card } from '@open-zentra/foundation-design-system';

import type { TokenSource } from '../../api';
import type { RejectionReason, Thread, ThreadInvestigation } from '../../types';
import { cancelInvestigation, decideApproval, retryInvestigation } from './api';

const REJECTION_REASONS: readonly { value: RejectionReason; label: string }[] = [
  { value: 'insufficient_evidence', label: 'Insufficient evidence' },
  { value: 'incorrect_interpretation', label: 'Incorrect interpretation' },
  { value: 'policy_mismatch', label: 'Policy mismatch' },
  { value: 'needs_more_analysis', label: 'Needs more analysis' },
];

export const InvestigationControls = ({
  getToken,
  thread,
  investigation,
}: {
  readonly getToken: TokenSource;
  readonly thread: Thread;
  readonly investigation: ThreadInvestigation;
}) => {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState<RejectionReason>('insufficient_evidence');

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['thread', thread.thread_id] });

  const cancel = useMutation({
    mutationFn: () => cancelInvestigation(getToken, investigation.investigation_id),
    onSuccess: refresh,
  });

  const retry = useMutation({
    mutationFn: () => retryInvestigation(getToken, investigation.investigation_id),
    onSuccess: refresh,
  });

  const decision = useMutation({
    mutationFn: (choice: 'approve' | 'reject') => {
      const approval = investigation.approval;
      if (!approval) throw new Error('This approval is no longer available.');
      return decideApproval(
        getToken,
        investigation.investigation_id,
        approval.approval_id,
        choice,
        choice === 'reject' ? reason : null,
      );
    },
    onSuccess: refresh,
  });

  const approval = investigation.approval;
  const awaitingDecision = approval?.can_decide === true && approval.decided_at === null;
  const error = cancel.error ?? retry.error ?? decision.error;

  if (!thread.actions.can_cancel && !thread.actions.can_retry && !awaitingDecision) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3">
      {awaitingDecision && approval ? (
        <Card component="section" padding="md">
          <div className="flex flex-wrap items-center gap-3">
            <Badge intent="warning" size="sm">
              Awaiting your decision
            </Badge>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
              {approval.reason.replace(/_/g, ' ')}
            </span>
          </div>

          {approval.failed_conditions.length > 0 ? (
            <ul className="mt-3 flex list-none flex-col gap-1 p-0">
              {approval.failed_conditions.map((condition) => (
                <li
                  key={condition}
                  className="font-mono text-[10px] uppercase tracking-[0.14em] text-danger"
                >
                  {condition.replace(/_/g, ' ')}
                </li>
              ))}
            </ul>
          ) : null}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button
              intent="primary"
              size="sm"
              disabled={decision.isPending}
              onClick={() => decision.mutate('approve')}
            >
              Approve
            </Button>
            <select
              className="rounded-sm border border-border bg-background px-2 py-1 text-sm"
              value={reason}
              aria-label="Reason for rejecting"
              onChange={(event) => setReason(event.target.value as RejectionReason)}
            >
              {REJECTION_REASONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <Button
              intent="danger"
              size="sm"
              disabled={decision.isPending}
              onClick={() => decision.mutate('reject')}
            >
              Reject
            </Button>
          </div>
        </Card>
      ) : null}

      <div className="flex flex-wrap gap-3">
        {thread.actions.can_cancel ? (
          <Button
            intent="ghost"
            size="sm"
            disabled={cancel.isPending || cancel.isSuccess}
            onClick={() => cancel.mutate()}
          >
            {cancel.isSuccess ? 'Stopping…' : 'Stop this investigation'}
          </Button>
        ) : null}
        {thread.actions.can_retry ? (
          <Button
            intent="ghost"
            size="sm"
            disabled={retry.isPending}
            onClick={() => retry.mutate()}
          >
            Try again
          </Button>
        ) : null}
      </div>

      {error ? (
        <p className="text-sm text-danger" role="alert">
          {error.message}
        </p>
      ) : null}
    </div>
  );
};
