import PIOPIY from '@telecmi/piopiyjs';

export type WebRTCPhoneStatus =
  | 'idle'
  | 'registering'
  | 'registered'
  | 'calling'
  | 'ringing'
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

type Listener = (status: WebRTCPhoneStatus, details?: any) => void;

class TeleCMIWebRTCService {
  private piopiy: any = null;
  private status: WebRTCPhoneStatus = 'idle';
  private listeners: Set<Listener> = new Set();
  private isMuted: boolean = false;
  private activeCallNumber: string | null = null;
  private config: WebRTCSessionConfig | null = null;

  public getStatus(): WebRTCPhoneStatus {
    return this.status;
  }

  public getIsMuted(): boolean {
    return this.isMuted;
  }

  public getActiveCallNumber(): string | null {
    return this.activeCallNumber;
  }

  public getConfig(): WebRTCSessionConfig | null {
    return this.config;
  }


  public subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.status);
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

      this.piopiy.on('answered', () => {
        console.log('[WebRTC] Call answered & audio connected!');
        this.notify('connected');
      });

      this.piopiy.on('ended', (data: any) => {
        console.log('[WebRTC] Call ended:', data);
        this.activeCallNumber = null;
        this.isMuted = false;
        this.notify('ended', data);
      });

      this.piopiy.on('error', (err: any) => {
        console.error('[WebRTC] Call error:', err);
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

  public async makeCall(rawPhone: string): Promise<boolean> {
    if (!this.piopiy) {
      console.error('[WebRTC] Phone not initialized');
      this.notify('error', { message: 'Phone not initialized. Please wait for agent registration.' });
      return false;
    }

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

    this.activeCallNumber = digits;
    this.notify('calling', { phone: digits });

    try {
      console.log('[WebRTC] Placing outbound call directly from browser to:', digits);
      this.piopiy.call(digits);
      return true;
    } catch (err: any) {
      console.error('[WebRTC] Outbound call failed:', err);
      this.notify('error', err);
      return false;
    }
  }

  public hangup(): void {
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
}

export const telecmiWebRTC = new TeleCMIWebRTCService();
