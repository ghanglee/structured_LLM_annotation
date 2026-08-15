You are annotating a building-regulation dataset as one member of an independent panel.

Decide, for each sentence, whether the requirement is **BIM-checkable**: could a rule engine
decide its compliance against a Building Information Model alone?

A requirement is BIM-checkable only when it is a grammatically whole statement rather than a
heading or fragment; it imposes an obligation or prohibition ("should" counts) rather than a
permission, definition or advisory; everything needed to apply it is present in the sentence
rather than in a cited clause, table, figure or standard; compliance could be decided from a
standard, fully-populated BIM model alone, without a physical test, inspection, certification,
empirical analysis, timed verification, external project-specific data, or a person's
subjective judgment; and it states a single requirement rather than several that could
independently pass or fail.

Complex calculation over model geometry does not disqualify a requirement.

Also report a calibrated confidence for each verdict, as an integer from 0 to 100. Report low
confidence when the sentence sits near a boundary, when reasonable annotators could differ, or
when your verdict turned on a judgment call rather than on something explicit in the text.
Do not report high confidence merely because you produced an answer.
