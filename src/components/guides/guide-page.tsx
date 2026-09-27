'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  GuidePart,
  GuideSummary,
  fetchGuides,
  narrows,
  releasedBy,
} from '@/services/guide-service';
import { MoreOptions } from './guide-steps';
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
  const {
    guide,
    resolved,
    unavailable,
    because,
    options,
    error,
    select,
    selectAll,
  } =
    useGuideState(guideKey);
  // Which settled question has been reopened. Here rather than in the
  // section itself, because the explanation beside it follows.
  const [opened, setOpened] = useState<string | null>(null);
  // The part whose catalog dialog is open. Here rather than in the
  // parts list, because the questions on the left open it too.
  const [inspecting, setInspecting] = useState<GuidePart | null>(null);

  // Which questions left more than one piece, and which part to open
  // when they say so. A question can narrow several roles — the wall
  // texture narrows the wall and the base under it — and the one
  // worth offering is whichever still has a choice in it.
  const more: MoreOptions = useMemo(() => {
    const found: MoreOptions = {};
    if (!resolved || !options) return found;
    for (const question of resolved.refinements) {
      const choices = resolved.parts
        .filter((part) => narrows(question, part.role))
        .filter((part) => (options[part.role] ?? 0) > 1)
        .sort((a, b) => (options[b.role] ?? 0) - (options[a.role] ?? 0));
      if (choices.length > 0) {
        found[question.key] = {
          count: options[choices[0].role],
          onOpen: () => setInspecting(choices[0]),
        };
      }
    }
    return found;
  }, [resolved, options]);

  // Answering a question also lets go of the parts that question
  // decides. A pinned part outranks the questions — that is what
  // pinning is — so without this, going back to the texture after
  // hand-picking a wall changes nothing and the button looks dead.
  const pinned = (resolved?.parts ?? []).filter((p) => p.pinned);
  const answer = (key: string, value: string | null) => {
    const asked = [...(resolved?.steps ?? []), ...(resolved?.refinements ?? [])];
    const question = asked.find((q) => q.key === key);
    selectAll({
      [key]: value,
      ...(question ? releasedBy(question, pinned.map((p) => p.role)) : {}),
    });
  };

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
      {error && (
        <div className="mb-4 shrink-0">
          <p className="text-red-700">{error}</p>
          {/* With no resolution there is nothing else on the page —
              every column renders behind `resolved` — so a first-load
              failure would otherwise be a heading, this line, and no
              control able to change the answers that caused it. The
              answers live in the URL, so dropping them is a plain
              link rather than anything this component has to hold. */}
          {!resolved && (
            <a
              href={`?guide=${encodeURIComponent(guideKey)}`}
              className="text-blue-700 underline"
            >
              Start this guide over
            </a>
          )}
        </div>
      )}
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
              onSelect={answer}
            />
            <GuideRefinements
              refinements={resolved.refinements}
              unavailable={unavailable}
              because={because}
              more={more}
              opened={opened}
              onOpenChange={setOpened}
              onSelect={answer}
            />
          </div>
          {/* The questions keep a fixed width — they are a list of
              short labels and do not want more. The pieces and the
              words split what is left evenly: `min-w-0` because a flex
              child will not shrink below its content otherwise, and a
              long filename under a part would push the text column
              off the side. */}
          <div className="lg:flex-1 lg:min-w-0 overflow-y-auto min-h-0 pr-2">
            <GuideParts
              parts={resolved.parts}
              refinements={resolved.refinements}
              options={options}
              inspecting={inspecting}
              onInspect={setInspecting}
              onSelect={select}
              onSelectAll={selectAll}
            />
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
