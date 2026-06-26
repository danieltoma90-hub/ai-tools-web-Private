"use client";
import { useEffect } from "react";

export function FetchSanitizer() {
  useEffect(() => {
    const orig = window.fetch.bind(window);

    window.fetch = function (
      input: RequestInfo | URL,
      init?: RequestInit
    ): Promise<Response> {
      if (init?.headers) {
        let entries: [string, string][];

        if (init.headers instanceof Headers) {
          entries = Array.from((init.headers as Headers).entries());
        } else {
          entries = Object.entries(init.headers as Record<string, string>);
        }

        let dirty = false;
        const cleaned: Record<string, string> = {};

        for (const [key, val] of entries) {
          const str = String(val);
          let clean = "";
          for (let i = 0; i < str.length; i++) {
            if (str.charCodeAt(i) > 255) {
              console.warn(
                `[FetchSanitizer] Header "${key}" la poz ${i}: U+${str
                  .charCodeAt(i)
                  .toString(16)
                  .toUpperCase()} eliminat`
              );
              dirty = true;
            } else {
              clean += str[i];
            }
          }
          cleaned[key] = clean;
        }

        if (dirty) init = { ...init, headers: cleaned };
      }

      return orig(input, init);
    };

    return () => {
      window.fetch = orig;
    };
  }, []);

  return null;
}
