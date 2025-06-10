import numpy as np, matplotlib.pyplot as plt
D, S, N = 784, 2, 20_000                    # dimensions, slices per dim, max samples
steps = np.unique(np.logspace(2, np.log10(N), 20, dtype=int)); counts = []
def codeword(u):                            # quantise a unit vector -> integer tuple
    return tuple(((u + 1) * S / 2).astype(int))
for n in steps:                             # simulate growing training set
    v = np.random.randn(n, D)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    counts.append(len({codeword(row) for row in v}))
plt.plot(steps, counts); plt.xscale('log'); plt.yscale('log')
plt.xlabel('Samples'); plt.ylabel('Unique cells')
plt.title(f'PGC cells vs samples (D={D}, S={S})')
plt.tight_layout(); plt.show()
ang = np.degrees(np.arccos(1 - 2 / S))
print(f'Per-axis angular width ≈ {ang:.2f}°')
print(f'Unique cells after {steps[-1]} samples ≈ {counts[-1]}')
