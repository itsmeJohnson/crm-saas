import React, { useEffect, useState } from 'react';
import { companyApi, CompanyCommunication } from '../../services/companyApi';
import { Phone, Mail, PlayCircle } from 'lucide-react';

export const CompanyCommunications: React.FC<{ companyId: string }> = ({ companyId }) => {
  const [items, setItems] = useState<CompanyCommunication[]>([]);

  useEffect(() => {
    companyApi.getCommunications(companyId).then(setItems).catch(() => {});
  }, [companyId]);

  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-200 mb-3">Communication History</h3>
      {items.length === 0 ? (
        <p className="text-xs text-slate-500">No calls or emails logged.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((c) => (
            <li key={c.id} className="flex items-start gap-3 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg">
              {c.channel === 'Call' ? <Phone className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" /> : <Mail className="w-4 h-4 text-brand-400 mt-0.5 shrink-0" />}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-slate-200 truncate">{c.subject}</p>
                <p className="text-[11px] text-slate-500">
                  {c.channel}{c.direction ? ` · ${c.direction}` : ''} · {c.status} · {new Date(c.timestamp).toLocaleString()}
                </p>
              </div>
              {c.recording_url && (
                <a href={c.recording_url} target="_blank" rel="noreferrer" className="text-slate-400 hover:text-brand-300 shrink-0" title="Recording">
                  <PlayCircle className="w-4 h-4" />
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
