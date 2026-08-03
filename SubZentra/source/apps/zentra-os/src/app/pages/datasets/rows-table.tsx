interface RowsTableProps {
  readonly columns: readonly string[];
  readonly rows: readonly (string | null)[][];
}

/** A raw row grid, reusing `table-detail-modal.tsx`'s sticky-header markup. */
export const RowsTable = ({ columns, rows }: RowsTableProps) => (
  <table className="w-full min-w-[640px] border-separate border-spacing-0 text-sm">
    <thead>
      <tr className="text-left">
        {columns.map((column) => (
          <th
            key={column}
            scope="col"
            className="sticky top-0 z-20 border-b border-border bg-[var(--bg-layer-00)] pb-2 pr-4 pt-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-foreground-muted shadow-[0_-1.25rem_0_0_var(--bg-layer-00)]"
          >
            {column}
          </th>
        ))}
      </tr>
    </thead>
    <tbody>
      {rows.map((row, index) => (
        // Rows carry no id, and a page is small and static.
        <tr key={index}>
          {row.map((cell, cellIndex) => (
            <td
              key={columns[cellIndex]}
              className="border-b border-border/50 py-2 pr-4 font-mono text-xs"
            >
              {cell ?? <span className="text-foreground-muted">null</span>}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
);
