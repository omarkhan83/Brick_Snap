# A model file that holds several separate pieces laid out side by side
- status: in-progress
- owner: Alec-42 (since 2026-11-19)
- stage: 4

Some files are not one object but a layout of separate pieces, for example the parts of a kit arranged
flat for 3D printing. The conversion treats the whole layout as one model, so the size chosen in studs is
spread across empty space and each piece comes out as a small, coarse pile. A person sees a poor result
and cannot tell why.

Done when the conversion notices that a model is made of pieces that do not touch (and are not simply
small details of one object), says so in plain words in the web app and on the command line before
building, and offers the sensible choices: build the largest piece alone, build one chosen piece, or carry
on with everything as it is.

## Notes
Found on 19 November: a file Alec tried in the web app was a print layout of about ten pieces; at 25 studs
across the whole layout the largest piece was only about eight studs long. `trimesh` can split a mesh into
connected bodies; the pieces' bounding boxes and volumes are enough to tell a layout from one object with
loose details.
