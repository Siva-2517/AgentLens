import '@testing-library/jest-dom/vitest';

// Mock ResizeObserver for React Flow in jsdom
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

window.ResizeObserver = window.ResizeObserver || MockResizeObserver;

// Mock DOMMatrixReadOnly for React Flow
if (typeof window.DOMMatrixReadOnly === 'undefined') {
  // @ts-expect-error Mock DOMMatrixReadOnly
  window.DOMMatrixReadOnly = class {
    m22 = 1;
  };
}
