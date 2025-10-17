import { useCallback, useEffect, useRef, useState } from 'react';

const STREAM_URL = '/api/stream.mjpg';
const INTERVAL_MS = 120;
const MAX_SPEED = 30; // deg per second
const EXPONENT = 1.6;
const KEY_STEP = 5;

export default function VideoPanel({ badge, onRelativeMove, onHome, ptz }) {
  const [streamKey, setStreamKey] = useState(0);
  const [status, setStatus] = useState('online');
  const [dragging, setDragging] = useState(false);
  const [vector, setVector] = useState({ x: 0, y: 0 });
  const containerRef = useRef(null);
  const animationRef = useRef(null);

  const updateVector = useCallback((clientX, clientY) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const radius = rect.width / 2;
    const cx = rect.left + radius;
    const cy = rect.top + radius;
    const dx = clientX - cx;
    const dy = clientY - cy;
    setVector({
      x: Math.max(-1, Math.min(1, dx / radius)),
      y: Math.max(-1, Math.min(1, dy / radius)),
    });
  }, []);

  useEffect(() => {
    if (!dragging) {
      return undefined;
    }
    animationRef.current = setInterval(() => {
      if (!vector.x && !vector.y) return;
      const magnitude = Math.min(1, Math.hypot(vector.x, vector.y));
      const gain = Math.pow(magnitude, EXPONENT) * (INTERVAL_MS / 1000);
      const dpan = Math.sign(vector.x) * Math.abs(vector.x) * MAX_SPEED * gain;
      const dtilt = -Math.sign(vector.y) * Math.abs(vector.y) * MAX_SPEED * gain;
      if (onRelativeMove) {
        onRelativeMove({ dpan_deg: dpan, dtilt_deg: dtilt });
      }
    }, INTERVAL_MS);
    return () => clearInterval(animationRef.current);
  }, [dragging, vector, onRelativeMove]);

  const handlePointerMove = useCallback((event) => {
    updateVector(event.clientX, event.clientY);
  }, [updateVector]);

  const handlePointerUp = useCallback(() => {
    setDragging(false);
    setVector({ x: 0, y: 0 });
    window.removeEventListener('pointermove', handlePointerMove);
  }, [handlePointerMove]);

  const handlePointerDown = useCallback((event) => {
    event.preventDefault();
    setDragging(true);
    updateVector(event.clientX, event.clientY);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp, { once: true });
  }, [updateVector, handlePointerMove, handlePointerUp]);

  const handleReload = () => {
    setStreamKey((key) => key + 1);
    setStatus('online');
  };

  const handleKeyDown = useCallback((event) => {
    if (!onRelativeMove) return;
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
      return;
    }
    event.preventDefault();
    const delta = { dpan_deg: 0, dtilt_deg: 0 };
    if (event.key === 'ArrowUp') delta.dtilt_deg = KEY_STEP;
    if (event.key === 'ArrowDown') delta.dtilt_deg = -KEY_STEP;
    if (event.key === 'ArrowLeft') delta.dpan_deg = -KEY_STEP;
    if (event.key === 'ArrowRight') delta.dpan_deg = KEY_STEP;
    onRelativeMove(delta);
  }, [onRelativeMove]);

  useEffect(() => () => window.removeEventListener('pointermove', handlePointerMove), [handlePointerMove]);

  return (
    <section className="card video-panel">
      <div className="video-wrapper">
        <img
          key={streamKey}
          src={`${STREAM_URL}?v=${streamKey}`}
          alt="Live camera stream"
          className="video-frame"
          onError={() => setStatus('offline')}
          onLoad={() => setStatus('online')}
        />
        {badge && <span className="video-badge">{badge}</span>}
        {ptz && (
          <span className="video-badge badge-secondary">
            Pan {ptz.pan_deg.toFixed(0)}° · Tilt {ptz.tilt_deg.toFixed(0)}°
          </span>
        )}
        <div
          className="joystick"
          ref={containerRef}
          role="application"
          aria-label="Pan tilt joystick"
          aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight"
          tabIndex={0}
          onKeyDown={handleKeyDown}
        >
          <div
            className={`joystick-thumb${dragging ? ' active' : ''}`}
            style={{ transform: `translate(${vector.x * 35}%, ${vector.y * 35}%)` }}
            onPointerDown={handlePointerDown}
          />
        </div>
        <div className="video-actions">
          <span className={`status-indicator ${status}`} role="status" aria-live="polite">
            {status === 'online' ? '● Live' : '● Offline'}
          </span>
          <div className="video-buttons">
            <button type="button" className="ghost-button" onClick={handleReload}>
              Reload stream
            </button>
            <button type="button" className="ghost-button" onClick={() => onHome?.()}>
              Home
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
