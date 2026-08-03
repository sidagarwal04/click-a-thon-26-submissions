// Dynamic, per-tenant cubes generated from a Data Connection's confirmed
// Join Graph. This is ADR-0014's governance intent ("only permitted joins
// are queryable") reimplemented as compiled-schema absence rather than a
// bespoke runtime gate: the internal endpoint below only ever emits
// confirmed Relations, so an unconfirmed join structurally cannot appear
// here — there is nothing to enforce at query time because there is
// nothing to query.
//
// Absent on the demo-warehouse path on purpose: COMPILE_CONTEXT carries no
// dataConnectionId there, and this module returns immediately rather than
// making a wasted (or failing) callback for every non-connector query.
// Duplicated in cube.js's driverFactory rather than shared: this file runs
// inside Cube's own schema-compiler sandbox, which does not support
// requiring a plain CommonJS helper module the way cube.js (a plain Node
// config module) does — verified empirically. Both call sites are ~15
// lines; the duplication is the accepted cost of that boundary.
// Assume nothing about this sandbox's globals. On Node 22 it has none of
// `fetch`, `URL`, `process` or `Buffer` — only `require` and what
// COMPILE_CONTEXT carries — so this uses node's http module and reads its
// configuration from the security context `cube.js` attaches in checkAuth.
//
// Getting that wrong was silent until it wasn't: the compiler threw
// `ReferenceError: fetch is not defined`, every /meta call answered 500, and a
// tenant's connected tables were never compiled into a cube at all. The demo
// warehouse kept working throughout, which is what made it look like an agent
// problem rather than a schema one.
function fetchConnectorModel(securityContext) {
  const url = `${securityContext.internalApiUrl}/internal/v1/cube/model/${securityContext.tenantId}/${securityContext.dataConnectionId}`;
  // `URL` is not defined in here either, so the transport is chosen from the
  // string and the URL is handed to http.request as a string. Assume nothing
  // about this sandbox's globals: it has neither `fetch` nor `URL` on Node 22.
  const transport = require(url.startsWith('https:') ? 'https' : 'http');

  return new Promise((resolve, reject) => {
    const request = transport.request(
      url,
      {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${securityContext.internalApiSecret}`,
        },
      },
      (response) => {
        // String concatenation rather than Buffer.concat: `Buffer` is not
        // defined in here either. setEncoding makes each chunk a string.
        let body = '';
        response.setEncoding('utf8');
        response.on('data', (chunk) => {
          body += chunk;
        });
        response.on('end', () => {
          if (response.statusCode !== 200) {
            reject(
              new Error(
                `Connector model fetch failed with ${response.statusCode} for data connection ${securityContext.dataConnectionId}: ${body.slice(0, 200)}`
              )
            );
            return;
          }
          try {
            resolve(JSON.parse(body));
          } catch (error) {
            reject(new Error(`Connector model was not JSON: ${error.message}`));
          }
        });
      }
    );
    request.on('error', reject);
    request.end();
  });
}

asyncModule(async () => {
  const { securityContext } = COMPILE_CONTEXT;
  if (!securityContext || !securityContext.dataConnectionId) {
    return;
  }

  const model = await fetchConnectorModel(securityContext);

  const joinsByTable = {};
  for (const join of model.joins) {
    (joinsByTable[join.fromTable] ??= []).push(join);
  }

  for (const table of model.tables) {
    const dimensions = {};
    const measures = {
      count: { type: 'count' },
    };
    // Descriptions are compiled onto the members rather than kept API-side:
    // Cube returns them from /meta, which is where the governed catalog an
    // agent reasons over is read from. A name says `orders.amount` exists; the
    // description is what says whether it is nullable and how many distinct
    // values it holds.
    // Every `sql` is a function, never a string. The JS data-model API rejects
    // a string outright — "(dimensions.x.sql) must be of type function" — and
    // the resulting validation failure takes the *whole* schema down, not just
    // the offending member, which is why one wrong shape here meant no
    // connected table was queryable at all.
    for (const field of table.fields) {
      if (field.cubeType === 'number') {
        // `total_` prefixed, because a member name is unique across measures
        // *and* dimensions in one cube. Emitting both under the bare field
        // name failed the whole schema with "defined more than once", and a
        // numeric column is genuinely both things: `amount` is worth summing,
        // and `scroll_depth_pct` is worth grouping by.
        measures[`total_${field.name}`] = {
          sql: () => field.name,
          type: 'sum',
          description: field.description
            ? `Sum of ${field.name}. ${field.description}`
            : `Sum of ${field.name}.`,
        };
      }
      dimensions[field.name] = {
        sql: () => field.name,
        type: field.cubeType,
        description: field.description ?? undefined,
      };
    }

    const joins = {};
    for (const join of joinsByTable[table.name] ?? []) {
      joins[join.toTable] = {
        relationship: join.relationship,
        // `CUBE` resolves to this cube's alias inside the function; the other
        // side is referenced by its cube name, which is the table name this
        // module generated it under.
        sql: () => `${CUBE}.${join.fromField} = ${join.toTable}.${join.toField}`,
      };
    }

    cube(table.name, {
      sql: () => `SELECT * FROM ${table.sqlTable}`,
      dataSource: 'connector',
      description: table.description ?? undefined,
      measures,
      dimensions,
      joins,
    });
  }
});
