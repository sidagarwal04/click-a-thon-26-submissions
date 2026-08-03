import { memo, useCallback, useEffect, useState } from 'react';
import { ArrowLeft, Trash2, X } from 'lucide-react';
import { useSetRecoilState } from 'recoil';
import { Button, Spinner, useToastContext } from '@librechat/client';
import type { AnalyticsBlock, AnalyticsReport, TConversation } from 'librechat-data-provider';
import InsightBlock from '~/components/Analytics/InsightBlock';
import TextBlock from '~/components/Analytics/TextBlock';
import {
  useDeleteReportMutation,
  useReportQuery,
  useUpdateReportMutation,
} from '~/data-provider';
import { useLocalize, useNavigateToConvo } from '~/hooks';
import store from '~/store';

type ReportViewProps = {
  reportId: string;
};

type ReportHeaderProps = {
  report: AnalyticsReport;
  onBack: () => void;
  onOpenChat: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
};

/** Title edits stay local so typing does not remount chart blocks. */
const ReportHeader = memo(function ReportHeader({
  report,
  onBack,
  onOpenChat,
  onDelete,
  onRename,
}: ReportHeaderProps) {
  const localize = useLocalize();
  const [title, setTitle] = useState(report.title);

  useEffect(() => {
    setTitle(report.title);
  }, [report.title]);

  const commitTitle = () => {
    const next = title.trim();
    if (!next || next === report.title) {
      setTitle(report.title);
      return;
    }
    onRename(next);
  };

  return (
    <div className="sticky top-0 z-[1] flex flex-col gap-3 border-b border-border-light bg-presentation px-4 py-3">
      <div className="flex items-center gap-2">
        <Button
          size="icon"
          variant="ghost"
          className="text-text-primary"
          aria-label={localize('com_ui_back')}
          onClick={onBack}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <input
          className="min-w-0 flex-1 rounded-md border border-transparent bg-transparent px-2 py-1 text-lg font-semibold text-text-primary outline-none focus:border-border-medium"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          onBlur={commitTitle}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.currentTarget.blur();
            }
          }}
          aria-label={localize('com_ui_rename')}
        />
        <Button size="sm" variant="outline" onClick={onOpenChat}>
          {localize('com_ui_reports_open_chat')}
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="text-text-primary"
          aria-label={localize('com_ui_delete')}
          onClick={onDelete}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
});

type ReportBlocksProps = {
  reportId: string;
  blocks: AnalyticsBlock[];
  onRemoveBlock: (index: number) => void;
};

const ReportBlocks = memo(function ReportBlocks({
  reportId,
  blocks,
  onRemoveBlock,
}: ReportBlocksProps) {
  const localize = useLocalize();

  if (blocks.length === 0) {
    return <p className="text-sm text-text-secondary">{localize('com_ui_reports_no_blocks')}</p>;
  }

  return (
    <>
      {blocks.map((block, index) => (
        <div key={`${reportId}-${index}`} className="group relative rounded-lg">
          <button
            type="button"
            className="absolute -right-8 top-1 z-[1] rounded-md p-1 text-text-secondary opacity-0 transition-opacity hover:bg-surface-hover hover:text-text-primary group-hover:opacity-100 focus:opacity-100"
            aria-label={localize('com_ui_reports_remove_block')}
            onClick={() => onRemoveBlock(index)}
          >
            <X className="h-3.5 w-3.5" />
          </button>
          {block.type === 'text' ? <TextBlock block={block} /> : <InsightBlock block={block} />}
        </div>
      ))}
    </>
  );
});

export default function ReportView({ reportId }: ReportViewProps) {
  const localize = useLocalize();
  const { showToast } = useToastContext();
  const setSelectedReportId = useSetRecoilState(store.selectedReportId);
  const { navigateToConvo } = useNavigateToConvo(0);
  const { data: report, isLoading } = useReportQuery(reportId);
  const updateMutation = useUpdateReportMutation();
  const deleteMutation = useDeleteReportMutation();

  const handleBack = useCallback(() => setSelectedReportId(null), [setSelectedReportId]);

  const handleOpenChat = useCallback(() => {
    if (!report) {
      return;
    }
    setSelectedReportId(null);
    navigateToConvo({ conversationId: report.conversationId } as TConversation);
  }, [navigateToConvo, report, setSelectedReportId]);

  const handleRename = useCallback(
    (title: string) => {
      if (!report) {
        return;
      }
      updateMutation.mutate({ id: report.id, title });
    },
    [report, updateMutation],
  );

  const handleDelete = useCallback(() => {
    if (!report) {
      return;
    }
    if (!window.confirm(localize('com_ui_reports_delete_confirm'))) {
      return;
    }
    deleteMutation.mutate(report.id, {
      onSuccess: () => {
        setSelectedReportId(null);
        showToast({ message: localize('com_ui_reports_deleted'), status: 'success' });
      },
    });
  }, [deleteMutation, localize, report, setSelectedReportId, showToast]);

  const handleRemoveBlock = useCallback(
    (index: number) => {
      if (!report) {
        return;
      }
      const blocks = report.blocks.filter((_, i) => i !== index);
      updateMutation.mutate({ id: report.id, blocks });
    },
    [report, updateMutation],
  );

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6">
        <p className="text-sm text-text-secondary">{localize('com_ui_reports_not_found')}</p>
        <Button size="sm" variant="outline" onClick={handleBack}>
          {localize('com_ui_back')}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto" data-testid="report-view">
      <ReportHeader
        report={report}
        onBack={handleBack}
        onOpenChat={handleOpenChat}
        onDelete={handleDelete}
        onRename={handleRename}
      />

      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6 xl:max-w-4xl">
        <ReportBlocks
          reportId={report.id}
          blocks={report.blocks}
          onRemoveBlock={handleRemoveBlock}
        />
      </div>
    </div>
  );
}
