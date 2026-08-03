import { useCallback } from 'react';
import { useRecoilValue, useSetRecoilState } from 'recoil';
import { replaceSpecialVars } from 'librechat-data-provider';
import type { TMessage } from 'librechat-data-provider';
import { useChatContext, useChatFormContext } from '~/Providers';
import useAnalyticsSubmit from '~/hooks/Chat/useAnalyticsSubmit';
import { useAuthContext } from '~/hooks/AuthContext';
import { mainTextareaId } from '~/common';
import store from '~/store';

/**
 * Chat submit always goes through the analytics agent for this deployment.
 */
export default function useSubmitMessage() {
  const { user } = useAuthContext();
  const methods = useChatFormContext();
  const { index } = useChatContext();
  const { submitAnalytics } = useAnalyticsSubmit();

  const autoSendPrompts = useRecoilValue(store.autoSendPrompts);
  const setActivePrompt = useSetRecoilState(store.activePromptByIndex(index));

  const submitMessage = useCallback(
    (data?: {
      text: string;
      overrideFiles?: TMessage['files'];
      overrideQuotes?: string[];
      overrideManualSkills?: string[];
    }) => {
      if (!data) {
        return console.warn('No data provided to submitMessage');
      }

      void submitAnalytics(data.text);
      return true;
    },
    [submitAnalytics],
  );

  const submitPrompt = useCallback(
    (text: string) => {
      const parsedText = replaceSpecialVars({ text, user });
      if (autoSendPrompts) {
        submitMessage({ text: parsedText });
        return;
      }

      const textarea = document.getElementById(mainTextareaId) as HTMLTextAreaElement | null;
      const currentText = textarea?.value ?? methods.getValues('text');
      const newText = currentText.trim().length > 1 ? `\n${parsedText}` : parsedText;
      setActivePrompt(newText);
    },
    [autoSendPrompts, submitMessage, setActivePrompt, methods, user],
  );

  return { submitMessage, submitPrompt };
}
