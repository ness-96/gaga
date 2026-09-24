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
time = (analysisStart + analysisEnd) / 2
f1 = Get value at time: 1, time, "Hertz", "Linear"
f2 = Get value at time: 2, time, "Hertz", "Linear"
f3 = Get value at time: 3, time, "Hertz", "Linear"
writeFileLine: outputPath$, f1, tab$, f2, tab$, f3
Remove
