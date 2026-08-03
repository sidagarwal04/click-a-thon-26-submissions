/**
 * Vitest setup file
 * @module test/setup
 */

import '@testing-library/jest-dom';

import { configure } from '@testing-library/react';

/**
 * Configure Testing Library to use `data-ozid` as the test ID attribute
 * This allows us to use a single attribute for both testing and analytics
 */
configure({
  testIdAttribute: 'data-ozid',
});
