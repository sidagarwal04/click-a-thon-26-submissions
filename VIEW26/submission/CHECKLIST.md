# VIEW26 submission readiness

## Complete

- [x] Project source is in one repository.
- [x] Root `README.md` includes team, track, project, product summary, hosted URL, architecture, build stack, and run link.
- [x] `RUN.md` lists environment variables, ClickHouse connectivity, one-command pipeline, unseen flow, tests, and staging routing.
- [x] Three standalone agents and explicit handoffs are documented.
- [x] Eight-source-table Analytics Agent report captured with Langfuse trace.
- [x] Five known features replayed in sequence.
- [x] Generated DDL for all five known features captured.
- [x] Sealed sixth feature completed end to end without feature-specific schema hints.
- [x] Context v5→v6 schema/ontology changelog captured.
- [x] Generated sixth-feature DDL, PM insight, and trace captured.
- [x] All six feature runs pass 9/9 context-evolution checks (54/54 total).
- [x] Four standard PM probes captured with synced traces.
- [x] All eleven graded Langfuse traces published as public share links.
- [x] Hosted application deployed and verified at [https://clickathon-2026.view26.com](https://clickathon-2026.view26.com).
- [x] Team-member names and GitHub handles included in root `README.md`.
- [x] Backend test suite passes.
- [x] Pitch-deck source and PDF are generated and visually verified.

## Owner actions before the PR

- [ ] Record the final 2–3 minute demo and replace the video placeholder in `README.md`.
- [ ] Rotate the Langfuse secret that appeared in a screenshot; update staging `.env` only.
- [ ] Copy the repository into `VIEW26/` at the root of the official submissions fork.
- [ ] Confirm no secret, dataset dump, `.env`, build output, or local runtime file is staged.
- [ ] Open exactly one PR titled `[Submission] VIEW26`.
- [ ] Run every link in the PR description once after publishing.
