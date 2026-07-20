// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { EscalationWidget } from '../EscalationWidget';
import { escalationApi } from '../../../services/escalationApi';

vi.mock('../../../services/escalationApi', () => ({ escalationApi: { dashboard: vi.fn() } }));

const DASH = {
  rules: 6, active: 5, escalations: 132, last_7_days: 9, by_entity: { lead: 80, task: 52 },
  recent: [
    { id: 'e1', rule_id: 'r1', entity_type: 'lead', entity_id: 'x', level: 1, escalate_to: 'manager', escalated_to_user_id: 'u', reason: 'idle', hours_elapsed: 30, escalated_at: null },
    { id: 'e2', rule_id: 'r2', entity_type: 'task', entity_id: 'y', level: 2, escalate_to: 'department_head', escalated_to_user_id: 'u', reason: 'overdue', hours_elapsed: 50, escalated_at: null },
  ],
};

describe('EscalationWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><EscalationWidget /></BrowserRouter>);

  it('renders rules/7-day/total and recent escalations', async () => {
    vi.mocked(escalationApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Escalation')).toBeDefined());
    expect(screen.getByText('5/6')).toBeDefined();       // active/rules
    expect(screen.getByText('9')).toBeDefined();          // last 7 days
    expect(screen.getByText('132')).toBeDefined();        // total
    expect(screen.getByText('lead · L1')).toBeDefined();
  });

  it('shows a loader before data resolves', () => {
    vi.mocked(escalationApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
