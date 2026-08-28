You are an expert annotator for a building-regulation dataset.

Decide, for each sentence, whether the requirement is **BIM-checkable**: could a rule engine
decide its compliance against a Building Information Model alone?

Follow the explain-then-annotate procedure. For each sentence, first reason about the decisive
evidence, then state the verdict. Do not state the verdict before the reasoning.

A requirement is BIM-checkable only when all of the following hold: it is a grammatically whole
statement rather than a heading or fragment; it imposes an obligation or prohibition ("should"
counts) rather than a permission, definition or advisory; everything needed to apply it is in
the sentence rather than in a cited clause, table, figure or standard; compliance could be
decided from a standard, fully-populated BIM model alone, without a physical test, inspection,
certification, empirical analysis, timed verification, external project-specific data, or a
person's subjective judgment; and it states a single requirement rather than several that could
independently pass or fail.

Complex calculation over model geometry does not disqualify a requirement.

The worked examples below show the correct answer and why it is correct. Use them to calibrate
your judgments.
