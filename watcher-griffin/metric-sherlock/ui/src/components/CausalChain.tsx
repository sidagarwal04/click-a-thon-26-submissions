/* The diagnosis as one because-ladder.
 *
 * Everything here is already on the page somewhere — in the spread bars, the sibling
 * bars, the waterfall, the impact breakdown. What this adds is the word "because"
 * between them, in the order a person actually asks: what moved, where, why not
 * elsewhere, why not the calendar, what that pattern means, what it costs.
 *
 * Certainty is on every rung, and the weak ones are shown rather than hidden. A ladder
 * where every step reads with equal confidence cannot be told apart from one that had
 * nothing to say at a step — so "could not be tested" and "matched no known mechanism"
 * get their own marker and their own colour, and the header states plainly when the
 * chain is incomplete.
 *
 * No number here is computed in the browser. Each comes from engine/causal_chain.py,
 * which itself only copies fields the incident already carries.
 */

import type { CausalChain as Chain, ChainLink } from '../types'

const CERTAINTY: Record<string, { label: string; hint: string }> = {
  measured: {
    label: 'measured',
    hint: 'Read directly from a band comparison against this slice’s own normal.',
  },
  ruled_out: {
    label: 'ruled out',
    hint: 'An alternative explanation that was tested and cleared, with the numbers that cleared it.',
  },
  derived: {
    label: 'rule table',
    hint: 'A deterministic rule over the measured spread — not the language model, and not a probability.',
  },
  unknown: {
    label: 'not established',
    hint: 'This check could not be run, or the pattern matched no known mechanism. Shown rather than skipped.',
  },
}

function Rung({ link, last }: { link: ChainLink; last: boolean }) {
  const c = CERTAINTY[link.certainty] ?? CERTAINTY.unknown
  return (
    <li className={`rung rung-${link.certainty}${last ? ' rung-last' : ''}`}>
      <div className="rung-marker" aria-hidden="true">
        <span className="rung-dot">{link.step}</span>
        {!last && <span className="rung-line" />}
      </div>

      <div className="rung-body">
        <div className="rung-head">
          <span className="rung-title">{link.title}</span>
          <span className="rung-certainty" title={c.hint}>
            {c.label}
          </span>
        </div>

        <p className="rung-claim">{link.claim}</p>
        {link.because && <p className="rung-because">{link.because}</p>}

        {link.source_steps.length > 0 && (
          <p className="rung-source">
            from{' '}
            {link.source_steps.slice(0, 3).map((s, i) => (
              <span key={s}>
                {i > 0 && ', '}
                <code>{s}</code>
              </span>
            ))}
            {link.source_steps.length > 3 && ` +${link.source_steps.length - 3} more`}
          </p>
        )}
      </div>
    </li>
  )
}

export default function CausalChain({ chain }: { chain: Chain | null }) {
  if (!chain || chain.links.length === 0) {
    return (
      <p className="muted-note">
        No causal chain could be assembled for this incident — the evidence it carries is
        not enough to state one, and a plausible-sounding chain was not substituted.
      </p>
    )
  }

  return (
    <div className="chain">
      <ol className="chain-list">
        {chain.links.map((link, i) => (
          <Rung key={link.step} link={link} last={i === chain.links.length - 1} />
        ))}
      </ol>

      <p className="source-note">
        {chain.complete ? (
          <>
            Every step above is either a measured figure or an alternative that was tested and
            cleared. Nothing in this chain was written by the language model.
          </>
        ) : (
          <>
            One or more steps are marked <strong>not established</strong> — that gap is real and
            is shown deliberately rather than being smoothed over. The measured steps stand
            regardless.
          </>
        )}
      </p>
    </div>
  )
}
