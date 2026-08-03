---
id: runbook-clerk-local-setup
title: Set Up Clerk for Local Development
type: runbook
status: active
owner: unassigned
source: repository
created: 2026-07-30
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
implementation: current
priority: high
tags: [runbook, clerk, identity, local]
related: ["[[Runbooks MOC]]", "[[Identity and Tenancy]]", "[[adr/0003-provider-neutral-multi-tenant-identity]]"]
repo_path: tools/evals/bind_clerk_identity.py
code_refs:
  - tools/evals/bind_clerk_identity.py
  - apps/api/src/zentra_api/auth.py
  - libs/adapters/postgres/src/zentra_adapter_postgres/identity.py
---

# Set Up Clerk for Local Development

Driving the app over HTTP needs Clerk. The live-run harness does not — it seeds
a tenant directly and bypasses auth, which is why every agent recording was made
without any of this.

Four things must line up. Three are configuration; the fourth is the one that
fails *after* a successful sign-in and looks like a Clerk problem.

## 1. Two environment variables

Both files are gitignored.

`apps/zentra-os/.env.local`:

```bash
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
VITE_API_URL=http://localhost:8000
```

`apps/api/.env`:

```bash
CLERK_ISSUER=https://your-instance.clerk.accounts.dev
CLERK_AUDIENCE=
```

The issuer is the **Frontend API URL** from the Clerk dashboard. It is also
encoded in the publishable key: everything after `pk_test_` is base64 of the
domain, so `base64 -d` on that segment gives it without a dashboard trip. The
API reads `{CLERK_ISSUER}/.well-known/jwks.json` to verify signatures.

**`CLERK_AUDIENCE` must stay empty.** The web app requests a default Clerk
session token, whose `aud` claim is not `first_party_http` — that string is an
internal transport label in `foundation-auth`, not a Clerk value.
`auth.py` sets `verify_aud` only when the audience is configured, so filling this
in rejects every valid token. Binding an audience properly means creating a JWT
template in Clerk, wiring `tokenTemplates` into `ClerkAuthProvider`, and setting
this to the template's `aud` — all three together or none.

**The Clerk secret key is not used anywhere in this repository.** Verification is
JWKS-based and there is no server-side Clerk SDK call. Do not add it.

## 2. Organizations, enabled

`auth.py` rejects any token without an `org_id`:

> An active Clerk organization is required

Dashboard → **Configure → Organizations** → enable, and set **Membership
required**. Turning on **Create first organization automatically** is worth it:
otherwise the first user signs up with no organization, and the creator dropdown
on the dashboard's org form is empty because no application user exists yet.

Clerk's own roles are never consulted. Authorization comes from
`tenant_memberships.role` in Postgres — provider-neutral identity, ADR-0003.

## 3. Sign up through the app

The signed-out screen offers one button, **Enter the observatory**, which
redirects to Clerk's hosted sign-in. Sign up there. A Clerk *dashboard* account
is not an application user; they are separate.

## 4. Bind the organization to a tenant

This is the step with no equivalent in Clerk, and the one that fails silently.
`resolve_identity_context` needs two rows Clerk knows nothing about:

| Table | Maps |
| --- | --- |
| `tenant_identity_bindings` | Clerk org → `tenants.tenant_id` |
| `identity_subjects` | Clerk user → `users.user_id` |

Without them the browser signs in cleanly and the app shows *"This organization
is not bound to a ZentraOS tenant."*

```bash
uv run python tools/evals/bind_clerk_identity.py \
  --org org_... --user user_... --email you@example.com \
  --name "Nexus Dev" --tier premium
```

It creates the tenant, the user, an owner membership, and both bindings.
Re-running is safe. Get the ids from the dashboard, or from the browser console
once signed in:

```js
await window.Clerk.session.getToken().then(t => {
  const c = JSON.parse(atob(t.split('.')[1]));
  console.log('org:', c.org_id ?? c.o?.id, '| user:', c.sub);
});
```

`--tier premium` matters for what you can demonstrate: on the free tier the
independence ceiling caps confidence at 0.85 at best, and on the small refund
scenario every run gates. Premium on the channel-growth scenario is the only
combination that reaches the publish path.

## When it does not work

| Symptom | Cause |
| --- | --- |
| "Setup required. Add `VITE_CLERK_PUBLISHABLE_KEY`" | key missing, or Vite started before `.env.local` existed — restart the dev server, it does not hot-reload env |
| "Clerk issuer is not configured" | `CLERK_ISSUER` unset, or the API started before it was set — restart it |
| "An active Clerk organization is required" | organizations disabled, or no org active in the session |
| "This organization is not bound to a ZentraOS tenant" | step 4 not run |
| "Failed to fetch" | the API is down or on another port; check `curl localhost:8000/health/live` |
| 401 on every request, log says `MissingRequiredClaimError: "aud"` | `CLERK_AUDIENCE` holds a value the token does not carry. Blank is handled — it means unconfigured |

Parent: [[Runbooks MOC]]
