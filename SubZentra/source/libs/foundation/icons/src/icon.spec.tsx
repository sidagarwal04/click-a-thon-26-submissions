/**
 * @vitest-environment jsdom
 */
import { render } from '@testing-library/react';
import type { RenderResult } from '@testing-library/react';
import { Home, Search } from 'lucide-react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Icon } from './icon';
import { clearRegistry, registerIcon } from './registry/registry';
import type { IconName } from './registry/registry';

// Helper to safely query container (container is HTMLElement with querySelector in jsdom)
const queryContainer = (container: RenderResult['container'], selector: string) => {
  return (container as unknown as Element).querySelector(selector);
};

describe('Icon', () => {
  beforeEach(() => {
    clearRegistry();
    registerIcon({ name: 'home', component: Home });
    registerIcon({ name: 'search', component: Search });
  });

  it('should render successfully', () => {
    const { container } = render(<Icon name="home" />);
    expect(container).toBeTruthy();
  });

  it('should render the correct icon', () => {
    const { container } = render(<Icon name="home" />);
    // container is HTMLElement which has querySelector in jsdom environment
    const svg = queryContainer(container, 'svg');
    expect(svg).toBeTruthy();
  });

  it('should apply default size classes', () => {
    const { container } = render(<Icon name="home" />);
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.className).toContain('h-4 w-4'); // base size
  });

  it('should apply custom size classes', () => {
    const { container } = render(<Icon name="home" size="lg" />);
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.className).toContain('h-5 w-5'); // lg size
  });

  it('should apply custom className', () => {
    const { container } = render(<Icon name="home" className="text-blue-500" />);
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.className).toContain('text-blue-500');
  });

  it('should apply iconClassName to SVG', () => {
    const { container } = render(<Icon name="home" iconClassName="fill-current" />);
    const svg = queryContainer(container, 'svg') as SVGElement;
    expect(svg).toBeTruthy();
    // Check if the class is present in the rendered HTML
    // This works around jsdom's handling of SVG className
    const html = container.innerHTML;
    expect(html).toContain('fill-current');
  });

  it('should include flex and justify-center classes', () => {
    const { container } = render(<Icon name="home" />);
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.className).toContain('flex');
    expect(wrapper?.className).toContain('justify-center');
    expect(wrapper?.className).toContain('items-center');
  });

  it('should apply w-full h-full to SVG', () => {
    const { container } = render(<Icon name="home" />);
    const svg = queryContainer(container, 'svg') as SVGElement;
    expect(svg).toBeTruthy();
    // Check if the classes are present in the rendered HTML
    // This works around jsdom's handling of SVG className
    const html = container.innerHTML;
    expect(html).toContain('w-full');
    expect(html).toContain('h-full');
  });

  it('should handle onClick', () => {
    const handleClick = vi.fn();
    const { container } = render(<Icon name="home" onClick={handleClick} />);
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    if (wrapper) {
      (wrapper as HTMLElement).click();
    }
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('should apply inline styles', () => {
    const { container } = render(<Icon name="home" style={{ color: 'red' }} />);
    const wrapper = queryContainer(container, 'i') as HTMLElement;
    expect(wrapper).toBeTruthy();
    // In jsdom, style.color might be normalized, so check the style object directly
    expect(wrapper.style.getPropertyValue('color')).toBe('red');
  });

  it('should apply data-testid', () => {
    const { container } = render(<Icon name="home" data-testid="test-icon" />);
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.getAttribute('data-testid')).toBe('test-icon');
  });

  it('should apply aria-label', () => {
    const { container } = render(<Icon name="home" aria-label="Home icon" />);
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.getAttribute('aria-label')).toBe('Home icon');
  });

  it('should set aria-hidden by default', () => {
    const { container } = render(<Icon name="home" />);
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.getAttribute('aria-hidden')).toBe('true');
  });

  it('should not set aria-hidden when aria-label is provided', () => {
    const { container } = render(<Icon name="home" aria-label="Home icon" />);
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    // When aria-label is provided, aria-hidden is set to undefined, so the attribute is not present
    expect(wrapper?.hasAttribute('aria-hidden')).toBe(false);
  });

  it('should render fallback placeholder for unregistered icon', () => {
    const { container } = render(<Icon name={'non-existent' as IconName} />);
    // When icon is not found, component renders a fallback placeholder
    const wrapper = queryContainer(container, 'i');
    expect(wrapper).toBeTruthy();
    // Placeholder contains an SVG with a rect and two crossing lines
    const svg = queryContainer(container, 'svg');
    expect(svg).toBeTruthy();
    const rect = queryContainer(container, 'rect');
    expect(rect).toBeTruthy();
    const lines = container.querySelectorAll('line');
    expect(lines).toHaveLength(2);
  });

  it('should support all size variants', () => {
    const sizes = [
      '4xs',
      '3xs',
      '2xs',
      'xs',
      'sm',
      'base',
      'lg',
      'xl',
      '2xl',
      '3xl',
      '4xl',
      '5xl',
      '9xl',
      '12xl',
      '16xl',
      '24xl',
      'full',
    ] as const;

    sizes.forEach((size) => {
      const { container } = render(<Icon name="home" size={size} />);
      const wrapper = queryContainer(container, 'i');
      expect(wrapper).toBeTruthy();
    });
  });
});
