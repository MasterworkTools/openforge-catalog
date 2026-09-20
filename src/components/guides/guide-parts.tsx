'use client';

import React from 'react';
import { GuidePart, thumbnailOf } from '@/services/guide-service';
import { downloadFiles } from '@/utils/blueprint-utils';

/**
 * The answer: one recommended piece per role, with its picture and its
 * download. A role that matched nothing says so rather than vanishing.
 */
export function GuideParts({ parts }: { parts: GuidePart[] }) {
  if (parts.length === 0) return null;
  const urls = parts
    .filter((part) => part.blueprint)
    .map((part) => `/api/blueprints/${part.blueprint!.id}/download`);

  return (
    <section className="guide-parts">
      <h2 className="text-xl font-bold mb-3">What to print</h2>
      <ul className="flex flex-col gap-3">
        {parts.map((part) => (
          <li key={part.role} className="border border-gray-300 rounded p-3">
            <Part part={part} />
          </li>
        ))}
      </ul>
      {urls.length > 0 && (
        <button
          type="button"
          className="mt-4 border border-gray-300 rounded px-3 py-2"
          onClick={() => downloadFiles(urls)}
        >
          Download all {urls.length} files
        </button>
      )}
    </section>
  );
}

function Part({ part }: { part: GuidePart }) {
  const image = thumbnailOf(part.blueprint);
  return (
    <div className="flex items-center gap-3">
      {image && (
        <img
          src={image.image_url}
          alt={part.blueprint?.blueprint_name ?? part.title}
          className="w-16 h-16 object-contain"
        />
      )}
      <div>
        <div className="font-semibold">
          {part.title}
          {part.under && (
            <span className="font-normal text-sm"> (under the {part.under})</span>
          )}
        </div>
        {part.blueprint ? (
          <a
            href={`/api/blueprints/${part.blueprint.id}/download`}
            className="text-blue-700 underline break-all"
          >
            {part.blueprint.blueprint_name}
          </a>
        ) : (
          <span className="text-sm">
            Nothing in the catalog matches this combination yet.
          </span>
        )}
      </div>
    </div>
  );
}
