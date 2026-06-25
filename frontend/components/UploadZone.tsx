"use client";
import { useRef, useState } from "react";

type Props = {
  accept: string;
  label: string;
  onFile: (file: File) => void;
};

export default function UploadZone({ accept, label, onFile }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  function handle(file: File) {
    setSelected(file.name);
    onFile(file);
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files[0];
        if (f) handle(f);
      }}
      onClick={() => inputRef.current?.click()}
      className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
        dragOver
          ? "border-blue-400 bg-blue-50"
          : "border-slate-300 hover:border-blue-300 hover:bg-slate-50"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handle(f);
        }}
      />
      <p className="text-2xl mb-2">⬆️</p>
      {selected ? (
        <p className="text-sm font-medium text-blue-700">{selected}</p>
      ) : (
        <>
          <p className="text-sm text-slate-600">Trage {label} aici</p>
          <p className="text-xs text-slate-400 mt-1">
            sau{" "}
            <span className="text-blue-600 font-medium">
              caută pe calculator
            </span>
          </p>
        </>
      )}
    </div>
  );
}
