"""
TSNE Module for UCL Scientific Literature

Reusable functions for:
- Loading TSNE data from CSV
- Computing TSNE from embeddings
- Visualizing TSNE embeddings

Usage:
    from tsne_module import load_tsne_data, visualize_tsne, compute_tsne_from_embeddings
"""

import os
import csv
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_OUTPUT_DIR = "/mnt/wwn-0x5000c500d577b928/mo_data/models_etc/tsne"
DEFAULT_EMBEDDINGS_FILE = "/mnt/wwn-0x5000c500d577b928/mo_data/datasets/418.9k_UCL_title_abstracts_whole_abstract_max_sentences_BAAI-bge-large-en_embeddings"
DEFAULT_OPENALEX_FILE = "/home/mo/github/datasets/419K_decoded_abstracts_w_all_openalex_cols.pkl"


# =============================================================================
# Data Loading Functions
# =============================================================================

def load_tsne_data(csv_path=None, n_samples=None):
    """
    Load TSNE data from a pre-computed CSV file.

    Parameters:
        csv_path: Path to CSV file. If None, uses default based on n_samples.
        n_samples: If csv_path is None, load the file for this sample count.
                   Options: None (full ~370K), 64000, 8000

    Returns:
        pandas DataFrame with columns: cleaned_title, decoded_abstract,
        tsne_x, tsne_y, raw_doi, doi, publication_year, cited_by_count,
        citations_per_year, type, language
    """
    if csv_path is None:
        if n_samples is None:
            csv_path = os.path.join(DEFAULT_OUTPUT_DIR, "ucl_papers_tsne_mapping.csv")
        else:
            sample_str = f"{n_samples // 1000}K" if n_samples >= 1000 else str(n_samples)
            csv_path = os.path.join(DEFAULT_OUTPUT_DIR, f"ucl_papers_tsne_mapping_{sample_str}.csv")

    print(f"Loading TSNE data from: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df):,} papers with TSNE coordinates")
    return df


def load_tsne_coordinates(pickle_path=None, n_samples=None):
    """
    Load raw TSNE coordinates from pickle file.

    Returns:
        dict with 'tsne_coordinates', 'parameters', 'n_samples'
    """
    if pickle_path is None:
        if n_samples is None:
            pickle_path = os.path.join(DEFAULT_OUTPUT_DIR, "ucl_papers_tsne_coordinates.pkl")
        else:
            sample_str = f"{n_samples // 1000}K" if n_samples >= 1000 else str(n_samples)
            pickle_path = os.path.join(DEFAULT_OUTPUT_DIR, f"ucl_papers_tsne_coordinates_{sample_str}.pkl")

    with open(pickle_path, 'rb') as f:
        data = pickle.load(f)
    print(f"Loaded TSNE coordinates: {data['n_samples']:,} samples")
    return data


# =============================================================================
# Visualization Functions
# =============================================================================

def visualize_tsne(df, color_by=None, cmap='viridis', figsize=(12, 10),
                   point_size=1, alpha=0.5, title=None,
                   log_color=False, colorbar_label=None,
                   save_path=None, show=True):
    """
    Visualize TSNE embedding space.

    Parameters:
        df: DataFrame with 'tsne_x' and 'tsne_y' columns
        color_by: Column name to color points by (e.g., 'citations_per_year', 'publication_year')
                  If None, all points are the same color.
        cmap: Matplotlib colormap name
        figsize: Figure size tuple
        point_size: Size of scatter points
        alpha: Transparency of points
        title: Plot title (auto-generated if None)
        log_color: If True, apply log transform to color values
        colorbar_label: Label for colorbar (auto-generated if None)
        save_path: If provided, save figure to this path
        show: If True, display the figure

    Returns:
        matplotlib Figure object
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Prepare color values
    if color_by is not None and color_by in df.columns:
        colors = df[color_by].copy()
        if log_color:
            # Handle zeros/negatives for log transform
            colors = colors.apply(lambda x: np.log(x) if x > 0 else np.nan)
            if colorbar_label is None:
                colorbar_label = f'Log({color_by})'
        else:
            if colorbar_label is None:
                colorbar_label = color_by

        scatter = ax.scatter(
            df['tsne_x'], df['tsne_y'],
            c=colors, cmap=cmap, s=point_size, alpha=alpha
        )
        plt.colorbar(scatter, ax=ax, label=colorbar_label)
    else:
        ax.scatter(df['tsne_x'], df['tsne_y'], s=point_size, alpha=alpha)

    # Labels and title
    ax.set_xlabel('TSNE Dimension 1')
    ax.set_ylabel('TSNE Dimension 2')

    if title is None:
        title = f'TSNE Visualization ({len(df):,} papers)'
        if color_by:
            title += f' - colored by {color_by}'
    ax.set_title(title)

    # Equal aspect ratio for proper visualization
    ax.set_aspect('equal')
    ax.axis('off')  # Clean look without axes

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved figure to: {save_path}")

    if show:
        plt.show()

    return fig


def visualize_tsne_heatmap(df, figsize=(12, 10), bins=200, cmap='hot',
                           title=None, save_path=None, show=True):
    """
    Visualize TSNE as a 2D histogram/heatmap showing point density.

    Parameters:
        df: DataFrame with 'tsne_x' and 'tsne_y' columns
        figsize: Figure size tuple
        bins: Number of bins for histogram
        cmap: Matplotlib colormap name
        title: Plot title
        save_path: If provided, save figure to this path
        show: If True, display the figure

    Returns:
        matplotlib Figure object
    """
    fig, ax = plt.subplots(figsize=figsize)

    h = ax.hist2d(df['tsne_x'], df['tsne_y'], bins=bins, cmap=cmap, cmin=1)
    plt.colorbar(h[3], ax=ax, label='Number of papers')

    if title is None:
        title = f'TSNE Density Heatmap ({len(df):,} papers)'
    ax.set_title(title)
    ax.set_xlabel('TSNE Dimension 1')
    ax.set_ylabel('TSNE Dimension 2')
    ax.set_aspect('equal')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved figure to: {save_path}")

    if show:
        plt.show()

    return fig


# =============================================================================
# TSNE Computation Functions (for generating new embeddings)
# =============================================================================

def compute_tsne_from_embeddings(embeddings_array, n_components=2, perplexity=40,
                                  n_iter=1000, use_pca=True, pca_components=50,
                                  random_state=42, verbose=2):
    """
    Compute TSNE from embedding vectors.

    Parameters:
        embeddings_array: numpy array of shape (n_samples, embedding_dim)
        n_components: TSNE output dimensions (2 or 3)
        perplexity: TSNE perplexity parameter
        n_iter: Number of iterations
        use_pca: If True, reduce dimensions with PCA first (faster)
        pca_components: Number of PCA components
        random_state: Random seed for reproducibility
        verbose: Verbosity level

    Returns:
        numpy array of shape (n_samples, n_components)
    """
    if use_pca and embeddings_array.shape[1] > pca_components:
        print(f"Applying PCA: {embeddings_array.shape[1]} -> {pca_components} dimensions")
        pca = PCA(n_components=pca_components)
        embeddings_for_tsne = pca.fit_transform(embeddings_array)
        print(f"PCA explained variance: {sum(pca.explained_variance_ratio_):.3f}")
    else:
        embeddings_for_tsne = embeddings_array

    print(f"Computing {n_components}D TSNE (perplexity={perplexity}, iterations={n_iter})...")
    tsne = TSNE(
        n_components=n_components,
        perplexity=perplexity,
        n_iter=n_iter,
        verbose=verbose,
        random_state=random_state
    )
    tsne_results = tsne.fit_transform(embeddings_for_tsne)
    print(f"TSNE complete. Shape: {tsne_results.shape}")

    return tsne_results


def load_embeddings_and_metadata(embeddings_file=None, openalex_file=None,
                                  max_samples=None, random_state=42):
    """
    Load embeddings and OpenAlex metadata, deduplicate, and optionally sample.

    Parameters:
        embeddings_file: Path to embeddings pickle file
        openalex_file: Path to OpenAlex metadata pickle file
        max_samples: If provided, randomly sample this many papers
        random_state: Random seed for sampling

    Returns:
        tuple of (embeddings_df, openalex_df, embeddings_array)
    """
    if embeddings_file is None:
        embeddings_file = DEFAULT_EMBEDDINGS_FILE
    if openalex_file is None:
        openalex_file = DEFAULT_OPENALEX_FILE

    print(f"Loading embeddings from: {embeddings_file}")
    embeddings_df = pd.read_pickle(embeddings_file)
    print(f"Loaded {len(embeddings_df):,} rows")

    print(f"Loading OpenAlex metadata from: {openalex_file}")
    openalex_df = pd.read_pickle(openalex_file)
    print(f"Loaded {len(openalex_df):,} rows")

    # Deduplicate
    n_duplicates = embeddings_df.duplicated(subset='decoded_abstract', keep='first').sum()
    print(f"Found {n_duplicates:,} duplicate abstracts")

    embeddings_df = embeddings_df.drop_duplicates(subset='decoded_abstract', keep='first').copy()
    embeddings_df = embeddings_df.reset_index(drop=True)
    print(f"After deduplication: {len(embeddings_df):,} unique papers")

    # Sample if requested
    if max_samples and len(embeddings_df) > max_samples:
        print(f"Sampling {max_samples:,} papers (seed={random_state})")
        embeddings_df = embeddings_df.sample(n=max_samples, random_state=random_state)
        embeddings_df = embeddings_df.reset_index(drop=True)

    # Extract embedding vectors
    embeddings_array = np.array(embeddings_df["combined_embedding"].tolist())
    print(f"Embeddings shape: {embeddings_array.shape}")

    # Deduplicate OpenAlex
    openalex_df = openalex_df.drop_duplicates(subset='decoded_abstract', keep='first').copy()

    return embeddings_df, openalex_df, embeddings_array


def extract_field_from_concepts(concepts_str, level=0):
    """
    Extract research field from OpenAlex concepts at specified hierarchy level.

    Parameters:
        concepts_str: String or list of concept dictionaries
        level: Hierarchy level (0=broadest like "Medicine", 1=sub-field, 2=specific)

    Returns:
        Highest-scored concept name at the specified level, or None
    """
    import ast
    if pd.isna(concepts_str) or not concepts_str:
        return None
    try:
        if isinstance(concepts_str, str):
            concepts = ast.literal_eval(concepts_str)
        else:
            concepts = concepts_str

        # Filter to specified level and sort by score
        level_concepts = [c for c in concepts if c.get('level') == level]
        if not level_concepts:
            return None

        # Return highest scored
        best = max(level_concepts, key=lambda x: x.get('score', 0))
        return best.get('display_name')
    except:
        return None


def save_tsne_results(embeddings_df, openalex_df, tsne_results, output_dir=None,
                       sample_str=None):
    """
    Merge TSNE results with metadata and save to CSV and pickle.

    Parameters:
        embeddings_df: DataFrame with paper data
        openalex_df: DataFrame with OpenAlex metadata
        tsne_results: numpy array of TSNE coordinates
        output_dir: Output directory
        sample_str: String to append to filename (e.g., "64K")

    Returns:
        Path to saved CSV file
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    # Add TSNE coordinates
    embeddings_df = embeddings_df.copy()
    embeddings_df['tsne_x'] = tsne_results[:, 0]
    embeddings_df['tsne_y'] = tsne_results[:, 1]
    if tsne_results.shape[1] > 2:
        embeddings_df['tsne_z'] = tsne_results[:, 2]

    # Merge with OpenAlex metadata
    metadata_cols = [
        'decoded_abstract', 'raw_doi', 'doi', 'title', 'display_name',
        'publication_date', 'publication_year', 'cited_by_count',
        'concepts', 'authorships', 'type', 'language', 'open_access'
    ]
    available_cols = [c for c in metadata_cols if c in openalex_df.columns]
    openalex_subset = openalex_df[available_cols]

    final_df = embeddings_df.merge(
        openalex_subset, on='decoded_abstract', how='left', suffixes=('', '_openalex')
    )

    # Extract field hierarchy from concepts (levels 0, 1, 2)
    if 'concepts' in final_df.columns:
        print("Extracting research field hierarchy from concepts...")
        for level in [0, 1, 2]:
            col_name = f'field_level_{level}'
            final_df[col_name] = final_df['concepts'].apply(
                lambda x: extract_field_from_concepts(x, level=level)
            )
            n_with_field = final_df[col_name].notna().sum()
            print(f"  Level {level}: {n_with_field:,} / {len(final_df):,} papers")

    # Select output columns (now including field hierarchy and tsne_z if 3D)
    csv_columns = [
        'cleaned_title', 'decoded_abstract', 'tsne_x', 'tsne_y', 'tsne_z',
        'raw_doi', 'doi', 'publication_year', 'cited_by_count',
        'citations_per_year', 'field_level_0', 'field_level_1', 'field_level_2',
        'type', 'language'
    ]
    csv_columns = [c for c in csv_columns if c in final_df.columns]
    output_df = final_df[csv_columns].copy()

    # Save CSV
    if sample_str:
        csv_path = os.path.join(output_dir, f"ucl_papers_tsne_mapping_{sample_str}.csv")
    else:
        csv_path = os.path.join(output_dir, "ucl_papers_tsne_mapping.csv")

    output_df.to_csv(csv_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
    print(f"Saved CSV: {csv_path}")

    return csv_path
