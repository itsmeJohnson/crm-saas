// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { DateTimePicker } from '../DateTimePicker';

describe('DateTimePicker', () => {
  afterEach(() => cleanup());

  it('opens, emits a YYYY-MM-DDTHH:mm value when a day is picked', () => {
    const onChange = vi.fn();
    render(<DateTimePicker value="" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /select date & time/i }));
    fireEvent.click(screen.getByRole('button', { name: '15' }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toMatch(/^\d{4}-\d{2}-15T\d{2}:\d{2}$/);
  });

  it('closes when Done is clicked (the fix for the never-closing native popup)', () => {
    render(<DateTimePicker value="2026-07-15T09:35" onChange={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /15 Jul 2026/i }));
    expect(screen.getByRole('button', { name: /done/i })).toBeTruthy(); // panel open
    fireEvent.click(screen.getByRole('button', { name: /done/i }));
    expect(screen.queryByRole('button', { name: /done/i })).toBeNull();  // panel closed
  });

  it('closes on an outside click', () => {
    render(<div><DateTimePicker value="2026-07-15T09:35" onChange={() => {}} /><button>outside</button></div>);
    fireEvent.click(screen.getByRole('button', { name: /15 Jul 2026/i }));
    expect(screen.getByRole('button', { name: /done/i })).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole('button', { name: 'outside' }));
    expect(screen.queryByRole('button', { name: /done/i })).toBeNull();
  });
});
