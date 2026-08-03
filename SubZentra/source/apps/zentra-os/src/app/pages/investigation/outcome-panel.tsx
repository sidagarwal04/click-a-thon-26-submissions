import { approvalHeadings } from '../../constants/labels';
import type { Investigation } from '../../types';

/**
 * The typed outcome the evaluator recorded, in its own vocabulary.
 */
export const OutcomePanel = ({
  investigation,
}: {
  readonly investigation: Investigation;
}) => {
  const outcome = investigation.outcome;
  if (!outcome) return null;

  const heading = investigation.pending_approval
    ? (approvalHeadings[investigation.pending_approval.reason] ?? 'Human judgment required')
    : null;

  if (outcome.kind === 'confidence') {
    const percent = Math.round(outcome.score * 100);
    return (
      <section
        className="mt-8 border-t border-border pt-6"
        aria-labelledby="outcome-title"
      >
        <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
          Typed outcome · confidence
        </p>
        <h3 id="outcome-title" className="mt-2 text-lg font-medium">
          {heading ?? 'Rechecked and cleared to publish'}
        </h3>
        <p className="mt-3 text-sm text-foreground-muted">
          <strong className="font-mono text-2xl text-foreground">{percent}%</strong> confidence
        </p>
        <ul className="mt-4 flex list-none flex-col gap-2 p-0 text-sm text-foreground-muted">
          <li>Calibrated by: {outcome.calibration_method.replace(/_/g, ' ')}</li>
          <li>Evaluation attempts: {investigation.evaluation_attempts} of 3</li>
          {outcome.calibration_method === 'capped_evaluator_shared_model_family' ? (
            <li className="text-warning">
              ! The recheck ran on the same model family as the analysis, so it was not
              independent. Confidence is capped and this cannot publish without you.
            </li>
          ) : null}
        </ul>
      </section>
    );
  }

  return (
    <section className="mt-8 border-t border-border pt-6" aria-labelledby="outcome-title">
      <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
        Typed outcome · validation
      </p>
      <h3 id="outcome-title" className="mt-2 text-lg font-medium">
        {heading ?? 'Validation passed'}
      </h3>
      <ul className="mt-4 flex list-none flex-col gap-2 p-0 text-sm text-foreground-muted">
        {outcome.checks.map((check) => (
          <li key={check}>✓ {check}</li>
        ))}
        {outcome.issues.map((issue) => (
          <li className="text-warning" key={issue}>
            ! {issue}
          </li>
        ))}
      </ul>
    </section>
  );
};
