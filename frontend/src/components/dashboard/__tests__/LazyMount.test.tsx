// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, cleanup, act } from '@testing-library/react';
import { LazyMount } from '../LazyMount';

/**
 * These assertions matter because the dashboard's API-call budget depends on
 * them: if LazyMount mounted eagerly we would be back to ~136 calls per load,
 * and if it never mounted, below-the-fold widgets would silently never load.
 */
type IOCallback = (entries: Array<{ isIntersecting: boolean }>) => void;

let callbacks: IOCallback[] = [];
let disconnectCount = 0;

class MockIO {
  constructor(cb: IOCallback) { callbacks.push(cb); }
  observe() { /* noop */ }
  disconnect() { disconnectCount += 1; }
  unobserve() { /* noop */ }
}

describe('LazyMount', () => {
  beforeEach(() => {
    callbacks = [];
    disconnectCount = 0;
    (globalThis as any).IntersectionObserver = MockIO as any;
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it('does not render children until they intersect the viewport', () => {
    render(<LazyMount><div>widget-body</div></LazyMount>);
    expect(screen.queryByText('widget-body')).toBeNull();
  });

  it('renders children once intersection is reported', () => {
    render(<LazyMount><div>widget-body</div></LazyMount>);
    expect(screen.queryByText('widget-body')).toBeNull();
    act(() => { callbacks.forEach(cb => cb([{ isIntersecting: true }])); });
    expect(screen.getByText('widget-body')).toBeDefined();
  });

  it('stays mounted after scrolling away, so it never refetches', () => {
    render(<LazyMount><div>widget-body</div></LazyMount>);
    act(() => { callbacks.forEach(cb => cb([{ isIntersecting: true }])); });
    act(() => { callbacks.forEach(cb => cb([{ isIntersecting: false }])); });
    expect(screen.getByText('widget-body')).toBeDefined();
    expect(disconnectCount).toBeGreaterThan(0); // observer released after mount
  });

  it('mounts immediately when IntersectionObserver is unavailable', () => {
    delete (globalThis as any).IntersectionObserver;
    render(<LazyMount><div>widget-body</div></LazyMount>);
    expect(screen.getByText('widget-body')).toBeDefined();
  });
});
