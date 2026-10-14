import React, { useCallback, useEffect, useRef, useState } from 'react';
import { restaurantApi, VoucherLookup, RedeemResult } from '../services/restaurantApi';
import { useAuthStore } from '../store/authStore';

/**
 * Staff-facing voucher redemption scanner at /staff/redeem (authenticated).
 * Installable PWA screen for the floor team: point the camera at a guest's
 * voucher QR (or type the code), preview it, then burn it. Redemption is an
 * authenticated, atomic server call — a voucher can be burned exactly once.
 *
 * Camera decoding uses the native BarcodeDetector where available (Android
 * Chrome). Everywhere else, manual code entry is the reliable fallback.
 */

const ACCENT = '#D97706';
const GREEN = '#10b981';

type Phase = 'idle' | 'looking' | 'preview' | 'burning' | 'done' | 'error';

/** Pull a voucher code out of raw scanned text (raw code, or a URL with ?code=). */
function extractCode(text: string): string {
  const t = (text || '').trim();
  try {
    const u = new URL(t);
    const q = u.searchParams.get('code');
    if (q) return q.trim().toUpperCase();
  } catch { /* not a URL */ }
  const m = t.match(/[A-Za-z0-9]+-[A-Za-z0-9]{4,}/);
  return (m ? m[0] : t).toUpperCase();
}

export const RestaurantStaffScanner: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const [phase, setPhase] = useState<Phase>('idle');
  const [manual, setManual] = useState('');
  const [table, setTable] = useState('');
  const [preview, setPreview] = useState<VoucherLookup | null>(null);
  const [done, setDone] = useState<RedeemResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [camError, setCamError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const busyRef = useRef(false); // guards against duplicate lookups mid-scan

  const supportsCamera = typeof navigator !== 'undefined'
    && !!navigator.mediaDevices
    && 'BarcodeDetector' in window;

  const stopCamera = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setScanning(false);
  }, []);

  const lookup = useCallback(async (code: string) => {
    if (!code || busyRef.current) return;
    busyRef.current = true;
    stopCamera();
    setPhase('looking'); setError(null);
    try {
      const v = await restaurantApi.lookup(code);
      setPreview(v);
      setPhase('preview');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Voucher not found.');
      setPhase('error');
    } finally {
      busyRef.current = false;
    }
  }, [stopCamera]);

  const startCamera = useCallback(async () => {
    setCamError(null);
    if (!supportsCamera) {
      setCamError('Camera scanning isn’t supported on this browser — enter the code manually below.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } }, audio: false,
      });
      streamRef.current = stream;
      const video = videoRef.current!;
      video.srcObject = stream;
      await video.play();
      setScanning(true);
      // @ts-expect-error BarcodeDetector is not in the TS DOM lib yet
      const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
      const tick = async () => {
        if (!streamRef.current) return;
        try {
          const codes = await detector.detect(video);
          if (codes && codes.length) {
            const raw = codes[0].rawValue as string;
            if (raw) { lookup(extractCode(raw)); return; }
          }
        } catch { /* transient decode error — keep scanning */ }
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch (e: any) {
      setCamError(e?.name === 'NotAllowedError'
        ? 'Camera permission denied. Allow camera access or enter the code manually.'
        : 'Could not open the camera — enter the code manually below.');
      setScanning(false);
    }
  }, [supportsCamera, lookup]);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const burn = async () => {
    if (!preview) return;
    setPhase('burning'); setError(null);
    try {
      const res = await restaurantApi.redeem(preview.code, table.trim() || undefined);
      setDone(res);
      setPhase('done');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Could not redeem this voucher.');
      setPhase('error');
    }
  };

  const reset = () => {
    setPreview(null); setDone(null); setError(null); setManual('');
    setPhase('idle');
  };

  // ---------------- render ----------------
  return (
    <div style={S.shell}>
      <div style={S.header}>
        <div>
          <p style={S.kicker}>Staff Floor Scanner</p>
          <h1 style={S.title}>Voucher Redemption</h1>
        </div>
        <span style={S.who}>{user?.first_name || user?.email || 'Staff'}</span>
      </div>

      <div style={S.body}>
        {(phase === 'idle' || phase === 'looking') && (
          <>
            <div style={S.camWrap}>
              <video ref={videoRef} style={S.video} muted playsInline />
              {!scanning && (
                <div style={S.camOverlay}>
                  {phase === 'looking'
                    ? <p style={S.muted}>Checking voucher…</p>
                    : (
                      <>
                        <div style={{ fontSize: 40, marginBottom: 8 }}>📷</div>
                        <button style={S.primary} onClick={startCamera}>Scan voucher QR</button>
                        {camError && <p style={S.warn}>{camError}</p>}
                        {!supportsCamera && <p style={S.fine}>Tip: use manual entry below.</p>}
                      </>
                    )}
                </div>
              )}
              {scanning && <div style={S.reticle} />}
            </div>

            <div style={S.divider}><span>or enter code</span></div>

            <form onSubmit={(e) => { e.preventDefault(); lookup(extractCode(manual)); }}>
              <input
                style={S.input} value={manual} placeholder="e.g. SMOKE-APP-8192"
                autoCapitalize="characters" autoComplete="off"
                onChange={(e) => setManual(e.target.value)}
              />
              <button type="submit" style={{ ...S.secondary, marginTop: 10 }} disabled={!manual.trim()}>
                Look up
              </button>
            </form>
          </>
        )}

        {phase === 'preview' && preview && (
          <div style={S.card}>
            <StatusBadge status={preview.status} redeemable={preview.redeemable} />
            <p style={S.offer}>{preview.offer_title}</p>
            <div style={S.codeChip}>{preview.code}</div>
            <dl style={S.meta}>
              {preview.guest_name && <Row k="Guest" v={preview.guest_name} />}
              {preview.guest_phone_masked && <Row k="Phone" v={preview.guest_phone_masked} />}
              {preview.expires_at && <Row k="Expires" v={new Date(preview.expires_at).toLocaleDateString()} />}
              {preview.redeemed_at && <Row k="Redeemed" v={new Date(preview.redeemed_at).toLocaleString()} />}
            </dl>

            {preview.redeemable ? (
              <>
                <input
                  style={{ ...S.input, marginTop: 4 }} value={table}
                  placeholder="Table (optional) e.g. T-04" autoComplete="off"
                  onChange={(e) => setTable(e.target.value)}
                />
                <button style={{ ...S.burn, marginTop: 12 }} onClick={burn}>🔥 Approve & Burn Voucher</button>
              </>
            ) : (
              <div style={S.cannot}>
                {preview.status === 'redeemed' ? 'Already redeemed — cannot be reused.'
                  : preview.status === 'expired' ? 'This voucher has expired.'
                    : 'This voucher is not valid.'}
              </div>
            )}
            <button style={{ ...S.ghost, marginTop: 12 }} onClick={reset}>Scan another</button>
          </div>
        )}

        {phase === 'burning' && <div style={S.card}><p style={S.muted}>Redeeming…</p></div>}

        {phase === 'done' && done && (
          <div style={{ ...S.card, textAlign: 'center' }}>
            <div style={S.tick}>✓</div>
            <h2 style={S.doneH}>Redeemed!</h2>
            <p style={S.offer}>{done.voucher.offer_title}</p>
            <div style={S.codeChip}>{done.voucher.code}</div>
            <p style={S.fine}>Burned by {done.voucher.redeemed_by} · WhatsApp receipt sent to the guest.</p>
            <button style={{ ...S.primary, marginTop: 16, width: '100%' }} onClick={reset}>Scan next table</button>
          </div>
        )}

        {phase === 'error' && (
          <div style={{ ...S.card, textAlign: 'center' }}>
            <div style={S.cross}>!</div>
            <p style={{ ...S.warn, fontSize: 15 }}>{error}</p>
            <button style={{ ...S.primary, marginTop: 16, width: '100%' }} onClick={reset}>Try again</button>
          </div>
        )}
      </div>

      <p style={S.footer}>Johnson Softwares · Secure single-use redemption</p>
    </div>
  );
};

const StatusBadge: React.FC<{ status: string; redeemable: boolean }> = ({ status, redeemable }) => {
  const color = redeemable ? GREEN : status === 'redeemed' ? '#f87171' : '#fbbf24';
  const label = redeemable ? 'Valid · Ready to burn'
    : status === 'redeemed' ? 'Already redeemed'
      : status === 'expired' ? 'Expired' : status;
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color, fontWeight: 700, fontSize: 14 }}>
      <span style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />{label}
    </div>
  );
};
const Row: React.FC<{ k: string; v: string }> = ({ k, v }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #1f2937' }}>
    <dt style={{ color: '#94a3b8', fontSize: 13 }}>{k}</dt>
    <dd style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>{v}</dd>
  </div>
);

const S: Record<string, React.CSSProperties> = {
  shell: { minHeight: '100vh', background: 'radial-gradient(120% 70% at 50% 0%, #101828 0%, #080b14 60%)', color: '#e5e7eb', fontFamily: 'system-ui, -apple-system, sans-serif', display: 'flex', flexDirection: 'column', padding: 'env(safe-area-inset-top) 16px 16px', boxSizing: 'border-box' },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 4px 12px' },
  kicker: { color: ACCENT, fontSize: 11, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', margin: 0 },
  title: { fontSize: 22, fontWeight: 800, margin: '2px 0 0' },
  who: { fontSize: 12, color: '#94a3b8', background: '#111827', border: '1px solid #1f2937', borderRadius: 20, padding: '6px 12px' },
  body: { flex: 1, maxWidth: 460, width: '100%', margin: '0 auto' },
  camWrap: { position: 'relative', width: '100%', aspectRatio: '1 / 1', background: '#0b1220', border: '1px solid #1f2937', borderRadius: 20, overflow: 'hidden' },
  video: { width: '100%', height: '100%', objectFit: 'cover' },
  camOverlay: { position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, textAlign: 'center', padding: 20 },
  reticle: { position: 'absolute', inset: '18%', border: `3px solid ${ACCENT}`, borderRadius: 16, boxShadow: '0 0 0 9999px rgba(0,0,0,.35)' },
  divider: { textAlign: 'center', color: '#64748b', fontSize: 12, margin: '16px 0', position: 'relative' },
  input: { width: '100%', boxSizing: 'border-box', padding: '14px 16px', borderRadius: 12, background: '#0b1220', border: '1px solid #293244', color: '#e5e7eb', fontSize: 16, outline: 'none', textAlign: 'center', letterSpacing: '.05em' },
  primary: { padding: '12px 20px', borderRadius: 12, border: 'none', background: ACCENT, color: '#0a0c14', fontWeight: 800, fontSize: 15, cursor: 'pointer' },
  secondary: { width: '100%', padding: '13px 16px', borderRadius: 12, border: '1px solid #334155', background: '#111827', color: '#e5e7eb', fontWeight: 700, fontSize: 15, cursor: 'pointer' },
  ghost: { width: '100%', padding: '12px', borderRadius: 12, border: 'none', background: 'transparent', color: '#94a3b8', fontWeight: 600, cursor: 'pointer' },
  burn: { width: '100%', padding: '16px', borderRadius: 14, border: 'none', background: ACCENT, color: '#0a0c14', fontWeight: 800, fontSize: 17, cursor: 'pointer' },
  card: { background: 'rgba(17,24,39,.75)', border: '1px solid #1f2937', borderRadius: 18, padding: 20, marginTop: 4 },
  offer: { fontSize: 17, fontWeight: 700, color: '#f8fafc', margin: '10px 0 8px' },
  codeChip: { fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 22, fontWeight: 800, letterSpacing: '.06em', color: ACCENT, background: '#0b1220', border: `1px dashed ${ACCENT}`, borderRadius: 12, padding: '10px 14px', textAlign: 'center' },
  meta: { margin: '14px 0 4px' },
  cannot: { marginTop: 14, background: '#7f1d1d33', border: '1px solid #b91c1c', color: '#fca5a5', borderRadius: 10, padding: '12px', fontSize: 14, textAlign: 'center', fontWeight: 600 },
  tick: { width: 64, height: 64, borderRadius: '50%', background: '#10b98122', color: GREEN, display: 'grid', placeItems: 'center', margin: '0 auto', fontSize: 34, border: `2px solid ${GREEN}55` },
  cross: { width: 56, height: 56, borderRadius: '50%', background: '#7f1d1d33', color: '#f87171', display: 'grid', placeItems: 'center', margin: '0 auto 8px', fontSize: 30, fontWeight: 800, border: '2px solid #b91c1c' },
  doneH: { fontSize: 22, fontWeight: 800, margin: '12px 0 4px' },
  muted: { color: '#94a3b8', fontSize: 14, textAlign: 'center' },
  warn: { color: '#fca5a5', fontSize: 13, margin: '8px 0 0', lineHeight: 1.4 },
  fine: { color: '#64748b', fontSize: 12, margin: '8px 0 0', textAlign: 'center', lineHeight: 1.4 },
  footer: { textAlign: 'center', color: '#475569', fontSize: 11, marginTop: 16 },
};
