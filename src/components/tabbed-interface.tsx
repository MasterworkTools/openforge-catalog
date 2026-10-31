'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react';
import TabPartSearch from './tab-part-search';
import GuidePage from './guides/guide-page';
import TabAdmin from './tab-admin';
import { useAdminContext } from '@/contexts/admin-context';
import { loadAppConfig } from '@/utils/app-config';
import { clearGuide } from '@/hooks/use-guide-state';
import { CONSUMED } from '@/hooks/use-url-parameters';

/** Which tab a URL is asking for, or null if it does not say. */
function tabFor(search: string): 'guides' | 'partSearch' | null {
  const params = new URLSearchParams(search);
  // A guide wins over everything: `?guide=x&tag=y` is a guide link
  // that happens to carry a stale parameter, not a search.
  if (params.get('guide')) return 'guides';
  return CONSUMED.some((key) => params.has(key)) ? 'partSearch' : null;
}

const TabbedInterface = () => {
  const [activeTab, setActiveTab] = useState<'partSearch' | 'guides' | 'baseGenerator' | 'admin'>('guides');
  const [baseGeneratorUrl, setBaseGeneratorUrl] = useState(process.env.NEXT_PUBLIC_BASE_GENERATOR_URL || 'http://localhost:8000');

  const { state } = useAdminContext();

  // The query string the page was opened with.
  //
  // Captured in the first render rather than read in the effect below,
  // and that is load-bearing: `use-url-parameters` takes its own
  // parameters out of the URL once Part Search mounts, and a child's
  // effect runs before its parent's, so by the time the effect looks
  // there is nothing left to see. A parent renders before its children
  // mount, so this still sees them. Nothing is rendered from it, so
  // the prerendered markup is unaffected.
  const landing = useRef<string | null>(null);
  if (landing.current === null) {
    landing.current = typeof window === 'undefined' ? '' : window.location.search;
  }

  const showGuides = useCallback(() => setActiveTab('guides'), []);

  // The tab is a way out of a build, clicked from any tab: a build is
  // its query string, so leaving it there would make the button do
  // nothing for the person already looking at it. Only the button —
  // the effect below follows a guide URL onto this tab and must not
  // throw away the guide it came for.
  const openGuides = useCallback(() => {
    showGuides();
    clearGuide();
  }, [showGuides]);

  // The URL says which tab the person meant, so this follows it — on
  // `popstate` as well as at mount, because back and forward move the
  // URL without remounting anything and the person may have moved to
  // another tab since.
  //
  // Both ways. A link carrying Part Search's own parameters is a
  // shared result, and the copy-link button builds them, so landing
  // such a link on the guides tab hides what it pointed at. A URL
  // naming neither leaves the tab alone.
  //
  // In an effect rather than a `useState` initialiser, and that is not
  // a style choice: this is a static export, so the markup is
  // prerendered with no `window` and an initialiser reading
  // `location.search` would bake the build-time answer into it.
  useEffect(() => {
    const go = (want: 'guides' | 'partSearch' | null) => {
      if (want) setActiveTab(want);
    };
    // The landing URL at mount, because Part Search has taken its own
    // parameters out by now; the live one afterwards, because back and
    // forward put them back.
    go(tabFor(landing.current ?? ''));
    const follow = () => go(tabFor(window.location.search));
    window.addEventListener('popstate', follow);
    return () => window.removeEventListener('popstate', follow);
  }, []);

  useEffect(() => {
    // Load base generator URL from localStorage and app-config.json
    const savedUrl = localStorage.getItem('baseGeneratorUrl');
    if (savedUrl) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setBaseGeneratorUrl(savedUrl);
    }

    loadAppConfig().then(cfg => { if (cfg.BASE_GENERATOR_URL) setBaseGeneratorUrl(cfg.BASE_GENERATOR_URL); });
  }, []);


  return (
    <div className="tabbedInterface">
      <div className="tabContainer">
        <div className="tabButtons">
          <button
            className={`tab ${activeTab === 'guides' ? 'active' : ''}`}
            onClick={openGuides}
          >
            Guided Builds
          </button>
          <button
            className={`tab ${activeTab === 'partSearch' ? 'active' : ''}`}
            onClick={() => setActiveTab('partSearch')}
          >
            Part Search
          </button>
          <button
            className={`tab ${activeTab === 'baseGenerator' ? 'active' : ''}`}
            onClick={() => setActiveTab('baseGenerator')}
          >
            Base Generator
          </button>
          {state.isAuthenticated && (
            <button
              className={`tab ${activeTab === 'admin' ? 'active' : ''}`}
              onClick={() => setActiveTab('admin')}
            >
              Admin
            </button>
          )}
        </div>
        <div className="tabContent">
          <div style={{ display: activeTab === 'partSearch' ? 'block' : 'none' }}>
            <TabPartSearch />
          </div>
          {/* Mounted unconditionally, like its neighbours. It is the
              tab the site opens on, so every visitor fetches the guides
              anyway, and unmounting on a tab switch refetched the
              document, the resolution and the availability — the
              options count rides on the slowest of those and visibly
              vanished and returned. */}
          <div
            style={{
              display: activeTab === 'guides' ? 'block' : 'none',
              // `.tabContent` is a fixed height with `overflow: hidden`,
              // so a pane that does not handle its own overflow has its
              // content cut off and unreachable — the document does not
              // scroll either. Every sibling handles it: Part Search on
              // its three column wrappers, the Base Generator with
              // `height: 100%` on the div below. This one is plain flow
              // content, so it needs both.
              //
              // Invisible today because one guide fits at every
              // viewport. It becomes a bug the moment a second guide
              // ships, which is a data change with no code change.
              height: '100%',
              overflowY: 'auto',
            }}
          >
            <GuidePage />
          </div>
          <div style={{ display: activeTab === 'baseGenerator' ? 'block' : 'none', height: '100%' }}>
            <iframe src={baseGeneratorUrl} style={{ width: '100%', height: '100%', border: 'none', display: 'block' }} title="Base Generator" />
          </div>
          {state.isAuthenticated && (
            <div style={{ display: activeTab === 'admin' ? 'block' : 'none' }}>
              <TabAdmin />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TabbedInterface;
