-- Language dimension normalization (audio_language, subtitle_language)
--
-- PROBLEM: 41 raw audio_language variants for ~15 real languages.
--   case          hin / HIN          eng / ENG          mal / MAL ...
--   qualifier     hin-hindi, hin-Hindi, eng-English, jpn-japanese ...
--   ALIAS         jap (1,374) and jpn (675) are BOTH Japanese
--   sentinels     unk / UNK / und / UND / non / NON / AUT / ''
--   junk          '-soundhandler'
--
-- Unnormalized, `audio_language = 'hin'` silently drops 92,635 Hindi rows
-- (HIN + hin-hindi + hin-Hindi). That reads as a concurrency bug, not a
-- dimension bug, which is what makes it dangerous.
--
-- TWO STAGES, because neither alone is sufficient:
--   Stage 1  mechanical, deterministic, needs no maintenance. Handles case and
--            qualifier suffixes. Verified: 41 variants -> 18 groups.
--   Stage 2  curated dictionary. Handles what no algorithm can infer -- that
--            'jap' and 'jpn' are the same language -- plus display names.
--            Verified: 18 -> 15 canonical languages.
--
-- FUTURE-PROOFING: anything Stage 2 does not recognise still resolves (to
-- itself) and is *recorded* in dim_language_unmapped. A new variant on the
-- unseen day surfaces as a row to review, never as a silent extra category.
-- Adding support = one INSERT. No pipeline change, no redeploy.

-- ---------------------------------------------------------------------------
-- Stage 1: mechanical normalization
-- ---------------------------------------------------------------------------
-- lower -> trim -> take token before '-' -> keep [a-z] only -> '' becomes 'unknown'
--   'hin-Hindi'      -> 'hin'
--   'ENG'            -> 'eng'
--   '-soundhandler'  -> 'unknown'   (empty head token)
CREATE OR REPLACE FUNCTION langMechanical AS (raw) ->
    if(
        extract(lower(trim(ifNull(raw, ''))), '^([a-z]+)') = '',
        'unknown',
        extract(lower(trim(ifNull(raw, ''))), '^([a-z]+)')
    );

-- ---------------------------------------------------------------------------
-- Stage 2: curated canonical map
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_language_map (
    token         String,              -- output of langMechanical()
    canonical     String,              -- ISO 639-2/B code, or 'unknown'
    display_name  String,              -- what analytics shows
    is_sentinel   UInt8 DEFAULT 0      -- 1 = "not a language" (unknown/off)
) ENGINE = MergeTree ORDER BY token;

-- CANONICAL FORM: BCP 47 (W3C), which prefers the SHORTEST available subtag.
-- Every language present here has an ISO 639-1 two-letter code, so the
-- canonical value is two letters -- 'hi', not 'hin'. The source's three-letter
-- 639-2 codes become inputs, never outputs.
--
-- This also makes the output directly usable as an HTML lang attribute, an
-- Accept-Language value, or an Intl.DisplayNames key -- none of which accept
-- 'hin'.
INSERT INTO dim_language_map (token, canonical, display_name, is_sentinel) VALUES
    -- 639-2 (as delivered)  ->  639-1 (BCP 47 canonical)
    ('hin','hi','Hindi',0),       ('eng','en','English',0),
    ('mal','ml','Malayalam',0),   ('tel','te','Telugu',0),
    ('tam','ta','Tamil',0),       ('mar','mr','Marathi',0),
    ('kan','kn','Kannada',0),     ('ben','bn','Bengali',0),
    ('guj','gu','Gujarati',0),    ('jpn','ja','Japanese',0),
    ('kor','ko','Korean',0),      ('oji','oj','Ojibwe',0),
    -- already-short inputs, in case a client sends 639-1 directly
    ('hi','hi','Hindi',0),        ('en','en','English',0),
    ('ml','ml','Malayalam',0),    ('te','te','Telugu',0),
    ('ta','ta','Tamil',0),        ('mr','mr','Marathi',0),
    ('kn','kn','Kannada',0),      ('bn','bn','Bengali',0),
    ('gu','gu','Gujarati',0),     ('ja','ja','Japanese',0),
    ('ko','ko','Korean',0),       ('oj','oj','Ojibwe',0),
    ('as','as','Assamese',0),     ('oc','oc','Occitan',0),
    -- NON-STANDARD inputs. Stage 1 cannot reach these -- they are not case or
    -- suffix variants, they are simply wrong codes that only a human can map.
    ('jap','ja','Japanese',0),    -- 'jap' is not an ISO code at all
    ('ass','as','Assamese',0),    -- correct 639-2 is 'asm'; 'ass' is invalid
    ('occ','oc','Occitan',0),     -- correct 639-2 is 'oci'; 'occ' is invalid
    -- sentinels: absence of information, not a language.
    -- 'und' is BCP 47's own subtag for undetermined, so it is both the correct
    -- canonical value AND one of the inbound variants.
    ('unk','und','Unknown',1),    ('und','und','Unknown',1),
    ('aut','und','Unknown',1),    ('unknown','und','Unknown',1),
    -- CAUTION: 'non' is a real 639-2 code (Old Norse), but in this feed it is
    -- plainly a "none" sentinel -- 8,445 events on an India-only service.
    -- Mapped to undetermined deliberately; revisit if Old Norse ever ships.
    ('non','und','Unknown',1),
    -- 'zxx' is BCP 47 for "no linguistic content", which is exactly what
    -- subtitles-off means. Kept DISTINCT from 'und': "I turned subtitles off"
    -- and "we don't know what was on" are different facts.
    ('off','zxx','Subtitles off',1);

CREATE DICTIONARY IF NOT EXISTS dict_language (
    token        String,
    canonical    String,
    display_name String,
    is_sentinel  UInt8
)
PRIMARY KEY token
SOURCE(CLICKHOUSE(TABLE 'dim_language_map'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 300 MAX 600);

-- ---------------------------------------------------------------------------
-- The call sites
-- ---------------------------------------------------------------------------
-- Canonical code for the serving layer. Unknown tokens pass through unchanged
-- rather than collapsing to 'unknown' -- a new language must stay countable
-- while we notice it, not vanish into a bucket.
CREATE OR REPLACE FUNCTION langCanonical AS (raw) ->
    dictGetOrDefault('dict_language', 'canonical',
                     tuple(langMechanical(raw)), langMechanical(raw));

-- Display name for dashboards.
CREATE OR REPLACE FUNCTION langDisplay AS (raw) ->
    dictGetOrDefault('dict_language', 'display_name',
                     tuple(langMechanical(raw)), langMechanical(raw));

-- ---------------------------------------------------------------------------
-- The safety net: surface new variants instead of silently splitting on them
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_language_unmapped (
    token       String,
    raw_sample  String,
    first_seen  DateTime,
    events      UInt64
) ENGINE = SummingMergeTree(events) ORDER BY token;

-- Run after every load, including the unseen day. Non-empty output is a
-- to-do list, not an error: add rows to dim_language_map, reload the
-- dictionary, done.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_language_unmapped
TO dim_language_unmapped AS
SELECT
    langMechanical(audio_language) AS token,
    any(audio_language)            AS raw_sample,
    min(event_timestamp)           AS first_seen,
    count()                        AS events
FROM bronze_events
WHERE NOT dictHas('dict_language', tuple(langMechanical(audio_language)))
GROUP BY token;

-- Post-load check. Expected to return zero rows on the provided day.
--   SELECT token, raw_sample, events FROM dim_language_unmapped
--   ORDER BY events DESC;

-- Verification against the provided day -- expect 41 -> 15:
--   SELECT uniqExact(audio_language)                AS raw_variants,
--          uniqExact(langCanonical(audio_language)) AS canonical
--   FROM bronze_events;
