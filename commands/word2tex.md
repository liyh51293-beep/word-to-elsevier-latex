---
description: Convert a Word (.docx) manuscript to an Elsevier CAS LaTeX project. Pass the docx path as the argument.
argument-hint: <path-to-docx>
---

Use the `docx-to-elsevier` skill from this plugin to convert the Word document at `$ARGUMENTS` into an Elsevier CAS LaTeX project (numeric `[1][2]` citations, all formatting fixes pre-applied).

Follow the 8-step pipeline in the skill's SKILL.md exactly. Stop and ask the user only if:
- the .docx path doesn't exist
- the docx uses paragraph styles that don't match the known mapping
- a compile error appears that isn't covered by the gotchas list

Otherwise drive end-to-end: unzip → parse → build → compile → open the PDF.
