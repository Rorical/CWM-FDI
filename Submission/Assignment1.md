## Info

Name: Cody (Zhexian) Liu
Assignment Number: 1
Repo Link: https://github.com/Rorical/CWM-FDI

## Basic Timing

### What is the difference you observe between real, user, and sys time?

![[Pasted image 20260608100712.png]]![[Pasted image 20260608101019.png]]
The system time is smallest among all the time measurements. The real time is the longest because it measures the total amount of time the program spend. It is the sum of user and sys time.

### Which summary statistics would you report: mean, median, or minimum? Why?

![[Pasted image 20260608101336.png]]
**Mean**. The mean time of execution represents the expectation of time the program costs, which will be the real and stable amount of time it takes when deployed in large scale.

## Reading Counters with perf stat

### Report the output.

![[Pasted image 20260608101614.png]]
It reported 817666898 cycles; 2299661070 instructions with  2.81 instructions-per-cycle ratio

### Report the instructions-per-cycle ratio. What does it suggest? Report cache misses you observe. Why may this matter?

![[Pasted image 20260608102304.png]]
The perf shows 2.83 instructions per cycle. It suggests that CPU is efficiently executing multiple instructions in a single cycle. With that value higher, the program is more efficient and execute faster because it has higher CPU utilization.

Cache miss is 686353 times. This means CPU cannot find the data it want in caches, and has to fetch from memory or other places. CPU has three layers of caches that accelerate its memory reads. More cache miss means slower execution due to bandwidth limits between CPU and memory and each memory operation costs more time.

## Hotspot discovery with perf record and perf report

![[Pasted image 20260608103132.png]]

### Which function consumes the largest fraction of samples?

 **PyEval_EvalFrameDefault** consumes 75% of overhead, but it is used for execution of python bytecode, which is not interesting. The second large consumption comes from **PyFloat_FromDouble** which means python creating floating point number objects. I guess that in doing the $O(n^3)$ operations to each element of matrix, it create new floating point for each one which slows down the program.

## Flame Graphs

![[flamegraph.svg]]

### a. Which function dominates runtime?

**PyEval_EvalFrameDefault**

### b. Given this dominating call, what are the likely bottlenecks in the matmul_slow() program?

PyEval_EvalFrameDefault is used to execute python codes. This domination means it spent most of time executing pure python code. Python is interpreter based and very slow to execute line by line. The bottleneck is that all the computationally intensive functions are in python. It is better to use numpy or torch which dispatch the actual computation to C code and optimized hardware.

### Propose optimizations for speeding up the execution of matmul_slow.py

The matrix is defined as double nested list in the code:
```python
Matrix = List[List[float]]
```

The slow code just compute each element that access a in consecutive rows but b in consecutive columns. This is not cache friendly to b because each time the pointer jumps far away to the next row, and cache only store consecutive memory words. The better way is to also access b in consecutive rows, such as taking transpose of it first, then multiple a and b row by row.
