/**
 * The rendered generative UI.
 *
 * `c1_response` is an opaque payload produced by Thesys from the governed
 * brief, so it is handed to `<C1Component>` rather than parsed here — the
 * whole point of the renderer is that this side does not know what shape the
 * answer took. `<C1Chat>` is deliberately not used: it would run its own
 * conversation loop against its own endpoint, and the conversation already
 * belongs to the Thread API.
 *
 * Interactivity is the part that needs care. A button in this payload was
 * written by a model, so whatever parameters it carries are untrusted. Only
 * the `action_id` is read, and only when it matches an action the *server*
 * put in the brief; everything else is dropped, and the server drops it again.
 */

import { C1Component, ThemeProvider } from '@thesysai/genui-sdk';

import '@crayonai/react-ui/styles/index.css';
import '@thesysai/genui-sdk/dist/genui-sdk.css';

import type { BriefAction } from '../../types';

/** Pull an action id out of whatever the renderer attached to the event. */
const actionIdFrom = (params: Record<string, unknown> | undefined): string | null => {
  const candidate = params?.['action_id'] ?? params?.['actionId'] ?? params?.['id'];
  return typeof candidate === 'string' ? candidate : null;
};

export const C1Answer = ({
  c1Response,
  actions,
  onAction,
}: {
  readonly c1Response: string;
  /** The actions the server authored. Nothing outside this list is executable. */
  readonly actions: readonly BriefAction[];
  readonly onAction: (actionId: string) => void;
}) => (
  <ThemeProvider mode="dark">
    <C1Component
      c1Response={c1Response}
      isStreaming={false}
      onAction={(event) => {
        const actionId = actionIdFrom(event.params);
        if (actionId && actions.some((action) => action.action_id === actionId)) {
          onAction(actionId);
        }
      }}
    />
  </ThemeProvider>
);

export default C1Answer;
