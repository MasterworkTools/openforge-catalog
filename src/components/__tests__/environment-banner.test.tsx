import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import EnvironmentBanner from '../environment-banner';
import { AppConfig } from '@/utils/app-config';

function mockConfig(config: AppConfig | Error) {
  global.fetch = jest.fn().mockImplementation(() =>
    config instanceof Error
      ? Promise.reject(config)
      : Promise.resolve({ ok: true, json: () => Promise.resolve(config) }),
  ) as jest.Mock;
}

describe('EnvironmentBanner', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    window.history.pushState({}, '', '/');
    jest.restoreAllMocks();
  });

  it('names the environment and links to production off production', async () => {
    mockConfig({ ENVIRONMENT: 'staging', PRODUCTION_URL: 'https://openforge.tools' });

    render(<EnvironmentBanner />);

    const banner = await screen.findByRole('status');
    expect(banner).toHaveTextContent('This is the OpenForge staging instance');
    const link = screen.getByRole('link', { name: /live catalog at openforge\.tools/i });
    expect(link).toHaveAttribute('href', 'https://openforge.tools/');
  });

  it('carries a deep link across to production so old staging links keep working', async () => {
    window.history.pushState({}, '', '/?blueprint_id=00047386-f1cf-4e5f-976b-c19c6d8fecc9&md5=abc');
    mockConfig({ ENVIRONMENT: 'staging', PRODUCTION_URL: 'https://openforge.tools' });

    render(<EnvironmentBanner />);

    const link = await screen.findByRole('link');
    expect(link).toHaveAttribute(
      'href',
      'https://openforge.tools/?blueprint_id=00047386-f1cf-4e5f-976b-c19c6d8fecc9&md5=abc',
    );
    expect(link).toHaveTextContent('Open this page on openforge.tools');
  });

  it('carries the path as well as the query', async () => {
    window.history.pushState({}, '', '/admin/?tab=blueprints');
    mockConfig({ ENVIRONMENT: 'staging', PRODUCTION_URL: 'https://openforge.tools' });

    render(<EnvironmentBanner />);

    const link = await screen.findByRole('link');
    expect(link).toHaveAttribute('href', 'https://openforge.tools/admin/?tab=blueprints');
  });

  it('renders nothing on production', async () => {
    mockConfig({ ENVIRONMENT: 'production', PRODUCTION_URL: 'https://openforge.tools' });

    const { container } = render(<EnvironmentBanner />);

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the config names no environment', async () => {
    mockConfig({ BASE_GENERATOR_URL: 'https://openscad.openforge.tools' });

    render(<EnvironmentBanner />);

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('still warns when no production URL is configured', async () => {
    mockConfig({ ENVIRONMENT: 'staging' });

    render(<EnvironmentBanner />);

    const banner = await screen.findByRole('status');
    expect(banner).toHaveTextContent('This is the OpenForge staging instance');
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('stays silent when the config cannot be loaded', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    mockConfig(new Error('network down'));

    render(<EnvironmentBanner />);

    await waitFor(() => expect(console.error).toHaveBeenCalled());
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
