# AIML-02 — Model card

## Model

DenseNet-121 (ImageNet initialization) fine-tuned for multi-label chest X-ray classification. 14 NIH ChestX-ray14 findings, sigmoid outputs, BCEWithLogits loss. Trained on a Colab T4 in 561 seconds for 5 epochs (run `colab-nih-sample-001`).

Checkpoint: `artifacts/demo/model.pt` (28 MB, 7.05 M parameters). The serving wrapper uses `image_size=224`, ImageNet normalization, and a non-in-place forward pass so Grad-CAM can differentiate the feature map.

## Data

- Official NIH ChestX-ray14 **sample**: 5,606 frontal images, 14 labels, patient IDs.
- Patient-level split: 4,492 / 556 / 558 images (train / validation / test). No patient appears in two splits.
- Labels were mined from reports by the NIH authors; they are noisy. "No Finding" is not one of the 14 outputs.

## Metrics (test split, 593 evaluated rows)

| Metric | Value |
|---|---|
| Mean AUROC | **0.775** |
| Test rows | 593 |
| Backbone | DenseNet-121 |
| Epochs | 5 |
| Best validation mean AUROC | 0.750 |

Per-label AUROC:

| Finding | AUROC | Prevalence |
|---|---|---|
| Atelectasis | 0.767 | 8.9% |
| Cardiomegaly | 0.760 | 4.2% |
| Effusion | 0.830 | 14.2% |
| Infiltration | 0.690 | 18.2% |
| Mass | 0.684 | 5.4% |
| Nodule | 0.696 | 4.7% |
| Pneumonia | 0.608 | 1.2% |
| Pneumothorax | 0.814 | 5.7% |
| Consolidation | 0.800 | 6.1% |
| Edema | 0.883 | 2.7% |
| Emphysema | 0.853 | 2.2% |
| Fibrosis | 0.781 | 1.7% |
| Pleural_Thickening | 0.776 | 3.5% |
| Hernia | 0.912 | 0.17% |

## Thresholds

The checkpoint reports sensitivity/specificity at a fixed 0.5 cutoff. Sensitivity is near zero for most findings because of class imbalance — the model ranks well but is not calibrated at 0.5. The UI therefore ranks all 14 probabilities and highlights the top two; **per-label threshold calibration on the validation split is the next training task**. Do not read 0.5 as a clinical cutoff.

## Explanations

Grad-CAM is computed on the final convolutional feature map for the top two findings. It shows where the model looked, not where disease is. Sanity checks: finite values, expected shape, non-degenerate variance on demo studies. Randomized-weight and class-sensitivity tests are not yet automated.

## Intended use

Education and research demonstration of a DICOM → model → review pipeline on public data.

**Not for:** clinical diagnosis, triage, screening, or any decision affecting a patient.

## Limitations

Single dataset, sample subset, noisy labels, no external validation, no demographic bias analysis (NIH metadata is incomplete), no calibration, and a synthetic demo DICOM generator that is not representative of scanner variation.
