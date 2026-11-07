# K:LINK project boundary

This checkout belongs to **KTCS / KTcs-KLink/ai-assistant**. Keep it separate from
멋사, 샤이닝, Shining, and unrelated projects. The user explicitly requested this separation.

- Use the KEPCO source files under the parent KTCS workspace's `outputs/` for this
  HR quality task. Keep corpus, golden questions, index versions and prior results intact.
- Do not import, merge, copy, or publish another project's code, documents,
  employee data, environment files, database contents, or credentials here or vice versa.
- The existing KTCS-root `.env` is server-only. Never copy it into a UI, artifact,
  prompt, log, commit, or another project's folder. Never display credential values.
- Reusing read-only model weights does not authorize sharing project data or configuration.
  Verify the model/index/service identity before using a local embedding service.
- Supabase ingestion and other external database writes remain **on hold** until
  the user explicitly resumes them. Do not infer approval from a passing test.
- Preserve main and team branches. Work only on the task feature branch; never create a PR.
- Do not present an automated source check or model agreement as independent human
  approval, current KTCS policy applicability, or a guarantee of all answer semantics.

The parent KTCS `AGENTS.md` also applies.
