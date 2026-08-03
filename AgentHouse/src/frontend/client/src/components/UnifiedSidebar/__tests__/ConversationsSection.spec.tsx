import React from 'react';
import { DndProvider } from 'react-dnd';
import { BrowserRouter } from 'react-router-dom';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { render, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { atom, RecoilRoot, useRecoilValue, useSetRecoilState } from 'recoil';
import type { SetterOrUpdater } from 'recoil';

/**
 * Real recoil atom used to force ConversationsSection to re-render on demand,
 * standing in for the conversation-list / title-generation cache churn that
 * happens while a message is streaming.
 */
const streamTickAtom = atom<number>({ key: 'conversations-section-stream-tick', default: 0 });

const mockUseTitleGeneration = jest.fn(() => {
  useRecoilValue(streamTickAtom);
});

jest.mock('~/store', () => {
  const { atom: recoilAtom } = jest.requireActual('recoil');
  return {
    __esModule: true,
    default: {
      sidebarExpanded: recoilAtom({ key: 'mock-cs-sidebarExpanded', default: false }),
      search: recoilAtom({
        key: 'mock-cs-search',
        default: { query: '', debouncedQuery: '', enabled: false, isTyping: false },
      }),
    },
  };
});

jest.mock('~/hooks', () => ({
  __esModule: true,
  useLocalize: () => (key: string) => key,
  useAuthContext: () => ({ isAuthenticated: true }),
  useLocalStorage: () => [true, jest.fn()],
  useNavScrolling: () => ({ moveToTop: jest.fn() }),
}));

jest.mock('~/data-provider', () => ({
  __esModule: true,
  useConversationsInfiniteQuery: () => ({
    data: { pages: [{ conversations: [], nextCursor: null }] },
    fetchNextPage: jest.fn(),
    isFetchingNextPage: false,
    isLoading: false,
    isFetching: false,
  }),
  useTitleGeneration: () => mockUseTitleGeneration(),
}));

jest.mock('~/components/Conversations', () => ({
  __esModule: true,
  Conversations: () => <div data-testid="conversations-stub" />,
}));

jest.mock('~/components/Nav/SearchBar', () => ({
  __esModule: true,
  default: () => <div data-testid="searchbar-stub" />,
}));

import ConversationsSection from '../ConversationsSection';

let setStreamTick: SetterOrUpdater<number>;

function TickController() {
  setStreamTick = useSetRecoilState(streamTickAtom);
  return null;
}

const createQueryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

const renderSection = () =>
  render(
    <QueryClientProvider client={createQueryClient()}>
      <RecoilRoot>
        <BrowserRouter>
          <DndProvider backend={HTML5Backend}>
            <TickController />
            <ConversationsSection />
          </DndProvider>
        </BrowserRouter>
      </RecoilRoot>
    </QueryClientProvider>,
  );

describe('ConversationsSection streaming re-renders', () => {
  beforeEach(() => {
    mockUseTitleGeneration.mockImplementation(() => {
      useRecoilValue(streamTickAtom);
    });
  });

  it('re-renders chat history during stream without crashing', () => {
    const { getByTestId } = renderSection();
    expect(getByTestId('conversations-stub')).toBeInTheDocument();

    const titleBaseline = mockUseTitleGeneration.mock.calls.length;

    for (let i = 0; i < 5; i++) {
      act(() => {
        setStreamTick((prev) => prev + 1);
      });
    }

    expect(mockUseTitleGeneration.mock.calls.length).toBeGreaterThan(titleBaseline);
    expect(getByTestId('conversations-stub')).toBeInTheDocument();
  });
});
