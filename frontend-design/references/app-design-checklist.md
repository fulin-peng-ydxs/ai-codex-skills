# App and PWA Design Checklist

Use when building or reshaping an app or PWA with a declared mobile target. Apply the sections relevant to the change; use the project's target devices, design system, and verification rules. A desktop-only PWA does not acquire mobile requirements merely by supporting installation. These checks do not prescribe a framework, component name, universal fixed header, alignment direction, or animation duration.

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
- For long lists, distinguish content clipping from a data limit. Choose scrolling, pagination, or progressive loading for the task, and expose the actual continuation state. A clear pager does not need prose explaining how to page; use a count or search prompt only when it resolves a real limit or ambiguity. Match footer alignment and control styling to equivalent lists.

## Alignment and native controls

- Compare control boxes, text insets, helper/error text, baselines, and vertical text centers separately. A common border does not prove that text aligns; native date/time/select controls need actual target-platform inspection.
- Choose numeric alignment for the role: editing continuity and comparison across rows have different needs. Define a coherent convention for each role instead of forcing every number to one side.
- Compare same-role controls across consumers in default, disabled, loading, and error states. Check inherited and responsive overrides rather than relying on a shared class name.

## Input, keyboard, and overlays

- Design browsing, temporary search, selected value, and committed form value as distinct states. Cover opening, selection, cancellation, keyboard dismissal, field handoff, and navigation without prematurely changing the selected value.
- Size candidates and overlays within the actual visible viewport and remaining fixed regions. Check complete rows, scrolling, and reachable actions; an outer box that fits while its content is clipped is not sufficient.
- Treat focus, keyboard appearance, and viewport scaling separately. Prevent unintended tap/focus zoom using platform-appropriate controls while retaining accessibility zoom; do not globally disable scaling to mask layout faults.

## Touch intent and platform capability

- Define the relationship between tap, long press, dragging, and native text selection. Cancel a pending long press when scrolling begins and prevent a drag from becoming a release click; provide a discoverable alternative to gesture-only commands. Do not introduce swipe actions simply because the target is mobile.
- Where native selection/callouts conflict with actionable buttons or cards, suppress them within those targets while preserving editable fields and text users need to copy. Diagnose selection, tap highlights, and focus outlines separately; avoid blanket removal of keyboard focus indicators.
- Separate responsive layout decisions from input and API capabilities. Viewport width is a layout signal, not proof of a phone or a touch-only device. Check feature availability and secure-context requirements where relevant, including non-local HTTP access; an optional draft or client helper failure must not silently swallow the primary action.

## Charts and transient feedback

- Choose how a touch user reads values before choosing chart effects. Use labels, fixed readouts, or deliberate selection where they improve legibility; hover is not a sufficient mobile path, and not every chart needs the same pattern.
- Test dragging across a chart as part of page scrolling. Ensure scroll intent does not accidentally select, navigate, or commit an action, and keep readouts away from finger occlusion and fixed controls.
- Define when transient feedback ends: pointer departure, focus departure, dismissal, page hiding, and data changes as applicable. Check touch and desktop behavior separately.
- Place status messages so they do not cover fixed actions or shift unrelated page regions. Choose dismissal by message role: routine success can expire automatically, while errors or recovery actions may need to remain. For conditional helper text, use an existing row or stable allocation where continuity matters; a long message must still fit the supported width.
- Preserve card hierarchy without spending body space on repeated counts and action rows. Align secondary metadata with its related value where that improves scanning, rather than imposing one universal card arrangement.

## Numeric presentation and semantic color

- Establish display precision separately from calculation and storage. If the product omits redundant zero decimals, apply that rule consistently to amounts, prices, quantities, and percentages without rounding meaningful precision or rewriting partially typed input. Reuse the project's exact-decimal formatter where required rather than converting business amounts to binary floating point.
- Map numeric color from domain meaning, not from the fact that an element is a number or a button. Compare summaries, cards, ranks, and chart readouts in supported themes; verify computed colors because local selector specificity can override the intended semantic class. Keep labels and controls in their own visual roles and retain non-color cues where needed.

## Copy and recovery

- Describe what was saved, what was not saved, and what the user can do next. Distinguish local backup failure from failure of the primary operation; do not expose implementation terms unless they help the user act.
- Keep labels, search prompts, and action names consistent across equivalent contexts. Explain meaningful differences rather than mechanically giving different operations the same wording.

## Navigation, reuse, and evidence

- Define what is retained, closed, or paused when leaving a page. Auxiliary flows should return to the originating task with the agreed draft, conditions, and scroll state; hidden pages must not retain active overlays or steal focus.
- Distinguish first entry, cached tab return, explicit detail/drill return, and data refresh. Apply each position source only for its intended transition; an old return parameter must not repeatedly overwrite the user's latest scroll. Restore after content is ready, and guard delayed work against a changed route, inactive page, or newer request.
- Find shared components, state helpers, and style roles before implementing the same behavior again. Verify affected consumers, including edits inside overlays and hidden pages on return; reuse requires consistent behavior, not just an import.
- Confirm the version actually loaded. Use rendered geometry, screenshots, and direct interaction for visual and gesture claims; type checks and CSS declarations establish different facts.
- Follow project rules for browser emulation, native simulator, device browser, and installed PWA checks. Focus alone does not prove a keyboard appeared; a phone-sized desktop window does not prove native gestures. Report uncovered behavior, and do not make a physical-device test mandatory for every change without a concrete project or platform reason.
