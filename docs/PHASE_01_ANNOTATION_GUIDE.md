# Phase 01 annotation guide - v0.3 calibration rules

## Overall

Overall is an independent surgeon judgment of the whole image:

> Considering the image as a whole, how much is task-relevant operative-field visibility impaired?

- 0 = necessary operative-field information is essentially intact
- 1 = slightly difficult to see, but recognition is essentially intact
- 2 = recognition is clearly limited, but the field remains interpretable
- 3 = necessary structures, boundaries, or spatial relationships cannot be reliably recognized

Overall is **not**:
- the sum of component scores;
- the maximum component score;
- a score of how aesthetically clean the image looks.

## Components

Each component asks how much that particular factor contributes to task-relevant visibility loss.

- 0 = absent, or present but no relevant visibility effect
- 1 = mild contribution; recognition remains intact
- 2 = clearly limits recognition
- 3 = severely limits/prevents reliable recognition

Do not sum components. Do not force Overall to equal max(component).

If a component is higher than Overall, recheck both ratings. If both still express your judgment, keep them. The discordance is allowed during this calibration pilot.

## Near-contact / red-out

Near-contact/red-out means loss of field information due to excessive camera-tissue proximity or contact.

- 0 = close or not close, but relevant structure and spatial relationships remain clear
- 1 = slightly too close, but recognition remains intact
- 2 = excessive proximity clearly limits structural recognition or orientation
- 3 = contact/red-out/extreme close-up prevents reliable interpretation

A close-up alone is not near-contact impairment.

## Firefly / ICG

Firefly/ICG is an imaging-mode context flag, not a visibility impairment by itself.

A clear Firefly image can have Overall = 0.

## Confidence

Confidence means:

> How confident are you that, under the same rules, you would assign essentially the same ratings if you reviewed this still again?

- 1 = low
- 2 = moderate
- 3 = high

## Soft consistency checks

The app may warn when:
- max(component) > Overall; or
- Overall is 2-3 while all components are 0.

These warnings do not block saving and do not automatically alter any score.
