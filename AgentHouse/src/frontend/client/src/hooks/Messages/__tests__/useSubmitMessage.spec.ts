import { act, renderHook } from '@testing-library/react';
import { useRecoilValue, useSetRecoilState } from 'recoil';
import { useChatContext, useChatFormContext } from '~/Providers';
import { useAuthContext } from '~/hooks/AuthContext';
import useSubmitMessage from '../useSubmitMessage';

const mockSetActivePrompt = jest.fn();
const mockSubmitAnalytics = jest.fn();

jest.mock('recoil', () => ({
  useRecoilValue: jest.fn(),
  useSetRecoilState: jest.fn(),
}));

jest.mock('librechat-data-provider', () => ({
  replaceSpecialVars: jest.fn(({ text }) => text),
}));

jest.mock('~/Providers', () => ({
  useChatContext: jest.fn(),
  useChatFormContext: jest.fn(),
}));

jest.mock('~/hooks/AuthContext', () => ({
  useAuthContext: jest.fn(),
}));

jest.mock('~/hooks/Chat/useAnalyticsSubmit', () => ({
  __esModule: true,
  default: jest.fn(() => ({
    submitAnalytics: mockSubmitAnalytics,
  })),
}));

jest.mock('~/store', () => ({
  __esModule: true,
  default: {
    autoSendPrompts: 'autoSendPrompts',
    activePromptByIndex: jest.fn(() => 'activePromptByIndex'),
  },
}));

const mockUseRecoilValue = useRecoilValue as jest.Mock;
const mockUseSetRecoilState = useSetRecoilState as jest.Mock;
const mockUseChatContext = useChatContext as jest.Mock;
const mockUseChatFormContext = useChatFormContext as jest.Mock;
const mockUseAuthContext = useAuthContext as jest.Mock;

describe('useSubmitMessage', () => {
  const reset = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseRecoilValue.mockReturnValue(false);
    mockUseSetRecoilState.mockReturnValue(mockSetActivePrompt);
    mockUseAuthContext.mockReturnValue({ user: { id: 'user-1' } });
    mockUseChatFormContext.mockReturnValue({ reset, getValues: jest.fn(() => '') });
    mockUseChatContext.mockReturnValue({
      index: 0,
    });
  });

  it('always routes submits through the analytics agent', () => {
    const { result } = renderHook(() => useSubmitMessage());

    let submitted: false | void | true = undefined;
    act(() => {
      submitted = result.current.submitMessage({ text: 'what is the revenue?' });
    });

    expect(submitted).toBe(true);
    expect(mockSubmitAnalytics).toHaveBeenCalledWith('what is the revenue?');
  });
});
