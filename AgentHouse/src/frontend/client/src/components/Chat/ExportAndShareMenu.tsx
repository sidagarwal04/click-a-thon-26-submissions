import { useState, useId, useRef } from 'react';
import { useRecoilValue, useSetRecoilState } from 'recoil';
import * as Ariakit from '@ariakit/react';
import { useQueryClient } from '@tanstack/react-query';
import { FileText, Upload, Share2 } from 'lucide-react';
import { PermissionTypes, Permissions, QueryKeys } from 'librechat-data-provider';
import { DropdownPopup, TooltipAnchor, useMediaQuery, useToastContext } from '@librechat/client';
import type { TMessage } from 'librechat-data-provider';
import type * as t from '~/common';
import ExportModal from '~/components/Nav/ExportConversation/ExportModal';
import { ShareButton } from '~/components/Conversations/ConvoOptions';
import {
  collectAnalyticsBlocks,
  reportTitleFromConversation,
  useCreateReportMutation,
} from '~/data-provider';
import { useHasAccess, useLocalize } from '~/hooks';
import store from '~/store';

export default function ExportAndShareMenu({
  isSharedButtonEnabled,
}: {
  isSharedButtonEnabled: boolean;
}) {
  const localize = useLocalize();
  const queryClient = useQueryClient();
  const { showToast } = useToastContext();
  const setSelectedReportId = useSetRecoilState(store.selectedReportId);
  const createReport = useCreateReportMutation();
  const [showExports, setShowExports] = useState(false);
  const [isPopoverActive, setIsPopoverActive] = useState(false);
  const [showShareDialog, setShowShareDialog] = useState(false);

  const menuId = useId();
  const shareButtonRef = useRef<HTMLButtonElement>(null);
  const exportButtonRef = useRef<HTMLButtonElement>(null);
  const canCreateSharedLinks = useHasAccess({
    permissionType: PermissionTypes.SHARED_LINKS,
    permission: Permissions.CREATE,
  });
  const isSmallScreen = useMediaQuery('(max-width: 768px)');
  const conversation = useRecoilValue(store.conversationByIndex(0));

  const hasConversation =
    conversation &&
    conversation.conversationId != null &&
    conversation.conversationId !== 'search';

  const exportable =
    hasConversation &&
    conversation.conversationId !== 'new' &&
    conversation.conversationId != null;

  if (!hasConversation) {
    return null;
  }

  const shareHandler = () => {
    setShowShareDialog(true);
  };

  const exportHandler = () => {
    setShowExports(true);
  };

  const saveReportHandler = () => {
    const conversationId = conversation.conversationId;
    if (!conversationId) {
      return;
    }
    const messages =
      queryClient.getQueryData<TMessage[]>([QueryKeys.messages, conversationId]) ?? [];
    const blocks = collectAnalyticsBlocks(messages);
    if (blocks.length === 0) {
      showToast({ message: localize('com_ui_reports_no_blocks_to_save'), status: 'error' });
      return;
    }

    createReport.mutate(
      {
        title: reportTitleFromConversation(conversation.title, messages),
        conversationId,
        blocks,
      },
      {
        onSuccess: (report) => {
          setSelectedReportId(report.id);
          showToast({ message: localize('com_ui_reports_saved'), status: 'success' });
        },
      },
    );
  };

  const dropdownItems: t.MenuItemProps[] = [
    {
      label: localize('com_ui_reports_save'),
      onClick: saveReportHandler,
      icon: <FileText className="icon-md mr-2 text-text-secondary" />,
      show: true,
    },
    {
      label: localize('com_ui_share'),
      onClick: shareHandler,
      icon: <Share2 className="icon-md mr-2 text-text-secondary" />,
      show: Boolean(exportable && isSharedButtonEnabled && canCreateSharedLinks),
      /** NOTE: THE FOLLOWING PROPS ARE REQUIRED FOR MENU ITEMS THAT OPEN DIALOGS */
      hideOnClick: false,
      ref: shareButtonRef,
      render: (props) => <button {...props} data-testid="share-conversation-menu-item" />,
    },
    {
      label: localize('com_endpoint_export'),
      onClick: exportHandler,
      icon: <Upload className="icon-md mr-2 text-text-secondary" />,
      show: Boolean(exportable),
      /** NOTE: THE FOLLOWING PROPS ARE REQUIRED FOR MENU ITEMS THAT OPEN DIALOGS */
      hideOnClick: false,
      ref: exportButtonRef,
      render: (props) => <button {...props} />,
    },
  ];

  return (
    <>
      <DropdownPopup
        portal={true}
        menuId={menuId}
        focusLoop={true}
        unmountOnHide={true}
        isOpen={isPopoverActive}
        setIsOpen={setIsPopoverActive}
        trigger={
          <TooltipAnchor
            description={localize('com_endpoint_export_share')}
            render={
              <Ariakit.MenuButton
                id="export-menu-button"
                aria-label="Export options"
                className="inline-flex size-9 flex-shrink-0 items-center justify-center rounded-xl border border-border-light bg-presentation text-text-primary transition-all ease-in-out hover:bg-surface-tertiary disabled:pointer-events-none disabled:opacity-50 radix-state-open:bg-surface-tertiary"
              >
                <Share2
                  className="icon-md text-text-primary"
                  aria-hidden="true"
                  focusable="false"
                />
              </Ariakit.MenuButton>
            }
          />
        }
        items={dropdownItems}
        className={isSmallScreen ? '' : 'absolute right-0 top-0 mt-2'}
      />
      <ExportModal
        open={showExports}
        onOpenChange={setShowExports}
        conversation={conversation}
        triggerRef={exportButtonRef}
        aria-label={localize('com_ui_export_convo_modal')}
      />
      <ShareButton
        triggerRef={shareButtonRef}
        conversationId={conversation.conversationId ?? ''}
        open={showShareDialog}
        onOpenChange={setShowShareDialog}
      />
    </>
  );
}
