import { Badge, Modal, Switch } from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';

import { formatBytes, formatFraction, formatRows } from './format';
import type { CatalogField, CatalogTable } from './types';

interface TableDetailModalProps {
  readonly table: CatalogTable | null;
  readonly canWrite: boolean;
  readonly onClose: () => void;
  readonly onToggleField: (fieldName: string, visible: boolean) => void;
}

const Stat = ({ label, value }: { readonly label: string; readonly value: string }) => (
  <div>
    <dt className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-foreground-muted">
      {label}
    </dt>
    <dd className="mt-1 text-sm tabular-nums">{value}</dd>
  </div>
);

/**
 * A field's observed statistics, or nothing at all.
 *
 * Absent rather than zeroed when the field was not profiled: a null fraction of
 * "0%" claims the column was measured and had no nulls, which is a different
 * statement from never having looked.
 */
const Profile = ({ field }: { readonly field: CatalogField }) => {
  const profile = field.profile;
  if (!profile) return <span className="text-foreground-muted">not profiled</span>;

  return (
    <span className="flex flex-wrap gap-x-4 gap-y-1 tabular-nums">
      <span title="Fraction of sampled rows that were null">
        {formatFraction(profile.null_fraction)} null
      </span>
      {profile.distinct_count != null ? (
        <span title="Distinct values within the sample">
          {formatRows(profile.distinct_count)} distinct
        </span>
      ) : null}
      <span className="text-foreground-muted" title="Rows the statistics are based on">
        of {formatRows(profile.sampled_rows)} sampled
      </span>
    </span>
  );
};

/**
 * Everything a harvest learned about one table.
 *
 * The column list is the point of the page, so it is a table rather than cards:
 * comparing types down a column is the thing a reader is here to do.
 */
export const TableDetailModal = ({
  table,
  canWrite,
  onClose,
  onToggleField,
}: TableDetailModalProps) => {
  const fields = [...(table?.fields ?? [])].sort((a, b) => a.position - b.position);

  return (
    <Modal
      size="960"
      open={table !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Modal.Content>
        <Modal.Header>
          <Modal.Title>
            <span className="font-mono">{table?.name}</span>
          </Modal.Title>
          <Modal.Description>
            {table?.database} · {fields.length} columns
            {table?.engine ? ` · ${table.engine}` : ''}
          </Modal.Description>
          <Modal.Close />
          {/* The summary lives in the header, not the body. `Modal.Header` is
              `shrink-0` and sits outside the scroll container, so these four
              numbers stay put while the columns scroll — which is the point of
              them: they are the context you read the column list against. */}
          <dl className="mt-4 grid grid-cols-2 gap-5 sm:grid-cols-4">
            <Stat label="Rows" value={formatRows(table?.estimated_rows)} />
            <Stat label="Size" value={formatBytes(table?.size_bytes)} />
            <Stat label="Columns" value={String(fields.length)} />
            <Stat label="Engine" value={table?.engine ?? '—'} />
          </dl>
        </Modal.Header>

        <Modal.Body>
          <div>
            {/* `border-separate`, not `border-collapse`. With collapsed borders
                a cell's background is not painted by the cell itself, so a
                sticky `th` shows the rows passing beneath it; separated borders
                keep each cell opaque.

                The background is the layer token directly rather than
                `bg-background`, and the box-shadow paints that same colour
                upward over the body's `pt-4` — sticky `top-0` pins the row to
                the scrollport's padding edge, so without it rows show through
                that 1rem strip above the headings. */}
            <table className="w-full min-w-[640px] border-separate border-spacing-0 text-sm">
              <thead>
                <tr className="text-left">
                  {['#', 'Column', 'Type', 'Family', 'Null', 'Profile', 'Agent Access'].map((heading) => (
                    <th
                      className="sticky top-0 z-20 border-b border-border bg-[var(--bg-layer-00)] pb-2 pr-4 pt-2 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-foreground-muted shadow-[0_-1.25rem_0_0_var(--bg-layer-00)]"
                      key={heading}
                      scope="col"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fields.map((field) => (
                  <tr key={field.field_id}>
                    <td className="border-b border-border/50 py-2 pr-4 tabular-nums text-foreground-muted">
                      {field.position}
                    </td>
                    <td className="border-b border-border/50 py-2 pr-4 font-mono">{field.name}</td>
                    <td className="border-b border-border/50 py-2 pr-4 font-mono text-xs">
                      {field.declared_type}
                    </td>
                    <td className="border-b border-border/50 py-2 pr-4">
                      <Badge intent="default" size="sm">
                        {field.family}
                      </Badge>
                    </td>
                    <td className="border-b border-border/50 py-2 pr-4">
                      {field.nullable ? (
                        <Icon
                          name="check"
                          size="sm"
                          aria-label="Nullable"
                          className="text-foreground-muted"
                        />
                      ) : (
                        <span className="sr-only">Not nullable</span>
                      )}
                    </td>
                    <td className="border-b border-border/50 py-2 pr-4 text-xs text-foreground-muted">
                      <Profile field={field} />
                    </td>
                    <td className="border-b border-border/50 py-2">
                      <Switch
                        size="sm"
                        checked={field.agent_visible}
                        disabled={!canWrite}
                        onCheckedChange={(visible) => onToggleField(field.name, visible)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {fields.length === 0 ? (
            <p className="mt-5 text-sm text-foreground-muted">
              This table was listed but its columns were not described — the harvest may
              have run out of its query budget before reaching it.
            </p>
          ) : null}
        </Modal.Body>
      </Modal.Content>
    </Modal>
  );
};
