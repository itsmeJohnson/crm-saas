import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X, Send, Paperclip, FileText, Image as ImageIcon,
  Check, CheckCheck, Clock, AlertTriangle, Phone,
  FileCheck, ShieldCheck, Download, ExternalLink,
  MessageCircle, MessageSquare, Loader2
} from 'lucide-react';
import { LeadResponse, leadApi } from '../../services/leadApi';
import { whatsappApi, WaMessage, QuickReply } from '../../services/whatsappApi';
import { smsApi, SmsItem } from '../../services/smsApi';
import { extractErrorMessage } from '../../utils/errors';

interface OmniChannelChatDrawerProps {
  lead: LeadResponse | null;
  isOpen: boolean;
  onClose: () => void;
  initialChannel?: 'whatsapp' | 'sms';
}

interface ChatMessage {
  id: string;
  channel: 'whatsapp' | 'sms';
  direction: 'INBOUND' | 'OUTBOUND';
  body: string | null;
  status: string;
  created_at: string;
  media_type?: string;
  media_url?: string;
  filename?: string;
  filesize?: number | null;
}

const ONBOARDING_TEMPLATES = [
  {
    label: '📄 KYC Documents Request',
    text: 'Dear customer, to complete your onboarding verification, please upload your PAN card, Aadhaar card, and Address Proof (PDF or Image) here.',
  },
  {
    label: '📑 GST & Bank Details Request',
    text: 'Please share your GST Registration Certificate and Cancelled Cheque / Bank Statement (PDF or CSV) to verify your account details.',
  },
  {
    label: '✍️ Service Agreement',
    text: 'Please find attached your Onboarding Service Agreement. Kindly review, sign, and send back the signed copy.',
  },
  {
    label: '✅ Verification Approved',
    text: 'Great news! Your onboarding documents have been verified and approved. Your account is now active.',
  },
  {
    label: '⚠️ Document Re-upload Request',
    text: 'The submitted document was unclear or incomplete. Please re-upload a clear, readable copy (PDF or high-res image).',
  },
];

export const OmniChannelChatDrawer: React.FC<OmniChannelChatDrawerProps> = ({
  lead,
  isOpen,
  onClose,
  initialChannel = 'whatsapp',
}) => {
  const [channel, setChannel] = useState<'whatsapp' | 'sms'>(initialChannel);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Active WhatsApp conversation ID if resolved
  const [waConvId, setWaConvId] = useState<string | null>(null);
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    chatEndRef.current?.scrollIntoView({ behavior });
  };

  // Load conversation history for current lead & channel
  const loadConversation = useCallback(async () => {
    if (!lead || !lead.phone) return;
    setLoading(true);
    setError(null);
    try {
      if (channel === 'whatsapp') {
        const cleanPhone = lead.phone.replace(/[^0-9]/g, '');
        const convs = await whatsappApi.conversations({ search: cleanPhone });
        if (convs.length > 0) {
          const conv = convs[0];
          setWaConvId(conv.id);
          const thread = await whatsappApi.thread(conv.id);
          const formatted: ChatMessage[] = thread.messages.map((m: WaMessage) => ({
            id: m.id,
            channel: 'whatsapp',
            direction: m.direction,
            body: m.body,
            status: m.wa_status,
            created_at: m.created_at,
            media_type: m.media_type,
            media_url: m.attachments?.[0]?.media_url,
            filename: m.attachments?.[0]?.file_name,
            filesize: m.attachments?.[0]?.file_size,
          }));
          setMessages(formatted);
        } else {
          setWaConvId(null);
          setMessages([]);
        }
      } else {
        // SMS channel history
        const history = await smsApi.messages({ search: lead.phone });
        const formatted: ChatMessage[] = (history.items || []).map((s: SmsItem) => ({
          id: s.id,
          channel: 'sms',
          direction: s.direction || 'OUTBOUND',
          body: s.body,
          status: s.sms_status || 'sent',
          created_at: s.timestamp,
        }));
        setMessages(formatted);
      }
    } catch (err: any) {
      console.warn('Could not load chat messages:', err);
    } finally {
      setLoading(false);
      setTimeout(() => scrollToBottom('auto'), 100);
    }
  }, [lead, channel]);

  useEffect(() => {
    if (isOpen && lead) {
      loadConversation();
      whatsappApi.listQuickReplies().then(setQuickReplies).catch(() => {});
    }
  }, [isOpen, lead, channel, loadConversation]);

  if (!isOpen || !lead) return null;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file size: 15MB max
      if (file.size > 15 * 1024 * 1024) {
        setError('File size must not exceed 15MB.');
        return;
      }
      setSelectedFile(file);
      setError(null);
    }
  };

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!text.trim() && !selectedFile) return;
    if (!lead.phone) {
      setError('This lead does not have a phone number.');
      return;
    }

    setSending(true);
    setError(null);

    try {
      if (selectedFile) {
        setUploadProgress(true);
        // Upload as lead attachment first
        const attached = await leadApi.uploadAttachment(lead.id, selectedFile);
        
        // Also transmit via WhatsApp if on WhatsApp channel
        if (channel === 'whatsapp') {
          const form = new FormData();
          form.append('file', selectedFile);
          if (waConvId) form.append('conversation_id', waConvId);
          form.append('to_number', lead.phone);
          if (text.trim()) form.append('caption', text.trim());
          try {
            await whatsappApi.sendMedia(form);
          } catch (mErr: any) {
            console.warn('Media sent as lead attachment, WhatsApp send media note:', mErr);
          }
        }

        // Add to local message list immediately
        const newMsg: ChatMessage = {
          id: `local-${Date.now()}`,
          channel,
          direction: 'OUTBOUND',
          body: text.trim() || `Sent document: ${selectedFile.name}`,
          status: 'sent',
          created_at: new Date().toISOString(),
          media_type: selectedFile.type.includes('image') ? 'image' : 'document',
          media_url: attached.url,
          filename: selectedFile.name,
          filesize: selectedFile.size,
        };
        setMessages((prev) => [...prev, newMsg]);
        setSelectedFile(null);
        setText('');
      } else {
        // Text-only message
        if (channel === 'whatsapp') {
          await whatsappApi.sendText({
            body: text.trim(),
            conversation_id: waConvId || undefined,
            to_number: lead.phone,
            lead_id: lead.id,
          });
        } else {
          await smsApi.send({
            body: text.trim(),
            to_number: lead.phone,
            lead_id: lead.id,
          });
        }

        const newMsg: ChatMessage = {
          id: `local-${Date.now()}`,
          channel,
          direction: 'OUTBOUND',
          body: text.trim(),
          status: 'sent',
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, newMsg]);
        setText('');
      }

      setTimeout(() => scrollToBottom('smooth'), 50);
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to send message'));
    } finally {
      setSending(false);
      setUploadProgress(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const getFileBadge = (filename?: string, mediaType?: string) => {
    const ext = filename?.split('.').pop()?.toUpperCase() || '';
    if (ext === 'PDF' || mediaType === 'document') {
      return { icon: FileText, color: 'text-red-400 bg-red-500/10 border-red-500/25', label: 'PDF Document' };
    }
    if (ext === 'CSV' || ext === 'XLSX' || ext === 'XLS') {
      return { icon: FileCheck, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25', label: ext || 'CSV' };
    }
    if (mediaType === 'image' || ['PNG', 'JPG', 'JPEG', 'WEBP'].includes(ext)) {
      return { icon: ImageIcon, color: 'text-sky-400 bg-sky-500/10 border-sky-500/25', label: 'Image Proof' };
    }
    return { icon: FileText, color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/25', label: ext || 'File' };
  };

  const contactName = `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || lead.title || 'Customer';

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end animate-fade-in">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Drawer Container (Full screen on mobile, 520px wide on desktop) */}
      <div className="relative w-full md:w-[520px] max-w-full h-full bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col z-10">
        
        {/* Header */}
        <div className="p-4 border-b border-slate-800/80 bg-slate-900/95 flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm shrink-0 border ${
              channel === 'whatsapp' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30'
            }`}>
              {channel === 'whatsapp' ? <MessageCircle className="w-5 h-5" /> : <MessageSquare className="w-5 h-5" />}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-100 truncate">{contactName}</h2>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> KYC Ready
                </span>
              </div>
              <p className="text-xs text-slate-400 truncate flex items-center gap-2 mt-0.5">
                <span>{lead.phone || 'No phone'}</span>
                {lead.company_name && <span>• {lead.company_name}</span>}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {lead.phone && (
              <a
                href={`tel:${lead.phone.replace(/[^0-9+]/g, '')}`}
                title="Direct Phone Call"
                className="p-2 border border-slate-800 hover:bg-slate-800 text-slate-300 hover:text-white rounded-xl transition cursor-pointer"
              >
                <Phone className="w-4 h-4" />
              </a>
            )}
            <a
              href={`https://wa.me/${lead.phone?.replace(/[^0-9]/g, '')}`}
              target="_blank"
              rel="noopener noreferrer"
              title="Open external WhatsApp Web"
              className="p-2 border border-slate-800 hover:bg-emerald-500/10 text-emerald-400 rounded-xl transition cursor-pointer"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
            <button
              onClick={onClose}
              className="p-2 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white rounded-xl transition cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Channel Selector Tab Bar */}
        <div className="px-4 py-2 bg-slate-950/40 border-b border-slate-800/60 flex items-center justify-between gap-2 shrink-0">
          <div className="flex rounded-xl bg-slate-900 border border-slate-800 p-0.5 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setChannel('whatsapp')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition cursor-pointer ${
                channel === 'whatsapp'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageCircle className="w-3.5 h-3.5 text-emerald-400" /> WhatsApp
            </button>
            <button
              type="button"
              onClick={() => setChannel('sms')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition cursor-pointer ${
                channel === 'sms'
                  ? 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/25 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 text-indigo-400" /> DLT SMS
            </button>
          </div>

          <span className="text-[11px] text-slate-400 hidden sm:inline">
            {channel === 'whatsapp' ? 'Verified Meta Cloud API' : 'Indian DLT Route'}
          </span>
        </div>

        {/* Chat Feed */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-slate-950/20">
          {loading ? (
            <div className="py-20 text-center text-slate-400 flex flex-col items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-emerald-400 mb-2" />
              <p className="text-xs">Loading conversation history...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="py-16 text-center text-slate-400 space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-slate-800/50 border border-slate-700/50 mx-auto flex items-center justify-center text-slate-500">
                {channel === 'whatsapp' ? <MessageCircle className="w-6 h-6" /> : <MessageSquare className="w-6 h-6" />}
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-300">No previous messages</p>
                <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
                  Start the onboarding conversation below or select a quick verification template.
                </p>
              </div>
            </div>
          ) : (
            messages.map((m) => {
              const isOut = m.direction === 'OUTBOUND';
              const fileBadge = m.filename || m.media_url ? getFileBadge(m.filename, m.media_type) : null;
              const IconComp = fileBadge?.icon || FileText;

              return (
                <div key={m.id} className={`flex ${isOut ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl p-3 text-sm border flex flex-col gap-1.5 shadow-sm ${
                      isOut
                        ? channel === 'whatsapp'
                          ? 'bg-emerald-600/15 border-emerald-500/25 text-slate-100 rounded-br-none'
                          : 'bg-indigo-600/15 border-indigo-500/25 text-slate-100 rounded-br-none'
                        : 'bg-slate-800/90 border-slate-700/60 text-slate-200 rounded-bl-none'
                    }`}
                  >
                    {/* Document / Image Card if attached */}
                    {(m.filename || m.media_url) && (
                      <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center gap-3">
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center border shrink-0 ${fileBadge?.color}`}>
                          <IconComp className="w-5 h-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-slate-200 truncate">{m.filename || 'Document file'}</p>
                          <p className="text-[10px] text-slate-400 mt-0.5">
                            {fileBadge?.label} {m.filesize ? `• ${(m.filesize / 1024).toFixed(1)} KB` : ''}
                          </p>
                        </div>
                        {m.media_url && (
                          <a
                            href={m.media_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300 hover:text-white shrink-0"
                            title="Download document"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>
                    )}

                    {/* Message Body */}
                    {m.body && <p className="whitespace-pre-wrap break-words leading-relaxed text-xs sm:text-sm">{m.body}</p>}

                    {/* Timestamp & Status */}
                    <div className="flex items-center justify-end gap-1.5 text-[10px] text-slate-400 mt-0.5">
                      <span>{new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      {isOut && (
                        <span>
                          {m.status === 'read' ? <CheckCheck className="w-3.5 h-3.5 text-sky-400 inline" /> :
                           m.status === 'delivered' ? <CheckCheck className="w-3.5 h-3.5 text-slate-400 inline" /> :
                           m.status === 'sent' ? <Check className="w-3.5 h-3.5 text-slate-400 inline" /> :
                           m.status === 'failed' ? <AlertTriangle className="w-3.5 h-3.5 text-red-400 inline" /> :
                           <Clock className="w-3.5 h-3.5 text-slate-500 inline" />}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Quick Onboarding Response Chips */}
        <div className="px-3 pt-2 bg-slate-900 border-t border-slate-800/60 overflow-x-auto no-scrollbar flex items-center gap-1.5 shrink-0">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 shrink-0 mr-1">Quick:</span>
          {ONBOARDING_TEMPLATES.map((tmpl, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setText(tmpl.text)}
              className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/50 text-slate-300 hover:text-white transition shrink-0 cursor-pointer"
            >
              {tmpl.label}
            </button>
          ))}
          {quickReplies.map((qr) => (
            <button
              key={qr.id}
              type="button"
              onClick={() => setText(qr.text)}
              className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 text-emerald-300 transition shrink-0 cursor-pointer"
            >
              ⚡ {qr.shortcut}
            </button>
          ))}
        </div>

        {/* File Attachment Preview Bar */}
        {selectedFile && (
          <div className="p-2.5 mx-3 mt-2 rounded-xl bg-slate-800/90 border border-slate-700 flex items-center justify-between gap-3 animate-fade-in shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
                <FileText className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-200 truncate">{selectedFile.name}</p>
                <p className="text-[10px] text-slate-400">{(selectedFile.size / 1024).toFixed(1)} KB • Ready to send</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSelectedFile(null)}
              className="p-1 hover:bg-slate-700 rounded-lg text-slate-400 hover:text-white cursor-pointer shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="mx-3 mt-2 p-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center justify-between shrink-0">
            <span>{error}</span>
            <button onClick={() => setError(null)}><X className="w-3.5 h-3.5" /></button>
          </div>
        )}

        {/* Composer Form */}
        <form onSubmit={handleSend} className="p-3 border-t border-slate-800 bg-slate-900 shrink-0">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".pdf,.csv,.xlsx,.xls,.doc,.docx,.txt,image/*"
            className="hidden"
          />

          <div className="flex items-end gap-2">
            {/* Paperclip Button for Documents, Images, Files */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={sending}
              title="Attach document, image, or CSV/PDF"
              className={`p-2.5 rounded-xl border transition cursor-pointer shrink-0 ${
                selectedFile
                  ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                  : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:text-white hover:bg-slate-700'
              }`}
            >
              <Paperclip className="w-4 h-4" />
            </button>

            {/* Input Textarea */}
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              rows={2}
              placeholder={
                selectedFile
                  ? `Add message or caption for ${selectedFile.name}...`
                  : `Type ${channel === 'whatsapp' ? 'WhatsApp' : 'SMS'} message to customer...`
              }
              disabled={sending}
              className="flex-1 bg-slate-800/90 border border-slate-700 text-slate-200 py-2 px-3 rounded-xl text-xs sm:text-sm resize-none focus:outline-none focus:ring-1 focus:ring-emerald-500/50 placeholder:text-slate-500"
            />

            {/* Send Button */}
            <button
              type="submit"
              disabled={sending || (!text.trim() && !selectedFile)}
              className={`p-2.5 rounded-xl font-bold transition cursor-pointer shrink-0 text-white disabled:opacity-40 shadow-sm ${
                channel === 'whatsapp'
                  ? 'bg-emerald-600 hover:bg-emerald-500'
                  : 'bg-indigo-600 hover:bg-indigo-500'
              }`}
            >
              {sending || uploadProgress ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
};
