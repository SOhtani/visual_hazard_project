# PHASE_01_VISUAL_AUDIT_QUICK_GUIDE.md

## Purpose

This 136-frame review is an **internal retrieval audit**, not the final calibration/validation annotation set.

The only question at this stage is:

> What visual phenomenon is actually present in each frame?

Do **not** score severity, overall visibility, or component-related visibility impairment yet.

## Labels

Select all visibly present phenomena:

- Blur / defocus / motion blur
- Smoke / airborne veil
- Lens contamination / lens fogging
- Glare / specular reflection
- Whiteout / overexposure
- Underexposure / blackout
- Blood / fluid
- Physical obstruction
- Near-contact / wall view

Additional flags:

- None of the listed phenomena
- Mechanism uncertain / cannot confidently classify
- Non-standard imaging mode (e.g. Firefly/ICG)

## Definitions

### Blur / defocus / motion blur
Loss of fine detail or boundaries due to focus or motion. Smooth tissue with intrinsically little texture is not sufficient.

### Smoke / airborne veil
A translucent smoke- or mist-like layer between the camera and operative field. Do not use this label for simple low contrast or obvious lens fogging.

### Lens contamination / lens fogging
Blood, smear, condensation, droplets, or fog that appears to lie on the lens surface. If smoke vs lens contamination cannot be distinguished confidently, use the uncertainty flag.

### Glare / specular reflection
Bright focal reflection from a shiny surface. A white instrument or gauze is not glare merely because it is white.

### Whiteout / overexposure
Loss of visual information caused by saturation/overexposure. A white object with preserved surface detail is not whiteout.

### Underexposure / blackout
Loss of visual information because the image or region is too dark. A dark background with clearly visible operative structures is not sufficient.

### Blood / fluid
Visible blood or fluid in the operative field. Visibility impairment is not required at this stage.

### Physical obstruction
Instrument, gauze, tissue, suction device, or other material materially blocks the field behind it. Mere instrument presence does not qualify.

### Near-contact / wall view
Camera is extremely close to or contacting tissue, causing local tissue to dominate the image and spatial context to be lost. Redness is not required.

## What happens next

After all 136 frames are reviewed:

1. unblind retrieval stratum;
2. cross-tabulate retrieval route vs human-confirmed phenomenon;
3. identify underrepresented constructs;
4. add only the missing candidate types;
5. build the final targeted calibration set;
6. only then perform detailed 0-3 visibility scoring.
