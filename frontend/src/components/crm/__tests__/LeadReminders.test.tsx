// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { LeadReminders } from '../LeadReminders';
import { leadApi } from '../../../services/leadApi';

vi.mock('../../../services/leadApi', () => ({
  leadApi: {
    listReminders: vi.fn(),
    createReminder: vi.fn(),
    deleteReminder: vi.fn(),
  },
}));

describe('LeadReminders', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (leadApi.listReminders as any).mockResolvedValue([]);
    (leadApi.createReminder as any).mockResolvedValue({});
  });
  afterEach(() => cleanup());

  it('renders an Add button (it must not be hidden/clipped in the panel)', async () => {
    render(<LeadReminders leadId="lead-1" />);
    expect(await screen.findByRole('button', { name: /^add$/i })).toBeTruthy();
  });

  it('disables Add until a date is chosen via the picker', async () => {
    render(<LeadReminders leadId="lead-1" />);
    const add = (await screen.findByRole('button', { name: /^add$/i })) as HTMLButtonElement;
    expect(add.disabled).toBe(true);

    fireEvent.click(screen.getByRole('button', { name: /pick date & time/i })); // open picker
    fireEvent.click(screen.getByRole('button', { name: '15' }));                 // pick a day
    expect(add.disabled).toBe(false);
  });

  it('creates a reminder when Add is clicked after picking a date', async () => {
    render(<LeadReminders leadId="lead-1" />);
    await screen.findByRole('button', { name: /^add$/i });
    fireEvent.click(screen.getByRole('button', { name: /pick date & time/i }));
    fireEvent.click(screen.getByRole('button', { name: '15' }));
    fireEvent.click(screen.getByRole('button', { name: /^add$/i }));
    await waitFor(() => expect(leadApi.createReminder).toHaveBeenCalledTimes(1));
    expect((leadApi.createReminder as any).mock.calls[0][0]).toBe('lead-1');
  });
});
