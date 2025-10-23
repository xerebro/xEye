import { useEffect, useMemo, useRef } from 'react';

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

  const smoothStep = useMemo(() => Math.max(0.1, safeStep / 10), [safeStep]);

  const effectiveZoom = clampZoom(zoom);
  const isRelativeDisabled = !onRelativeMove || isMonitoring;
  const isZoomDisabled = !onZoomChange || isMonitoring;
  const isMonitoringDisabled = !onToggleMonitoring;

  const handleMove = (panDeg, tiltDeg) => {
    if (isRelativeDisabled) return;
    onRelativeMove({ dpan_deg: panDeg, dtilt_deg: tiltDeg });
  };

  const pointerState = useRef({
    timer: null,
    pointerId: null,
    suppressClick: false,
    resetTimer: null,
    target: null,
  });

  const clearPointerState = (event) => {
    if (pointerState.current.timer) {
      clearInterval(pointerState.current.timer);
    }
    pointerState.current.timer = null;
    if (pointerState.current.resetTimer) {
      clearTimeout(pointerState.current.resetTimer);
      pointerState.current.resetTimer = null;
    }
    const pointerId = pointerState.current.pointerId;
    const captureTarget = event?.currentTarget ?? pointerState.current.target;
    pointerState.current.pointerId = null;
    pointerState.current.target = null;
    if (captureTarget && pointerId !== null && typeof captureTarget.releasePointerCapture === 'function') {
      try {
        captureTarget.releasePointerCapture(pointerId);
      } catch (_) {
        // Ignore release errors for symmetry with capture.
      }
    }
  };

  useEffect(() => () => clearPointerState(), []);

  useEffect(() => {
    if (!isRelativeDisabled) return;
    clearPointerState();
    pointerState.current.suppressClick = false;
  }, [isRelativeDisabled]);

  const startContinuousMove = (event, panMultiplier, tiltMultiplier) => {
    if (isRelativeDisabled) return;
    if (typeof event.button === 'number' && event.button !== 0 && event.button !== -1) {
      return;
    }
    if (pointerState.current.resetTimer) {
      clearTimeout(pointerState.current.resetTimer);
      pointerState.current.resetTimer = null;
    }
    pointerState.current.suppressClick = true;
    const performMove = () => {
      handleMove(panMultiplier * smoothStep, tiltMultiplier * smoothStep);
    };
    performMove();
    clearPointerState();
    pointerState.current.pointerId = event.pointerId ?? null;
    pointerState.current.target = event.currentTarget || null;
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch (_) {
      // Ignore lack of pointer capture support.
    }
    pointerState.current.timer = setInterval(performMove, 50);
  };

  const stopContinuousMove = (event) => {
    const activePointerId = pointerState.current.pointerId;
    if (activePointerId !== null && event && event.pointerId !== activePointerId) {
      return;
    }
    clearPointerState(event);
    pointerState.current.resetTimer = setTimeout(() => {
      pointerState.current.suppressClick = false;
      pointerState.current.resetTimer = null;
    }, 0);
  };

  const createDirectionalHandlers = (panMultiplier, tiltMultiplier) => ({
    onClick: () => {
      if (pointerState.current.suppressClick) return;
      handleMove(panMultiplier * safeStep, tiltMultiplier * safeStep);
    },
    onPointerDown: (event) => {
      event.preventDefault();
      startContinuousMove(event, panMultiplier, tiltMultiplier);
    },
    onPointerUp: (event) => {
      event.preventDefault();
      stopContinuousMove(event);
    },
    onPointerCancel: stopContinuousMove,
    onPointerLeave: stopContinuousMove,
  });

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
          {...createDirectionalHandlers(0, 1)}
          disabled={isRelativeDisabled}
          aria-label="Nudge up"
        >
          ▲
        </button>
        <div className="ptz-middle-row">
          <button
            type="button"
            className="ghost-button arrow-button"
            {...createDirectionalHandlers(-1, 0)}
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
            {...createDirectionalHandlers(1, 0)}
            disabled={isRelativeDisabled}
            aria-label="Nudge right"
          >
            ▶
          </button>
        </div>
        <button
          type="button"
          className="ghost-button arrow-button"
          {...createDirectionalHandlers(0, -1)}
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
