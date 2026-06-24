import React, { useState, useEffect } from 'react';
import { portalApi, SupportTicketResponse } from '../../services/portalApi';
import {
  LifeBuoy, Send, MessageSquare, Plus, PlusCircle, Clock,
  CheckCircle, AlertCircle, Loader2, AlertTriangle, ChevronRight, X
} from 'lucide-react';

export const PortalSupport: React.FC = () => {
  const [tickets, setTickets] = useState<SupportTicketResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Selected ticket for chat detail view
  const [activeTicket, setActiveTicket] = useState<SupportTicketResponse | null>(null);
  const [replyText, setReplyText] = useState('');
  const [sendingReply, setSendingReply] = useState(false);

  // File ticket modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creatingTicket, setCreatingTicket] = useState(false);
  const [newTicket, setNewTicket] = useState({
    subject: '',
    priority: 'Medium',
    description: ''
  });

  useEffect(() => {
    fetchTickets();
  }, []);

  const fetchTickets = async () => {
    try {
      setLoading(true);
      const data = await portalApi.getTickets();
      setTickets(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load support tickets.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTicket = async (ticketId: string) => {
    try {
      setError(null);
      const ticketDetails = await portalApi.getTicket(ticketId);
      setActiveTicket(ticketDetails);
    } catch (err: any) {
      setError("Failed to fetch support ticket details.");
    }
  };

  const handlePostReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTicket || !replyText.trim()) return;

    try {
      setSendingReply(true);
      const updated = await portalApi.commentOnTicket(activeTicket.id, {
        content: replyText
      });
      setActiveTicket(updated);
      setReplyText('');
      fetchTickets(); // Refresh lists
    } catch (err: any) {
      setError("Failed to post comment reply.");
    } finally {
      setSendingReply(false);
    }
  };

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreatingTicket(true);
      setError(null);
      setSuccess(null);

      const created = await portalApi.createTicket(newTicket);
      setSuccess(`Support ticket "${created.subject}" successfully submitted!`);
      setShowCreateModal(false);
      setNewTicket({ subject: '', priority: 'Medium', description: '' });
      fetchTickets();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to file support ticket.");
    } finally {
      setCreatingTicket(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8 text-left max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
            Support Ticketing Desk
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            File support tickets for portal adjustments, discuss issues with administrators, and view status history.
          </p>
        </div>
        <button
          onClick={() => {
            setError(null);
            setSuccess(null);
            setShowCreateModal(true);
          }}
          className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          Create Support Request
        </button>
      </div>

      {success && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <CheckCircle className="w-4 h-4 shrink-0" />
          {success}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Split view: ticket list vs chat thread */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Ticket List */}
        <div className="lg:col-span-1 glass-panel border border-slate-900 rounded-2xl overflow-hidden">
          <div className="p-4 border-b border-slate-900 bg-slate-950/40">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">All Raised Tickets</h3>
          </div>
          {tickets.length === 0 ? (
            <p className="p-6 text-slate-500 text-xs text-center">No support requests filed.</p>
          ) : (
            <div className="divide-y divide-slate-900 max-h-[500px] overflow-y-auto scrollbar-thin">
              {tickets.map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleSelectTicket(t.id)}
                  className={`w-full p-4 text-left transition-all hover:bg-slate-900/40 flex items-start justify-between gap-3 ${
                    activeTicket?.id === t.id ? 'bg-slate-900/60 border-l-2 border-brand-500' : ''
                  }`}
                >
                  <div className="space-y-1 overflow-hidden">
                    <h4 className="text-xs font-bold text-slate-200 truncate">{t.subject}</h4>
                    <p className="text-[10px] text-slate-500 truncate">{t.description}</p>
                    <div className="flex gap-1.5 items-center pt-1.5">
                      <span className={`px-1.5 py-0.5 text-[8px] font-bold rounded uppercase ${
                        t.priority === 'Critical'
                          ? 'bg-rose-500/10 text-rose-400'
                          : t.priority === 'High'
                          ? 'bg-amber-500/10 text-amber-400'
                          : 'bg-slate-500/10 text-slate-400'
                      }`}>
                        {t.priority}
                      </span>
                      <span className="text-[9px] text-slate-600 font-mono">
                        {new Date(t.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <span className={`px-1.5 py-0.5 text-[8px] font-bold rounded uppercase shrink-0 border ${
                    t.status.toLowerCase() === 'open'
                      ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                      : t.status.toLowerCase() === 'resolved'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                  }`}>
                    {t.status}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Chat Thread */}
        <div className="lg:col-span-2 glass-panel border border-slate-900 rounded-2xl min-h-[450px] flex flex-col justify-between bg-slate-950/20">
          {activeTicket ? (
            <>
              {/* Header */}
              <div className="p-4 border-b border-slate-900 bg-slate-950/60 flex justify-between items-start gap-4">
                <div>
                  <h3 className="text-sm font-bold text-slate-200">{activeTicket.subject}</h3>
                  <p className="text-[10px] text-slate-500 mt-1">Filed on {new Date(activeTicket.created_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="px-2 py-0.5 text-[9px] font-bold bg-slate-900 border border-slate-800 text-slate-400 rounded uppercase">
                    {activeTicket.priority} Priority
                  </span>
                  <span className="px-2 py-0.5 text-[9px] font-bold bg-brand-500/10 border border-brand-500/20 text-brand-400 rounded uppercase">
                    {activeTicket.status}
                  </span>
                </div>
              </div>

              {/* Chat messages */}
              <div className="flex-1 p-6 space-y-4 max-h-[300px] overflow-y-auto scrollbar-thin">
                {/* Description source post */}
                <div className="flex gap-3 items-start text-xs max-w-[85%]">
                  <div className="w-8 h-8 rounded-full bg-slate-900 flex items-center justify-center font-bold text-slate-400 border border-slate-800 shrink-0">
                    Q
                  </div>
                  <div className="p-3 bg-slate-900/60 border border-slate-900 rounded-2xl rounded-tl-none space-y-1">
                    <p className="font-bold text-slate-400 text-[10px]">Support Request Source</p>
                    <p className="text-slate-300 leading-relaxed">{activeTicket.description}</p>
                  </div>
                </div>

                {/* Comment replies list */}
                {activeTicket.comments?.map((c, idx) => (
                  <div
                    key={idx}
                    className={`flex gap-3 items-start text-xs max-w-[85%] ${
                      c.author.includes('Admin') || c.author.includes('Support')
                        ? 'ml-auto flex-row-reverse text-right'
                        : ''
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-white shrink-0 ${
                      c.author.includes('Admin') || c.author.includes('Support')
                        ? 'bg-indigo-600'
                        : 'bg-brand-500'
                    }`}>
                      {c.author.substring(0, 1).toUpperCase()}
                    </div>
                    <div className={`p-3 rounded-2xl space-y-1 border ${
                      c.author.includes('Admin') || c.author.includes('Support')
                        ? 'bg-slate-900/80 border-slate-800 rounded-tr-none text-left'
                        : 'bg-slate-900/40 border-slate-900 rounded-tl-none'
                    }`}>
                      <p className="font-bold text-slate-400 text-[10px]">
                        {c.author} • <span className="font-normal font-mono">{new Date(c.timestamp).toLocaleTimeString()}</span>
                      </p>
                      <p className="text-slate-200 leading-relaxed">{c.content}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Chat Input */}
              <form onSubmit={handlePostReply} className="p-4 border-t border-slate-900 bg-slate-950/40 flex gap-2">
                <input
                  type="text"
                  placeholder="Type a comment reply in ticket thread..."
                  disabled={activeTicket.status.toLowerCase() === 'closed'}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  className="flex-1 px-3.5 py-2 bg-slate-900 border border-slate-850 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={sendingReply || !replyText.trim() || activeTicket.status.toLowerCase() === 'closed'}
                  className="p-2 bg-brand-500 hover:bg-brand-600 disabled:bg-slate-900 text-white disabled:text-slate-600 rounded-xl transition-all cursor-pointer border border-transparent disabled:border-slate-850"
                >
                  {sendingReply ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </button>
              </form>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center p-8 flex-1 text-slate-500 text-xs text-center space-y-2">
              <LifeBuoy className="w-10 h-10 text-slate-700 animate-pulse" />
              <p>Select a support ticket from the list to view the comment replies thread.</p>
            </div>
          )}
        </div>
      </div>

      {/* Raise Ticket Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <form
            onSubmit={handleCreateTicket}
            className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-5 bg-slate-950"
          >
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-lg font-bold text-slate-100">Raise Support Ticket</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Describe issues or portal settings help. Support staff updates ticket within standard SLAs.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="p-1 text-slate-500 hover:text-slate-300 transition-all cursor-pointer"
              >
                <X className="w-4.5 h-4.5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Subject</label>
                <input
                  type="text"
                  required
                  placeholder="Need seat capacity extension error..."
                  value={newTicket.subject}
                  onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })}
                  className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Priority</label>
                <select
                  value={newTicket.priority}
                  onChange={(e) => setNewTicket({ ...newTicket, priority: e.target.value })}
                  className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700"
                >
                  <option value="Low">Low Priority</option>
                  <option value="Medium">Medium Priority</option>
                  <option value="High">High Priority</option>
                  <option value="Critical">Critical Priority</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">Description</label>
                <textarea
                  required
                  rows={4}
                  placeholder="Describe your issue in detail here..."
                  value={newTicket.description}
                  onChange={(e) => setNewTicket({ ...newTicket, description: e.target.value })}
                  className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-slate-700 resize-none font-sans"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creatingTicket}
                className="flex items-center justify-center gap-1.5 px-6 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold cursor-pointer"
              >
                {creatingTicket ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <>
                    <LifeBuoy className="w-3.5 h-3.5" />
                    Submit Request
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
