/**
 * Test state management for component testing
 * @module test/test-state
 */

interface ComponentTestState {
  name: string;
  themeKey: string;
}

function isComponentTestState(state: unknown): state is ComponentTestState {
  if (typeof state !== 'object' || state === null) {
    return false;
  }
  return (
    'name' in state &&
    typeof state['name'] === 'string' &&
    'themeKey' in state &&
    typeof state['themeKey'] === 'string'
  );
}

/**
 * Sets the testing component state in Vitest/Jest expect state
 *
 * @param component - Component test state
 */
export function setTestingComponentState(component: ComponentTestState): void {
  expect.setState({ component });
}

/**
 * Gets the current testing component state
 *
 * @returns Component test state
 * @throws Error if not called within describeComponent
 */
export function getTestingComponentState(): ComponentTestState {
  const { component } = expect.getState();
  if (!isComponentTestState(component)) {
    throw new Error(
      'Cannot get currently testing component state. Did you forget to run the test in `describeComponent`?',
    );
  }
  return component;
}

/**
 * Resets the testing component state
 */
export function resetTestingComponentState(): void {
  expect.setState({ component: undefined });
}
