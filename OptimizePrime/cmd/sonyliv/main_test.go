package main

import (
	"context"
	"strings"
	"testing"
)

// These tests cover the CLI surface that never touches a network: dispatch,
// flag parsing, and target validation. Anything needing a live ClickHouse
// stays out of unit tests entirely — docs/TESTS.md, and the standing rule
// that `make ci` must not depend on any database, least of all the graded one.

func TestRunDispatch(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name    string
		args    []string
		wantErr string // "" means success
	}{
		{"no args is an error", nil, "no subcommand given"},
		{"unknown subcommand", []string{"frobnicate"}, `unknown subcommand "frobnicate"`},
		{"version subcommand", []string{"version"}, ""},
		{"help subcommand", []string{"help"}, ""},
		{"short help flag", []string{"-h"}, ""},
		{"long help flag", []string{"--help"}, ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			err := run(context.Background(), tc.args)
			if tc.wantErr == "" {
				if err != nil {
					t.Fatalf("run(%v) error = %v, want nil", tc.args, err)
				}
				return
			}
			if err == nil || !strings.Contains(err.Error(), tc.wantErr) {
				t.Fatalf("run(%v) error = %v, want it to contain %q", tc.args, err, tc.wantErr)
			}
		})
	}
}

func TestVerifyAndObserveRejectBadInputBeforeConnecting(t *testing.T) {
	t.Parallel()
	// Both subcommands must fail on flag/target validation BEFORE any
	// connection attempt — these tests pass with no ClickHouse anywhere.
	subcommands := []string{"verify", "observe"}
	cases := []struct {
		name    string
		extra   []string
		wantErr string
	}{
		{"bad flag", []string{"-no-such-flag"}, "flag provided but not defined"},
		{"unknown target", []string{"-target", "mars"}, `unknown target "mars"`},
	}
	for _, sub := range subcommands {
		for _, tc := range cases {
			args := append([]string{sub}, tc.extra...)
			t.Run(sub+" "+tc.name, func(t *testing.T) {
				t.Parallel()
				err := run(context.Background(), args)
				if err == nil || !strings.Contains(err.Error(), tc.wantErr) {
					t.Fatalf("run(%v) error = %v, want it to contain %q", args, err, tc.wantErr)
				}
			})
		}
	}
}
