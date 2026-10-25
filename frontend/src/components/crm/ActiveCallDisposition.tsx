import React from 'react';
import { FloatingDialerWidget } from './FloatingDialerWidget';
import { CallDispositionModal } from './CallDispositionModal';

export const ActiveCallDisposition: React.FC = () => {
  return (
    <>
      <FloatingDialerWidget />
      <CallDispositionModal />
    </>
  );
};
