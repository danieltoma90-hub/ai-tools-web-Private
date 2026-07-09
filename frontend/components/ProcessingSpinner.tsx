"use client";
import { useEffect, useState } from "react";

export default function ProcessingSpinner({ label }: { label?: string } = {}) {
  const [showColdStart, setShowColdStart] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setShowColdStart(true), 5000);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="w-10 h-10 border-4 border-[#c7ccf0] border-t-[#18257f] rounded-full animate-spin" />
      <p className="text-sm text-slate-600">{label ?? "Se generează documentul..."}</p>
      {showColdStart && (
        <p className="text-xs text-slate-400 text-center max-w-xs">
          Se pornește serverul, poate dura 10-15 secunde la prima utilizare din
          zi.
        </p>
      )}
    </div>
  );
}
