'use client';

import React, { useEffect, useState } from 'react';
import { fetchGuides, type GuideSummary } from '@/services/guide-service';
import { isPlainClick, selectGuide } from '@/hooks/use-guide-state';

/**
 * The page people arrive at: a card per thing they might want to build.
 *
 * A catalog look rather than a list of links, because that is what the
 * rest of this hobby's sites look like and because the illustration is
 * the part that answers "is this the thing I want?" — a wall guide and a
 * floor guide read identically as two lines of text.
 *
 * Its own file rather than a third component inside `guide-page.tsx`,
 * which `complexity-reviewer` has flagged twice for length.
 */
export default function GuideEntry() {
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

  return (
    // A `div`, not a `main`. This renders in two places — as the whole
    // of `/guides`, where `guide-page.tsx` supplies the landmark, and as
    // a tab panel inside `MainContentWrapper`'s `main`, where a second
    // one would nest. `main` forbids a `main` ancestor and ARIA wants
    // one per document, and the component cannot know which place it is
    // in, so neither use declares it.
    <div className="p-6 mx-auto max-w-6xl">
      {/* The heading first, then whatever the fetch turns out to say.
          Returning null until the guides land made the feature's
          landing page a blank document for the length of a cold start,
          which reads as broken rather than as loading. */}
      {/* An `h1`, and there is another one on the same page:
          `instructions-part-search.tsx` has its own. Not a conflict —
          the inactive tab panel is `display: none`, which prunes it from
          the accessibility tree, so exactly one is exposed at a time.
          Recorded because it is the fourth thing about this component
          that changed meaning when it became a panel as well as a whole
          route, and it is the one that turned out to be fine. If a tab
          is ever shown by another mechanism than `display`, this and
          that one start colliding. */}
      <h1 className="text-3xl font-bold">Guided builds</h1>
      <p className="mt-2 mb-6 max-w-2xl text-gray-700">
        Pick what you want to build and answer a few questions. You get a
        parts list with the files to print.
      </p>
      {guides !== null && (failed ? <AskFailed /> : <Cards guides={guides} />)}
    </div>
  );
}

function AskFailed() {
  return <p>Could not load the guides.</p>;
}

function Cards({ guides }: { guides: GuideSummary[] }) {
  if (guides.length === 0) return <p>No guides yet.</p>;
  return (
    // `auto-fill` rather than a fixed column count so one guide is one
    // card at its natural size instead of one card stretched across the
    // page. There is exactly one guide today.
    <ul className="grid grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] gap-6 list-none p-0">
      {guides.map((guide) => (
        <li key={guide.guide_key}>
          <GuideCard guide={guide} />
        </li>
      ))}
    </ul>
  );
}

/**
 * One card. The whole card is the link, not just the title.
 *
 * Sized against what the comparable catalogs do — Printables,
 * MyMiniFactory, Printable Scenery all land near a 16rem column with a
 * square image — so the illustrations are authored at 640px and drawn at
 * about half that, which keeps them sharp on a 2x display.
 */
function GuideCard({ guide }: { guide: GuideSummary }) {
  return (
    <a
      // A real link to the standalone route, so middle-click and
      // open-in-new-tab give a whole page — but a plain left click is
      // taken over, because in the Guided Builds tab following it would
      // navigate out of the tabbed app into a route with no tab strip.
      // Picking a guide writes the URL in place instead and the panel
      // swaps to it; on `/guides` the two are the same destination and
      // this just avoids a reload.
      href={`/guides/?guide=${encodeURIComponent(guide.guide_key)}`}
      onClick={(e) => {
        if (!isPlainClick(e)) return;
        e.preventDefault();
        selectGuide(guide.guide_key);
      }}
      // `h-full` and a column so every card in a row is the same height
      // whatever its summary runs to. Without it the grid is ragged
      // along the bottom, because a guide with two sentences makes a
      // taller card than one with six words.
      className="group flex h-full flex-col overflow-hidden rounded-lg border
                 border-gray-200 bg-white transition-shadow hover:shadow-lg
                 focus-visible:outline focus-visible:outline-2
                 focus-visible:outline-blue-700"
    >
      <CardImage guide={guide} />
      <div className="p-4">
        <h2 className="font-semibold text-lg group-hover:text-blue-700">
          {guide.title}
        </h2>
        {guide.summary && (
          // Clamped, because nothing bounds a summary: the schema takes
          // any string, and the card is a teaser for the guide rather
          // than a place to read it.
          <p className="mt-1 text-sm text-gray-600 line-clamp-3">
            {guide.summary}
          </p>
        )}
      </div>
    </a>
  );
}

/**
 * The illustration, or a stand-in that is not a broken image.
 *
 * Two ways there is no picture, and they have to look the same: a guide
 * authored without one, and a URL whose file is not in the bucket. The
 * second is not hypothetical — the document carries the URL and the
 * upload is a separate step, so the ordinary state during authoring is a
 * guide whose illustration 404s. A browser's broken-image glyph reads as
 * a bug in the page; an empty frame reads as a guide nobody has
 * photographed yet, which is what it is.
 *
 * `aspect-square` on the frame rather than a height on the image, so the
 * grid does not reflow as the pictures arrive.
 */
function CardImage({ guide }: { guide: GuideSummary }) {
  const [broken, setBroken] = useState(false);

  return (
    <div className="aspect-square w-full bg-gray-100">
      {guide.hero_image && !broken && (
        <img
          src={guide.hero_image}
          // Empty on purpose. The whole card is one link, so its
          // accessible name is its contents — and the heading below
          // already says "Wall". An alt of the title makes the link
          // announce the name twice, which is what a decorative image
          // beside a heading that names it is supposed to avoid.
          alt=""
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => setBroken(true)}
        />
      )}
    </div>
  );
}
