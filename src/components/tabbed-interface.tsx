'use client'

import React, { useState, useEffect } from 'react';
import TabPartSearch from './tab-part-search';
import GuidePage from './guides/guide-page';
import TabAdmin from './tab-admin';
import { useAdminContext } from '@/contexts/admin-context';
import { loadAppConfig } from '@/utils/app-config';

const TabbedInterface = () => {
  const [activeTab, setActiveTab] = useState<'partSearch' | 'guides' | 'baseGenerator' | 'admin'>('partSearch');
  const [baseGeneratorUrl, setBaseGeneratorUrl] = useState(process.env.NEXT_PUBLIC_BASE_GENERATOR_URL || 'http://localhost:8000');

  const { state } = useAdminContext();

  // A guide in the URL means the person is looking at a guide, so open
  // on that tab rather than dropping them on Part Search holding a
  // parameter nothing on screen explains. This is what makes a card's
  // in-place selection survive a reload and `/?guide=wall` shareable
  // from inside the tab.
  //
  // In an effect, not a `useState` initialiser. This is a static
  // export: the HTML is prerendered with no `window`, so an initialiser
  // reading `location.search` picks `partSearch` at build time and the
  // real page loads on the wrong tab — which it did, while the jsdom
  // test passed, because jsdom never prerenders.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('guide')) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveTab('guides');
    }
  }, []);

  // Mounted from the first time it is opened, and kept mounted after.
  //
  // Purely conditional was wrong in the other direction: leaving the
  // tab unmounted the guide, so coming back refetched the document, the
  // resolution and the availability, and the options count — which
  // rides on the slowest of the three — visibly vanished and returned.
  // Three requests and a flicker for a tab the person had already
  // loaded.
  const [guidesOpened, setGuidesOpened] = useState(false);
  useEffect(() => {
    if (activeTab === 'guides' && !guidesOpened) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setGuidesOpened(true);
    }
  }, [activeTab, guidesOpened]);

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
            className={`tab ${activeTab === 'partSearch' ? 'active' : ''}`}
            onClick={() => setActiveTab('partSearch')}
          >
            Part Search
          </button>
          <button
            className={`tab ${activeTab === 'guides' ? 'active' : ''}`}
            onClick={() => setActiveTab('guides')}
          >
            Guided Builds
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
          {/* Mounted only while it is the open tab, unlike its
              neighbours until it has been opened once. A hidden
              `GuidePage` still runs its effects, so mounting it up front
              would spend a Lambda invocation on /api/guides for every
              visitor who never opens this tab. After the first open it
              stays, because unmounting on every tab switch refetched
              everything and made the options count flicker. */}
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
            {guidesOpened && <GuidePage />}
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
