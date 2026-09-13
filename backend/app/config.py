"""Hackathon-scope constants.

There is no User model and no auth (see CLAUDE.md: "Auth: none — hardcoded
user_id = 1 — out of scope for hackathon"), so there is nowhere in the schema to
read a display name or subject list from. GREETING_NAME and SUBJECT_TAGS are
hardcoded for the demo in the same spirit as USER_ID — swap them for real data
if a profile concept ever gets built.
"""

USER_ID = 1

GREETING_NAME = "Aya"
SUBJECT_TAGS = ["algorithms", "data structures", "discrete math"]
