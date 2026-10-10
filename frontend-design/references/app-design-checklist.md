# App and PWA Design Checklist

Use when building or reshaping a mobile app or PWA. Apply the sections relevant to the change; use the project's target devices, design system, and verification rules. These checks do not prescribe a framework, component name, universal fixed header, alignment direction, or animation duration.

## Task, hierarchy, and density

- Start with the smallest supported phone viewport and the frequent task, then enhance larger layouts. Arrange for touch instead of shrinking a desktop page; keep related short fields together only when their values and errors fit.
- Separate primary submission, utility actions, editable conditions, and inputs. A large touch target does not require a large painted control; preserve reachability when reducing visual bulk.
- Evaluate the usable body space after headings, filters, actions, navigation, and safe areas. Consolidate repetitive headings, helper text, and secondary metadata before shrinking readable text or hit areas.
- Use realistic long values, multiple filters, errors, and keyboard states. Group titles and markers should communicate the task; improve their hierarchy without removing a needed grouping function.

## Scroll ownership and fixed regions

- Identify the scroll owner of the page and each overlay, plus any intentionally fixed regions. Verify these boundaries at the start, middle, and end of content; fixed behavior is a product decision, not a requirement for every header.
- Reserve space once for fixed actions and navigation, using their actual occupied space and safe areas. Check the final item, bottom gaps, transparent-area clicks, and short as well as long content.
- Distinguish native inertia, local edge feedback, scroll chaining, and movement of the outer page. Repair unwanted outer movement without making ordinary scrolling rigid; avoid simulated touch physics unless the interaction requires it.
- Keep position indicators within their scroll surface and out of the touch path. Choose visibility and exit timing consistently for the same role, and release timers and listeners on departure.

## Alignment and native controls

- Compare control boxes, text insets, helper/error text, baselines, and vertical text centers separately. A common border does not prove that text aligns; native date/time/select controls need actual target-platform inspection.
- Choose numeric alignment for the role: editing continuity and comparison across rows have different needs. Define a coherent convention for each role instead of forcing every number to one side.
- Compare same-role controls across consumers in default, disabled, loading, and error states. Check inherited and responsive overrides rather than relying on a shared class name.

## Input, keyboard, and overlays

- Design browsing, temporary search, selected value, and committed form value as distinct states. Cover opening, selection, cancellation, keyboard dismissal, field handoff, and navigation without prematurely changing the selected value.
- Size candidates and overlays within the actual visible viewport and remaining fixed regions. Check complete rows, scrolling, and reachable actions; an outer box that fits while its content is clipped is not sufficient.
- Treat focus, keyboard appearance, and viewport scaling separately. Prevent unintended tap/focus zoom using platform-appropriate controls while retaining accessibility zoom; do not globally disable scaling to mask layout faults.

## Charts and transient feedback

- Choose how a touch user reads values before choosing chart effects. Use labels, fixed readouts, or deliberate selection where they improve legibility; hover is not a sufficient mobile path, and not every chart needs the same pattern.
- Test dragging across a chart as part of page scrolling. Ensure scroll intent does not accidentally select, navigate, or commit an action, and keep readouts away from finger occlusion and fixed controls.
- Define when transient feedback ends: pointer departure, focus departure, dismissal, page hiding, and data changes as applicable. Check touch and desktop behavior separately.
- Preserve card hierarchy without spending body space on repeated counts and action rows. Align secondary metadata with its related value where that improves scanning, rather than imposing one universal card arrangement.

## Copy and recovery

- Describe what was saved, what was not saved, and what the user can do next. Distinguish local backup failure from failure of the primary operation; do not expose implementation terms unless they help the user act.
- Keep labels, search prompts, and action names consistent across equivalent contexts. Explain meaningful differences rather than mechanically giving different operations the same wording.

## Navigation, reuse, and evidence

- Define what is retained, closed, or paused when leaving a page. Auxiliary flows should return to the originating task with the agreed draft, conditions, and scroll state; hidden pages must not retain active overlays or steal focus.
- Find shared components, state helpers, and style roles before implementing the same behavior again. Verify affected consumers, including edits inside overlays and hidden pages on return; reuse requires consistent behavior, not just an import.
- Confirm the version actually loaded. Use rendered geometry, screenshots, and direct interaction for visual and gesture claims; type checks and CSS declarations establish different facts.
- Follow project rules for browser emulation, native simulator, device browser, and installed PWA checks. Focus alone does not prove a keyboard appeared; a phone-sized desktop window does not prove native gestures. Report uncovered behavior, and do not make a physical-device test mandatory for every change without a concrete project or platform reason.
