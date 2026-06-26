"use client";

// Runs synchronously when the browser parses the bundle —
// before React hydration, before any fetch is attempted.
if (typeof window !== "undefined") {
  const _orig = window.fetch.bind(window);

  function clean(str: string, label: string): string {
    let out = "";
    for (let i = 0; i < str.length; i++) {
      if (str.charCodeAt(i) > 255) {
        console.warn(
          `[FetchSanitizer] "${label}" pos ${i}: U+${str
            .charCodeAt(i)
            .toString(16)
            .toUpperCase()} removed`
        );
      } else {
        out += str[i];
      }
    }
    return out;
  }

  window.fetch = function (
    input: RequestInfo | URL,
    init?: RequestInit
  ): Promise<Response> {
    if (init?.headers) {
      let entries: [string, string][];
      if (Array.isArray(init.headers)) {
        entries = init.headers as [string, string][];
      } else if (init.headers instanceof Headers) {
        entries = Array.from((init.headers as Headers).entries());
      } else {
        entries = Object.entries(init.headers as Record<string, string>);
      }

      const sanitized: Record<string, string> = {};
      for (const [k, v] of entries) {
        sanitized[clean(k, "key")] = clean(String(v), `val[${k}]`);
      }
      init = { ...init, headers: sanitized };
    }
    return _orig(input, init);
  };
}

// Component is just a mount point so the module gets included in the bundle
export function FetchSanitizer() {
  return null;
}
