/**
 * The questions an empty thread offers.
 *
 * These used to be the two governed scenarios the router would resolve; every
 * other question was refused, so offering anything else invited a
 * clarification. Questions are free text now (ADR-0023), and the constraint
 * that replaced it is a softer one: a suggestion should name something this
 * tenant actually has. So they are built from the tenant's own governed
 * catalog rather than written here — this file holds sentence shapes, never
 * measure or dimension names.
 */

import type { CatalogSummary, ChatSuggestion } from '../../types';

/**
 * How many to show. The empty state is a starting point, not a catalogue, and
 * the grid is built for a small number.
 */
const SHOWN = 4;

/** Cube names members `Cube.member`; only the second half reads as English. */
const readable = (member: string): string => {
  const leaf = member.includes('.') ? member.slice(member.indexOf('.') + 1) : member;
  return leaf
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .toLowerCase();
};

export const suggestionsFromCatalog = (
  catalog: CatalogSummary | null,
): readonly ChatSuggestion[] => {
  if (!catalog) return [];

  // A time dimension makes "over time" honest; without one, do not imply the
  // tenant can be asked about a trend.
  const overTime = catalog.dimensions.some((dimension) => dimension.type === 'time');
  // Something to break a measure down by. Skipped when the only dimensions are
  // high-cardinality identifiers, which group into noise rather than an answer.
  const groupable = catalog.dimensions.filter(
    (dimension) => dimension.type === 'string' && dimension.values.length > 1,
  );

  return catalog.measures.slice(0, SHOWN).map((measure, index) => {
    const metric = readable(measure.name);
    const by = groupable[index % Math.max(1, groupable.length)];
    const prompt =
      by && index % 2 === 1
        ? `Which ${readable(by.name)} accounted for the change in ${metric}?`
        : overTime
          ? `What changed in ${metric} over the last two months?`
          : `What does ${metric} look like right now?`;

    return {
      suggestion_id: measure.name,
      icon: 'search',
      label: measure.description ?? metric,
      prompt,
    };
  });
};
