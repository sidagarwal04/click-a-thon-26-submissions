import type { ComponentProps } from 'react';

import type { HotkeysProvider as BaseHotkeysProvider } from 'react-hotkeys-hook';

export { HotkeysProvider } from 'react-hotkeys-hook';

export type HotkeysProviderProps = ComponentProps<typeof BaseHotkeysProvider>;
