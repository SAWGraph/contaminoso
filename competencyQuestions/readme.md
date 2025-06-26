# Competency Questions

To evaluate COSO, we distill questions from the larger SAWGraph use case to the components that the COSO ontology must support about contaminant samples, releases, observations, results and features.

These competency questions also serve as template questions, and by modifying the *variables* additional questions can be answered. 

The SAWGraph questions demonstrate some of the more complicated questions that require to COSO competency highlighted, but also require linking to data and ontologies in other graphs in order answer. 

| Question # (link) | COSO Question | Variables | Result (link) | SAWGraph Extended Questions |
| -- | ------------------ | ------------------ | --------- | --------- |
| [CQ1](./CQ1.rq) | What Samples have tested for *PFOA*? What type of sample are they? | Substance | [CQ1-result](./CQ1-result.csv) | <ul><li> What wells are near locations with a reported  PFOA contamination above 4ppt? </li></ul>|
| [CQ2](./CQ2.rq) | What *soil* samples have been tested for *PFBS*? What is min and max result? | Sample type, substance  | [CQ2-result](./CQ2-result.csv) | |
| [CQ3](./CQ3.rq) | What *wells* have been tested for *PFOA* at levels below *20 ppt* or it was not detected?  | sampled feature type, substance, result value| [CQ3-result](./CQ3-result.csv) | <ul><li> What wells are near locations with a cumulative contamination of above 20ppt? </li> </ul>|
| [CQ4](./CQ4.rq) | Samples from what *surface water bodies* have a cumulative contamination result of above *20 ppt*? | sampled feature type, aggregate result value| [CQ4-result](CQ4-result.csv) | |
| [CQ5](./CQ5.rq) | What is the mean concentration of *PFOA* in *fish tissue* in *Maine*? | sample type, aggregate result value, geography | [CQ5-result](./CQ5-result.csv) |<ul><li> What is the mean concentration of *PFOA* in *shellfish* harvested in *Maine*? </li><li> Of fish samples in this area, which chemical is the highest by species? </li></ul>|
| [6]() | What was the detection limit of measurement XXXXXX? | | | |
| [7]() | What known *release points* exist in *this region*? | s2 cells, point type | | <ul><li> What suspected contamination sources exist above this aquifer?</li><li>How many suspected contamination sources are within a radius of two S2L13 cells of each well?</li></ul>|
| [8]() | What locations have had multiple reported PFAS releases over time? | | | |
| [9]() | Where did known contaminant releases occur in 2023? | | | |
| [10]() | 100 sample points with results | | | |
| [11]() | All surface water and fish tissue sample results from one samplepoint | | | |
| [12]()| Retrieve all sample points and count how many there are for each type of sample point | | | |
| [13]() | Retrieve all marine samplepoints and determine what and how many of each sample type are there | | | |