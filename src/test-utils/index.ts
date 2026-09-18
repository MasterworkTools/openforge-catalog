import type { Blueprint, Paging, ConfigTags } from '@/types';

// Mock clipboard API
export const mockClipboard = {
  writeText: jest.fn(),
};

// Test data factories
export const createMockBlueprint = (overrides: Partial<Blueprint> = {}): Blueprint => ({
  id: '1',
  blueprint_name: 'Test Blueprint',
  blueprint_type: 'model',
  file_name: 'test.stl',
  file_md5: 'abc123',
  file_size: 1024,
  file_modified_at: '2023-01-01T00:00:00Z',
  full_name: 'Test Blueprint Full Name',
  created_at: '2023-01-01T00:00:00Z',
  updated_at: '2023-01-01T00:00:00Z',
  storage_address: '/test/path',
  signed_url: 'https://test.com/file',
  tags: [],
  images: [],
  ...overrides,
});

export const createMockPaging = (overrides: Partial<Paging> = {}): Paging => ({
  total_count: 10,
  start_count: 0,
  next_token: 'next-token',
  previous_token: 'prev-token',
  ...overrides,
});

export const createMockConfigTags = (overrides: Partial<ConfigTags> = {}): ConfigTags => ({
  require: [],
  deny: [],
  accept: [],
  constrain: [],
  ...overrides,
});

// Mock functions
export const createMockFunctions = () => ({
  setSelectedBlueprint: jest.fn(),
  clearTags: jest.fn(),
  removeTag: jest.fn(),
  addTag: jest.fn(),
  fetchBlueprints: jest.fn(),
  setTagState: jest.fn(),
  setSearchTerm: jest.fn(),
  toggleNode: jest.fn(),
  addAllTags: jest.fn(),
  addDenyTag: jest.fn(),
  removeDenyTag: jest.fn(),
  setBlueprints: jest.fn(),
  fetchTagDescriptions: jest.fn(),
  fetchData: jest.fn(),
  setData: jest.fn(),
  setConfigSelection: jest.fn(),
  fetchBlueprintById: jest.fn(),
  fetchBlueprintByMd5: jest.fn(),
  clearConfigSelections: jest.fn(),
  setInitialSetupComplete: jest.fn(),
});

// Setup function for common test setup
export const setupTestEnvironment = () => {
  // Mock clipboard API
  Object.assign(navigator, {
    clipboard: mockClipboard,
  });

  // Clear all mocks
  jest.clearAllMocks();
  jest.useFakeTimers();
};

export const cleanupTestEnvironment = () => {
  jest.useRealTimers();
};

let originalLocationProps: { search?: string; pathname?: string } | undefined;

export function mockWindowLocation(props: Partial<Pick<Location, 'search' | 'pathname'>>) {
  if (!originalLocationProps) {
    originalLocationProps = {
      search: window.location.search,
      pathname: window.location.pathname,
    };
  }

  if (props.search !== undefined) window.location.search = props.search;
  if (props.pathname !== undefined) window.location.pathname = props.pathname;
}

export function restoreWindowLocation() {
  if (originalLocationProps) {
    if (originalLocationProps.search !== undefined) window.location.search = originalLocationProps.search;
    if (originalLocationProps.pathname !== undefined) window.location.pathname = originalLocationProps.pathname;
    originalLocationProps = undefined;
  }
}

export function mockHistoryReplaceState(fn = jest.fn()) {
  window.history.replaceState = fn;
  return fn;
}
