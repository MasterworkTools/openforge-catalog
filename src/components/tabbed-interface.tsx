'use client'

import React, { useCallback, useEffect, useState } from 'react';
import TabPartSearch from './tab-part-search';
import GuidePage from './guides/guide-page';
import TabAdmin from './tab-admin';
import { useAdminContext } from '@/contexts/admin-context';
import { loadAppConfig } from '@/utils/app-config';

const TabbedInterface = () => {
  const [activeTab, setActiveTab] = useState<'partSearch' | 'guides' | 'baseGenerator' | 'admin'>('guides');
  const [baseGeneratorUrl, setBaseGeneratorUrl] = useState(process.env.NEXT_PUBLIC_BASE_GENERATOR_URL || 'http://localhost:8000');

  const { state } = useAdminContext();

  const openGuides = useCallback(() => setActiveTab('guides'), []);

  // A guide in the URL means the person is looking at a guide, so this
  // follows it back onto that tab — on `popstate` as well as at mount,
  // because back and forward move the URL without remounting anything,
  // and the person may have moved to another tab since.
  //
  // Only ever *into* the guides tab. A URL with no guide in it means
  // the cards, which is this tab anyway; switching away would take
  // someone off a tab they are using.
  //
  // In an effect rather than a `useState` initialiser, and that is not
  // a style choice: this is a static export, so the markup is
  // prerendered with no `window` and an initialiser reading
  // `location.search` would bake the build-time answer into it.
  useEffect(() => {
    const follow = () => {
      if (new URLSearchParams(window.location.search).get('guide')) {
        openGuides();
      }
    };
    follow();
    window.addEventListener('popstate', follow);
    return () => window.removeEventListener('popstate', follow);
  }, [openGuides]);

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
