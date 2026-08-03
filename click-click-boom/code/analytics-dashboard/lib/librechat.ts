// LibreChat API client for Analytics Agent

export interface AgentResponse {
  text: string;
  toolCalls?: any[];
  traceUrl?: string;
}

export async function callAnalyticsAgent(
  message: string,
  conversationId?: string
): Promise<AgentResponse> {
  const apiKey = process.env.LIBRECHAT_API_KEY;
  const agentId = process.env.LIBRECHAT_AGENT_ANALYTICS;
  const baseUrl = process.env.LIBRECHAT_BASE_URL || 'http://localhost:3080';

  if (!apiKey || !agentId) {
    throw new Error('Missing LIBRECHAT_API_KEY or LIBRECHAT_AGENT_ANALYTICS in environment');
  }

  const response = await fetch(`${baseUrl}/api/agents/v1/responses`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
      'User-Agent': 'Mozilla/5.0 (Analytics Dashboard)',
    },
    body: JSON.stringify({
      model: agentId, // LibreChat treats agent_id as model
      messages: [
        {
          role: 'user',
          content: message,
        },
      ],
      conversationId: conversationId || undefined,
      stream: false,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`LibreChat API error: ${response.status} - ${error}`);
  }

  const data = await response.json();

  // Parse LibreChat response format
  const text = data.choices?.[0]?.message?.content || data.text || '';
  const toolCalls = data.choices?.[0]?.message?.tool_calls || [];

  return {
    text,
    toolCalls,
    traceUrl: data.metadata?.traceUrl,
  };
}

export async function streamAnalyticsAgent(
  message: string,
  conversationId?: string,
  onChunk?: (chunk: string) => void
): Promise<AgentResponse> {
  const apiKey = process.env.LIBRECHAT_API_KEY;
  const agentId = process.env.LIBRECHAT_AGENT_ANALYTICS;
  const baseUrl = process.env.LIBRECHAT_BASE_URL || 'http://localhost:3080';

  if (!apiKey || !agentId) {
    throw new Error('Missing LIBRECHAT_API_KEY or LIBRECHAT_AGENT_ANALYTICS in environment');
  }

  const response = await fetch(`${baseUrl}/api/agents/v1/responses`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
      'User-Agent': 'Mozilla/5.0 (Analytics Dashboard)',
    },
    body: JSON.stringify({
      model: agentId,
      messages: [
        {
          role: 'user',
          content: message,
        },
      ],
      conversationId: conversationId || undefined,
      stream: true,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`LibreChat API error: ${response.status} - ${error}`);
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  let fullText = '';

  if (reader) {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n').filter(line => line.trim());

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') continue;

          try {
            const parsed = JSON.parse(data);
            const content = parsed.choices?.[0]?.delta?.content || '';
            if (content) {
              fullText += content;
              onChunk?.(content);
            }
          } catch (e) {
            // Ignore parse errors
          }
        }
      }
    }
  }

  return {
    text: fullText,
  };
}
