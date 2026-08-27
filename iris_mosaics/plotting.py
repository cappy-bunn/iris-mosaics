"""Shared diagnostic plots.

``plot_lines_sidebyside`` was defined identically in most of the pipeline
notebooks; it lives here now so a change to it applies everywhere.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.axes_grid1 import ImageGrid


def plot_lines_sidebyside(
    si_iv_1394,
    si_iv_1403,
    title: str = "",
    percentile_min: float = 0,
    percentile_max: float = 100,
    size: tuple = (5, 5),
    exp_min=None,
    exp_max=None,
    cbar_label: str = "DN",
):
    """Show the Si IV 1394 and 1403 regions side by side on a shared scale.

    The scale is taken from the 1394 image (via ``exp_min``/``exp_max``, or the
    given percentiles) and applied to both, so the two are directly comparable.
    """
    fig = plt.figure(figsize=size)
    grid = ImageGrid(
        fig,
        111,
        nrows_ncols=(1, 2),
        axes_pad=0.15,
        cbar_location="right",
        cbar_mode="single",
        cbar_size="20%",
        cbar_pad=0.15,
    )

    if exp_min is None:
        exp_min = np.nanpercentile(si_iv_1394, percentile_min)
    if exp_max is None:
        exp_max = np.nanpercentile(si_iv_1394, percentile_max)

    grid[0].imshow(si_iv_1394, vmin=exp_min, vmax=exp_max)
    im2 = grid[1].imshow(si_iv_1403, vmin=exp_min, vmax=exp_max)
    grid[0].set_title("1394 Å")
    grid[1].set_title("1403 Å")
    fig.suptitle(title)

    grid[~0].cax.colorbar(im2).set_label(cbar_label, rotation=270)
    grid[0].invert_yaxis()
    return fig
