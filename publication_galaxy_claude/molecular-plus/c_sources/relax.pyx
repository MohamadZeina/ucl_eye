# Particle overlap relaxation using spatial hash
# Pushes overlapping particles apart before simulation starts
# NOTE: This file is concatenated after simulate.pyx, so imports are inherited


cpdef relax_overlaps(float[:] par_loc, float[:] par_size, int max_iterations, float min_separation, float strength, int num_threads):
    """
    Push overlapping particles apart until no overlaps remain.
    Uses spatial hash for O(n) neighbor lookups instead of O(n²).

    Args:
        par_loc: array of [x,y,z,x,y,z,...] particle positions (modified in place)
        par_size: array of particle radii
        max_iterations: maximum relaxation passes
        min_separation: target separation as multiple of sum of radii (1.001 = tiny gap)
        strength: how much to push apart per iteration (0.5=gentle, 1.0=full, 0.8=recommended)
        num_threads: number of CPU threads

    Returns:
        (iterations_used, initial_overlaps, final_overlaps)
    """
    cdef int n = len(par_size)
    if n < 2:
        return (0, 0, 0)

    cdef int i, j, iteration
    cdef int initial_overlaps = 0
    cdef int overlaps_this_pass = 0
    cdef int final_overlaps = 0

    # Find max particle size for spatial hash cell size
    cdef float max_size = 0.0
    for i in range(n):
        if par_size[i] > max_size:
            max_size = par_size[i]

    # Cell size = 2 * max_size * min_separation (ensures we catch all potential overlaps)
    cdef float cell_size = max_size * 2.0 * min_separation * 1.1

    # Find bounds
    cdef float min_x = par_loc[0], max_x = par_loc[0]
    cdef float min_y = par_loc[1], max_y = par_loc[1]
    cdef float min_z = par_loc[2], max_z = par_loc[2]

    for i in range(n):
        if par_loc[i*3] < min_x: min_x = par_loc[i*3]
        if par_loc[i*3] > max_x: max_x = par_loc[i*3]
        if par_loc[i*3+1] < min_y: min_y = par_loc[i*3+1]
        if par_loc[i*3+1] > max_y: max_y = par_loc[i*3+1]
        if par_loc[i*3+2] < min_z: min_z = par_loc[i*3+2]
        if par_loc[i*3+2] > max_z: max_z = par_loc[i*3+2]

    # Add padding
    min_x -= cell_size
    min_y -= cell_size
    min_z -= cell_size
    max_x += cell_size
    max_y += cell_size
    max_z += cell_size

    # Grid dimensions - cap at 10M cells to avoid memory issues
    cdef int MAX_CELLS = 10000000
    cdef int grid_x = <int>((max_x - min_x) / cell_size) + 1
    cdef int grid_y = <int>((max_y - min_y) / cell_size) + 1
    cdef int grid_z = <int>((max_z - min_z) / cell_size) + 1

    # If grid too large, increase cell size
    cdef long total_cells_long = <long>grid_x * <long>grid_y * <long>grid_z
    while total_cells_long > MAX_CELLS and cell_size < 1000.0:
        cell_size *= 2.0
        grid_x = <int>((max_x - min_x) / cell_size) + 1
        grid_y = <int>((max_y - min_y) / cell_size) + 1
        grid_z = <int>((max_z - min_z) / cell_size) + 1
        total_cells_long = <long>grid_x * <long>grid_y * <long>grid_z

    cdef int total_cells = <int>total_cells_long

    # Allocate cell arrays (using malloc, then zero manually)
    cdef int *cell_counts = <int *>malloc(total_cells * sizeof(int))
    cdef int *cell_starts = <int *>malloc(total_cells * sizeof(int))
    cdef int *particle_cells = <int *>malloc(n * sizeof(int))
    cdef int *sorted_indices = <int *>malloc(n * sizeof(int))

    if cell_counts == NULL or cell_starts == NULL or particle_cells == NULL or sorted_indices == NULL:
        if cell_counts != NULL: free(cell_counts)
        if cell_starts != NULL: free(cell_starts)
        if particle_cells != NULL: free(particle_cells)
        if sorted_indices != NULL: free(sorted_indices)
        return (0, 0, -1)  # Error

    # Zero cell_counts
    for i in range(total_cells):
        cell_counts[i] = 0

    cdef int cell_x, cell_y, cell_z, cell_idx
    cdef float xi, yi, zi, xj, yj, zj, ri, rj
    cdef float dx, dy, dz, dist_sq, dist, min_dist, overlap
    cdef float inv_dist, nx, ny, nz
    cdef int start_idx, end_idx, neighbor_idx
    cdef int cx, cy, cz, ncx, ncy, ncz, neighbor_cell

    for iteration in range(max_iterations):
        overlaps_this_pass = 0

        # Reset cell counts
        for i in range(total_cells):
            cell_counts[i] = 0

        # Count particles per cell
        for i in range(n):
            cell_x = <int>((par_loc[i*3] - min_x) / cell_size)
            cell_y = <int>((par_loc[i*3+1] - min_y) / cell_size)
            cell_z = <int>((par_loc[i*3+2] - min_z) / cell_size)
            if cell_x < 0: cell_x = 0
            if cell_x >= grid_x: cell_x = grid_x - 1
            if cell_y < 0: cell_y = 0
            if cell_y >= grid_y: cell_y = grid_y - 1
            if cell_z < 0: cell_z = 0
            if cell_z >= grid_z: cell_z = grid_z - 1
            cell_idx = cell_x + cell_y * grid_x + cell_z * grid_x * grid_y
            particle_cells[i] = cell_idx
            cell_counts[cell_idx] += 1

        # Calculate cell starts (prefix sum)
        cell_starts[0] = 0
        for i in range(1, total_cells):
            cell_starts[i] = cell_starts[i-1] + cell_counts[i-1]

        # Reset counts for placement
        for i in range(total_cells):
            cell_counts[i] = 0

        # Place particles into sorted array
        for i in range(n):
            cell_idx = particle_cells[i]
            sorted_indices[cell_starts[cell_idx] + cell_counts[cell_idx]] = i
            cell_counts[cell_idx] += 1

        # Check each particle against neighbors in adjacent cells
        for i in range(n):
            xi = par_loc[i*3]
            yi = par_loc[i*3+1]
            zi = par_loc[i*3+2]
            ri = par_size[i]

            cx = <int>((xi - min_x) / cell_size)
            cy = <int>((yi - min_y) / cell_size)
            cz = <int>((zi - min_z) / cell_size)

            # Check 3x3x3 neighborhood
            for ncx in range(cx - 1, cx + 2):
                if ncx < 0 or ncx >= grid_x:
                    continue
                for ncy in range(cy - 1, cy + 2):
                    if ncy < 0 or ncy >= grid_y:
                        continue
                    for ncz in range(cz - 1, cz + 2):
                        if ncz < 0 or ncz >= grid_z:
                            continue

                        neighbor_cell = ncx + ncy * grid_x + ncz * grid_x * grid_y
                        start_idx = cell_starts[neighbor_cell]
                        end_idx = start_idx + cell_counts[neighbor_cell]

                        for neighbor_idx in range(start_idx, end_idx):
                            j = sorted_indices[neighbor_idx]

                            # Only process each pair once (j > i)
                            if j <= i:
                                continue

                            xj = par_loc[j*3]
                            yj = par_loc[j*3+1]
                            zj = par_loc[j*3+2]
                            rj = par_size[j]

                            dx = xj - xi
                            dy = yj - yi
                            dz = zj - zi
                            dist_sq = dx*dx + dy*dy + dz*dz
                            min_dist = (ri + rj) * min_separation

                            if dist_sq < min_dist * min_dist:
                                # Overlap detected
                                if dist_sq > 1e-10:
                                    dist = sqrt(dist_sq)
                                else:
                                    dist = 1e-5
                                    dx = 1.0
                                    dy = 0.0
                                    dz = 0.0

                                if iteration == 0:
                                    initial_overlaps += 1
                                overlaps_this_pass += 1

                                # Push apart
                                overlap = (min_dist - dist) * strength
                                inv_dist = 1.0 / dist
                                nx = dx * inv_dist
                                ny = dy * inv_dist
                                nz = dz * inv_dist

                                par_loc[i*3] -= nx * overlap
                                par_loc[i*3+1] -= ny * overlap
                                par_loc[i*3+2] -= nz * overlap
                                par_loc[j*3] += nx * overlap
                                par_loc[j*3+1] += ny * overlap
                                par_loc[j*3+2] += nz * overlap

                                # Update local position for subsequent checks
                                xi = par_loc[i*3]
                                yi = par_loc[i*3+1]
                                zi = par_loc[i*3+2]

        if overlaps_this_pass == 0:
            # Converged
            free(cell_counts)
            free(cell_starts)
            free(particle_cells)
            free(sorted_indices)
            return (iteration + 1, initial_overlaps, 0)

        final_overlaps = overlaps_this_pass

    # Clean up
    free(cell_counts)
    free(cell_starts)
    free(particle_cells)
    free(sorted_indices)

    return (max_iterations, initial_overlaps, final_overlaps)
