// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { FailedRowsDownload } from '../FailedRowsDownload';

describe('FailedRowsDownload Component', () => {
  const mockOnDownloadFailedRows = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders nothing when there are no failed rows', () => {
    const { container } = render(
      <FailedRowsDownload
        importId="job-1"
        failedRowsCount={0}
        errorSummary={null}
        onDownloadFailedRows={mockOnDownloadFailedRows}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders errors list and triggers download on click', () => {
    const errors = [
      { row: 2, email: 'bad-email@test.com', reason: 'Email is already registered' },
      { row: 5, email: null, reason: 'Last Name is a required field and is missing' },
    ];

    render(
      <FailedRowsDownload
        importId="job-1"
        failedRowsCount={2}
        errorSummary={errors}
        onDownloadFailedRows={mockOnDownloadFailedRows}
      />
    );

    expect(screen.getByText('Row Validation Errors (2)')).toBeDefined();
    expect(screen.getByText('bad-email@test.com')).toBeDefined();
    expect(screen.getByText('Email is already registered')).toBeDefined();
    expect(screen.getByText('Last Name is a required field and is missing')).toBeDefined();

    const btn = screen.getByText('Download Error Report');
    fireEvent.click(btn);
    expect(mockOnDownloadFailedRows).toHaveBeenCalledWith('job-1');
  });
});
