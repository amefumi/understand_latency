import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import newton

def solve_queue_patience(observed_times, num_leavers):
    """
    observed_times (t_survivors): Array of wait times for those who entered (N).
    num_leavers (M): Count of customers who left.
    """
    t_obs = np.array(observed_times)
    N = len(t_obs)
    M = num_leavers
    total_population = N + M

    # 1. Define the Estimating Equation
    # We need to find k such that: sum(exp(0.5 * k * t^2)) = N + M
    def equation(k):
        # Avoid overflow in exp for the solver
        val = np.sum(np.exp(0.5 * k * t_obs**2)) - total_population
        return val

    # 2. Solve for k (Hazard Rate coefficient)
    # Initial guess: Small positive number
    try:
        k_est = newton(equation, x0=1e-5, maxiter=1000)
    except RuntimeError:
        print("Solver failed to converge. Check data scaling.")
        return None

    # 3. Calculate Statistics
    # Mean of a Rayleigh distribution is sqrt(pi / (2k))
    estimated_mean_patience = np.sqrt(np.pi / (2 * k_est))
    
    return k_est, estimated_mean_patience

# --- Example Usage ---

# Synthetic Data: 
# Imagine a system where true patience is Rayleigh(scale=10), mean ~12.5s
# But the queue is slow, so many leave.
np.random.seed(42)
true_k = 1.0 / (10**2) # using scale=10 -> sigma=10, k=1/sigma^2
survivors = []
M_leavers = 0

# Simulate 1000 customers attempting to enter
for _ in range(1000):
    patience = np.random.rayleigh(scale=10)
    wait_time_needed = np.random.uniform(5, 15) # Queue takes 5-15 seconds
    
    if patience >= wait_time_needed:
        survivors.append(wait_time_needed)
    else:
        M_leavers += 1 # We don't see their time, just that they left

survivors = np.array(survivors)

print(f"Observed (N): {len(survivors)}")
print(f"Unobserved (M): {M_leavers}")
print(f"Avg Observed Wait Time: {np.mean(survivors):.2f}s")

# Run the Estimator
k_hat, mean_patience_hat = solve_queue_patience(survivors, M_leavers)

print(f"--- Estimation Results ---")
print(f"Estimated k: {k_hat:.5f} (True: {true_k:.5f})")
print(f"Estimated Mean Patience: {mean_patience_hat:.2f}s")

# --- Plotting (Academic Style) ---
plt.style.use('seaborn-v0_8-whitegrid')
plt.figure(figsize=(8, 5))

# Plot observed data histogram
plt.hist(survivors, bins=30, density=True, alpha=0.6, color='gray', label='Observed Wait Times ($t_{survivors}$)')

# Plot Estimated Distribution (Rayleigh PDF)
x = np.linspace(0, 30, 200)
pdf = (k_hat * x) * np.exp(-0.5 * k_hat * x**2)
plt.plot(x, pdf, color='darkred', linewidth=2, label=f'Est. Patience Distribution\n(Rayleigh, $\sigma$={1/np.sqrt(k_hat):.1f})')

plt.xlabel('Time ($t$)')
plt.ylabel('Density')
plt.title('Reconstructing Patience Distribution from Censored Queue Data')
plt.legend()
plt.tight_layout()
plt.savefig('patience_estimation_academic_style.png', dpi=300)