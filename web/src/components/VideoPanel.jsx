import { useState } from 'react';
import Joystick from './Joystick.jsx';

const STREAM_URL = '/api/stream.mjpg';
export default function VideoPanel({ badge, onHome, ptz }) {
  const [streamKey, setStreamKey] = useState(0);
  const [status, setStatus] = useState('online');

  const handleReload = () => {
    setStreamKey((key) => key + 1);
    setStatus('online');
  };

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
        <Joystick />
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
