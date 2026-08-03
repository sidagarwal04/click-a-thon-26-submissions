/**
 * Member reference utilities.
 *
 * Canonical parser/extractors for values in `table.column` format.
 *
 * @module utils/member-ref
 */

import { MemberRef as MemberRefUtil } from '@open-zentra/foundation-data-model';

/**
 * Parsed member reference.
 */
export interface ParsedMemberRef {
  readonly table: string;
  readonly column: string;
}

/**
 * Parse a member reference in `table.column` format.
 */
export const parseMemberRef = (member: string): ParsedMemberRef | null => {
  if (!MemberRefUtil.isValid(member)) {
    return null;
  }

  const parsed = MemberRefUtil.parse(MemberRefUtil.from(member));
  return {
    table: parsed.table,
    column: parsed.member,
  };
};

/**
 * Extract table name from member reference.
 *
 * NOTE: If you also need the column name, call `parseMemberRef()` once instead
 * of calling `extractTableName()` + `extractColumnName()` separately, to avoid
 * parsing the same string twice.
 */
export const extractTableName = (member: string): string | null => {
  const parsed = parseMemberRef(member);
  return parsed?.table ?? null;
};

/**
 * Extract column/member name from member reference.
 *
 * NOTE: If you also need the table name, call `parseMemberRef()` once instead
 * of calling `extractTableName()` + `extractColumnName()` separately, to avoid
 * parsing the same string twice.
 */
export const extractColumnName = (member: string): string | null => {
  const parsed = parseMemberRef(member);
  return parsed?.column ?? null;
};
