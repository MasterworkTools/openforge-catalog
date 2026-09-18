import { renderHook } from '@testing-library/react';
import { useBlueprintUrlCleanup } from '../use-blueprint-url-cleanup';
import { createMockBlueprint } from '@/test-utils';

// Mock URLSearchParams
const mockGet = jest.fn();
const mockGetAll = jest.fn();
const mockDelete = jest.fn();
const mockSet = jest.fn();
const mockHas = jest.fn();
const mockToString = jest.fn();

const mockURLSearchParams = jest.fn(() => ({
  get: mockGet,
  getAll: mockGetAll,
  delete: mockDelete,
  set: mockSet,
  has: mockHas,
  toString: mockToString,
}));

// Mock window.addEventListener and window.removeEventListener
const mockAddEventListener = jest.fn();
const mockRemoveEventListener = jest.fn();

// Mock location and history objects
const mockLocation: Partial<Location> = {
  search: '',
  pathname: '/',
  reload: jest.fn(),
};

const mockHistory: Partial<History> = {
  replaceState: jest.fn(),
};

// Mock URLSearchParams globally
global.URLSearchParams = mockURLSearchParams as unknown as typeof URLSearchParams;

describe('useBlueprintUrlCleanup', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockReturnValue(null);
    mockGetAll.mockReturnValue([]);
    mockToString.mockReturnValue('');
    mockHas.mockReturnValue(false);

    // Mock window methods
    window.addEventListener = mockAddEventListener;
    window.removeEventListener = mockRemoveEventListener;
  });

  it('adds popstate event listener when blueprint is provided', () => {
    const blueprint = createMockBlueprint({ id: '123' });
    renderHook(() => useBlueprintUrlCleanup(blueprint, mockLocation as Location, mockHistory as History));
    expect(mockAddEventListener).toHaveBeenCalledWith('popstate', expect.any(Function));
  });

  it('adds popstate event listener when blueprint is null', () => {
    renderHook(() => useBlueprintUrlCleanup(null, mockLocation as Location, mockHistory as History));
    expect(mockAddEventListener).toHaveBeenCalledWith('popstate', expect.any(Function));
  });

  it('removes popstate event listener on cleanup', () => {
    const blueprint = createMockBlueprint({ id: '123' });
    const { unmount } = renderHook(() => useBlueprintUrlCleanup(blueprint, mockLocation as Location, mockHistory as History));
    unmount();
    expect(mockRemoveEventListener).toHaveBeenCalledWith('popstate', expect.any(Function));
  });

  it('calls useEffect when blueprint changes', () => {
    const blueprint1 = createMockBlueprint({ id: '123' });
    const blueprint2 = createMockBlueprint({ id: '456' });
    const { rerender } = renderHook(({ blueprint }) => useBlueprintUrlCleanup(blueprint, mockLocation as Location, mockHistory as History), {
      initialProps: { blueprint: blueprint1 }
    });
    jest.clearAllMocks();
    rerender({ blueprint: blueprint2 });
    expect(mockAddEventListener).toHaveBeenCalledWith('popstate', expect.any(Function));
  });

  describe('URL cleanup logic', () => {
    it('removes blueprint_id from URL when blueprint is provided and URL contains blueprint_id', () => {
      const blueprint = createMockBlueprint({ id: '123' });
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '?blueprint_id=123&other=param', pathname: '/test' };
      mockHas.mockReturnValue(true);
      mockToString.mockReturnValue('other=param');

      renderHook(() => useBlueprintUrlCleanup(blueprint, locationWithParams as Location, mockHistory as History));

      expect(mockHas).toHaveBeenCalledWith('blueprint_id');
      expect(mockDelete).toHaveBeenCalledWith('blueprint_id');
      expect(mockHistory.replaceState).toHaveBeenCalledWith({}, '', '/test?other=param');
    });

    it('removes blueprint_id from URL when blueprint is provided and URL only contains blueprint_id', () => {
      const blueprint = createMockBlueprint({ id: '123' });
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '?blueprint_id=123', pathname: '/test' };
      mockHas.mockReturnValue(true);
      mockToString.mockReturnValue('');

      renderHook(() => useBlueprintUrlCleanup(blueprint, locationWithParams as Location, mockHistory as History));

      expect(mockHas).toHaveBeenCalledWith('blueprint_id');
      expect(mockDelete).toHaveBeenCalledWith('blueprint_id');
      expect(mockHistory.replaceState).toHaveBeenCalledWith({}, '', '/test');
    });

    it('does not modify URL when blueprint is provided but URL does not contain blueprint_id', () => {
      const blueprint = createMockBlueprint({ id: '123' });
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '?other=param', pathname: '/test' };
      mockHas.mockReturnValue(false);

      renderHook(() => useBlueprintUrlCleanup(blueprint, locationWithParams as Location, mockHistory as History));

      expect(mockHas).toHaveBeenCalledWith('blueprint_id');
      expect(mockDelete).not.toHaveBeenCalled();
      expect(mockHistory.replaceState).not.toHaveBeenCalled();
    });

    it('does not modify URL when blueprint is null', () => {
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '?blueprint_id=123&other=param', pathname: '/test' };
      mockHas.mockReturnValue(true);

      renderHook(() => useBlueprintUrlCleanup(null, locationWithParams as Location, mockHistory as History));

      expect(mockHas).not.toHaveBeenCalled();
      expect(mockDelete).not.toHaveBeenCalled();
      expect(mockHistory.replaceState).not.toHaveBeenCalled();
    });
  });

  describe('popstate event handling', () => {
    it('reloads page when popstate occurs and no blueprint_id in URL but blueprint is provided', () => {
      const blueprint = createMockBlueprint({ id: '123' });
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '', pathname: '/' };
      mockGet.mockReturnValue(null);

      renderHook(() => useBlueprintUrlCleanup(blueprint, locationWithParams as Location, mockHistory as History));
      const popstateHandler = mockAddEventListener.mock.calls[0][1];
      popstateHandler();

      expect(mockGet).toHaveBeenCalledWith('blueprint_id');
      expect(locationWithParams.reload).toHaveBeenCalled();
    });

    it('does not reload page when popstate occurs and blueprint_id is in URL', () => {
      const blueprint = createMockBlueprint({ id: '123' });
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '?blueprint_id=123', pathname: '/' };
      mockGet.mockReturnValue('123');

      renderHook(() => useBlueprintUrlCleanup(blueprint, locationWithParams as Location, mockHistory as History));
      const popstateHandler = mockAddEventListener.mock.calls[0][1];
      popstateHandler();

      expect(mockGet).toHaveBeenCalledWith('blueprint_id');
      expect(locationWithParams.reload).not.toHaveBeenCalled();
    });

    it('does not reload page when popstate occurs and no blueprint is provided', () => {
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '', pathname: '/' };
      mockGet.mockReturnValue(null);

      renderHook(() => useBlueprintUrlCleanup(null, locationWithParams as Location, mockHistory as History));
      const popstateHandler = mockAddEventListener.mock.calls[0][1];
      popstateHandler();

      expect(mockGet).toHaveBeenCalledWith('blueprint_id');
      expect(locationWithParams.reload).not.toHaveBeenCalled();
    });

    it('does not reload page when popstate occurs and blueprint_id is in URL but blueprint is null', () => {
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '?blueprint_id=123', pathname: '/' };
      mockGet.mockReturnValue('123');

      renderHook(() => useBlueprintUrlCleanup(null, locationWithParams as Location, mockHistory as History));
      const popstateHandler = mockAddEventListener.mock.calls[0][1];
      popstateHandler();

      expect(mockGet).toHaveBeenCalledWith('blueprint_id');
      expect(locationWithParams.reload).not.toHaveBeenCalled();
    });
  });

  describe('edge cases', () => {
    it('handles URL with multiple blueprint_id parameters', () => {
      const blueprint = createMockBlueprint({ id: '123' });
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '?blueprint_id=123&blueprint_id=456&other=param', pathname: '/test' };
      mockHas.mockReturnValue(true);
      mockToString.mockReturnValue('other=param');

      renderHook(() => useBlueprintUrlCleanup(blueprint, locationWithParams as Location, mockHistory as History));

      expect(mockHas).toHaveBeenCalledWith('blueprint_id');
      expect(mockDelete).toHaveBeenCalledWith('blueprint_id');
      expect(mockHistory.replaceState).toHaveBeenCalledWith({}, '', '/test?other=param');
    });

    it('handles URL with empty blueprint_id parameter', () => {
      const blueprint = createMockBlueprint({ id: '123' });
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '?blueprint_id=&other=param', pathname: '/test' };
      mockHas.mockReturnValue(true);
      mockToString.mockReturnValue('other=param');

      renderHook(() => useBlueprintUrlCleanup(blueprint, locationWithParams as Location, mockHistory as History));

      expect(mockHas).toHaveBeenCalledWith('blueprint_id');
      expect(mockDelete).toHaveBeenCalledWith('blueprint_id');
      expect(mockHistory.replaceState).toHaveBeenCalledWith({}, '', '/test?other=param');
    });

    it('handles complex URL with multiple parameters', () => {
      const blueprint = createMockBlueprint({ id: '123' });
      const locationWithParams: Partial<Location> = { ...mockLocation, search: '?param1=value1&blueprint_id=123&param2=value2&param3=value3', pathname: '/complex/path' };
      mockHas.mockReturnValue(true);
      mockToString.mockReturnValue('param1=value1&param2=value2&param3=value3');

      renderHook(() => useBlueprintUrlCleanup(blueprint, locationWithParams as Location, mockHistory as History));

      expect(mockHas).toHaveBeenCalledWith('blueprint_id');
      expect(mockDelete).toHaveBeenCalledWith('blueprint_id');
      expect(mockHistory.replaceState).toHaveBeenCalledWith({}, '', '/complex/path?param1=value1&param2=value2&param3=value3');
    });
  });
});
