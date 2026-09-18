// Global test setup (add custom setup here if needed)

// Suppress console errors and warnings during tests
const originalError = console.error;
const originalWarn = console.warn;

beforeAll(() => {
  console.error = (...args: Parameters<typeof console.error>) => {
    // Only suppress React act() warnings, not intentional error logging
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: An update to') &&
      args[0].includes('inside a test was not wrapped in act(...)')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };

  console.warn = (...args: Parameters<typeof console.warn>) => {
    // Suppress common React warnings
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('Warning: ReactDOM.render is no longer supported') ||
       args[0].includes('Warning: componentWillReceiveProps') ||
       args[0].includes('Warning: componentWillUpdate'))
    ) {
      return;
    }
    originalWarn.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
  console.warn = originalWarn;
});
