# %% [markdown]
# # TSNE Computation and Visualization for UCL Scientific Literature
#
# This script loads pre-computed TSNE embeddings and visualizes them.
# The data generation code is preserved but commented out.
#
# Usage:
#   python compute_tsne.py                      # Visualize full dataset
#   python compute_tsne.py --samples 64000      # Visualize 64K sample
#   python compute_tsne.py --samples 8000       # Visualize 8K sample

# %% Imports
import sys
from tsne_module import (
    load_tsne_data,
    visualize_tsne,
    visualize_tsne_heatmap
)

# =============================================================================
# 2D VISUALIZATION CODE (COMMENTED OUT - 2D DATA ALREADY GENERATED)
# =============================================================================

# # %% Parse command line arguments
# N_SAMPLES = None  # None means full dataset
# for i, arg in enumerate(sys.argv[1:], 1):
#     if arg == '--samples' and i < len(sys.argv):
#         N_SAMPLES = int(sys.argv[i + 1])
#     elif arg.startswith('--samples='):
#         N_SAMPLES = int(arg.split('=')[1])
#
# # %% Load pre-computed TSNE data
# df = load_tsne_data(n_samples=N_SAMPLES)
#
# # %% Visualize TSNE - colored by citations per year
# fig1 = visualize_tsne(
#     df,
#     color_by='citations_per_year',
#     log_color=True,
#     cmap='plasma',
#     point_size=0.5,
#     alpha=0.6,
#     title=f'UCL Papers TSNE ({len(df):,} papers) - Log Citations/Year'
# )
#
# # %% Visualize TSNE - colored by publication year
# fig2 = visualize_tsne(
#     df,
#     color_by='publication_year',
#     cmap='viridis',
#     point_size=0.5,
#     alpha=0.6,
#     title=f'UCL Papers TSNE ({len(df):,} papers) - Publication Year'
# )
#
# # %% Visualize TSNE - density heatmap
# fig3 = visualize_tsne_heatmap(
#     df,
#     bins=150,
#     cmap='hot',
#     title=f'UCL Papers TSNE Density ({len(df):,} papers)'
# )


# =============================================================================
# 3D TSNE GENERATION CODE (ACTIVE)
# =============================================================================

# %% [GENERATION-3D] Imports
import os
import csv
import pickle
import numpy as np
import pandas as pd
from tsne_module import (
    load_embeddings_and_metadata,
    compute_tsne_from_embeddings,
    save_tsne_results,
    DEFAULT_OUTPUT_DIR
)

# %% [GENERATION-3D] Configuration
MAX_SAMPLES = None  # Set to 64000, 8000, etc. for smaller runs - controlled via command line
N_COMPONENTS = 3  # 3D TSNE

# Parse command line for sample size
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == '--samples' and i < len(sys.argv):
        MAX_SAMPLES = int(sys.argv[i + 1])
    elif arg.startswith('--samples='):
        MAX_SAMPLES = int(arg.split('=')[1])

if MAX_SAMPLES:
    print(f"*** 3D TSNE: Processing {MAX_SAMPLES:,} samples ***")
else:
    print(f"*** 3D TSNE: Processing FULL dataset ***")

# %% [GENERATION-3D] Load embeddings and metadata
embeddings_df, openalex_df, embeddings_array = load_embeddings_and_metadata(
    max_samples=MAX_SAMPLES
)

# %% [GENERATION-3D] Compute 3D TSNE
tsne_results = compute_tsne_from_embeddings(
    embeddings_array,
    n_components=N_COMPONENTS,
    perplexity=40,
    n_iter=1000,
    use_pca=True,
    pca_components=50
)

# %% [GENERATION-3D] Save results
sample_str = None
if MAX_SAMPLES:
    sample_str = f"{MAX_SAMPLES // 1000}K_3D" if MAX_SAMPLES >= 1000 else f"{MAX_SAMPLES}_3D"
else:
    sample_str = "full_3D"

csv_path = save_tsne_results(
    embeddings_df, openalex_df, tsne_results,
    output_dir=DEFAULT_OUTPUT_DIR,
    sample_str=sample_str
)

# %% [GENERATION-3D] Also save raw TSNE pickle
pickle_path = os.path.join(DEFAULT_OUTPUT_DIR, f"ucl_papers_tsne_coordinates_{sample_str}.pkl")

with open(pickle_path, 'wb') as f:
    pickle.dump({
        'tsne_coordinates': tsne_results,
        'parameters': {
            'perplexity': 40,
            'iterations': 1000,
            'components': N_COMPONENTS,
            'pca_first': True,
            'pca_components': 50
        },
        'n_samples': len(tsne_results)
    }, f)
print(f"Saved 3D TSNE pickle: {pickle_path}")

print("\n" + "="*60)
print(f"3D TSNE COMPLETE")
print(f"Samples: {len(tsne_results):,}")
print(f"CSV: {csv_path}")
print(f"Pickle: {pickle_path}")
print("="*60)
