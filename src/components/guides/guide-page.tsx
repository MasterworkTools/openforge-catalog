'use client';

import React, { useEffect, useState } from 'react';
import { GuideSummary, fetchGuides } from '@/services/guide-service';
import { useGuideKey, useGuideState } from '@/hooks/use-guide-state';
import { GuideParts } from './guide-parts';
import { GuideExplainer } from './guide-explainer';
import { GuideRefinements, GuideSteps } from './guide-steps';

/**
 * The guide page: pick a guide, answer a question or two, get a parts
 * list. Everything the person has chosen lives in the query string, so
 * the page is shareable as it stands.
 */
export default function GuidePage() {
  const guideKey = useGuideKey();
  const { guide, resolved, unavailable, because, error, select } =
    useGuideState(guideKey);
  // Which settled question has been reopened. Here rather than in the
  // section itself, because the explanation beside it follows.
  const [opened, setOpened] = useState<string | null>(null);

  // Before hydration the URL is unknown, which is not the same as a URL
  // with no guide in it. Rendering the list here would fetch every
  // guide on every view of a single one. So `undefined` is checked
  // first and on its own — every other falsy key means "no guide".
  if (guideKey === undefined) return null;
  // `?guide=` is a URL with no guide in it, not a guide named "".
  // Asking the API for that one only produces a 404 to show someone.
  if (!guideKey) return <GuideList />;

  return (
    // A fixed-height page rather than a scrolling one, because the
    // three columns fill up at different rates: the questions grow as
    // you answer them, the parts stay about the same, and the prose
    // varies wildly. Scrolling them together means hunting for the
    // question you wanted while the pictures slide away.
    <main className="p-6 h-screen flex flex-col">
      <h1 className="text-3xl font-bold mb-4 shrink-0">
        {guide?.title ?? 'Guided build'}
      </h1>
      {error && <p className="mb-4 text-red-700 shrink-0">{error}</p>}
      {resolved && (
        // Questions, then pieces, then the words. Left to right is the
        // order you use them in: you choose, you look at what you got,
        // and you read about it when you want to know why.
        //
        // `min-h-0` on the row and on each column is what lets the
        // columns scroll rather than the page — without it a flex
        // child refuses to shrink below its content and every
        // `overflow-y-auto` below is dead.
        <div className="flex flex-col lg:flex-row gap-8 flex-1 min-h-0">
          <div className="lg:w-72 lg:shrink-0 overflow-y-auto min-h-0 pr-2">
            <GuideSteps
              steps={resolved.steps}
              unavailable={unavailable}
              because={because}
              opened={opened}
              onOpenChange={setOpened}
              onSelect={select}
            />
            <GuideRefinements
              refinements={resolved.refinements}
              unavailable={unavailable}
              because={because}
              opened={opened}
              onOpenChange={setOpened}
              onSelect={select}
            />
          </div>
          {/* The questions keep a fixed width — they are a list of
              short labels and do not want more. The pieces and the
              words split what is left evenly: `min-w-0` because a flex
              child will not shrink below its content otherwise, and a
              long filename under a part would push the text column
              off the side. */}
          <div className="lg:flex-1 lg:min-w-0 overflow-y-auto min-h-0 pr-2">
            <GuideParts parts={resolved.parts} />
          </div>
          <div className="lg:flex-1 lg:min-w-0 overflow-y-auto min-h-0 pr-2">
            <GuideExplainer
              steps={resolved.steps}
              refinements={resolved.refinements}
              unavailable={unavailable}
              opened={opened}
            />
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
