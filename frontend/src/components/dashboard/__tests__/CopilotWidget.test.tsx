// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { CopilotWidget } from '../CopilotWidget';

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<any>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});
vi.mock('../../../services/copilotApi', () => ({ copilotApi: { capabilities: vi.fn().mockResolvedValue({}) } }));

describe('CopilotWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><CopilotWidget /></BrowserRouter>);

  it('renders the launcher and suggestion chips', () => {
    renderWidget();
    expect(screen.getByText('CRM Copilot')).toBeDefined();
    expect(screen.getByText('Find opportunities')).toBeDefined();
    expect(screen.getByPlaceholderText(/Ask the CRM anything/)).toBeDefined();
  });

  it('navigates to the copilot with the typed question as seed', () => {
    renderWidget();
    const input = screen.getByPlaceholderText(/Ask the CRM anything/);
    fireEvent.change(input, { target: { value: 'how many leads' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(navigate).toHaveBeenCalledWith('/copilot', { state: { seed: 'how many leads' } });
  });
});
