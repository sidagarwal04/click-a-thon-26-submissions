/**
 * Source Map Resolver
 * @module instrumentation/errors/source-map-resolver
 *
 * Note: Actual source map resolution should happen server-side
 * for security reasons. This module provides utilities for
 * preparing stack traces for server-side resolution.
 */

/**
 * Stack frame information
 */
export interface StackFrame {
  /** Function name */
  functionName: string;
  /** File name/URL */
  fileName: string;
  /** Line number */
  lineNumber: number;
  /** Column number */
  columnNumber: number;
  /** Is native code */
  isNative: boolean;
  /** Is eval */
  isEval: boolean;
  /** Source (for eval) */
  source?: string;
}

/**
 * Parsed stack trace
 */
export interface ParsedStackTrace {
  /** Original stack string */
  raw: string;
  /** Parsed frames */
  frames: StackFrame[];
  /** Error message */
  message?: string;
}

/**
 * Parse a stack trace string into frames
 */
export function parseStackTrace(stack: string): ParsedStackTrace {
  const lines = stack.split('\n');
  const frames: StackFrame[] = [];
  let message: string | undefined;

  // First line is usually the error message
  if (lines.length > 0 && !lines[0].trim().startsWith('at ')) {
    message = lines[0];
  }

  for (const line of lines) {
    const frame = parseStackFrame(line);
    if (frame) {
      frames.push(frame);
    }
  }

  return {
    raw: stack,
    frames,
    message,
  };
}

/**
 * Parse a single stack frame
 */
function parseStackFrame(line: string): StackFrame | null {
  const trimmed = line.trim();

  // Chrome/Edge/Node format: "    at functionName (file:line:column)"
  const chromeMatch = trimmed.match(/^at\s+(?:(.+?)\s+\()?(?:(.+?):(\d+):(\d+)|([^)]+))\)?$/);

  if (chromeMatch) {
    const [, functionName, fileName, lineNumber, columnNumber, evalSource] = chromeMatch;

    if (evalSource) {
      return {
        functionName: functionName || '<anonymous>',
        fileName: 'eval',
        lineNumber: 0,
        columnNumber: 0,
        isNative: false,
        isEval: true,
        source: evalSource,
      };
    }

    return {
      functionName: functionName || '<anonymous>',
      fileName: fileName || 'unknown',
      lineNumber: parseInt(lineNumber, 10) || 0,
      columnNumber: parseInt(columnNumber, 10) || 0,
      isNative: fileName === 'native' || functionName?.includes('[native code]'),
      isEval: fileName?.includes('eval') || false,
    };
  }

  // Firefox format: "functionName@file:line:column"
  const firefoxMatch = trimmed.match(/^(.*)@(.+):(\d+):(\d+)$/);

  if (firefoxMatch) {
    const [, functionName, fileName, lineNumber, columnNumber] = firefoxMatch;

    return {
      functionName: functionName || '<anonymous>',
      fileName: fileName || 'unknown',
      lineNumber: parseInt(lineNumber, 10) || 0,
      columnNumber: parseInt(columnNumber, 10) || 0,
      isNative: false,
      isEval: fileName?.includes('eval') || false,
    };
  }

  return null;
}

/**
 * Serialize stack frames for sending to server
 */
export function serializeStackFrames(frames: StackFrame[]): string {
  return JSON.stringify(
    frames.map((frame) => ({
      fn: frame.functionName,
      f: frame.fileName,
      l: frame.lineNumber,
      c: frame.columnNumber,
    })),
  );
}

/**
 * Clean file path for display (remove query strings, etc.)
 */
export function cleanFilePath(filePath: string): string {
  try {
    const url = new URL(filePath);
    return url.pathname;
  } catch {
    // Not a URL, return as-is
    return filePath;
  }
}

/**
 * Get source map URL for a file
 * Note: This is for documentation purposes - actual resolution should be server-side
 */
export function getSourceMapUrl(jsFileUrl: string): string {
  // Convention: source map is at same URL with .map extension
  return `${jsFileUrl}.map`;
}

/**
 * Extract source map comment from script content
 * Note: This should only be used in development/debugging
 */
export function extractSourceMapComment(scriptContent: string): string | null {
  // //# sourceMappingURL=...
  const match = scriptContent.match(/\/\/[#@]\s*sourceMappingURL=(.+?)(?:\s|$)/);
  return match ? match[1] : null;
}

/**
 * Check if a stack frame is from our application (not a library)
 */
export function isApplicationFrame(frame: StackFrame, applicationPaths: string[] = []): boolean {
  if (frame.isNative) {
    return false;
  }

  const fileName = frame.fileName.toLowerCase();

  // Exclude common library paths
  const libraryPatterns = ['node_modules', 'vendor', '/react.', '/react-dom.', 'webpack', 'chunk'];

  if (libraryPatterns.some((pattern) => fileName.includes(pattern))) {
    return false;
  }

  // Include if matches application paths
  if (applicationPaths.length > 0) {
    return applicationPaths.some((path) => fileName.includes(path.toLowerCase()));
  }

  return true;
}

/**
 * Get top N application frames from stack
 */
export function getTopApplicationFrames(
  stack: string,
  count = 5,
  applicationPaths: string[] = [],
): StackFrame[] {
  const parsed = parseStackTrace(stack);
  const appFrames = parsed.frames.filter((frame) => isApplicationFrame(frame, applicationPaths));
  return appFrames.slice(0, count);
}

/**
 * Create a fingerprint for error grouping
 */
export function createErrorFingerprint(
  error: { name: string; message: string; stack?: string },
  applicationPaths: string[] = [],
): string {
  const parts: string[] = [error.name];

  // Add cleaned message (remove dynamic parts)
  const cleanedMessage = error.message
    .replace(/\b\d+\b/g, 'N') // Replace numbers
    .replace(/["'][^"']+["']/g, '""') // Replace quoted strings
    .replace(/\b[0-9a-f]{8,}\b/gi, 'ID'); // Replace hex IDs

  parts.push(cleanedMessage);

  // Add top application frame
  if (error.stack) {
    const topFrames = getTopApplicationFrames(error.stack, 1, applicationPaths);
    if (topFrames.length > 0) {
      const frame = topFrames[0];
      parts.push(`${cleanFilePath(frame.fileName)}:${frame.lineNumber}`);
    }
  }

  return parts.join('|');
}
