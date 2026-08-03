/**
 * Axios Internal Config Augmentations
 *
 * Internal metadata fields attached by foundation-http interceptors.
 */

import 'axios';

declare module 'axios' {
  interface InternalAxiosRequestConfig {
    __oiHttpRetryCount?: number;
    __oiHttpRetryStartTime?: number;
    __oiHttpHostKey?: string;
  }
}

export {};
