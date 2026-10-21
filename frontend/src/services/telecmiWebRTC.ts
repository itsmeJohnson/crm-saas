import PIOPIY from '@telecmi/piopiyjs';

export type WebRTCPhoneStatus =
  | 'idle'
  | 'registering'
  | 'registered'
  | 'calling'
  | 'ringing'
  | 'incoming'
  | 'connected'
  | 'ended'
  | 'error';

export interface WebRTCSessionConfig {
  user_id: string;
  password: string;
  region?: string;
  caller_id?: string;
  agent_name?: string;
}

export interface WebRTCIncomingCall {
  from: string;
  name?: string;
  call_id: string;
  to_number?: string;
}

type Listener = (status: WebRTCPhoneStatus, details?: any) => void;

class TeleCMIWebRTCService {
  private piopiy: any = null;
  private status: WebRTCPhoneStatus = 'idle';
  private listeners: Set<Listener> = new Set();
  private isMuted: boolean = false;
  private activeCallNumber: string | null = null;
  private incomingCall: WebRTCIncomingCall | null = null;
  private config: WebRTCSessionConfig | null = null;
  private isOutboundPending: boolean = false;
  private outboundTimeout: any = null;

  public setOutboundPending(targetPhone: string): void {
    this.isOutboundPending = true;
    this.activeCallNumber = targetPhone;
    if (this.outboundTimeout) clearTimeout(this.outboundTimeout);
    this.outboundTimeout = setTimeout(() => {
      this.isOutboundPending = false;
      this.outboundTimeout = null;
    }, 35000);
  }

  public clearOutboundPending(): void {
    this.isOutboundPending = false;
    if (this.outboundTimeout) {
      clearTimeout(this.outboundTimeout);
      this.outboundTimeout = null;
    }
  }

  public getStatus(): WebRTCPhoneStatus {
    return this.status;
  }

  public getIsMuted(): boolean {
    return this.isMuted;
  }

  public getActiveCallNumber(): string | null {
    return this.activeCallNumber;
  }

  public getIncomingCall(): WebRTCIncomingCall | null {
    return this.incomingCall;
  }

  public getConfig(): WebRTCSessionConfig | null {
    return this.config;
  }

  public subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.status, this.incomingCall);
    return () => this.listeners.delete(listener);
  }

  private notify(status: WebRTCPhoneStatus, details?: any) {
    this.status = status;
    this.listeners.forEach((fn) => {
      try {
        fn(status, details);
      } catch (e) {
        console.error('[WebRTC] Listener error:', e);
      }
    });
  }

  public init(config: WebRTCSessionConfig): void {
    if (
      this.piopiy &&
      (this.status === 'registered' ||
        this.status === 'connected' ||
        this.status === 'calling' ||
        this.status === 'ringing' ||
        this.status === 'incoming') &&
      this.config?.user_id === config.user_id
    ) {
      console.log('[WebRTC] Already initialized and connected for user:', config.user_id);
      return;
    }

    this.config = config;
    if (this.piopiy) {
      try {
        this.piopiy.logout();
      } catch {}
      this.piopiy = null;
    }

    try {
      this.notify('registering');
      this.piopiy = new PIOPIY({
        name: config.agent_name || 'Telecaller Agent',
        debug: true,
        autoplay: true,
        autoReboot: true,
        ringTime: 45,
      });

      this.piopiy.on('login', () => {
        console.log('[WebRTC] TeleCMI Agent Registered successfully');
        this.notify('registered');
      });

      this.piopiy.on('loginFailed', (err: any) => {
        console.error('[WebRTC] TeleCMI Login failed:', err);
        this.notify('error', err);
      });

      this.piopiy.on('ringing', () => {
        console.log('[WebRTC] Ringing remote party...');
        this.notify('ringing');
      });

      // Handle Inbound Call from customer or Agent Bridge Leg
      this.piopiy.on('inComingCall', (data: any) => {
        console.log('[WebRTC] Inbound call event received:', data);
        if (this.isOutboundPending) {
          console.log('[WebRTC] Auto-answering agent leg for outbound Click-to-Call to:', this.activeCallNumber);
          this.clearOutboundPending();
          try {
            this.piopiy.answer();
            this.notify('connected');
          } catch (e) {
            console.error('[WebRTC] Error auto-answering outbound call leg:', e);
          }
          return;
        }

        const incoming: WebRTCIncomingCall = {
          from: data?.from || '',
          name: data?.name || '',
          call_id: data?.call_id || '',
          to_number: data?.to_number || '',
        };
        this.incomingCall = incoming;
        this.activeCallNumber = incoming.from;
        this.notify('incoming', incoming);
      });

      this.piopiy.on('answered', () => {
        console.log('[WebRTC] Call answered & audio connected!');
        this.clearOutboundPending();
        this.incomingCall = null;
        this.notify('connected');
      });

      this.piopiy.on('ended', (data: any) => {
        console.log('[WebRTC] Call ended:', data);
        this.clearOutboundPending();
        this.activeCallNumber = null;
        this.incomingCall = null;
        this.isMuted = false;
        this.notify('ended', data);
      });

      this.piopiy.on('error', (err: any) => {
        console.error('[WebRTC] Call error:', err);
        this.incomingCall = null;
        this.notify('error', err);
      });

      this.piopiy.on('mediaFailed', (err: any) => {
        console.error('[WebRTC] Media/Microphone failed:', err);
        this.notify('error', { type: 'mediaFailed', message: 'Microphone access denied or unavailable' });
      });

      // Regional endpoint: sbcind.telecmi.com (India) or default
      const region = config.region || 'sbcind.telecmi.com';
      this.piopiy.login(config.user_id, config.password, region);
    } catch (err: any) {
      console.error('[WebRTC] Failed to initialize PIOPIY client:', err);
      this.notify('error', err);
    }
  }

  public answer(): void {
    if (this.piopiy) {
      try {
        console.log('[WebRTC] Answering incoming call session...');
        this.piopiy.answer();
        this.incomingCall = null;
        this.notify('connected');
      } catch (e) {
        console.error('[WebRTC] Failed to answer incoming call:', e);
      }
    }
  }

  public reject(): void {
    if (this.piopiy) {
      try {
        console.log('[WebRTC] Rejecting incoming call session...');
        this.piopiy.reject();
      } catch (e) {
        console.error('[WebRTC] Failed to reject incoming call:', e);
      }
    }
    this.incomingCall = null;
    this.activeCallNumber = null;
    this.notify('idle');
  }

  public async makeCall(rawPhone: string): Promise<boolean> {
    let digits = (rawPhone || '').replace(/\D/g, '');
    if (digits.length === 10) {
      digits = '91' + digits;
    } else if (digits.length === 11 && digits.startsWith('0')) {
      digits = '91' + digits.slice(1);
    }

    if (!digits) {
      console.error('[WebRTC] Invalid phone number:', rawPhone);
      return false;
    }

    this.setOutboundPending(digits);
    this.notify('calling', { phone: digits });
    console.log('[WebRTC] Outbound pending bridge leg registered for:', digits);
    return true;
  }

  public hangup(): void {
    this.clearOutboundPending();
    if (this.piopiy) {
      try {
        this.piopiy.terminate();
      } catch (e) {
        console.warn('[WebRTC] Terminate failed:', e);
      }
    }
    this.activeCallNumber = null;
    this.isMuted = false;
    this.notify('ended');
  }

  public toggleMute(): boolean {
    if (!this.piopiy) return false;
    this.isMuted = !this.isMuted;
    try {
      if (this.isMuted) {
        this.piopiy.mute();
      } else {
        this.piopiy.unMute();
      }
    } catch (e) {
      console.warn('[WebRTC] Mute toggle failed:', e);
    }
    return this.isMuted;
  }

  public sendDTMF(digit: string | number): void {
    const tone = String(digit);
    if (this.piopiy && typeof this.piopiy.sendDtmf === 'function') {
      try {
        this.piopiy.sendDtmf(tone);
        console.log('[WebRTC] DTMF tone sent:', tone);
      } catch (e) {
        console.warn('[WebRTC] sendDtmf error:', e);
      }
    }
    this.playDTMFAudio(tone);
  }

  private playDTMFAudio(tone: string): void {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();

      // Standard Dual-Tone Multi-Frequency (DTMF) map
      const dtmfFreqs: Record<string, [number, number]> = {
        '1': [697, 1209],
        '2': [697, 1336],
        '3': [697, 1477],
        '4': [770, 1209],
        '5': [770, 1336],
        '6': [770, 1477],
        '7': [852, 1209],
        '8': [852, 1336],
        '9': [852, 1477],
        '*': [941, 1209],
        '0': [941, 1336],
        '#': [941, 1477],
      };

      const freqs = dtmfFreqs[tone] || [697, 1209];
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.frequency.setValueAtTime(freqs[0], ctx.currentTime);
      osc2.frequency.setValueAtTime(freqs[1], ctx.currentTime);

      gain.gain.setValueAtTime(0.06, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);

      osc1.start();
      osc2.start();
      osc1.stop(ctx.currentTime + 0.2);
      osc2.stop(ctx.currentTime + 0.2);
    } catch {}
  }
}

export const telecmiWebRTC = new TeleCMIWebRTCService();
