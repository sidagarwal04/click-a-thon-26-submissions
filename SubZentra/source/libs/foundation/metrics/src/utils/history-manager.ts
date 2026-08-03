/**
 * Centralized History API Manager (Singleton)
 *
 * Patches History API once, all subscribers notified.
 * Prevents conflicts from multiple modules patching the same methods.
 *
 * @module utils/history-manager
 */

/**
 * Callback type for history change events
 */
export type HistoryCallback = (url: string, state: unknown) => void;

/**
 * Centralized History API manager as a singleton class.
 */
export class HistoryManager {
  private static instance: HistoryManager | null = null;

  private isInstalled = false;
  private originalPushState: History['pushState'] | null = null;
  private originalReplaceState: History['replaceState'] | null = null;
  private listeners = new Set<HistoryCallback>();

  private constructor() {
    this.install();
  }

  static getInstance = (): HistoryManager => {
    if (!HistoryManager.instance) {
      HistoryManager.instance = new HistoryManager();
    }
    return HistoryManager.instance;
  };

  static reset = (): void => {
    if (HistoryManager.instance) {
      HistoryManager.instance.uninstall();
      HistoryManager.instance = null;
    }
  };

  /**
   * Subscribe to history changes. Returns an unsubscribe function.
   */
  subscribe = (callback: HistoryCallback): (() => void) => {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  };

  /**
   * Get the current number of listeners
   */
  getListenerCount = (): number => this.listeners.size;

  private install = (): void => {
    if (typeof window === 'undefined' || typeof window.history === 'undefined') return;
    if (this.isInstalled) return;

    const historyApi = window.history;
    this.originalPushState = historyApi.pushState.bind(historyApi);
    this.originalReplaceState = historyApi.replaceState.bind(historyApi);

    const notifyListeners = (url: string, historyState: unknown): void => {
      for (const listener of this.listeners) {
        try {
          listener(url, historyState);
        } catch (e) {
          console.error('[HistoryManager] Listener error:', e);
        }
      }
    };

    historyApi.pushState = (data: unknown, unused: string, url?: string | URL | null) => {
      const originalPushState = this.originalPushState;
      if (originalPushState === null) {
        return;
      }
      originalPushState(data, unused, url);
      if (url) {
        notifyListeners(url.toString(), data);
      }
    };

    historyApi.replaceState = (data: unknown, unused: string, url?: string | URL | null) => {
      const originalReplaceState = this.originalReplaceState;
      if (originalReplaceState === null) {
        return;
      }
      originalReplaceState(data, unused, url);
      if (url) {
        notifyListeners(url.toString(), data);
      }
    };

    this.isInstalled = true;
  };

  private uninstall = (): void => {
    if (!this.isInstalled) return;

    const historyApi = window.history;
    if (this.originalPushState) {
      historyApi.pushState = this.originalPushState;
    }
    if (this.originalReplaceState) {
      historyApi.replaceState = this.originalReplaceState;
    }

    this.listeners.clear();
    this.isInstalled = false;
  };
}
