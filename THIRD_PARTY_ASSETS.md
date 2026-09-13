# Interface asset provenance

The current browser interface uses an original first-person desk scene in
`frontend/src/components/DeskScene.tsx`, `DeskMonitor.tsx`, and `DeskKeyboard.tsx`,
with local camera and screen-projection code. Its procedural geometry depicts
a curved ultrawide monitor, wooden desk, ivory and sage mechanical keyboard,
mouse, coffee, plants, and lamp from a seated viewpoint. No human or chair is
visible. The static SVG fallback and neutral SVG monitor mark are also authored
in the project. Locations and provenance are recorded in `assets/manifest.json`.

The visual refinements in `DeskAccessories.tsx`, `DeskPlants.tsx`, and
`DeskAtmosphere.tsx` use original procedural geometry and deterministic,
in-memory surface, contact-shadow, and studio-reflection textures. No model,
HDR image, texture pack, or additional font was downloaded for these changes.
The user's workspace reference guided the palette and material treatment.
[Questopia](https://github.com/GlintonLiao/questopia) was consulted as a visual
quality benchmark only; its code, models, textures, layout, and camera controls
are not incorporated.

User-supplied Samsung Odyssey G8 photographs served as a visual reference for
the monitor's proportions and curved silhouette. The implementation contains
no copied photograph, promotional image, Samsung logo, or branded product
asset, and implies no affiliation with or endorsement by Samsung.

The keyboard's visual references were
[Developer-Square/Threejs-Keyboard](https://github.com/Developer-Square/Threejs-Keyboard)
and [Keyboard Simulator](https://keyboardsimulator.xyz/). The reference
repository was inspected and identifies its code as MIT licensed. The shipped
keyboard geometry, materials, and SVG artwork are newly authored; no code or
assets from these references are incorporated, so no reference license is
bundled as an asset license.

The internal browser UI bundles Latin-subset variable fonts Inter (body/UI,
400–700) and Manrope (headings, 600–700), obtained from Google Fonts on
2026-09-11. They are served locally from `frontend/public/fonts/`; the app does
not contact Google Fonts at runtime. Both are distributed under the SIL Open
Font License 1.1, retained as `OFL-Inter.txt` and `OFL-Manrope.txt` alongside the
fonts. Sources: https://fonts.google.com/specimen/Inter and
https://fonts.google.com/specimen/Manrope. The landing retains its system font
stack, also used as fallback for glyphs outside the bundled subsets. Third-party
software dependencies, including Three.js and React, retain their own licenses
and notices. This asset inventory does not replace or relicense those notices.

The internal editorial headers also bundle the Latin subset of Caveat
(400–500), obtained from Google Fonts on 2026-09-12. The font and its SIL Open
Font License 1.1 are stored in `frontend/public/fonts/caveat-latin.woff2` and
`OFL-Caveat.txt`. Source: https://fonts.google.com/specimen/Caveat; upstream
license: https://github.com/google/fonts/blob/main/ofl/caveat/OFL.txt. Like the
other UI fonts, it is served locally without runtime third-party requests.
The search illustration is original CSS and existing project SVG icon geometry
in `SearchArtwork.tsx`; organic background shapes are CSS, not external images.

The repository license is recorded in `LICENSE`. Provenance here describes how
the replacement visuals were produced; it is not a trademark clearance or a
claim of rights over any third-party material.
