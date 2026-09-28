'use client'

import React, { useState, useEffect } from 'react';
import TabPartSearch from './tab-part-search';
import GuideEntry from './guides/guide-entry';
import TabAdmin from './tab-admin';
import { useAdminContext } from '@/contexts/admin-context';
import { loadAppConfig } from '@/utils/app-config';

const TabbedInterface = () => {
  const [activeTab, setActiveTab] = useState<'partSearch' | 'guides' | 'baseGenerator' | 'admin'>('partSearch');
  const [baseGeneratorUrl, setBaseGeneratorUrl] = useState(process.env.NEXT_PUBLIC_BASE_GENERATOR_URL || 'http://localhost:8000');

  const { state } = useAdminContext();

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
              neighbours. A hidden `GuideEntry` still runs its effect, so
              leaving it mounted would spend a Lambda invocation on
              /api/guides for every visitor who never opens this tab.
              Re-opening re-fetches, which is a small response and no
              cache to get wrong. */}
          <div style={{ display: activeTab === 'guides' ? 'block' : 'none' }}>
            {activeTab === 'guides' && <GuideEntry />}
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
