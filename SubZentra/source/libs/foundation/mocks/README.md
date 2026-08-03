# Foundation Mocks

`@open-zentra/foundation-mocks` provides test builders and mock utilities for foundation-layer tests.

## Purpose

Use this package in unit/integration tests to create consistent, typed test data and payloads.

## Public Surface

- Builders from `./src/builders`
- Domain-specific mock helpers exported by library index

## Example

```ts
import { MutationBuilder, QueryBuilder } from '@open-zentra/foundation-mocks';

const query = QueryBuilder.create().withTable('events').withMeasure('count', 'count').build();
const mutation = MutationBuilder.create()
  .ofType('create')
  .forTable('users')
  .withData({ name: 'Ada' })
  .build();
```
