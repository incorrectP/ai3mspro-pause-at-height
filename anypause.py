import os
import re
import argparse
from typing import List, Dict, Tuple

class GCodeProcessor:
    def __init__(self, input_path: str):
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"G-code file not found: {input_path}")

        self.input_path = input_path
        self.lines = self._load_gcode()

    def _load_gcode(self) -> List[str]:
        with open(self.input_path, "r", encoding="utf-8") as f:
            return f.readlines()

# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="AnyPause",
        description="Process a G-code file and output multiple processed versions."
    )

    parser.add_argument("input_file", help="Path to the input G-code file")

    parser.add_argument(
        "--layers", "-l",
        nargs="+",
        type=int,
        required=True,
        help="One or more layer numbers to split at (e.g. -l 10 20)"
    )

    parser.add_argument(
        "--prefix", "-p",
        default="AP",
        help="Prefix for output G-code files (default: AP)"
    )

    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        help="Directory to save output G-code files (default: input file directory)"
    )

    parser.add_argument(
        "--faststart", "-fs",
        action="store_true",
        help="Insert command (M220 S25) to slow down the first layer of non-first files"
    )

    parser.add_argument(
        "--bed-off",
        action="store_true",
        help="Insert command (M140 S0) at the end of split segments"
    )

    parser.add_argument(
        "--extruder-off",
        action="store_true",
        help="Insert command (M104 S0) at the end of split segments"
    )

    parser.add_argument(
        "--fan-off",
        action="store_true",
        help="Turn the fan off (M107) in finished split files and restore it in subsequent parts"
    )

    args = parser.parse_args()

    processor = GCodeProcessor(args.input_file)

    # locate startcode/endcode files
    base_dir = os.path.dirname(os.path.abspath(args.input_file))
    script_dir = os.path.dirname(os.path.abspath(__file__))
    def _find_candidate(names: List[str]) -> str:
        for p in names:
            if os.path.exists(p):
                return p
        return names[0]

    startcode_path1 = _find_candidate([
        os.path.join(script_dir, "restartcode1.gcode"),
        os.path.join(script_dir, "codeblocks", "restartcode1.gcode"),
        os.path.join(base_dir, "restartcode1.gcode"),
        os.path.join(base_dir, "codeblocks", "restartcode1.gcode"),
    ])
    startcode_path2 = _find_candidate([
        os.path.join(script_dir, "restartcode2.gcode"),
        os.path.join(script_dir, "codeblocks", "restartcode2.gcode"),
        os.path.join(base_dir, "restartcode2.gcode"),
        os.path.join(base_dir, "codeblocks", "restartcode2.gcode"),
    ])
    endcode_path = _find_candidate([
        os.path.join(script_dir, "pausecode.gcode"),
        os.path.join(script_dir, "codeblocks", "pausecode.gcode"),
        os.path.join(base_dir, "pausecode.gcode"),
        os.path.join(base_dir, "codeblocks", "pausecode.gcode"),
    ])

    def _read_optional(path: str) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.readlines()
        except Exception:
            return []

    startcode_lines1 = _read_optional(startcode_path1)
    startcode_lines2 = _read_optional(startcode_path2)
    endcode_lines = _read_optional(endcode_path)

    # Parse slicer information comments for temps and find layer markers
    slicer_info: Dict[str, str] = {}
    slicer_pattern = re.compile(r";\s*Slicer info:([^;]+);(.+)", re.IGNORECASE)
    layer_pattern = re.compile(r";\s*LAYER\s*[:#]?\s*(\d+)", re.IGNORECASE)
    requested_layers = sorted(set(args.layers))
    found_layers = {}
    
    for idx, line in enumerate(processor.lines):
        m = layer_pattern.search(line)
        ms = slicer_pattern.search(line)
        if ms:
            key = ms.group(1).strip()
            val = ms.group(2).strip()
            slicer_info[key] = val
        if m:
            try:
                ln = int(m.group(1))
            except ValueError:
                continue
            if ln in requested_layers and ln not in found_layers:
                found_layers[ln] = idx

    nozzle_temp = slicer_info.get("material_print_temperature")
    nozzle_layer0_temp = slicer_info.get("material_print_temperature_layer_0")
    bed_temp = slicer_info.get("material_bed_temperature")
    bed_layer0_temp = slicer_info.get("material_bed_temperature_layer_0")

    missing = [ln for ln in requested_layers if ln not in found_layers]
    if missing:
        print(f"Warning: layer markers not found for layers: {missing}")

    split_starts = [0] + [found_layers[ln] for ln in sorted(found_layers.keys())]
    split_starts = sorted(set(split_starts))

    ranges: List[Tuple[int, int]] = []
    for i in range(len(split_starts)):
        start = split_starts[i]
        end = split_starts[i + 1] if i + 1 < len(split_starts) else len(processor.lines)
        ranges.append((start, end))

    # Output generation
    outputs: List[str] = []
    for part_idx, (start, end) in enumerate(ranges, start=1):

        # Create output path
        out_name = f"{args.prefix}{part_idx}_{os.path.basename(args.input_file)}"
        out_dir = args.output_dir if args.output_dir else base_dir
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        out_path = os.path.join(out_dir, out_name)

        # First file
        if part_idx == 1:
            segment_lines = processor.lines[start:end] # Split marker excluded

            offs: List[str] = []
            if args.extruder_off:
                offs.append("M104 S0                                    ; Extruder off \n")
            if args.bed_off:
                offs.append("M140 S0                                    ; Heatbed off \n")
            if args.fan_off:
                offs.append("M107                                       ; Fan off \n")

            if offs:
                segment_lines = segment_lines + ["\n"] + offs + ["\n"]

            segment_lines = segment_lines + endcode_lines
            
        # Subsequent files
        else:
            mod_start: List[str] = []
            mod_start.extend(startcode_lines1)
            segment_body = processor.lines[start:end]

            # Turn fan back on
            if args.fan_off:
                insert_at = -1
                mod_start.insert(insert_at, "M106 S255                                  ; Fan on\n")

            # Define first layer region
            first_layer_region_end = None
            for j, ll in enumerate(segment_body[1:], start=1):
                if layer_pattern.search(ll):
                    first_layer_region_end = j
                    break
            if first_layer_region_end is None:
                first_layer_region_end = len(segment_body)

            # Raise to start height and speed multiplier for first layer
            z_start = None
            z_pattern = re.compile(r"[Zz]([-+]?[0-9]*\.?[0-9]+)")
            for ll in segment_body:
                mz = z_pattern.search(ll)
                if mz:
                    z_start = mz.group(1)
                    break

            prefix_cmds: List[str] = []
            if z_start:
                prefix_cmds.append(f"G0 Z{z_start}\n")
            if not args.faststart:
                prefix_cmds.append("M106 S128\n")
                prefix_cmds.append("M220 S25\n")
                restore_pos = first_layer_region_end + len(prefix_cmds)
                if restore_pos <= len(segment_body):
                    segment_body.insert(restore_pos, "M106 S255\n")
                    segment_body.insert(restore_pos, "M220 S100\n")

            # Set temp commands for reinit
            template: List[str] = []
            use_bed = bed_layer0_temp or bed_temp
            use_nozzle = nozzle_layer0_temp or nozzle_temp
            if args.bed_off and use_bed:
                template.append(f"\nM140 S{use_bed}   ; Start heating the bed\n")
                template.append("G4 S60                                     ; wait 1 minute \n")
                template.append(f"M190 S{use_bed}   ; wait for bed\n")

            if args.extruder_off and use_nozzle:
                template.append(f"\nM104 S{use_nozzle} ; start hotend\n")
                template.append(f"M109 S{use_nozzle} ; wait hotend\n")

            mod_start.extend(template)
            mod_start.extend(startcode_lines2)

            # If first layer uses different temps, reset
            post_layer_cmds: List[str] = []
            if nozzle_temp and (nozzle_layer0_temp != nozzle_temp):
                post_layer_cmds.append(f"M104 S{nozzle_temp} ; set nozzle to general temp\n")
            if bed_temp and (bed_layer0_temp != bed_temp):
                post_layer_cmds.append(f"M140 S{bed_temp} ; set bed to general temp\n")

            if post_layer_cmds:
                insert_pos = first_layer_region_end
                for cmd in reversed(post_layer_cmds):
                    segment_body.insert(insert_pos, cmd)

            segment_lines = mod_start + ["\n"] + prefix_cmds + segment_body

            # Check if more sections are following
            is_last = (end == len(processor.lines))
            if not is_last:
                offs: List[str] = []
                if args.extruder_off:
                    offs.append("M104 S0                                    ; Extruder off \n")
                if args.bed_off:
                    offs.append("M140 S0                                    ; Heatbed off \n")
                if args.fan_off:
                    offs.append("M107                                       ; Fan off \n")

                if offs:
                    segment_lines = segment_lines + ["\n"] + offs + ["\n"]
                segment_lines = segment_lines + endcode_lines

        with open(out_path, "w", encoding="utf-8") as f:
            f.writelines(segment_lines)

        outputs.append(out_path)

    print("Wrote split files:")
    for o in outputs:
        print(" -", o)
