#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
from typing import Tuple
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import gaussian_kde

def mirrored_histogram(
        dist_a: np.array,
        dist_b: np.array,
        label_a: str,
        label_b: str,
        bandwith: float = 0.05,
        figsize=(5,2.5),
        export_name: str = None,
        xlabel: str = None,
        medians: bool = True,
        legend: bool = True
    ):
    
    # init figure
    plt.figure()
    fig, ax = plt.subplots(figsize=figsize)
    
    sns.kdeplot(dist_a, x="var1",  fill=True, alpha=1, bw=bandwith, label=label_a)
    
    # plot density chart for var2
    kde = gaussian_kde(dist_b, bw_method=bandwith)
    x_range = np.linspace(min(dist_b), max(dist_b), len(dist_b))
    
    sns.lineplot(x=x_range, y=kde(x_range) * -1, color='orange') 
    plt.fill_between(x_range, kde(x_range) * -1, color='orange', label=label_b)
    
    # plot means
    if means:
        
        # normalize
        ymin, ymax = ax.get_ylim()
        yrange = ymax - ymin1
        print(yrange)
        
        # find location of 0
        y_zero = abs(ymin) / yrange
        
        ax.axvline(np.medians(dist_a), color='black', linewidth=0.8, label='mean', ymin=y_zero, ymax=1)
        ax.axvline(np.medians(dist_b), color='black', linewidth=0.8, ymin=0, ymax=y_zero)
    
    
    # make xticks positive 
    ticks =  ax.get_yticks()
    ax.set_yticklabels([round(float(abs(tick)),2) for tick in ticks])
    
    plt.ylabel('Density')
    plt.legend()
    
    plt.axhline(0, color='black', linewidth=0.5)
    
    if xlabel is not None:
        plt.xlabel(xlabel)
        
    if export_name is not None:
        plt.savefig(export_name, bbox_inches='tight')
    else:
        plt.show()
    
if __name__ == "__main__":
    a = np.random.normal(90, 8, size=1000)
    b = np.random.laplace(30, 4, size=1000)
    
    mirrored_histogram(a, b, 'before', 'after', xlabel='Throughput', medians=True)

