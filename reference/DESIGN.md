# Design System Inspiration of Notion

## 1. Visual Theme & Atmosphere

Notion's website embodies the philosophy of the tool itself: a blank canvas that gets out of your way. The design system is built on warm neutrals rather than cold grays, creating a distinctly approachable minimalism that feels like quality paper rather than sterile glass. The page canvas is pure white (`#ffffff`) but the text isn't pure black -- it's a warm near-black (`rgba(0,0,0,0.95)`) that softens the reading experience imperceptibly. The warm gray scale (`#f6f5f4`, `#31302e`, `#615d59`, `#a39e98`) carries subtle yellow-brown undertones, giving the interface a tactile, almost analog warmth.

The custom NotionInter font (a modified Inter) is the backbone of the system. At display sizes (64px), it uses aggressive negative letter-spacing (-2.125px), creating headlines that feel compressed and precise. The weight range is broader than typical systems: 400 for body, 500 for UI elements, 600 for semi-bold labels, and 700 for display headings. OpenType features `"lnum"` (lining numerals) and `"locl"` (localized forms) are enabled on larger text, adding typographic sophistication that rewards close reading.

What makes Notion's visual language distinctive is its border philosophy. Rather than heavy borders or shadows, Notion uses ultra-thin borders (`border border-base-300` in DaisyUI) -- borders that exist as whispers, barely perceptible division lines that create structure without weight. The shadow system is equally restrained: use Tailwind shadow classes (`shadow-md` for cards, `shadow-xl` for elevated content) with DaisyUI's `--depth: 1` theme variable, creating depth that's felt rather than seen.

**Key Characteristics:**
- NotionInter (modified Inter) with negative letter-spacing at display sizes (-2.125px at 64px)
- Warm neutral palette: grays carry yellow-brown undertones (`#f6f5f4` warm white, `#31302e` warm dark) -- mapped to DaisyUI `base-100`, `base-200`, `neutral`, `base-content`
- Near-black text via `rgba(0,0,0,0.95)` -- not pure black, creating micro-warmth -- use `text-base-content`
- Ultra-thin borders: `border border-base-300` throughout -- whisper-weight division
- Tailwind shadow classes (`shadow-md`, `shadow-xl`) with DaisyUI `--depth: 1` for component depth
- Notion Blue (`#0075de`) as `primary` -- the singular accent color for CTAs and interactive elements
- DaisyUI `badge` with `--radius-selector: 9999px` (full pill) for status indicators
- 4px base spacing unit aligned with Tailwind CSS 4 default scale

## 2. Color Palette & Roles

### Primary
- **Notion Black** (`rgba(0,0,0,0.95)` / `#000000f2`): Primary text, headings, body copy. The 95% opacity softens pure black without sacrificing readability.
- **Pure White** (`#ffffff`): Page background, card surfaces, button text on blue.
- **Notion Blue** (`#0075de`): Primary CTA, link color, interactive accent -- the only saturated color in the core UI chrome.

### Brand Secondary
- **Deep Navy** (`#213183`): Secondary brand color, used sparingly for emphasis and dark feature sections.
- **Active Blue** (`#005bab`): Button active/pressed state -- darker variant of Notion Blue.

### Warm Neutral Scale
- **Warm White** (`#f6f5f4`): Background surface tint, section alternation, subtle card fill. The yellow undertone is key.
- **Warm Dark** (`#31302e`): Dark surface background, dark section text. Warmer than standard grays.
- **Warm Gray 500** (`#615d59`): Secondary text, descriptions, muted labels.
- **Warm Gray 300** (`#a39e98`): Placeholder text, disabled states, caption text.

### Semantic Accent Colors
- **Teal** (`#2a9d99`): Success states, positive indicators.
- **Green** (`#1aae39`): Confirmation, completion badges.
- **Orange** (`#dd5b00`): Warning states, attention indicators.
- **Pink** (`#ff64c8`): Decorative accent, feature highlights.
- **Purple** (`#391c57`): Premium features, deep accents.
- **Brown** (`#523410`): Earthy accent, warm feature sections.

### Interactive
- **Link Blue** (`#0075de`): Primary link color with underline-on-hover.
- **Link Light Blue** (`#62aef0`): Lighter link variant for dark backgrounds.
- **Focus Blue** (`#097fe8`): Focus ring on interactive elements.
- **Badge Blue Bg** (`#f2f9ff`): Pill badge background, tinted blue surface.
- **Badge Blue Text** (`#097fe8`): Pill badge text, darker blue for readability.

### DaisyUI Semantic Color Mapping

The Notion design palette maps to DaisyUI 5 semantic color names as follows. Use DaisyUI semantic names (`bg-primary`, `text-base-content`, etc.) in component code for automatic dark mode support.

| Notion Design Color | Hex Value | DaisyUI Semantic Name | Description |
|---|---|---|---|
| Notion Blue | `#0075de` | `primary` | Brand CTA color |
| Deep Navy | `#213183` | `secondary` | Brand auxiliary color |
| Pure White | `#ffffff` | `base-100` | Page background |
| Warm White | `#f6f5f4` | `base-200` | Alternating section background |
| Warm Dark | `#31302e` | `neutral` | Dark surface |
| Near-Black | `rgba(0,0,0,0.95)` | `base-content` | Primary text |
| Warm Gray 500 | `#615d59` | `base-content` (with opacity) | Secondary text, use `text-base-content/70` |
| Warm Gray 300 | `#a39e98` | `base-content` (with opacity) | Placeholder, use `text-base-content/50` |
| Teal | `#2a9d99` | `success` | Success state |
| Green | `#1aae39` | `success` (variant) | Confirmation |
| Orange | `#dd5b00` | `warning` | Warning state |
| Focus Blue | `#097fe8` | `info` | Info / focus |
| Error Red | `#e53e3e` | `error` | Error / destructive states |

Each semantic color has a corresponding `*-content` color for text placed on that background (e.g., `primary-content`, `secondary-content`, `base-content`, `success-content`, `error-content`). These are required in DaisyUI 5 theme configuration and must maintain good contrast against their associated color.

> **Note**: DaisyUI 5 does not provide `pink`, `purple`, or `brown` as semantic colors. For these, use Tailwind native colors (`bg-pink-400`, `bg-purple-800`, `bg-amber-800`) or CSS custom variables directly.

### Shadows & Depth
- **Card Shadow**: Use Tailwind `shadow-md` -- maps to DaisyUI `--depth: 1` enabled component elevation.
- **Deep Shadow**: Use Tailwind `shadow-xl` or `shadow-2xl` for modals and featured content.
- **Whisper Border**: Use `border border-base-300` (DaisyUI semantic border).

> **Note**: DaisyUI 5 controls shadow depth via `--depth: 1` (on) or `--depth: 0` (off) theme variable. For custom Notion-style ultra-light shadows, define `--shadow-card` and `--shadow-deep` in `@theme` if needed.

## 3. Typography Rules

### Font Family
- **Primary**: `NotionInter`, with fallbacks: `Inter, -apple-system, system-ui, Segoe UI, Helvetica, Apple Color Emoji, Arial, Segoe UI Emoji, Segoe UI Symbol`
- **OpenType Features**: `"lnum"` (lining numerals) and `"locl"` (localized forms) enabled on display and heading text.

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|------|--------|-------------|----------------|-------|
| Display Hero | NotionInter | 64px (4.00rem) | 700 | 1.00 (tight) | -2.125px | Maximum compression, billboard headlines |
| Display Secondary | NotionInter | 54px (3.38rem) | 700 | 1.04 (tight) | -1.875px | Secondary hero, feature headlines |
| Section Heading | NotionInter | 48px (3.00rem) | 700 | 1.00 (tight) | -1.5px | Feature section titles, with `"lnum"` |
| Sub-heading Large | NotionInter | 40px (2.50rem) | 700 | 1.50 | normal | Card headings, feature sub-sections |
| Sub-heading | NotionInter | 26px (1.63rem) | 700 | 1.23 (tight) | -0.625px | Section sub-titles, content headers |
| Card Title | NotionInter | 22px (1.38rem) | 700 | 1.27 (tight) | -0.25px | Feature cards, list titles |
| Body Large | NotionInter | 20px (1.25rem) | 600 | 1.40 | -0.125px | Introductions, feature descriptions |
| Body | NotionInter | 16px (1.00rem) | 400 | 1.50 | normal | Standard reading text |
| Body Medium | NotionInter | 16px (1.00rem) | 500 | 1.50 | normal | Navigation, emphasized UI text |
| Body Semibold | NotionInter | 16px (1.00rem) | 600 | 1.50 | normal | Strong labels, active states |
| Body Bold | NotionInter | 16px (1.00rem) | 700 | 1.50 | normal | Headlines at body size |
| Nav / Button | NotionInter | 15px (0.94rem) | 600 | 1.33 | normal | Navigation links, button text |
| Caption | NotionInter | 14px (0.88rem) | 500 | 1.43 | normal | Metadata, secondary labels |
| Caption Light | NotionInter | 14px (0.88rem) | 400 | 1.43 | normal | Body captions, descriptions |
| Badge | NotionInter | 12px (0.75rem) | 600 | 1.33 | 0.125px | Pill badges, tags, status labels |
| Micro Label | NotionInter | 12px (0.75rem) | 400 | 1.33 | 0.125px | Small metadata, timestamps |

### Principles
- **Compression at scale**: NotionInter at display sizes uses -2.125px letter-spacing at 64px, progressively relaxing to -0.625px at 26px and normal at 16px. The compression creates density at headlines while maintaining readability at body sizes.
- **Four-weight system**: 400 (body/reading), 500 (UI/interactive), 600 (emphasis/navigation), 700 (headings/display). The broader weight range compared to most systems allows nuanced hierarchy.
- **Warm scaling**: Line height tightens as size increases -- 1.50 at body (16px), 1.23-1.27 at sub-headings, 1.00-1.04 at display. This creates denser, more impactful headlines.
- **Badge micro-tracking**: The 12px badge text uses positive letter-spacing (0.125px) -- the only positive tracking in the system, creating wider, more legible small text.

## 4. Component Stylings

### Buttons

DaisyUI provides a unified `btn` component. Apply modifiers to change variants.

**Primary Blue** -> `btn btn-primary`
- Background: `bg-primary` (Notion Blue `#0075de`)
- Text: `text-primary-content`
- Radius: controlled by `--radius-field`
- Hover: DaisyUI auto-darkens via `btn-primary:hover`
- Active: DaisyUI auto-presses via `btn:active`
- Focus: DaisyUI built-in focus ring via `--focus`
- Use: Primary CTA ("Get SherpaNote", "Try it")

**Secondary / Tertiary** -> `btn btn-secondary` or `btn btn-soft`
- Background: DaisyUI secondary styling
- Text: `text-secondary-content`
- Use: Secondary actions, form submissions

**Ghost / Link Button** -> `btn btn-ghost`
- Background: transparent
- Text: `text-base-content`
- Hover: DaisyUI built-in hover highlight
- Use: Tertiary actions, inline links

**Outline Button** -> `btn btn-outline`
- Border: `border-primary`
- Text: `text-primary`
- Hover: filled background on hover
- Use: De-emphasized actions

**Pill Badge Button** -> `badge badge-primary`
- Background: tinted primary surface
- Text: primary color
- Radius: full pill via `--radius-selector`
- Font: DaisyUI badge sizing
- Use: Status badges, feature labels, "New" tags

### Cards & Containers

DaisyUI `card` component with `card-body`, `card-title`, `card-actions`:

```html
<div class="card bg-base-100 shadow-md border border-base-300">
  <div class="card-body">
    <h3 class="card-title">Title</h3>
    <p>Body content</p>
    <div class="card-actions justify-end">
      <button class="btn btn-primary">Action</button>
    </div>
  </div>
</div>
```

- Background: `bg-base-100` (white)
- Border: `border border-base-300` (whisper border)
- Radius: controlled by `--radius-box`
- Shadow: `shadow-md` (card elevation)
- Hover: optional `hover:shadow-xl` for intensification
- Image cards: use `card` with `figure` element for top image

### Inputs & Forms

DaisyUI form controls: `input`, `textarea`, `select`, `label`, `fieldset`, `checkbox`, `radio`, `toggle`, `range`.

```html
<label class="label">Workspace Name</label>
<input type="text" class="input input-bordered" placeholder="My Team Workspace" />
<textarea class="textarea textarea-bordered" placeholder="Describe..."></textarea>
```

- Input: `input input-bordered` with `--radius-field` radius
- Focus: DaisyUI built-in focus ring (`input-primary`)
- Error: `input input-error` for validation states
- Disabled: `input input-disabled`

### Navigation

DaisyUI `navbar` and `dropdown` components:

```html
<div class="navbar bg-base-100 border-b border-base-300">
  <div class="navbar-start"><!-- logo --></div>
  <div class="navbar-center"><!-- links --></div>
  <div class="navbar-end">
    <a class="btn btn-primary">Get SherpaNote</a>
  </div>
</div>
```

- Brand logo left-aligned in `navbar-start`
- Links in `navbar-center` with `btn btn-ghost` styling
- CTA in `navbar-end` with `btn btn-primary`
- Mobile: use `drawer` component for hamburger menu
- Product dropdowns: `dropdown` + `dropdown-content`

### Image Treatment
- Product screenshots with `border border-base-300`
- Top-rounded images via `--radius-box`
- Dashboard/workspace preview screenshots dominate feature sections
- Warm gradient backgrounds behind hero illustrations (decorative character illustrations)

### Distinctive Components

**Feature Cards with Illustrations** -> `card` with `figure`
- Large illustrative headers
- `--radius-box` card with `border-base-300`
- Title via `card-title`, description in `card-body`
- `bg-base-200` background variant for alternating sections

**Trust Bar / Logo Grid**
- Company logos in their brand colors
- Grid layout with `grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6`
- Metric display: `stat` component for large number + description

**Metric Cards** -> DaisyUI `stat` component
```html
<div class="stat bg-base-100 border border-base-300 shadow-md">
  <div class="stat-title">Metric Name</div>
  <div class="stat-value text-primary">$4,200</div>
  <div class="stat-desc">ROI per team</div>
</div>
```

**Alert / Toast** -> DaisyUI `alert` and `toast`
```html
<div class="alert alert-success">Operation completed successfully</div>
<div class="alert alert-warning">Please check your input</div>
<div class="alert alert-error">Something went wrong</div>
<div class="toast">...</div>
```

**Modal / Dialog** -> DaisyUI `modal`
```html
<dialog class="modal">
  <div class="modal-box">
    <h3 class="font-bold text-lg">Confirm Action</h3>
    <p class="py-4">Are you sure?</p>
    <div class="modal-action">
      <button class="btn btn-primary">Confirm</button>
      <button class="btn btn-ghost">Cancel</button>
    </div>
  </div>
</dialog>
```

**Table** -> DaisyUI `table`
```html
<div class="overflow-x-auto">
  <table class="table table-zebra">
    <!-- thead / tbody -->
  </table>
</div>
```

## 5. Layout Principles

### Spacing System

Aligned with Tailwind CSS 4 default spacing scale (4px base unit):

| Tailwind Class | Value | Common Use |
|---|---|---|
| `p-1` / `gap-1` | 4px (0.25rem) | Micro padding, icon gaps |
| `p-2` / `gap-2` | 8px (0.5rem) | Inner padding, list item spacing |
| `p-3` / `gap-3` | 12px (0.75rem) | Component internal padding |
| `p-4` / `gap-4` | 16px (1rem) | Card padding, section internal spacing |
| `p-5` / `gap-5` | 20px (1.25rem) | Generous component padding |
| `p-6` / `gap-6` | 24px (1.5rem) | Section padding, form group spacing |
| `p-8` / `gap-8` | 32px (2rem) | Large section padding |
| `p-12` / `gap-12` | 48px (3rem) | Major section vertical spacing |
| `p-16` / `gap-16` | 64px (4rem) | Hero padding, major section breaks |

> **Note**: Avoid non-standard spacing values. If a specific value is required, use Tailwind arbitrary values (e.g., `p-[14px]`) sparingly. Prefer rounding to the nearest standard value.

### Grid & Container
- Max content width: `max-w-7xl` (1280px) or `max-w-6xl` (1152px) -- Tailwind container classes
- Hero: centered single-column with `py-20 md:py-24 lg:py-32` padding
- Feature sections: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3` for cards
- Full-width `bg-base-200` section backgrounds for alternation
- Code/dashboard screenshots as contained with `border border-base-300`

### Whitespace Philosophy
- **Generous vertical rhythm**: `py-16 md:py-20 lg:py-24` between major sections.
- **Warm alternation**: `bg-base-100` sections alternate with `bg-base-200` sections, creating gentle visual rhythm without harsh color breaks.
- **Content-first density**: Body text blocks are compact (line-height 1.50) but surrounded by ample margin, creating islands of readable content in a sea of white space.

### Border Radius Scale

Aligned with DaisyUI 5's 3-tier radius system via CSS variables:

| DaisyUI Variable | Value | Tailwind Equivalent | Use |
|---|---|---|---|
| `--radius-field` | `0.25rem` (4px) | `rounded-sm` | Buttons, inputs, tabs, select |
| `--radius-box` | `0.75rem` (12px) | `rounded-lg` | Cards, modals, containers, dropdowns |
| `--radius-selector` | `9999px` | `rounded-full` | Badges, pills, status indicators, toggles |

> **Note**: For circular elements (avatars, icon buttons), use Tailwind `rounded-full` or DaisyUI `btn-circle`. DaisyUI 5 applies `--radius-*` values automatically to its components. For manual radius control on non-DaisyUI elements, use Tailwind utilities: `rounded-sm` (4px), `rounded-lg` (12px), `rounded-full` (pill).

## 6. Depth & Elevation

### Shadow System

Use Tailwind standard shadow classes. DaisyUI controls component depth via `--depth: 1` (on) in theme configuration.

| Level | Tailwind Class | Use |
|-------|---------------|-----|
| Flat (Level 0) | none | Page background, text blocks |
| Whisper (Level 1) | `border border-base-300` | Standard borders, card outlines, dividers |
| Soft Card (Level 2) | `shadow-md` | Content cards, feature blocks |
| Deep Card (Level 3) | `shadow-xl` | Modals, featured panels, hero elements |
| Extra Deep | `shadow-2xl` | Elevated overlays, popovers |
| Focus (Accessibility) | DaisyUI built-in `outline` | Keyboard focus on all interactive elements |

### Custom Shadow Variables (Optional)

For Notion-style ultra-light shadows not covered by Tailwind defaults, define in CSS `@theme`:

```css
@theme {
  --shadow-card: 0 4px 18px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.027);
  --shadow-deep: 0 14px 28px rgba(0,0,0,0.04), 0 23px 52px rgba(0,0,0,0.05);
}
```

Then use via Tailwind: `shadow-[var(--shadow-card)]`.

**Shadow Philosophy**: Notion's shadow system uses multiple layers with extremely low individual opacity (0.01 to 0.05) that accumulate into soft, natural-looking elevation. This layered approach makes elements feel embedded in the page rather than floating above it. In DaisyUI, set `--depth: 1` to enable built-in component depth, and supplement with Tailwind shadow classes as needed.

### Decorative Depth
- Hero section: decorative character illustrations (playful, hand-drawn style)
- Section alternation: `bg-base-100` to `bg-base-200` background shifts
- No hard section borders -- separation comes from background color changes and spacing

## 7. Theme & Dark Mode

### DaisyUI Theme System

SherpaNote uses DaisyUI 5's `data-theme` attribute for theme switching. All components using DaisyUI semantic color names automatically adapt to the active theme.

**Switching themes:**
```html
<html data-theme="light">  <!-- Light mode -->
<html data-theme="dark">   <!-- Dark mode -->
```

**Programmatic switch:**
```javascript
document.documentElement.setAttribute('data-theme', 'dark');
document.documentElement.setAttribute('data-theme', 'light');
```

### Theme Configuration

DaisyUI themes are configured in CSS using `@plugin "daisyui/theme"` blocks. The light and dark themes map Notion's warm palette to DaisyUI semantic names:

```css
/* In your main CSS file */
@import "tailwindcss";
@plugin "daisyui";

@plugin "daisyui/theme" {
  name: "sherpanote-light";
  default: true;
  color-scheme: light;

  --color-base-100: #ffffff;
  --color-base-200: #f6f5f4;
  --color-base-300: #e8e7e6;
  --color-base-content: rgba(0,0,0,0.95);
  --color-primary: #0075de;
  --color-primary-content: #ffffff;
  --color-secondary: #213183;
  --color-secondary-content: #ffffff;
  --color-accent: #097fe8;
  --color-accent-content: #ffffff;
  --color-neutral: #31302e;
  --color-neutral-content: #ffffff;
  --color-info: #097fe8;
  --color-info-content: #ffffff;
  --color-success: #2a9d99;
  --color-success-content: #ffffff;
  --color-warning: #dd5b00;
  --color-warning-content: #ffffff;
  --color-error: #e53e3e;
  --color-error-content: #ffffff;

  --radius-selector: 9999px;
  --radius-field: 0.25rem;
  --radius-box: 0.75rem;

  --depth: 1;
}

@plugin "daisyui/theme" {
  name: "sherpanote-dark";
  prefersdark: true;
  color-scheme: dark;

  --color-base-100: #191919;
  --color-base-200: #1e1e1e;
  --color-base-300: #2a2a2a;
  --color-base-content: rgba(255,255,255,0.92);
  --color-primary: #4da3f0;
  --color-primary-content: #191919;
  --color-secondary: #6878c8;
  --color-secondary-content: #ffffff;
  --color-accent: #5aacf5;
  --color-accent-content: #191919;
  --color-neutral: #d4d3d1;
  --color-neutral-content: #191919;
  --color-info: #5aacf5;
  --color-info-content: #191919;
  --color-success: #3dbdb9;
  --color-success-content: #191919;
  --color-warning: #f07020;
  --color-warning-content: #191919;
  --color-error: #f56565;
  --color-error-content: #ffffff;

  --radius-selector: 9999px;
  --radius-field: 0.25rem;
  --radius-box: 0.75rem;

  --depth: 1;
}
```

### Dark Mode Guidelines

1. **Use DaisyUI semantic colors**: Elements using `bg-primary`, `text-base-content`, `bg-base-200`, etc. automatically adapt. No `dark:` prefix needed.
2. **Tailwind hardcoded colors need `dark:` prefix**: Colors like `text-gray-800`, `bg-white`, `border-gray-200` need `dark:text-gray-200`, `dark:bg-gray-900`, etc.
3. **Avoid hardcoded colors when possible**: Prefer `text-base-content` over `text-gray-800`, and `bg-base-100` over `bg-white`.
4. **Images and media**: Add `dark:opacity-80` or `dark:brightness-90` for images that appear too bright in dark mode.
5. **Theme persistence**: Store user preference in `localStorage` and apply on page load to prevent flash of wrong theme.

## 8. Responsive Behavior

### Breakpoints

Aligned with Tailwind CSS 4 standard breakpoints:

| Tailwind Class | Min Width | Description | Key Changes |
|---|---|---|---|
| (default) | 0px | Mobile | Single column, stacked layout |
| `sm:` | 640px | Mobile landscape | Slightly wider cards, 2-col grids begin |
| `md:` | 768px | Tablet | Full card grids, expanded padding, sidebar visible |
| `lg:` | 1024px | Desktop | Standard desktop layout, navigation fully expanded |
| `xl:` | 1280px | Large Desktop | Full layout, max content width |
| `2xl:` | 1536px | Extra Large | Centered, generous margins |

> **Note**: If a custom 400px breakpoint is needed for very small devices, use Tailwind CSS 4's `@custom-variant` to extend the breakpoint system. However, the standard breakpoints above should cover the vast majority of use cases.

### Touch Targets
- Buttons use comfortable padding (8px-16px vertical)
- Navigation links at 15px with adequate spacing
- Pill badges have 8px horizontal padding for tap targets
- Mobile menu toggle uses standard hamburger button

### Collapsing Strategy
- Hero: `text-6xl lg:text-7xl` (48px -> 72px), scales down with `text-4xl` on mobile
- Navigation: horizontal links + CTA -> DaisyUI `drawer` for mobile hamburger menu
- Feature cards: `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` responsive grid
- Product screenshots: `aspect-auto` with responsive images
- Trust bar logos: `grid-cols-2 md:grid-cols-4 lg:grid-cols-6`
- Footer: `grid-cols-1 md:grid-cols-2 lg:grid-cols-4` -> stacked on mobile
- Section spacing: `py-16 lg:py-24` -> `py-12` on mobile

### Image Behavior
- Workspace screenshots maintain `border border-base-300` at all sizes
- Hero illustrations scale proportionally
- Product screenshots use responsive images with consistent `rounded-lg` radius
- Full-width `bg-base-200` sections maintain edge-to-edge treatment

## 9. Accessibility & States

### Focus System
- All interactive elements receive visible focus indicators via DaisyUI built-in `--focus` styling
- Tab navigation supported throughout all interactive components
- High contrast text: `text-base-content` on `bg-base-100` exceeds WCAG AAA (>14:1 ratio)

### Interactive States
DaisyUI provides built-in state styles for most components. Additional states:

- **Default**: Standard appearance with `border-base-300` borders
- **Hover**: DaisyUI auto-applies hover variants (`btn:hover`, `card:hover`)
- **Active/Pressed**: DaisyUI auto-applies press variants (`btn:active`)
- **Focus**: DaisyUI built-in focus ring via `--focus` CSS variable
- **Disabled**: DaisyUI `btn-disabled`, `input-disabled` classes; or `disabled` attribute
- **Loading**: DaisyUI `btn loading` with spinner

### Color Contrast
- Primary text (`base-content`) on `base-100`: ~18:1 ratio
- Secondary text (`base-content/70`) on `base-100`: ~5.5:1 ratio (WCAG AA)
- CTA (`primary`) on `primary-content`: ~4.6:1 ratio (WCAG AA for large text)
- Badge text (`primary`) on tinted surface: ~4.5:1 ratio (WCAG AA for large text)

## 10. Agent Prompt Guide

### Quick DaisyUI Color Reference
- Primary CTA: `btn btn-primary` (Notion Blue `#0075de`)
- Background: `bg-base-100` (Pure White `#ffffff`)
- Alt Background: `bg-base-200` (Warm White `#f6f5f4`)
- Heading text: `text-base-content` (Near-Black `rgba(0,0,0,0.95)`)
- Body text: `text-base-content`
- Secondary text: `text-base-content/70` (Warm Gray 500)
- Muted text: `text-base-content/50` (Warm Gray 300)
- Border: `border border-base-300`
- Link: `text-primary` or `link link-primary`
- Focus ring: DaisyUI built-in `--focus` styling

### Example Component Prompts (DaisyUI + Tailwind)

- "Create a hero section with `bg-base-100` background. Headline at `text-6xl lg:text-7xl font-bold tracking-tighter text-base-content`. Subtitle at `text-xl font-semibold text-base-content/70`. Primary CTA using `btn btn-primary` and ghost button using `btn btn-ghost`."
- "Design a card using DaisyUI: `card bg-base-100 shadow-md border border-base-300`. Title in `card-title font-bold text-xl`. Body in `text-base text-base-content/70`. Actions in `card-actions` with `btn btn-primary` and `btn btn-ghost`."
- "Build a status badge: `badge badge-primary` for brand badges. Use `badge badge-success` for available status, `badge badge-warning` for warnings, `badge badge-error` for errors."
- "Create navigation using DaisyUI `navbar`: `navbar bg-base-100 border-b border-base-300`. Links as `btn btn-ghost` in `navbar-center`. Primary CTA as `btn btn-primary` in `navbar-end`."
- "Design an alternating section layout: `bg-base-100` sections alternate with `bg-base-200` sections. Each section uses `py-16 lg:py-24` with `max-w-7xl mx-auto px-4`. Section heading at `text-4xl lg:text-5xl font-bold tracking-tight`."
- "Create a form using DaisyUI: `label` + `input input-bordered input-primary` for focused state. `textarea textarea-bordered` for multiline. Use `fieldset` + `legend` for grouping. Validation: `input input-error` with `label text-error`."

### DaisyUI Component Quick Reference

| Component | Class | Modifiers |
|---|---|---|
| Button | `btn` | `btn-primary`, `btn-secondary`, `btn-ghost`, `btn-outline`, `btn-soft`, `btn-link`, `btn-sm`, `btn-lg` |
| Card | `card` | `card-body`, `card-title`, `card-actions`, `card-image` |
| Badge | `badge` | `badge-primary`, `badge-secondary`, `badge-success`, `badge-warning`, `badge-error`, `badge-info`, `badge-ghost` |
| Navigation | `navbar` | `navbar-start`, `navbar-center`, `navbar-end` |
| Input | `input` | `input-bordered`, `input-primary`, `input-error`, `input-disabled`, `input-sm`, `input-lg` |
| Textarea | `textarea` | `textarea-bordered`, `textarea-primary`, `textarea-error` |
| Select | `select` | `select-bordered`, `select-primary` |
| Modal | `modal` | `modal-box`, `modal-backdrop`, `modal-action` |
| Drawer | `drawer` | `drawer-side`, `drawer-content`, `drawer-toggle` |
| Dropdown | `dropdown` | `dropdown-content`, `dropdown-hover`, `dropdown-end` |
| Alert | `alert` | `alert-success`, `alert-warning`, `alert-error`, `alert-info` |
| Toast | `toast` | `toast-start`, `toast-center`, `toast-end` |
| Table | `table` | `table-zebra`, `table-pin-rows`, `table-pin-cols` |
| Stat | `stat` | `stat-title`, `stat-value`, `stat-desc` |
| Toggle | `toggle` | `toggle-primary`, `toggle-secondary` |
| Checkbox | `checkbox` | `checkbox-primary`, `checkbox-secondary` |
| Radio | `radio` | `radio-primary`, `radio-secondary` |

### Iteration Guide
1. Always use DaisyUI semantic colors (`text-base-content`, `bg-base-200`) -- Notion's warm neutrals are baked into the theme variables
2. Letter-spacing scales with font size: `tracking-tighter` at display, `tracking-tight` at sub-headings, `tracking-normal` at body
3. Four weights: `font-normal` (read), `font-medium` (interact), `font-semibold` (emphasize), `font-bold` (announce)
4. Borders are whispers: `border border-base-300` -- never heavier
5. Use Tailwind shadow classes: `shadow-md` for cards, `shadow-xl` for modals, `shadow-2xl` for overlays
6. The `bg-base-200` section background is essential for visual rhythm (alternating with `bg-base-100`)
7. Status badges: `badge` for status/tags, `btn` for buttons and inputs -- DaisyUI handles radius via `--radius-field` and `--radius-selector`
8. `text-primary` (Notion Blue) is the primary accent -- use it sparingly for CTAs and links via `btn btn-primary` and `link link-primary`
9. Dark mode: use DaisyUI semantic colors everywhere. Only add `dark:` prefix for Tailwind hardcoded colors
10. DaisyUI 5 applies `--radius-*` values automatically to components. For non-DaisyUI elements, use Tailwind `rounded-sm` (4px), `rounded-lg` (12px), `rounded-full` (pill)
