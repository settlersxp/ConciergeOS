/**
 * Vitest test setup file.
 * Runs before each test file to configure testing utilities.
 */

import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Automatically cleanup after each test (unmounts React trees)
afterEach(() => {
  cleanup();
});