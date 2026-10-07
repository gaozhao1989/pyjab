Updating the checklist against the 1.2.0 code. Currently supported:

* `nodename`
* `@attr = 'value'`
* `@attr = contains('value')`
* `//*`
* `[n]` positional predicates

Still missing (unchanged):

* `/` and `//` as distinct axes -- the parser currently treats the tree as flat
* `.` and `..`
* comparison predicates such as `[@indexinparent > 10]`
* union `|`
* axes

Given the traversal-pruning work in 1.3.0 touches the same code path, I would
rather land the parser changes together with it than twice. Keeping this open
as the tracking issue.
