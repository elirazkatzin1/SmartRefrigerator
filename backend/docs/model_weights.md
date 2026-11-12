# Model weights

The trained detector, `detector.pt` (~5.5 MB), is **not in git**. Every training run produces a new
binary file, and git would keep all of them forever. It lives in `backend/storage/models/`, which is
in `.gitignore` together with every other `*.pt` file.

The current version is published as a file attached to a
[GitHub Release](https://github.com/elirazkatzin1/SmartRefrigerator/releases) whose tag starts with
`model`. The first one is `modelv1`; use `model-v2`, `model-v3`, ... from now on.

## Getting the current model

After cloning the repository (or when a new model is released):

```
cd backend
docker compose run --rm --no-deps web python -m scripts.download_detector
docker compose restart web
```

This downloads `detector.pt` from the newest `model` release into `storage/models/detector.pt`.
To get a specific version: `python -m scripts.download_detector --tag modelv1`.

The server loads the model on startup (`main.lifespan`). Without it the server still starts, logs a
warning and keeps receiving images, but detection does not work.

## Publishing a new model

After training a model that is better than the current one (`scripts/train_detector.py`, then
`scripts/evaluate_detector.py` to compare on the same test set):

1. On GitHub: **Releases** → **Draft a new release**.
2. **Choose a tag**: type the next version, e.g. `model-v2`, then click the
   **+ Create new tag: model-v2 on publish** line under the box (typing alone does not create the tag,
   and GitHub then fails with "tag name can't be blank"). Target: `main`.
3. **Title**: e.g. `Detector model v2`.
4. **Description**: what changed and the main results from `docs/model_evaluation.md`, for example:
   number of training images, test mAP@50, precision and recall, and the weakest classes.
5. Attach `backend/storage/models/detector.pt`. The file must be named exactly `detector.pt`.
6. **Publish release**.

The repository is public, so the release (and the model file) is public too. The model contains only
the learned weights, not the training images.
