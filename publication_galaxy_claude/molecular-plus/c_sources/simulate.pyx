#cython: profile=False
#cython: boundscheck=False
#cython: wraparound=False
#cython: cdivision=True
#cython: language_level=3
#cython: cpow=True

# NOTE: order of slow functions to be optimize/multithreaded:
# spatial_hash_building, spatial_hash_querying, linksolving


cimport cython
from time import process_time as clock
from cython.parallel import parallel, prange, threadid
from libc.stdlib cimport malloc, realloc, free, rand, srand, abs
from libc.string cimport memcpy
from libc.math cimport sqrt, pow

#cdef extern from "omp.h":
#    void omp_set_max_active_levels(int max_levels)

#def set_max_active_levels(int max_levels):
#    omp_set_max_active_levels(max_levels)

#set_max_active_levels(1)

cdef extern from "limits.h":
    int INT_MAX

cdef extern from "float.h":
    float FLT_MAX


cdef extern from "stdlib.h":
    ctypedef void const_void "const void"
    void qsort(
        void *base,
        int nmemb,
        int size,
        int(*compar)(const_void *, const_void *)
    )noexcept nogil


cdef float fps = 0
cdef int substep = 0
cdef float deltatime = 0
cdef int parnum = 0
cdef int psysnum = 0
cdef int cpunum = 0
cdef int newlinks = 0
cdef int totallinks = 0
cdef int totaldeadlinks = 0
cdef int *deadlinks = NULL
cdef Particle *parlist = NULL
cdef SParticle *parlistcopy = NULL
cdef ParSys *psys = NULL
cdef SpatialHash *spatialhash = NULL

# Barnes-Hut gravity globals
cdef int gravity_enabled = 0
cdef float gravity_G = 1.0
cdef float gravity_theta = 0.5
cdef float gravity_softening = 0.01

# Initial rotation (applied ONCE on first frame, after gravity)
cdef int initial_rotation_applied = 0
cdef float initial_rotation_strength = 0.0
cdef float initial_rotation_falloff = 0.5  # 0=flat, 0.5=Keplerian

# Track if simulation has started (to prevent Blender from overwriting our velocities)
cdef int simulation_started = 0

print("cmolcore imported  v1.21.20+enclosed_mass_safe")


# ============================================================================
# Barnes-Hut N-body Gravity Implementation
# ============================================================================

cdef inline int get_octant(float px, float py, float pz,
                           float cx, float cy, float cz) noexcept nogil:
    """Get octant index for a point relative to center"""
    cdef int octant = 0
    if px >= cx: octant |= 1
    if py >= cy: octant |= 2
    if pz >= cz: octant |= 4
    return octant


cdef inline OctreeNode* allocate_node(Octree *tree) noexcept nogil:
    """Allocate a node from the pre-allocated pool"""
    if tree.next_free >= tree.pool_size:
        return NULL
    cdef OctreeNode *node = &tree.node_pool[tree.next_free]
    tree.next_free += 1
    node.is_leaf = 1
    node.particle_id = -1
    node.num_particles = 0
    node.mass = 0.0
    node.com[0] = 0.0
    node.com[1] = 0.0
    node.com[2] = 0.0
    cdef int j
    for j in range(8):
        node.children[j] = NULL
    return node


cdef Octree* Octree_create(int max_particles, float theta, float G, float softening) noexcept nogil:
    """Create octree with pre-allocated node pool"""
    cdef Octree *tree = <Octree *>malloc(cython.sizeof(Octree))
    # Allocate ~2x particles for internal nodes
    tree.pool_size = max_particles * 2
    tree.node_pool = <OctreeNode *>malloc(tree.pool_size * cython.sizeof(OctreeNode))
    tree.next_free = 0
    tree.root = NULL
    tree.theta = theta
    tree.G = G
    tree.softening = softening
    return tree


cdef void Octree_destroy(Octree *tree) noexcept nogil:
    """Free octree memory"""
    if tree != NULL:
        if tree.node_pool != NULL:
            free(tree.node_pool)
        free(tree)


cdef void Octree_insert(Octree *tree, OctreeNode *node, Particle *par,
                        float cx, float cy, float cz, float half_size, int depth) noexcept nogil:
    """Insert particle into octree, building structure as needed"""
    if node == NULL or depth > 50:  # Depth limit to prevent infinite recursion
        return

    cdef int octant
    cdef float new_half = half_size * 0.5
    cdef float new_cx, new_cy, new_cz
    cdef Particle *existing

    # Update center of mass incrementally
    cdef float total_mass = node.mass + par.mass
    if total_mass > 0:
        node.com[0] = (node.com[0] * node.mass + par.loc[0] * par.mass) / total_mass
        node.com[1] = (node.com[1] * node.mass + par.loc[1] * par.mass) / total_mass
        node.com[2] = (node.com[2] * node.mass + par.loc[2] * par.mass) / total_mass
    node.mass = total_mass
    node.num_particles += 1

    # If leaf with no particle yet, just store this particle
    if node.is_leaf and node.particle_id == -1:
        node.particle_id = par.id
        return

    # If leaf with existing particle, subdivide and re-insert both
    if node.is_leaf and node.particle_id != -1:
        node.is_leaf = 0
        # Re-insert existing particle into appropriate child
        existing = &parlist[node.particle_id]
        octant = get_octant(existing.loc[0], existing.loc[1], existing.loc[2], cx, cy, cz)
        if node.children[octant] == NULL:
            node.children[octant] = allocate_node(tree)
            if node.children[octant] == NULL:
                return  # Pool exhausted
            new_cx = cx + (new_half if (octant & 1) else -new_half)
            new_cy = cy + (new_half if (octant & 2) else -new_half)
            new_cz = cz + (new_half if (octant & 4) else -new_half)
            node.children[octant].center[0] = new_cx
            node.children[octant].center[1] = new_cy
            node.children[octant].center[2] = new_cz
            node.children[octant].half_size = new_half
        Octree_insert(tree, node.children[octant], existing,
                      node.children[octant].center[0],
                      node.children[octant].center[1],
                      node.children[octant].center[2], new_half, depth + 1)
        node.particle_id = -1

    # Insert new particle into appropriate child
    octant = get_octant(par.loc[0], par.loc[1], par.loc[2], cx, cy, cz)
    if node.children[octant] == NULL:
        node.children[octant] = allocate_node(tree)
        if node.children[octant] == NULL:
            return  # Pool exhausted
        new_cx = cx + (new_half if (octant & 1) else -new_half)
        new_cy = cy + (new_half if (octant & 2) else -new_half)
        new_cz = cz + (new_half if (octant & 4) else -new_half)
        node.children[octant].center[0] = new_cx
        node.children[octant].center[1] = new_cy
        node.children[octant].center[2] = new_cz
        node.children[octant].half_size = new_half
    Octree_insert(tree, node.children[octant], par,
                  node.children[octant].center[0],
                  node.children[octant].center[1],
                  node.children[octant].center[2], new_half, depth + 1)


cdef void Octree_calculate_force(Octree *tree, OctreeNode *node, Particle *par,
                                 float *force) noexcept nogil:
    """Calculate gravitational force on particle from node (recursive Barnes-Hut)"""
    if node == NULL or node.num_particles == 0:
        return

    # Skip self (when leaf contains this particle)
    if node.is_leaf and node.particle_id == par.id:
        return

    cdef float dx = node.com[0] - par.loc[0]
    cdef float dy = node.com[1] - par.loc[1]
    cdef float dz = node.com[2] - par.loc[2]
    cdef float dist_sq = dx*dx + dy*dy + dz*dz + tree.softening * tree.softening
    cdef float dist = sqrt(dist_sq)
    cdef float size = node.half_size * 2.0
    cdef float force_mag
    cdef int j

    # Barnes-Hut criterion: if node is far enough, treat as single point mass
    if node.is_leaf or (size / dist) < tree.theta:
        # Compute acceleration: a = G * M / r^2 in direction of r
        force_mag = tree.G * node.mass / dist_sq
        force[0] += force_mag * dx / dist
        force[1] += force_mag * dy / dist
        force[2] += force_mag * dz / dist
    else:
        # Node is too close, recurse into children
        for j in range(8):
            if node.children[j] != NULL:
                Octree_calculate_force(tree, node.children[j], par, force)


cdef void apply_barnes_hut_gravity(int num_threads) noexcept nogil:
    """Apply gravitational forces using Barnes-Hut algorithm with parallel force computation"""
    global parlist, parnum, deltatime, gravity_G, gravity_theta, gravity_softening

    cdef int i, j
    cdef float minX = FLT_MAX, minY = FLT_MAX, minZ = FLT_MAX
    cdef float maxX = -FLT_MAX, maxY = -FLT_MAX, maxZ = -FLT_MAX
    cdef float cx, cy, cz, half_size
    cdef Octree *octree
    cdef float force[3]

    # Find bounding box of all particles
    for i in range(parnum):
        if parlist[i].state >= 3:  # Only alive particles
            if parlist[i].loc[0] < minX: minX = parlist[i].loc[0]
            if parlist[i].loc[0] > maxX: maxX = parlist[i].loc[0]
            if parlist[i].loc[1] < minY: minY = parlist[i].loc[1]
            if parlist[i].loc[1] > maxY: maxY = parlist[i].loc[1]
            if parlist[i].loc[2] < minZ: minZ = parlist[i].loc[2]
            if parlist[i].loc[2] > maxZ: maxZ = parlist[i].loc[2]

    # Compute center and half-size with small margin
    cx = (minX + maxX) * 0.5
    cy = (minY + maxY) * 0.5
    cz = (minZ + maxZ) * 0.5
    half_size = (maxX - minX)
    if (maxY - minY) > half_size:
        half_size = (maxY - minY)
    if (maxZ - minZ) > half_size:
        half_size = (maxZ - minZ)
    half_size = half_size * 0.5 + 1.0  # Add margin

    # Create octree
    octree = Octree_create(parnum, gravity_theta, gravity_G, gravity_softening)
    if octree == NULL:
        return
    octree.root = allocate_node(octree)
    if octree.root == NULL:
        Octree_destroy(octree)
        return
    octree.root.center[0] = cx
    octree.root.center[1] = cy
    octree.root.center[2] = cz
    octree.root.half_size = half_size

    # Insert all alive particles into octree (serial - modifies shared structure)
    for i in range(parnum):
        if parlist[i].state >= 3 and parlist[i].mass > 0:
            Octree_insert(octree, octree.root, &parlist[i], cx, cy, cz, half_size, 0)

    # Calculate forces and update velocities (PARALLEL - each particle independent)
    for i in prange(parnum, schedule='dynamic', chunksize=64, num_threads=num_threads):
        if parlist[i].state >= 3:
            force[0] = 0.0
            force[1] = 0.0
            force[2] = 0.0
            Octree_calculate_force(octree, octree.root, &parlist[i], force)
            # Update velocity: v += a * dt
            parlist[i].vel[0] = parlist[i].vel[0] + force[0] * deltatime
            parlist[i].vel[1] = parlist[i].vel[1] + force[1] * deltatime
            parlist[i].vel[2] = parlist[i].vel[2] + force[2] * deltatime

    # Cleanup
    Octree_destroy(octree)


cdef void apply_initial_rotation_once(int num_threads) noexcept:
    """Apply initial tangential velocity ONCE (first frame only).

    Uses ENCLOSED MASS with CORE SOFTENING:
    v = strength * sqrt(G * M_enclosed / r_effective)
    r_effective = sqrt(r^2 + r_core^2)
    r_core = falloff * r_max

    Falloff parameter controls core softening:
    - falloff = 0: no core (can be fast at center)
    - falloff = 0.1-0.3: gentle core protection
    - falloff = 0.5: large core, flatter profile
    """
    global parlist, parnum, gravity_G, initial_rotation_strength, initial_rotation_falloff, initial_rotation_applied

    cdef int i
    cdef int j
    cdef float px, py, r_xy, inv_r
    cdef float r_j
    cdef float v_tangent
    cdef float tangent_dir_x, tangent_dir_y
    cdef int count = 0
    cdef float r_max = 0.0
    cdef float r_core = 0.0
    cdef float r_effective = 0.0
    cdef float enclosed_mass = 0.0
    cdef float min_v = 999999.0
    cdef float max_v = 0.0

    # First pass: find maximum radius
    for i in range(parnum):
        if parlist[i].mass > 0:
            r_xy = sqrt(parlist[i].loc[0] * parlist[i].loc[0] +
                       parlist[i].loc[1] * parlist[i].loc[1])
            if r_xy > r_max:
                r_max = r_xy

    if r_max < 0.001:
        r_max = 1.0

    # Core radius for softening
    r_core = initial_rotation_falloff * r_max

    print(f"  Rotation: strength={initial_rotation_strength:.4f}, core={r_core:.4f}, r_max={r_max:.4f}, G={gravity_G:.6f}")

    # For each particle, calculate enclosed mass and velocity
    for i in range(parnum):
        if parlist[i].mass <= 0:
            continue

        px = parlist[i].loc[0]
        py = parlist[i].loc[1]
        r_xy = sqrt(px * px + py * py)

        if r_xy < 0.001:
            continue

        # Calculate enclosed mass (mass of particles closer to center than this one)
        enclosed_mass = 0.0
        for j in range(parnum):
            if parlist[j].mass > 0:
                r_j = sqrt(parlist[j].loc[0] * parlist[j].loc[0] +
                          parlist[j].loc[1] * parlist[j].loc[1])
                if r_j <= r_xy:
                    enclosed_mass = enclosed_mass + parlist[j].mass

        if enclosed_mass <= 0.0:
            continue

        # Softened effective radius
        r_effective = sqrt(r_xy * r_xy + r_core * r_core)

        inv_r = 1.0 / r_xy

        # Tangent direction (counter-clockwise, normalized)
        tangent_dir_x = -py * inv_r
        tangent_dir_y = px * inv_r

        # Enclosed mass orbital velocity with core softening
        v_tangent = initial_rotation_strength * sqrt(gravity_G * enclosed_mass / r_effective)

        if v_tangent < min_v:
            min_v = v_tangent
        if v_tangent > max_v:
            max_v = v_tangent

        count = count + 1

        # ADD tangential velocity
        parlist[i].vel[0] = parlist[i].vel[0] + tangent_dir_x * v_tangent
        parlist[i].vel[1] = parlist[i].vel[1] + tangent_dir_y * v_tangent

    print(f"  Rotation applied to {count} particles, v range: {min_v:.4f} to {max_v:.4f}")

    # Mark as applied so we don't do it again
    initial_rotation_applied = 1


cpdef simulate(importdata):
    global spatialhash
    global parlist
    global parlistcopy
    global parnum
    global psysnum
    global psys
    global cpunum
    global deltatime
    global newlinks
    global totallinks
    global totaldeadlinks
    global deadlinks
    global gravity_enabled
    global initial_rotation_frames_remaining
    global simulation_started

    cdef int i = 0
    cdef int ii = 0
    cdef int profiling = 0
    cdef float minX = INT_MAX
    cdef float minY = INT_MAX
    cdef float minZ = INT_MAX
    cdef float maxX = -INT_MAX
    cdef float maxY = -INT_MAX
    cdef float maxZ = -INT_MAX
    cdef float maxSize = -INT_MAX
    cdef Pool *parPool = <Pool *>malloc(1 * cython.sizeof(Pool))
    parPool.parity = <Parity *>malloc(2 * cython.sizeof(Parity))
    parPool[0].axis = -1
    parPool[0].offset = 0
    parPool[0].max = 0
    cdef float query_radius = 0

    newlinks = 0
    for i in range(cpunum):
        deadlinks[i] = 0
    if profiling == 1:
        print("-->start simulate")
        stime2 = clock()
        stime = clock()

    update(importdata)

    if profiling == 1:
        print("-->update time", clock() - stime, "sec")
        stime = clock()

    for i in range(parnum):
        parlistcopy[i].id = parlist[i].id

        parlistcopy[i].loc[0] = parlist[i].loc[0]
        if parlist[i].loc[0] < minX:
            minX = parlist[i].loc[0]
        if parlist[i].loc[0] > maxX:
            maxX = parlist[i].loc[0]

        parlistcopy[i].loc[1] = parlist[i].loc[1]
        if parlist[i].loc[1] < minY:
            minY = parlist[i].loc[1]
        if parlist[i].loc[1] > maxY:
            maxY = parlist[i].loc[1]

        parlistcopy[i].loc[2] = parlist[i].loc[2]
        if parlist[i].loc[2] < minZ:
            minZ = parlist[i].loc[2]
        if parlist[i].loc[2] > maxZ:
            maxZ = parlist[i].loc[2]

        if parlist[i].sys.links_active == 1:
            if parlist[i].links_num > 0:
                for ii in range(parlist[i].links_num):
                    if parlist[i].links[ii].lenght > maxSize:
                        maxSize = parlist[i].links[ii].lenght

        if (parlist[i].size * 2) > maxSize:
            maxSize = (parlist[i].size * 2)

    if (maxX - minX) >= (maxY - minY) and (maxX - minX) >= (maxZ - minZ):
        parPool[0].axis = 0
        parPool[0].offset = 0 - minX
        parPool[0].max = maxX + parPool[0].offset

    if (maxY - minY) > (maxX - minX) and (maxY - minY) > (maxZ - minZ):
        parPool[0].axis = 1
        parPool[0].offset = 0 - minY
        parPool[0].max = maxY + parPool[0].offset

    if (maxZ - minZ) > (maxY - minY) and (maxZ - minZ) > (maxX - minX):
        parPool[0].axis = 2
        parPool[0].offset = 0 - minZ
        parPool[0].max = maxZ + parPool[0].offset

    if (parPool[0].max / ( cpunum * 10 )) > maxSize:
        maxSize = (parPool[0].max / ( cpunum * 10 ))


    cdef int pair
    cdef int heaps
    cdef float scale = 1 / ( maxSize * 2.1 )

    for pair in range(2):

        parPool[0].parity[pair].heap = \
            <Heap *>malloc((<int>(parPool[0].max * scale) + 1) * \
            cython.sizeof(Heap))

        for heaps in range(<int>(parPool[0].max * scale) + 1):
            parPool[0].parity[pair].heap[heaps].parnum = 0
            parPool[0].parity[pair].heap[heaps].maxalloc = 50

            parPool[0].parity[pair].heap[heaps].par = \
                <int *>malloc(parPool[0].parity[pair].heap[heaps].maxalloc * \
                cython.sizeof(int))

    for i in range(parnum):
        pair = <int>(((
            parlist[i].loc[parPool[0].axis] + parPool[0].offset) * scale) % 2
        )
        heaps = <int>((
            parlist[i].loc[parPool[0].axis] + parPool[0].offset) * scale
        )
        parPool[0].parity[pair].heap[heaps].parnum += 1

        if parPool[0].parity[pair].heap[heaps].parnum > \
                parPool[0].parity[pair].heap[heaps].maxalloc:

            parPool[0].parity[pair].heap[heaps].maxalloc = \
                <int>(parPool[0].parity[pair].heap[heaps].maxalloc * 1.25)

            parPool[0].parity[pair].heap[heaps].par = \
                <int *>realloc(
                    parPool[0].parity[pair].heap[heaps].par,
                    (parPool[0].parity[pair].heap[heaps].maxalloc + 2 ) * \
                    cython.sizeof(int)
                )

        parPool[0].parity[pair].heap[heaps].par[
            (parPool[0].parity[pair].heap[heaps].parnum - 1)] = parlist[i].id

    if profiling == 1:
        print("-->copy data time", clock() - stime, "sec")
        stime = clock()

    # Build spatial hash grid
    SpatialHash_build(spatialhash, parlistcopy, parnum, maxSize)

    if profiling == 1:
        print("-->create spatial hash time", clock() - stime,"sec")
        stime = clock()

    # Query neighbors using spatial hash
    with nogil:
        for i in prange(
                        parnum,
                        schedule='dynamic',
                        chunksize=2,
                        num_threads=cpunum
                        ):
            query_radius = parlist[i].size * 2.0
            if parlist[i].sys.collision_adhesion_factor > 0:
                query_radius = max(query_radius,(parlist[i].size * 2) * (1.0 + parlist[i].sys.collision_adhesion_distance))
            SpatialHash_query_neighbors(
                spatialhash,
                &parlist[i],
                parlist,
                query_radius
            )

    if profiling == 1:
        print("-->neighbours time", clock() - stime, "sec")
        stime = clock()

    # Apply Barnes-Hut gravity if enabled
    if gravity_enabled == 1:
        with nogil:
            apply_barnes_hut_gravity(cpunum)

    # Apply initial rotation ONCE (first frame only), right after gravity
    if gravity_enabled == 1 and initial_rotation_strength > 0 and initial_rotation_applied == 0:
        apply_initial_rotation_once(cpunum)

    if profiling == 1:
        print("-->gravity time", clock() - stime, "sec")
        stime = clock()

    #cdef int total_heaps = <int>(parPool[0].max * scale) + 1
    #cdef int total_pairs = 2

    # Create a list of tasks
    #tasks = [(pair, heaps, i) for pair in range(total_pairs) for heaps in range(total_heaps) for i in range(parPool[0].parity[pair].heap[heaps].parnum)]

    #cdef int index
    #for index in prange(len(tasks), nogil=True):
    #    pair, heaps, i = tasks[index]
    #    collide(&parlist[parPool[0].parity[pair].heap[heaps].par[i]])
    #    solve_link(&parlist[parPool[0].parity[pair].heap[heaps].par[i]])

    #    if parlist[parPool[0].parity[pair].heap[heaps].par[i]].neighboursnum > 1:
    #        parlist[parPool[0].parity[pair].heap[heaps].par[i]].neighboursnum = 0

    with nogil:
        for pair in range(2):
            for heaps in prange(
                                <int>(parPool[0].max * scale) + 1,
                                schedule='dynamic',
                                chunksize=2,
                                num_threads=cpunum
                                ):
                for i in range(parPool[0].parity[pair].heap[heaps].parnum):

                    collide(
                        &parlist[parPool[0].parity[pair].heap[heaps].par[i]]
                    )

                    solve_link(
                        &parlist[parPool[0].parity[pair].heap[heaps].par[i]]
                    )

                    if parlist[
                        parPool[0].parity[pair].heap[heaps].par[i]
                    ].neighboursnum > 1:

                       # free(parlist[i].neighbours)

                        parlist[
                            parPool[0].parity[pair].heap[heaps].par[i]
                        ].neighboursnum = 0

    if profiling == 1:
        print("-->collide/solve link time", clock() - stime, "sec")
        stime = clock()

    # Position integration: x += v * dt
    # This must be done AFTER all forces are applied to velocities
    with nogil:
        for i in prange(parnum, schedule='static', num_threads=cpunum):
            if parlist[i].state >= 3:  # Only alive particles
                parlist[i].loc[0] = parlist[i].loc[0] + parlist[i].vel[0] * deltatime
                parlist[i].loc[1] = parlist[i].loc[1] + parlist[i].vel[1] * deltatime
                parlist[i].loc[2] = parlist[i].loc[2] + parlist[i].vel[2] * deltatime

    if profiling == 1:
        print("-->position integration time", clock() - stime, "sec")
        stime = clock()

    exportdata = []
    parloc = []
    parvel = []
    parloctmp = []
    parveltmp = []

    for i in range(psysnum):
        for ii in range(psys[i].parnum):
            parloctmp.append(psys[i].particles[ii].loc[0])
            parloctmp.append(psys[i].particles[ii].loc[1])
            parloctmp.append(psys[i].particles[ii].loc[2])
            parveltmp.append(psys[i].particles[ii].vel[0])
            parveltmp.append(psys[i].particles[ii].vel[1])
            parveltmp.append(psys[i].particles[ii].vel[2])
        parloc.append(parloctmp)
        parvel.append(parveltmp)
        parloctmp = []
        parveltmp = []

    totallinks += newlinks
    pydeadlinks = 0
    for i in range(cpunum):
        pydeadlinks += deadlinks[i]
    totaldeadlinks += pydeadlinks

    exportdata = [
        parloc,
        parvel,
        newlinks,
        pydeadlinks,
        totallinks,
        totaldeadlinks
    ]

    for pair in range(2):
        for heaps in range(<int>(parPool[0].max * scale) + 1):
            parPool[0].parity[pair].heap[heaps].parnum = 0
            free(parPool[0].parity[pair].heap[heaps].par)
        free(parPool[0].parity[pair].heap)
    free(parPool[0].parity)
    free(parPool)

    # Mark simulation as started so update() won't overwrite our velocities
    simulation_started = 1

    if profiling == 1:
        print("-->export time", clock() - stime, "sec")
        print("-->all process time", clock() - stime2, "sec")
    return exportdata
