"use client";
import { useEffect, useState } from "react";
import { getAccesEu, type AccesEu } from "@/lib/api";

/** Modulele site-ului, cu eticheta din meniu (aceleași chei ca în backend/acces.py). */
export const MODULE_ETICHETE: Record<string, string> = {
  minuta: "Minută",
  mockup: "Mockup",
  scenarii: "Scenarii",
  "scop-core": "Scop CORE",
  training: "Training",
};

/** Ruta paginii → modulul de care ține; paginile care nu sunt aici sunt comune tuturor. */
export const MODUL_RUTA: Record<string, string> = {
  "/minuta": "minuta",
  "/mockup": "mockup",
  "/scenarii": "scenarii",
  "/scop-core": "scop-core",
  "/training": "training",
};

/** Folderul documentelor → modulul (contextele de proiect țin de Minută). */
export const MODUL_TOOL: Record<string, string> = {
  minuta: "minuta",
  context: "minuta",
  mockup: "mockup",
  scenarii: "scenarii",
  "scop-core": "scop-core",
  training: "training",
};

let promisiune: Promise<AccesEu> | null = null;

/** Accesul utilizatorului curent: o singură cerere pe încărcarea paginii, împărțită de toate componentele. */
export function incarcaAcces(fortat = false): Promise<AccesEu> {
  if (!promisiune || fortat) {
    promisiune = getAccesEu().catch((e) => {
      promisiune = null;
      throw e;
    });
  }
  return promisiune;
}

export function useAcces(): { acces: AccesEu | null; eroare: string } {
  const [acces, setAcces] = useState<AccesEu | null>(null);
  const [eroare, setEroare] = useState("");
  useEffect(() => {
    let viu = true;
    incarcaAcces()
      .then((a) => {
        if (viu) setAcces(a);
      })
      .catch((e) => {
        if (viu) setEroare(e instanceof Error ? e.message : "Accesul nu a putut fi verificat");
      });
    return () => {
      viu = false;
    };
  }, []);
  return { acces, eroare };
}

/** True dacă pagina/modulul poate fi folosit. Fără modul = pagină comună. */
export function poateFolosi(acces: AccesEu | null, modul: string | undefined): boolean {
  return !modul || (acces?.module.includes(modul) ?? false);
}
