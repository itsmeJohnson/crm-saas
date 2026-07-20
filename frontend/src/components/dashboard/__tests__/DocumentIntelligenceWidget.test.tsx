// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { DocumentIntelligenceWidget } from '../DocumentIntelligenceWidget';
import { documentIntelligenceApi } from '../../../services/documentIntelligenceApi';

vi.mock('../../../services/documentIntelligenceApi', () => ({
  documentIntelligenceApi: { dashboard: vi.fn() },
}));

const DASH = {
  totals: {
    documents: 23, by_type: { invoice: 9, contract: 5 }, by_status: { processed: 22, needs_ocr: 1 },
    pages: 87, ocr_used: 6, with_tables: 11, with_structured_extraction: 14,
  },
  recent: [],
  capabilities: {
    pdf: true, docx: true, xlsx: true, images: true, ocr: true,
    text_formats: ['.txt'], image_formats: ['.png'], embedding_model: 'hash_embed_v1',
  },
};

describe('DocumentIntelligenceWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><DocumentIntelligenceWidget /></BrowserRouter>);

  it('renders document, OCR and table stats', async () => {
    vi.mocked(documentIntelligenceApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Document Intelligence')).toBeDefined());
    expect(screen.getByText('23')).toBeDefined();
    expect(screen.getByText('6')).toBeDefined();
    expect(screen.getByText('11')).toBeDefined();
  });

  it('shows a fallback when the dashboard is unavailable', async () => {
    vi.mocked(documentIntelligenceApi.dashboard).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No document data/)).toBeDefined());
  });
});
