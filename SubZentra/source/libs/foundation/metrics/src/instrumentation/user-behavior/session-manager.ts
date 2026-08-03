/**
 * Session Manager
 * @module instrumentation/user-behavior/session-manager
 */

import { generateId, hashStringSync } from '@open-zentra/foundation-utils';

import { getSpanAttributes } from '../../core/context-manager';
import { getMeter } from '../../core/otel-provider';
import type { SessionData, SessionState, UserBehaviorSignalConfig } from '../../types';

/**
 * Session manager state
 */
interface SessionManagerState {
  config: UserBehaviorSignalConfig;
  isInstalled: boolean;
  session: SessionData;
  lastActivityTime: number;
  activityCheckInterval: ReturnType<typeof setInterval> | null;
  callback?: (session: SessionData) => void;
}

let state: SessionManagerState | null = null;

const SESSION_STORAGE_KEY = 'fm_session';

/**
 * Install session manager
 */
export function installSessionManager(
  config: UserBehaviorSignalConfig,
  callback?: (session: SessionData) => void,
): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (state?.isInstalled) {
    console.warn('[FoundationMetrics] Session manager already installed');
    return;
  }

  // Try to restore existing session
  const existingSession = restoreSession();
  const now = Date.now();

  const session: SessionData = existingSession || {
    id: hashStringSync(generateId()),
    startTime: now,
    lastActivityTime: now,
    state: 'active',
    pageViewCount: 0,
    interactionCount: 0,
    errorCount: 0,
  };

  state = {
    config,
    isInstalled: false,
    session,
    lastActivityTime: now,
    activityCheckInterval: null,
    callback,
  };

  if (!config.trackSession) {
    return;
  }

  // Check if session has expired
  const sessionTimeout = config.sessionTimeout || 30 * 60 * 1000;
  if (existingSession && now - existingSession.lastActivityTime > sessionTimeout) {
    // Session expired, create new one
    startNewSession();
  }

  // Listen for user activity
  document.addEventListener('click', handleActivity, { passive: true });
  document.addEventListener('keydown', handleActivity, { passive: true });
  document.addEventListener('scroll', handleActivity, { passive: true });
  document.addEventListener('mousemove', handleActivityThrottled, { passive: true });

  // Listen for visibility changes
  document.addEventListener('visibilitychange', handleVisibilityChange);

  // Listen for beforeunload to save session
  window.addEventListener('beforeunload', saveSession);

  // Set up periodic session check
  state.activityCheckInterval = setInterval(checkSessionStatus, 60000); // Every minute

  // Increment page view count
  incrementPageViews();

  // Save initial session
  saveSession();

  state.isInstalled = true;
}

/**
 * Uninstall session manager
 */
export function uninstallSessionManager(): void {
  // Clear the throttle timeout to prevent memory leaks
  if (throttleTimeout) {
    clearTimeout(throttleTimeout);
    throttleTimeout = null;
  }

  if (typeof document !== 'undefined') {
    document.removeEventListener('click', handleActivity);
    document.removeEventListener('keydown', handleActivity);
    document.removeEventListener('scroll', handleActivity);
    document.removeEventListener('mousemove', handleActivityThrottled);
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  }

  if (typeof window !== 'undefined') {
    window.removeEventListener('beforeunload', saveSession);
  }

  if (state?.activityCheckInterval) {
    clearInterval(state.activityCheckInterval);
  }

  state = null;
}

/**
 * Handle user activity
 */
function handleActivity(): void {
  if (!state?.config.enabled) {
    return;
  }

  const now = Date.now();
  state.lastActivityTime = now;
  state.session.lastActivityTime = now;

  // Update session state if it was inactive
  if (state.session.state !== 'active') {
    state.session.state = 'active';
    recordSessionStateChange('active');
  }
}

/**
 * Throttled activity handler for frequent events
 */
let throttleTimeout: ReturnType<typeof setTimeout> | null = null;
function handleActivityThrottled(): void {
  if (throttleTimeout) {
    return;
  }

  throttleTimeout = setTimeout(() => {
    handleActivity();
    throttleTimeout = null;
  }, 1000);
}

/**
 * Handle visibility change
 */
function handleVisibilityChange(): void {
  if (!state?.config.enabled) {
    return;
  }

  if (document.visibilityState === 'hidden') {
    // Save session when page becomes hidden
    saveSession();
  } else {
    // Check if session should be renewed when page becomes visible
    checkSessionStatus();
  }
}

/**
 * Check session status
 */
function checkSessionStatus(): void {
  if (!state?.config.enabled) {
    return;
  }

  const now = Date.now();
  const sessionTimeout = state.config.sessionTimeout || 30 * 60 * 1000;
  const timeSinceActivity = now - state.lastActivityTime;

  if (timeSinceActivity > sessionTimeout) {
    // Session expired
    if (state.session.state !== 'expired') {
      state.session.state = 'expired';
      recordSessionStateChange('expired');
      recordSessionEnd();
    }
  } else if (timeSinceActivity > sessionTimeout / 2) {
    // Session inactive
    if (state.session.state === 'active') {
      state.session.state = 'inactive';
      recordSessionStateChange('inactive');
    }
  }
}

/**
 * Start a new session
 */
export function startNewSession(): void {
  if (!state) {
    return;
  }

  const now = Date.now();

  // Record end of previous session
  if (state.session.state !== 'expired') {
    recordSessionEnd();
  }

  // Create new session
  state.session = {
    id: hashStringSync(generateId()),
    startTime: now,
    lastActivityTime: now,
    state: 'active',
    pageViewCount: 1,
    interactionCount: 0,
    errorCount: 0,
  };

  state.lastActivityTime = now;

  // Record new session start
  recordSessionStart();
  saveSession();

  state.callback?.(state.session);
}

/**
 * Increment page views
 */
export function incrementPageViews(): void {
  if (!state) {
    return;
  }

  state.session.pageViewCount++;
  handleActivity();
}

/**
 * Increment interaction count
 */
export function incrementInteractions(): void {
  if (!state) {
    return;
  }

  state.session.interactionCount++;
  handleActivity();
}

/**
 * Increment error count
 */
export function incrementErrors(): void {
  if (!state) {
    return;
  }

  state.session.errorCount++;
}

/**
 * Get current session
 */
export function getCurrentSession(): SessionData | null {
  return state?.session ?? null;
}

/**
 * Get session ID
 */
export function getSessionId(): string {
  return state?.session.id ?? '';
}

/**
 * Save session to storage
 */
function saveSession(): void {
  if (!state || typeof sessionStorage === 'undefined') {
    return;
  }

  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(state.session));
  } catch {
    // Storage not available
  }
}

/**
 * Restore session from storage
 */
function restoreSession(): SessionData | null {
  if (typeof sessionStorage === 'undefined') {
    return null;
  }

  try {
    const stored = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch {
    // Invalid or no stored session
  }

  return null;
}

/**
 * Record session start
 */
function recordSessionStart(): void {
  try {
    const meter = getMeter();
    const spanAttributes = getSpanAttributes();

    const sessionCounter = meter.createCounter('sessions_started_total', {
      description: 'Total number of sessions started',
    });

    sessionCounter.add(1, spanAttributes);
  } catch (e) {
    console.error('[FoundationMetrics] Error recording session start:', e);
  }
}

/**
 * Record session end
 */
function recordSessionEnd(): void {
  if (!state) {
    return;
  }

  try {
    const meter = getMeter();
    const spanAttributes = getSpanAttributes();

    // Session duration
    const sessionDuration = Date.now() - state.session.startTime;
    const durationHistogram = meter.createHistogram('session_duration_ms', {
      description: 'Session duration in milliseconds',
      unit: 'ms',
    });

    durationHistogram.record(sessionDuration, spanAttributes);

    // Page views per session
    const pageViewsHistogram = meter.createHistogram('session_page_views', {
      description: 'Page views per session',
    });

    pageViewsHistogram.record(state.session.pageViewCount, spanAttributes);

    // Interactions per session
    const interactionsHistogram = meter.createHistogram('session_interactions', {
      description: 'Interactions per session',
    });

    interactionsHistogram.record(state.session.interactionCount, spanAttributes);

    // Sessions with errors
    if (state.session.errorCount > 0) {
      const errorSessionCounter = meter.createCounter('sessions_with_errors_total', {
        description: 'Total number of sessions with errors',
      });

      errorSessionCounter.add(1, spanAttributes);
    }
  } catch (e) {
    console.error('[FoundationMetrics] Error recording session end:', e);
  }
}

/**
 * Record session state change
 */
function recordSessionStateChange(newState: SessionState): void {
  try {
    const meter = getMeter();
    const spanAttributes = getSpanAttributes();

    const stateChangeCounter = meter.createCounter('session_state_changes_total', {
      description: 'Total number of session state changes',
    });

    stateChangeCounter.add(1, {
      ...spanAttributes,
      'session.state': newState,
    });
  } catch (e) {
    console.error('[FoundationMetrics] Error recording session state change:', e);
  }
}

/**
 * Check if session manager is installed
 */
export function isSessionManagerInstalled(): boolean {
  return state?.isInstalled ?? false;
}
