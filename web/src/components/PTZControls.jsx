import { useMemo } from 'react';

const clampZoom = (value) => {
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (Number.isNaN(num)) {
    return 1;
  }
  const rounded = Math.round(num * 10) / 10;
  return Math.min(4, Math.max(1, rounded));
};

export default function PTZControls({
  step = 5,
  onRelativeMove,
  zoom = 1,
  onZoomChange,
  isMonitoring = false,
  onToggleMonitoring,
}) {
  const safeStep = useMemo(() => {
    if (typeof step !== 'number' || Number.isNaN(step) || step <= 0) {
      return 5;
    }
    return step;
  }, [step]);

  const effectiveZoom = clampZoom(zoom);
  const isRelativeDisabled = !onRelativeMove || isMonitoring;
  const isZoomDisabled = !onZoomChange || isMonitoring;
  const isMonitoringDisabled = !onToggleMonitoring;

  const handleMove = (panDeg, tiltDeg) => {
    if (isRelativeDisabled) return;
    onRelativeMove({ dpan_deg: panDeg, dtilt_deg: tiltDeg });
  };

  const adjustZoom = (delta) => {
    if (isZoomDisabled) return;
    const next = clampZoom(effectiveZoom + delta);
    onZoomChange(next);
  };

  const handleMonitoringClick = () => {
    if (isMonitoringDisabled) return;
    onToggleMonitoring();
  };

  return (
    <section className="card ptz-control-card" aria-label="Live positioning controls">
      <div className="ptz-control-header">
        <h2>Live positioning</h2>
        <p>Fine tune the frame with graceful movements and quick zoom controls.</p>
      </div>
      <div className={`ptz-pad${isMonitoring ? ' monitoring-active' : ''}`}>
        <button
          type="button"
          className="ghost-button arrow-button"
          onClick={() => handleMove(0, safeStep)}
          disabled={isRelativeDisabled}
          aria-label="Nudge up"
        >
          ▲
        </button>
        <div className="ptz-middle-row">
          <button
            type="button"
            className="ghost-button arrow-button"
            onClick={() => handleMove(-safeStep, 0)}
            disabled={isRelativeDisabled}
            aria-label="Nudge left"
          >
            ◀
          </button>
          <div className="ptz-center-indicator" aria-hidden="true">
            <span>PTZ</span>
          </div>
          <button
            type="button"
            className="ghost-button arrow-button"
            onClick={() => handleMove(safeStep, 0)}
            disabled={isRelativeDisabled}
            aria-label="Nudge right"
          >
            ▶
          </button>
        </div>
        <button
          type="button"
          className="ghost-button arrow-button"
          onClick={() => handleMove(0, -safeStep)}
          disabled={isRelativeDisabled}
          aria-label="Nudge down"
        >
          ▼
        </button>
      </div>
      <div className="ptz-zoom-row" role="group" aria-label="Zoom controls">
        <button
          type="button"
          className="ghost-button zoom-pill"
          onClick={() => adjustZoom(-0.2)}
          disabled={isZoomDisabled}
        >
          Zoom out
        </button>
        <span className="ptz-zoom-display">{effectiveZoom.toFixed(1)}×</span>
        <button
          type="button"
          className="ghost-button zoom-pill"
          onClick={() => adjustZoom(0.2)}
          disabled={isZoomDisabled}
        >
          Zoom in
        </button>
      </div>
      <button
        type="button"
        className={`ghost-button monitoring-toggle${isMonitoring ? ' active' : ''}`}
        onClick={handleMonitoringClick}
        disabled={isMonitoringDisabled}
      >
        {isMonitoring ? 'Stop monitoring' : 'Monitoring'}
      </button>
    </section>
  );
}
