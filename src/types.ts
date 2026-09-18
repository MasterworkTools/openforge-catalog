export interface Image {
  created_at: string;
  id: string;
  image_name: string;
  image_url: string;
  updated_at: string;
}

export interface ConfigTag {
  tag: string;
}

export type ConstrainTag =
  | { tag: string; siblings?: string[]; parent?: boolean }
  | { filter: string };

export interface ConfigTags {
  accept?: ConfigTag[];
  require?: ConfigTag[];
  deny?: ConfigTag[];
  constrain?: ConstrainTag[];
}

export interface ConfigPart {
  name: string;
  optional?: boolean;
  tags: ConfigTags;
  fulfills?: { part: string }[];
}

export interface BlueprintConfig {
  parts?: ConfigPart[];
  fulfills?: { part: string }[];
}

export interface Blueprint {
  blueprint_name: string;
  blueprint_type: string;
  blueprint_config?: BlueprintConfig;
  created_at: string;
  file_md5: string;
  file_modified_at: string;
  file_name: string;
  file_size: number;
  full_name: string;
  id: string;
  images: Image[];
  signed_url: string;
  storage_address: string;
  tags: string[];
  updated_at: string;
}

// Documentation types
export interface BlueprintDocumentation {
  id: string;
  blueprint_id: string;
  document: string;
  document_type: 'changelog' | 'instructions';
  is_live: boolean;
  created_at: string;
  updated_at: string;
}

export interface TagDocumentation {
  id: string;
  tag: string[];
  document: string;
  document_type: 'instructions';
  is_live: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChangelogEntry {
  blueprint_id: string;
  blueprint_name: string;
  changelog: string | null;
  created_at: string | null;
  depth: number;
  successor_id: string | null;
  deprecated: boolean;
}

export interface ChangelogHistory {
  changelogs: ChangelogEntry[];
  has_more: boolean;
  total_count: number;
}

export interface CombinedBlueprintDocumentation {
  blueprint_id: string;
  blueprint_name: string;
  blueprint_documentation: BlueprintDocumentation[];
  changelog_history: ChangelogHistory;
  tag_documentation: Record<string, TagDocumentation[]>;
}

export interface TagNode {
  __count?: number;
  __totalCount?: number;
  __subTags?: number;
  children?: Record<string, TagNode>;
  [key: string]: unknown;
}

export interface Paging {
  previous_token: string | undefined;
  next_token: string | undefined;
  total_count: number;
  start_count: number;
}

// Sprite thumbnail types
export interface SpriteAngle {
  index: number;
  name: string;
  camera_pos: [number, number, number];
}

export interface SpriteThumbnailData {
  type: 'sprite';
  sprite_url: string;
  grid_rows: number;
  grid_cols: number;
  tile_size: number;
  angles: SpriteAngle[];
  default_angle: number;
}

export interface LegacyThumbnailData {
  type: 'single';
  thumbnail_url: string;
}

export type ThumbnailVariants = SpriteThumbnailData | LegacyThumbnailData;
