# Competency Questions

To evaluate COSO, we distill questions from the larger SAWGraph use case to the components that the COSO ontology must support about contaminant samples, releases, observations, results and features.

| Question # (link) | COSO Question | Variables | Result (link) | SAWGraph Questions | 
| -- | ------------------ | ------------------ | --------- | --------- |
| [1](./CQ1.rq) | What Samples have tested for *PFOA*? What type of sample are they? | Substance | | <ul><li> What wells are near locations with a reported  PFOA contamination above 4ppt? </li></ul>|
| [2]() | What *soil* samples have been test for *PFBS*? What is min and max result? | Sample type, substance  | | |
| [3]() | What *wells* have been tested for *PFOA* at levels above *20 ppt*?  | sampled feature type, substance, result value| | <ul><li> What wells are near locations with a cumulative contamination of above 20ppt? </li> </ul>|
| [4]() | What *surface water bodies* have a cumulative contamination result of above *20 ppt*? | sampled feature type, aggregate result value| | |
| [5]() | What is the mean concentration of *PFOA* in *fish tissue* in *Maine*? What is the mean concentration of *PFOA* in *shellfish* harvested in *Maine*?  | sample type, aggregate result value, geography | | |
| [6]() | What locations have *PFOS* levels above *40ppt* with no known contamination release point nearby? | substance, result value, release point distance | | |
| [7]() | What known release points exist in *this region*? | s2 cells | | <ul><li> What suspected contamination sources exist above this aquifer?</li><li>How many suspected contamination sources are within a radius of two S2L13 cells of each well?</li></ul>|