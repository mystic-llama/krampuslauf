# Classic Client menu measurements

Inspected November 1, 2026. Game content is 640 x 480; the observed window includes a title bar and border. Coordinates below are measured inside the game content, not from the desktop or window origin. These are visual centre estimates; no game input was sent and no user overrides were changed.

| Control | x | y |
|---|---:|---:|
| Character name field | 355 | 80 |
| Human | 237 | 444 |
| Elf | 237 | 464 |
| Gargoyle | 128 | 444 |
| Male | 481 | 444 |
| Female | 481 | 464 |
| Hair style dropdown arrow | 208 | 165 |
| Facial hair dropdown arrow | 208 | 212 |
| Skin tone swatch | 551 | 166 |
| Next arrow | 620 | 445 |

Existing built-in points fall within these visible controls. No replacements are needed from this inspection. Hair and facial-hair rows were subsequently measured from the supplied open-menu screenshots; skin palette corners were subsequently measured below. Login was subsequently checked from the supplied screenshot; see below. The later sections record subsequent inspections of the other menu screens.

Display scaling remains handled by client_geometry.py. Logical positions are transformed from the game-area origin using the detected scale: 1.25 at 125% or 1.5 at 150%. Those settings were not changed or physically tested during this inspection.

## Profession and world selection

Both screens were visually inspected in the same 640 x 480 content area. No game clicks were sent.

| Screen / control | Measured content centre (x, y), approximate | Built-in point | Result |
|---|---|---|---|
| Profession: Blacksmith preset | (294, 394) | (294, 393) | Inside preset icon |
| Profession: Next arrow | (619, 445) | (622, 444) | Inside arrow |
| World: Moonglow map marker | (402, 166) | (402, 165) | Inside marker |
| World: Next arrow | (619, 445) | (622, 444) | Inside arrow |

World selection was showing New Haven as the selected city. This verifies the visible Moonglow click target, but does not yet verify recognition after selecting Moonglow. Character Select and Shards were subsequently inspected below.

## Character Select and Shards

Visually inspected after the user navigated to each screen. All coordinates use the 640 x 480 game-content origin. The game window observed was 642 x 512 including its border and title bar; those decorations are excluded from these coordinates.

| Screen / control | Built-in content point | Visual result |
|---|---|---|
| Character slot 1 | (477, 139) | Inside first character row |
| Character slot 2 | (477, 179) | Inside second character row |
| Character row spacing | 40 pixels | Matches successive visible rows |
| New character | (252, 405) | Inside New button |
| Back | (592, 444) | Inside bottom-left-facing arrow |
| Shards first row | (377, 114) | Inside Legends row with list at top |
| Shard row spacing | 25 pixels | Matches Legends, Atlantic, Lake Superior and subsequent rows |
| Scroll up | (537, 99) | Inside top scrollbar arrow area |
| Scroll down | (537, 354) | Inside bottom scrollbar arrow area, near lower edge |

No built-in coordinates or user calibration were changed: the existing points are inside the observed target areas. These are visual bounds checks, not click-execution tests. Marker matching, selected-Moonglow recognition and physical behavior at 125%/150% Windows scaling remain untested in this pass. Human hair and facial-hair lists were subsequently checked below; elf/gargoyle dropdown alignment remains to be inspected; skin palettes were subsequently mapped below.

## Login screenshot

Verified from the user-supplied 641 x 512 screenshot. The game artwork begins below the title bar at approximately screenshot y=31 and occupies the standard 640 x 480 content area.

The Login button below Password occupies approximately screenshot x=283..366, y=395..423. Its centre is approximately (325, 409), or (325, 378) in game-content coordinates. The existing built-in login_button point (325, 381) is comfortably inside the button, so no coordinate change is necessary. No credential input or login action was performed.

## Shard screen: complete dimensions and targets

Expanded from the supplied shard-screen screenshot on November 1, 2026. The attached image is approximately 646 x 512 pixels including window decorations. The game artwork is the standard **640 x 480** area, starting at approximately screenshot **(5, 31)**. All coordinates below are **inside that game area**, with (0, 0) at the artwork's top-left. They must never be applied relative to the outer window or directly as desktop positions.

Bounds are approximate visual measurements, expressed as (left, top, right, bottom); widths and heights are right-minus-left and bottom-minus-top. Row bounds describe conservative clickable strips, not a measured native UI hitbox. The existing points are retained where they already fall inside the control.

| Region / control | Approximate bounds | Width x height | Target (x, y) |
|---|---|---|---|
| Complete game menu | (0, 0, 640, 480) | 640 x 480 | ? |
| Shard list including frame | (151, 92, 526, 359) | 375 x 267 | ? |
| Scrollbar UP button | (528, 93, 544, 113) | 16 x 20 | **(537, 99)** existing |
| Scrollbar DOWN button | (528, 340, 544, 359) | 16 x 19 | **(537, 354)** existing |
| Last-shard globe / Earth | (150, 393, 230, 473) | 80 x 80 | **(190, 433)** approximate centre |
| Bottom right, left-facing red Back arrow | (583, 434, 607, 457) | 24 x 23 | **(594, 445)** approximate centre |
| Bottom right, right-facing Next arrow | (607, 434, 631, 457) | 24 x 23 | **(619, 445)** approximate centre |

### All nine visible shard rows

The app uses **x=377**, first-row **y=114**, and **25-pixel vertical spacing**. It calculates the other eight points rather than storing nine unrelated coordinates. These target strips intentionally stop before the scrollbar.

| Visible row | Shard shown in this screenshot | Approximate target strip | Target (x, y) |
|---|---|---|---|
| 1 | Legends | (175, 102, 510, 126) | **(377, 114)** |
| 2 | Atlantic | (175, 127, 510, 151) | **(377, 139)** |
| 3 | Lake Superior | (175, 152, 510, 176) | **(377, 164)** |
| 4 | Great Lakes | (175, 177, 510, 201) | **(377, 189)** |
| 5 | Chesapeake | (175, 202, 510, 226) | **(377, 214)** |
| 6 | Catskills | (175, 227, 510, 251) | **(377, 239)** |
| 7 | Siege Perilous | (175, 252, 510, 276) | **(377, 264)** |
| 8 | Origin | (175, 277, 510, 301) | **(377, 289)** |
| 9 | Pacific | (175, 302, 510, 326) | **(377, 314)** |

Each documented target strip is approximately **335 x 24 pixels**. Names belong to the current visible ordering, not permanent row assignments. The partial text below Pacific is not treated as a tenth selectable row by the app. For later shards, the app scrolls down and reuses visible row 9.

### Which controls the app uses

- **Normal shard selection:** clicks the calculated row point and waits for a recognized result. It does not append Enter or a Next click after a successful transition.
- **Fast Return:** `select_last_shard_shortcut` in cycler_engine.py already uses **Enter**. It is enabled only for an eligible previously verified shard and checks the resulting screen/title. If Enter leaves the client on Shards, it falls back to explicit row selection. A globe click is therefore not required by the current path.
- **Globe and Next:** their screenshot targets are recorded above as alternatives; neither has been added as an automatic fallback in this measurement pass. The globe caption shows the client's remembered shard; it must not be assumed to match the requested shard.
- **Red arrow:** the left-facing red arrow goes Back. It is not the right-facing Next control and should not be used as a login/continue target.

These coordinates have been checked visually against the screenshot, not by clicking the live client. The existing UP, DOWN and nine calculated row targets need no changes based on this image. The new globe and arrow bounds are approximate measurements, not confirmed click-execution results.

## Hair and facial-hair dropdowns

Measured from the two user-supplied open-menu screenshots. Their outer window decorations differ, so each image is normalized independently to its 640 x 480 game artwork. The first image's artwork starts at approximately (3, 31); the second at approximately (4, 26). The cursor is not used as the coordinate origin.

The menu entries have a **14-pixel vertical pitch**. The existing built-in points match the visible text rows; no changes to click coordinates are needed.

| Control / measurement | Game-content coordinate or size |
|---|---|
| Hair dropdown open target (existing) | (205, 160) |
| Hair first entry, NONE (existing) | (115, 160) |
| Hair second entry, Short (existing) | (115, 174) |
| Hair entry pitch | 14 pixels |
| Hair open-list background, approximately | (97, 155, 226, 323): 129 x 168 pixels |
| Facial-hair dropdown open target (existing) | (205, 208) |
| Facial-hair first entry, NONE (existing) | (115, 208) |
| Facial-hair entry pitch | 14 pixels, shared with hair |
| Facial-hair open-list background, approximately | (97, 200, 271, 340): 174 x 140 pixels |

Click targets are deliberately inside each text row, not exact glyph centres. The blank area below the last entry is not another selectable style. Open-list background bounds are approximate screenshot measurements, not native hitbox measurements.

### Human male hair: all 10 entries

| Entry (1-based) | Style | Target (x, y) |
|---|---|---|
| 1 | NONE | (115, 160) |
| 2 | Short | (115, 174) |
| 3 | Long | (115, 188) |
| 4 | Pony Tail | (115, 202) |
| 5 | Mohawk | (115, 216) |
| 6 | Pageboy | (115, 230) |
| 7 | Topknot | (115, 244) |
| 8 | Curly | (115, 258) |
| 9 | Receding | (115, 272) |
| 10 | 2 Tails | (115, 286) |

### Human male facial hair: all 8 entries

| Entry (1-based) | Style | Target (x, y) |
|---|---|---|
| 1 | NONE | (115, 208) |
| 2 | Goatee | (115, 222) |
| 3 | Long Beard | (115, 236) |
| 4 | Short Beard | (115, 250) |
| 5 | Moustache | (115, 264) |
| 6 | Short Beard & Moustache | (115, 278) |
| 7 | Long Beard & Moustache | (115, 292) |
| 8 | Vandyke | (115, 306) |

### Applying the same row calculation to other races and sexes

The engine already uses `appearance.list_item_point(index, first, spacing)`, where index is zero-based. It opens the correct list, then clicks **(first_x, first_y + index * 14)**. No separate per-style calibration is required.

| Style group in the app | Entry count | First target | Last calculated target |
|---|---:|---|---|
| Human Male Hair | 10 | (115, 160) | (115, 286) |
| Human Male Facial | 8 | (115, 208) | (115, 306) |
| Human Female Hair | 10 | (115, 160) | (115, 286) |
| Elf Male Hair | 9 | (115, 160) | (115, 272) |
| Elf Female Hair | 9 | (115, 160) | (115, 272) |
| Gargoyle Male Hair | 8 | (115, 160) | (115, 258) |
| Gargoyle Male Facial | 4 | (115, 208) | (115, 250) |
| Gargoyle Female Hair | 8 | (115, 160) | (115, 258) |

Human male row spacing and counts are visible in the supplied images. The other rows in this table are calculated from the app's existing style dictionaries using that same pitch; elf/gargoyle dropdown origins and style ordering have not been separately confirmed from an open-menu screenshot. Females and elves have no facial-hair list; male gargoyles have four facial-horn choices. No live dropdown clicks were sent in this pass.

## Built-in skin-palette mapping: human, elf and gargoyle

Measured from the three supplied open-palette screenshots. Template matching against the bundled `seed_appearance` marker located the 640 x 480 game-area origins at **(6, 31)** for human, **(4, 31)** for elf and **(8, 31)** for gargoyle. Match scores were approximately 0.998, 0.958 and 0.958. Subtracting those origins avoids including the differing window frames in click coordinates.

All positions below are game-content coordinates. Bounds use exclusive right/bottom edges.

| Race | Grid | Palette bounds | Cell size | First cell centre | Last cell centre |
|---|---|---|---|---|---|
| Human | 8 columns x 8 rows, 64 cells | (491, 138, 611, 418) | 15 x 35 | **(498, 155)** | **(603, 400)** |
| Elf | 4 columns x 8 rows, 32 cells | (489, 138, 613, 418) | 31 x 35 | **(504, 155)** | **(597, 400)** |
| Gargoyle | 4 columns x 7 rows, 28 cells | (489, 138, 613, 418) | 31 x 40 | **(504, 158)** | **(597, 398)** |

The six centres now ship in `menu_layout.py`. The existing Skin Tone opener **(545, 163)** remains inside the closed swatch. `appearance.skin_cell_point` interpolates each row/column from the first and last centres. Cell indices are row-major: zero is top-left, with the index increasing across each row before moving down. Existing recorded overrides still take precedence; Reset to built-in restores these defaults. Users no longer need to record skin-palette corners before their first run.

Every calculated cell is checked against these measured palette bounds. Coordinates retain the shared game-area scaling transformation for 125% and 150%. This pass does not send game input or confirm physical skin changes in the client.

Pixel verification: sampled every calculated target in the supplied screenshots and compared it with the corresponding cell in the bundled palette image. **64/64 human, 32/32 elf and 28/28 gargoyle cells matched exactly in RGB**, confirming both geometry and row-major cell ordering. All 124 targets also pass measured-cell bounds checks at 100%, 125% and 150% coordinate scaling. Full suite: 307 passed, 6 skipped. Physical live-client selection remains untested.

## Appearance recognition marker: tooltip-safe name field

The updated `seed_appearance.png` and `new_character.png` both use the name-field/header crop at **(227, 49, 484, 139)**, size **257 x 90**. Their search regions in `menu_layout.py` now match those crops. The former bottom race/sex area can be obscured by tooltips and is no longer used for these two markers. Swapping a marker image requires its crop location to agree with its search region; clickpoint overrides do not control recognition regions. The replacement crop matched all three supplied appearance screenshots at approximately 1.000 correlation.

## Revised appearance marker: fixed panel border

The name-field crop was superseded because name-entry tooltips can cover it. Both `seed_appearance` and `new_character` now use the supplied **244 x 24** panel-border crop with region **(19, 118, 263, 142)**. The source crop is copied unchanged. It matches all three supplied human/elf/gargoyle appearance screenshots at approximately 1.000 correlation. Scores in the corresponding login and shard regions are approximately 0.039 and 0.219, below the 0.83 threshold. Tests cover name-area and bottom-controls overlays at 100%, 125% and 150%.

## Character-selection corner marker

The supplied Baja crop (Delete button, panel corner and navigation arrows) replaces the header crop for `characters.png`. Dimensions: **193 x 65**, search region **(439, 395, 632, 460)** in game coordinates. Match against the supplied Baja screenshot: approximately **1.000**. This avoids character names and the title/header area. Latest reported Baja halt was specifically an Origin-error classification; the new build includes the marker scores in that error to distinguish a warning from a recognition problem.

## Character-selection crop tightened for seven-character lists

The final supplied **194 x 60** crop supersedes the 193 x 65 corner marker. Its region is **(439, 401, 633, 461)**. Removing the top strip keeps the seventh character row outside the marker. Both supplied Baja and Drachenfels screenshots match at approximately 1.000 correlation. Recognition tests overwrite the entire seven-row character area through y=399 and verify the marker at 100%, 125%, and 150% scaling.

## Character-screen alternative crops for hover tooltips

Character selection now accepts either the tight corner marker at **(439, 401, 633, 461)** or `characters_header.png` at **(144, 68, 577, 124)**. The fallback header is checked only when the corner match is below threshold. This keeps the usual single-crop path fast. Back/Start tooltips may cover the corner while the header remains visible. Both are independent templates for the same `characters` state; no tooltip itself authorizes a click. Tests cover either crop obscured and both crops obscured at 100%, 125% and 150%. Both obscured must not recognize the screen. Pointer parking after released input remains enabled.


## Hair/horn colour palettes ? 2026-11-03

Measured from `hair_palette.png`, `elf_hair.png`, `gargoyle_horn.png` and `gargoyle_facial_horn.png`. All origins below are relative to the matched palette crop within the 640 x 480 game area, never the desktop/window corner. Existing Hair Color and Facial Hair Color opener points remain shared by all races.

| Race / part | Crop pixels | Grid | Choices | X cell edges | Y cell edges |
| --- | --- | --- | --- | --- | --- |
| Human hair/facial hair | 120 x 280 | 6 x 8 | 48 | 0,20,40,60,80,100,120 | 0,35,70,105,140,175,210,245,280 |
| Elf hair | 120 x 279 | 6 x 9 | 54 | 0,20,40,60,80,100,120 | 0,31,62,93,124,155,186,217,248,279 |
| Gargoyle horns/facial horns | 117 x 273 | 6 x 3 | 18 each | 0,18,38,58,78,98,117 | 0,91,184,273 |

The two gargoyle images are identical. Their outside cells are slightly cropped; the mapping uses those measured edges, not the human row height. Gargoyle cell centres are X=9,28,48,68,88,108 and Y=46,138,229. Every palette uses row-major ordering. Elf facial colours are unavailable; female facial colours and explicit NONE styles are skipped.

The selected race/part image is located after its swatch opens; the chosen cell centre is added to that detected origin, then transformed for desktop scaling. Template caching includes both artwork and scale, so switching races cannot reuse a different race's palette. Simulated-screen checks pass at 100%, 125% and 150%; every target is inside its measured cell. Native controls and persisted selections were verified with temporary app data. No live game clicks were sent during this update.
