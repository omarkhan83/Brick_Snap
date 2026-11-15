# tools/serve.ps1 does not check that a requested file is inside the project folder
- status: open
- owner: nobody

The server decodes the URL path and joins it onto the project folder with no containment check
(`tools/serve.ps1` lines 5-9), so a request like `/..%2F..%2Fsomefile` may read files outside the project.
It listens on localhost only, so the exposure is other programs on the same computer, and whether the request
gets through depends on the PowerShell version; this was read, not tested. It also serves `.git/`.

Done when the script resolves the full path and returns 404 unless it is inside the project folder.

## Notes
Found in the 2026-11-15 code review.
