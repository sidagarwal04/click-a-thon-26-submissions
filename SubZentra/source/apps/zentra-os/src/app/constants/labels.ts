/**
 * The words the product uses for the API's own vocabulary.
 *
 * Every map here falls back to the raw literal at the call site, so an event
 * type or condition the API adds tomorrow renders as itself rather than
 * disappearing.
 */

export const eventLabels: Record<string, string> = {
  'investigation.evidence_erased': 'Evidence erased at the tenant’s request',
  'human_approval.denied': 'A decision was attempted and refused',
  'investigation.created': 'Question registered',
  'investigation.started': 'Governed query started',
  'investigation.evaluation_started': 'Validation opened',
  'investigation.validation_completed': 'Evidence validated',
  'human_approval.requested': 'Human judgment requested',
  'human_approval.granted': 'Human judgment recorded',
  'human_approval.rejected': 'Evidence rejected',
  'investigation.completed': 'Investigation completed',
  'investigation.rejected': 'Investigation rejected',
  'investigation.retry_requested': 'Recheck disagreed, retrying',
  'investigation.failed': 'Investigation failed',
  'agent.execution_completed': 'Agent step completed',
  'agent.execution_failed': 'Agent step failed',
};

export const agentLabels: Record<string, string> = {
  orchestrator: 'Orchestrator',
  cube_analyst: 'Cube Analyst',
  // Read-compatibility (ADR-0025). Agent Executions that ran before the rename
  // still carry this role, and Replay renders them — a step labelled by its
  // raw role string would be the one place the old name leaks to a reader.
  sql_analyst: 'Cube Analyst',
  evaluator: 'Evaluator',
};

export const approvalHeadings: Record<string, string> = {
  low_confidence: 'Confidence below the tenant threshold',
  contradiction_unresolved: 'The recheck did not converge',
  tenant_policy: 'Review required by tenant policy',
  irreversible_action: 'Irreversible action requires approval',
  regulatory_exposure: 'Regulated data requires approval',
  evidence_incomplete: 'A claim cannot be followed to its evidence',
};

// The publication policy's own words. The heading leads with one reason; this
// is every condition that failed, because a reviewer deciding on the headline
// alone would be deciding on part of the picture.
export const conditionLabels: Record<string, string> = {
  converged: 'The independent recheck did not agree',
  confident: 'Bounded confidence is below the tenant threshold',
  evidenced: 'A substantive claim has no evidence that can be followed',
  uncontradicted: 'A contradiction is still open',
};
