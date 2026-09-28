'use client';

import GuideEntry from './guide-entry';
import React, { useMemo, useState } from 'react';
import { narrows, releasedBy } from '@/services/guide-service';
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
    status,
    select,
    selectAll,
  } = useGuideState(guideKey);
  // Which settled question has been reopened. Here rather than in the
  // section itself, because the explanation beside it follows.
  const [opened, setOpened] = useState<string | null>(null);
  // Whose catalog dialog is open, by role. The role rather than the
  // part, because a part is a snapshot of one resolution and the
  // dialog outlives it: `GuideParts` renders nothing when a resolution
  // has no parts, so stepping back to the first screen unmounts the
  // dialog without closing it, and stepping forward again reopened it
  // holding the old part — a pick then wrote a pin against a predicate
  // the questions no longer agreed to. A role is the same role in
  // every resolution. Here rather than in the parts list, because the
  // questions on the left open it too.
  const [inspecting, setInspecting] = useState<string | null>(null);

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
          onOpen: () => setInspecting(choices[0].role),
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
  // No landmark here either. This component is the whole of `/guides`
  // *and* the Guided Builds tab panel, so whichever element it picks is
  // wrong in one of them. `src/app/guides/page.tsx` supplies the `main`
  // for the route; inside the tab, `MainContentWrapper` already has one.
  if (!guideKey) return <GuideEntry />;

  return (
    // A fixed-height page rather than a scrolling one, because the
    // three columns fill up at different rates: the questions grow as
    // you answer them, the parts stay about the same, and the prose
    // varies wildly. Scrolling them together means hunting for the
    // question you wanted while the pictures slide away.
    //
    // Only where there are columns, though. The columns are gated on
    // `lg:` and the height was not, so on a phone this was one
    // viewport holding three independent scrollers stacked down it —
    // a few of the answers, a part and a half, a paragraph and a bit,
    // and no way to scroll the page itself. Below `lg` it is an
    // ordinary document again.
    <div className="p-6 lg:h-screen flex flex-col">
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
              answers live in the URL, so dropping them is a plain link
              rather than anything this component has to hold.
              A `Link` would not do: the page reads the URL through
              `useSyncExternalStore` over `popstate`, which pushState
              does not fire, so it would change the address bar and
              leave the page on the state that failed.

              Two arms, because `error` covers two failures. If the
              guide document loaded, the selections are the problem and
              dropping them is the fix. If it did not — an unknown key
              — then starting that same guide over reloads the same
              404, and there is no site nav to escape by, so the way
              out is the list. */}
          {/* Exactly 500, because it is the only status a broken
              document can arrive as: Flask runs inside the Lambda, so
              an unhandled `ValueError` is a 500 and never a 502. A 502
              or 504 is a cold start or a container that went away and
              a 503 is no healthy target — none of those is a statement
              about the stored guide, so they keep the retry.

              Not the converse. A 500 is *also* what a psycopg failure
              against serverless Postgres looks like, and there is no
              app-wide error handler to tell the two apart, so this arm
              sends a transient fault to the list. It costs the person
              a link, not their answers: neither link retries the
              request that failed, and both drop the selections — the
              cost is one more click, since `?guide=X` is a full
              navigation and does re-ask the API. Telling them apart needs the
              document fault to carry a JSON body the page can key on,
              which is its own change. */}
          {!resolved &&
            (guide && status !== 500 ? (
              <a
                href={`?guide=${encodeURIComponent(guideKey)}`}
                className="text-blue-700 underline"
              >
                Start this guide over
              </a>
            ) : (
              <a href="./" className="text-blue-700 underline">
                All guides
              </a>
            ))}
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
          <div className="lg:w-72 lg:shrink-0 lg:overflow-y-auto lg:min-h-0 pr-2">
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
          <div className="lg:flex-1 lg:min-w-0 lg:overflow-y-auto lg:min-h-0 pr-2">
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
          <div className="lg:flex-1 lg:min-w-0 lg:overflow-y-auto lg:min-h-0 pr-2">
            <GuideExplainer
              steps={resolved.steps}
              refinements={resolved.refinements}
              unavailable={unavailable}
              opened={opened}
            />
          </div>
        </div>
      )}
    </div>
  );
}
