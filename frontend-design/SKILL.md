---
name: frontend-design
description: Guidance for intentional visual and interaction design when building or reshaping mobile apps, PWAs, web pages, landing pages, dashboards, or components. Use when Codex needs typography, hierarchy, density, layout, copy, or aesthetic direction grounded in the product and its target device.
---

# Frontend Design

Make deliberate choices grounded in the product, its audience, and the user's brief. Read the project's design system and same-role components before choosing typography, density, or visual treatments; preserve established contracts unless the user authorizes changing them.

## Choose the product context

- For expressive landing, editorial, or brand pages, use the visual exploration below; a distinctive aesthetic choice can serve the brief.
- For mobile apps, PWAs, and recurring task tools, use the App guidance below. Task efficiency and consistent controls come first; a hero, new font pairing, or aesthetic risk is not a required deliverable.
- Interpret feedback against the intended function and target element. Changing a container background is different from changing its buttons; improving an unattractive hierarchy marker does not authorize removing the hierarchy requirement. Resolve routine styling from the existing brief rather than repeatedly seeking approval.

## App and PWA guidance

For mobile apps and PWAs with a declared mobile target, read [references/app-design-checklist.md](references/app-design-checklist.md) before shaping the interface, then use its applicable checks to critique the rendered result. A desktop-only PWA uses the project's desktop task and interaction contracts; installability alone does not require phone layouts or keyboard tests. For a local change, cover the affected behavior and consumers rather than treating every checklist item as a mandatory full-app audit.

Design around the frequent task, the target input methods, and the project's existing component roles. Define what stays fixed, what scrolls, and what survives navigation before adjusting density or styling. The checklist supplies decision criteria; dimensions, alignment choices, timings, and terminal verification requirements come from the project and the user's brief.

## Ground it in the subject

If the brief does not pin down what the product or subject is, pin it yourself before designing: name one concrete subject, its audience, and the page's single job, and state your choice. If there's any information in your memory about the human's preferences, context about what they're building, or designs you've made before, use that as a hint. The subject's own world, its materials, instruments, artifacts, and vernacular, is where distinctive choices come from. Build with the brief's real content and subject matter throughout.

## Design principles

For landing and editorial designs, the hero is a thesis. Open with the most characteristic thing in the subject's world, in whatever form makes sense for it: a headline, an image, an animation, a live demo, an interactive moment. Be deliberate with your choice: a big number with a small label, supporting stats, and a gradient accent is the template answer, only use if that's truly the best option.

For expressive sites, typography carries the personality of the page. Pair the display and body faces deliberately, not the same families you would reach for on any other project, and set a clear type scale with intentional weights, widths, and spacing. For established products, preserve their type system and express hierarchy through its existing roles.

Structure is information. Structural devices, numbering, eyebrows, dividers, labels, should encode something true about the content, not decorate it. Many generic designs use numbered markers (01 / 02 / 03), but that's only appropriate if the content actually is a sequence, like a real process or a typed timeline where order carries information the reader needs. Question if choices like numbered markers actually make sense before incorporating them.

Leverage motion deliberately. Think about where and if animation can serve the subject: a page-load sequence, a scroll-triggered reveal, hover micro-interactions, ambient atmosphere. An orchestrated moment usually lands harder than scattered effects; choose what the direction calls for. However, sometimes less is more, and extra animation contributes to the feeling that the design is AI-generated.

Match complexity to the vision. Maximalist directions need elaborate execution; minimal directions need precision in spacing, type, and detail. Elegance is executing the chosen vision well.

Consider written content carefully. Often a design brief may not contain real content, and it's up to you to come up with copy. Copy can make a design feel as templated as the design itself. See the below section on writing for more guidance.

## Process: brainstorm, explore, plan, critique, build, critique again

For calibration: AI-generated design right now clusters around three looks: (1) a warm cream background (near #F4F1EA) with a high-contrast serif display and a terracotta accent; (2) a near-black background with a single bright acid-green or vermilion accent; (3) a broadsheet-style layout with hairline rules, zero border-radius, and dense newspaper-like columns. All three are legitimate for some briefs, but they are defaults rather than choices, and they appear regardless of subject. Where the brief pins down a visual direction, follow it exactly. The brief's own words always win, including when it asks for one of these looks. Where it leaves an axis free, don't spend that freedom on one of these defaults. Just like a human designer who's hired, there's often a careful balance between doing what you're good at and taking each project as a chance to experiment and learn.

For expressive sites without an established design system, work in two passes. First, brainstorm a short design plan based on the human's design brief: create a compact token system with color, type, layout, and signature. Color: describe the palette as 4-6 named hex values. Type: choose faces for display, body, and captions or data where needed. Layout: use one-sentence prose descriptions and ASCII wireframes to compare concepts. Signature: choose a distinctive element that embodies the brief. For an existing App, instead map its task, control roles, and interaction states to the project's current tokens and components.

Then review the choices against the brief before building. For expressive sites, revise generic defaults that fail to reflect the subject; for Apps, revise ordering, density, or interaction that slows the task or conflicts with the design system. Derive color and type decisions from the resulting design, and check the actual rendered result after implementation.

When writing the code, be careful of structuring your CSS selector specificities. It's easy to generate CSS classes that cancel each other out, especially with a type-based selector like `.section` and an element-based selector like `.cta`. This can happen often with paddings and margins between sections.

Try to do a lot of this planning and iteration in your thinking, and only show ideas to the user when you have higher confidence it'll delight them.

## Restraint and self-critique

For expressive sites, spend boldness in one place and keep the rest disciplined. For task Apps, prioritize consistency, clear hierarchy, and low interaction cost. Cut decoration that does not serve the brief. Check the supported responsive layouts, visible focus, and reduced motion; inspect screenshots and actual interactions rather than treating correct CSS or successful compilation as a finished design. Keep observations in the response unless the user requests a saved process record.

## More on writing in design

Words appear in a design for one reason: to make it easier to understand, and therefore easier to use. They are design material, not decoration. Bring the same intentionality to copy that you would bring to spacing and color. Before writing anything, ask what the design needs to say, and how it can best be said to help the person navigate the experience.

Write from the end user's side of the screen. Name things by what people control and recognize, never by how the system is built. A person manages notifications, not webhook config. Describe what something does in plain terms rather than selling it. Being specific is always better than being clever.

Use active voice as default. A control should say exactly what happens when it's used: "Save changes," not "Submit." An action keeps the same name through the whole flow, so the button that says "Publish" produces a toast that says "Published." The vocabulary of an interface is the signposting for someone navigating the product. Cohesion and consistency are how people learn their way around.

Treat failure and emptiness as moments for direction, not mood. Explain what went wrong and how to fix it, in the interface's voice rather than a person's. Errors don't apologize, and they are never vague about what happened. An empty screen is an invitation to act.

Keep the register conversational and tuned: plain verbs, sentence case, no filler, with tone matched to the brand and the audience. Let each element do exactly one job. A label labels, an example demonstrates, and nothing quietly does double duty.
