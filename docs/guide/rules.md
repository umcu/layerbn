# Rules for arcs

The layer order already rules out every arc that runs backwards. Rules can rule out more, or
require an arc. They **can never allow an arc against the layer order**; requiring one is an
error that says so.

```yaml
constraints:
  within_layers: true            # default for layers without their own arcs_within
  forbid:
    - {from: SEX, to: EXPOSURE_B}             # one arc
    - {from_layer: Exposures, to_layer: Outcome}   # every arc between two layers
  require:
    - {from: AGE, to: EXPOSURE_A}
  no_parents: [AGE, SEX]         # nothing in the study may influence these
  no_children: [OUTCOME]         # these may influence nothing
```

Variables and layers can be written by column name or by label (`Exposure A (score)`). A
layer stands for all the variables in it, and `from`/`to` can be mixed with
`from_layer`/`to_layer`.

| Rule | Use it for |
| --- | --- |
| `forbid` | An arc you know to be impossible, which the order allows. |
| `require` | An arc you take as given. **Use sparingly**: a required arc is an assumption, not a finding, and needs a reason in your methods. |
| `no_parents` | Variables nothing in the study can influence, beyond what the order says. |
| `no_children` | Variables that cannot influence anything in the study. |
| `within_layers` | Allow or forbid arcs inside layers by default. A layer's own `arcs_within` takes precedence. |

!!! tip "Conflicts are reported"

    A rule that is both required and forbidden, or that collides with `no_parents` or with a
    layer without inner arcs, is an error that names the pair.
