# Feature spec — Traveller Basket Editing

## What it does
A basket of add-on services that the traveller edits freely before checkout. Items go
in, come out, and get dragged into a different order, any number of times and in any
order. There is no canonical sequence: `item_removed` regularly precedes `item_added`
for the same basket, and a basket may be checked out with fewer items than were ever
added to it.

The only metric that means anything at basket level is net state — what is actually in
the basket when editing stops. Counting mutation events overstates engagement, and an
ordered funnel over the mutation events measures nothing at all.

## User actions (raw events emitted)
- `basket_created` — an empty basket is opened (`basket_id`)
- `item_added` — an item is added (`item_id`, `item_category`, `items_after`)
- `item_removed` — an item is taken out (`item_id`, `items_after`)
- `item_reordered` — an item is dragged (`position_from`, `position_to`, `items_after`)
- `basket_checked_out` — editing ends and the basket is paid for (`items_after`,
  `basket_value_minor`)

## Questions the PM will ask
- Net items per basket at checkout, not total mutations.
- Churn ratio: removals per addition, and does high churn predict abandonment?
- Which `item_category` is added and then removed most often?
- Do reorders correlate with checkout at all?
