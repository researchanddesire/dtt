# DTT jock mount (concept)

The snap backplate's cradle, worn on a jockstrap waistband. The case sits on the
pubic mound with the jack end down, so the distance sensor looks straight out
over the base of the penis and measures the partner's head moving up and down.
The back curves round the body.

![Hero](images/Jock-Mount-Hero.png)

| Mount | Body side | From the waist |
| --- | --- | --- |
| ![Part](images/Jock-Mount-Part.png) | ![Rear](images/Jock-Mount-Rear.png) | ![End](images/Jock-Mount-End.png) |

## Use

- **Band:** thread the waistband (up to 50 mm wide) over each outer bar and down
  through its slot, so the band runs behind the plate.
- **Fit and release:** as on the backplate. Slide the case in jack end first
  until the lever clicks, then press the blue tab to slide it out. The back pad
  is notched round the lever, so the tab can still be pressed while it's worn.

## Print

- **Mount:** rear face down, with tree supports under the curved back, at least
  4 walls. For two colours, load the `-Black` and `-Blue` STLs as one object.
- **Pad:** cut 3 mm adhesive-backed EVA or neoprene foam with the `-Pad.dxf`
  template, or print `-Pad.stl` flat in TPU 95A. It's optional.

The files are in
[production-exports/cad/jock-mount](../../production-exports/cad/jock-mount/).

## Source

`build_jock_mount.py` reuses `../snap-backplate/build_snap_backplate.py` and
`../enclosed-case/DTT-Enclosed.FCStd` without changing them. Every dimension is
in `PARAMS`. Run `freecadcmd hardware/cad/jock-mount/build_jock_mount.py` from
the repository root, then `python3 hardware/cad/jock-mount/render_jock_mount.py`
for the images.

## Check on a test print and a wearer

- Body curve (`BodyR`, assumed 120 mm).
- Band slot fit on a real jockstrap (`BandW`, `SlotT`).
- Whether the sensor sees the head and not the shaft or the pouch at this
  height. Try `BandY`, or wear it higher on the band.
- Comfort with and without the pad (`PadT`).
