import type { AnalyticsBlock, TMessage } from 'librechat-data-provider';
import { isAnalyticsMessageMetadata } from 'librechat-data-provider';

/** Flatten every analytics block attached to messages in a conversation. */
export function collectAnalyticsBlocks(messages: TMessage[]): AnalyticsBlock[] {
  const blocks: AnalyticsBlock[] = [];
  for (const message of messages) {
    const analytics = message.metadata?.analytics;
    if (isAnalyticsMessageMetadata(analytics)) {
      blocks.push(...analytics.blocks);
    }
  }
  return blocks;
}

export function reportTitleFromConversation(
  title: string | null | undefined,
  messages: TMessage[],
): string {
  if (title && title.trim() && title !== 'New Chat') {
    return title.trim();
  }
  const firstUser = messages.find((message) => message.isCreatedByUser && message.text?.trim());
  if (firstUser?.text) {
    const text = firstUser.text.trim();
    return text.length > 60 ? `${text.slice(0, 57)}...` : text;
  }
  return 'Untitled report';
}
