# Contributing to DataCatalog

## Git workflow

The git workflow followed is based on https://nvie.com/posts/a-successful-git-branching-model/.

## Merge requests

- Any major contributions must be done through merge requests.
- The branch name should start with the issue number (except if no issues exist like for minor or technical changes).
  Example: 124-fancy-new-feature
- A merge request can be open as soon as the branch is created but in this case, the MR should be set as draft/WIP.
- The MR name should contain the issue number prefixed by '#' (e.g. #98-improve-error-handling).
- The MR description should contain relevant implementation notes (a new setting has been introduced, etc.) and
  eventually a description of what has changed compared to the issue description (e.g. partial implementation).
- The MR description also contains the DoD checklist, the submitter is in charge of checking are marking each item as
  checked.
- If the implementation impacts the user interface, screenshots of the new feature or of the changes should be included.
- If the MR presents some merge conflicts, they need to be resolved. If the conflicts are trivial, they can be fixed
  directly by the MR submitter. If not trivial, the team should get together to resolve the conflicts.
- Once the draft status is removed the MR should be unassigned or assigned to the team member(s) who will do the review.
  The draft status should be removed only when the issue has been fully addressed, see definition of "done" below.
- At least one approval from another team member is needed before the MR can be merged (
  c.f. [Code review](#code-review)).

## Definition of "done" (DoD):

- the issue requirements are implemented
- the pipeline is passing
- the test coverage is not decreased compared to before the implementation of the issue
- except for very minor changes a unit test should cover and check the implementation
- settings.py.template is updated in case changes of the settings file are required
- the added methods and classes have docstrings and type hints
- readme is updated if impacted by the changes

## Code review

Code review is done using the comments feature on gitlab merge requests. Comments on code should target the
corresponding range of lines of code. General comments not targeting some specific lines of codes should be added using
the start thread option when posting a comment. The reviewer should checkout the corresponding branch and actually test
the feature, reviewing the code cannot be considered sufficient.
See https://dev.to/alexomeyer/code-review-a-comprehensive-checklist-5gnm for some recommendations on how to do a good
review.

The reviewer also check the implementation against the DoD (see above).

Once the review is done, the MR should be assigned back to its submitter. The submitter of the MR answers the comments
and eventually push some new changes. Once the submitter has addressed all comments, they assign the MR back to the
reviewer. The reviewer checks if the comments have been addressed and mark the corresponding threads as resolved. If not
all threads can be resolved the MR is assigned back to the submitter and so forth. Once all threads are marked as
resolved, the reviewer approves and merge the MR. The corresponding issue can be closed when the MR is merged and the
implementation has also been checked on the test instance by the MR submitter.
