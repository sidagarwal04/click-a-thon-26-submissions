import { NextRequest, NextResponse } from 'next/server';
import { callAnalyticsAgent } from '@/lib/librechat';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { message, conversationId } = body;

    if (!message) {
      return NextResponse.json(
        { error: 'Message is required' },
        { status: 400 }
      );
    }

    const result = await callAnalyticsAgent(message, conversationId);

    return NextResponse.json({
      text: result.text,
      traceUrl: result.traceUrl,
      toolCalls: result.toolCalls,
    });
  } catch (error) {
    console.error('Failed to call analytics agent:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to call analytics agent' },
      { status: 500 }
    );
  }
}
