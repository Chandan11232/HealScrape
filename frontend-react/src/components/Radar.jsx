import { RADAR_SOURCES } from '../collectors'

export default function Radar({ size = 900 }) {
  return (
    <div className="radar" style={{ width: size, height: size }}>
      <div className="radar-ring" />
      <div className="radar-ring r2" />
      <div className="radar-ring r3" />
      <div className="radar-ring r4" />
      <div className="radar-sweep" />
      {RADAR_SOURCES.map((s, i) => (
        <div
          className="node"
          key={s.name}
          style={{ top: s.top, left: s.left, animationDelay: `${(i * 0.3) % 2.4}s` }}
        >
          <span className="node-dot" style={{ animationDelay: `${(i * 0.3) % 2.4}s` }} />
          <span className="node-label mono">{s.name}</span>
        </div>
      ))}

      <style>{`
        .radar {
          position: absolute;
          top: 50%; left: 50%;
          transform: translate(-50%, -50%);
          border-radius: 50%;
          opacity: 0.55;
          filter: drop-shadow(0 0 60px rgba(57, 255, 158, 0.08));
        }
        .radar-ring {
          position: absolute;
          inset: 0;
          border: 1px solid var(--border);
          border-radius: 50%;
        }
        .radar-ring.r2 { inset: 90px; }
        .radar-ring.r3 { inset: 180px; }
        .radar-ring.r4 { inset: 270px; }
        .radar-sweep {
          position: absolute;
          inset: 0;
          border-radius: 50%;
          background: conic-gradient(from 0deg, transparent 0deg, transparent 300deg, var(--signal-dim) 340deg, var(--signal) 360deg);
          animation: spin 5s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .node {
          position: absolute;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 6px;
          transform: translate(-50%, -50%);
        }
        .node-dot {
          width: 6px; height: 6px;
          border-radius: 50%;
          background: var(--signal);
          display: block;
          animation: ping 2.4s ease-out infinite;
        }
        @keyframes ping {
          0% { box-shadow: 0 0 0 0 rgba(57,255,158,0.5); }
          70% { box-shadow: 0 0 0 10px rgba(57,255,158,0); }
          100% { box-shadow: 0 0 0 0 rgba(57,255,158,0); }
        }
        .node-label {
          font-size: 10px;
          color: var(--text-dim);
          letter-spacing: 0.02em;
          white-space: nowrap;
        }
        @media (max-width: 720px) {
          .radar { width: 500px !important; height: 500px !important; }
          .node-label { font-size: 8px; }
        }
      `}</style>
    </div>
  )
}
