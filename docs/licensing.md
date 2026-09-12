# 3D asset licensing and publication gate

[Español](licensing.es.md) · Last reviewed: 2026-08-29

This is an engineering compliance checklist, not legal advice. The exact terms
accepted when each file was acquired control.

## Two independent distributions

1. Adding FBX/GLB to a public GitHub repository lets visitors copy and fork it.
   GitHub requires the publisher to have rights that permit those operations
   ([GitHub Terms §§5–6](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service?apiVersion=2022-11-28)).
2. An interactive web viewer sends the GLB bytes to the browser. Hosting it on a
   CDN, using Git LFS, base64, signed URLs, compression, conversion, or
   JavaScript obfuscation does not turn delivery into a mere rendered image.

Non-monetization does not cure a no-redistribution clause. “Free” and
“royalty-free” describe price/royalty, not permission to redistribute source
files. The repository's Apache-2.0 license covers code only and must never be
presented as relicensing third-party assets.

## Common license outcomes

| License | Public repo + browser GLB | Conditions |
| --- | --- | --- |
| [CC0](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en) | Usually yes | Verify provenance and separate trademark/likeness rights; attribution is still good practice |
| [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Yes | Credit, license/source link, notices, and modification indication; preserve downstream freedoms |
| CC BY-SA 4.0 | Yes | Distribute modifications to the model under the same license; mark code and asset scopes separately |
| CC BY-NC 4.0 | Only genuinely noncommercial | Poor fit for reusable public software; downstream commercial use remains prohibited |
| [CC BY-ND 4.0](https://creativecommons.org/licenses/by-nd/4.0/) | Only unadapted material | Do not publish artistic/rig/animation modifications; technical conversion requires careful review |
| Editorial | Normally no | Only the licensed news/commentary context, not decoration or promotion |
| Marketplace standard/royalty-free | Normally no raw file | Often permits renders or an incorporated end product only, with anti-extraction duties |
| No license or unknown source | No | Copyright permission is absent; a download button is not a license |

For CC attribution, record Title, Author, Source, and License plus modifications
as recommended by [Creative Commons](https://creativecommons.org/reusing-cc-licensed-content/).
CC does not automatically clear trademarks, publicity/privacy rights, moral
rights, or third-party franchise content.

Examples of restrictive stock terms:

- [Sketchfab Standard](https://sketchfab.com/licenses) forbids making licensed
  material available so others can download, extract, or access it standalone.
- [CGTrader Royalty Free](https://help.cgtrader.com/hc/en-us/articles/360015124437-Royalty-Free-License)
  requires an incorporated product from which a third party cannot retrieve the
  model.
- [Unity Asset Store](https://assetstore.unity.com/ko-KR/browse/eula-faq) permits
  distribution only when an asset is incorporated into a substantial product
  not designed to allow extraction.
- [Fab Standard](https://www.fab.com/eula?lang=en) allows incorporated projects,
  not free or paid standalone redistribution.
- [TurboSquid](https://www.turbosquid.com/licensing) has specific WebGL
  protection/transformation conditions that an ordinary public GLB does not
  satisfy automatically.
- Adobe permits Mixamo content in creative projects, but its
  [general Content Files terms](https://www.adobe.com/legal/terms.html) prohibit
  standalone distribution. Animations must be reviewed separately from the
  character mesh.

## Evidence recorded per model

Each delivered 3D slot records:

1. author/rightsholder and original source URL;
2. exact license name/version, stable text/permalink, and retrieval date;
3. receipt or other proof tied to the correct person/entity and seat plan;
4. required attribution and notices;
5. explicit permission to modify;
6. explicit permission to redistribute a browser-downloadable GLB and public
   GitHub copies/forks;
7. provenance/license for mesh, textures, materials, rig, and every animation;
8. conversion and modification log from source to delivery file;
9. trademark, fictional-character, voice, and likeness review;
10. file checksum and reviewer/date/decision.

An uploader cannot license a model ripped from a game or another creator. A CC
badge does not repair missing ownership. Ambiguity means the model falls back
to the neutral procedural avatar.

## Gate procedure

The current [`assets/manifest.json`](../assets/manifest.json) and schema allow
exactly one GLB: user-supplied, byte-verified **Smol Ame in an Upcycled
Terrarium** by Seafoam under CC BY 4.0. It is
`included_local_noncommercial` and `publishable: true` with required
attribution. The validator checks path, size, SHA-256, evidence, animation, and
fallback declarations.

The manifest also records `UKLELESONG.mp3` and `ame.png`, both supplied by the
project owner with explicit authorization for inclusion and redistribution in
AmeWork. Their checksum, size, original filename, and license boundary remain
separate from the source code. Audio is optional and playback failure never
blocks the application.

For a replacement or future asset:

- preserve the evidence outside Git if it contains account or payment data;
- add a public redacted license record and attribution;
- map every delivered file to that record and checksum;
- ensure the repository license explicitly excludes it or records its compatible
  open license;
- validate web delivery, not only local authoring/render rights;
- run security, performance, accessibility, and license checks in review.

Until all checks pass, use the static fallback. Never replace first and
“verify later”: forks and caches make recall unreliable.

## Render-only strategy

If a license permits use/renders but not source redistribution:

- keep the source outside the public repository and provide a neutral CC0
  placeholder plus a user-supplied local path;
- publish server-rendered images/video/sprite sheets if the license permits
  those outputs;
- use an official provider embed when its terms and the individual model permit
  embedding; or
- replace the model or obtain a written license that explicitly covers public
  WebGL and repository redistribution.

A private build store does not solve a public interactive viewer: the browser
still receives the model. Encryption or format conversion is not a substitute
for permission.
