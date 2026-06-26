import React from 'react';
import { Construction, Sparkles } from 'lucide-react';

interface UnderDevelopmentProps {
  featureName?: string;
  description?: string;
  planName?: string;
}

export const UnderDevelopment: React.FC<UnderDevelopmentProps> = ({
  featureName = 'This Feature',
  description = 'Our team is actively building this. It will be available in an upcoming release.',
  planName,
}) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-8 text-center">
      <div className="w-20 h-20 rounded-3xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-6">
        <Construction className="w-10 h-10 text-amber-400" />
      </div>
      <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-full text-xs font-semibold text-amber-400 mb-4">
        <Sparkles className="w-3 h-3" />
        Under Development
      </div>
      <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-3">{featureName}</h2>
      <p className="text-sm text-[var(--text-muted)] max-w-sm leading-relaxed mb-4">{description}</p>
      {planName && (
        <div className="px-4 py-2 bg-brand-500/10 border border-brand-500/20 rounded-xl text-xs text-brand-400 font-medium">
          ✓ Included in your <strong>{planName}</strong> plan — coming soon
        </div>
      )}
    </div>
  );
};
