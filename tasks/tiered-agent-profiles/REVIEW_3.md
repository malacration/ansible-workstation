CONSOLIDATED REVIEW (round 3): CHANGES REQUESTED. Caveat: the tree changed during the review.
[MAJOR][A] A-1 as above. [MAJOR][A+B] A-2 as above. [MINOR][A] A-3, A-4, A-5, A-6, A-7 as above.
[MINOR][B] B-1: ai/roles/herdr/tasks/release.yml:109-115 `backup: true` leaves a binary copy per upgrade or reconcile, and the cache keeps every version. Keep at most one backup, or delete it after successful revalidation, and prune cache versions other than the resolved one.
[NIT][A] Double start on migration; README wording at 228-229, 496 and 237.
[NIT][B] Unauthenticated GitHub API is limited to 60/h; acceptable. installed_state.py:31-40 rejects symlinked ancestors such as /home → /var/home; document it in roles/herdr/README.md.
VERIFIED OK: REVIEW_2 resolved (N1, D2, D1, m-a..m-e, nits); service rename and migration semantics; single cao_terminal_backend definition and visibility; herdr trust chain fail-closed, idempotent, check mode only predicts; security OK.
Required for approval: A-1, A-2, A-4 (fresh frozen logs). Recommended: A-3, A-5..A-7, B-1.
