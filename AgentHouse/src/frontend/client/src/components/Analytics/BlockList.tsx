import { memo } from 'react';
import type { AnalyticsBlock } from 'librechat-data-provider';
import { insightBlockKey } from './map';
import InsightBlock from './InsightBlock';
import TextBlock from './TextBlock';

type BlockListProps = {
  blocks: AnalyticsBlock[];
  isLatestMessage?: boolean;
};

function blockKey(block: AnalyticsBlock, index: number): string {
  if (block.type === 'text') {
    return `text-${index}-${block.text.slice(0, 48)}`;
  }
  return `insight-${insightBlockKey(block)}`;
}

function BlockList({ blocks, isLatestMessage = false }: BlockListProps) {
  if (!blocks.length) {
    return null;
  }

  return (
    <div
      className="analytics-block-list not-prose flex w-full flex-col gap-3"
      data-testid="analytics-block-list"
    >
      {blocks.map((block, index) => {
        if (block.type === 'text') {
          return (
            <TextBlock
              key={blockKey(block, index)}
              block={block}
              isLatestMessage={isLatestMessage}
            />
          );
        }
        return <InsightBlock key={blockKey(block, index)} block={block} />;
      })}
    </div>
  );
}

export default memo(BlockList);
