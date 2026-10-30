// Polyfill browser APIs missing in JSDOM / headless test runners (Vitest)
function ensureBrowserGlobals() {
  if (typeof window !== 'undefined') {
    if (typeof window.matchMedia !== 'function') {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: (query) => ({
          matches: false,
          media: query,
          onchange: null,
          addListener: () => {},
          removeListener: () => {},
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
        }),
      })
    }

    if (typeof window.IntersectionObserver === 'undefined') {
      class MockIntersectionObserver {
        constructor(callback) {
          this.callback = callback
        }
        observe() {}
        unobserve() {}
        disconnect() {}
      }
      Object.defineProperty(window, 'IntersectionObserver', {
        writable: true,
        configurable: true,
        value: MockIntersectionObserver,
      })
      Object.defineProperty(globalThis, 'IntersectionObserver', {
        writable: true,
        configurable: true,
        value: MockIntersectionObserver,
      })
    }

    if (typeof window.ResizeObserver === 'undefined') {
      class MockResizeObserver {
        constructor(callback) {
          this.callback = callback
        }
        observe() {}
        unobserve() {}
        disconnect() {}
      }
      Object.defineProperty(window, 'ResizeObserver', {
        writable: true,
        configurable: true,
        value: MockResizeObserver,
      })
      Object.defineProperty(globalThis, 'ResizeObserver', {
        writable: true,
        configurable: true,
        value: MockResizeObserver,
      })
    }

    if (typeof HTMLCanvasElement !== 'undefined') {
      const isJsdom = typeof navigator !== 'undefined' && navigator.userAgent?.includes('jsdom')
      if (isJsdom) {
        HTMLCanvasElement.prototype.getContext = () => null
      }
    }
  }
}

ensureBrowserGlobals()

export default ensureBrowserGlobals
