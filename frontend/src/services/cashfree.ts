import { portalApi } from './portalApi';

/**
 * Cashfree Checkout (JS SDK v3) integration.
 *
 * Flow: create a Cashfree order on the backend → open the hosted checkout modal
 * with the returned payment_session_id → after the modal resolves, ask OUR backend
 * to confirm the payment (server-to-server verification against Cashfree, which is
 * the real source of truth — the SDK result is only a UX signal).
 */

const SDK_URL = 'https://sdk.cashfree.com/js/v3/cashfree.js';
let sdkPromise: Promise<any> | null = null;

function loadCashfreeSdk(): Promise<any> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Cashfree SDK can only load in the browser.'));
  }
  if ((window as any).Cashfree) return Promise.resolve((window as any).Cashfree);
  if (sdkPromise) return sdkPromise;

  sdkPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SDK_URL;
    script.async = true;
    script.onload = () => {
      const factory = (window as any).Cashfree;
      if (factory) resolve(factory);
      else reject(new Error('Cashfree SDK loaded but was not available on window.'));
    };
    script.onerror = () => {
      sdkPromise = null;
      reject(new Error('Could not load the Cashfree payment SDK. Check your connection and try again.'));
    };
    document.body.appendChild(script);
  });
  return sdkPromise;
}

/**
 * Runs the full Cashfree payment for an existing (unpaid) invoice.
 * Resolves when the backend has confirmed the payment; rejects if the payment
 * was cancelled, failed, or could not be verified.
 */
export async function payInvoiceViaCashfree(invoiceId: string): Promise<void> {
  // 1. Create the Cashfree order (backend stashes cf_order_id on the invoice).
  const order = await portalApi.createCashfreeCheckout(invoiceId);
  if (!order.payment_session_id) {
    throw new Error('Payment could not be initialised. Please try again.');
  }

  // 2. Open the hosted checkout modal.
  const factory = await loadCashfreeSdk();
  const cashfree = factory({ mode: order.env === 'production' ? 'production' : 'sandbox' });
  const result = await cashfree.checkout({
    paymentSessionId: order.payment_session_id,
    redirectTarget: '_modal',
  });

  if (result && result.error) {
    throw new Error(result.error.message || 'Payment was cancelled or failed.');
  }

  // 3. Confirm with our backend, which verifies directly with Cashfree before
  //    marking the invoice paid and applying the purchase.
  await portalApi.payInvoice(invoiceId, { gateway: 'Cashfree' });
}
