package main

import (
	"context"
	"encoding/json"
	"fmt"
)

// Minimal Model Context Protocol implementation — JSON-RPC 2.0 with the handful of
// methods a client actually calls. Hand-rolled rather than pulled from a dependency
// because the surface used here is small, and because the alternative is adding an SDK
// to a repo whose only other dependencies are the ClickHouse driver and uuid.
//
// Protocol revision 2025-06-18. Clients that speak an older revision still work: the
// version is echoed from initialize, and nothing below depends on a post-2024 feature.

const protocolVersion = "2025-06-18"

type rpcRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type rpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Result  any             `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

// JSON-RPC reserved codes. -32602 is the one clients surface most usefully, so bad
// arguments map to it rather than to a generic internal error.
const (
	codeParse          = -32700
	codeInvalidRequest = -32600
	codeMethodNotFound = -32601
	codeInvalidParams  = -32602
	codeInternal       = -32603
)

type toolDef struct {
	Name        string         `json:"name"`
	Title       string         `json:"title,omitempty"`
	Description string         `json:"description"`
	InputSchema map[string]any `json:"inputSchema"`
}

type contentBlock struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type toolResult struct {
	Content []contentBlock `json:"content"`
	IsError bool           `json:"isError,omitempty"`
}

func textResult(s string) *toolResult {
	return &toolResult{Content: []contentBlock{{Type: "text", Text: s}}}
}

// errorResult reports a failure the model should read and act on — a refused table, a
// bad argument — as a successful call carrying isError. A JSON-RPC error would be
// surfaced to the user as a transport failure instead, which hides the explanation.
func errorResult(err error) *toolResult {
	return &toolResult{Content: []contentBlock{{Type: "text", Text: err.Error()}}, IsError: true}
}

// dispatch routes one JSON-RPC request. A nil return means "notification, send nothing".
func (s *server) dispatch(ctx context.Context, req *rpcRequest) *rpcResponse {
	reply := func(result any) *rpcResponse {
		return &rpcResponse{JSONRPC: "2.0", ID: req.ID, Result: result}
	}
	fail := func(code int, msg string) *rpcResponse {
		return &rpcResponse{JSONRPC: "2.0", ID: req.ID, Error: &rpcError{Code: code, Message: msg}}
	}

	switch req.Method {
	case "initialize":
		return reply(map[string]any{
			"protocolVersion": protocolVersion,
			"capabilities": map[string]any{
				"tools":     map[string]any{},
				"prompts":   map[string]any{},
				"resources": map[string]any{},
			},
			"serverInfo": map[string]any{
				"name":    "sonyliv-serving",
				"version": buildVersion,
			},
			// Surfaced by clients before the first tool call, so the additivity rule and
			// the grouping rule are in front of the model from the start rather than
			// only once it reads a tool description.
			"instructions": knowledgeSummary,
		})

	// Notifications carry no id and must not be answered.
	case "notifications/initialized", "notifications/cancelled":
		return nil

	case "ping":
		return reply(map[string]any{})

	case "tools/list":
		return reply(map[string]any{"tools": s.toolDefs()})

	case "tools/call":
		var p struct {
			Name      string          `json:"name"`
			Arguments json.RawMessage `json:"arguments"`
		}
		if err := json.Unmarshal(req.Params, &p); err != nil {
			return fail(codeInvalidParams, "malformed params: "+err.Error())
		}
		h, ok := s.handlers[p.Name]
		if !ok {
			return fail(codeMethodNotFound, "unknown tool: "+p.Name)
		}
		res, err := h(ctx, p.Arguments)
		if err != nil {
			return reply(errorResult(err))
		}
		return reply(res)

	case "prompts/list":
		return reply(map[string]any{"prompts": promptDefs()})

	case "prompts/get":
		var p struct {
			Name string `json:"name"`
		}
		if err := json.Unmarshal(req.Params, &p); err != nil {
			return fail(codeInvalidParams, "malformed params: "+err.Error())
		}
		body, ok := promptBody(p.Name)
		if !ok {
			return fail(codeInvalidParams, "unknown prompt: "+p.Name)
		}
		return reply(map[string]any{
			"description": body.description,
			"messages": []map[string]any{{
				"role":    "user",
				"content": map[string]any{"type": "text", "text": body.text},
			}},
		})

	case "resources/list":
		return reply(map[string]any{"resources": resourceDefs()})

	case "resources/read":
		var p struct {
			URI string `json:"uri"`
		}
		if err := json.Unmarshal(req.Params, &p); err != nil {
			return fail(codeInvalidParams, "malformed params: "+err.Error())
		}
		text, mime, ok := resourceBody(p.URI)
		if !ok {
			return fail(codeInvalidParams, "unknown resource: "+p.URI)
		}
		return reply(map[string]any{
			"contents": []map[string]any{{"uri": p.URI, "mimeType": mime, "text": text}},
		})

	default:
		return fail(codeMethodNotFound, fmt.Sprintf("unsupported method %q", req.Method))
	}
}
