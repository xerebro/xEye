import { useEffect, useState } from 'react';

const clampZoom = (value) => {
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (Number.isNaN(num)) {
    return 1;
  }
  return Math.min(4, Math.max(1, num));
};

export default function ZoomControl({ value = 1, onChange }) {
  const [zoom, setZoom] = useState(clampZoom(value));

  useEffect(() => {
    setZoom(clampZoom(value));
  }, [value]);

  const send = (next) => {
    const clamped = clampZoom(next);
    setZoom(clamped);
    onChange?.(clamped);
  };

  return (
    <div className="zoom-control">
      <div className="zoom-label-row">
        <span>Zoom</span>
        <span>{zoom.toFixed(1)}×</span>
      </div>
      <div className="zoom-row">
        <button
          type="button"
          className="ghost-button zoom-button"
          onClick={() => send(zoom - 0.1)}
          aria-label="Zoom out"
        >
          −
        </button>
        <input
          type="range"
          min="1"
          max="4"
          step="0.1"
          value={zoom}
          onChange={(event) => send(event.target.value)}
        />
        <button
          type="button"
          className="ghost-button zoom-button"
          onClick={() => send(zoom + 0.1)}
          aria-label="Zoom in"
        >
          +
        </button>
      </div>
    </div>
  );
}
