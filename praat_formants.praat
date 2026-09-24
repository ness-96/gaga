form Arguments
    sentence Audio_file
    sentence Profile male
    sentence Output_file
endform

audioPath$ = audio_file$
outputPath$ = output_file$
maximumFormant = 5500
if profile$ = "male"
    maximumFormant = 5000
endif
Read from file: audioPath$
To Formant (burg): 0, 5, maximumFormant, 0.025, 50
formant = selected("Formant")
duration = Get total duration
startTime = Get start time
endTime = Get end time
analysisStart = max(startTime, duration * 0.3)
analysisEnd = min(endTime, duration * 0.7)
if analysisEnd <= analysisStart
    analysisStart = startTime
    analysisEnd = endTime
endif
timeA = analysisStart
timeB = analysisStart + (analysisEnd - analysisStart) / 6
timeC = analysisStart + (analysisEnd - analysisStart) * 2 / 6
timeD = analysisStart + (analysisEnd - analysisStart) * 3 / 6
timeE = analysisStart + (analysisEnd - analysisStart) * 4 / 6
timeF = analysisStart + (analysisEnd - analysisStart) * 5 / 6
timeG = analysisEnd
f1a = Get value at time: 1, timeA, "Hertz", "Linear"
f2a = Get value at time: 2, timeA, "Hertz", "Linear"
f3a = Get value at time: 3, timeA, "Hertz", "Linear"
f1b = Get value at time: 1, timeB, "Hertz", "Linear"
f2b = Get value at time: 2, timeB, "Hertz", "Linear"
f3b = Get value at time: 3, timeB, "Hertz", "Linear"
f1c = Get value at time: 1, timeC, "Hertz", "Linear"
f2c = Get value at time: 2, timeC, "Hertz", "Linear"
f3c = Get value at time: 3, timeC, "Hertz", "Linear"
f1d = Get value at time: 1, timeD, "Hertz", "Linear"
f2d = Get value at time: 2, timeD, "Hertz", "Linear"
f3d = Get value at time: 3, timeD, "Hertz", "Linear"
f1e = Get value at time: 1, timeE, "Hertz", "Linear"
f2e = Get value at time: 2, timeE, "Hertz", "Linear"
f3e = Get value at time: 3, timeE, "Hertz", "Linear"
f1f = Get value at time: 1, timeF, "Hertz", "Linear"
f2f = Get value at time: 2, timeF, "Hertz", "Linear"
f3f = Get value at time: 3, timeF, "Hertz", "Linear"
f1g = Get value at time: 1, timeG, "Hertz", "Linear"
f2g = Get value at time: 2, timeG, "Hertz", "Linear"
f3g = Get value at time: 3, timeG, "Hertz", "Linear"
writeFileLine: outputPath$, f1a, tab$, f2a, tab$, f3a, tab$, f1b, tab$, f2b, tab$, f3b, tab$, f1c, tab$, f2c, tab$, f3c, tab$, f1d, tab$, f2d, tab$, f3d, tab$, f1e, tab$, f2e, tab$, f3e, tab$, f1f, tab$, f2f, tab$, f3f, tab$, f1g, tab$, f2g, tab$, f3g
Remove
