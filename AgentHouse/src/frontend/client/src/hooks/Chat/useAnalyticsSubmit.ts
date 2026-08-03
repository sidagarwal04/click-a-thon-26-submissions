import { useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useSetRecoilState } from 'recoil';
import { Constants, dataService, QueryKeys } from 'librechat-data-provider';
import type { TConversation, TMessage, AnalyticsResponse, AnalyticsBlock } from 'librechat-data-provider';
import { useChatContext, useChatFormContext } from '~/Providers';
import { useAuthContext } from '~/hooks/AuthContext';
import { addConversationToAllConversationsQueries } from '~/utils';
import store from '~/store';

function textFromBlocks(blocks: AnalyticsBlock[]): string {
  const texts = blocks
    .filter((block): block is Extract<AnalyticsBlock, { type: 'text' }> => block.type === 'text')
    .map((block) => block.text.trim())
    .filter(Boolean);
  if (texts.length > 0) {
    return texts.join('\n\n');
  }
  const titles = blocks
    .filter(
      (block): block is Extract<AnalyticsBlock, { type: 'insight' }> => block.type === 'insight',
    )
    .map((block) => block.title || block.caption || 'Insight')
    .filter(Boolean);
  return titles.join('\n') || 'Analytics response';
}

function titleFromPrompt(prompt: string): string {
  const trimmed = prompt.trim();
  if (!trimmed) {
    return 'Analytics chat';
  }
  return trimmed.length > 60 ? `${trimmed.slice(0, 57)}...` : trimmed;
}

function historyFromMessages(
  messages: TMessage[] | undefined,
): Array<{ role: 'user' | 'assistant'; content: string }> {
  if (!messages?.length) {
    return [];
  }
  const history: Array<{ role: 'user' | 'assistant'; content: string }> = [];
  for (const message of messages) {
    if (message.messageId.endsWith('_') || message.error || message.unfinished) {
      continue;
    }
    const content = (message.text ?? '').trim();
    if (!content) {
      continue;
    }
    history.push({
      role: message.isCreatedByUser ? 'user' : 'assistant',
      content,
    });
  }
  return history;
}

/**
 * Submits the user prompt to the analytics agent, appends messages locally,
 * and persists via /api/analytics/persist (native /api/messages rejects new convos).
 */
export default function useAnalyticsSubmit() {
  const { user } = useAuthContext();
  const methods = useChatFormContext();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { index, conversation, getMessages, setMessages, setConversation } = useChatContext();
  const setIsSubmitting = useSetRecoilState(store.isSubmittingFamily(index));
  const setShowStopButton = useSetRecoilState(store.showStopButtonByIndex(index));

  const submitAnalytics = useCallback(
    async (prompt: string) => {
      const trimmed = prompt.trim();
      if (!trimmed) {
        return false;
      }

      const startedAsNew =
        !conversation?.conversationId || conversation.conversationId === Constants.NEW_CONVO;
      const conversationId: string = startedAsNew
        ? uuidv4()
        : String(conversation.conversationId);

      const priorMessages = getMessages() ?? [];
      const history = historyFromMessages(priorMessages);

      const parentMessageId =
        priorMessages.filter((m) => !m.messageId.endsWith('_')).at(-1)?.messageId ??
        Constants.NO_PARENT;

      const userMessageId = uuidv4();
      const assistantMessageId = uuidv4();
      const now = new Date().toISOString();
      const title = startedAsNew
        ? titleFromPrompt(trimmed)
        : conversation?.title || titleFromPrompt(trimmed);

      const userMessage: TMessage = {
        messageId: userMessageId,
        parentMessageId,
        conversationId,
        text: trimmed,
        sender: user?.name || 'User',
        isCreatedByUser: true,
        endpoint: conversation?.endpoint ?? undefined,
        model: conversation?.model ?? undefined,
        createdAt: now,
        updatedAt: now,
      };

      const pendingAssistant: TMessage = {
        messageId: assistantMessageId,
        parentMessageId: userMessageId,
        conversationId,
        text: '',
        sender: 'Analytics',
        isCreatedByUser: false,
        unfinished: true,
        endpoint: conversation?.endpoint ?? undefined,
        model: conversation?.model ?? undefined,
        createdAt: now,
        updatedAt: now,
      };

      const existing = startedAsNew
        ? priorMessages.map((message) =>
            message.conversationId === conversationId
              ? message
              : { ...message, conversationId },
          )
        : priorMessages;
      setMessages([...existing, userMessage, pendingAssistant]);
      setIsSubmitting(true);
      setShowStopButton(false);
      methods.reset();

      try {
        const response: AnalyticsResponse = await dataService.queryAnalytics({
          prompt: trimmed,
          conversation_id: conversationId,
          history: history.length > 0 ? history : undefined,
        });
        const text = textFromBlocks(response.blocks);
        const assistantMessage: TMessage = {
          ...pendingAssistant,
          text,
          unfinished: false,
          updatedAt: new Date().toISOString(),
          metadata: {
            analytics: { blocks: response.blocks },
          },
        };

        const finalMessages = [...existing, userMessage, assistantMessage];
        setMessages(finalMessages);

        try {
          await dataService.persistAnalyticsConversation({
            conversationId,
            title,
            endpoint: conversation?.endpoint ?? null,
            model: conversation?.model ?? null,
            messages: [
              {
                messageId: userMessage.messageId,
                parentMessageId: userMessage.parentMessageId ?? Constants.NO_PARENT,
                conversationId,
                text: userMessage.text ?? trimmed,
                sender: userMessage.sender ?? 'User',
                isCreatedByUser: true,
                endpoint: userMessage.endpoint ?? null,
                model: userMessage.model ?? null,
                createdAt: userMessage.createdAt,
                updatedAt: userMessage.updatedAt,
              },
              {
                messageId: assistantMessage.messageId,
                parentMessageId: userMessageId,
                conversationId,
                text: assistantMessage.text ?? text,
                sender: assistantMessage.sender ?? 'Analytics',
                isCreatedByUser: false,
                endpoint: assistantMessage.endpoint ?? null,
                model: assistantMessage.model ?? null,
                metadata: assistantMessage.metadata as Record<string, unknown> | undefined,
                unfinished: false,
                createdAt: assistantMessage.createdAt,
                updatedAt: assistantMessage.updatedAt,
              },
            ],
          });

          if (startedAsNew) {
            const nextConvo: TConversation = {
              ...(conversation ?? {}),
              conversationId,
              title,
              endpoint: conversation?.endpoint ?? null,
              createdAt: now,
              updatedAt: new Date().toISOString(),
            };

            setConversation(nextConvo);
            queryClient.setQueryData<TConversation>(
              [QueryKeys.conversation, conversationId],
              nextConvo,
            );
            queryClient.setQueryData<TMessage[]>([QueryKeys.messages, conversationId], finalMessages);
            queryClient.removeQueries({ queryKey: [QueryKeys.messages, Constants.NEW_CONVO] });
            addConversationToAllConversationsQueries(queryClient, nextConvo);

            if (location.pathname === `/c/${Constants.NEW_CONVO}`) {
              navigate(`/c/${conversationId}`, { replace: true });
            }
          } else {
            queryClient.setQueryData<TMessage[]>([QueryKeys.messages, conversationId], finalMessages);
            queryClient.invalidateQueries({ queryKey: [QueryKeys.allConversations] });
          }
        } catch (persistError) {
          console.error('Failed to persist analytics conversation', persistError);
        }

        return true;
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Analytics query failed';
        const errorMessage: TMessage = {
          ...pendingAssistant,
          text: message,
          error: true,
          unfinished: false,
          updatedAt: new Date().toISOString(),
        };
        setMessages([...existing, userMessage, errorMessage]);
        return false;
      } finally {
        setIsSubmitting(false);
      }
    },
    [
      conversation,
      getMessages,
      location.pathname,
      methods,
      navigate,
      queryClient,
      setConversation,
      setIsSubmitting,
      setMessages,
      setShowStopButton,
      user?.name,
    ],
  );

  return { submitAnalytics };
}
