'use client'

import React, { useEffect, useState } from 'react';
import { loadAppConfig, type AppConfig } from '@/utils/app-config';

/** Hostname alone reads better in a sentence than the full URL. */
function hostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

/**
 * The same page on production, so a deep link someone followed here keeps working.
 * Blueprint links carry their identifier in the query string, so the query has to
 * travel with the path.
 */
function productionHref(productionUrl: string): string {
  if (typeof window === 'undefined') {
    return productionUrl;
  }
  const { pathname, search, hash } = window.location;
  try {
    return new URL(`${pathname}${search}${hash}`, productionUrl).toString();
  } catch {
    return productionUrl;
  }
}

/** A bare home page needs no "this page" phrasing. */
function isDeepLink(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  const { pathname, search } = window.location;
  return search.length > 0 || pathname.replace(/\/+$/, '') !== '';
}

/**
 * Tells visitors when they are not on the live catalog.
 *
 * Fixed rather than in flow: the layout is full of `calc(100vh - N)` rules that
 * would each be short by the banner's height if it took up space.
 */
export default function EnvironmentBanner() {
  const [config, setConfig] = useState<AppConfig | null>(null);

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
  if (!environment || environment === 'production') {
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
      {productionUrl && (
        <>
          {' '}
          <a
            className="font-semibold underline"
            href={productionHref(productionUrl)}
          >
            {isDeepLink()
              ? `Open this page on ${hostname(productionUrl)}`
              : `Go to the live catalog at ${hostname(productionUrl)}`}
          </a>
        </>
      )}
    </div>
  );
}
