import { useEffect, useRef, useState } from 'react';
import { ptzNudge } from '../lib/api.js';

const NUDGE_DEG = 0.5;
const TICK_MS = 50;

export default function Joystick({ className = '' }) {
  const ref = useRef(null);
  const pointerId = useRef(null);
  const activeRef = useRef(false);
  const [vector, setVector] = useState({ x: 0, y: 0 });
  const [active, setActive] = useState(false);

  useEffect(() => {
    if (!active) {
      return undefined;
    }
    const id = setInterval(() => {
      const mag = Math.min(1, Math.hypot(vector.x, vector.y));
      if (mag < 0.1) {
        return;
      }
      const steps = Math.ceil(mag * 2);
      for (let i = 0; i < steps; i += 1) {
        ptzNudge(vector.x * NUDGE_DEG, -vector.y * NUDGE_DEG).catch(() => {});
      }
    }, TICK_MS);
    return () => clearInterval(id);
  }, [active, vector]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;

    const getCenter = () => {
      const rect = el.getBoundingClientRect();
      const radius = Math.min(rect.width, rect.height) / 2;
      return {
        cx: rect.left + rect.width / 2,
        cy: rect.top + rect.height / 2,
        radius,
      };
    };

    const updateVector = (event) => {
      if (!activeRef.current) return;
      const { cx, cy, radius } = getCenter();
      if (radius <= 0) return;
      const rawX = (event.clientX - cx) / radius;
      const rawY = (event.clientY - cy) / radius;
      let x = rawX;
      let y = rawY;
      const length = Math.hypot(rawX, rawY);
      if (length > 1) {
        x /= length || 1;
        y /= length || 1;
      }
      x = Math.max(-1, Math.min(1, x));
      y = Math.max(-1, Math.min(1, y));
      setVector({ x, y });
    };

    const handleDown = (event) => {
      event.preventDefault();
      pointerId.current = event.pointerId;
      activeRef.current = true;
      setActive(true);
      try {
        el.setPointerCapture(event.pointerId);
      } catch (_) {
        // Ignore capture errors on browsers that do not support it.
      }
      updateVector(event);
    };

    const handleMove = (event) => {
      if (!activeRef.current) return;
      if (pointerId.current !== event.pointerId) return;
      updateVector(event);
    };

    const handleEnd = (event) => {
      if (pointerId.current !== event.pointerId) return;
      pointerId.current = null;
      activeRef.current = false;
      setActive(false);
      setVector({ x: 0, y: 0 });
      try {
        el.releasePointerCapture(event.pointerId);
      } catch (_) {
        // Ignore release errors for symmetry with capture.
      }
    };

    el.addEventListener('pointerdown', handleDown);
    el.addEventListener('pointermove', handleMove);
    el.addEventListener('pointerup', handleEnd);
    el.addEventListener('pointercancel', handleEnd);

    return () => {
      el.removeEventListener('pointerdown', handleDown);
      el.removeEventListener('pointermove', handleMove);
      el.removeEventListener('pointerup', handleEnd);
      el.removeEventListener('pointercancel', handleEnd);
    };
  }, []);

  return (
    <div
      ref={ref}
      className={`joystick ${className}`.trim()}
      role="application"
      aria-label="Pan tilt joystick"
      style={{ touchAction: 'none', pointerEvents: 'auto', userSelect: 'none' }}
    >
      <div
        className={`joystick-thumb${active ? ' active' : ''}`}
        style={{ transform: `translate(${vector.x * 35}%, ${vector.y * 35}%)` }}
      />
    </div>
  );
}
