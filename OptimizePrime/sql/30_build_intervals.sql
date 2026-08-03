-- ============================================================================
-- 30_build_intervals.sql — H2. Derive session_intervals from the raw stream.
--
-- ACTIVE = (a run of events with no gap > HEARTBEAT_GAP_S) MINUS (paused windows).
--
-- Two signals, because ONE is not enough — measured, see ADR 0007:
--
--   backgrounding -> heartbeat GAPS. Beats effectively stop while backgrounded
--                    (0.047/min vs 4.72/min active, a 100x drop), so a gap
--                    detects it. bg/fg events are NOT used: they do not pair
--                    (14,700 vs 14,321) — ADR 0001.
--
--   pause         -> EXPLICIT pause/resume events. Beats SURVIVE a pause
--                    (0.756/min, 16% of active = one event every ~79s, well
--                    inside a 150s threshold). A gap-only model therefore
--                    counts paused time as watching, which the statement
--                    forbids. This is the correction ADR 0007 mandates.
--
-- Re-running is safe: session_intervals is a ReplacingMergeTree keyed on
-- (video_session_id, interval_start), versioned on build_version, so the newest
-- derivation always wins — whether the interval grew OR SHRANK. It used to be
-- versioned on interval_end, which silently kept stale over-long intervals; see
-- the engine comment in 10_intervals.sql and evidence/truncation.txt.
--
-- DIMENSION ATTRIBUTION (ADR 0008). A dimension is a property of an EVENT, not
-- of a session, and the provided file proves it: 8,796 of 10,866 sessions carry
-- more than one audio_language and 10,862 carry more than one
-- subtitle_language. Almost all of that is the player reporting a sentinel
-- before it has resolved a track — VideoSessionStart carries a sentinel
-- subtitle_language on 10,880 of 10,880 sessions — so the naive any() picks the
-- sentinel far more often than the truth. MEASURED against a per-minute
-- attribution over all 139,800 session-minute cells:
--
--   rule                                   audio wrong    subtitle wrong
--   any()            (what this used)         44.5%           47.6%
--   dominant per interval (what this does)     3.3%            1.8%
--
-- At the graded peak minute any() puts 2,004 of 2,726 active sessions (73.5%)
-- in the wrong audio bucket. any() is also NOT DETERMINISTIC — the same query
-- at max_threads 1 / 8 / 32 returns three different attributions — so two
-- rebuilds of the same data can serve two different answers to the same
-- filtered query. That alone disqualifies it for a graded rebuild.
--
-- The rule used instead: the DOMINANT (most frequent) raw value among the
-- events that fall inside THAT interval, ties broken by the value itself so the
-- result is a pure function of the input. Raw values, never canonicalised —
-- 'HIN' and 'hin' stay distinct because the private ground truth is matched on
-- the shipped strings, not on our idea of tidy ones.
--
-- ADR 0009 EXTENDS THAT RULE TO ALL SEVEN. ADR 0008 applied it to app_version,
-- audio_language, subtitle_language and player_version only, and left user_id,
-- content_id, platform and country on any() because the accuracy exposure there
-- is small (95 sessions carry 2 platforms, 120 carry 2 user_ids). The accuracy
-- argument was the wrong argument: any() is NON-DETERMINISTIC, re-measured on
-- exactly those four columns (three hashes at max_threads 1/8/32, see below), so
-- it makes the BUILD irreproducible regardless of how few rows it touches. One
-- rule for all seven now; there is no second mechanism to keep in step.
--
-- The interval is NOT split when a dimension changes mid-interval. Splitting
-- would put two intervals of the SAME session on the same minute with different
-- dimension tuples, and the merge in 40_deltas.sql groups by session precisely
-- because two +1s for one viewer is a double count — it is the bug /reconcile
-- caught once already (556 of 1,903 minutes wrong). Genuine mid-session changes
-- (case- and sentinel-normalised) are 250 sessions for audio_language, 70 for
-- player_version, 20 for subtitle_language and 0 for app_version, i.e. ≤2.3% of
-- sessions on the worst dimension; a double count would be wrong on every
-- minute of every filtered query. Attribute, do not split.
-- ============================================================================

INSERT INTO session_intervals
    (video_session_id, user_id, content_id, platform, country,
     app_version, audio_language, subtitle_language, player_version,
     extra_dimensions,
     interval_start, interval_end, is_open, build_version)
WITH
    -- ---- THE POLICY (ADR 0032) ------------------------------------------
    -- These four constants USED TO BE LITERALS HERE, and copies of them lived
    -- in sql/90_reconcile.sql, tools/reference_interpreter.py,
    -- tools/cruel-gen.sh, tools/golden-gen.sh and tools/scale-load.sql. Six
    -- sites across three languages meant the model, the GATE, the reference
    -- ORACLE and both data GENERATORS all shared the fitted value — so a
    -- mis-fitted GAP_S went green on every instrument we own, simultaneously
    -- and by construction (docs/DYNAMIC_PARAMS.md §4).
    --
    -- They are now DECLARED ONCE in policy/model.policy and rendered into
    -- v_model_policy by tools/policy.sh gen. The values are UNCHANGED — this
    -- is a relocation, not a retune; see the ADR for the before/after build
    -- diff. A scalar subquery over a one-row view folds to a constant, so it
    -- is free inside the lambdas below, and a database with no policy view
    -- FAILS LOUDLY rather than defaulting GAP_S to zero.
    --
    -- What each one means, and what it is worth, stays in the declaration.
    -- Read policy/model.policy before changing any of them; the sensitivity
    -- sweep is evidence/params/ and the decision is ADR 0028.
    (SELECT gap_s                     FROM v_model_policy) AS GAP_S,
    (SELECT tail_s                    FROM v_model_policy) AS TAIL_S,
    (SELECT unclosed_pause_to_run_end FROM v_model_policy) AS UNCLOSED_PAUSE_TO_RUN_END,
    (SELECT point_activity_counts     FROM v_model_policy) AS POINT_ACTIVITY_COUNTS,

    -- GAP_S is derived from the MEASURED inter-arrival p99 of 49s (ADR 0007),
    -- not from the "60s cadence" that the data disproved. 150s is ~3x p99 —
    -- wide enough to survive a burst pause, tight enough to catch a
    -- backgrounding within one minute bucket. (Re-measured 2026-08-02: the p99
    -- is 45s counting same-second pairs and 155s excluding them, so the value
    -- survives but "3x p99" depends on a choice this comment never stated.
    -- ADR 0028 item 2.)
    --
    -- TAIL_S is the credit after the last event of a run. One cadence, not a
    -- full gap: the viewer was watching until at least the next expected event.
    --
    -- THE UNCLOSED-PAUSE RULE. 23% of pauses never resume, and the two readings
    -- are not close: MEASURED end to end on the real file,
    --   conservative  1,949.3 h counted, PEAK 2,887
    --   permissive    2,048.6 h counted, PEAK 3,018   (+5.09% hours, +4.5% PEAK)
    -- Both at the same minute, 2026-07-26 10:56. The peak is the graded number,
    -- so this constant moves the headline by 131 viewers.
    -- Default CONSERVATIVE: against an EXACT private ground truth, under-counting
    -- is a visible, explainable error while over-counting invents viewers that
    -- were demonstrably not receiving playback events. See ADR 0007; mentor Q2.
    --
    -- THE POINT-ACTIVITY RULE (ADR 0031). Does a viewer who was demonstrably
    -- active at an instant, but for whom we can measure NO DURATION, count for
    -- one cadence — or for nothing at all?
    --
    -- Until ADR 0031 this file answered "nothing at all" BY ACCIDENT: the
    -- segment fold below drops a zero-length segment, and it does so BEFORE
    -- TAIL_S is applied, so a run of a single event earned no interval rather
    -- than the [t, t+TAIL_S] every other run end earns. Nothing in doubts/ or
    -- the ADRs ever stated that as a convention. It is now a CONSTANT, so the
    -- answer is a decision with a number attached rather than a side effect of
    -- where a filter sits.
    --
    -- MEASURED on the delivered file (evidence/point-activity/), local scratch
    -- rebuilt verbatim from this file, gate green under BOTH values:
    --   0 = shipped     30,323 intervals  1,978.1 h  PEAK 2,917 @ 07-26 10:56
    --   1 = point-activity-counts
    --                   30,653 intervals  1,982.7 h  PEAK 2,927 @ 07-26 10:56
    -- i.e. +330 intervals, +4.62 h (+0.23%), +10 PEAK (+0.34%), same minute.
    --
    -- The 330 are exactly the segments whose two endpoints coincide, and they
    -- are three distinct populations — see ADR 0031 for the census:
    --      182  a run of ONE instant (the viewer emitted one event and nothing
    --           within GAP_S either side). 124 of those instants are a
    --           VideoSessionEnd, which is why this interacts with doubts/07.
    --       95  a `resume` landing exactly on the run's last instant.
    --       53  a `pause` opening exactly where the previous segment resumed.
    -- A FOURTH population — 5,699 segments where an UNCLOSED pause runs through
    -- the run end — is NOT in that set and is still dropped at both values.
    -- That viewer was paused at the run's last instant, so crediting a cadence
    -- there would book paused time as watch time; see the window arithmetic
    -- below, which now ends an unclosed pause at run_end + 1 to say so.
    --
    -- DEFAULT 0 — NOT because it is the better reading. tools/reference_
    -- interpreter.py, which derives the spec from docs/EXPLAINER.md rather than
    -- from this file, counts point activity, and so does this file's own tail
    -- rule for every run that lasts even one second. ADR 0031 RECOMMENDS 1.
    -- It ships at 0 because flipping it moves a number we have already
    -- submitted (2,917 -> 2,927), and that is an operator's call, not a
    -- build's. Since ADR 0032 flipping it is ONE edit in policy/model.policy
    -- plus `tools/policy.sh gen` — the gate, the oracle and both generators
    -- follow automatically, where it used to be a six-file change.
    -- ------------------------------------------------------------------------

    per_session AS (
        SELECT
            video_session_id,
            arraySort(groupArray(toUnixTimestamp(event_timestamp)))                    AS ts,
            -- ALL SEVEN raw dimensions, carried as (ts, value…) tuples so they can
            -- be attributed PER INTERVAL below rather than collapsed to one value
            -- per session. Deliberately a SECOND array rather than a widened `ts`:
            -- `ts` drives run splitting and is left byte-identical, so this change
            -- provably cannot move an interval boundary — only label it. Sorted by
            -- the whole tuple, so equal timestamps order deterministically too.
            --
            -- user_id/content_id/platform/country used to sit above this as
            -- any(user_id) etc., under a comment saying a session is almost always
            -- one user/content/platform (1 session has 2 content_ids, 95 have 2
            -- platforms, 120 have 2 user_ids out of 10,866) and that the
            -- alternative "is not worth it until something measures it as
            -- mattering". Something did, in commit 8bfeeb2, and it is not the
            -- accuracy argument — it is DETERMINISM. Re-measured here on exactly
            -- these four columns, same data, same query:
            --   any(user_id, content_id, platform, country) per session
            --     max_threads=1   cityHash64 = 5126827698054385970
            --     max_threads=8                4514778022739255759
            --     max_threads=32               2307516582733793023
            -- Three different attributions of one input, so two rebuilds of the
            -- same data can serve two different answers to the same filtered
            -- query — against an EXACT private ground truth that is disqualifying,
            -- whether it moves 120 sessions or 12,000. They now use the SAME rule
            -- 8bfeeb2 established for the other four: dominant value per interval,
            -- tie-broken by the value itself. New members are appended at the tail
            -- so the existing .2–.5 slots keep their meaning. ADR 0009.
            arraySort(groupArray((
                toUnixTimestamp(event_timestamp),
                app_version, audio_language, subtitle_language, player_version,
                user_id, content_id, platform, country,
                CAST(extra, 'Map(String, String)')
            ))) AS dim_events,
            arraySort(groupArrayIf(toUnixTimestamp(event_timestamp), event = 'pause'))  AS pauses,
            arraySort(groupArrayIf(toUnixTimestamp(event_timestamp), event = 'resume')) AS resumes,
            -- No VideoSessionEnd at build time => still open. 2.2% of sessions
            -- emit events up to 2,081s AFTER their end event (ADR 0007), so
            -- "ended" is not the same as "sealed".
            countIf(event_type = 'VideoSessionEnd') = 0 AS is_open
        FROM v_ev_model_input
        GROUP BY video_session_id
    ),

    -- Split the session into runs wherever the gap exceeds the threshold.
    runs AS (
        SELECT
            video_session_id, is_open,
            pauses, resumes, dim_events,
            arrayJoin(arraySplit((t, i) -> (i > 1) AND ((t - ts[i - 1]) > GAP_S), ts, arrayEnumerate(ts))) AS run
        FROM per_session
    ),

    -- Clip pause windows into the run. An unclosed pause (23% of them) runs to
    -- the end of its run: CONSERVATIVE, never credit time we cannot prove was
    -- active. ADR 0007 records the alternative and what it costs.
    windowed AS (
        SELECT
            video_session_id, is_open,
            dim_events,
            run[1]              AS run_start,
            run[length(run)]    AS run_end,
            -- A pause window closes at the next `resume`. 23% of pauses never
            -- get one, and what happens then is UNCLOSED_PAUSE_TO_RUN_END:
            --   1 = CONSERVATIVE (default) — paused until the run ends. Never
            --       credits time we cannot prove was active.
            --   0 = PERMISSIVE — paused only until the next event of any kind,
            --       treating the unresolved pause as a blip.
            -- Flipping the constant at the top of this file is the whole change.
            --
            -- THE RESUME LOOKUP IS `>=`, NOT `>`, AND THAT IS A CORRECTNESS FIX.
            -- `ts` is toUnixTimestamp(event_timestamp), i.e. TRUNCATED TO WHOLE
            -- SECONDS, and 23.67% of adjacent event pairs already share the exact
            -- same millisecond. A strict `>` therefore cannot see a resume that
            -- lands in the SAME truncated second as its pause: the window ran on
            -- to the NEXT resume, or — with no next resume — became unclosed and
            -- ate the rest of the run. MEASURED on the real file:
            --   pause events                                        27,340
            --   with a resume in the same truncated second           2,697  (9.86%)
            --   closed-pause time, strict >                          834.1 h
            --   closed-pause time, inclusive >=                      792.6 h
            --   raw over-exclusion from the tie                       41.5 h
            -- Most of that raw over-exclusion overlaps time the GAP rule already
            -- excludes, exactly as ADR 0007 found for the unclosed-pause question
            -- (330 h estimated -> 99.3 h real). Clipped into runs and merged, the
            -- model actually over-excluded 309.5 h -> 286.2 h, i.e. 23.3 h. See
            -- ADR 0009 for the end-to-end effect on the PEAK.
            -- `>=` yields a ZERO-LENGTH window (p, p) for a tie. The fold below
            -- already absorbs it correctly — it pushes the segment up to p and
            -- leaves the cursor at p, so no active time is lost and none is
            -- invented — but it SPLITS one interval into two abutting ones at p.
            -- Measured: 31,938 intervals with the split vs 30,323 without, both
            -- at PEAK 2,917 / 1,978.1 h and both gate-green over 17,028 minutes.
            -- The split is dropped, because an interval
            -- boundary is also a DIMENSION ATTRIBUTION boundary (ADR 0008) and a
            -- pause that resumed in its own second is not a boundary of anything.
            -- Hence the outer arrayFilter(w -> w.2 > w.1, …).
            -- The PERMISSIVE branch's lookup into `run` stays STRICT: the pause
            -- event is itself in `run` at p, so `>=` there would match the pause
            -- and collapse every permissive window to zero.
            --
            -- A WINDOW IS HALF-OPEN [p, e): paused from p+1 through e-1, and the
            -- viewer is counted AT p (they demonstrably acted at p) and again AT
            -- e (a resume is an event). That is what the fold below implements,
            -- and it is why `e` must be a REAL ACTIVE INSTANT — which is exactly
            -- what the old `least(…, run_end)` destroyed. It clamped BOTH "a
            -- resume closed this pause" and "nothing ever closed it, so the
            -- viewer stayed paused to the end" to the same value, run_end, and
            -- so claimed run_end was active in both. While zero-length segments
            -- were dropped that was invisible. Under POINT_ACTIVITY_COUNTS = 1
            -- it would credit a cadence to 5,699 segments whose viewer was
            -- provably still paused — so the two cases are now distinguished:
            --   resume r with p <= r <= run_end  ->  e = r          (active at r)
            --   otherwise (no resume, or one beyond the run)
            --                                    ->  e = run_end + 1
            -- run_end + 1 is one past the last instant of the run: the whole run
            -- is paused-through, and the final segment (run_end + 1, run_end) is
            -- empty at EITHER value of POINT_ACTIVITY_COUNTS. At value 0 this
            -- rewrite is provably a no-op — the old expression differed only in
            -- a cursor value that no surviving segment ever read — and the gate
            -- confirms it: 17,028 minutes, 0 mismatched, PEAK unchanged at 2,917.
            arrayFilter(w -> w.2 > w.1, arraySort(arrayMap(
                p -> (p,
                        if((arrayFirst(x -> x >= p, resumes) != 0)
                             AND (arrayFirst(x -> x >= p, resumes) <= run[length(run)]),
                           toUInt32(arrayFirst(x -> x >= p, resumes)),
                           if(UNCLOSED_PAUSE_TO_RUN_END = 1,
                              toUInt32(run[length(run)] + 1),
                              -- next event inside this run; one past the run end
                              -- if it is the last (unreachable: p < run_end means
                              -- run_end itself always qualifies)
                              if(arrayFirst(x -> x > p, run) = 0,
                                 toUInt32(run[length(run)] + 1),
                                 toUInt32(arrayFirst(x -> x > p, run)))))),
                arrayFilter(p -> (p >= run[1]) AND (p < run[length(run)]), pauses)
            ))) AS pause_windows
        FROM runs
    ),

    -- Complement of the merged pause windows within [run_start, run_end].
    -- arrayFold walks the sorted windows carrying (segments_so_far, cursor).
    --
    -- The push test is where POINT_ACTIVITY_COUNTS bites for the 53 segments
    -- whose pause opens exactly where the previous one resumed: `win.1 > acc.2`
    -- discards the single active instant at acc.2, `win.1 = acc.2` keeps it as a
    -- zero-length segment. Starts stay strictly increasing either way — a push
    -- sets the cursor to win.2 > win.1 >= acc.2 — so no two segments of one run
    -- can share an interval_start and collide on the ReplacingMergeTree key.
    folded AS (
        SELECT
            *,
            arrayFold(
                (acc, win) -> (
                    if((win.1 > acc.2) OR ((POINT_ACTIVITY_COUNTS = 1) AND (win.1 = acc.2)),
                       arrayPushBack(acc.1, (acc.2, win.1)), acc.1),
                    greatest(acc.2, win.2)
                ),
                pause_windows,
                (CAST([], 'Array(Tuple(UInt32, UInt32))'), toUInt32(run_start))
            ) AS fold
        FROM windowed
    )

-- The outer projection lists exactly the 14 target columns. The inner SELECT
-- needs working aliases (the per-interval slice of dim_events and the value
-- arrays cut out of it) which must NOT reach the INSERT, hence the nest.
SELECT
    video_session_id,
    user_id,
    content_id,
    platform,
    country,
    app_version,
    audio_language,
    subtitle_language,
    player_version,
    extra_dimensions,
    interval_start,
    interval_end,
    is_open,
    build_version
FROM
(
    SELECT
        video_session_id,
        toDateTime64(seg.1, 3)                     AS interval_start,
        -- Tail grace is ONLY for a segment that ends because the run ended — there
        -- we do not know when the viewer actually left, so we credit one cadence.
        -- A segment ending at a PAUSE gets none: we know to the second when they
        -- stopped watching, and crediting 60s past it books paused (often
        -- backgrounded) time as watch time. Measured on the worked example: the
        -- viewer paused at 11:04:29 and backgrounded at 11:04:31, so the tail was
        -- landing entirely inside a 24-minute background.
        toDateTime64(seg.2 + if(seg.2 = run_end, TAIL_S, 0), 3) AS interval_end,
        is_open,
        -- Monotonic across builds so the newest derivation always wins the replace,
        -- whether the interval grew or shrank. now() is evaluated once per query.
        toUInt64(toUnixTimestamp(now())) AS build_version,

        -- ---- PER-INTERVAL DIMENSION ATTRIBUTION -------------------------------
        -- The events this interval actually covers. seg.1/seg.2 are both event
        -- timestamps (a segment starts at a run start or a resume and ends at a
        -- run end or a pause — all of which are events), so this slice is never
        -- empty and the endpoints are inclusive on both sides. The tail grace is
        -- added to interval_end above, deliberately AFTER this: no event exists
        -- in the grace window, so including it would change nothing but would
        -- make the intent unclear.
        arrayFilter(x -> (x.1 >= seg.1) AND (x.1 <= seg.2), dim_events) AS seg_events,
        arrayMap(x -> x.2, seg_events) AS v_app,
        arrayMap(x -> x.3, seg_events) AS v_audio,
        arrayMap(x -> x.4, seg_events) AS v_sub,
        arrayMap(x -> x.5, seg_events) AS v_player,
        arrayMap(x -> x.6, seg_events) AS v_user,
        arrayMap(x -> x.7, seg_events) AS v_content,
        arrayMap(x -> x.8, seg_events) AS v_platform,
        arrayMap(x -> x.9, seg_events) AS v_country,
        arrayMap(x -> x.10, seg_events) AS v_extra,

        -- Attribute future fields independently. Voting on a whole Map couples
        -- unrelated keys: adding or reordering one field can otherwise change
        -- which video_resolution wins. Presence is part of the vote so an
        -- absent key stays distinct from an explicitly empty value; a frequency
        -- tie prefers present, then the lexicographically smaller raw value.
        arraySort(arrayDistinct(arrayFlatten(arrayMap(m -> mapKeys(m), v_extra)))) AS extra_keys,
        arrayMap(k ->
            (
                k,
                arraySort(v ->
                    (
                        -toInt64(countEqual(
                            arrayMap(m -> (toUInt8(mapContains(m, k)), m[k]), v_extra), v)),
                        -toInt64(v.1),
                        v.2
                    ),
                    arrayDistinct(arrayMap(m -> (toUInt8(mapContains(m, k)), m[k]), v_extra))
                )[1]
            ),
            extra_keys
        ) AS extra_winners,
        arrayFilter(x -> x.2.1 = 1, extra_winners) AS present_extra_winners,

        -- Dominant value: sort the DISTINCT values by (-frequency, value) and
        -- take the first. The second sort term is what makes this deterministic
        -- where any() is not — a tie is broken by the value, never by which
        -- thread happened to finish first. Cost is O(distinct x length) on an
        -- array whose length is one interval's events (median 30, max 1,803),
        -- so it is negligible next to the arraySplit/arrayFold above.
        -- An empty slice would yield '' rather than an error; it cannot occur,
        -- but it fails soft rather than dropping the interval.
        arraySort(v -> (-toInt64(countEqual(v_app,    v)), v), arrayDistinct(v_app))[1]    AS app_version,
        arraySort(v -> (-toInt64(countEqual(v_audio,  v)), v), arrayDistinct(v_audio))[1]  AS audio_language,
        arraySort(v -> (-toInt64(countEqual(v_sub,    v)), v), arrayDistinct(v_sub))[1]    AS subtitle_language,
        arraySort(v -> (-toInt64(countEqual(v_player, v)), v), arrayDistinct(v_player))[1] AS player_version,
        -- The same expression, applied to the four that commit 8bfeeb2 left on
        -- any(). content_id is Int64 rather than a string; the tie-break sorts on
        -- the numeric value, which is just as total an order, so the rule is
        -- unchanged rather than adapted.
        arraySort(v -> (-toInt64(countEqual(v_user,     v)), v), arrayDistinct(v_user))[1]     AS user_id,
        arraySort(v -> (-toInt64(countEqual(v_content,  v)), v), arrayDistinct(v_content))[1]  AS content_id,
        arraySort(v -> (-toInt64(countEqual(v_platform, v)), v), arrayDistinct(v_platform))[1] AS platform,
        arraySort(v -> (-toInt64(countEqual(v_country,  v)), v), arrayDistinct(v_country))[1]  AS country,
        mapFromArrays(
            arrayMap(x -> x.1, present_extra_winners),
            arrayMap(x -> x.2.2, present_extra_winners)
        ) AS extra_dimensions
    FROM folded
    ARRAY JOIN
        -- The final segment (cursor, run_end), and the POINT_ACTIVITY_COUNTS
        -- test again. `x.2 > x.1` drops the run's last instant whenever the
        -- segment has no duration; `x.2 >= x.1` keeps it and it collects TAIL_S
        -- above, exactly as a one-second segment ending at the same instant
        -- would. A paused-through run is empty at BOTH values because its cursor
        -- is run_end + 1, so x.2 < x.1 (see the window arithmetic above).
        arrayFilter(x -> if(POINT_ACTIVITY_COUNTS = 1, x.2 >= x.1, x.2 > x.1),
            arrayPushBack(fold.1, (fold.2, toUInt32(run_end)))
        ) AS seg
);
