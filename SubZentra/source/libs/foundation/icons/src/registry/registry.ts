import type { LucideIcon } from 'lucide-react';

import type { RegisterIconOptions } from '../types';

/**
 * All registered icon name literals.
 *
 * Keep this list in sync with the `registerIcon` calls in `./index.ts`.
 * The `IconName` union type is derived from this array so that consumers
 * get autocomplete and compile-time safety.
 */
export const ICON_NAMES = {
  // Navigation
  HOME: 'home',
  MENU: 'menu',
  CHEVRON_LEFT: 'chevron_left',
  CHEVRON_RIGHT: 'chevron_right',
  CHEVRON_UP: 'chevron_up',
  CHEVRON_DOWN: 'chevron_down',
  ARROW_LEFT: 'arrow_left',
  ARROW_RIGHT: 'arrow_right',
  ARROW_UP: 'arrow_up',
  ARROW_DOWN: 'arrow_down',
  NAVIGATION: 'navigation',
  NAVIGATION_2: 'navigation_2',
  COMPASS: 'compass',

  // Actions
  SEARCH: 'search',
  PLUS: 'plus',
  MINUS: 'minus',
  EDIT: 'edit',
  EDIT_2: 'edit_2',
  EDIT_3: 'edit_3',
  TRASH: 'trash',
  TRASH_2: 'trash_2',
  SAVE: 'save',
  X: 'x',
  CHECK: 'check',
  COPY: 'copy',
  SCISSORS: 'scissors',
  CLIPBOARD: 'clipboard',
  CLIPBOARD_COPY: 'clipboard_copy',
  DOWNLOAD: 'download',
  UPLOAD: 'upload',
  SHARE: 'share',
  SHARE_2: 'share_2',
  SEND: 'send',
  MAIL: 'mail',
  MESSAGE_SQUARE: 'message_square',
  PHONE: 'phone',
  VIDEO: 'video',
  CAMERA: 'camera',
  IMAGE: 'image',
  FILE: 'file',
  FILE_TEXT: 'file_text',
  FOLDER: 'folder',
  FOLDER_OPEN: 'folder_open',
  SETTINGS: 'settings',
  MORE_VERTICAL: 'more_vertical',
  MORE_HORIZONTAL: 'more_horizontal',
  FILTER: 'filter',
  SORT_ASC: 'sort_asc',
  SORT_DESC: 'sort_desc',

  // Status
  ALERT_CIRCLE: 'alert_circle',
  ALERT_TRIANGLE: 'alert_triangle',
  INFO: 'info',
  CHECK_CIRCLE: 'check_circle',
  X_CIRCLE: 'x_circle',
  HELP_CIRCLE: 'help_circle',
  LOADER_2: 'loader_2',
  CLOCK: 'clock',
  CALENDAR: 'calendar',
  BELL: 'bell',
  BELL_OFF: 'bell_off',
  STAR: 'star',
  HEART: 'heart',
  THUMBS_UP: 'thumbs_up',
  THUMBS_DOWN: 'thumbs_down',

  // UI
  USER: 'user',
  USERS: 'users',
  USER_PLUS: 'user_plus',
  USER_MINUS: 'user_minus',
  LOCK: 'lock',
  UNLOCK: 'unlock',
  EYE: 'eye',
  EYE_OFF: 'eye_off',
  SHIELD: 'shield',
  KEY: 'key',
  LOG_IN: 'log_in',
  LOG_OUT: 'log_out',
  COG: 'cog',
  WRENCH: 'wrench',
  GRID: 'grid',
  LIST: 'list',
  LAYOUT: 'layout',
  SIDEBAR: 'sidebar',
  PANEL_LEFT: 'panel_left',
  COLUMNS: 'columns',
  ROWS: 'rows',

  // Additional common
  REFRESH_CW: 'refresh_cw',
  ROTATE_CW: 'rotate_cw',
  ROTATE_CCW: 'rotate_ccw',
  ZOOM_IN: 'zoom_in',
  ZOOM_OUT: 'zoom_out',
  MAXIMIZE: 'maximize',
  MINIMIZE: 'minimize',
  EXTERNAL_LINK: 'external_link',
  LINK: 'link',
  BOOKMARK: 'bookmark',
  TAG: 'tag',
  TAGS: 'tags',
  SHOPPING_CART: 'shopping_cart',
  CREDIT_CARD: 'credit_card',
  PACKAGE: 'package',
  BOX: 'box',
  ARCHIVE: 'archive',
  INBOX: 'inbox',

  // Data
  DATABASE: 'database',
  NETWORK: 'network',
  SPARKLES: 'sparkles',
} as const;

/**
 * Union type of all available icon names.
 *
 * Provides compile-time autocomplete and safety when referencing icons
 * by name. Accepts any string in `ICON_NAMES` plus arbitrary strings
 * registered at runtime via `registerIcon`.
 */
export type IconName = (typeof ICON_NAMES)[keyof typeof ICON_NAMES];

/**
 * Registry of available icons.
 *
 * Maps icon names to their lucide-react components for string-based lookup
 * via the `<Icon name="..." />` component.
 *
 * Note: lucide-react is tree-shakeable. The bundled cost is determined by
 * which icons are registered here, not by the lucide-react package itself.
 */
const iconRegistry = new Map<IconName, LucideIcon>();

/**
 * Register a new icon in the registry
 *
 * @param options - Options for registering the icon
 * @throws Error if icon name already exists
 *
 * @example
 * ```ts
 * import { Home } from 'lucide-react';
 * registerIcon({ name: 'home', component: Home });
 * ```
 */
export function registerIcon(options: RegisterIconOptions): void {
  const { name, component } = options;

  if (iconRegistry.has(name)) {
    throw new Error(`Icon "${name}" is already registered`);
  }

  iconRegistry.set(name, component);
}

/**
 * Get an icon component from the registry by name
 *
 * @param name - Name of the icon to retrieve
 * @returns The icon component or undefined if not found
 */
export function getIcon(name: IconName): LucideIcon | undefined {
  return iconRegistry.get(name);
}

/**
 * Check if an icon is registered
 *
 * @param name - Name of the icon to check
 * @returns True if the icon is registered, false otherwise
 */
export function hasIcon(name: IconName): boolean {
  return iconRegistry.has(name);
}

/**
 * Get all registered icon names
 *
 * Reads the registry, not `ICON_NAMES`. The constant is the catalogue of names
 * the library ships; the registry is what has actually been registered, which
 * is what a caller asking this question wants — including icons registered at
 * runtime, and excluding the built-ins after `clearRegistry`.
 *
 * @returns Array of all registered icon names
 */
export function getAllIconNames(): IconName[] {
  return Array.from(iconRegistry.keys());
}

/**
 * Clear all registered icons (useful for testing)
 */
export function clearRegistry(): void {
  iconRegistry.clear();
}
