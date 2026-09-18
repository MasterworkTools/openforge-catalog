'use client'

import React from 'react';
import { AdminProvider } from '@/contexts/admin-context';
import TabbedInterface from './tabbed-interface';
import AdminHeader from './admin-header';

export default function MainContentWrapper() {
  return (
    <AdminProvider>
      <main className="min-h-screen bg-gray-100">
        <div className='pageContainer'>
          <div className='pageHeaderWrapper'>
            OpenForge Catalog
            <div className='pageHeaderRight'>
              Version 0.6.8 |&nbsp;
              <a className='visibleLink' href='https://masterworktools.github.io/openforge-tutorials/' target="_blank" rel="noreferrer">Wiki</a> |&nbsp;
              <a className='visibleLink' href='https://www.patreon.com/masterworktools' target="_blank" rel="noreferrer">Support us on Patreon</a>
              <AdminHeader />
            </div>
          </div>
          <TabbedInterface />
        </div>
      </main>
    </AdminProvider>
  );
}
