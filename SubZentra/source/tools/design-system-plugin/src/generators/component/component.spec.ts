import type { Tree } from '@nx/devkit';
import { createTreeWithEmptyWorkspace } from '@nx/devkit/testing';

import { componentGenerator } from './component';
import type { ComponentGeneratorSchema } from './schema';

const DESIGN_SYSTEM_COMPONENTS = 'libs/foundation/design-system/src/components';

describe('component generator', () => {
  let tree: Tree;
  const options: ComponentGeneratorSchema = { name: 'test' };

  beforeEach(() => {
    tree = createTreeWithEmptyWorkspace();
    tree.write(`${DESIGN_SYSTEM_COMPONENTS}/index.ts`, '');
  });

  // This generator adds a component to the existing design-system library. It
  // never calls addProjectConfiguration, so what there is to assert is the
  // files it emits and the barrel it updates.
  it('emits the component, its types, its spec and a barrel', async () => {
    await componentGenerator(tree, options);

    expect(tree.exists(`${DESIGN_SYSTEM_COMPONENTS}/test/test.tsx`)).toBe(true);
    expect(tree.exists(`${DESIGN_SYSTEM_COMPONENTS}/test/test.types.ts`)).toBe(true);
    expect(tree.exists(`${DESIGN_SYSTEM_COMPONENTS}/test/test.spec.tsx`)).toBe(true);
    expect(tree.exists(`${DESIGN_SYSTEM_COMPONENTS}/test/index.ts`)).toBe(true);
  });

  it('exports the component from the components barrel', async () => {
    await componentGenerator(tree, options);

    expect(tree.read(`${DESIGN_SYSTEM_COMPONENTS}/index.ts`)?.toString()).toContain(
      "export * from './test';",
    );
  });

  it('leaves the barrel alone for a component that is not public', async () => {
    await componentGenerator(tree, { ...options, isPublic: false });

    expect(tree.read(`${DESIGN_SYSTEM_COMPONENTS}/index.ts`)?.toString()).not.toContain(
      "export * from './test';",
    );
  });

  it('omits the spec when tests are skipped', async () => {
    await componentGenerator(tree, { ...options, skipTests: true });

    expect(tree.exists(`${DESIGN_SYSTEM_COMPONENTS}/test/test.spec.tsx`)).toBe(false);
    expect(tree.exists(`${DESIGN_SYSTEM_COMPONENTS}/test/test.tsx`)).toBe(true);
  });

  it('nests the component when a directory is given', async () => {
    await componentGenerator(tree, { ...options, directory: 'forms' });

    expect(tree.exists(`${DESIGN_SYSTEM_COMPONENTS}/forms/test/test.tsx`)).toBe(true);
    expect(tree.read(`${DESIGN_SYSTEM_COMPONENTS}/index.ts`)?.toString()).toContain(
      "export * from './forms/test';",
    );
  });
});
