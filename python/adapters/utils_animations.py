import logging
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
import time
from typing import Any

from domain.enums import ACBoardType


logger = logging.getLogger("utils_animations")


def ac_animate_boards(
        region: str,
        data_store: dict[str, Any],
        frame_step: int = 1,
        interval_ms: int = 120,
) -> str:
    """
    Genera la animación HTML interactiva de la evolución espacial de los tableros del modelo SIR.
    """

    first_snapshots = data_store.get("frames_snapshots")
    if not first_snapshots:
        raise RuntimeError("Primero debes ejecutar ac_run_evolution_parallel(xp, ac_data_store).")

    frame_indices = list(range(0, len(first_snapshots), max(1, frame_step)))

    fig, axes = plt.subplots(
        nrows=2,
        ncols=5,
        figsize=(max(4.0, 2.8 * 5), max(3.5, 2.7 * 2)),
        dpi=72,
        squeeze=False,
    )

    init_date_str = first_snapshots[0]["fecha"].strftime("%b %Y")
    suptitle_obj = fig.suptitle(f"{region} — {init_date_str}", fontsize=12, fontweight="bold")

    # Precalcular vmax por cada par (entidad, tablero) para mantener la escala de color estable
    plot_items: list[tuple[Any, str]] = []

    for ax in axes.flat:
        ax.set_xticks([])
        ax.set_yticks([])

    selected_boards = list(ACBoardType)

    snaps = data_store["frames_snapshots"]
    for idx, b_type in enumerate(selected_boards):
        r, c = divmod(idx, 5)
        ax = axes[r, c]
        ax.set_title(b_type.label, fontsize=8.5)
        vmax = max(1, int(max(np.max(s[b_type.key]) for s in snaps)))
        vmin = int(min(np.min(s[b_type.key]) for s in snaps)) if "susceptible" in b_type.key else 0
        im = ax.imshow(snaps[0][b_type.key], cmap=b_type.cmap, vmin=vmin, vmax=vmax)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        plot_items.append((im, b_type.key))

    for idx in range(len(selected_boards), 2 * 5):
        r, c = divmod(idx, 5)
        axes[r, c].axis("off")

    fig.tight_layout(rect=[0, 0, 1, 0.95])

    def update_frame(frame_idx: int):
        current_date = first_snapshots[frame_idx]["fecha"].strftime("%b %Y")
        suptitle_obj.set_text(f"{region} — {current_date}")
        for im, b_key in plot_items:
            im.set_data(data_store["frames_snapshots"][frame_idx][b_key])
        return [im for im, _ in plot_items]

    anim = animation.FuncAnimation(
        fig,
        update_frame,
        frames=frame_indices,
        interval=interval_ms,
        blit=False,
    )

    plt.close(fig)

    start = time.perf_counter()
    result_html = anim.to_jshtml()
    elapsed = time.perf_counter() - start

    logger.debug(f"[TIEMPO] Tiempo de renderizado de animación: {elapsed} s")

    return result_html
