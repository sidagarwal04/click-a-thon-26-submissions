// Command validate-ask runs black-box Ask FeatureLens responses against an
// independent oracle built from fingerprint-verified retained-table snapshots.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/view26/featurelens/internal/domain"
	featureeval "github.com/view26/featurelens/internal/eval"
)

type validationSummary struct {
	APIURL            string                           `json:"api_url"`
	GeneratedAt       time.Time                        `json:"generated_at"`
	Reports           []featureeval.AskGroundingReport `json:"reports"`
	BoundaryChecks    []featureeval.GroundingCheck     `json:"boundary_checks"`
	Total             int                              `json:"total"`
	Passed            int                              `json:"passed"`
	Failed            int                              `json:"failed"`
	FullyVerified     int                              `json:"fully_verified"`
	PartiallyVerified int                              `json:"partially_verified"`
}

func main() {
	apiURL := flag.String("api-url", envDefault("FEATURELENS_API_URL", "http://localhost:8080"), "FeatureLens API base URL")
	feature := flag.String("feature", "", "optional exact feature filter")
	jsonOutput := flag.Bool("json", false, "emit the complete JSON report")
	timeout := flag.Duration("timeout", 90*time.Second, "timeout for each API request")
	flag.Parse()

	client := &http.Client{Timeout: *timeout}
	ctx := context.Background()
	runs, err := getRuns(ctx, client, strings.TrimRight(*apiURL, "/"))
	if err != nil {
		fatalf("load published runs: %v", err)
	}
	completed := make([]domain.FeatureRun, 0, len(runs))
	for _, run := range runs {
		if run.Stage != domain.StageCompleted || run.Profile == nil || run.Schema == nil || run.Context == nil {
			continue
		}
		if *feature != "" && !strings.EqualFold(*feature, run.Input.Name) {
			continue
		}
		completed = append(completed, run)
	}
	if len(completed) == 0 {
		fatalf("no completed published feature runs matched %q", *feature)
	}
	sort.SliceStable(completed, func(i, j int) bool { return completed[i].Context.Version < completed[j].Context.Version })

	summary := validationSummary{APIURL: *apiURL, GeneratedAt: time.Now().UTC()}
	for _, run := range completed {
		for _, published := range run.QuestionAnswers {
			intent := published.Contract.Intent
			answer, status, askErr := postAsk(ctx, client, strings.TrimRight(*apiURL, "/"), domain.QuestionRequest{Role: "product_manager", Feature: run.Input.Name, Question: published.Contract.Question})
			if askErr != nil || status != http.StatusOK {
				detail := fmt.Sprintf("status=%d", status)
				if askErr != nil {
					detail += " error=" + askErr.Error()
				}
				summary.Reports = append(summary.Reports, featureeval.AskGroundingReport{
					Feature: run.Input.Name, Question: published.Contract.Question, Intent: intent, Passed: false, Completeness: "none",
					Checks: []featureeval.GroundingCheck{{Name: "ask_request", Passed: false, Details: detail}},
				})
				continue
			}
			oracle, oracleErr := featureeval.BuildAskOracle(run, intent)
			if published.Contract.Answerability == "not_answerable" || oracleErr != nil {
				checks := featureeval.ValidateFailClosed(answer)
				passed := true
				for _, check := range checks {
					if !check.Passed {
						passed = false
					}
				}
				details := "published question has an explicit not_answerable contract"
				if oracleErr != nil {
					details = oracleErr.Error()
				}
				checks = append([]featureeval.GroundingCheck{{Name: "fail_closed_required", Passed: true, Details: details}}, checks...)
				summary.Reports = append(summary.Reports, featureeval.AskGroundingReport{
					Feature: run.Input.Name, Question: published.Contract.Question, Intent: answer.Contract.Intent, Passed: passed, Completeness: "fail_closed", Checks: checks,
				})
				continue
			}
			summary.Reports = append(summary.Reports, featureeval.ValidateAskGrounding(run, answer, oracle))
		}
	}

	// Boundary cases are as important as numerical matches: the context layer
	// must abstain when meaning is unavailable and reject invalid feature scope.
	boundaryRun := completed[0]
	boundaryAnswer, boundaryStatus, boundaryErr := postAsk(ctx, client, strings.TrimRight(*apiURL, "/"), domain.QuestionRequest{
		Role: "product_manager", Feature: boundaryRun.Input.Name, Question: "How many verified customers are resident in each city?",
	})
	if boundaryErr != nil || boundaryStatus != http.StatusOK {
		summary.BoundaryChecks = append(summary.BoundaryChecks, featureeval.GroundingCheck{Name: "unsupported_semantics_request", Passed: false, Details: fmt.Sprintf("status=%d error=%v", boundaryStatus, boundaryErr)})
	} else {
		summary.BoundaryChecks = append(summary.BoundaryChecks, featureeval.ValidateFailClosed(boundaryAnswer)...)
	}
	_, invalidStatus, _ := postAsk(ctx, client, strings.TrimRight(*apiURL, "/"), domain.QuestionRequest{Role: "product_manager", Feature: "__feature_that_does_not_exist__", Question: "How is it doing?"})
	summary.BoundaryChecks = append(summary.BoundaryChecks, featureeval.GroundingCheck{Name: "unknown_feature_rejected", Passed: invalidStatus == http.StatusUnprocessableEntity, Details: fmt.Sprintf("status=%d expected=%d", invalidStatus, http.StatusUnprocessableEntity)})

	if len(completed) > 1 {
		oldest := completed[0]
		oldVersion := oldest.Context.Version
		_, staleStatus, _ := postAsk(ctx, client, strings.TrimRight(*apiURL, "/"), domain.QuestionRequest{Role: "product_manager", Feature: oldest.Input.Name, Question: "What is completion?", ContextVersion: &oldVersion})
		summary.BoundaryChecks = append(summary.BoundaryChecks, featureeval.GroundingCheck{Name: "stale_context_requires_consent", Passed: staleStatus == http.StatusUnprocessableEntity, Details: fmt.Sprintf("status=%d expected=%d", staleStatus, http.StatusUnprocessableEntity)})
	}

	for _, report := range summary.Reports {
		summary.Total++
		if report.Passed {
			summary.Passed++
		} else {
			summary.Failed++
		}
		if report.Passed && report.Completeness == "full" {
			summary.FullyVerified++
		}
		if report.Passed && report.Completeness == "partial" {
			summary.PartiallyVerified++
		}
	}
	for _, check := range summary.BoundaryChecks {
		summary.Total++
		if check.Passed {
			summary.Passed++
		} else {
			summary.Failed++
		}
	}

	if *jsonOutput {
		encoded, _ := json.MarshalIndent(summary, "", "  ")
		fmt.Println(string(encoded))
	} else {
		for _, report := range summary.Reports {
			status := "PASS"
			if !report.Passed {
				status = "FAIL"
			}
			fmt.Printf("%-4s  %-24s  %-28s  %s\n", status, truncate(report.Feature, 24), report.Intent, report.Completeness)
			if !report.Passed {
				for _, check := range report.Checks {
					if !check.Passed {
						fmt.Printf("      %s: %s\n", check.Name, check.Details)
					}
				}
			}
		}
		for _, check := range summary.BoundaryChecks {
			status := "PASS"
			if !check.Passed {
				status = "FAIL"
			}
			fmt.Printf("%-4s  %-24s  %-28s  boundary\n", status, "context boundary", check.Name)
			if !check.Passed {
				fmt.Printf("      %s\n", check.Details)
			}
		}
		fmt.Printf("\n%d/%d checks passed; %d fully and %d partially table-verified Ask cases\n", summary.Passed, summary.Total, summary.FullyVerified, summary.PartiallyVerified)
	}
	if summary.Failed > 0 {
		os.Exit(1)
	}
}

func getRuns(ctx context.Context, client *http.Client, apiURL string) ([]domain.FeatureRun, error) {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, apiURL+"/api/runs", nil)
	if err != nil {
		return nil, err
	}
	response, err := client.Do(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(response.Body)
		return nil, fmt.Errorf("HTTP %d: %s", response.StatusCode, strings.TrimSpace(string(body)))
	}
	var payload struct {
		Runs []domain.FeatureRun `json:"runs"`
	}
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		return nil, err
	}
	return payload.Runs, nil
}

func postAsk(ctx context.Context, client *http.Client, apiURL string, input domain.QuestionRequest) (domain.QuestionResponse, int, error) {
	payload, err := json.Marshal(input)
	if err != nil {
		return domain.QuestionResponse{}, 0, err
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, apiURL+"/api/questions", bytes.NewReader(payload))
	if err != nil {
		return domain.QuestionResponse{}, 0, err
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := client.Do(request)
	if err != nil {
		return domain.QuestionResponse{}, 0, err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(response.Body)
		return domain.QuestionResponse{}, response.StatusCode, fmt.Errorf("%s", strings.TrimSpace(string(body)))
	}
	var answer domain.QuestionResponse
	if err := json.NewDecoder(response.Body).Decode(&answer); err != nil {
		return domain.QuestionResponse{}, response.StatusCode, err
	}
	return answer, response.StatusCode, nil
}

func truncate(value string, limit int) string {
	if len(value) <= limit {
		return value
	}
	return value[:limit-1] + "…"
}
func envDefault(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "validate-ask: "+format+"\n", args...)
	os.Exit(2)
}
