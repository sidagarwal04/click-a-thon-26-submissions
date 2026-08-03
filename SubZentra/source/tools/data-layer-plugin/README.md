# Data Layer Plugin

Nx generator plugin for creating CRUD wrapper hooks aligned with `@open-zentra/foundation-data-layer`.

## Usage

```bash
nx g @open-zentra/data-layer-plugin:crud product \
  --directory=libs/products/data-layer/src \
  --dataModel=@open-zentra/products-data-model \
  --endpoint=/api/products
```

## What It Generates

- query-key helpers
- detail/list hooks backed by `ApiQueryDescriptor`
- create/update/delete hooks backed by `ApiMutationDescriptor`
- default endpoint descriptors using the provided `--endpoint`

The generated wrappers provide:

- table naming
- default query keys
- default HTTP descriptor scaffolding
- a clean extension point if you want to override the generated descriptor
