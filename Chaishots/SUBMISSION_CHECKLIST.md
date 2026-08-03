# Click-a-thon 2026 submission checklist — Atlys

The official deadline is **12:00 noon IST on 2 August 2026**. A GitHub PR alone
does not count: the PR URL must also be submitted through the hackathon portal
before it closes. The portal submission cannot be edited, and clicking
**Withdraw** permanently voids it.

## Required repository package

- [ ] Fork `sidagarwal04/click-a-thon-26-submissions`.
- [ ] Create one root folder named exactly after the team.
- [x] Include backend and frontend source together (`backend/` and `frontend/`);
      do not rely only on links to separate repositories.
- [ ] Add a team README with track, project, members/GitHub handles, what it
      does, hosted demo, demo video, architecture, build notes, and local run
      instructions.
- [x] Add the architecture explanation and diagram in `ARCHITECTURE.md`.
- [ ] Add a public hosted demo link.
- [ ] Add a 2–3 minute demo-video link.
- [x] Add the pitch deck as `pitch-deck-1.pdf`.
- [ ] Confirm no `.env`, API key, password, private trace credential, or other
      secret is present in the diff or Git history.

## Required Atlys evidence

- [x] Three agents are present: Instrumentation, Analytics, and Context.
- [x] `RUN.md` lists environment variables, ClickHouse Cloud setup, and one
      command that runs a feature end to end.
- [x] Architecture explains agent hand-offs, context storage and rationale,
      Langfuse wiring, any ClickStack/LibreChat integration, and LLM choice.
- [ ] Generated DDL exists for all five known specs and the sealed sixth spec.
- [ ] An autonomous Analytics Agent report over the eight existing tables is
      included.
- [ ] Living context plus a before/after changelog proves it changed when a new
      table was added.
- [ ] The sealed sixth-spec bundle contains generated schema, product-facing
      insights, and its mandatory trace.
- [ ] Shared links or exported Langfuse traces exist for every agent run.

## Mandatory standard probes

Include outputs and traces for these exact prompts:

1. “Analyze the existing funnel and surface the most important issues, with the why.”
2. “Where are we losing conversions, and for which segments (device / geo / destination)?”
3. “Are there any regressions or trends over the last quarter?”
4. “Is anything in the base context wrong, stale, or self-contradictory?”

## Final validation and submission

- [x] Backend tests, Ruff, and mypy pass.
- [x] Frontend type-check and production build pass.
- [ ] Hosted demo opens in a signed-out browser and demonstrates the track
      requirements—not only a landing page.
- [ ] Video URL opens without requesting access and is 2–3 minutes long.
- [ ] Deck PDF opens from the PR.
- [ ] Open one PR against the submissions repository titled
      `[Submission] <Team Name>`.
- [ ] Verify the final PR URL opens, targets the correct repository, and contains
      the final source and artifacts.
- [ ] Enter the project title and PR URL in the hackathon portal, click
      **Submit**, and confirm success before 12:00 noon IST.
- [ ] Do **not** click **Withdraw** after submission.

## Details still needed from the team

- Team name
- Team-member names and GitHub handles
- Final project title (currently documented as **Asklys**)
- Hosted demo URL
- Demo video URL
