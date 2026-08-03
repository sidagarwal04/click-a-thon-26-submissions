package generator

import (
	"math/rand/v2"
)

// The distributions below are taken from the supplied 905,558-event extract.
// Generated traffic is only useful if it stresses the same edges the real data
// does — skewed platforms, a dominant app version, inconsistent language
// casing, and a client family that never emits the periodic ping.

// weighted is a discrete distribution sampled by cumulative weight.
type weighted[T any] struct {
	values []T
	cum    []float64
	total  float64
}

func newWeighted[T any](values []T, weights []float64) *weighted[T] {
	w := &weighted[T]{values: values, cum: make([]float64, len(weights))}
	var run float64
	for i, x := range weights {
		run += x
		w.cum[i] = run
	}
	w.total = run
	return w
}

func (w *weighted[T]) pick(r *rand.Rand) T {
	target := r.Float64() * w.total
	lo, hi := 0, len(w.cum)-1
	for lo < hi {
		mid := (lo + hi) / 2
		if w.cum[mid] < target {
			lo = mid + 1
		} else {
			hi = mid
		}
	}
	return w.values[lo]
}

// platformProfile carries the per-platform behaviour that changes the shape of
// the event stream, not just its labels.
type platformProfile struct {
	Name string
	// TrioProbability is the chance a session on this platform emits the
	// periodic {network-activity, buffer-health, video-resize} bundle.
	// 74.4% of IPHONE sessions emit none at all, which is exactly why liveness
	// must be defined over any event name rather than over the trio.
	TrioProbability float64
}

// platformDist is weighted by observed event share.
//
// Event share is used as a proxy for session share; they differ (TV sessions
// run longer and emit more) but the ranking and the order of magnitude hold,
// and the point of the generator is to exercise skew, not to reproduce it to
// three decimal places.
var platformDist = newWeighted([]platformProfile{
	{"ANDROID_PHONE", 0.998},
	{"SONY_ANDROID_TV", 0.99},
	{"IPHONE", 0.256}, // 1,139 of 1,530 sessions emit no trio
	{"JIO_ANDROID_TV", 0.99},
	{"Mweb", 0.95},
	{"ANDROID_TAB", 0.99},
	{"XIAOMI_ANDROID_TV", 0.99},
	{"SAMSUNG_HTML_TV", 0.95},
	{"FIRE_TV", 0.99},
	{"LG_HTML_TV", 0.95},
}, []float64{
	629646, 79850, 78020, 56567, 16166, 13021, 10322, 9969, 7260, 4737,
})

// appVersionDist mirrors the observed long tail: one dominant version at 54%.
var appVersionDist = newWeighted([]string{
	"6.34.8", "6.34.4", "6.25.1", "3.11.1", "8.9.5", "3.9.4", "6.33.2", "2.14.0",
}, []float64{
	490940, 89349, 72693, 46098, 39428, 20000, 15000, 12000,
})

// playerVersionDist: 1.8.2 covers 87.8% of rows, with a couple of messy tails.
var playerVersionDist = newWeighted([]string{
	"1.8.2", "1.1", "3.33.50_ADE", "v-0.0.117.12.05.1_adNE_gaBlocked",
}, []float64{
	794717, 76486, 4000, 2000,
})

// videoResolutionDist reproduces the surprise extract's shape, including its
// inconsistency -- both '1920*1080' and '1920 * 1080' are emitted, because the
// source emits both and the normalization in events_raw_to_clean_mv exists to
// merge them. A generator that only ever produced the tidy spelling would mean
// the live path never exercised the rule the CSV path depends on.
//
// Weights are counts from an 800,000-row sample of
// data/ch-hackathon-raw-data_surprise.csv.
var videoResolutionDist = newWeighted([]string{
	"1920*1080", "Auto-1280*720", "960*540", "1920 * 1080", "1280*720",
	"1080*1920", "Auto-1920*1080", "NA", "1280 * 720", "Auto-960*540",
	"Auto-640*360", "640*360", "720*1280", "3840*2160", "Auto-256*144",
	"NA-1280*720", "DataSaver-640*360", "Auto-Auto",
}, []float64{
	73265, 59088, 42229, 31594, 28259,
	25548, 18479, 16224, 11654, 10794,
	7444, 6844, 5375, 4159, 4022,
	3865, 3003, 2793,
})

// audioLanguageDist is the post-start value; the start event emits placeholders.
var audioLanguageDist = newWeighted([]string{
	"hin", "eng", "tam", "tel", "mar", "ben", "kan", "mal", "eng-English",
}, []float64{
	520000, 210000, 48000, 41000, 22000, 18000, 12000, 9000, 6000,
})

// subtitleLanguageDist deliberately mixes the casing variants seen in the
// source ('OFF' vs 'off', 'UNK' vs 'unk'). If the generator emitted clean
// values, the normalization path would never be tested by generated traffic.
var subtitleLanguageDist = newWeighted([]string{
	"OFF", "UNK", "ENG", "eng-English", "off", "HIN",
}, []float64{
	620000, 180000, 60000, 12000, 8000, 6000,
})

// Non-periodic heartbeat telemetry. These fire in bursts around user actions
// and buffering, and they count as liveness even though they are not the ping.
var telemetryDist = newWeighted([]string{
	"BufferStart", "BufferEnd", "video_forward", "Seek", "network-bandwidth",
	"upshift", "dropped-frames", "downshift", "video_rewind",
}, []float64{
	66641, 66289, 49879, 32036, 30637, 19400, 11089, 7294, 6587,
})

// trioEvents fire together at one identical millisecond — 53.69% of all rows in
// the source extract.
var trioEvents = [3]string{"network-activity", "buffer-health", "video-resize"}

// startPlaceholders are the values VideoSessionStart emits before player and
// track metadata are known: lowercase 'unk' or empty. Reproducing this is what
// makes the generated stream exercise the language-normalization rules.
func startAudioPlaceholder(r *rand.Rand) string {
	if r.Float64() < 0.82 {
		return "unk"
	}
	return ""
}

func startSubtitlePlaceholder(r *rand.Rand) string {
	if r.Float64() < 0.82 {
		return "unk"
	}
	return ""
}

// startPlayerVersion is empty for ~14% of start rows in the source.
func startPlayerVersion(r *rand.Rand, steady string) string {
	if r.Float64() < 0.141 {
		return ""
	}
	return steady
}
