'use client';

import React, { useEffect, useState } from 'react';
import { GuideSummary, fetchGuides } from '@/services/guide-service';
import { useGuideKey, useGuideState } from '@/hooks/use-guide-state';
import { GuideParts } from './guide-parts';
import { GuideRefinements, GuideSteps } from './guide-steps';

/**
 * The guide page: pick a guide, answer a question or two, get a parts
 * list. Everything the person has chosen lives in the query string, so
 * the page is shareable as it stands.
 */
export default function GuidePage() {
  const guideKey = useGuideKey();
  const { guide, resolved, error, select } = useGuideState(guideKey);

  // Before hydration the URL is unknown, which is not the same as a URL
  // with no guide in it. Rendering the list here would fetch every
  // guide on every view of a single one.
  if (guideKey === undefined) return null;
  if (guideKey === null) return <GuideList />;

  return (
    <main className="p-6 max-w-7xl">
      <h1 className="text-3xl font-bold mb-6">
        {guide?.title ?? 'Guided build'}
      </h1>
      {error && <p className="mb-6 text-red-700">{error}</p>}
      {resolved && (
        // Questions on the left, pieces on the right: you read the
        // questions, and the answer appears beside them. One column
        // below `lg`, where side by side would make both too narrow,
        // and there the questions come first for the same reason.
        <div className="flex flex-col lg:flex-row gap-10 items-start">
          <div className="lg:w-80 lg:shrink-0">
            <GuideSteps steps={resolved.steps} onSelect={select} />
            <GuideRefinements
              refinements={resolved.refinements}
              onSelect={select}
            />
          </div>
          <div className="lg:flex-1">
            <GuideParts parts={resolved.parts} />
          </div>
        </div>
      )}
    </main>
  );
}

function GuideList() {
  const [guides, setGuides] = useState<GuideSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let current = true;
    fetchGuides()
      .then((result) => {
        if (current) setGuides(result);
      })
      .catch((e) => {
        if (!current) return;
        console.error('Error fetching guides:', e);
        // Distinct from an empty list: "none yet" and "we could not
        // ask" should not read the same to someone looking at it.
        setFailed(true);
        setGuides([]);
      });
    return () => {
      current = false;
    };
  }, []);

  if (guides === null) return null;

  return (
    <main className="p-6 max-w-3xl">
      <h1 className="text-3xl font-bold mb-6">Guided builds</h1>
      {failed ? (
        <p>Could not load the guides.</p>
      ) : guides.length === 0 ? (
        <p>No guides yet.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {guides.map((guide) => (
            <li key={guide.guide_key}>
              <a
                href={`?guide=${encodeURIComponent(guide.guide_key)}`}
                className="text-blue-700 underline font-semibold"
              >
                {guide.title}
              </a>
              {guide.summary && <p className="text-sm">{guide.summary}</p>}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
