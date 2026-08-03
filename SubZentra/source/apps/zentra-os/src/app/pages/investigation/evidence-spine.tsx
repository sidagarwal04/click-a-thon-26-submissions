import { Card } from '@open-zentra/foundation-design-system';
import { motion, useReducedMotion } from 'motion/react';

import { agentLabels, conditionLabels, eventLabels } from '../../constants/labels';
import type { Investigation } from '../../types';

/**
 * The persisted evidence timeline: what happened, in the order the ledger
 * recorded it.
 */
export const EvidenceSpine = ({
  investigation,
}: {
  readonly investigation: Investigation;
}) => {
  const reducedMotion = useReducedMotion();
  const resolved = investigation.status === 'completed';
  const rejected = investigation.status === 'rejected';
  const pathColor = rejected ? 'text-danger' : resolved ? 'text-primary' : 'text-accent';

  return (
    <Card component="section" aria-labelledby="evidence-title">
      <Card.Header end={
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
          {investigation.audit_delivery === 'complete'
            ? 'Ledger synchronized'
            : 'Ledger delivery pending'}
        </span>
      }
      >
        <Card.Title>Evidence trace</Card.Title>
      </Card.Header>

      <h2 id="evidence-title" className="sr-only">
        Persisted evidence timeline
      </h2>

      <div className="relative pl-5">
        <svg
          aria-hidden="true"
          className={`absolute left-0 top-1 h-[calc(100%-0.5rem)] w-2 ${pathColor}`}
          viewBox="0 0 8 100"
          preserveAspectRatio="none"
        >
          <motion.path
            d="M4 0 V100"
            fill="none"
            stroke="currentColor"
            strokeWidth={1}
            initial={reducedMotion ? false : { pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: reducedMotion ? 0 : 0.82, ease: 'easeOut' }}
          />
        </svg>

        <ol className="m-0 flex list-none flex-col gap-5 p-0">
          {investigation.timeline.map((entry, index) => (
            <motion.li
              className="relative grid grid-cols-[1fr_auto] items-start gap-3"
              key={entry.entry_id}
              initial={reducedMotion ? false : { opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{
                duration: 0.2,
                delay: reducedMotion ? 0 : Math.min(index * 0.07, 0.56),
              }}
            >
              <span
                className="absolute -left-[1.4rem] top-1.5 h-1.5 w-1.5 rounded-full bg-primary"
                aria-hidden="true"
              />
              <div className="flex min-w-0 flex-col gap-0.5">
                <strong className="text-sm font-medium text-foreground">
                  {entry.agent_id
                    ? `${agentLabels[entry.agent_id.replace(/_v\d+$/, '')] ?? entry.agent_id}${
                        entry.step ? ` · step ${entry.step}` : ''
                      }`
                    : (eventLabels[entry.event_type] ?? entry.event_type)}
                </strong>
                {/* The version was in `agent_id` all along and stripped for
                    readability, so Replay could not answer which build of an
                    Agent produced a Finding. */}
                {entry.agent_id?.match(/_v(\d+)$/) ? (
                  <small className="font-mono text-[10px] text-foreground-muted">
                    v{entry.agent_id.match(/_v(\d+)$/)?.[1]}
                    {entry.latency_ms !== null ? ` · ${entry.latency_ms} ms` : ''}
                  </small>
                ) : null}
                {entry.model ? (
                  <small className="font-mono text-[10px] text-foreground-muted">
                    {entry.model}
                  </small>
                ) : null}
                {/* The chain degrading is part of what happened. Showing only
                    the provider that answered makes an outage invisible. */}
                {entry.fallbacks.length > 0 ? (
                  <small className="font-mono text-[10px] text-warning">
                    after {entry.fallbacks.length} failed{' '}
                    {entry.fallbacks.length === 1 ? 'rung' : 'rungs'}
                  </small>
                ) : null}
                {/* Why the gate opened, in the policy's own words, at the
                    point in the timeline where it opened. */}
                {entry.failed_conditions.length > 0 ? (
                  <small className="text-[11px] text-warning">
                    {entry.failed_conditions
                      .map((c) => conditionLabels[c] ?? c.replace(/_/g, ' '))
                      .join(' · ')}
                  </small>
                ) : null}
                <small className="font-mono text-[10px] text-foreground-muted">
                  {new Date(entry.created_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                  })}
                  {entry.delivery === 'pending' ? ' · audit pending' : ''}
                </small>
              </div>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
                {entry.status.replace(/_/g, ' ')}
              </span>
            </motion.li>
          ))}
        </ol>
      </div>
    </Card>
  );
};
