
# Synthetic example

Open the example with **File → Open synthetic annotation demo** or run:

```bash
python -m annotationstudio --schema-demo
```

The project contains 19 illustrative records, 10 tracks and two fictional objects. It has no linked media. The times and object states were invented for demonstrating the editor, export, and speech-timing structure.

Real recordings and the original OCUMO sample projects are kept outside this repository. Tests that require those files skip when the files are absent. Tests using generated BVH snippets and waveforms still run in a clean checkout.
