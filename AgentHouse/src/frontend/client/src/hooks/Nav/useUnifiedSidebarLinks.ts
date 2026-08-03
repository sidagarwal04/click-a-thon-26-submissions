import { useMemo } from 'react';
import { FileText, MessagesSquare } from 'lucide-react';
import type { NavLink } from '~/common';
import { ReportsPanel } from '~/components/Reports';
import ConversationsSection from '~/components/UnifiedSidebar/ConversationsSection';

/** Analytics sidebar: chat history + saved reports. */
export default function useUnifiedSidebarLinks() {
  const links = useMemo(() => {
    const conversationLink: NavLink = {
      title: 'com_ui_chat_history',
      label: '',
      icon: MessagesSquare,
      id: 'conversations',
      Component: ConversationsSection,
    };

    const reportsLink: NavLink = {
      title: 'com_ui_reports',
      label: '',
      icon: FileText,
      id: 'reports',
      Component: ReportsPanel,
    };

    return [conversationLink, reportsLink];
  }, []);

  return links;
}
