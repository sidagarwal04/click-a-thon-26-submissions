import { memo } from 'react';
import type { AnalyticsTextBlock } from 'librechat-data-provider';
import Markdown from '~/components/Chat/Messages/Content/Markdown';

type TextBlockProps = {
  block: AnalyticsTextBlock;
  isLatestMessage?: boolean;
};

function TextBlock({ block, isLatestMessage = false }: TextBlockProps) {
  return (
    <div className="analytics-text-block markdown prose dark:prose-invert light w-full break-words dark:text-gray-100">
      <Markdown content={block.text} isLatestMessage={isLatestMessage} />
    </div>
  );
}

export default memo(
  TextBlock,
  (prev, next) =>
    prev.block.text === next.block.text && prev.isLatestMessage === next.isLatestMessage,
);
