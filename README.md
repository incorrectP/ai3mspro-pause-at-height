# ai3mspro-pause-at-height
Simple python script to circumvent problems with Cura's "pause at height" functionality on Anycubic i3 Mega models.
Turns a single `.gcode` into several finished prints depending on number of pauses.
Each section gets wrapped into start and end code blocks (based on https://github.com/NilsRo/Cura_Anycubic_MegaS_Profile) to cleanly start where you left off. Print speed for first layers of all non-first files is reduced to 25% of original print speed.



## Usage
Easiest way to use is clone the repository and copy the contents of `ai3mspro-pause-at-height` to the SD card used for your printer.
Save your `.gcode` onto the card and open the card in a terminal.
Then run for example `python anypause.py file.gcode -L 20 30 --extruder-off` to split your file at layers 20 and 30 as well as turn off the hotend for the duration of the pause.

Run `python anypause.py --help` to show help:

```
usage: AnyPause [-h] --layers LAYERS [LAYERS ...] [--prefix PREFIX] [--output-dir OUTPUT_DIR] [--faststart] [--bed-off] [--extruder-off] [--fan-off] input_file

Process a G-code file and output multiple processed versions.

positional arguments:
  input_file            Path to the input G-code file

options:
  -h, --help            show this help message and exit
  --layers LAYERS [LAYERS ...], -l LAYERS [LAYERS ...]
                        One or more layer numbers to split at (e.g. -l 10 20)
  --prefix PREFIX, -p PREFIX
                        Prefix for output G-code files (default: AP)
  --output-dir OUTPUT_DIR, -o OUTPUT_DIR
                        Directory to save output G-code files (default: input file directory)
  --faststart, -fs      Insert command (M220 S25) to slow down the first layer of non-first files
  --bed-off             Insert command (M140 S0) at the end of split segments
  --extruder-off        Insert command (M104 S0) at the end of split segments
  --fan-off             Turn the fan off (M107) in finished split files and restore it in subsequent parts
```

By default output gets placed into the directory of the **input file** labeled with the original file name prefixed by `AP{#}_`. You can change this with flags `--output-dir` and `--prefix`.

The `--faststart` flag omitts print speed reduction for the first layer of non-first files.

### Notes

The **first** resulting file retains the startcode from your slicer, the **last** file will keep the orginal endcode.

Tested with Anycubic i3 Mega S