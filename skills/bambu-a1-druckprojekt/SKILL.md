---
name: "bambu-a1-druckprojekt"
description: "Use when designing or exporting a 3D print model (STL/3MF) for the Bambu Lab A1, e.g. signs, reliefs, boxes, QR codes or figures."
---
 
# Druckprojekt für Bambu Lab A1
 
Antworten kurz und auf Deutsch. Bei Unklarheit nachfragen statt raten.
 
## Drucker und Material
- Bambu Lab A1, offener Drucker, Bauraum **256 × 256 × 256 mm**. Teile grösser als ~250 mm teilen (mit Steckverbindung/Passstiften, Toleranz 0.2–0.3 mm).
- Standard: **PLA**, Düse 0.4 mm. PETG möglich (strukturierte PEI-Platte, trocknen, langsamer). Kein ABS/ASA/PC/Nylon.
- PLA verzieht sich ab ~55 °C, nicht spülmaschinenfest.
## Konstruktionsregeln
- Wandstärke min. 1.2 mm (3 Linien), Text/Linien min. 0.6–0.8 mm breit.
- Überhänge max. ~45°, sonst Stützen vermeiden durch Geometrie (Fasen, Teilung).
- Flache Unterseite aufs Bett, keine schwebenden Teile.
- Mesh muss wasserdicht (manifold) sein, vor Export prüfen (z.B. trimesh `is_watertight`).
- Einheiten in mm.
## Zweifarbig (ohne AMS)
- Basis (weiss) und Erhöhung (schwarz) als **getrennte STLs** plus **komplett_einfarbig.stl**.
- Farbwechsel per **Pause bei Z-Höhe**: die genaue Z-Höhe (Oberkante Basis, z.B. Z = 1.00) immer in der Antwort und ANLEITUNG nennen.
- Optional 3MF mit beiden Objekten als `_2farbig.3mf`.
- QR-Codes nach jedem Build mit einem Decoder prüfen (Render der Draufsicht scannen).
## Dateien und Ablage
- Ein Ordner pro Projekt (kebab-case), z.B. `twint-schild/`.
- Inhalt: STL(s)/3MF, `vorschau.png` (Render), `ANLEITUNG.md` (Masse, Material, Slicer-Einstellungen, Pausenhöhe, Zusammenbau).
- Dateinamen deutsch, snake_case, mit Variante: `name_v5_kaefig_platte_weiss.stl`.
- Versionen: neue Version nur, wenn verlangt. Sagt der Nutzer "überschreiben", bestehende Version ersetzen und überzählige löschen.
- Hinweis geben, wenn eine bestehende 3MF des Nutzers noch die alte Geometrie enthält.
## Abschluss
- Kurz melden: was geändert, Masse (B × H × T), Pausenhöhe, wo die Dateien liegen.