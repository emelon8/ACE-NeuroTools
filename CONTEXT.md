# Comenius experiment workspace

Shared language for organizing neuroscience recordings and their analysis.

## Language

**Project**: A research workspace containing related experiments.
_Avoid_: Repository, when referring to a researcher's data workspace rather than the software source repository.

**Experiment**: A researcher-selected unit of work within a project, to which recordings, configuration, and results belong. Its exact relationship to subjects and recording sessions remains a product-design question.
_Avoid_: Subject, CSV row, or pipeline execution as interchangeable names.

**Recording**: Data captured during acquisition, with the timing and metadata needed to interpret it.
_Avoid_: Result, when referring to acquired inputs.

**Modality**: A type of measurement, such as calcium imaging or electrophysiology.
_Avoid_: File format, which describes how a measurement is stored.

**Processing pipeline**: A chosen sequence of operations that turns recordings into derived signals or other outputs.
_Avoid_: Experiment, when referring only to processing.

**Analysis**: A calculation or interpretation performed on selected signals or derived outputs to answer a research question.
_Avoid_: Acquisition, when referring to calculations on existing data.

**Result**: An output of processing or analysis associated with its originating experiment.
_Avoid_: Raw recording.
