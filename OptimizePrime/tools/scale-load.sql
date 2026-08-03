-- ============================================================================
-- tools/scale-load.sql — generate ONE synthetic event stream, server-side.
--
-- > Summary: `INSERT INTO ev_raw SELECT ... FROM numbers_mt({S})`, three nested
-- > levels — session, beat, burst. Every random draw is `cityHash64(sid, salt)`,
-- > so the stream is DETERMINISTIC: the same {S}/{SEED} regenerates byte-for-byte.
-- > Reads the vocabularies built by tools/scale-gen.sql. Parameters:
-- >   {S} sessions to emit · {SEED} hash salt · {NC} distinct content ids in play.
-- > Driver: tools/scale-test.sh. There is NO external generator; this is it.
--
-- WHY A GENERATOR AND NOT A COPY. Replaying the provided file N times with
-- re-keyed session ids would leave every event on the SAME minute with the SAME
-- dimension tuple, so `cc_minute_delta` would not gain a single row and the
-- serving layer would look free. That measures the copy, not the design. Here
-- each session gets its own start second inside its hour, its own length, its
-- own runs and its own pauses — so minute-grain cardinality grows the way it
-- would in production, and the ADR 0008 row ceiling gets a real test.
--
-- THE THREE LEVELS
--   L1  one row per SESSION — start time, dimensions, and the array of beat
--                             timestamps (a >150 s step opens a new run)
--   L2  one row per BEAT    — burst size and the pause/resume flags, all pure
--                             functions of (sid, beat), so no state is carried
--   L3  one row per EVENT   — the burst expanded, dimensions attached
--
-- SALTS are 1,000,000 apart on purpose. A beat index reaches ~590 at the
-- longest session, so adjacent salt bases would make one beat's pause draw the
-- same number as a distant beat's gap draw — a silent correlation.
-- ============================================================================

INSERT INTO ev_raw
    (content_id, video_session_id, user_id, event_type, event, event_timestamp,
     platform, app_version, country, audio_language, subtitle_language,
     player_version, session_start_epoch)

WITH
    -- Deterministic uniform on [0,1): 53 mantissa bits out of a cityHash64, so
    -- two salts on the same session are independent draws and the whole stream
    -- is a pure function of ({S}, {SEED}).
    (a, k) -> bitShiftRight(cityHash64(a, k, {SEED:UInt64}), 11) * pow(2, -53) AS U,
    (a, k1, k2) -> sqrt(-2 * log(greatest(U(a, k1), 1e-12))) * cos(2 * pi() * U(a, k2)) AS N01,
    -- arrayFirstIndex returns 0 when nothing matches, and a[0] throws. The CDF
    -- ends at 1.0 in exact arithmetic but is a float sum, so clamp rather than
    -- trust it.
    (u, cdf) -> greatest(1, arrayFirstIndex(x -> x >= u, cdf)) AS PICK,

    -- The MODEL's gap threshold, read from the one declaration (ADR 0032).
    -- This generator synthesises "big gaps" as GAP_S + a lognormal excess, so
    -- it manufactures exactly the silences the model is tuned to split on.
    -- While that was a literal 150 here, the scale evidence could not detect a
    -- GAP_S mismatch at all — the generator produced gap structure defined by
    -- the same threshold the model was being tested against
    -- (docs/DYNAMIC_PARAMS.md §D1). Sharing one declaration does not remove
    -- the circularity, but it makes it a single visible fact instead of two
    -- numbers that happen to agree.
    (SELECT gap_s FROM v_model_policy) AS GAP_S,

    -- ---- fitted constants (provided-file measurement -> value) -------------
    3.4    AS BURST_MEAN,       -- 905,558 events over ~267k beats
    53.0   AS SESS_MEDIAN,      -- events per session, p50 = 53
    0.951  AS SESS_SIGMA,       -- so mean = 53*exp(sigma^2/2) = 83.3, the real mean
    0.0153 AS P_BIG_GAP,        -- 0.376 gaps >150 s per session over 24.6 beats
    223.0  AS BIG_GAP_MEDIAN,   -- median excess over 150 s (real median gap 373 s)
    1.417  AS BIG_GAP_SIGMA,    -- so mean excess 609 s (real mean big gap 759 s)
    0.102  AS P_PAUSE,          -- 2.516 pauses per session over 24.6 beats
    0.23   AS P_PAUSE_UNCLOSED, -- ADR 0007: 23% of pauses never resume
    0.060  AS P_BARE_RESUME,    -- real resumes 31,780 > pauses 27,340 (§B.4)
    0.885  AS P_OWN_USER,       -- 9,618 users over 10,866 sessions
    3.4    AS CONTENT_ZIPF,     -- so rank 1 takes ~9% of events, as it really does
    0.18   AS P_BLANK_SENTINEL, -- 1,991 of 10,880 starts carry '' rather than 'unk'

    -- ---- vocabularies (scalar subqueries: evaluated ONCE per query) --------
    -- Each is re-sorted by idx INSIDE an array rather than by an ORDER BY under
    -- groupArray, which does not promise to honour it across threads. A value
    -- array mis-paired with its CDF array yields plausible garbage.
    -- 65,536-slot session-start LUT at MINUTE grain (tools/scale-gen.sql
    -- explains why hour grain was not good enough). O(1) per session.
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, minute_epoch)))) FROM gen_start) AS start_v,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'platform')          AS plat_v,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'platform')          AS plat_c,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'country')           AS ctry_v,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'country')           AS ctry_c,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'app_version')       AS app_v,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'app_version')       AS app_c,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'player_version')    AS ply_v,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'player_version')    AS ply_c,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'audio_language')    AS aud_v,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'audio_language')    AS aud_c,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'subtitle_language') AS sub_v,
    (SELECT arrayMap(x -> x.2,           arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'subtitle_language') AS sub_c,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((rank, content_id)))) FROM gen_content WHERE rank <= {NC:UInt32})       AS cont_v,
    -- 4,096-slot event LUT: an O(1) array index per event. An inverse-CDF scan
    -- here would be O(30) comparisons on every one of 90M rows.
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, event))))      FROM gen_ev) AS ev_lut,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, event_type)))) FROM gen_ev) AS et_lut

SELECT
    content_id,
    video_session_id,
    user_id,
    -- The model reads only `event_type = 'VideoSessionEnd'` (is_open) and
    -- `event_type IN ('VideoHeartbeat','VideoPlay')` (the stateless MV); the
    -- rest of the vocabulary exists so the STORAGE numbers are honest.
    multiIf(is_first, 'VideoSessionStart',
            is_last,  'VideoSessionEnd',
            is_pause_ev OR is_resume_ev, 'VideoHeartbeat',
            et_lut[lut_slot])                                       AS event_type,
    multiIf(is_first, 'VideoSessionStart',
            is_last,  'VideoSessionEnd',
            is_pause_ev,  'pause',
            is_resume_ev, 'resume',
            ev_lut[lut_slot])                                       AS event,
    toDateTime64(bt + ((cityHash64(sid, bi, k, {SEED:UInt64}) % 1000) / 1000.0), 3) AS event_timestamp,
    platform,
    app_version,
    country,
    -- The sentinel-then-resolved behaviour ADR 0008 is built around: the first
    -- beat reports before the player has resolved a track, so essentially every
    -- session carries more than one raw audio/subtitle value and `any()` picks
    -- the sentinel. Reproducing it is what makes the dominant-value attribution
    -- in 30_build_intervals.sql do real work at scale.
    if(bi = 1, if(U(sid, 11) < P_BLANK_SENTINEL, '', 'unk'), audio_resolved)  AS audio_language,
    if(bi = 1, if(U(sid, 12) < P_BLANK_SENTINEL, '', 'unk'), sub_resolved)    AS subtitle_language,
    player_version,
    session_start_epoch
FROM
(
    -- ================= L3: one row per EVENT ==============================
    SELECT
        sid, bi, bt, nb, bsz, k,
        content_id, video_session_id, user_id, platform, app_version, country,
        player_version, audio_resolved, sub_resolved, session_start_epoch,
        (bi = 1)  AND (k = 0)         AS is_first,
        (bi = nb) AND (k = (bsz - 1)) AS is_last,
        -- pause takes slot 0 of its burst, resume the last slot, so a burst of
        -- one that draws both keeps the pause. Rare and deliberate: an
        -- unresumed pause is the conservative reading (ADR 0007).
        is_pause_beat  AND (k = 0)                             AS is_pause_ev,
        is_resume_beat AND (k = (bsz - 1)) AND NOT is_pause_ev AS is_resume_ev,
        1 + toUInt32(cityHash64(sid, bi, k, {SEED:UInt64}) % 4096) AS lut_slot
    FROM
    (
        -- ================= L2: one row per BEAT ===========================
        SELECT
            sid, bi, bt, nb,
            content_id, video_session_id, user_id, platform, app_version, country,
            player_version, audio_resolved, sub_resolved, session_start_epoch,
            -- burst size ~ 1 + Exp(mean 2.4) => mean 3.4, which is why the real
            -- inter-arrival p50 is 0 s while p90 is 40 s
            -- round(), not floor(): flooring an exponential costs half a
            -- unit of mean and put the whole stream 15% under the real event
            -- count on the first calibration run.
            least(20, 1 + toUInt32(round(-(BURST_MEAN - 1) * log(greatest(U(sid, 5000000 + bi), 1e-12))))) AS bsz,
            -- pause / resume are PURE FUNCTIONS of (sid, beat), so a resume can
            -- look back at whether beat bi-d was an unresolved pause without any
            -- state being carried through the array joins.
            U(sid, 6000000 + bi) < P_PAUSE AS is_pause_beat,
            (
                ((bi > 1) AND (U(sid, 5999999 + bi) < P_PAUSE) AND ((cityHash64(sid, 6999999 + bi, {SEED:UInt64}) % 3) = 0) AND (U(sid, 7999999 + bi) >= P_PAUSE_UNCLOSED))
             OR ((bi > 2) AND (U(sid, 5999998 + bi) < P_PAUSE) AND ((cityHash64(sid, 6999998 + bi, {SEED:UInt64}) % 3) = 1) AND (U(sid, 7999998 + bi) >= P_PAUSE_UNCLOSED))
             OR ((bi > 3) AND (U(sid, 5999997 + bi) < P_PAUSE) AND ((cityHash64(sid, 6999997 + bi, {SEED:UInt64}) % 3) = 2) AND (U(sid, 7999997 + bi) >= P_PAUSE_UNCLOSED))
             -- §B.4: the file carries MORE resumes (31,780) than pauses
             -- (27,340) — `resume` is overloaded, so some pair with nothing.
             -- Reproduced rather than tidied away.
             OR (U(sid, 9000000 + bi) < P_BARE_RESUME)
            ) AS is_resume_beat
        FROM
        (
            -- ================= L1: one row per SESSION ====================
            SELECT
                sid, nb, beat_ts, platform, country, app_version, player_version,
                audio_resolved, sub_resolved, content_id, video_session_id,
                user_id, session_start_epoch
            FROM
            (
                SELECT
                    number AS sid,

                    -- Start MINUTE drawn from the real session-start histogram,
                    -- then uniform inside the minute. This is the line that keeps
                    -- 88% of the load inside two hours — and, because it is
                    -- minute grain rather than hour grain, that reproduces the
                    -- intra-hour spike the peak number actually comes from.
                    toUInt32(start_v[1 + toUInt32(cityHash64(number, 1, {SEED:UInt64}) % 65536)]
                             + floor(U(number, 2) * 60)) AS t0,

                    -- events per session ~ LogNormal(median 53, mean 83.3)
                    least(2000, greatest(3, toUInt32(round(SESS_MEDIAN * exp(SESS_SIGMA * N01(number, 3, 4)))))) AS nev,
                    greatest(1, toUInt32(round(nev / BURST_MEAN))) AS nb,

                    -- Beat spacing: 40-41 s normally. The real inter-arrival mean
                    -- of 11.83 s over 3.4 events per beat implies a 40.2 s beat,
                    -- which is where that range comes from. With P_BIG_GAP the
                    -- step instead becomes a >150 s silence — exactly what
                    -- 30_build_intervals.sql splits a run on.
                    --
                    -- Capped at 3,600 s so a lognormal tail cannot walk a session
                    -- out of the generated window. The cap trims the top ~1% of
                    -- big gaps (real p99 = 6,539 s) and is the one place this
                    -- generator is knowingly narrower than the real file.
                    arrayMap(x -> t0 + x, arrayCumSum(arrayMap(j -> if(j = 1, toUInt32(0),
                        if(U(number, 1000000 + j) < P_BIG_GAP,
                           least(toUInt32(3600), toUInt32(GAP_S + round(exp(log(BIG_GAP_MEDIAN) + (BIG_GAP_SIGMA * N01(number, 2000000 + j, 3000000 + j)))))),
                           toUInt32(40 + floor(U(number, 4000000 + j) * 2)))
                        ), range(1, nb + 1)))) AS beat_ts,

                    -- Dimensions are per SESSION: 0 of the 10,866 real sessions
                    -- carry two app_versions, 1 carries two content_ids, 95 carry
                    -- two platforms. Inverse CDF is O(|vocab|) but runs ONCE PER
                    -- SESSION, never per event.
                    plat_v[PICK(U(number, 21), plat_c)] AS platform,
                    ctry_v[PICK(U(number, 22), ctry_c)] AS country,
                    app_v[PICK(U(number, 23), app_c)]   AS app_version,
                    ply_v[PICK(U(number, 24), ply_c)]   AS player_version,
                    aud_v[PICK(U(number, 25), aud_c)]   AS audio_resolved,
                    sub_v[PICK(U(number, 26), sub_c)]   AS sub_resolved,

                    -- Popularity is Zipf-shaped: rank = 1 + floor(NC * u^3.4)
                    -- puts ~9% of events on rank 1, the share the top title
                    -- takes in the provided file (81,517 of 905,558).
                    cont_v[1 + least({NC:UInt32} - 1, toUInt32(floor({NC:UInt32} * pow(U(number, 27), CONTENT_ZIPF))))] AS content_id,

                    -- 64-char uppercase hex, the shape of the real ids. Short
                    -- synthetic keys would flatter every storage number here.
                    hex(SHA256(concat('sess:', toString(number), ':', toString({SEED:UInt64})))) AS video_session_id,
                    hex(SHA256(concat('user:', toString(
                        if(U(number, 7) < P_OWN_USER, number,
                           toUInt64(floor(U(number, 8) * greatest(1, intDiv({S:UInt64}, 50)))))
                    )))) AS user_id,

                    toDateTime64(t0, 3) AS session_start_epoch
                FROM numbers_mt({S:UInt64})
            )
        )
        ARRAY JOIN
            beat_ts                 AS bt,
            arrayEnumerate(beat_ts) AS bi
    )
    ARRAY JOIN range(bsz) AS k
);
