# CareSaathi design system: "Evidence after dark"

Source of truth for the look. Tokens live in `frontend/src/app/globals.css`; motion in `frontend/src/app/motion.css`.
(The first version, "paper and ink" with cream, teal and a serif, was replaced on Oct 27, 2026: it read as generic wellness styling.)

## Idea

The interface is deep ink. Anything that is **evidence** (a source sheet, the Emergency Card) stays literal white paper.
That ties the look to the product promise: every line points back to a real document.

## Colour

| Role | Token | Value | Use |
| --- | --- | --- | --- |
| Base | `--paper` | `#0a0e1a` | Page background |
| Surface | `--card`, `--card-hi` | `#0f1526`, `#151c32` | Cards, drawer |
| Text | `--ink`, `--ink-2`, `--ink-3` | `#f3f6fb`, `#b9c1d3`, `#8c96ae` | Primary, secondary, quiet |
| Signal | `--signal` | `#c8f135` | Verified, confirmed, primary actions. Text on it is `--on-signal` `#10150a` |
| Coral | `--coral` | `#ff6b57` | Danger, allergy conflicts, SOS. Text on it is `--on-coral` |
| Amber | `--gold` | `#ffb938` | Voice, Elder mode, "waiting for you" |
| Ice | `--ice` | `#6fd3ff` | Sources and links to evidence |
| Paper | `--sheet` | `#f5f2e9` | Source sheet, Emergency Card, the document in the demo. Use the `.on-paper` scope |

Legacy names (`--teal`, `--marigold`, `--rose`, `--leaf`, `--blue`) are aliases of the roles above. Do not add purple or cream.
State is never colour alone: pills and banners carry an icon and words.

## Type

- Display: Bricolage Grotesque, 700 to 800, tracking -0.03 to -0.04em.
- Body: Atkinson Hyperlegible (chosen for legibility; its slashed zero keeps doses unambiguous).
- Labels, line numbers, source chips: JetBrains Mono, uppercase labels at 11 to 12.5px with wide tracking.
- Devanagari: Noto Sans Devanagari as the fallback in both stacks.

## Shape and depth

Radii 10 / 18 / 28. Cards are glass with a 1px border and a spotlight border that follows the pointer. Primary buttons are lime with a light sweep on hover.

## Motion (all off for reduced motion; pointer effects only for fine pointers)

Drifting aurora, grid and grain backdrop; cursor glow; spotlight card borders; 3D tilt on the demo and bento cards; magnetic hero buttons;
split-word headline reveal; evidence ticker; counters; scroll reveals with blur; scroll progress hairline; staggered list entrances;
a living voice orb whose ring speeds up while listening. Only transform and opacity are animated. The page wrapper animates opacity
only, because a transform there would break fixed children (the SOS bar, the drawer).

## Rules

1. Sources are always ice, dashed and monospace, and open a paper sheet with the line highlighted.
2. Elder mode: type never smaller than 19px for content, 56px minimum touch targets, highest-contrast pairs only.
3. Do not add a screen that hides a source or shows an empty allergy list as "none".
4. New colours or fonts need a decision entry in `docs/09-decisions.md`.
