import { useRecoilValue } from 'recoil';
import { Constants } from 'librechat-data-provider';
import { useState, useRef, useCallback, useEffect } from 'react';
import type { TMessage } from 'librechat-data-provider';
import { useMessagesConversation, useMessagesSubmission } from '~/Providers';
import useScrollToRef from '~/hooks/useScrollToRef';
import { reconcileMessageContentLayout } from './messageLayout';
import store from '~/store';

const threshold = 0.85;
const debounceRate = 150;
const resizeFollowThreshold = 120;

export default function useMessageScrolling(messagesTree?: TMessage[] | null) {
  const autoScroll = useRecoilValue(store.autoScroll);

  const scrollableRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const isNearBottomRef = useRef(true);
  const suppressNextResizeFollowRef = useRef(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const { conversation, conversationId } = useMessagesConversation();
  const { setAbortScroll, isSubmitting, abortScroll } = useMessagesSubmission();

  const timeoutIdRef = useRef<NodeJS.Timeout>();

  const getIsNearBottom = useCallback(() => {
    const scrollEl = scrollableRef.current;
    if (!scrollEl) {
      return true;
    }
    const distance = scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight;
    return distance <= resizeFollowThreshold;
  }, []);

  const debouncedSetShowScrollButton = useCallback((value: boolean) => {
    clearTimeout(timeoutIdRef.current);
    timeoutIdRef.current = setTimeout(() => {
      setShowScrollButton(value);
    }, debounceRate);
  }, []);

  useEffect(() => {
    if (!messagesEndRef.current || !scrollableRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        isNearBottomRef.current = entry.isIntersecting;
        debouncedSetShowScrollButton(!entry.isIntersecting);
      },
      { root: scrollableRef.current, threshold },
    );

    observer.observe(messagesEndRef.current);

    return () => {
      observer.disconnect();
      clearTimeout(timeoutIdRef.current);
    };
  }, [messagesEndRef, scrollableRef, debouncedSetShowScrollButton]);

  const debouncedHandleScroll = useCallback(() => {
    isNearBottomRef.current = getIsNearBottom();
    if (messagesEndRef.current && scrollableRef.current) {
      const observer = new IntersectionObserver(
        ([entry]) => {
          isNearBottomRef.current = entry.isIntersecting;
          debouncedSetShowScrollButton(!entry.isIntersecting);
        },
        { root: scrollableRef.current, threshold },
      );
      observer.observe(messagesEndRef.current);
      return () => observer.disconnect();
    }
  }, [debouncedSetShowScrollButton, getIsNearBottom]);

  const scrollCallback = () => {
    reconcileMessageContentLayout(scrollableRef.current);
    isNearBottomRef.current = true;
    debouncedSetShowScrollButton(false);
  };

  const { scrollToRef: scrollToBottom, handleSmoothToRef } = useScrollToRef({
    targetRef: messagesEndRef,
    callback: scrollCallback,
    smoothCallback: () => {
      scrollCallback();
      setAbortScroll(false);
    },
  });

  /**
   * Pin the viewport to the bottom without scrollIntoView animations.
   * Smooth scroll chase after a large height dump is what made insights "snap/fly" in.
   */
  const stickToBottom = useCallback(() => {
    const scrollEl = scrollableRef.current;
    if (!scrollEl) {
      return;
    }
    scrollEl.scrollTop = scrollEl.scrollHeight;
    reconcileMessageContentLayout(scrollEl);
    isNearBottomRef.current = true;
    debouncedSetShowScrollButton(false);
  }, [debouncedSetShowScrollButton]);

  const stickToBottomAfterLayout = useCallback(() => {
    requestAnimationFrame(() => {
      stickToBottom();
      requestAnimationFrame(stickToBottom);
    });
  }, [stickToBottom]);

  const clampScrollToContent = useCallback(() => {
    const scrollEl = scrollableRef.current;
    if (!scrollEl) {
      return false;
    }

    const maxScrollTop = Math.max(0, scrollEl.scrollHeight - scrollEl.clientHeight);
    if (scrollEl.scrollTop <= maxScrollTop) {
      return false;
    }

    scrollEl.scrollTop = maxScrollTop;
    isNearBottomRef.current = getIsNearBottom();
    return true;
  }, [getIsNearBottom]);

  const reconcileContentResize = useCallback(
    (shouldFollowResize = true) => {
      if (clampScrollToContent()) {
        return;
      }

      if (suppressNextResizeFollowRef.current) {
        suppressNextResizeFollowRef.current = false;
        isNearBottomRef.current = getIsNearBottom();
        return;
      }

      if (abortScroll === true || !shouldFollowResize) {
        return;
      }

      if (!(isNearBottomRef.current || getIsNearBottom())) {
        return;
      }

      // Keep bottom glued while insight height animates / charts mount.
      stickToBottom();
    },
    [abortScroll, clampScrollToContent, getIsNearBottom, stickToBottom],
  );

  useEffect(() => {
    const contentEl = contentRef.current;
    if (!contentEl || typeof ResizeObserver === 'undefined') {
      return;
    }

    const observer = new ResizeObserver(() => reconcileContentResize());
    observer.observe(contentEl);
    return () => observer.disconnect();
  }, [reconcileContentResize]);

  useEffect(() => {
    const contentEl = contentRef.current;
    if (!contentEl) {
      return;
    }

    const suppressNextResizeFollow = () => {
      suppressNextResizeFollowRef.current = true;
    };

    contentEl.addEventListener('pointerdown', suppressNextResizeFollow, true);
    contentEl.addEventListener('keydown', suppressNextResizeFollow, true);
    return () => {
      contentEl.removeEventListener('pointerdown', suppressNextResizeFollow, true);
      contentEl.removeEventListener('keydown', suppressNextResizeFollow, true);
    };
  }, []);

  useEffect(() => {
    if (!messagesTree || messagesTree.length === 0) {
      return;
    }

    if (!messagesEndRef.current || !scrollableRef.current) {
      return;
    }

    if (abortScroll === true) {
      return () => {
        scrollToBottom?.cancel();
      };
    }

    if (isSubmitting || isNearBottomRef.current || getIsNearBottom()) {
      stickToBottomAfterLayout();
    }

    return () => {
      if (abortScroll === true) {
        scrollToBottom?.cancel();
      }
    };
  }, [
    isSubmitting,
    messagesTree,
    scrollToBottom,
    abortScroll,
    getIsNearBottom,
    stickToBottomAfterLayout,
  ]);

  useEffect(() => {
    if (!messagesEndRef.current || !scrollableRef.current) {
      return;
    }

    if (scrollToBottom && autoScroll && conversationId !== Constants.NEW_CONVO) {
      scrollToBottom();
    }
  }, [autoScroll, conversationId, scrollToBottom]);

  return {
    conversation,
    contentRef,
    scrollableRef,
    messagesEndRef,
    scrollToBottom,
    showScrollButton,
    handleSmoothToRef,
    debouncedHandleScroll,
  };
}
