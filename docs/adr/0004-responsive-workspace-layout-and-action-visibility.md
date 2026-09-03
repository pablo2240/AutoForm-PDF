# 0004: Responsive Workspace Layout, Toolbar Elasticity, and Priority Action Visibility

Establish responsive layout rules, collapsible sidebar architecture (48px rail mode), elastic toolbar compacting, and navbar action prioritization to guarantee complete visibility on laptop and small screen viewports (<= 1280px).

## Context & Problem
On viewports <= 1366px (standard 13"-15" laptops or split-screen workflows), two high-value UI controls were pushed off-screen or cropped:
1. **The Primary Execution Action ("Generar PDF"):** Anchored at the far right of the top `.navbar-actions`, pushed off-screen by wide template selectors and multi-button labels.
2. **The Media Placement Control ("Agregar Imagen"):** Positioned at the far right of `.editor-secondary-toolbar`, cropped due to an unbounded `flex-grow` text editor box and lack of overflow scrolling.
3. **Restricted Canvas Viewport:** A static 340px sidebar starved the interactive PDF canvas of horizontal space on narrow screens.

## Decision
1. **Navbar Action Prioritization (Smart Icon Collapse <= 1280px):**
   - **Primary Action ("Generar PDF"):** Permanently retains its prominent gradient background, full label text, and badge count across all screen sizes.
   - **Secondary Actions ("Datos Empresa", "Guardar Mapeo", "Limpiar", "Subir PDF"):** Gracefully collapse text labels on `@media (max-width: 1280px)` to icon-only buttons with explicit tooltips, freeing over 250px of horizontal navbar space.
2. **Elastic Toolbar with Non-Destructive Scroll:**
   - The `.toolbar-section.flex-grow` text edit box receives an explicit `min-width: 140px; max-width: 320px;` constraint.
   - The toolbar container enables smooth horizontal touch/wheel scrolling (`overflow-x: auto; scrollbar-width: none; flex-shrink: 0;`), preventing clipping of "Agregar Imagen" and "Añadir Texto" even down to 1024px.
3. **Collapsible Rail Sidebar (340px <-> 48px):**
   - Introduces a toggleable rail state:
     - **Expanded (Default, 340px):** Full search bar, instruction cards, and variable tree.
     - **Collapsed (Rail Mode, 48px):** Displays vertical icon tabs allowing instant single-click expansion while dedicating maximum screen real-estate to the PDF canvas.
   - On screens `<= 1024px`, the sidebar defaults to rail mode or drawer mode to prevent canvas starvation.

## Consequences
- "Generar PDF" and "Agregar Imagen" remain permanently visible and accessible across all laptop and desktop resolutions.
- Workspace adapts seamlessly from 1024px tablet/split viewports up to 4K monitors without UI overflow.
- Canvas workspace expands dynamically when users collapse the sidebar.
