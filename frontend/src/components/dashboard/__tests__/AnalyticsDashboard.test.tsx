// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { AnalyticsDashboard } from '../AnalyticsDashboard';

// Mock state container
let mockStoreState = {
  dashboardData: null as any,
  isLoading: false,
  error: null as string | null,
  fetchDashboardMetrics: vi.fn(),
};

// Mock the Zustand store
vi.mock('../../../store/analyticsStore', () => ({
  useAnalyticsStore: () => mockStoreState,
}));

describe('AnalyticsDashboard Component', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    mockStoreState = {
      dashboardData: null,
      isLoading: false,
      error: null,
      fetchDashboardMetrics: vi.fn(),
    };
  });

  afterEach(() => {
    cleanup();
  });

  it('renders loading skeletons when isLoading is true and no data is present', () => {
    mockStoreState.isLoading = true;

    const { container } = render(<AnalyticsDashboard />);
    const skeletons = container.getElementsByClassName('animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders error message and retry button when error is present', () => {
    const mockRetry = vi.fn();
    mockStoreState.error = 'Network Timeout Exception';
    mockStoreState.fetchDashboardMetrics = mockRetry;

    render(<AnalyticsDashboard />);
    expect(screen.getByText('Failed to Load Performance Analytics')).toBeDefined();
    expect(screen.getByText('Network Timeout Exception')).toBeDefined();
    expect(screen.getByText('Retry Connection')).toBeDefined();
  });

  it('renders Agent Canvas for Telecaller role correctly', () => {
    mockStoreState.dashboardData = {
      role: 'Telecaller',
      metrics: {
        calls_made: 40,
        unique_leads_contacted: 30,
        conversions: 10,
        date: '2026-06-21',
      },
    };

    render(<AnalyticsDashboard />);
    
    // Telemetry components
    expect(screen.getByText("Today's Calls")).toBeDefined();
    expect(screen.getByText("Converted")).toBeDefined();
    expect(screen.getByText("Follow-up Counter")).toBeDefined();
    expect(screen.getByText("Conversion Ratio")).toBeDefined();

    // Verification of computed values
    expect(screen.getByText('40')).toBeDefined(); // calls
    expect(screen.getByText('10')).toBeDefined(); // conversions
    expect(screen.getByText('20')).toBeDefined(); // follow-up counter: unique(30) - conversions(10) = 20
    expect(screen.getByText('25.0%')).toBeDefined(); // conversion ratio: 10 / 40 = 25%
  });

  it('renders Team Leader Canvas with Performers Matrix', () => {
    mockStoreState.dashboardData = {
      role: 'TeamLeader',
      metrics: {
        total_calls_made: 150,
        total_conversions: 30,
        top_performer: {
          user_id: 'agent-1',
          first_name: 'John',
          last_name: 'Doe',
          calls_made: 50,
          conversions: 15,
          conversion_rate: 30,
        },
        low_performer: {
          user_id: 'agent-2',
          first_name: 'Jane',
          last_name: 'Smith',
          calls_made: 30,
          conversions: 2,
          conversion_rate: 6.7,
        },
        downlines: [
          {
            user_id: 'agent-1',
            first_name: 'John',
            last_name: 'Doe',
            email: 'john@company.com',
            calls_made: 50,
            unique_leads_contacted: 40,
            conversions: 15,
            conversion_rate: 30,
          },
          {
            user_id: 'agent-2',
            first_name: 'Jane',
            last_name: 'Smith',
            email: 'jane@company.com',
            calls_made: 30,
            unique_leads_contacted: 25,
            conversions: 2,
            conversion_rate: 6.7,
          },
        ],
      },
    };

    render(<AnalyticsDashboard />);

    // Cumulative stats
    expect(screen.getByText('Team Calls Made')).toBeDefined();
    expect(screen.getByText('150')).toBeDefined();
    expect(screen.getByText('Team Conversions')).toBeDefined();
    expect(screen.getAllByText('30')).toBeDefined(); // Matches 30 team conversions & 30% conversion rate of John
    expect(screen.getByText(/20\.0/)).toBeDefined(); // 30/150 = 20%

    // Leadership performers matrix elements
    expect(screen.getByText('Telecaller Performance Matrix')).toBeDefined();
    expect(screen.getByText('John Doe')).toBeDefined();
    expect(screen.getByText('Jane Smith')).toBeDefined();
    
    // Performance badges
    expect(screen.getByText('Top Performer')).toBeDefined();
    expect(screen.getByText('Low Performer')).toBeDefined();
  });

  it('renders Manager Canvas with side-by-side comparative group cards sorted by conversions', () => {
    mockStoreState.dashboardData = {
      role: 'Manager',
      metrics: {
        total_calls_made: 500,
        total_conversions: 100,
        teams: [
          {
            tl_id: 'tl-1',
            tl_first_name: 'Alice',
            tl_last_name: 'Leader',
            tl_email: 'alice@company.com',
            total_calls_made: 200,
            total_conversions: 60,
          },
          {
            tl_id: 'tl-2',
            tl_first_name: 'Bob',
            tl_last_name: 'Boss',
            tl_email: 'bob@company.com',
            total_calls_made: 300,
            total_conversions: 40,
          },
        ],
      },
    };

    render(<AnalyticsDashboard />);

    // Manager summary totals
    expect(screen.getByText('Manager Operational Cluster overview')).toBeDefined();
    expect(screen.getByText('500')).toBeDefined(); // total calls
    expect(screen.getByText('100')).toBeDefined(); // total conversions
    expect(screen.getByText(/20\.0/)).toBeDefined(); // 100/500 = 20%

    // Dynamic High vs Low performing nodes
    expect(screen.getByText('Alice Leader')).toBeDefined();
    expect(screen.getByText('High Production')).toBeDefined(); // Alice has 60 conversions (more than Bob's 40)
    
    expect(screen.getByText('Bob Boss')).toBeDefined();
    expect(screen.getByText('Low Production')).toBeDefined(); // Bob has 40 conversions (fewer than Alice's 60)
  });

  it('renders Super Admin Canvas with target horizontal progress milestones and text readouts', () => {
    mockStoreState.dashboardData = {
      role: 'SuperAdmin',
      metrics: {
        targets_progress: [
          {
            target_id: 'target-1',
            target_type: 'MONTHLY',
            metric_type: 'LEADS_CONVERTED',
            target_value: 100,
            actual_value: 78,
            progress_percentage: 78,
          },
          {
            target_id: 'target-2',
            target_type: 'DAILY',
            metric_type: 'CALLS_MADE',
            target_value: 100,
            actual_value: 50,
            progress_percentage: 50,
          },
        ],
      },
    };

    render(<AnalyticsDashboard />);

    expect(screen.getByText('Organizational Performance Milestones')).toBeDefined();
    
    // Clear text readout verification using custom matcher functions
    expect(screen.getAllByText((_, node) => {
      const text = node?.textContent || '';
      return text.includes('Monthly') && text.includes('Conversion') && text.includes('Goal Achieved');
    }).length).toBeGreaterThan(0);

    expect(screen.getAllByText((_, node) => {
      const text = node?.textContent || '';
      return text.includes('Daily') && text.includes('Call') && text.includes('Goal Achieved');
    }).length).toBeGreaterThan(0);
  });
});
