import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X, Send, Paperclip, FileText, Image as ImageIcon,
  Check, CheckCheck, Clock, AlertTriangle, Phone,
  FileCheck, ShieldCheck, Download, ExternalLink,
  MessageCircle, MessageSquare, Loader2, LayoutTemplate,
  Sparkles, CheckCircle2, FolderPlus, FolderCheck
} from 'lucide-react';
import { LeadResponse, leadApi } from '../../services/leadApi';
import { whatsappApi, WaMessage, QuickReply, WaTemplate, WaConversation } from '../../services/whatsappApi';
import { whatsappRealtime } from '../../services/whatsappRealtime';
import { smsApi, SmsItem } from '../../services/smsApi';
import { extractErrorMessage } from '../../utils/errors';
import { useAuthStore } from '../../store/authStore';

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

export interface DocRequestPreset {
  id: string;
  name: string;
  badge: string;
  desc: string;
  messageText: string;
}

export const DOC_REQUEST_PRESETS: DocRequestPreset[] = [
  {
    id: 'aadhaar',
    name: 'Aadhaar Card (Front & Back)',
    badge: 'ID Proof',
    desc: 'Government identity and address verification',
    messageText: 'Dear customer, please send a clear photo or PDF of your Aadhaar Card (both Front & Back sides) here on WhatsApp to proceed with verification.',
  },
  {
    id: 'pan',
    name: 'PAN Card',
    badge: 'Tax / Identity',
    desc: 'Clear photo or scanned PDF copy',
    messageText: 'Dear customer, kindly share a clear photo or copy of your PAN Card here on WhatsApp to complete your verification.',
  },
  {
    id: 'bank_statement',
    name: 'Bank Statement / Cheque',
    badge: 'Banking',
    desc: 'Latest 3-6 months statement or cancelled cheque',
    messageText: 'Dear customer, please share your latest 3 to 6 months Bank Account Statement (PDF) or a Cancelled Cheque on this WhatsApp chat for account verification.',
  },
  {
    id: 'salary_slip',
    name: 'Salary Slips / Income Proof',
    badge: 'Income',
    desc: 'Last 3 months payslips or Form 16',
    messageText: 'Dear customer, please upload your latest 3 months Salary Slips or Form 16 / Income Proof here on WhatsApp.',
  },
  {
    id: 'address_proof',
    name: 'Address Proof',
    badge: 'Address',
    desc: 'Electricity bill, rental agreement or voter ID',
    messageText: 'Dear customer, please provide a valid Address Proof (Electricity Bill, Gas Bill, or Rental Agreement) here on WhatsApp.',
  },
  {
    id: 'kyc_bundle',
    name: 'Complete KYC Bundle (All-in-One)',
    badge: 'Complete KYC',
    desc: 'Aadhaar + PAN + Bank Statement + Address Proof',
    messageText: 'Dear customer, to quickly complete your verification, please upload the following documents on this WhatsApp chat:\n1. Aadhaar Card (Front & Back)\n2. PAN Card\n3. Bank Statement (Last 3 Months)\n4. Address Proof\nThank you!',
  },
];

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
  const { user } = useAuthStore();
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

  // WhatsApp Template state
  const [waTemplates, setWaTemplates] = useState<WaTemplate[]>([]);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<WaTemplate | null>(null);
  const [templateVars, setTemplateVars] = useState<string[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  // Document Collection state
  const [showDocRequestModal, setShowDocRequestModal] = useState(false);
  const [selectedDocPreset, setSelectedDocPreset] = useState<DocRequestPreset>(DOC_REQUEST_PRESETS[0]);
  const [showDocsOnly, setShowDocsOnly] = useState(false);

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    chatEndRef.current?.scrollIntoView({ behavior });
  };

  const loadTemplates = useCallback(async () => {
    setLoadingTemplates(true);
    try {
      const list = await whatsappApi.listTemplates();
      if (list && list.length > 0) {
        setWaTemplates(list);
        setSelectedTemplate(list[0]);
      } else {
        const fallback: WaTemplate[] = [
          {
            id: 'hiring-default',
            organization_id: '',
            meta_template_id: 'hiring',
            name: 'hiring',
            category: 'UTILITY',
            language: 'en',
            status: 'APPROVED',
            header_format: null,
            header_text: null,
            body_text: 'Hi, thanks for your interest in telecaller hiring. We have received your application. Your interview is scheduled on Monday at Samartha Sankalpa OPC Pvt Ltd Location: Kengeri. Please reply with "CONFIRM" to confirm your slot.',
            footer_text: null,
            buttons: null,
          }
        ];
        setWaTemplates(fallback);
        setSelectedTemplate(fallback[0]);
      }
    } catch {
      const fallback: WaTemplate[] = [
        {
          id: 'hiring-default',
          organization_id: '',
          meta_template_id: 'hiring',
          name: 'hiring',
          category: 'UTILITY',
          language: 'en',
          status: 'APPROVED',
          header_format: null,
          header_text: null,
          body_text: 'Hi, thanks for your interest in telecaller hiring. We have received your application. Your interview is scheduled on Monday at Samartha Sankalpa OPC Pvt Ltd Location: Kengeri. Please reply with "CONFIRM" to confirm your slot.',
          footer_text: null,
          buttons: null,
        }
      ];
      setWaTemplates(fallback);
      setSelectedTemplate(fallback[0]);
    } finally {
      setLoadingTemplates(false);
    }
  }, []);

  // Load conversation history for current lead & channel
  // `silent` mode keeps the current message list mounted to completely avoid UI flickering during background re-syncs
  const loadConversation = useCallback(async (silent: boolean = false) => {
    if (!lead || !lead.phone) return;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      if (channel === 'whatsapp') {
        let convs: WaConversation[] = [];
        if (lead.id) {
          convs = await whatsappApi.conversations({ lead_id: lead.id });
        }
        if (!convs || convs.length === 0) {
          const cleanPhone = lead.phone.replace(/[^0-9]/g, '');
          const searchVal = cleanPhone.startsWith('91') && cleanPhone.length > 2 ? cleanPhone.slice(2) : cleanPhone;
          if (searchVal && searchVal.length >= 5) {
            convs = await whatsappApi.conversations({ search: searchVal });
          }
        }
        if (convs && convs.length > 0) {
          const conv = convs[0];
          setWaConvId(conv.id);
          const thread = await whatsappApi.thread(conv.id);
          const formatted: ChatMessage[] = (thread.messages || []).map((m: WaMessage) => ({
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
      if (!silent) {
        setLoading(false);
        setTimeout(() => scrollToBottom('auto'), 100);
      }
    }
  }, [lead?.id, lead?.phone, channel]);

  useEffect(() => {
    if (isOpen && lead) {
      loadConversation();
      whatsappApi.listQuickReplies().then(setQuickReplies).catch(() => {});
      loadTemplates();
    }
  }, [isOpen, lead?.id, channel, loadConversation, loadTemplates]);

  // Real-time listener for incoming WhatsApp replies and status confirmations
  useEffect(() => {
    if (!isOpen || !lead) return;

    if (user?.id) {
      whatsappRealtime.connect(user.id);
    }

    const leadLast10 = (lead.phone || '').replace(/[^0-9]/g, '').slice(-10);

    const unsubscribe = whatsappRealtime.subscribe((data) => {
      try {
        if (!data) return;
        const eventType = data.type || data.event;
        if (eventType === 'whatsapp_message') {
          const incomingMsg = data.message;
          const msgLeadId = data.lead_id;
          const msgConvId = data.conversation_id;
          const rawPhone = data.phone || data.from_number || (incomingMsg && incomingMsg.phone) || '';
          const msgLast10 = rawPhone.replace(/[^0-9]/g, '').slice(-10);

          const isMatch =
            (msgLeadId && msgLeadId === lead.id) ||
            (waConvId && msgConvId === waConvId) ||
            (leadLast10 && msgLast10 && leadLast10 === msgLast10);

          if (isMatch) {
            if (msgConvId && !waConvId) {
              setWaConvId(msgConvId);
            }
            if (incomingMsg) {
              setMessages((prev) => {
                if (prev.some((m) => m.id === incomingMsg.id)) {
                  return prev.map((m) =>
                    m.id === incomingMsg.id ? { ...m, status: incomingMsg.wa_status || m.status } : m
                  );
                }
                const formatted: ChatMessage = {
                  id: incomingMsg.id,
                  channel: 'whatsapp',
                  direction: incomingMsg.direction || 'INBOUND',
                  body: incomingMsg.body || '',
                  status: incomingMsg.wa_status || 'received',
                  created_at: incomingMsg.created_at || new Date().toISOString(),
                  media_type: incomingMsg.media_type,
                  media_url: incomingMsg.attachments?.[0]?.media_url,
                  filename: incomingMsg.attachments?.[0]?.file_name,
                };
                return [...prev, formatted];
              });
              setTimeout(() => scrollToBottom('smooth'), 50);
            } else {
              loadConversation(true);
            }
          }
        } else if (eventType === 'whatsapp_message_status') {
          const { message_id, wa_message_id, status } = data;
          if (status) {
            setMessages((prev) =>
              prev.map((m) =>
                (m.id === message_id || m.id === wa_message_id) ? { ...m, status } : m
              )
            );
          }
        }
      } catch (err) {
        console.error('[OmniChannelChatDrawer] Realtime error:', err);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [isOpen, lead?.id, lead?.phone, waConvId, loadConversation, user?.id]);

  // Periodic silent poll while drawer is open so double ticks and blue ticks update dynamically with zero UI flicker
  useEffect(() => {
    if (!isOpen || !lead || !lead.phone || channel !== 'whatsapp') return;
    const interval = setInterval(() => {
      loadConversation(true);
    }, 5000);
    return () => clearInterval(interval);
  }, [isOpen, lead?.id, lead?.phone, channel, loadConversation]);

  const handleSendTemplate = async (templateToUse?: WaTemplate) => {
    const tmpl = templateToUse || selectedTemplate;
    if (!tmpl || !lead || !lead.phone) return;
    setSending(true);
    setError(null);
    try {
      const defaultVars = [(lead.first_name || lead.title || 'Customer')];
      const res = await whatsappApi.sendTemplate({
        to_number: lead.phone,
        template_name: tmpl.name,
        template_id: tmpl.id?.includes('default') ? undefined : tmpl.id,
        conversation_id: waConvId || undefined,
        lead_id: lead.id,
        language: tmpl.language || 'en',
        variables: templateVars.length > 0 ? templateVars : defaultVars,
      });

      if (res?.conversation_id) {
        setWaConvId(res.conversation_id);
      }

      let displayBody = tmpl.body_text;
      templateVars.forEach((val, idx) => {
        displayBody = displayBody.replace(`{{${idx + 1}}}`, val);
      });

      const newMsg: ChatMessage = {
        id: res.id || `local-${Date.now()}`,
        channel: 'whatsapp',
        direction: 'OUTBOUND',
        body: res.body || displayBody,
        status: res.wa_status || 'sent',
        created_at: new Date().toISOString(),
        media_type: 'template',
      };
      setMessages((prev) => [...prev, newMsg]);
      setShowTemplateModal(false);
      setTemplateVars([]);
      setError(null);
      setTimeout(() => scrollToBottom('smooth'), 50);
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to send template message'));
    } finally {
      setSending(false);
    }
  };

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
          const res = await whatsappApi.sendText({
            body: text.trim(),
            conversation_id: waConvId || undefined,
            to_number: lead.phone,
            lead_id: lead.id,
          });
          if (res?.conversation_id) {
            setWaConvId(res.conversation_id);
          }
          const newMsg: ChatMessage = {
            id: res?.id || `local-${Date.now()}`,
            channel: 'whatsapp',
            direction: 'OUTBOUND',
            body: res?.body || text.trim(),
            status: res?.wa_status || 'sent',
            created_at: res?.created_at || new Date().toISOString(),
          };
          setMessages((prev) => [...prev, newMsg]);
        } else {
          const res = await smsApi.send({
            body: text.trim(),
            to_number: lead.phone,
            lead_id: lead.id,
          });
          const newMsg: ChatMessage = {
            id: (res as any)?.id || `local-${Date.now()}`,
            channel: 'sms',
            direction: 'OUTBOUND',
            body: text.trim(),
            status: 'sent',
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, newMsg]);
        }

        setText('');
        setTimeout(() => {
          loadConversation(true);
        }, 1000);
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

  const handleDirectSendText = async (messageText: string) => {
    if (!lead || !lead.phone || !messageText.trim()) return;
    setSending(true);
    setError(null);
    try {
      if (channel === 'whatsapp') {
        const res = await whatsappApi.sendText({
          to_number: lead.phone,
          body: messageText.trim(),
          conversation_id: waConvId || undefined,
          lead_id: lead.id,
        });
        if (res?.conversation_id) {
          setWaConvId(res.conversation_id);
        }
        const newMsg: ChatMessage = {
          id: res?.id || `local-${Date.now()}`,
          channel: 'whatsapp',
          direction: 'OUTBOUND',
          body: messageText.trim(),
          status: res?.wa_status || 'sent',
          created_at: res?.created_at || new Date().toISOString(),
        };
        setMessages((prev) => [...prev, newMsg]);
        setTimeout(() => {
          loadConversation(true);
        }, 1000);
      } else {
        const res = await smsApi.send({
          to_number: lead.phone,
          body: messageText.trim(),
          lead_id: lead.id,
        });
        const newMsg: ChatMessage = {
          id: (res as any)?.id || `local-${Date.now()}`,
          channel: 'sms',
          direction: 'OUTBOUND',
          body: messageText.trim(),
          status: 'sent',
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, newMsg]);
      }
      setTimeout(() => scrollToBottom('smooth'), 50);
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to send message'));
    } finally {
      setSending(false);
    }
  };

  const handleSendDocRequest = async (presetText: string, sendNow: boolean) => {
    if (sendNow) {
      await handleDirectSendText(presetText);
      setShowDocRequestModal(false);
    } else {
      setText(presetText);
      setShowDocRequestModal(false);
    }
  };

  const collectedDocs = messages.filter((m) =>
    Boolean(m.media_url || m.filename || (m.media_type && m.media_type !== 'text' && m.media_type !== 'template'))
  );
  const docCount = collectedDocs.length;
  const displayedMessages = showDocsOnly ? collectedDocs : messages;

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
      <div className="relative w-full md:w-[520px] max-w-full h-full bg-[var(--bg-card)] border-l border-[var(--border-color)] shadow-2xl flex flex-col z-10 text-[var(--text-primary)]">
        
        {/* Header */}
        <div className="p-4 border-b border-[var(--border-color)] bg-[var(--bg-surface)] flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm shrink-0 border ${
              channel === 'whatsapp' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30'
            }`}>
              {channel === 'whatsapp' ? <MessageCircle className="w-5 h-5" /> : <MessageSquare className="w-5 h-5" />}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-[var(--text-primary)] truncate">{contactName}</h2>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> KYC Ready
                </span>
              </div>
              <p className="text-xs text-[var(--text-muted)] truncate flex items-center gap-2 mt-0.5">
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
                className="p-2 border border-[var(--border-color)] hover:bg-[var(--bg-card-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-xl transition cursor-pointer"
              >
                <Phone className="w-4 h-4" />
              </a>
            )}
            <a
              href={`https://wa.me/${lead.phone?.replace(/[^0-9]/g, '')}`}
              target="_blank"
              rel="noopener noreferrer"
              title="Open external WhatsApp Web"
              className="p-2 border border-[var(--border-color)] hover:bg-emerald-500/10 text-emerald-400 rounded-xl transition cursor-pointer"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
            <button
              onClick={onClose}
              className="p-2 border border-[var(--border-color)] hover:bg-[var(--bg-card-hover)] text-[var(--text-muted)] hover:text-[var(--text-primary)] rounded-xl transition cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Channel Selector & Document Tools Tab Bar */}
        <div className="px-4 py-2 bg-[var(--bg-subtle)] border-b border-[var(--border-color)] flex items-center justify-between gap-2 shrink-0">
          <div className="flex rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] p-0.5 text-xs font-semibold">
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

          <div className="flex items-center gap-2">
            {docCount > 0 && (
              <button
                type="button"
                onClick={() => setShowDocsOnly(!showDocsOnly)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition cursor-pointer ${
                  showDocsOnly
                    ? 'bg-amber-500/20 border-amber-500/40 text-amber-300 shadow-sm'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
                title="Filter to show only files and documents exchanged"
              >
                <FolderCheck className="w-3.5 h-3.5 text-amber-400" />
                <span>Docs ({docCount})</span>
              </button>
            )}

            {channel === 'whatsapp' && (
              <button
                type="button"
                onClick={() => setShowDocRequestModal(true)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 transition cursor-pointer shadow-sm"
                title="Send document collection request on WhatsApp"
              >
                <FolderPlus className="w-3.5 h-3.5 text-emerald-400" />
                <span>Request Docs</span>
              </button>
            )}
          </div>
        </div>

        {/* Chat Feed */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-slate-950/20">
          {showDocsOnly && (
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between text-xs text-amber-300 animate-fade-in">
              <div className="flex items-center gap-2">
                <FolderCheck className="w-4 h-4 text-amber-400" />
                <span>Showing {docCount} collected document(s) &amp; file(s)</span>
              </div>
              <button
                type="button"
                onClick={() => setShowDocsOnly(false)}
                className="text-[11px] font-semibold underline hover:text-white cursor-pointer"
              >
                Show All Messages
              </button>
            </div>
          )}

          {loading ? (
            <div className="py-20 text-center text-slate-400 flex flex-col items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-emerald-400 mb-2" />
              <p className="text-xs">Loading conversation history...</p>
            </div>
          ) : displayedMessages.length === 0 ? (
            <div className="py-16 text-center text-slate-400 space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-slate-800/50 border border-slate-700/50 mx-auto flex items-center justify-center text-slate-500">
                {showDocsOnly ? <FolderCheck className="w-6 h-6 text-amber-400" /> : channel === 'whatsapp' ? <MessageCircle className="w-6 h-6" /> : <MessageSquare className="w-6 h-6" />}
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-300">
                  {showDocsOnly ? 'No documents collected yet' : 'No previous messages'}
                </p>
                <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
                  {showDocsOnly
                    ? 'Click "Request Docs" to prompt the lead to send KYC or onboarding documents on WhatsApp.'
                    : 'Start the onboarding conversation below or select a quick verification template.'}
                </p>
              </div>
            </div>
          ) : (
            displayedMessages.map((m) => {
              const isOut = m.direction === 'OUTBOUND';
              const fileBadge = m.filename || m.media_url ? getFileBadge(m.filename, m.media_type) : null;
              const IconComp = fileBadge?.icon || FileText;

              return (
                <div key={m.id} className={`flex ${isOut ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl p-3 text-sm border flex flex-col gap-1.5 shadow-sm ${
                      isOut
                        ? channel === 'whatsapp'
                          ? 'bg-emerald-500/10 border-emerald-500/25 text-[var(--text-primary)] rounded-br-none'
                          : 'bg-indigo-500/10 border-indigo-500/25 text-[var(--text-primary)] rounded-br-none'
                        : 'bg-[var(--bg-subtle)] border-[var(--border-color)] text-[var(--text-primary)] rounded-bl-none'
                    }`}
                  >
                    {/* Document / Image Card if attached */}
                    {(m.filename || m.media_url) && (
                      <div className="p-2.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] flex items-center gap-3">
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center border shrink-0 ${fileBadge?.color}`}>
                          <IconComp className="w-5 h-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-[var(--text-primary)] truncate">{m.filename || 'Document file'}</p>
                          <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
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

                    {/* Template Badge if template */}
                    {m.media_type === 'template' && (
                      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20 w-fit">
                        <FileCheck className="w-3 h-3" /> Approved WhatsApp Template
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
        <div className="px-3 pt-2 bg-[var(--bg-surface)] border-t border-[var(--border-color)] overflow-x-auto no-scrollbar flex items-center gap-1.5 shrink-0">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] shrink-0 mr-1">Quick:</span>
          {channel === 'whatsapp' && (
            <button
              type="button"
              onClick={() => {
                if (waTemplates.length > 0 && !selectedTemplate) setSelectedTemplate(waTemplates[0]);
                setShowTemplateModal(true);
              }}
              className="text-[11px] font-bold whitespace-nowrap px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 transition shrink-0 cursor-pointer flex items-center gap-1 shadow-sm"
            >
              <Sparkles className="w-3 h-3 text-emerald-400" /> ⚡ Send Template ({waTemplates.length})
            </button>
          )}
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
          <div className={`mx-3 mt-2 p-3 rounded-xl border text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 shrink-0 animate-fade-in shadow-lg ${
            error.toLowerCase().includes('24-hour') || error.toLowerCase().includes('template')
              ? 'bg-amber-500/15 border-amber-500/30 text-amber-200'
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            <div className="flex items-start gap-2.5">
              <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${
                error.toLowerCase().includes('24-hour') || error.toLowerCase().includes('template') ? 'text-amber-400' : 'text-red-400'
              }`} />
              <div>
                <p className="font-semibold">{error}</p>
                {channel === 'whatsapp' && (error.toLowerCase().includes('24-hour') || error.toLowerCase().includes('template')) && (
                  <p className="text-[11px] text-amber-300/80 mt-0.5">
                    Free-form messaging is paused until user replies. Send an approved template message to re-open the 24-hour communication session.
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
              {channel === 'whatsapp' && (error.toLowerCase().includes('24-hour') || error.toLowerCase().includes('template')) && (
                <button
                  type="button"
                  onClick={() => {
                    if (waTemplates.length > 0 && !selectedTemplate) setSelectedTemplate(waTemplates[0]);
                    setShowTemplateModal(true);
                  }}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer shadow-sm"
                >
                  <LayoutTemplate className="w-3.5 h-3.5" /> Send Template
                </button>
              )}
              <button onClick={() => setError(null)} className="p-1 text-slate-400 hover:text-white">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* Composer Form */}
        <form onSubmit={handleSend} className="p-3 border-t border-[var(--border-color)] bg-[var(--bg-surface)] shrink-0">
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
                  : 'bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)]'
              }`}
            >
              <Paperclip className="w-4 h-4" />
            </button>

            {/* Template Selector Button */}
            {channel === 'whatsapp' && (
              <button
                type="button"
                onClick={() => {
                  if (waTemplates.length > 0 && !selectedTemplate) setSelectedTemplate(waTemplates[0]);
                  setShowTemplateModal(true);
                }}
                disabled={sending}
                title="Send Approved WhatsApp Template (Bypasses 24h Window)"
                className="p-2.5 rounded-xl border bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 hover:text-emerald-300 transition cursor-pointer shrink-0 flex items-center gap-1.5"
              >
                <LayoutTemplate className="w-4 h-4" />
                <span className="text-xs font-semibold hidden sm:inline">Template</span>
              </button>
            )}

            {/* Request Docs Button */}
            {channel === 'whatsapp' && (
              <button
                type="button"
                onClick={() => setShowDocRequestModal(true)}
                disabled={sending}
                title="Request KYC & Onboarding Documents via WhatsApp"
                className="p-2.5 rounded-xl border bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20 hover:text-amber-300 transition cursor-pointer shrink-0 flex items-center gap-1.5"
              >
                <FolderPlus className="w-4 h-4" />
                <span className="text-xs font-semibold hidden md:inline">Request Docs</span>
              </button>
            )}

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
              className="flex-1 bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] py-2 px-3 rounded-xl text-xs sm:text-sm resize-none focus:outline-none focus:ring-1 focus:ring-emerald-500/50 placeholder:text-[var(--text-muted)]"
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

        {/* WhatsApp Template Selector Modal */}
        {showTemplateModal && (
          <div className="absolute inset-0 z-30 bg-slate-950/85 backdrop-blur-sm p-4 flex flex-col justify-end sm:justify-center animate-fade-in">
            <div className="bg-slate-900 border border-slate-700/80 rounded-2xl p-5 shadow-2xl max-h-[92%] flex flex-col overflow-hidden">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                    <LayoutTemplate className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-100">Send WhatsApp Template</h3>
                    <p className="text-[11px] text-slate-400">Approved Meta HSM broadcast template</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowTemplateModal(false)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="my-3 p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-300 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 shrink-0 text-emerald-400" />
                <span>Templates bypass the Meta 24-hour window restriction and re-open the conversation.</span>
              </div>

              <div className="flex-1 overflow-y-auto space-y-3.5 pr-1">
                {/* Template Selector */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-xs font-semibold text-slate-300">Select Approved Template</label>
                    {loadingTemplates && <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400" />}
                  </div>
                  <select
                    value={selectedTemplate?.name || ''}
                    onChange={(e) => {
                      const found = waTemplates.find((t) => t.name === e.target.value);
                      if (found) {
                        setSelectedTemplate(found);
                        setTemplateVars([]);
                      }
                    }}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                  >
                    {waTemplates.map((tmpl) => (
                      <option key={tmpl.name} value={tmpl.name}>
                        {tmpl.name} ({tmpl.category || 'UTILITY'} · {tmpl.language || 'en'})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Template Message Preview */}
                {selectedTemplate && (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[11px] font-semibold text-slate-400">Live WhatsApp Preview</span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-emerald-400 border border-emerald-500/20">
                        {selectedTemplate.category || 'UTILITY'}
                      </span>
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs leading-relaxed relative">
                      <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-bold mb-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Meta Verified HSM Template
                      </div>
                      <p className="whitespace-pre-wrap text-slate-300">{selectedTemplate.body_text}</p>
                    </div>
                  </div>
                )}

                {/* Variable fields if any */}
                {selectedTemplate && (selectedTemplate.body_text.match(/\{\{(\d+)\}\}/g) || []).length > 0 && (
                  <div className="space-y-2 pt-1">
                    <label className="block text-xs font-semibold text-slate-300">Template Dynamic Parameters</label>
                    {(selectedTemplate.body_text.match(/\{\{(\d+)\}\}/g) || []).map((_, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <span className="text-xs text-slate-400 w-16 shrink-0">Param {idx + 1}:</span>
                        <input
                          type="text"
                          value={templateVars[idx] || ''}
                          onChange={(e) => {
                            const updated = [...templateVars];
                            updated[idx] = e.target.value;
                            setTemplateVars(updated);
                          }}
                          placeholder={`Value for {{${idx + 1}}}`}
                          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Action buttons */}
              <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => setShowTemplateModal(false)}
                  disabled={sending}
                  className="px-3.5 py-2 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs font-semibold transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleSendTemplate()}
                  disabled={sending || !selectedTemplate}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center gap-1.5 disabled:opacity-50 shadow-lg shadow-emerald-900/30 cursor-pointer"
                >
                  {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  Send Template to {lead.phone}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Document Collection Modal */}
        {showDocRequestModal && (
          <div className="absolute inset-0 z-30 bg-slate-950/85 backdrop-blur-sm p-4 flex flex-col justify-end sm:justify-center animate-fade-in">
            <div className="bg-slate-900 border border-slate-700/80 rounded-2xl p-5 shadow-2xl max-h-[92%] flex flex-col overflow-hidden">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
                    <FolderPlus className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-100">Collect Documents via WhatsApp</h3>
                    <p className="text-[11px] text-slate-400">Send instant KYC &amp; document checklist to {contactName}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowDocRequestModal(false)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="my-3 p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-300 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 shrink-0 text-emerald-400" />
                <span>The customer can reply directly with camera photos or PDF files on WhatsApp.</span>
              </div>

              <div className="flex-1 overflow-y-auto space-y-3.5 pr-1">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-2">Select Document Requirement:</label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {DOC_REQUEST_PRESETS.map((p) => {
                      const isSel = selectedDocPreset.id === p.id;
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => setSelectedDocPreset(p)}
                          className={`text-left p-2.5 rounded-xl border transition cursor-pointer flex flex-col gap-1 ${
                            isSel
                              ? 'bg-emerald-500/15 border-emerald-500/50 text-slate-100 shadow-sm'
                              : 'bg-slate-800/60 border-slate-700/70 text-slate-300 hover:bg-slate-800'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-slate-200">{p.name}</span>
                            <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-slate-900/80 text-emerald-400 border border-emerald-500/20">
                              {p.badge}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 leading-tight">{p.desc}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Live Message Preview */}
                <div>
                  <label className="block text-[11px] font-semibold text-slate-400 mb-1.5">WhatsApp Message Preview</label>
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs leading-relaxed relative">
                    <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-bold mb-1">
                      <MessageCircle className="w-3.5 h-3.5" /> Outbound WhatsApp Message
                    </div>
                    <p className="whitespace-pre-wrap text-slate-300">{selectedDocPreset.messageText}</p>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2.5 mt-2">
                <button
                  type="button"
                  onClick={() => setShowDocRequestModal(false)}
                  className="px-3.5 py-2 text-xs font-semibold text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleSendDocRequest(selectedDocPreset.messageText, false)}
                  className="px-3.5 py-2 text-xs font-semibold text-slate-200 hover:text-white bg-slate-700 hover:bg-slate-600 rounded-xl transition cursor-pointer"
                >
                  Insert in Composer
                </button>
                <button
                  type="button"
                  disabled={sending}
                  onClick={() => handleSendDocRequest(selectedDocPreset.messageText, true)}
                  className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 rounded-xl transition cursor-pointer shadow-lg shadow-emerald-600/25 flex items-center gap-1.5 disabled:opacity-50"
                >
                  {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  Send WhatsApp Now
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
