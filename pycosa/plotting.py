#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
from typing import Tuple
import matplotlib.pyplot as plt

def mirrored_histogram(
        dist_a: np.array,
        dist_b: np.array,
        label_a: str,
        label_b: str,
        bins: Tuple[int, int] = (200,200),
        figsize=(5,2.5),
        export_name: str = None,
        xlabel: str = None,
        means: bool = True
    ):
    
    # compute bins and frequencies
    aa, aaa = np.histogram(dist_a, bins=bins[0])
    bb, bbb = np.histogram(dist_b, bins=bins[1])
    
    # init figure
    plt.figure()
    fig, ax = plt.subplots(figsize=figsize)
    
    # get maximum frequency & make plot symmetric
    maxx = max(max(aa), max(bb))
    plt.ylim(-maxx, maxx)
    
    # plot 'histograms'
    ax.bar(aaa[:-1], aa, label=label_a)
    ax.bar(bbb[:-1], bb*-1, label=label_b)
    
    # plot means
    if means:
        ax.axvline(np.mean(dist_a), ymin=0.5, ymax=1, color='black', linewidth=0.8, label='mean')
        ax.axvline(np.mean(dist_b), color='black', ymin=0, ymax=0.5, linewidth=0.8)
    
    # plot horizontal line
    plt.axhline(0, color='black', linewidth=0.5)
    
    # make xticks positive 
    ticks =  ax.get_yticks()
    ax.set_yticklabels([int(abs(tick)) for tick in ticks])
    
    plt.ylabel('Frequency')
    plt.legend()
    
    if xlabel is not None:
        plt.xlabel(xlabel)
        
    if export_name is not None:
        plt.savefig(export_name, bbox_inches='tight')
    else:
        plt.show()
    
if __name__ == "__main__":
    a = np.random.laplace(20, 8, size=1000)
    b = np.random.laplace(30, 4, size=1000)
    
    mirrored_histogram(a, b, 'before', 'after', bins=(200,200), xlabel='Throughput')