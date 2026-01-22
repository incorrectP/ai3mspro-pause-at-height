M300 S1396 P714		                       ; Beep
G28 X0 Y10 Z0                              ; move X/Y to min endstops 
M420 S1                                    ; Enable leveling 
M420 Z2.0                                  ; Set leveling fading height to 2 mm 
G0 Z0.15                                   ; lift nozzle a bit 
G92 E0                                     ; zero the extruded length 
G1 X50 E20 F500                            ; Extrude 20mm of filament in a 5cm line. 
G92 E0                                     ; zero the extruded length again 
G1 E-2 F500                                ; Retract a little 
G1 X50 F500                                ; wipe away from the filament line
G1 X100 F9000                              ; Quickly wipe away from the filament line