import React, { useEffect, useState } from 'react';
import { leadApi, EscalationConfig, WorkflowRule } from '../services/leadApi';
import { Zap, ShieldAlert, Trash2, Plus, Loader2 } from 'lucide-react';

const CONDITION_FIELDS = ['status', 'source', 'priority', 'value', 'city', 'company_name'];
const OPS = ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'contains'];
const ACTION_TYPES = ['set_priority', 'set_status', 'set_source', 'add_note', 'notify_user', 'send_sms', 'send_whatsapp', 'send_email', 'add_to_campaign'];

export const LeadAutomationPage: React.FC = () => {
  const [escalation, setEscalation] = useState<EscalationConfig | null>(null);
  const [rules, setRules] = useState<WorkflowRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // new-rule form
  const [name, setName] = useState('');
  const [trigger, setTrigger] = useState('lead_created');
  const [condField, setCondField] = useState('source');
  const [condOp, setCondOp] = useState('eq');
  const [condValue, setCondValue] = useState('');
  const [actionType, setActionType] = useState('set_priority');
  const [actionValue, setActionValue] = useState('');

  const load = async () => {
    setIsLoading(true);
    try {
      const [esc, wf] = await Promise.all([leadApi.getEscalationConfig(), leadApi.listWorkflows()]);
      setEscalation(esc);
      setRules(wf);
    } catch {
      /* silent */
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const updateEscalation = async (patch: { is_active?: boolean; idle_days?: number }) => {
    try {
      setEscalation(await leadApi.updateEscalationConfig(patch));
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Update failed');
    }
  };

  const createRule = async () => {
    if (!name.trim()) return;
    try {
      const conditions = condValue.trim() ? [{ field: condField, op: condOp, value: condValue }] : [];
      const actions = [
        actionType === 'add_note'
          ? { type: actionType, content: actionValue }
          : actionType === 'add_to_campaign'
          ? { type: actionType, campaign_id: actionValue }
          : actionType === 'notify_user' || actionType === 'send_sms' || actionType === 'send_whatsapp' || actionType === 'send_email'
          ? { type: actionType, message: actionValue }
          : { type: actionType, value: actionValue },
      ];
      await leadApi.createWorkflow({ name, trigger_event: trigger, conditions, actions });
      setName('');
      setCondValue('');
      setActionValue('');
      await load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to create rule');
    }
  };

  const toggleRule = async (rule: WorkflowRule) => {
    await leadApi.updateWorkflow(rule.id, { is_active: !rule.is_active });
    await load();
  };

  const deleteRule = async (id: string) => {
    await leadApi.deleteWorkflow(id);
    await load();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800/60 pb-6">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
          Lead Automation
        </h1>
        <p className="text-sm text-slate-400 mt-1">Configure escalation and automation rules for your leads.</p>
      </div>

      {/* Escalation */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-400" />
          Idle-Lead Escalation
        </h2>
        <div className="flex flex-wrap items-center gap-6">
          <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={escalation?.is_active || false}
              onChange={(e) => updateEscalation({ is_active: e.target.checked })}
              className="accent-brand-500"
            />
            Enabled
          </label>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Escalate after</span>
            <input
              type="number"
              min={1}
              value={escalation?.idle_days ?? 3}
              onChange={(e) => setEscalation(escalation ? { ...escalation, idle_days: Number(e.target.value) } : escalation)}
              onBlur={(e) => updateEscalation({ idle_days: Number(e.target.value) })}
              className="w-20 px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
            />
            <span className="text-sm text-slate-400">days of no activity → notify owner's manager</span>
          </div>
        </div>
      </div>

      {/* Workflow rules */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4 text-brand-400" />
          Automation Rules
        </h2>

        {/* Create form */}
        <div className="grid grid-cols-1 lg:grid-cols-6 gap-2 mb-5 p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Rule name"
            className="lg:col-span-2 px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50"
          />
          <select value={trigger} onChange={(e) => setTrigger(e.target.value)} className="px-2 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200">
            <option value="lead_created">On create</option>
            <option value="lead_updated">On update</option>
            <option value="call_logged">On call logged</option>
            <option value="call_disposition">On call disposition</option>
            <option value="sms_received">On SMS received</option>
            <option value="whatsapp_received">On WhatsApp received</option>
            <option value="email_received">On email received</option>
          </select>
          <div className="lg:col-span-3 flex items-center gap-1 text-[11px] text-slate-500">
            <span>IF</span>
            <select value={condField} onChange={(e) => setCondField(e.target.value)} className="px-1.5 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200">
              {CONDITION_FIELDS.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
            <select value={condOp} onChange={(e) => setCondOp(e.target.value)} className="px-1.5 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200">
              {OPS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <input value={condValue} onChange={(e) => setCondValue(e.target.value)} placeholder="value" className="w-20 px-2 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200" />
          </div>
          <div className="lg:col-span-5 flex items-center gap-1 text-[11px] text-slate-500">
            <span>THEN</span>
            <select value={actionType} onChange={(e) => setActionType(e.target.value)} className="px-1.5 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200">
              {ACTION_TYPES.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            <input value={actionValue} onChange={(e) => setActionValue(e.target.value)} placeholder="value / text" className="flex-1 px-2 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200" />
          </div>
          <button
            onClick={createRule}
            className="flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Rule
          </button>
        </div>

        {rules.length === 0 ? (
          <p className="text-xs text-slate-500">No automation rules yet.</p>
        ) : (
          <ul className="space-y-2">
            {rules.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-3 p-3 bg-slate-950/40 border border-slate-800/70 rounded-lg">
                <div className="min-w-0">
                  <p className="text-sm text-slate-200 font-medium truncate">{r.name}</p>
                  <p className="text-[11px] text-slate-500">
                    {r.trigger_event} · {r.conditions.length} condition(s) · {r.actions.map((a) => a.type).join(', ')}
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <label className="flex items-center gap-1.5 text-[11px] text-slate-400 cursor-pointer select-none">
                    <input type="checkbox" checked={r.is_active} onChange={() => toggleRule(r)} className="accent-brand-500" />
                    Active
                  </label>
                  <button onClick={() => deleteRule(r.id)} className="p-1 text-slate-500 hover:text-red-400 transition-colors cursor-pointer" title="Delete rule">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
