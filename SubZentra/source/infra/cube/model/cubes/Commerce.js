// The demo warehouse's one cube, defined only when no Data Connection is in
// scope. Cube compiles every file under model/ for every context, so an
// unconditional `cube(...)` here put `Commerce` in the catalog of a tenant
// querying their own ClickHouse — where it is not their data, cannot be
// queried through their driver, and is one more wrong member for an Agent to
// pick. The mirror of Connector.js, which returns early when there *is* no
// Data Connection.
if (!COMPILE_CONTEXT.securityContext || !COMPILE_CONTEXT.securityContext.dataConnectionId) {
cube('Commerce', {
  sql: `SELECT * FROM commerce_facts`,
  dataSource: 'default',

  measures: {
    grossRevenue: {
      sql: 'total_amount',
      type: 'sum',
      format: 'currency',
    },
    netRevenue: {
      sql: 'total_amount - refund_amount',
      type: 'sum',
      format: 'currency',
    },
    orderCount: {
      sql: 'order_id',
      type: 'countDistinct',
    },
    averageOrderValue: {
      sql: 'total_amount',
      type: 'avg',
      format: 'currency',
    },
    refundAmount: {
      sql: 'refund_amount',
      type: 'sum',
      format: 'currency',
    },
    refundRate: {
      sql: `100.0 * COUNT(DISTINCT CASE WHEN ${CUBE}.refund_amount > 0 THEN ${CUBE}.order_id END)
        / NULLIF(COUNT(DISTINCT ${CUBE}.order_id), 0)`,
      type: 'number',
      format: 'percent',
    },
    activeCustomers: {
      sql: 'customer_id',
      type: 'countDistinct',
    },
    repeatPurchaseRate: {
      sql: `100.0 * COUNT(DISTINCT CASE WHEN ${CUBE}.customer_order_count > 1 THEN ${CUBE}.customer_id END)
        / NULLIF(COUNT(DISTINCT ${CUBE}.customer_id), 0)`,
      type: 'number',
      format: 'percent',
    },
  },

  dimensions: {
    orderId: {
      sql: 'order_id',
      type: 'number',
      primaryKey: true,
    },
    orderedAt: {
      sql: 'ordered_at',
      type: 'time',
    },
    region: {
      sql: 'region',
      type: 'string',
    },
    country: {
      sql: 'country',
      type: 'string',
    },
    category: {
      sql: 'category',
      type: 'string',
    },
    channel: {
      sql: 'channel',
      type: 'string',
    },
    refundReason: {
      sql: 'refund_reason',
      type: 'string',
    },
    shippingDelayDays: {
      sql: 'shipping_delay_days',
      type: 'number',
    },
  },
});
}
