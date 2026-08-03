package detectionv2

import (
	"testing"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/services/anomalydetector"
)

func TestClaimInvestigationsAppliesLimitAfterSkippingVerified(t *testing.T) {
	verifiedID := uuid.New()
	pendingOneID := uuid.New()
	pendingTwoID := uuid.New()
	pipeline := &Pipeline{
		episodes:     map[uuid.UUID]Episode{},
		investigated: map[uuid.UUID]bool{},
	}
	episodes := []Episode{
		{ID: verifiedID, Severity: anomalydetector.SeverityCrit, VerificationStatus: "verified"},
		{ID: pendingOneID, Severity: anomalydetector.SeverityHigh, VerificationStatus: "pending"},
		{ID: pendingTwoID, Severity: anomalydetector.SeverityMedium, VerificationStatus: "pending"},
	}

	claimed := pipeline.claimInvestigations(episodes, 2)
	if len(claimed) != 2 {
		t.Fatalf("claimed %d episodes, want 2", len(claimed))
	}
	if claimed[0].ID != pendingOneID || claimed[1].ID != pendingTwoID {
		t.Fatalf("claimed IDs %v and %v, want pending episodes", claimed[0].ID, claimed[1].ID)
	}
	if episodes[0].VerificationStatus != "verified" {
		t.Fatal("verified episode status was changed")
	}
	for _, episode := range episodes[1:] {
		if episode.VerificationStatus != "investigating" || episode.UpdatedAt.IsZero() {
			t.Fatalf("pending episode was not claimed: %+v", episode)
		}
		if time.Since(episode.UpdatedAt) > time.Minute {
			t.Fatalf("unexpected claim timestamp %s", episode.UpdatedAt)
		}
	}
}
