'use client'

import React, { useEffect, useState } from 'react';
import { loadAppConfig, type AppConfig } from '@/utils/app-config';
import { hostname, isDeepLink, productionHref, type PageLocation } from '@/utils/environment-link';

/** The URL the visitor arrived with, read before anything rewrites it. */
function entryLocation(): PageLocation | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const { pathname, search, hash } = window.location;
  return { pathname, search, hash };
}

/**
 * Tells visitors when they are not on the live catalog, and offers them the page
 * they asked for on it.
 *
 * Fixed rather than in flow: the layout sizes its panes with `calc(100vh - N)`,
 * which would each be short by the banner's height if it took up space. Instead the
 * banner marks the body so those panes can leave room for it.
 */
export default function EnvironmentBanner() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  // A lazy initializer runs during the first render, before the effects in
  // use-url-parameters and use-blueprint-url-cleanup strip blueprint_id from the URL.
  const [arrivedAt] = useState<PageLocation | null>(entryLocation);

  useEffect(() => {
    let active = true;
    loadAppConfig().then((loaded) => {
      if (active) {
        setConfig(loaded);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const environment = config?.ENVIRONMENT;
  const visible = Boolean(environment) && environment !== 'production';

  useEffect(() => {
    if (!visible) {
      return;
    }
    document.body.classList.add('hasEnvironmentBanner');
    return () => {
      document.body.classList.remove('hasEnvironmentBanner');
    };
  }, [visible]);

  if (!visible) {
    return null;
  }

  const productionUrl = config?.PRODUCTION_URL;

  return (
    <div
      role="status"
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-amber-400 bg-amber-100 px-4 py-2 text-center text-sm text-amber-900 shadow-[0_-1px_4px_rgba(0,0,0,0.12)]"
    >
      This is the OpenForge <strong>{environment}</strong> instance. Its catalog is a copy and may be
      out of date.
      {productionUrl && arrivedAt && (
        <>
          {' '}
          <a
            className="font-semibold underline"
            href={productionHref(productionUrl, arrivedAt)}
          >
            {isDeepLink(arrivedAt)
              ? `Open this page on ${hostname(productionUrl)}`
              : `Go to the live catalog at ${hostname(productionUrl)}`}
          </a>
        </>
      )}
    </div>
  );
}
