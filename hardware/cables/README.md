# DT Trainer Cable Harnesses

Wireviz cable harness source files belong in this folder.

The product-level `hardware/bom.csv` should list each harness as a top-level
assembly. Detailed wire, connector, and child-part BOMs should come from the
Wireviz-generated output, not from duplicated product BOM rows.

## Files

- `dtt-harness.yml`: WireViz source for the main harness (PCB J2 to the OLED and the GP2Y0A51SK0F sensor). The battery is not part of it, because the cell comes with its own leads and a JST PH plug for J6.
- Render with WireViz 0.4.1 (`pip install wireviz==0.4.1`, needs Graphviz `dot`): `wireviz dtt-harness.yml` writes `dtt-harness.{svg,png,html,bom.tsv}`. Commit the outputs with the YAML.
