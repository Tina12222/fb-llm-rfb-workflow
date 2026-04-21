from __future__ import annotations
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import List, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np

INT_RE = re.compile(r'\d+')


def _to_int(val) -> int | None:
    if val is None:
        return None
    m = INT_RE.search(str(val))
    return int(m.group()) if m else None


def _collect_one(json_path: Union[str, Path], feas_key: str, inno_key: str) -> Tuple[Counter, Counter, Counter, int]:
    p = Path(json_path).expanduser().resolve()
    data = json.loads(p.read_text(encoding='utf-8'))
    cnt_feas, cnt_inno, cnt_pair = Counter(), Counter(), Counter()
    for item in data:
        f_val = _to_int(item.get(feas_key))
        i_val = _to_int(item.get(inno_key))
        if f_val is not None:
            cnt_feas[f_val] += 1
        if i_val is not None:
            cnt_inno[i_val] += 1
        if f_val is not None and i_val is not None:
            cnt_pair[(f_val, i_val)] += 1
    return cnt_feas, cnt_inno, cnt_pair, len(data)


def _draw_bar(counter: Counter, title: str, save_path: Path, dpi: int):
    xs = range(1, 11)
    ys = [counter.get(x, 0) for x in xs]
    fig, ax = plt.subplots(figsize=(5, 4), constrained_layout=True)
    bars = ax.bar(xs, ys, color='#4c72b0')
    ax.set(title=title, xlabel='Score', ylabel='Count', xticks=xs, xlim=(0.5, 10.5))
    for _, y, bar in zip(xs, ys, bars):
        if y:
            ax.annotate(str(y), (bar.get_x() + bar.get_width() / 2, y), xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontsize=8)
    fig.savefig(save_path, dpi=dpi)
    plt.close(fig)


def _draw_heatmap(pair_counter: Counter, title: str, save_path: Path, dpi: int):
    if not pair_counter:
        return
    grid = np.zeros((11, 11), dtype=int)
    for (f, i), c in pair_counter.items():
        if 0 <= f <= 10 and 0 <= i <= 10:
            grid[i, f] = c
    fig, ax = plt.subplots(figsize=(6, 5), constrained_layout=True)
    im = ax.imshow(grid, origin='lower', cmap='Blues')
    ax.set(title=title, xlabel='Feasibility score', ylabel='Innovation score', xticks=range(11), yticks=range(11))
    for f in range(11):
        for i in range(11):
            if grid[i, f]:
                ax.text(f, i, str(grid[i, f]), ha='center', va='center', fontsize=7)
    fig.colorbar(im, ax=ax).set_label('Count')
    fig.savefig(save_path, dpi=dpi)
    plt.close(fig)


def plot_and_save_score_distributions(json_paths: Union[str, Path, Sequence[Union[str, Path]]], feasibility_key: str = 'Feasibility score', innovation_key: str = 'Innovation score', out_dir: Union[str, Path] = '.', file_prefix: str = 'score_dist', dpi: int = 300):
    paths: List[Path] = [Path(p).expanduser().resolve() for p in ([json_paths] if isinstance(json_paths, (str, Path)) else json_paths)]
    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    total_feas, total_inno, total_pair = Counter(), Counter(), Counter()
    total_n = 0

    for p in paths:
        c_f, c_i, c_pair, n = _collect_one(p, feasibility_key, innovation_key)
        total_feas.update(c_f)
        total_inno.update(c_i)
        total_pair.update(c_pair)
        total_n += n

        stem = p.stem
        _draw_bar(c_f, f'Feasibility ({stem})', out / f'{file_prefix}_{stem}_feasibility.png', dpi)
        _draw_bar(c_i, f'Innovation ({stem})', out / f'{file_prefix}_{stem}_innovation.png', dpi)
        _draw_heatmap(c_pair, f'Joint ({stem})', out / f'{file_prefix}_{stem}_joint_heatmap.png', dpi)

    _draw_bar(total_feas, 'Feasibility (all)', out / f'{file_prefix}_all_feasibility.png', dpi)
    _draw_bar(total_inno, 'Innovation (all)', out / f'{file_prefix}_all_innovation.png', dpi)
    _draw_heatmap(total_pair, 'Joint (all)', out / f'{file_prefix}_all_joint_heatmap.png', dpi)
    print(f'Total samples: {total_n}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Plot score distributions from one or more JSON files.')
    parser.add_argument('json_paths', nargs='+')
    parser.add_argument('--out-dir', default='.')
    parser.add_argument('--prefix', default='score_dist')
    parser.add_argument('--dpi', type=int, default=300)
    args = parser.parse_args()

    plot_and_save_score_distributions(args.json_paths, out_dir=args.out_dir, file_prefix=args.prefix, dpi=args.dpi)
