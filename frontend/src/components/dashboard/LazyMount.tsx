import React, { useEffect, useRef, useState } from 'react';

/**
 * Defers mounting its children until they scroll near the viewport.
 *
 * The Home dashboard renders ~60 widgets, each fetching its own endpoint on
 * mount. Mounting them all at once fired well over 100 API calls for a single
 * page load, which on its own exceeded the per-minute rate-limit budget — the
 * widgets then silently caught the 429s and rendered "no data". Deferring the
 * off-screen ones keeps a page load to the handful of widgets actually visible.
 *
 * `rootMargin` starts the fetch slightly before the widget scrolls into view so
 * the content is usually ready by the time the user reaches it. Browsers without
 * IntersectionObserver mount immediately (old behaviour, no regression).
 */
export const LazyMount: React.FC<{
  children: React.ReactNode;
  /** Height reserved before mount, so the scrollbar doesn't jump. */
  minHeight?: number;
  rootMargin?: string;
}> = ({ children, minHeight = 180, rootMargin = '300px' }) => {
  const ref = useRef<HTMLDivElement | null>(null);
  const [show, setShow] = useState(() => typeof IntersectionObserver === 'undefined');

  useEffect(() => {
    if (show || !ref.current || typeof IntersectionObserver === 'undefined') return;
    const el = ref.current;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShow(true);      // one-way: never unmount and refetch on scroll-away
          obs.disconnect();
        }
      },
      { rootMargin },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [show, rootMargin]);

  if (show) return <>{children}</>;

  return (
    <div
      ref={ref}
      style={{ minHeight }}
      className="glass-panel border border-slate-800/85 rounded-2xl animate-pulse"
      aria-hidden="true"
    />
  );
};
