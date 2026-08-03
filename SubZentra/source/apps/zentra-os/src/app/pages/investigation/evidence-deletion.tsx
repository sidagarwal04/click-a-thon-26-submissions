import { useState } from 'react';

import { Button } from '@open-zentra/foundation-design-system';

import type { Investigation } from '../../types';

/**
 * Deleting evidence, with the confirmation the API also demands.
 *
 * Two steps, and the second names the Investigation. An irreversible action
 * reachable by one click on a page a reader is scrolling is an action that
 * will happen by accident.
 */
export const EvidenceDeletion = ({
  investigation,
  canDelete,
  onDelete,
  pending,
}: {
  readonly investigation: Investigation;
  readonly canDelete: boolean;
  readonly onDelete: () => void;
  readonly pending: boolean;
}) => {
  const [confirming, setConfirming] = useState(false);
  // Terminality is the server's call too: it is the same rule the erasure
  // operation enforces, and two copies of it would eventually disagree.
  if (!canDelete) return null;

  return (
    <section
      className="mt-10 border-t border-border pt-6"
      aria-labelledby="deletion-heading"
    >
      <h3 id="deletion-heading" className="sr-only">
        Delete evidence
      </h3>
      {confirming ? (
        <div role="alertdialog" aria-labelledby="deletion-confirm" className="flex flex-col gap-4">
          <p id="deletion-confirm" className="max-w-2xl text-sm leading-relaxed text-danger">
            This erases every measurement, claim and narrative for &ldquo;
            {investigation.canonical_question}&rdquo;. What happened stays in Replay; what it
            found does not. This cannot be undone.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button intent="danger" loading={pending} onClick={onDelete}>
              Erase this evidence
            </Button>
            <Button intent="secondary" onClick={() => setConfirming(false)}>
              Keep it
            </Button>
          </div>
        </div>
      ) : (
        <Button intent="ghost" onClick={() => setConfirming(true)}>
          Delete evidence
        </Button>
      )}
    </section>
  );
};
