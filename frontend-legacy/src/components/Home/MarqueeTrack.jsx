import React from 'react';

const MarqueeTrack = () => {
  return (
    <section className="relative mt-16 sm:mt-24 border-y border-stone-800 bg-[#0a0d1a]/40 overflow-hidden">
      <div className="py-4">
        <div className="marquee-track text-[12px] font-mono text-stone-500">
          <span className="inline-flex items-center gap-10">
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/case-laws/recent</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/statutes/central</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">POST</span>
              <span className="text-stone-500">/api/v1/search/semantic</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/notifications/rbi</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/articles/constitution</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">POST</span>
              <span className="text-stone-500">/api/v1/analyze/precedent</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/judgments/supreme-court</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/rules/state</span>
              <span className="text-stone-700">/</span>
            </span>
          </span>
          <span className="inline-flex items-center gap-10 ml-10">
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/case-laws/recent</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/statutes/central</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">POST</span>
              <span className="text-stone-500">/api/v1/search/semantic</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/notifications/rbi</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/articles/constitution</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">POST</span>
              <span className="text-stone-500">/api/v1/analyze/precedent</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/judgments/supreme-court</span>
              <span className="text-stone-700">/</span>
            </span>
            <span className="inline-flex items-center gap-3">
              <span className="text-stone-200 font-semibold">GET</span>
              <span className="text-stone-500">/api/v1/rules/state</span>
              <span className="text-stone-700">/</span>
            </span>
          </span>
        </div>
      </div>
    </section>
  );
};

export default MarqueeTrack;
