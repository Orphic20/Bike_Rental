# Muñoz Bike Rental — Design Direction

## Three initial approaches

### Theme Name: Coastal Utility Atelier
Very Brief Intro: A sun-washed, editorial rental shop identity that treats everyday movement as a small luxury. Quiet materials, tactile photography, and a clay-red accent make the booking experience feel local and considered.
Probability: 0.07

### Theme Name: Night Ride Dispatch
Very Brief Intro: A darker, kinetic direction with road-marking graphics, sharp type, and luminous safety details. It positions the shop as a confident after-hours mobility service.
Probability: 0.03

### Theme Name: Park Bench Modernism
Very Brief Intro: A light civic-inspired system with soft green, paper textures, and modular information panels. The mood is friendly, practical, and neighborhood-first.
Probability: 0.08

## Chosen approach: Coastal Utility Atelier

### Design Movement
Contemporary Mediterranean editorial design blended with Swiss utility graphics and a boutique travel-journal sensibility.

### Core Principles
1. Make local movement feel like a considered ritual, not a logistics transaction.
2. Use asymmetry, generous margins, and tactile imagery to create calm momentum.
3. Let utility details—availability, pricing, duration—remain crisp and immediately scannable.
4. Prefer honest materials, quiet texture, and one strong accent over decorative noise.

### Color Philosophy
The base is warm ivory and sun-baked stone so the page feels like a physical studio with daylight on the walls. Sage green signals dependable everyday mobility; clay red is the ownable action color, used sparingly for booking moments and wayfinding. Midnight navy grounds the system for high-contrast type and makes the warm palette feel grown-up rather than playful.

### Layout Paradigm
A left-anchored editorial frame with offset content rails, slim vertical labels, and alternating full-bleed imagery. Key actions sit in an asymmetric booking rail rather than a centered hero card, so the experience reads like a well-designed guidebook with a clear route through it.

### Signature Elements
- Thin route-line rules with numbered waypoints.
- Small clay-red utility tabs and pill-shaped availability markers.
- Oversized editorial numerals and vertical micro-labels for section navigation.

### Interaction Philosophy
Interactions should feel like turning a page or selecting a route: quick, tactile, and visually anchored. Hover states lift imagery slightly and reveal a route cue; selected states use clay red fill and a short confirmation label. Buttons have a subtle press scale and never rely on mystery icons alone.

### Animation
Use 180–260ms ease-out transitions for buttons, tabs, and image lifts. Introduce sections with a restrained upward fade and stagger cards by 50ms. Keep route rules static; animate only the small waypoint marker when a booking option is selected. Respect reduced-motion preferences.

### Typography System
Display: Fraunces, 600–700, used for large editorial headlines and feature numbers. Body: DM Sans, 400–600, used for navigation, labels, pricing, and paragraphs. Hierarchy is built through scale, not excessive weight: quiet uppercase labels at 11–12px, body at 15–17px, feature headings at 56–84px with tight leading.

### Brand Essence
Muñoz Bike Rental is the neighborhood's best way to borrow a bike and find a better pace—made for visitors and locals who prefer the scenic route.
Personality adjectives: Grounded, curious, generous.

### Brand Voice
Headlines sound observational and lightly poetic; CTAs are direct but never shouty; microcopy is useful, local, and specific. Avoid generic travel language.

Example lines:
- “Take the long way home.”
- “Your bike is waiting by the sea.”

### Wordmark & Logo
The wordmark uses a custom lowercase lockup with a slightly extended “o” counter to echo a wheel. The supporting mark is a bold sun-over-wheel symbol: two interlocking arcs that remain legible at favicon size and on shop signage.

### Signature Brand Color
Clay Red `#C84C3D` — a warm signal color inspired by painted curbs, terracotta roof tile, and the moment a rider decides where to turn next.

### Implementation reminder
Every edited CSS, page, and component file should carry a short comment reminding the author to reinforce the Coastal Utility Atelier direction: warm daylight, editorial asymmetry, crisp utility, and restrained clay-red interaction cues.
