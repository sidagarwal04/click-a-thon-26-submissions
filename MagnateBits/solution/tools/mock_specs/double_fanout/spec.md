# Feature spec — Collaborative Trip Boards

## What it does
A traveller opens a shared board (the parent), starts one or more discussion threads
on it (the children), and anyone with the link posts replies to a thread (the
grandchildren). Reactions come from link recipients who may have no account at all.

The fan-out is two levels deep, so there is no single obvious entity key: a board, a
thread and a reply are each a defensible unit of analysis and the right answer depends
on the question being asked.

## User actions (raw events emitted)
- `board_opened` — a member opens a board (`board_id`)
- `thread_created` — a thread is started on the board (`board_id`, `thread_id`, `topic`)
- `thread_published` — the thread becomes visible to link recipients (`visibility`)
- `reply_posted` — a reply lands on a thread (`reply_id`, `reply_kind`)
- `reply_reacted` — a recipient reacts to a reply (`reaction`); carries no account

## Questions the PM will ask
- Threads per board, and replies per thread.
- Which `topic` produces the most replies per thread?
- Reaction rate per reply, split by `reply_kind`.
- What fraction of reactions come from people with no account?
