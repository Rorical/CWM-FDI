# !/usr/bin/python3
import numpy as np
import matplotlib.pyplot as plt


# parameters to modify (can also be passed as CLI args: python plot.py <data_file> <fig_name>)
import sys

_default = {
    'filename': "time_py.txt",
    'label': 'Consecutive TSC diff',
    'xlabel': 'Sample index',
    'ylabel': 'Time (ns)',
    'title': 'Read Time (Python)',
    'fig_name': 'read_time.png',
}
if len(sys.argv) > 1:
    _default['filename'] = sys.argv[1]
if len(sys.argv) > 2:
    _default['fig_name'] = sys.argv[2]
if len(sys.argv) > 3:
    _default['title'] = sys.argv[3]
if len(sys.argv) > 4:
    _default['label'] = sys.argv[4]
if len(sys.argv) > 5:
    _default['xlabel'] = sys.argv[5]
if len(sys.argv) > 6:
    _default['ylabel'] = sys.argv[6]

filename = _default['filename']
label = _default['label']
xlabel = _default['xlabel']
ylabel = _default['ylabel']
title = _default['title']
fig_name = _default['fig_name']
bins=100

## load data from input file
t = np.loadtxt(filename, delimiter=" ", dtype="float")

## clip x-axis to the 1st–99th percentile range so outliers don't distort
lo, hi = np.percentile(t, [1, 99])
margin = (hi - lo) * 0.1

## CDF (cumulative distribution function) — best for visualizing timing distributions
n = np.arange(1, len(t) + 1) / float(len(t))
ts = np.sort(t)
plt.step(ts, n, where='post', label=label)
plt.xlim(lo - margin, hi + margin)

## comment the lines above and uncomment the line below to plot a simple CDF
#plt.hist(t[:], bins, density=True, histtype='step', cumulative=True, label=label)

## comment the lines above and uncomment the 4 lines below for a nicer CDF
#n = np.arange(1,len(t)+1) / float(len(t))
#ts = np.sort(t)
#fig, ax = plt.subplots()
#ax.step(ts,n)

plt.xlabel(xlabel)
plt.ylabel(ylabel)
plt.title(title)
plt.legend()
plt.savefig(fig_name)
plt.show()
