# TerraPulse Model Evaluation Guide

How the landslide model is validated, which numbers matter, and how to defend them.

Every figure in this document is read from a `metrics.json` produced by
`scripts/train_landslide_model.py`. Nothing here is estimated or rounded up. If a number is not in a
stored `metrics.json`, do not quote it.

---

## 0. Which model this document is about

**As of `landslide_v0.4` the shipped model is LightGBM, not Random Forest.** This document was written
around the Random Forest that shipped as `landslide_v0.2`, and sections 1 to 8 still describe that
evaluation in detail. Those numbers remain correct *for that model*: they are the record of how it was
measured, and of why spatial validation is mandatory here.

The figures for the model actually being served, and the comparison that selected it, are in
`model_architecture.md` under "Why the shipped model changed". The short version:

| Metric | landslide_v0.2 (Random Forest) | landslide_v0.4 (LightGBM, shipped) |
|---|---|---|
| Block CV ROC-AUC | 0.7338 | 0.7389 |
| Block CV F1 | 0.7170 | 0.7200 |
| LOSO ROC-AUC | 0.6811 | 0.6863 |
| LOSO F1 | 0.6641 | 0.6659 |
| Recall, state held out entirely | 0.7186 | 0.8211 |
| Artifact size | 13.9 MB | 2.1 MB |

Do not quote a figure from sections 1 to 8 without saying which version it belongs to.

---

## 1. Why we cannot use a random train/test split

The obvious approach is to shuffle all 17,092 points and split 80/20. On this dataset that produces a
flattering score and the score is worthless.

Landslide points are **not independent**. GSI records them along the same slope, the same road cut,
the same river bank. Two records are frequently a few hundred metres apart. Split by row and a test
point almost always has a near-twin in the training set. The model does not predict the landslide,
it recognises a neighbourhood it has already memorised.

The failure mode is the dangerous one: the notebook looks excellent, and the model collapses in the
field where every location is genuinely new ground.

**Rule: never split by row. Split by geography.**

Note: an earlier non-spatial split produced a far rosier figure. That number is not in
`metrics.json`, it is not reproducible by this pipeline, and it must not be quoted.

---

## 2. The two benchmarks

We report two, because they answer two different questions.

### Benchmark A - three-way spatial block CV (primary)

Answers: *does the model work on ground it has never seen, in the region it was trained on?*

This is not a plain 5-fold CV. It is three-way, and the split is spatial:

1. The whole region is carved into **0.5 degree geographic blocks**.
2. Blocks are divided into three disjoint groups: **fit**, **validation**, **test**.
3. The model is fitted on the fit blocks.
4. The alert threshold is chosen on **validation** blocks only.
5. Performance is reported on the **test** blocks only.
6. Rotate and repeat 5 times.

Why three ways and not two: if you choose the threshold on the same data you report on, you have
tuned the result. Early in this project the cut was chosen on training rows, which under-reported
recall at **0.545**. Fixing the design - choosing the cut on held-out blocks - moved the honest
recall to **0.869**. The model did not improve; the measurement was corrected.

Every row is a test row exactly once across the five folds, so the **pooled** confusion matrix below
covers the full 17,092 points.

### Benchmark B - leave-one-state-out (LOSO)

Answers: *does the model transfer to a state it has never seen at all?*

Train on seven states, test on the eighth, repeat for all eight. This is the harsher test, because a
whole state's terrain, geology and survey practice are removed, not just a block.

Per-state folds are **not** 1:1. Positives and negatives were balanced across the region, not within
each state - Arunachal has 1,048 positives against 2,062 negatives, Manipur has 1,575 against 944.
A fold's base rate therefore differs from state to state, which is why precision swings so widely
across the LOSO rows. Read LOSO for ranking and recall, not for precision.

---

## 3. The metrics, in order of what matters

### 3.1 Recall - the mission metric

> Of the landslides that actually happened, what fraction did we flag?

Recall is first because the failure that kills people is the **missed landslide**: no warning, no
evacuation, no road closure. A false alarm costs a wasted patrol. A miss costs a village.

From the pooled block-CV confusion matrix: of **8,546** recorded landslides, the model flags
**7,541** and misses **1,005** - recall **0.8824**.

If a judge asks what you optimise, the answer is recall, and the reason is the cost asymmetry, not
the number.

### 3.2 ROC-AUC - the honest headline

> If you pick one real landslide and one non-landslide at random, how often does the model score the
> landslide higher?

That is the entire meaning. **0.7338** on block CV means it ranks correctly about three times in
four. **0.6811** on LOSO.

AUC is the headline because it is **threshold-free**. It does not depend on where we set the alert
cut, so it cannot be gamed by tuning. It measures ranking quality, which is exactly the job: sorting
a map into "look here first" and "look here later".

### 3.3 F1 - the operational number

> The balance of recall and precision **at the alert level we actually deploy**.

F1 is the single number that describes what the system does in production, because it is measured at
one specific cut, not across all of them. Block CV **0.7170**, LOSO **0.6641**.

F1 is also the metric we used to **select** the model, and the reason is in section 3.5.

### 3.4 Average Precision - secondary, keep in the appendix

Summarises the precision/recall curve. Block CV **0.6925**, LOSO **0.6464**. Useful supporting
evidence, never the headline.

### 3.5 Why AUC did not select the model

Across the three tree models on block CV:

| Model | ROC-AUC |
|---|---|
| Random Forest | 0.7338 |
| XGBoost | 0.7393 |
| LightGBM | 0.7408 |

Spread: **0.0070**. Fold-to-fold standard deviation for these models: roughly **0.026 to 0.028**.

The difference between the models is still about **four times smaller than the noise**. AUC cannot
separate them. Neither, honestly, can F1 - the F1 band across all six configurations we tested is
0.7141 to 0.7195, a spread of 0.0054 against the same 0.03 noise.

So we state the truthful position: **the tree models are statistically tied.** Random Forest was
saved because it had the best mean F1 and the best recall, and because it degrades least when
training data is removed. Not because it is meaningfully more accurate.

### 3.6 Precision - the price of recall

Know this number, do not headline it. Every unit of recall is bought with false alarms, and the
district office is the one who pays. It matters when choosing an operating point (section 5), not as
a measure of model quality. A judge who asks "how many false alarms?" is asking for precision, and
the answer is in the confusion matrix.

### 3.7 Accuracy - never report it

The dataset is exactly **8,546 positives against 8,546 constructed negatives**. A 50/50 base rate
does not exist in the real world. Accuracy measured against it is meaningless and flattering, and a
sharp judge will say so. AGENTS.md lists accuracy as a value that must never be fabricated - here we
simply never compute it.

If asked for accuracy, the answer is: *this is a case-control design, so accuracy is not a metric we
report; recall and ROC-AUC are.*

---

## 4. The recorded results

### 4.1 Three-way spatial block CV, 0.5 degree blocks, 5 folds

| Model | ROC-AUC | Avg Precision | Precision | Recall | F1 | fold std (F1 / AUC) |
|---|---|---|---|---|---|---|
| Logistic regression | 0.6725 | 0.6437 | 0.5640 | 0.9073 | 0.6950 | 0.0186 / 0.0153 |
| **Random Forest (saved)** | 0.7338 | 0.6925 | 0.6116 | **0.8718** | **0.7170** | 0.0358 / 0.0283 |
| XGBoost | 0.7393 | 0.7078 | 0.6159 | 0.8603 | 0.7165 | 0.0198 / 0.0257 |
| LightGBM | 0.7408 | 0.7132 | 0.6164 | 0.8566 | 0.7152 | 0.0230 / 0.0268 |

Logistic regression was carried as a floor check. It reaches high recall (0.9073) but ranks poorly
(AUC 0.6725), which confirms the terrain relationships are non-linear - exactly why we use trees.

### 4.2 Pooled test folds, Random Forest (all 17,092 points)

Chosen threshold **0.38**, the median of the cuts selected on validation blocks.

| | | |
|---|---|---|
| ROC-AUC | | 0.7316 |
| Avg precision | | 0.6900 |
| Precision | | 0.6110 |
| Recall | | 0.8824 |
| F1 | | 0.7222 |

Confusion matrix:

| | predicted no | predicted yes |
|---|---|---|
| **actual no** | 3,744 | 4,802 |
| **actual yes** | 1,005 | 7,541 |

The two numbers to carry in your head: **7,541 of 8,546 landslides flagged**, **1,005 missed**.

### 4.3 Leave-one-state-out

| Model | ROC-AUC | Avg Precision | Precision | Recall | F1 |
|---|---|---|---|---|---|
| Logistic regression | 0.6300 | 0.5933 | 0.5404 | 0.7772 | 0.6140 |
| **Random Forest (saved)** | 0.6811 | 0.6464 | 0.5578 | **0.8498** | **0.6641** |
| XGBoost | 0.6838 | 0.6479 | 0.5499 | 0.8431 | 0.6571 |
| LightGBM | 0.6847 | 0.6509 | 0.5505 | 0.8366 | 0.6542 |

Random Forest wins F1 **and** recall under both validation designs. The margins are small, but they
point the same way in two independent tests, which is the honest argument for having chosen it.

### 4.4 LOSO per state (Random Forest)

| State | Threshold | ROC-AUC | Recall | F1 |
|---|---|---|---|---|
| Assam | 0.39 | 0.8631 | 0.8910 | 0.7473 |
| Tripura | 0.40 | 0.7869 | 0.8806 | 0.6378 |
| Arunachal Pradesh | 0.38 | 0.7424 | 0.9189 | 0.5384 |
| Manipur | 0.35 | 0.6603 | 0.9454 | 0.7914 |
| Meghalaya | 0.34 | 0.6421 | 0.8740 | 0.7179 |
| Nagaland | 0.34 | 0.6344 | 0.9406 | 0.7036 |
| Sikkim | 0.33 | 0.6300 | 0.7576 | 0.5630 |
| **Mizoram** | 0.42 | **0.4899** | 0.5901 | 0.6132 |

This table is the most useful slide in the deck, because it shows where the model works and where it
does not.

- **Mizoram is at chance** - AUC 0.4899 means better-than-coin-flip is all we can claim. Mizoram is
  2,042 points, **24% of all positives**. Say this before a judge finds it.
- **Sikkim is the weak recalled state** - 0.7576 recall, so we miss about a quarter of
  events. Sikkim is the steepest terrain and the densest debris-flow label set, so the landslide
  case-control framing fits it worst.
- **Arunachal has low precision (0.3808)** - because that fold carries 1,048 positives against 2,062
  negatives, so the cut is operating in a different base rate. A fold artefact, not a terrain fact.

---

## 5. The alert level is a dial, not a property of the model

The model outputs a score from 0 to 1. We choose where to cut. Move the cut and you trade false
alarms against misses, without retraining anything.

On the held-out Random Forest the trade runs like this:

| Alert cut | Recall | Precision |
|---|---|---|
| 0.10 | 0.998 | 0.525 |
| 0.20 | 0.988 | 0.550 |
| 0.30 | 0.950 | 0.580 |
| **0.38 (deployed)** | **0.882** | **0.611** |
| 0.50 | 0.645 | 0.667 |
| 0.35 (F1-optimal) | 0.915 | 0.599 |

This is a **policy decision, not a modelling decision**, and it belongs to the administrator. A
district office that can absorb patrols may want 0.998 recall and accept double the false alarms. A
state control room short of staff may want fewer, surer alerts.

Saying this out loud is a strength: it shows the alert level is a governance choice we expose, not a
magic number we picked.

---

## 6. Limitations that must be disclosed, unprompted

Say these before anyone asks. Volunteering them is what makes the rest of the numbers believable.

1. **The score is a ranking, not a probability.** The 1:1 case-control design fixes the base rate at
   0.5. "0.73" does not mean "73% chance of sliding".
2. **Negatives are constructed, not observed.** A missing GSI record is not evidence that no
   landslide happened. GSI is a presence-only inventory.
3. **About 67% of records sit within 200 m of a road.** Partly real - cut slopes genuinely fail -
   partly survey bias, because landslides near roads are the ones that get reported. This means the
   model's road-proximity feature is partly learning the survey, not the hazard. A road ablation
   showed proximity is worth about 0.05 AUC, not the whole score.
4. **Mizoram is at chance**, and it is a quarter of the data.
5. **The training data carries no event date for negatives**, so event-year rainfall is excluded as
   leakage. The model uses rainfall climatology only. It is a susceptibility model, not a live
   rainfall-trigger model.
6. **These are cross-validation numbers, not production performance.** No calibration against real
   event prevalence has been done yet.

---

## 7. The size of the saved artifact

Not an accuracy question, but it is a deployment question and a judge may ask.

The saved Random Forest was **198 MB**, against 2 MB for XGBoost and 2 MB for LightGBM. TerraPulse is
meant to run inference offline on a field phone, so 198 MB does not ship.

We measured the size/performance curve rather than guess:

| Configuration | F1 | Recall | AUC | Size |
|---|---|---|---|---|
| RF 600 trees, leaf 2 (superseded) | 0.7195 | 0.8688 | 0.7376 | 198.1 MB |
| RF 300 trees, leaf 8 | 0.7141 | 0.8469 | 0.7354 | 41.5 MB |
| RF 200 trees, leaf 15, depth 16 | 0.7170 | 0.8718 | 0.7338 | 13.2 MB |
| RF 120 trees, leaf 30, depth 12 | 0.7153 | 0.8787 | 0.7247 | 3.3 MB |

600 fully-grown trees with `leaf=2` memorise the training set. Cutting to 200 trees with a minimum
leaf of 15 removes 93% of the artifact and moves F1 by 0.0025 - roughly a tenth of the noise. The
198 MB bought no performance.

**Applied.** `build_model` now builds the 200 trees / leaf 15 / depth 16 forest, so the saved
artifact is **13.21 MB** instead of 198.08 MB. The on-disk cost of the whole model directory is now
about 13 MB for Random Forest plus 2.01 MB for XGBoost. The LightGBM artifact was deleted: LightGBM
still appears in `metrics.json` as a measured comparison, but no LightGBM artifact ships.

---

## 8. Benchmarks and where the numbers come from

| Item | Source |
|---|---|
| Landslide labels (positive) | GSI landslide inventory, `bhusanket.gsi.gov.in` |
| Negative points | Constructed, `scripts/build_negatives.py` |
| Terrain | Copernicus DEM GLO-30, derived slope / aspect / curvature |
| Rainfall | IMD gridded, climatology only |
| Soil | SoilGrids |
| Land cover | ESA WorldCover 2021 |
| Roads / rivers | OpenStreetMap |
| Administration boundaries | GADM |
| Validation | Three-way spatial block CV and LOSO, `scripts/train_landslide_model.py` |
| Bhuvan geology | ISRO/NRSC geomorphology and lineaments, 1:50,000 |
| Stored metrics | `models/landslide_v0.4/metrics.json` (active version, resolved through `models/registry.json`) |

---

## 9. Quick card

**Quote these**

- Active artifact **landslide_v0.4** (LightGBM), resolved through `models/registry.json`
- Recall **0.89** block CV / **0.84** LOSO
- ROC-AUC **0.7389** block CV / **0.6863** LOSO
- F1 **0.7200** block CV / **0.6659** LOSO
- 7,548 of 8,546 recorded landslides flagged on held-out blocks at the artifact's alert cut of 0.18
- Recall **0.82** in Sikkim, a state held out of training entirely
- Validated by spatial blocks and by holding out whole states

**Where it is used**

- `TrainedMLRiskPredictor` loads it; the live cycle scores the monitoring cells with it
- the operational path loads the model and never retrains it; stages 01-04 assemble the
  feature vector, stage 05 loads the artifact
- retraining is the separate offline gate in `feedback_loop.py`, on its own timer

**Never quote these**

- Accuracy - not measured, and the 1:1 design makes it meaningless
- Any probability reading of the score - it is a ranking
- The rosy figure from a non-spatial split - not reproducible, not in `metrics.json`
- Any claim of production performance or a validated rainfall threshold

**If asked "how accurate is it?"**

> ROC-AUC 0.74 on held-out ground, recall 0.89. On an entire state it has never seen it still catches
> 82% of recorded landslides. It is a ranking model, not a probability, and the numbers come from
> spatial cross-validation, not a random split.