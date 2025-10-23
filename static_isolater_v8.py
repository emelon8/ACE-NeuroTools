#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import tifffile
import caiman as cm
from miniscope_api import MiniscopeAPI

# -------------- small helpers --------------
def to_dense(x):
    return x.toarray() if hasattr(x, "toarray") else np.asarray(x)

def destripe_rowcol(R):
    # subtract per-row and per-column medians per frame (display-only)
    Rc = R - np.median(R, axis=2, keepdims=True)
    Rc = Rc - np.median(Rc, axis=1, keepdims=True)
    # remove per-frame DC
    Rc = Rc - Rc.mean(axis=(1,2), keepdims=True)
    return Rc.astype(np.float32)

# -------------- 1) run / load CNMF-E --------------
api = MiniscopeAPI()
api.run(
    filenames=['0.avi'],
    line_num=97,
    run_CNMFE=True,
    save_estimates=True,
    remove_components_with_gui=False
)

cnmf_obj = api.miniscope_data_manager.CNMFE_obj
est = cnmf_obj.estimates

# same movie CNMF-E fit on
if api.miniscope_data_manager.preprocessed_movie_filepath:
    Y3 = cm.load(api.miniscope_data_manager.preprocessed_movie_filepath).astype(np.float32)
else:
    Y3 = np.asarray(api.miniscope_data_manager.movie, dtype=np.float32)

T, d1, d2 = Y3.shape
d = d1 * d2
Yr = Y3.reshape(T, -1).T  # (d, T)

# -------------- 2) residuals (Option A logic) --------------
# Always build AC; decide how to handle residuals based on b/f presence
A = to_dense(est.A)                  # (d, K)
C = np.asarray(est.C, np.float32)    # (K, T)
AC = (A @ C).T.reshape(T, d1, d2).astype(np.float32)

print(C.shape)

b = getattr(est, 'b', None)
f = getattr(est, 'f', None)

if (b is not None) and (f is not None):
    # We can optionally try compute_residuals, else fall back to manual
    try:
        est.compute_residuals(Yr=Yr)  # populates est.YrA (d, T) in many versions
        res_mat = None
        for attr in ("YrA", "residual", "R"):
            if hasattr(est, attr) and getattr(est, attr) is not None:
                res_mat = to_dense(getattr(est, attr))
                break
        if (res_mat is not None) and (res_mat.shape == (d, T)):
            R = res_mat.T.reshape(T, d1, d2).astype(np.float32)
        else:
            # manual fallback
            b_dense = to_dense(b).astype(np.float32)       # (d, nb)
            f_dense = np.asarray(f, np.float32)            # (nb, T)
            B = (b_dense @ f_dense).T.reshape(T, d1, d2).astype(np.float32)
            b0 = getattr(est, 'b0', None)
            if b0 is not None:
                B += np.asarray(b0, np.float32).reshape(1, d1, d2)
            R = (Y3 - AC - B).astype(np.float32)
    except Exception:
        # compute_residuals not usable; do manual residual
        b_dense = to_dense(b).astype(np.float32)
        f_dense = np.asarray(f, np.float32)
        B = (b_dense @ f_dense).T.reshape(T, d1, d2).astype(np.float32)
        b0 = getattr(est, 'b0', None)
        if b0 is not None:
            B += np.asarray(b0, np.float32).reshape(1, d1, d2)
        R = (Y3 - AC - B).astype(np.float32)
else:
    # Option A: if b or f is None (ring background case), skip compute_residuals and do manual
    B = np.zeros((T, d1, d2), dtype=np.float32)
    b0 = getattr(est, 'b0', None)
    if b0 is not None:
        B += np.asarray(b0, np.float32).reshape(1, d1, d2)
    R = (Y3 - AC - B).astype(np.float32)

# -------------- 3) save residuals --------------
tifffile.imwrite("v8_residual_raw.tif", R)

# (optional) add constant baseline back for a DC-included view
b0 = getattr(est, 'b0', None)
if b0 is not None:
    b0_im = np.asarray(b0, np.float32).reshape(1, d1, d2)
    tifffile.imwrite("v8_residual_plus_b0.tif", (R + b0_im).astype(np.float32))

# -------------- 4) de-striping view (display-only) --------------
R_clean = destripe_rowcol(R)
tifffile.imwrite("v8_residual_clean.tif", R_clean)

# -------------- 5) standardized view (optional) --------------
sn = getattr(est, 'sn', None)
if sn is not None:
    sn_map = np.asarray(sn, np.float32).reshape(d1, d2)
    Z = R_clean / (sn_map[None, :, :] + 1e-8)
    Z_view = np.clip(Z, -4, 4)
    Z_view = (Z_view - Z_view.min()) / (Z_view.max() - Z_view.min() + 1e-6)
    tifffile.imwrite("v8_residual_clean_standardized.tif", Z_view.astype(np.float32))

print("Saved:")
print("  v8_residual_raw.tif                 (manual residual when b/f None; else compute_residuals or fallback)")
if b0 is not None:
    print("  v8_residual_plus_b0.tif             (raw residual with b0 added back)")
print("  v8_residual_clean.tif               (row/col de-striped view)")
if sn is not None:
    print("  v8_residual_clean_standardized.tif  (de-striped & whitened by sn)")
