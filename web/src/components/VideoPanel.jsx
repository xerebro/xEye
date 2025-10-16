import { useEffect, useRef, useState } from 'react';

const STREAM_URL = '/api/stream.mjpg';
const INTERVAL_MS = 120;
const MAX_SPEED = 30; // deg per second
const EXPONENT = 1.6;

export default function VideoPanel({ badge, onRelativeMove, onHome, ptz }) {
  const [streamKey, setStreamKey] = useState(0);
  const [status, setStatus] = useState('online');
  const [dragging, setDragging] = useState(false);
  const [vector, setVector] = useState({ x: 0, y: 0 });
  const containerRef = useRef(null);
  const animationRef = useRef(null);

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

  const updateVector = (clientX, clientY) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const radius = rect.width / 2;
    const cx = rect.left + radius;
    const cy = rect.top + radius;
    const dx = clientX - cx;
    const dy = clientY - cy;
    setVector({ x: Math.max(-1, Math.min(1, dx / radius)), y: Math.max(-1, Math.min(1, dy / radius)) });
  };

  const handlePointerDown = (event) => {
    event.preventDefault();
    setDragging(true);
    updateVector(event.clientX, event.clientY);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp, { once: true });
  };

  const handlePointerMove = (event) => {
    updateVector(event.clientX, event.clientY);
  };

  const handlePointerUp = () => {
    setDragging(false);
    setVector({ x: 0, y: 0 });
    window.removeEventListener('pointermove', handlePointerMove);
  };

  const handleReload = () => {
    setStreamKey((key) => key + 1);
    setStatus('online');
  };

  useEffect(() => () => window.removeEventListener('pointermove', handlePointerMove), []);

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
        <div className="joystick" ref={containerRef} role="application" aria-label="Pan tilt joystick">
          <div
            className={`joystick-thumb${dragging ? ' active' : ''}`}
            style={{ transform: `translate(${vector.x * 35}%, ${vector.y * 35}%)` }}
            onPointerDown={handlePointerDown}
          />
        </div>
        <div className="video-actions">
          <span className={`status-indicator ${status}`}>{status === 'online' ? '● Live' : '● Offline'}</span>
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
