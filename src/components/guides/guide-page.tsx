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
  const { document, resolved, error, select } = useGuideState(guideKey);

  if (!guideKey) return <GuideList />;

  return (
    <main className="p-6 max-w-3xl">
      <h1 className="text-3xl font-bold mb-6">
        {document?.title ?? 'Guided build'}
      </h1>
      {error && <p className="mb-6 text-red-700">{error}</p>}
      {resolved && (
        <>
          <GuideSteps steps={resolved.steps} onSelect={select} />
          <GuideParts parts={resolved.parts} />
          <GuideRefinements
            refinements={resolved.refinements}
            onSelect={select}
          />
        </>
      )}
    </main>
  );
}

function GuideList() {
  const [guides, setGuides] = useState<GuideSummary[] | null>(null);

  useEffect(() => {
    fetchGuides()
      .then(setGuides)
      .catch((e) => {
        console.error('Error fetching guides:', e);
        setGuides([]);
      });
  }, []);

  if (guides === null) return null;

  return (
    <main className="p-6 max-w-3xl">
      <h1 className="text-3xl font-bold mb-6">Guided builds</h1>
      {guides.length === 0 ? (
        <p>No guides yet.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {guides.map((guide) => (
            <li key={guide.guide_key}>
              <a
                href={`?guide=${guide.guide_key}`}
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
