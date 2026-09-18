import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BlueprintProvider, useBlueprintContext } from '../blueprint-context';
import { Blueprint } from '@/types';
import '@testing-library/jest-dom';

import { createBlueprintStore } from '@/stores/blueprint-store';
import { useSearchParams } from 'next/navigation';

jest.mock('@/stores/blueprint-store', () => ({
  createBlueprintStore: jest.fn(),
}));
jest.mock('next/navigation', () => ({
  useSearchParams: jest.fn(),
}));

const mockCreateBlueprintStore = createBlueprintStore as jest.Mock;
const mockUseSearchParams = useSearchParams as jest.Mock;

// Test component to use the context
const TestComponent = () => {
  const selectedBlueprint = useBlueprintContext((state) => state.selectedBlueprint);
  const setSelectedBlueprint = useBlueprintContext((state) => state.setSelectedBlueprint);
  const fetchBlueprintById = useBlueprintContext((state) => state.fetchBlueprintById);
  const fetchBlueprintByMd5 = useBlueprintContext((state) => state.fetchBlueprintByMd5);
  const configSelections = useBlueprintContext((state) => state.configSelections);
  const setConfigSelection = useBlueprintContext((state) => state.setConfigSelection);
  const clearConfigSelections = useBlueprintContext((state) => state.clearConfigSelections);

  return (
    <div>
      <div data-testid="selected-blueprint">
        {selectedBlueprint ? selectedBlueprint.blueprint_name : 'No blueprint selected'}
      </div>
      <div data-testid="config-selections-count">
        {Object.keys(configSelections).length}
      </div>
      <button
        data-testid="set-blueprint"
        onClick={() => {
          const mockBlueprint: Blueprint = {
            id: 'test-id',
            blueprint_name: 'Test Blueprint',
            blueprint_type: 'blueprint',
            blueprint_config: {},
            file_md5: 'test-md5',
            file_size: 1000,
            file_name: 'test.stl',
            full_name: 'Test Blueprint Full Name',
            file_modified_at: '2023-01-01T00:00:00Z',
            storage_address: 'test-address',
            signed_url: 'test-url',
            created_at: '2023-01-01T00:00:00Z',
            updated_at: '2023-01-01T00:00:00Z',
            tags: ['test-tag'],
            images: [],
          };
          setSelectedBlueprint(mockBlueprint);
        }}
      >
        Set Blueprint
      </button>
      <button
        data-testid="fetch-by-id"
        onClick={() => fetchBlueprintById('test-id')}
      >
        Fetch by ID
      </button>
      <button
        data-testid="fetch-by-md5"
        onClick={() => fetchBlueprintByMd5('test-md5')}
      >
        Fetch by MD5
      </button>
      <button
        data-testid="set-config"
        onClick={() => {
          const mockBlueprint: Blueprint = {
            id: 'config-id',
            blueprint_name: 'Config Blueprint',
            blueprint_type: 'blueprint',
            blueprint_config: {},
            file_md5: 'config-md5',
            file_size: 1000,
            file_name: 'config.stl',
            full_name: 'Config Blueprint Full Name',
            file_modified_at: '2023-01-01T00:00:00Z',
            storage_address: 'config-address',
            signed_url: 'config-url',
            created_at: '2023-01-01T00:00:00Z',
            updated_at: '2023-01-01T00:00:00Z',
            tags: ['config-tag'],
            images: [],
          };
          setConfigSelection('test-part', mockBlueprint);
        }}
      >
        Set Config
      </button>
      <button
        data-testid="clear-configs"
        onClick={() => clearConfigSelections()}
      >
        Clear Configs
      </button>
    </div>
  );
};

describe('BlueprintContext', () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let mockStore: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let mockState: any;

  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    // Create mock state
    mockState = {
      selectedBlueprint: null,
      configSelections: {},
      setSelectedBlueprint: jest.fn(),
      fetchBlueprintById: jest.fn().mockResolvedValue(undefined),
      fetchBlueprintByMd5: jest.fn().mockResolvedValue(undefined),
      setConfigSelection: jest.fn(),
      clearConfigSelections: jest.fn(),
    };

    // Create mock store with Zustand API
    mockStore = {
      getState: jest.fn(() => mockState),
      subscribe: jest.fn(),
      setState: jest.fn(),
    };

    // Setup store mock
    mockCreateBlueprintStore.mockReturnValue(mockStore);

    // Setup search params mock
    mockUseSearchParams.mockReturnValue({
      get: jest.fn().mockReturnValue(null),
    });
  });

  describe('BlueprintProvider', () => {
    it('renders children without crashing', () => {
      render(
        <BlueprintProvider>
          <div data-testid="test-child">Test Child</div>
        </BlueprintProvider>
      );

      expect(screen.getByTestId('test-child')).toBeInTheDocument();
    });

    it('creates store only once', () => {
      render(
        <BlueprintProvider>
          <div>Test</div>
        </BlueprintProvider>
      );

      expect(mockCreateBlueprintStore).toHaveBeenCalledTimes(1);
    });

    it('does not autoload when autoload is false', () => {
      mockUseSearchParams.mockReturnValue({
        get: jest.fn().mockReturnValue('test-id'),
      });

      render(
        <BlueprintProvider autoload={false}>
          <div>Test</div>
        </BlueprintProvider>
      );

      expect(mockState.fetchBlueprintById).not.toHaveBeenCalled();
    });

    it('autoloads blueprint by ID when autoload is true and blueprint_id is present', async () => {
      const mockBlueprint: Blueprint = {
        id: 'test-id',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'blueprint',
        blueprint_config: {},
        file_md5: 'test-md5',
        file_size: 1000,
        file_name: 'test.stl',
        full_name: 'Test Blueprint Full Name',
        file_modified_at: '2023-01-01T00:00:00Z',
        storage_address: 'test-address',
        signed_url: 'test-url',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
        tags: ['test-tag'],
        images: [],
      };

      mockUseSearchParams.mockReturnValue({
        get: jest.fn((key) => key === 'blueprint_id' ? 'test-id' : null),
      });

      mockState.fetchBlueprintById.mockResolvedValue(mockBlueprint);

      render(
        <BlueprintProvider autoload={true}>
          <div>Test</div>
        </BlueprintProvider>
      );

      await waitFor(() => {
        expect(mockState.fetchBlueprintById).toHaveBeenCalledWith('test-id');
        expect(mockState.setSelectedBlueprint).toHaveBeenCalledWith(mockBlueprint);
      });
    });

    it('autoloads blueprint by MD5 when autoload is true and md5 is present', async () => {
      const mockBlueprint: Blueprint = {
        id: 'test-id',
        blueprint_name: 'Test Blueprint',
        blueprint_type: 'blueprint',
        blueprint_config: {},
        file_md5: 'test-md5',
        file_size: 1000,
        file_name: 'test.stl',
        full_name: 'Test Blueprint Full Name',
        file_modified_at: '2023-01-01T00:00:00Z',
        storage_address: 'test-address',
        signed_url: 'test-url',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
        tags: ['test-tag'],
        images: [],
      };

      mockUseSearchParams.mockReturnValue({
        get: jest.fn((key) => key === 'md5' ? 'test-md5' : null),
      });

      mockState.fetchBlueprintByMd5.mockResolvedValue(mockBlueprint);

      render(
        <BlueprintProvider autoload={true}>
          <div>Test</div>
        </BlueprintProvider>
      );

      await waitFor(() => {
        expect(mockState.fetchBlueprintByMd5).toHaveBeenCalledWith('test-md5');
        expect(mockState.setSelectedBlueprint).toHaveBeenCalledWith(mockBlueprint);
      });
    });

    it('handles fetch errors gracefully', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      mockUseSearchParams.mockReturnValue({
        get: jest.fn((key) => key === 'blueprint_id' ? 'test-id' : null),
      });

      mockState.fetchBlueprintById.mockRejectedValue(new Error('Fetch failed'));

      render(
        <BlueprintProvider autoload={true}>
          <div>Test</div>
        </BlueprintProvider>
      );

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to fetch initial blueprint:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });

    it('prioritizes blueprint_id over md5 when both are present', async () => {
      mockUseSearchParams.mockReturnValue({
        get: jest.fn((key) => {
          if (key === 'blueprint_id') return 'test-id';
          if (key === 'md5') return 'test-md5';
          return null;
        }),
      });

      render(
        <BlueprintProvider autoload={true}>
          <div>Test</div>
        </BlueprintProvider>
      );

      await waitFor(() => {
        expect(mockState.fetchBlueprintById).toHaveBeenCalledWith('test-id');
        expect(mockState.fetchBlueprintByMd5).not.toHaveBeenCalled();
      });
    });
  });

  describe('useBlueprintContext', () => {
    it('throws error when used outside provider', () => {
      // Suppress console.error for this test
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        render(<TestComponent />);
      }).toThrow('useBlueprintContext must be used within a BlueprintProvider');

      consoleSpy.mockRestore();
    });

    it('provides access to store state and methods when used within provider', () => {
      render(
        <BlueprintProvider>
          <TestComponent />
        </BlueprintProvider>
      );

      expect(screen.getByTestId('selected-blueprint')).toHaveTextContent('No blueprint selected');
      expect(screen.getByTestId('config-selections-count')).toHaveTextContent('0');
    });

    it('allows setting selected blueprint', () => {
      render(
        <BlueprintProvider>
          <TestComponent />
        </BlueprintProvider>
      );

      screen.getByTestId('set-blueprint').click();

      expect(mockState.setSelectedBlueprint).toHaveBeenCalledWith(expect.objectContaining({
        id: 'test-id',
        blueprint_name: 'Test Blueprint',
      }));
    });

    it('allows fetching blueprint by ID', () => {
      render(
        <BlueprintProvider>
          <TestComponent />
        </BlueprintProvider>
      );

      screen.getByTestId('fetch-by-id').click();

      expect(mockState.fetchBlueprintById).toHaveBeenCalledWith('test-id');
    });

    it('allows fetching blueprint by MD5', () => {
      render(
        <BlueprintProvider>
          <TestComponent />
        </BlueprintProvider>
      );

      screen.getByTestId('fetch-by-md5').click();

      expect(mockState.fetchBlueprintByMd5).toHaveBeenCalledWith('test-md5');
    });

    it('allows setting config selection', () => {
      render(
        <BlueprintProvider>
          <TestComponent />
        </BlueprintProvider>
      );

      screen.getByTestId('set-config').click();

      expect(mockState.setConfigSelection).toHaveBeenCalledWith('test-part', expect.objectContaining({
        id: 'config-id',
        blueprint_name: 'Config Blueprint',
      }));
    });

    it('allows clearing config selections', () => {
      render(
        <BlueprintProvider>
          <TestComponent />
        </BlueprintProvider>
      );

      screen.getByTestId('clear-configs').click();

      expect(mockState.clearConfigSelections).toHaveBeenCalled();
    });
  });
});
