# Foundation Hooks

`@open-zentra/foundation-hooks` contains reusable React hooks shared across foundation libraries and apps.

## Purpose

Use this package for small, framework-specific hook utilities that should not live in `foundation-utils`.

## Exported Hooks

- `useMountedRef`
- `useCallbackRef`
- `useAbortController`
- `useStableCallback`

## Example

```tsx
import { useAbortController, useStableCallback } from '@open-zentra/foundation-hooks';

export function SearchBox() {
  const { signal, reset } = useAbortController();
  const onSearch = useStableCallback(async (query: string) => {
    reset();
    await fetch(`/api/search?q=${encodeURIComponent(query)}`, { signal });
  });

  return <input onChange={(e) => void onSearch(e.target.value)} />;
}
```
