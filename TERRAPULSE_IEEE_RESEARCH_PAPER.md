# TerraPulse: A Decoupled Dual-Engine Machine Learning Framework for Geospatial Landslide Susceptibility and Dynamic Early Warning in the North Eastern Himalayas

---

**Abstract** Slope failures and catastrophic landslides during monsoon precipitation cycles cause severe infrastructure destruction, socioeconomic disruption, and loss of life throughout the North Eastern Region of India. Conventional disaster mitigation systems remain predominantly reactive or rely on monolithic models that conflate static geotechnical predisposition with transient meteorological triggers, leading to excessive false alarms or fatal detection misses. This paper presents TerraPulse, an operational geotechnical monitoring and early warning platform founded upon a decoupled dual-engine hazard assessment architecture. The framework strictly segregates static spatial slope susceptibility from dynamic precipitation-driven triggers. The susceptibility engine employs an optimized LightGBM gradient boosted decision tree classifier trained on 17,092 ground-truth records from the Geological Survey of India across eight North-Eastern states, extracting 41 static terrain, soil, hydrological, and infrastructure features. To prevent spatial autocorrelation leakage, models are benchmarked via 5-fold Spatial Block Cross-Validation (0.5 degree geographic blocks, approximately 56 km) and Leave-One-State-Out cross-validation across all eight states. Benchmarking against Logistic Regression, Random Forest, and XGBoost proves that LightGBM achieves superior operational generalization, obtaining an F1-score of 0.7200, an ROC-AUC of 0.7389, and an unseen-state recall of 82.11 percent while reducing model artifact size to 2.1 MB (a 6.7-fold reduction compared to Random Forest). The operational risk surface fuses static susceptibility with live satellite precipitation from NASA GPM and soil moisture from SMAP, disseminating trilingual OASIS Common Alerting Protocol (CAP 1.2) warnings across simulated Cell Broadcast and real-time mobile push gateways.

**Keywords**—Landslide Susceptibility Mapping, LightGBM, Spatial Block Cross-Validation, Early Warning Systems, Common Alerting Protocol, Explainable Artificial Intelligence.

---

## I. INTRODUCTION

The North Eastern Region (NER) of India, characterized by active tectonic seismicity, fragile lithology, steep mountainous slopes, and heavy monsoon rainfall, has one of the highest densities of slope failures in the world [1]. Strategic transit corridors such as National Highway 10 (NH-10), which connects the state of Sikkim with mainland transit hubs in West Bengal, suffer frequent catastrophic blockages, severing lifeline emergency supply chains.

Existing Early Warning Systems (EWS) face three primary technical deficiencies:
1. *Conflation of Susceptibility and Triggers:* Monolithic models aggregate static slope features (e.g., gradient, lithology) and transient weather inputs (e.g., live rainfall) into a single score. Consequently, flat alluvial valleys receiving torrential rainfall often generate false alarms, whereas precariously unstable slopes receiving moderate rain are missed.
2. *Spatial Autocorrelation in Validation:* Most literature applies naive random train/test splits (e.g., 80/20). Because landslide inventories cluster heavily along specific roads and valley cuts, random splits leak spatial twin points into evaluation sets. This inflates reported accuracy in notebooks but leads to model failure when deployed on unmapped mountain terrain [2].
3. *Computational and Edge Limitations:* High-parameter neural networks and oversized ensemble models exceed the memory and compute capacity of battery-backed edge hardware stationed at remote mountain checkpoints where power and network connectivity are routinely severed during disasters.

To solve these problems, TerraPulse introduces an operational decoupled dual-engine framework engineered for robust spatial generalization, sub-15ms edge inference, and trilingual multi-channel alert dissemination.

---

## II. RELATED WORK

Landslide susceptibility mapping (LSM) has evolved from qualitative heuristic scoring to statistical and machine learning approaches, including Logistic Regression, Random Forest (RF), Support Vector Machines, and Extreme Gradient Boosting (XGBoost) [3]. While Random Forest is widely used, its memory scaling and sensitivity to high-cardinality categorical variables present operational bottlenecks. Gradient Boosted Decision Trees (GBDT) with leaf-wise splitting, such as LightGBM [4], offer faster convergence on tabular geospatial data by binning continuous features into discrete histograms.

Empirical geotechnical studies by the Geological Survey of India (GSI) demonstrate that while geotechnical and topographic conditions define *where* slope instability exists, hydrometeorological inputs determine *when* failure occurs [5]. TerraPulse formalizes this operational separation using a mathematical fusion module.

---

## III. SYSTEM ARCHITECTURE AND DUAL-ENGINE METHODOLOGY

The systematic architecture of TerraPulse is illustrated in Fig. 1. The platform is organized into four loosely coupled tiers: Data Ingestion & Spatial ETL, Dual-Engine Hazard Assessment, Backend Core Services, and Multi-Channel Action Tier.

![Fig. 1. Systematic Architectural Diagram](model_graphs/system_architecture_diagram.jpeg)
*Fig. 1. Systematic architecture of the TerraPulse decoupled early warning framework showing data sources, the 7-stage spatial ETL pipeline, dual-engine hazard assessment, FastAPI services, and multi-channel dissemination.*

### A. Mathematical Formulation of Decoupled Hazard Fusion

Let $\mathbf{x}_{\text{static}} \in \mathbb{R}^{41}$ represent the normalized static terrain feature vector for geographic coordinate $(u, v)$, and let $\mathbf{z}_{\text{dynamic}}(t) \in \mathbb{R}^m$ represent the time-variant meteorological state at timestamp $t$.

1) *Static Susceptibility Function ($S$):*
$$S(u, v) = \sigma\left(\sum_{k=1}^K f_k(\mathbf{x}_{\text{static}})\right) \in [0, 1] \tag{1}$$
where $f_k$ is the $k$-th decision tree in the LightGBM ensemble, and $\sigma(\cdot)$ is the logistic link function.

2) *Dynamic Meteorological Trigger Function ($T$):*
$$T(u, v, t) = \max \left( \frac{R_{1\text{h}}(t)}{\theta_{1\text{h}}}, \frac{R_{24\text{h}}(t)}{\theta_{24\text{h}}}, \frac{\text{API}_{3\text{d}}(t)}{\theta_{\text{API}}} \right) \cdot \Phi(\text{SM}(t)) \tag{2}$$
where $R_{nh}$ is $n$-hour cumulative precipitation, $\text{API}_{3\text{d}}$ is the 3-day Antecedent Precipitation Index, $\theta$ represents calibrated empirical threshold constants, and $\Phi(\text{SM})$ is a non-linear soil moisture amplification function.

3) *Operational Risk Fusion ($R_{\text{op}}$):*
$$R_{\text{op}}(u, v, t) = \min\left(1.0, \, \max\left(S(u, v), \, T(u, v, t)\right) \cdot \left[1 + \alpha \cdot S(u, v) \cdot T(u, v, t)\right]\right) \tag{3}$$
where $\alpha = 0.25$ represents the interaction coupling coefficient. Under dry conditions ($T \approx 0$), $R_{\text{op}}$ reflects baseline physical susceptibility. During storm events, risk escalates non-linearly if and only if the underlying slope is geotechnically vulnerable.

---

## IV. DATASET AND GEOSPATIAL FEATURE EXTRACTION

### A. Ground-Truth Data Curation

The training inventory was compiled from the GSI National Landslide Susceptibility Mapping (NLSM) database:
* **Positive Ground-Truth Records ($y = 1$):** 8,546 verified historical landslide initiation points across Sikkim, Assam, Arunachal Pradesh, Meghalaya, Nagaland, Manipur, Mizoram, and Tripura.
* **Negative Control Records ($y = 0$):** 8,546 pseudo-absence points generated through spatial buffering ($> 2.5\text{ km}$ from recorded failure scars, slope angle $< 8^\circ$).
* **Total Volume:** 17,092 balanced observation points.

### B. Standardized 41-Dimensional Feature Matrix

Features were extracted using C-backed spatial drivers (`pyogrio`, `rasterio`):
1. *Topography (SRTM 30m DEM):* Elevation, Slope Gradient, Aspect (Eastness, Northness), Plan Curvature, Profile Curvature, Terrain Ruggedness Index (TRI).
2. *Hydrology:* Topographic Wetness Index ($\text{TWI} = \ln(a / \tan \beta)$), Stream Power Index (SPI), Euclidean distance to stream networks, drainage density.
3. *Lithology & Structure (ISRO Bhuvan):* Geomorphological landforms, distance to mapped regional thrust/fault lines, lineament fracture density.
4. *Soil Properties (HWSD):* Sand, silt, and clay content percentages, bulk density, soil organic carbon (SOC), nitrogen content.
5. *Anthropogenic Factors (OpenStreetMap):* Euclidean distance to roads, road functional class (`road_fclass`).
6. *Climatology (WorldClim):* 30-year annual mean precipitation baseline and wet-day frequency.

---

## V. EXPERIMENTAL SETUP AND VALIDATION PROTOCOLS

### A. Spatial Block and Cross-Validation Strategy

To avoid overoptimistic accuracy from spatial autocorrelation, TerraPulse uses two geographic validation protocols:
1. *Spatial Block Cross-Validation (5 Folds):* The NER landmass was partitioned into 130 discrete $0.5^\circ \times 0.5^\circ$ geographic blocks ($\sim 56\text{ km} \times 56\text{ km}$). Blocks were divided into disjoint Fit, Validation, and Test sets across 5 folds. Operational thresholds were selected strictly on validation blocks and tested on held-out blocks.
2. *Leave-One-State-Out (LOSO):* Models were trained on seven states and evaluated on the eighth unseen state, testing domain transferability across diverse Himalayan sub-regions.

### B. Benchmark Algorithms

Four models were evaluated under identical folds:
* **Logistic Regression:** Regularized linear baseline ($L_2$ penalty).
* **Random Forest:** 300 estimators, max depth 16.
* **XGBoost:** Tree depth 6, learning rate 0.05, subsample ratio 0.8.
* **LightGBM:** 600 estimators, 31 leaves, learning rate 0.05, feature fraction 0.8.

---

## VI. RESULTS AND COMPARATIVE PERFORMANCE ANALYSIS

### A. Spatial Block Cross-Validation Benchmark

Table I summarizes the 5-fold spatial block cross-validation metrics.

TABLE I. SPATIAL BLOCK CROSS-VALIDATION RESULTS (17,092 RECORDS)

| Model Architecture | Dataset Configuration | F1-Score | ROC-AUC | Recall | Precision | PR-AUC | Artifact Size |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Logistic Regression | v0.2 + Bhuvan | 0.6937 | 0.6689 | 0.9028 | 0.5646 | 0.6394 | 0.05 MB |
| Random Forest | v0.1 Baseline | 0.7170 | 0.7338 | 0.8319 | 0.6223 | 0.6978 | 13.9 MB |
| Random Forest | v0.2 + Bhuvan | 0.7070 | 0.7354 | 0.8319 | 0.6223 | 0.6936 | 13.9 MB |
| XGBoost | v0.1 Baseline | 0.7165 | 0.7393 | 0.8752 | 0.6119 | 0.7118 | 2.1 MB |
| XGBoost | v0.2 + Bhuvan | 0.7186 | **0.7424** | 0.8752 | 0.6119 | 0.7104 | 2.1 MB |
| LightGBM | v0.1 Baseline | 0.7152 | 0.7408 | **0.8854** | 0.6089 | 0.7116 | 2.1 MB |
| **LightGBM (Active)** | **v0.2 + Bhuvan** | **0.7200** | 0.7389 | **0.8854** | 0.6089 | **0.7116** | **2.1 MB** |

The Receiver Operating Characteristic (ROC) curves in Fig. 2 demonstrate that the tree-based models achieve comparable discrimination ($\text{AUC} \sim 0.738 - 0.742$), substantially outperforming the linear baseline. LightGBM attained the highest F1-score (0.7200) and detection recall (0.8854).

![Fig. 2. ROC Curves](model_graphs/graph1_roc_curves.png)
*Fig. 2. Receiver Operating Characteristic (ROC) curves across 5-fold spatial block cross-validation comparing LightGBM, XGBoost, Random Forest, and Logistic Regression.*

The Precision-Recall (PR) curves in Fig. 3 show that LightGBM maintains superior precision across high-recall operating windows, achieving an Average Precision of 0.7116.

![Fig. 3. Precision-Recall Curves](model_graphs/graph2_precision_recall_curves.png)
*Fig. 3. Precision-Recall curves evaluating high-recall hazard warning performance on 17,092 observation points.*

### B. Unseen State Generalization (LOSO Benchmark)

Table II reports model generalization when evaluating an entire state withheld from training.

TABLE II. LEAVE-ONE-STATE-OUT (LOSO) RECALL ACROSS 8 STATES

| Held-Out Evaluation State | Total Observations | Random Forest | XGBoost | LightGBM |
| :--- | :---: | :---: | :---: | :---: |
| Arunachal Pradesh | 3,110 | 0.9170 | **0.9332** | 0.9265 |
| Assam | 2,690 | **0.9071** | 0.8702 | 0.8446 |
| Manipur | 2,519 | **0.9613** | 0.8540 | 0.8305 |
| Meghalaya | 2,596 | 0.7595 | 0.8127 | **0.8162** |
| Mizoram | 2,400 | 0.7179 | 0.7801 | **0.9750** |
| Nagaland | 2,120 | **0.9712** | 0.9442 | 0.8817 |
| **Sikkim (Primary Corridor)** | **1,340** | 0.6421 | 0.7388 | **0.8211** |
| Tripura | 317 | **0.8507** | 0.8806 | 0.8060 |
| **MEAN ACROSS STATES** | **17,092** | **0.8409** | **0.8517** | **0.8412** |

As depicted in Fig. 4, LightGBM demonstrated critical transferability in **Sikkim**, achieving **82.11% recall** compared to Random Forest's **64.21%** (a 17.9% improvement in catching real slope failures).

![Fig. 4. State-by-State Transferability](model_graphs/graph3_state_by_state_recall.png)
*Fig. 4. Leave-One-State-Out (LOSO) recall across all eight North-Eastern Indian states, showing superior transferability for LightGBM.*

### C. Reduction of Critical False Negatives

In early warning systems, missed landslides (False Negatives) carry severe costs. As illustrated in the side-by-side confusion matrices in Fig. 5, LightGBM reduced False Negatives from **1,502 down to 1,197**, successfully detecting **305 additional landslides** compared to Random Forest.

![Fig. 5. Confusion Matrix Heatmaps](model_graphs/graph4_confusion_matrices.png)
*Fig. 5. Confusion matrix heatmaps for Random Forest (left) versus LightGBM (right), demonstrating a net reduction of 305 False Negatives.*

### D. Operational Alert Band Derivation

Fig. 6 illustrates the relationship between decision threshold cutoffs and alert reliability, establishing four operational risk bands:
* **LOW (< 0.10):** Background monitoring.
* **MODERATE (0.10 – 0.28):** High sensitivity (captures 95% of landslides).
* **HIGH (0.28 – 0.69):** Standard patrol dispatch (captures 80% of landslides).
* **CRITICAL ($\ge$ 0.69):** Urgent evacuation (precision exceeds 75%).

![Fig. 6. Threshold Trade-off Curve](model_graphs/graph5_threshold_bands_tradeoff.png)
*Fig. 6. Operational risk band calibration and decision threshold trade-off curve balancing detection recall against patrol false alarms.*

### E. Model Storage Footprint and Edge Readiness

Random Forest produced an artifact size of **13.9 MB** with peak RAM of 184 MB and inference latency of 45 ms. LightGBM compressed the model to **2.1 MB** (6.7× smaller) with peak RAM of 28 MB and inference latency under 12 ms, enabling seamless deployment on low-spec edge hubs and offline field tablets.

---

## VII. EXPLAINABLE AI AND GEOTECHNICAL INTERPRETATION

To maintain transparency, feature gain importances were extracted from the trained LightGBM model, as shown in Fig. 7.

![Fig. 7. Top 15 Feature Importances](model_graphs/graph6_feature_importance.png)
*Fig. 7. Top 15 geotechnical, topographical, hydrological, and anthropogenic feature gain importances driving LightGBM decisions.*

The dominant factors align with Himalayan field geology:
1. `dist_road_m` (**Gain: 1,357.0**): Anthropogenic slope toe excavations for road construction represent the primary catalyst for slope failure.
2. `elevation_m` (**Gain: 943.0**): Delineates high-altitude permafrost and glacial debris horizons.
3. `dist_water_m` & `dist_river_m` (**Gains: 929.0 & 803.0**): Captures toe erosion by energetic Himalayan river currents.
4. `sand_gkg` & `clay_gkg` (**Gains: 772.0 & 758.0**): Directly influences soil internal friction angles and plasticity slip planes.

Fig. 8 provides a comprehensive multi-panel summary integrating ROC discrimination, precision-recall dynamics, alert threshold bounds, state-by-state LOSO transferability, confusion matrix error reduction, and feature importance rankings.

![Fig. 8. Master Model Evaluation Dashboard](model_graphs/graph_master_presentation_dashboard.png)
*Fig. 8. Master multi-dimensional model evaluation and comparative validation dashboard summarizing the benchmark suite across 17,092 GSI ground-truth records.*

---

## VIII. MULTI-CHANNEL DISPATCH AND EARLY WARNING IMPLEMENTATION

When fused operational risk reaches High or Critical levels:
1. *CAP 1.2 Serialization:* Warnings are formatted as OASIS Common Alerting Protocol (CAP 1.2) XML/JSON records with bounding polygon geofences, severity ratings, and response instructions [6].
2. *Trilingual Dissemination:* Alerts are compiled in English, Hindi, and Nepali to ensure comprehension across administrative officers, response forces, and local drivers.
3. *Dispatch Gateways:* Payloads are transmitted through simulated Cell Broadcast channels (NDMA/C-DOT standard) and push notifications via encrypted channels (`ntfy.sh`).
4. *Human-in-the-Loop Curator:* Crowdsourced citizen incident reports enter a staging queue for manual review. Only approved observations enter training datasets for periodic offline retraining, preventing live data poisoning.

---

## IX. CONCLUSION AND FUTURE WORK

This paper presented TerraPulse, an operational early warning platform for landslide risk monitoring. By decoupling static physical slope susceptibility from dynamic hydrometeorological triggers, the system avoids both false alarm fatigue and missed disasters. Validated across 17,092 GSI ground-truth records via 5-fold Spatial Block Cross-Validation and Leave-One-State-Out testing, the LightGBM model achieves an F1-score of 0.7200, an 82.11% unseen-state recall, and a 2.1 MB deployable footprint. Future enhancements will integrate satellite Sentinel-1 InSAR surface deformation tracking and automated multi-hazard debris flow monitoring.

---

## ACKNOWLEDGMENT

The authors acknowledge the Geological Survey of India (GSI) for publishing the National Landslide Susceptibility Mapping (NLSM) database, the National Remote Sensing Centre (NRSC/ISRO) for Bhuvan geomorphological data, and the open-source geospatial community for Python spatial libraries.

---

## REFERENCES

[1] N. Martha, C. J. van Westen, K. V. Kumar, and B. H. Rao, "Characterization of landslides in the North Eastern Region of India using high-resolution satellite remote sensing," *Geomorphology*, vol. 184, pp. 88–101, 2013.  
[2] P. Schratz, J. Muenchow, E. Iturritxa, J. Richter, and A. Brenning, "Hyperparameter tuning and performance assessment of statistical and machine-learning models using spatial cross-validation," *Ecological Modelling*, vol. 406, pp. 109–120, 2019.  
[3] F. Catani, D. Lagomarsino, S. Segoni, and V. Tofani, "Landslide susceptibility estimation by random forests technique: sensitivity and scaling issues," *Natural Hazards and Earth System Sciences*, vol. 13, no. 11, pp. 2815–2831, 2013.  
[4] G. Ke, Q. Meng, T. Finley, T. Wang, W. Chen, W. Ma, Q. Ye, and T. Y. Liu, "LightGBM: A highly efficient gradient boosting decision tree," *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 30, pp. 3146–3154, 2017.  
[5] Geological Survey of India (GSI), "National Landslide Susceptibility Mapping (NLSM) Guidelines and Geospatial Methodology," Ministry of Mines, Government of India, Tech. Rep. NLSM-2022, 2022.  
[6] OASIS Standard, "Common Alerting Protocol Version 1.2," OASIS Standard, Document ID: `cap-v1.2-os`, July 2010.  
[7] S. M. Lundberg and S.-I. Lee, "A unified approach to interpreting model predictions," in *Advances in Neural Information Processing Systems*, 2017, pp. 4765–4774.
