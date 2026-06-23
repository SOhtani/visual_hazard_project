# GitHub Workflow

## Recommended repository policy

Keep `plans/PLAN_VISUAL_HAZARD.md` under version control. Treat it as the single source of truth for architecture, metric definitions, validation rules, and current progress.

All code changes should be linked to a plan phase. If a change is not described in the PLAN, update the PLAN first.

## Branch policy

Use short-lived branches:

```bash
git checkout -b phase-01-component-aliases
git add plans docs scripts data/templates README.md .gitignore .github
git commit -m "Add visual hazard planning docs and component aliases"
git push -u origin phase-01-component-aliases
```

Open a pull request and review:

1. Which PLAN phase the PR implements.
2. Which files were touched.
3. Which existing columns are preserved.
4. Whether any metric definition changed.
5. Whether tests or smoke checks were run.
6. Whether `plans/PLAN_VISUAL_HAZARD.md` progress log was updated.

## AI coding session prompt

Use this at the beginning of every coding session:

```text
Read plans/PLAN_VISUAL_HAZARD.md, docs/METRIC_CALCULATION_REFERENCE.md, and docs/COMPONENT_VALIDATION_PROTOCOL.md first.
Before writing code, summarize:
1. current phase,
2. files you will touch,
3. existing columns you will preserve,
4. tests or smoke checks you will run,
5. assumptions and unknowns.
Do not construct a composite score unless the PLAN explicitly says to do so.
Do not interpret blackness as anthracosis or redness as blood before validation.
Update the PLAN progress log after the phase is complete.
```

## What not to commit

Do not commit raw surgical videos, extracted frames, patient identifiers, clinical CSVs, or generated reports containing PHI. Use `.gitignore` and keep data outside GitHub unless fully de-identified and approved for sharing.
