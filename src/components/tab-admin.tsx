'use client'

import React, { useState } from 'react';
import './tab-admin.css';
import DocumentationEditor from './admin/documentation-editor';
import DeprecatedObjectsManager from './admin/deprecated-objects-manager';

type AdminSubTab = 'documentation' | 'deprecated';

const TabAdmin = () => {
  const [activeSubTab, setActiveSubTab] = useState<AdminSubTab>('documentation');

  return (
    <div className="admin-tab">
      <div className="admin-content">
        <h2>Admin Panel</h2>

        {/* Sub-tab navigation */}
        <div className="admin-sub-tabs">
          <button
            className={`admin-sub-tab ${activeSubTab === 'documentation' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('documentation')}
          >
            Documentation Editor
          </button>
          <button
            className={`admin-sub-tab ${activeSubTab === 'deprecated' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('deprecated')}
          >
            Deprecated Objects
          </button>
        </div>

        {/* Sub-tab content */}
        <div className="admin-sub-content">
          {activeSubTab === 'documentation' && (
            <DocumentationEditor />
          )}
          {activeSubTab === 'deprecated' && (
            <DeprecatedObjectsManager />
          )}
        </div>
      </div>
    </div>
  );
};

export default TabAdmin;
