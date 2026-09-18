import { CombinedBlueprintDocumentation } from '@/types';

export class DocumentationService {
  static async getBlueprintAllDocumentation(
    blueprintId: string,
    changelogLimit: number = 10,
    changelogOffset: number = 0
  ): Promise<CombinedBlueprintDocumentation | null> {
    try {
      const response = await fetch(
        `/api/blueprints/${blueprintId}/all-documentation?changelog_limit=${changelogLimit}&changelog_offset=${changelogOffset}`
      );

      if (!response.ok) {
        if (response.status === 404) {
          // Documentation not found - this is normal, not an error
          return null;
        }
        throw new Error(`Failed to fetch documentation: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching blueprint documentation:', error);
      return null;
    }
  }

  static async getBlueprintChangelogHistory(
    blueprintId: string,
    limit: number = 10,
    offset: number = 0
  ) {
    try {
      const response = await fetch(
        `/api/blueprints/${blueprintId}/changelog-history?limit=${limit}&offset=${offset}`
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch changelog history: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching changelog history:', error);
      return null;
    }
  }
}
