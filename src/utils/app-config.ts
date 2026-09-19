/**
 * Runtime configuration, served next to the static export as /app-config.json.
 *
 * The build is environment-agnostic: each deploy writes this file into the
 * bucket it syncs to, so staging and production differ without rebuilding.
 * public/app-config.json holds the local-development values.
 */

export interface AppConfig {
  /** OpenSCAD base generator the "Base Generator" tab embeds. */
  BASE_GENERATOR_URL?: string;
  /** "development", "staging" or "production". Anything but production shows a banner. */
  ENVIRONMENT?: string;
  /** Public URL of the live catalog, linked from that banner. */
  PRODUCTION_URL?: string;
}

export async function loadAppConfig(): Promise<AppConfig> {
  try {
    const response = await fetch('/app-config.json');
    if (!response.ok) {
      throw new Error(`/app-config.json returned ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    // A missing or malformed config leaves every consumer on its default.
    console.error('Failed to load or parse app-config.json', error);
    return {};
  }
}
