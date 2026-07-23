# Capability Preflight

Run this preflight before making changes. Record only the capabilities relevant to the task.

## 1. Identify accessible systems

Confirm whether the active session can access:

- internal company knowledge or project connectors;
- the target Git repository and its default branch;
- repository write operations, branches, pull requests, and CI details;
- the target host, service manager, logs, listeners, and health endpoints;
- a local runtime for tests, scripts, packaging, or artifact creation;
- privileged operations such as `sudo`, service restart, package installation, DNS, firewall, certificates, or authentication changes.

Do not promise operations that the available tools cannot perform.

## 2. Resolve the execution path

Choose the strongest available path:

1. perform the work directly with connected tools;
2. prepare and validate repository changes while leaving deployment blocked;
3. create an exact user-run command or script when direct host access is unavailable;
4. provide diagnosis only when neither modification nor validated command preparation is possible.

Continue all work supported by the current capability set.

## 3. Establish authority

For each intended action, identify the matching authority source:

- current user instruction;
- applicable standing authorization in the active conversation;
- repository-owned mission or authority file;
- project-specific handoff.

Treat authorization as scoped to the named project, repository, service, host, and environment. Do not import authority from unrelated work.

## 4. Verify freshness

Before acting, obtain fresh evidence for the items that can change:

- repository default branch and remote HEAD;
- current branch, commit, and working tree;
- open PR or issue state;
- latest CI status;
- current service state and recent logs;
- current deployment target and environment.

Do not use old logs or earlier conversation state as proof of the present condition when fresh evidence is available.

## 5. Select a mode

Select exactly one starting mode from `deployment-modes.md`:

- Inspect;
- Develop;
- Deploy.

Escalate to a more powerful mode only when the corresponding access and authority are both present.

## 6. Preflight outcome

Internally capture:

- objective;
- available tools and missing capabilities;
- active authority source;
- selected mode;
- verified repository and environment state;
- first executable action.

Begin immediately after the preflight. Do not stop merely to restate it unless the user requests a status report or a missing capability blocks every useful path.
