/**
 * Error Instrumentation Exports
 * @module instrumentation/errors
 */

export {
  installErrorInstrumentation,
  uninstallErrorInstrumentation,
  captureError,
  createErrorBoundaryHandler,
  isErrorInstrumentationInstalled,
} from './error-instrumentation';

export {
  parseStackTrace,
  serializeStackFrames,
  cleanFilePath,
  getSourceMapUrl,
  extractSourceMapComment,
  isApplicationFrame,
  getTopApplicationFrames,
  createErrorFingerprint,
} from './source-map-resolver';
export type { StackFrame, ParsedStackTrace } from './source-map-resolver';
