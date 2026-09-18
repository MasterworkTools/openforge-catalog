import { devLog } from '../log';

describe('devLog', () => {
  const originalEnv = process.env.NODE_ENV;
  const originalLog = console.log;
  let mockLog: jest.MockedFunction<typeof console.log>;

  beforeEach(() => {
    jest.resetModules();
    mockLog = jest.fn();
    console.log = mockLog;
  });

  afterEach(() => {
    Object.defineProperty(process.env, 'NODE_ENV', { value: originalEnv });
    console.log = originalLog;
  });

  it('logs when NODE_ENV is development', () => {
    Object.defineProperty(process.env, 'NODE_ENV', { value: 'development' });
    devLog('hello', 123);
    expect(console.log).toHaveBeenCalledWith('hello', 123);
  });

  it('does not log when NODE_ENV is not development', () => {
    Object.defineProperty(process.env, 'NODE_ENV', { value: 'production' });
    devLog('should not log');
    expect(console.log).not.toHaveBeenCalled();
  });
});
