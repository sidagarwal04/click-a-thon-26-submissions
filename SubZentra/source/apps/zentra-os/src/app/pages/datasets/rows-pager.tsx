import { Button } from '@open-zentra/foundation-design-system';

interface RowsPagerProps {
  readonly page: number;
  readonly pageSize: number;
  readonly total: number;
  readonly onPageChange: (page: number) => void;
  readonly disabled?: boolean;
}

/** Prev/Next paging, scoped to this page — no reusable pager exists yet. */
export const RowsPager = ({
  page,
  pageSize,
  total,
  onPageChange,
  disabled,
}: RowsPagerProps) => {
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const hasNext = to < total;

  return (
    <div className="mt-4 flex items-center justify-between gap-4 text-sm">
      <span className="tabular-nums text-foreground-muted">
        Rows {from}-{to} of {total.toLocaleString()}
      </span>
      <div className="flex gap-2">
        <Button
          intent="secondary"
          size="sm"
          disabled={disabled || page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Prev
        </Button>
        <Button
          intent="secondary"
          size="sm"
          disabled={disabled || !hasNext}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
};
