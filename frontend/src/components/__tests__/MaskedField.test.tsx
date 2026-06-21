// @vitest-environment happy-dom
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MaskedField } from '../common/MaskedField';

describe('MaskedField Component', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders fallback when value is null or undefined', () => {
    render(<MaskedField value={null} fallback="N/A" />);
    expect(screen.getByText('N/A')).toBeDefined();
  });

  it('renders original number if not masked (no asterisks)', () => {
    render(<MaskedField value="+919876543210" />);
    expect(screen.getByText('+919876543210')).toBeDefined();
  });

  it('renders masked format and Lock tooltip description when value has asterisks', () => {
    render(<MaskedField value="+91******10" />);
    expect(screen.getByText('+91******10')).toBeDefined();
    expect(screen.getByText('Protected Number')).toBeDefined();
  });
});
