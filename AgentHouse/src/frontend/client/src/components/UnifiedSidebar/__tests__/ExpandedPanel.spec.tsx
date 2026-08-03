import React from 'react';
import { RecoilRoot, useSetRecoilState } from 'recoil';
import '@testing-library/jest-dom/extend-expect';
import { FileText, MessagesSquare, NotebookPen } from 'lucide-react';
import { render, fireEvent, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { MutableSnapshot } from 'recoil';
import { ActivePanelProvider, DEFAULT_PANEL } from '~/Providers/ActivePanelContext';

const mockNewConversation = jest.fn();
const mockClearMessagesCache = jest.fn();

jest.mock('~/store', () => {
  const { atom } = jest.requireActual('recoil');
  let counter = 0;
  const switchAtom = atom({
    key: 'mock-newChatSwitchToHistory',
    default: true,
  });
  const customShortcutsAtom = atom({
    key: 'mock-customShortcuts',
    default: {},
  });
  const selectedReportIdAtom = atom({
    key: 'mock-selectedReportId',
    default: null as string | null,
  });
  return {
    __esModule: true,
    default: {
      conversationByIndex: () =>
        atom({ key: `mock-conversationByIndex-${counter++}`, default: null }),
      newChatSwitchToHistory: switchAtom,
      customShortcuts: customShortcutsAtom,
      selectedReportId: selectedReportIdAtom,
    },
  };
});

jest.mock('~/hooks', () => ({
  useLocalize: () => (key: string) => key,
  useNewConvo: () => ({ newConversation: mockNewConversation }),
}));

jest.mock('~/utils', () => ({
  clearMessagesCache: (...args: unknown[]) => mockClearMessagesCache(...args),
  cn: (...classes: unknown[]) => classes.filter(Boolean).join(' '),
}));

jest.mock('~/components/Chat/Menus/OpenSidebar', () => ({
  CLOSE_SIDEBAR_ID: 'close-sidebar',
}));

jest.mock('~/components/Nav/AccountSettings', () => ({
  __esModule: true,
  default: () => <div data-testid="account-settings" />,
}));

import ExpandedPanel from '../ExpandedPanel';
import store from '~/store';

function ClearReportButton() {
  const setSelectedReportId = useSetRecoilState(store.selectedReportId);
  return (
    <button type="button" onClick={() => setSelectedReportId(null)}>
      clear-report
    </button>
  );
}

const createLinks = () => [
  {
    title: 'com_ui_chat_history' as const,
    icon: MessagesSquare,
    id: DEFAULT_PANEL,
  },
  {
    title: 'com_ui_prompts' as const,
    icon: NotebookPen,
    id: 'prompts',
  },
  {
    title: 'com_ui_reports' as const,
    icon: FileText,
    id: 'reports',
  },
];

const createQueryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderPanel({
  expanded = true,
  onCollapse = jest.fn(),
  onExpand = jest.fn(),
  initialPanel = DEFAULT_PANEL,
  initializeState,
}: {
  expanded?: boolean;
  onCollapse?: jest.Mock;
  onExpand?: jest.Mock;
  initialPanel?: string;
  initializeState?: (snapshot: MutableSnapshot) => void;
} = {}) {
  if (initialPanel !== DEFAULT_PANEL) {
    localStorage.setItem('side:active-panel', initialPanel);
  }

  const result = render(
    <QueryClientProvider client={createQueryClient()}>
      <RecoilRoot initializeState={initializeState}>
        <ActivePanelProvider>
          <ExpandedPanel
            links={createLinks()}
            expanded={expanded}
            onCollapse={onCollapse}
            onExpand={onExpand}
          />
          <ClearReportButton />
        </ActivePanelProvider>
      </RecoilRoot>
    </QueryClientProvider>,
  );

  return { ...result, onCollapse, onExpand };
}

describe('ExpandedPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  describe('NavIconButton collapse toggle', () => {
    it('collapses sidebar when clicking the active icon while expanded', () => {
      const { onCollapse } = renderPanel({ expanded: true });
      const activeButton = screen.getByRole('button', { name: 'com_ui_chat_history' });
      fireEvent.click(activeButton);
      expect(onCollapse).toHaveBeenCalledTimes(1);
    });

    it('switches panel when clicking an inactive icon while expanded', () => {
      const { onCollapse } = renderPanel({ expanded: true });
      const inactiveButton = screen.getByRole('button', { name: 'com_ui_prompts' });
      fireEvent.click(inactiveButton);
      expect(onCollapse).not.toHaveBeenCalled();
      expect(localStorage.getItem('side:active-panel')).toBe('prompts');
    });

    it('expands sidebar when clicking any icon while collapsed', () => {
      const { onExpand } = renderPanel({ expanded: false });
      const activeButton = screen.getByRole('button', { name: 'com_ui_chat_history' });
      fireEvent.click(activeButton);
      expect(onExpand).toHaveBeenCalledTimes(1);
    });

    it('sets active panel and expands when clicking an inactive icon while collapsed', () => {
      const { onExpand } = renderPanel({ expanded: false });
      const inactiveButton = screen.getByRole('button', { name: 'com_ui_prompts' });
      fireEvent.click(inactiveButton);
      expect(onExpand).toHaveBeenCalledTimes(1);
      expect(localStorage.getItem('side:active-panel')).toBe('prompts');
    });
  });

  describe('NewChatButton panel switch', () => {
    it('switches to chat history panel on new chat click when setting is enabled', () => {
      renderPanel({ expanded: true, initialPanel: 'prompts' });

      const newChatLink = screen.getByTestId('new-chat-button');
      fireEvent.click(newChatLink);

      expect(mockNewConversation).toHaveBeenCalledTimes(1);
      expect(localStorage.getItem('side:active-panel')).toBe(DEFAULT_PANEL);
    });

    it('does not switch panel on new chat click when setting is disabled', () => {
      renderPanel({
        expanded: true,
        initialPanel: 'prompts',
        initializeState: ({ set }: MutableSnapshot) => {
          set(store.newChatSwitchToHistory, false);
        },
      });

      const newChatLink = screen.getByTestId('new-chat-button');
      fireEvent.click(newChatLink);

      expect(mockNewConversation).toHaveBeenCalledTimes(1);
      expect(localStorage.getItem('side:active-panel')).toBe('prompts');
    });
  });

  describe('report panel sync', () => {
    it('activates reports panel when a report is selected', () => {
      renderPanel({
        expanded: true,
        initialPanel: DEFAULT_PANEL,
        initializeState: ({ set }: MutableSnapshot) => {
          set(store.selectedReportId, 'report-1');
        },
      });

      expect(localStorage.getItem('side:active-panel')).toBe('reports');
      expect(screen.getByRole('button', { name: 'com_ui_reports' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
    });

    it('activates chat history when leaving a report', () => {
      renderPanel({
        expanded: true,
        initialPanel: DEFAULT_PANEL,
        initializeState: ({ set }: MutableSnapshot) => {
          set(store.selectedReportId, 'report-1');
        },
      });

      expect(localStorage.getItem('side:active-panel')).toBe('reports');

      fireEvent.click(screen.getByRole('button', { name: 'clear-report' }));

      expect(localStorage.getItem('side:active-panel')).toBe(DEFAULT_PANEL);
      expect(screen.getByRole('button', { name: 'com_ui_chat_history' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
    });
  });
});
