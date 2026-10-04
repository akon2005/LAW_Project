import React from 'react';

export default function EcosystemDiagram() {
  return (
    <section className="relative py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 grid lg:grid-cols-[1.05fr_1fr] gap-10 items-center">
        <div>
          <div className="mb-5">
            <span className="chip" style={{ fontFamily: 'var(--font-mono)' }}>
              <span className="inline-block w-1.5 h-1.5 rounded-full pulse-soft" style={{ background: '#FF9933' }}></span>
              open-source · comprehensive
            </span>
          </div>
          <h2 className="text-[44px] sm:text-5xl lg:text-[64px] leading-[1.1] tracking-tight uppercase text-stone-50 font-display">
            The Complete <span className="text-amber-300">Legal</span><br />
            Data <span className="text-stone-200 italic">Ecosystem</span>.
          </h2>
          <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-stone-400">
            VidhiVeda aggregates production-style legal endpoints — precedents, 
            statutes, constitutional articles, state rules, and more — so you can 
            perform extensive legal research using a unified interface.
          </p>
        </div>
        
        <div className="relative">
          <svg viewBox="0 0 600 440" className="w-full h-auto" role="img" aria-label="Animated diagram of legal endpoints orbiting a central hub">
            <defs>
              <radialGradient id="hub-glow-legal" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#0B3D91" stopOpacity="0.4"></stop>
                <stop offset="60%" stopColor="#0a0d1a" stopOpacity="0.6"></stop>
                <stop offset="100%" stopColor="#0a0d1a" stopOpacity="0"></stop>
              </radialGradient>
              <linearGradient id="line-grad-legal" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#ffffff" stopOpacity="0.05"></stop>
                <stop offset="50%" stopColor="#ffffff" stopOpacity="0.5"></stop>
                <stop offset="100%" stopColor="#ffffff" stopOpacity="0.05"></stop>
              </linearGradient>
              <filter id="soft-glow-legal" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2" result="blur"></feGaussianBlur>
                <feMerge>
                  <feMergeNode in="blur"></feMergeNode>
                  <feMergeNode in="SourceGraphic"></feMergeNode>
                </feMerge>
              </filter>
            </defs>

            <g className="orbit-slow" style={{ transformOrigin: '300px 210px' }}>
              <circle cx="300" cy="210" r="170" fill="none" stroke="rgba(255,255,255,0.15)" strokeDasharray="2 6"></circle>
            </g>
            <g className="orbit-fast" style={{ transformOrigin: '300px 210px' }}>
              <circle cx="300" cy="210" r="120" fill="none" stroke="rgba(255,255,255,0.18)" strokeDasharray="1 7"></circle>
            </g>
            <circle cx="300" cy="210" r="120" fill="url(#hub-glow-legal)"></circle>

            {/* Path 1: Case Laws */}
            <g>
              <path d="M80,70 Q190,110 300,210" stroke="url(#line-grad-legal)" strokeWidth="1.2" fill="none" opacity="0.7"></path>
              <path d="M80,70 Q190,110 300,210" stroke="#FF9933" strokeWidth="1.4" fill="none" className="dash-flow" style={{ animationDuration: '3s', opacity: 0.85 }}></path>
              <circle r="3" fill="#FF9933" filter="url(#soft-glow-legal)">
                <animateMotion dur="3.2s" repeatCount="indefinite" path="M80,70 Q190,110 300,210"></animateMotion>
              </circle>
            </g>

            {/* Path 2: Statutes */}
            <g>
              <path d="M360,50 Q330,100 300,210" stroke="url(#line-grad-legal)" strokeWidth="1.2" fill="none" opacity="0.7"></path>
              <path d="M360,50 Q330,100 300,210" stroke="#0B3D91" strokeWidth="1.4" fill="none" className="dash-flow" style={{ animationDuration: '3.4s', opacity: 0.85 }}></path>
              <circle r="3" fill="#0B3D91" filter="url(#soft-glow-legal)">
                <animateMotion dur="3.6s" repeatCount="indefinite" path="M360,50 Q330,100 300,210"></animateMotion>
              </circle>
            </g>

            {/* Path 3: Notifications */}
            <g>
              <path d="M540,130 Q420,140 300,210" stroke="url(#line-grad-legal)" strokeWidth="1.2" fill="none" opacity="0.7"></path>
              <path d="M540,130 Q420,140 300,210" stroke="#046A38" strokeWidth="1.4" fill="none" className="dash-flow" style={{ animationDuration: '3.8s', opacity: 0.85 }}></path>
              <circle r="3" fill="#046A38" filter="url(#soft-glow-legal)">
                <animateMotion dur="4s" repeatCount="indefinite" path="M540,130 Q420,140 300,210"></animateMotion>
              </circle>
            </g>

            {/* Path 4: Constitution */}
            <g>
              <path d="M520,320 Q410,235 300,210" stroke="url(#line-grad-legal)" strokeWidth="1.2" fill="none" opacity="0.7"></path>
              <path d="M520,320 Q410,235 300,210" stroke="#F5D77F" strokeWidth="1.4" fill="none" className="dash-flow" style={{ animationDuration: '4.2s', opacity: 0.85 }}></path>
              <circle r="3" fill="#F5D77F" filter="url(#soft-glow-legal)">
                <animateMotion dur="4.4s" repeatCount="indefinite" path="M520,320 Q410,235 300,210"></animateMotion>
              </circle>
            </g>

            {/* Path 5: State Rules */}
            <g>
              <path d="M300,380 Q300,265 300,210" stroke="url(#line-grad-legal)" strokeWidth="1.2" fill="none" opacity="0.7"></path>
              <path d="M300,380 Q300,265 300,210" stroke="#FF9933" strokeWidth="1.4" fill="none" className="dash-flow" style={{ animationDuration: '4.6s', opacity: 0.85 }}></path>
              <circle r="3" fill="#FF9933" filter="url(#soft-glow-legal)">
                <animateMotion dur="4.8s" repeatCount="indefinite" path="M300,380 Q300,265 300,210"></animateMotion>
              </circle>
            </g>

            {/* Path 6: Bills */}
            <g>
              <path d="M70,300 Q185,225 300,210" stroke="url(#line-grad-legal)" strokeWidth="1.2" fill="none" opacity="0.7"></path>
              <path d="M70,300 Q185,225 300,210" stroke="#0B3D91" strokeWidth="1.4" fill="none" className="dash-flow" style={{ animationDuration: '5s', opacity: 0.85 }}></path>
              <circle r="3" fill="#0B3D91" filter="url(#soft-glow-legal)">
                <animateMotion dur="5.2s" repeatCount="indefinite" path="M70,300 Q185,225 300,210"></animateMotion>
              </circle>
            </g>

            {/* Nodes */}
            <g>
              <circle cx="80" cy="70" r="18" fill="#141414" stroke="#FF9933" strokeWidth="1.6"></circle>
              <circle cx="80" cy="70" r="5" fill="#FF9933" className="pulse-soft"></circle>
              <g transform="translate(102, 74)">
                <rect x="0" y="-12" rx="6" ry="6" width="105" height="22" fill="#141414" stroke="rgba(255,255,255,0.15)"></rect>
                <text x="7" y="3" textAnchor="start" fill="#d4d4d8" fontSize="10.5" fontFamily="var(--font-mono)">GET /case_laws</text>
              </g>
            </g>
            <g>
              <circle cx="360" cy="50" r="18" fill="#141414" stroke="#0B3D91" strokeWidth="1.6"></circle>
              <circle cx="360" cy="50" r="5" fill="#0B3D91" className="pulse-soft"></circle>
              <g transform="translate(253.6, 54)">
                <rect x="-10" y="-12" rx="6" ry="6" width="94.4" height="22" fill="#141414" stroke="rgba(255,255,255,0.15)"></rect>
                <text x="77.4" y="3" textAnchor="end" fill="#d4d4d8" fontSize="10.5" fontFamily="var(--font-mono)">GET /statutes</text>
              </g>
            </g>
            <g>
              <circle cx="540" cy="130" r="18" fill="#141414" stroke="#046A38" strokeWidth="1.6"></circle>
              <circle cx="540" cy="130" r="5" fill="#046A38" className="pulse-soft"></circle>
              <g transform="translate(400.8, 134)">
                <rect x="0" y="-12" rx="6" ry="6" width="117.2" height="22" fill="#141414" stroke="rgba(255,255,255,0.15)"></rect>
                <text x="110.2" y="3" textAnchor="end" fill="#d4d4d8" fontSize="10.5" fontFamily="var(--font-mono)">GET /notifications</text>
              </g>
            </g>
            <g>
              <circle cx="520" cy="320" r="18" fill="#141414" stroke="#F5D77F" strokeWidth="1.6"></circle>
              <circle cx="520" cy="320" r="5" fill="#F5D77F" className="pulse-soft"></circle>
              <g transform="translate(413.6, 324)">
                <rect x="-15" y="-12" rx="6" ry="6" width="104.4" height="22" fill="#141414" stroke="rgba(255,255,255,0.15)"></rect>
                <text x="77.4" y="3" textAnchor="end" fill="#d4d4d8" fontSize="10.5" fontFamily="var(--font-mono)">GET /articles</text>
              </g>
            </g>
            <g>
              <circle cx="300" cy="380" r="18" fill="#141414" stroke="#FF9933" strokeWidth="1.6"></circle>
              <circle cx="300" cy="380" r="5" fill="#FF9933" className="pulse-soft"></circle>
              <g transform="translate(322, 384)">
                <rect x="0" y="-12" rx="6" ry="6" width="94.4" height="22" fill="#141414" stroke="rgba(255,255,255,0.15)"></rect>
                <text x="7" y="3" textAnchor="start" fill="#d4d4d8" fontSize="10.5" fontFamily="var(--font-mono)">GET /rules</text>
              </g>
            </g>
            <g>
              <circle cx="70" cy="300" r="18" fill="#141414" stroke="#0B3D91" strokeWidth="1.6"></circle>
              <circle cx="70" cy="300" r="5" fill="#0B3D91" className="pulse-soft"></circle>
              <g transform="translate(92, 304)">
                <rect x="0" y="-12" rx="6" ry="6" width="85" height="22" fill="#141414" stroke="rgba(255,255,255,0.15)"></rect>
                <text x="7" y="3" textAnchor="start" fill="#d4d4d8" fontSize="10.5" fontFamily="var(--font-mono)">GET /bills</text>
              </g>
            </g>

            {/* Central Hub */}
            <g>
              <circle cx="300" cy="210" r="40" fill="#0a0d1a" stroke="#d4af37" strokeOpacity="0.5" strokeWidth="1.8"></circle>
              <circle cx="300" cy="210" r="40" fill="none" stroke="#d4af37" strokeOpacity="0.6">
                <animate attributeName="r" values="40;52;40" dur="3.4s" repeatCount="indefinite"></animate>
                <animate attributeName="stroke-opacity" values="0.6;0;0.6" dur="3.4s" repeatCount="indefinite"></animate>
              </circle>
              <text x="300" y="206" textAnchor="middle" fill="#fafafa" fontSize="13" fontFamily="var(--font-display)" fontWeight="700">VidhiVeda</text>
              <text x="300" y="221" textAnchor="middle" fill="#a8a29e" fontSize="9" fontFamily="var(--font-mono)" letterSpacing="1">v1 · public</text>
            </g>
          </svg>
        </div>
      </div>
    </section>
  );
}
