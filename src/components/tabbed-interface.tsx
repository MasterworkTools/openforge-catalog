'use client'

import React, { useState, useEffect } from 'react';
import TabPartSearch from './tab-part-search';
import TabBlueprints from './tab-blueprints';
import TabAdmin from './tab-admin';
import { useAdminContext } from '@/contexts/admin-context';

const TabbedInterface = () => {
  const [activeTab, setActiveTab] = useState<'partSearch' | 'blueprints' | 'baseGenerator' | 'admin'>('partSearch');
  const [baseGeneratorUrl, setBaseGeneratorUrl] = useState(process.env.NEXT_PUBLIC_BASE_GENERATOR_URL || 'http://localhost:8000');

  const { state } = useAdminContext();

  useEffect(() => {
    // Load base generator URL from localStorage and app-config.json
    const savedUrl = localStorage.getItem('baseGeneratorUrl');
    if (savedUrl) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setBaseGeneratorUrl(savedUrl);
    }

    fetch('/app-config.json')
      .then(res => res.json())
      .then(cfg => { if (cfg.BASE_GENERATOR_URL) setBaseGeneratorUrl(cfg.BASE_GENERATOR_URL); })
      .catch(err => console.error("Failed to load or parse app-config.json", err));
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
            className={`tab ${activeTab === 'blueprints' ? 'active' : ''}`}
            onClick={() => setActiveTab('blueprints')}
          >
            Blueprints
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
          <div style={{ display: activeTab === 'blueprints' ? 'block' : 'none' }}>
            <TabBlueprints />
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
