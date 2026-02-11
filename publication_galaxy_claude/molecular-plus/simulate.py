import bpy
import array
import numpy as np
import os
import csv as csv_module
from .utils import get_object


# Field level 1 -> grouped ID mapping (sorted by field_level_0 FREQUENCY)
# Most common categories first for better color distribution with blackbody ramp
# Medicine: 0-40, Biology: 41-58, Psychology: 59-72, Computer science: 73-126,
# Chemistry: 127-146, Physics: 147-162, Materials science: 163-175, Sociology: 176-187,
# Geology: 188-199, Mathematics: 200-206, Political science: 207-215, Business: 216-231,
# Geography: 232-240, Environmental science: 241-251, Economics: 252-268,
# History: 269-272, Engineering: 273-278, Art: 279-282, Philosophy: 283
GROUPED_FIELD_L1_IDS = {
    # Medicine (0-40) - 36% of data
    "Anatomy": 0, "Anesthesia": 1, "Animal science": 2, "Bioinformatics": 3, "Cardiology": 4, "Demography": 5, "Dentistry": 6, "Dermatology": 7, "Emergency medicine": 8, "Environmental health": 9, "Family medicine": 10, "Gastroenterology": 11, "General surgery": 12, "Gerontology": 13, "Gynecology": 14, "Immunology": 15, "Intensive care medicine": 16, "Internal medicine": 17, "Library science": 18, "Medical education": 19, "Medical emergency": 20, "Medical physics": 21, "Nuclear medicine": 22, "Nursing": 23, "Obstetrics": 24, "Oncology": 25, "Operations management": 26, "Ophthalmology": 27, "Optometry": 28, "Orthodontics": 29, "Pathology": 30, "Pediatrics": 31, "Pharmacology": 32, "Physical medicine and rehabilitation": 33, "Physical therapy": 34, "Physiology": 35, "Psychiatry": 36, "Radiology": 37, "Surgery": 38, "Traditional medicine": 39, "Urology": 40,
    # Biology (41-58) - 13% of data
    "Agronomy": 41, "Andrology": 42, "Biotechnology": 43, "Botany": 44, "Cancer research": 45, "Cell biology": 46, "Computational biology": 47, "Ecology": 48, "Endocrinology": 49, "Evolutionary biology": 50, "Genetics": 51, "Horticulture": 52, "Microbiology": 53, "Molecular biology": 54, "Toxicology": 55, "Veterinary medicine": 56, "Virology": 57, "Zoology": 58,
    # Psychology (59-72) - 11% of data
    "Applied psychology": 59, "Audiology": 60, "Clinical psychology": 61, "Cognitive psychology": 62, "Cognitive science": 63, "Communication": 64, "Criminology": 65, "Developmental psychology": 66, "Linguistics": 67, "Mathematics education": 68, "Neuroscience": 69, "Psychoanalysis": 70, "Psychotherapist": 71, "Social psychology": 72,
    # Computer science (73-126) - 9% of data
    "Acoustics": 73, "Algorithm": 74, "Arithmetic": 75, "Artificial intelligence": 76, "Automotive engineering": 77, "Biochemical engineering": 78, "Biological system": 79, "Computational science": 80, "Computer architecture": 81, "Computer engineering": 82, "Computer graphics (images)": 83, "Computer hardware": 84, "Computer network": 85, "Computer security": 86, "Computer vision": 87, "Control engineering": 88, "Data mining": 89, "Data science": 90, "Database": 91, "Distributed computing": 92, "Electrical engineering": 93, "Electronic engineering": 94, "Embedded system": 95, "Engineering drawing": 96, "Engineering management": 97, "Human–computer interaction": 98, "Industrial engineering": 99, "Information retrieval": 100, "Internet privacy": 101, "Knowledge management": 102, "Machine learning": 103, "Management science": 104, "Manufacturing engineering": 105, "Mathematical optimization": 106, "Mechanical engineering": 107, "Multimedia": 108, "Natural language processing": 109, "Operating system": 110, "Operations research": 111, "Parallel computing": 112, "Process engineering": 113, "Programming language": 114, "Real-time computing": 115, "Reliability engineering": 116, "Remote sensing": 117, "Risk analysis (engineering)": 118, "Simulation": 119, "Software engineering": 120, "Speech recognition": 121, "Systems engineering": 122, "Telecommunications": 123, "Theoretical computer science": 124, "Transport engineering": 125, "World Wide Web": 126,
    # Chemistry (127-146) - 6% of data
    "Biochemistry": 127, "Biophysics": 128, "Chromatography": 129, "Combinatorial chemistry": 130, "Computational chemistry": 131, "Crystallography": 132, "Food science": 133, "Inorganic chemistry": 134, "Medicinal chemistry": 135, "Molecular physics": 136, "Nuclear chemistry": 137, "Nuclear magnetic resonance": 138, "Organic chemistry": 139, "Photochemistry": 140, "Physical chemistry": 141, "Polymer chemistry": 142, "Pulp and paper industry": 143, "Radiochemistry": 144, "Stereochemistry": 145, "Thermodynamics": 146,
    # Physics (147-162) - 7% of data
    "Aerospace engineering": 147, "Astrobiology": 148, "Astronomy": 149, "Astrophysics": 150, "Atomic physics": 151, "Classical mechanics": 152, "Computational physics": 153, "Geophysics": 154, "Mathematical physics": 155, "Mechanics": 156, "Nuclear physics": 157, "Particle physics": 158, "Quantum electrodynamics": 159, "Quantum mechanics": 160, "Statistical physics": 161, "Theoretical physics": 162,
    # Materials science (163-175) - 7% of data
    "Biomedical engineering": 163, "Chemical engineering": 164, "Chemical physics": 165, "Composite material": 166, "Condensed matter physics": 167, "Engineering physics": 168, "Metallurgy": 169, "Nanotechnology": 170, "Nuclear engineering": 171, "Optics": 172, "Optoelectronics": 173, "Polymer science": 174, "Structural engineering": 175,
    # Sociology (176-187) - 2% of data
    "Aesthetics": 176, "Anthropology": 177, "Engineering ethics": 178, "Environmental ethics": 179, "Epistemology": 180, "Gender studies": 181, "Management": 182, "Media studies": 183, "Pedagogy": 184, "Positive economics": 185, "Religious studies": 186, "Social science": 187,
    # Geology (188-199) - 1% of data
    "Earth science": 188, "Geochemistry": 189, "Geodesy": 190, "Geomorphology": 191, "Geotechnical engineering": 192, "Mineralogy": 193, "Mining engineering": 194, "Oceanography": 195, "Paleontology": 196, "Petrology": 197, "Physical geography": 198, "Seismology": 199,
    # Mathematics (200-206) - 1.5% of data
    "Applied mathematics": 200, "Combinatorics": 201, "Discrete mathematics": 202, "Geometry": 203, "Mathematical analysis": 204, "Pure mathematics": 205, "Statistics": 206,
    # Political science (207-215) - 2% of data
    "Development economics": 207, "Economic growth": 208, "Economic history": 209, "Economy": 210, "Law": 211, "Law and economics": 212, "Political economy": 213, "Public administration": 214, "Public relations": 215,
    # Business (216-231) - 1% of data
    "Accounting": 216, "Actuarial science": 217, "Advertising": 218, "Agricultural economics": 219, "Agricultural science": 220, "Business administration": 221, "Commerce": 222, "Environmental economics": 223, "Environmental planning": 224, "Finance": 225, "Financial system": 226, "Industrial organization": 227, "International trade": 228, "Marketing": 229, "Natural resource economics": 230, "Process management": 231,
    # Geography (232-240) - 1% of data
    "Agroforestry": 232, "Archaeology": 233, "Cartography": 234, "Economic geography": 235, "Environmental resource management": 236, "Fishery": 237, "Forestry": 238, "Regional science": 239, "Socioeconomics": 240,
    # Environmental science (241-251) - 0.7% of data
    "Agricultural engineering": 241, "Atmospheric sciences": 242, "Climatology": 243, "Environmental chemistry": 244, "Environmental engineering": 245, "Environmental protection": 246, "Meteorology": 247, "Petroleum engineering": 248, "Soil science": 249, "Waste management": 250, "Water resource management": 251,
    # Economics (252-268) - 1% of data
    "Classical economics": 252, "Demographic economics": 253, "Econometrics": 254, "Economic policy": 255, "Economic system": 256, "Financial economics": 257, "International economics": 258, "Keynesian economics": 259, "Labour economics": 260, "Macroeconomics": 261, "Market economy": 262, "Mathematical economics": 263, "Microeconomics": 264, "Monetary economics": 265, "Neoclassical economics": 266, "Public economics": 267, "Welfare economics": 268,
    # History (269-272) - 0.2% of data
    "Ancient history": 269, "Classics": 270, "Ethnology": 271, "Genealogy": 272,
    # Engineering (273-278) - 0.3% of data
    "Aeronautics": 273, "Architectural engineering": 274, "Civil engineering": 275, "Construction engineering": 276, "Forensic engineering": 277, "Marine engineering": 278,
    # Art (279-282) - 0.6% of data
    "Art history": 279, "Humanities": 280, "Literature": 281, "Visual arts": 282,
    # Philosophy (283) - 0% of data
    "Theology": 283,
}


def calculate_sizes_from_csv(psys_settings, num_particles):
    """
    Calculate particle sizes from CSV file using current settings.
    Returns array of sizes, or None if no CSV or error.

    This can be called independently to restore sizes without re-simulating.
    """
    csv_path = psys_settings.mol_initial_csv
    if not csv_path:
        return None

    csv_path_abs = bpy.path.abspath(csv_path)
    if not os.path.exists(csv_path_abs):
        print(f"  CSV file not found: {csv_path_abs}")
        return None

    # Initialize sizes with default (particle_size * min_scale)
    par_size = array.array("f", [psys_settings.particle_size * psys_settings.mol_csv_min_scale]) * num_particles

    try:
        with open(csv_path_abs) as f:
            reader = csv_module.DictReader(f)
            fieldnames = reader.fieldnames

            # Detect scale column
            scale_col = None
            if 'scale' in fieldnames:
                scale_col = 'scale'
            elif 'cited_by_count' in fieldnames:
                scale_col = 'cited_by_count'
            elif 'total_citation_count' in fieldnames:
                scale_col = 'total_citation_count'
            elif 'citation_count' in fieldnames:
                scale_col = 'citation_count'
            elif 'citations' in fieldnames:
                scale_col = 'citations'

            if not scale_col:
                print(f"  No scale column found in CSV")
                return par_size  # Return default sizes

            # Process rows
            for idx, row in enumerate(reader):
                if idx >= num_particles:
                    break

                # Get raw scale value
                raw_scale = 0.0
                try:
                    val = row.get(scale_col, '')
                    if val and val.strip():
                        raw_scale = float(val)
                except (ValueError, TypeError):
                    pass

                # Apply minimum scale
                min_scale = psys_settings.mol_csv_min_scale
                clamped_scale = max(min_scale, raw_scale)

                # Apply volume mode (cube root) if selected
                if psys_settings.mol_csv_scale_mode == 'VOLUME':
                    effective_scale = clamped_scale ** (1.0 / 3.0)
                else:
                    effective_scale = clamped_scale

                # Apply global multiplier
                global_mult = psys_settings.mol_csv_scale_multiplier
                final_scale = effective_scale * global_mult

                # Calculate final size
                par_size[idx] = psys_settings.particle_size * final_scale

        sizes = list(par_size)
        print(f"  CSV sizes restored: range [{min(sizes):.6f}, {max(sizes):.6f}]")
        return par_size

    except Exception as e:
        print(f"  Error reading CSV for sizes: {e}")
        return None


def calculate_fields_from_csv(psys_settings, num_particles):
    """
    Calculate particle field IDs from CSV file using current settings.
    Returns array of field IDs (3 components per particle for angular_velocity),
    or None if no CSV or no field column.

    This can be called independently to restore field colors without re-simulating.
    """
    csv_path = psys_settings.mol_initial_csv
    if not csv_path:
        return None

    csv_path_abs = bpy.path.abspath(csv_path)
    if not os.path.exists(csv_path_abs):
        print(f"  CSV file not found: {csv_path_abs}")
        return None

    # Initialize field array (3 components per particle: field_id, 0, 0)
    par_field = array.array("f", [0.0, 0.0, 0.0]) * num_particles

    try:
        with open(csv_path_abs) as f:
            reader = csv_module.DictReader(f)
            fieldnames = reader.fieldnames

            # Detect field/category column for coloring
            # Use user-selected field level if available
            field_col = None
            if 'field_id' in fieldnames:
                field_col = 'field_id'
            else:
                # Check for field_level_X based on user selection
                selected_level = psys_settings.mol_csv_field_level
                level_col = f'field_level_{selected_level}'
                if level_col in fieldnames:
                    field_col = level_col
                # Fallback to any available field_level
                elif 'field_level_0' in fieldnames:
                    field_col = 'field_level_0'
                elif 'field_level_1' in fieldnames:
                    field_col = 'field_level_1'
                elif 'field_level_2' in fieldnames:
                    field_col = 'field_level_2'
                elif 'mid_level' in fieldnames:
                    field_col = 'mid_level'
                elif 'field' in fieldnames:
                    field_col = 'field'
                elif 'category' in fieldnames:
                    field_col = 'category'
                elif 'cluster' in fieldnames:
                    field_col = 'cluster'

            if not field_col:
                print(f"  No field column found in CSV")
                return None

            # Build field name to ID mapping (for string fields like "Medicine")
            field_to_id = {}
            next_field_id = 0
            fields_set = 0

            # Process rows
            for idx, row in enumerate(reader):
                if idx >= num_particles:
                    break

                if row.get(field_col):
                    field_val = row[field_col]
                    try:
                        # Try numeric first
                        field_id = float(field_val)
                    except (ValueError, TypeError):
                        # String field name - convert to ID
                        # Use grouped mapping for field_level_1 to cluster related fields
                        if field_col == 'field_level_1' and field_val in GROUPED_FIELD_L1_IDS:
                            field_id = float(GROUPED_FIELD_L1_IDS[field_val])
                            if field_val not in field_to_id:
                                field_to_id[field_val] = GROUPED_FIELD_L1_IDS[field_val]
                        else:
                            # Fallback to first-seen order for other columns or unknown fields
                            if field_val not in field_to_id:
                                field_to_id[field_val] = next_field_id
                                next_field_id += 1
                            field_id = float(field_to_id[field_val])

                    par_field[idx * 3] = field_id
                    par_field[idx * 3 + 1] = 0.0  # Y unused
                    par_field[idx * 3 + 2] = 0.0  # Z unused
                    fields_set += 1

        # Print field name to ID mapping if string fields were converted
        if field_to_id:
            print(f"  Field mapping ({field_col}):")
            for name, fid in sorted(field_to_id.items(), key=lambda x: x[1]):
                print(f"    {fid}: {name}")

        print(f"  CSV fields restored: {fields_set} particles with field IDs from '{field_col}'")
        return par_field

    except Exception as e:
        print(f"  Error reading CSV for fields: {e}")
        return None


def relax_particle_overlaps(par_loc, par_size, max_iterations=100, min_separation=1.001, strength=0.8, num_threads=4):
    """
    Push overlapping particles apart until no overlaps remain.
    Calls into Cython spatial-hash implementation for O(n) performance.
    """
    from molecular_core import core
    return core.relax_overlaps(par_loc, par_size, max_iterations, min_separation, strength, num_threads)


def get_gn_float_attr(obj, mod_name, attr_name, weak_map):
    # Find target modifier index
    for target_idx, mod in enumerate(obj.modifiers):
        if mod.name == mod_name:
            break
    else:
        raise ValueError(f"Modifier '{mod_name}' not found")

    print("start bake weakmap from geo nodes: ", mod.name)

    # Temporarily disable modifiers after target
    orig_states = [(mod, mod.show_viewport) for mod in obj.modifiers[target_idx + 1 :]]
    for mod, _ in orig_states:
        mod.show_viewport = False

    # Force depsgraph to re-evaluate without those modifiers
    obj.update_tag()  # ← Critical!
    bpy.context.view_layer.update()

    try:
        # Evaluate and read FLOAT attribute directly into weak_map
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.data

        attr = mesh.attributes.get(attr_name)

        print("attributes: " + str(len(attr.data)))
        print("np_array: " + str(len(weak_map)))

        if len(attr.data) != len(weak_map):
            raise ValueError("Attribute and weak_map lengths do not match !")

        attr.data.foreach_get("value", weak_map)
    finally:
        # Restore modifier states
        for mod, state in orig_states:
            mod.show_viewport = state


def get_weak_map(obj, psys, par_weak):
    print("start bake weakmap from:", obj.name)

    tex = psys.settings.texture_slots[0].texture
    texm_offset = psys.settings.texture_slots[0].offset
    texm_scale = psys.settings.texture_slots[0].scale
    parlen = len(psys.particles)
    colramp = tex.color_ramp

    for i in range(parlen):
        newuv = (
            (psys.particles[i].location + texm_offset) @ obj.matrix_world * texm_scale
        )
        if tex.use_color_ramp:
            par_weak[i] = colramp.evaluate(tex.evaluate(newuv)[0])[0]
        else:
            par_weak[i] = tex.evaluate(newuv)[0]

        if psys.settings.mol_inv_weak_map:
            par_weak[i] = 1 - par_weak[i]

    print("Weakmap baked on:", psys.settings.name)


def pack_data(context, initiate):
    psyslen = 0
    parnum = 0
    scene = context.scene

    for ob in bpy.data.objects:
        obj = get_object(context, ob)  # Evaluated object (for particle positions)

        for i, psys in enumerate(obj.particle_systems):
            # IMPORTANT: Use settings from ORIGINAL object, not evaluated
            # The evaluated object's settings are a stale copy that doesn't update
            psys_settings = ob.particle_systems[i].settings

            if psys_settings.mol_matter != "-1":
                psys_settings.mol_density = float(psys_settings.mol_matter)

            parlen = len(psys.particles)

            if psys_settings.mol_active and parlen:
                par_loc = array.array("f", [0, 0, 0]) * parlen
                par_vel = array.array("f", [0, 0, 0]) * parlen
                par_size = array.array("f", [0]) * parlen
                par_alive = array.array("h", [0]) * parlen

                parnum += parlen

                psys.particles.foreach_get("location", par_loc)
                psys.particles.foreach_get("velocity", par_vel)
                psys.particles.foreach_get("alive_state", par_alive)

                # Get sizes early so CSV can override them
                if initiate:
                    psys.particles.foreach_get("size", par_size)

                # Initialize scale multipliers array (default 1.0, CSV overrides)
                # This stores RAW multipliers; final size = particle_size * scale_multiplier
                par_scale = None
                if initiate:
                    par_scale = array.array("f", [1.0]) * parlen

                # Initialize field IDs array (3 components for angular_velocity: field_id, 0, 0)
                par_field = None
                if initiate:
                    par_field = array.array("f", [0, 0, 0]) * parlen

                # CSV override for initial positions, sizes, and field IDs (from particle settings)
                if initiate:
                    csv_path = psys_settings.mol_initial_csv
                    if csv_path:
                        import os
                        import csv as csv_module
                        csv_path_abs = bpy.path.abspath(csv_path)
                        if os.path.exists(csv_path_abs):
                            csv_rows = 0
                            has_scale = False
                            has_field = False
                            is_2d = False
                            with open(csv_path_abs) as f:
                                reader = csv_module.DictReader(f)
                                # Detect column names from first row
                                fieldnames = reader.fieldnames
                                # Support both generic (x,y,z) and tsne (tsne_x, tsne_y, tsne_z) column names
                                if 'x' in fieldnames:
                                    x_col, y_col = 'x', 'y'
                                    z_col = 'z' if 'z' in fieldnames else None
                                elif 'tsne_x' in fieldnames:
                                    x_col, y_col = 'tsne_x', 'tsne_y'
                                    z_col = 'tsne_z' if 'tsne_z' in fieldnames else None
                                else:
                                    print(f"  CSV Warning: No recognized position columns (x,y,z or tsne_x,tsne_y,tsne_z)")
                                    x_col, y_col, z_col = None, None, None

                                # Detect scale column (generic or citation-based)
                                scale_col = None
                                if 'scale' in fieldnames:
                                    scale_col = 'scale'
                                elif 'cited_by_count' in fieldnames:
                                    scale_col = 'cited_by_count'
                                elif 'total_citation_count' in fieldnames:
                                    scale_col = 'total_citation_count'
                                elif 'citation_count' in fieldnames:
                                    scale_col = 'citation_count'
                                elif 'citations' in fieldnames:
                                    scale_col = 'citations'

                                # Detect field/category column for coloring
                                # Use user-selected field level if available
                                field_col = None
                                if 'field_id' in fieldnames:
                                    field_col = 'field_id'
                                else:
                                    # Check for field_level_X based on user selection
                                    selected_level = psys_settings.mol_csv_field_level
                                    level_col = f'field_level_{selected_level}'
                                    if level_col in fieldnames:
                                        field_col = level_col
                                    # Fallback to any available field_level
                                    elif 'field_level_0' in fieldnames:
                                        field_col = 'field_level_0'
                                    elif 'field_level_1' in fieldnames:
                                        field_col = 'field_level_1'
                                    elif 'field_level_2' in fieldnames:
                                        field_col = 'field_level_2'
                                    elif 'mid_level' in fieldnames:
                                        field_col = 'mid_level'
                                    elif 'field' in fieldnames:
                                        field_col = 'field'
                                    elif 'category' in fieldnames:
                                        field_col = 'category'
                                    elif 'cluster' in fieldnames:
                                        field_col = 'cluster'

                                # Build field name to ID mapping (for string fields like "Medicine")
                                field_to_id = {}
                                next_field_id = 0

                                if x_col and y_col:
                                    is_2d = (z_col is None)
                                    for idx, row in enumerate(reader):
                                        csv_rows += 1
                                        if idx >= parlen:
                                            continue  # Count all rows but only use up to parlen
                                        par_loc[idx*3] = float(row[x_col])
                                        par_loc[idx*3+1] = float(row[y_col])
                                        par_loc[idx*3+2] = float(row[z_col]) if z_col else 0.0
                                        # Calculate particle size from CSV scale
                                        # Pipeline: raw_csv -> max(min_scale) -> volume_mode -> global_multiplier -> particle_size
                                        raw_scale = 0.0
                                        if scale_col:
                                            try:
                                                val = row.get(scale_col, '')
                                                if val and val.strip():
                                                    raw_scale = float(val)
                                                    has_scale = True
                                            except (ValueError, TypeError):
                                                pass

                                        # Apply minimum scale (prevents zero-size)
                                        min_scale = psys_settings.mol_csv_min_scale
                                        clamped_scale = max(min_scale, raw_scale)

                                        # Apply volume mode (cube root) if selected
                                        if psys_settings.mol_csv_scale_mode == 'VOLUME':
                                            effective_scale = clamped_scale ** (1.0 / 3.0)
                                        else:
                                            effective_scale = clamped_scale

                                        # Apply global multiplier
                                        global_mult = psys_settings.mol_csv_scale_multiplier
                                        final_scale = effective_scale * global_mult

                                        # Store and calculate final size
                                        par_scale[idx] = final_scale
                                        par_size[idx] = psys_settings.particle_size * final_scale
                                        # Store field ID in angular_velocity (X component)
                                        # Convert string field names to numeric IDs
                                        if field_col and row.get(field_col):
                                            field_val = row[field_col]
                                            try:
                                                # Try numeric first
                                                field_id = float(field_val)
                                            except (ValueError, TypeError):
                                                # String field name - convert to ID
                                                # Use grouped mapping for field_level_1 to cluster related fields
                                                if field_col == 'field_level_1' and field_val in GROUPED_FIELD_L1_IDS:
                                                    field_id = float(GROUPED_FIELD_L1_IDS[field_val])
                                                    if field_val not in field_to_id:
                                                        field_to_id[field_val] = GROUPED_FIELD_L1_IDS[field_val]
                                                else:
                                                    # Fallback to first-seen order for other columns or unknown fields
                                                    if field_val not in field_to_id:
                                                        field_to_id[field_val] = next_field_id
                                                        next_field_id += 1
                                                    field_id = float(field_to_id[field_val])
                                            par_field[idx*3] = field_id
                                            par_field[idx*3+1] = 0.0  # Y unused
                                            par_field[idx*3+2] = 0.0  # Z unused
                                            has_field = True
                            loaded = min(csv_rows, parlen)
                            dim_msg = "2D" if is_2d else "3D"
                            size_msg = ", with scales" if has_scale else ""
                            field_msg = f", with {len(field_to_id)} fields" if has_field and field_to_id else (", with field IDs" if has_field else "")
                            print(f"  CSV: Loaded {loaded} {dim_msg} positions{size_msg}{field_msg} from {csv_path_abs}")
                            # Print field name to ID mapping if string fields were converted
                            if field_to_id:
                                print(f"  Field mapping ({field_col}):")
                                for name, fid in sorted(field_to_id.items(), key=lambda x: x[1]):
                                    print(f"    {fid}: {name}")
                            if csv_rows != parlen:
                                print(f"  Warning: CSV has {csv_rows} rows, particle system has {parlen} particles")

                if initiate:
                    par_mass = array.array("f", [0]) * parlen

                    # Note: par_size already fetched earlier (before CSV override)

                    # use texture in slot 0 for particle weak
                    par_weak = array.array("f", [1.0]) * parlen

                    if psys_settings.mol_bake_weak_map_geo:
                        get_gn_float_attr(ob, "M+ weak map", "weak_map", par_weak)
                        # Force depsgraph to re-evaluate with modifiers reenabled
                        ob.update_tag()  # ← Critical!
                        bpy.context.view_layer.update()
                        obj = get_object(context, ob)
                        psys = obj.particle_systems[i]

                    if psys_settings.mol_bake_weak_map:
                        get_weak_map(obj, psys, par_weak)

                    if psys_settings.mol_density_active:
                        par_mass_np = np.asarray(par_mass)
                        par_size_np = np.asarray(par_size)
                        par_mass_np[:] = psys_settings.mol_density * (
                            4 / 3 * 3.141592653589793 * ((par_size_np / 2) ** 3)
                        )
                        par_mass = par_mass_np

                    else:
                        par_mass = array.array("f", [psys_settings.mass]) * parlen

                    if scene.timescale != 1.0:
                        psys_settings.timestep = 1 / (
                            scene.render.fps / scene.timescale
                        )
                    else:
                        psys_settings.timestep = 1 / scene.render.fps

                    psyslen += 1

                    if bpy.context.scene.mol_minsize > min(par_size):
                        bpy.context.scene.mol_minsize = min(par_size)

                    if psys_settings.mol_link_samevalue:
                        psys_settings.mol_link_estiff = psys_settings.mol_link_stiff
                        psys_settings.mol_link_estiffrand = (
                            psys_settings.mol_link_stiffrand
                        )
                        psys_settings.mol_link_estiffexp = (
                            psys_settings.mol_link_stiffexp
                        )
                        psys_settings.mol_link_edamp = psys_settings.mol_link_damp
                        psys_settings.mol_link_edamprand = (
                            psys_settings.mol_link_damprand
                        )
                        psys_settings.mol_link_ebroken = psys_settings.mol_link_broken
                        psys_settings.mol_link_ebrokenrand = (
                            psys_settings.mol_link_brokenrand
                        )

                    if psys_settings.mol_relink_samevalue:
                        psys_settings.mol_relink_estiff = psys_settings.mol_relink_stiff
                        psys_settings.mol_relink_estiffrand = (
                            psys_settings.mol_relink_stiffrand
                        )
                        psys_settings.mol_relink_estiffexp = (
                            psys_settings.mol_relink_stiffexp
                        )
                        psys_settings.mol_relink_edamp = psys_settings.mol_relink_damp
                        psys_settings.mol_relink_edamprand = (
                            psys_settings.mol_relink_damprand
                        )
                        psys_settings.mol_relink_ebroken = (
                            psys_settings.mol_relink_broken
                        )
                        psys_settings.mol_relink_ebrokenrand = (
                            psys_settings.mol_relink_brokenrand
                        )

                    # Pre-simulation overlap relaxation
                    if psys_settings.mol_relax_overlaps:
                        iters, initial, final = relax_particle_overlaps(
                            par_loc,
                            par_size,
                            max_iterations=psys_settings.mol_relax_iterations,
                            min_separation=psys_settings.mol_relax_separation,
                            strength=psys_settings.mol_relax_strength,
                            num_threads=scene.mol_cpu
                        )
                        if initial > 0:
                            if final == 0:
                                print(f"  Relaxation: {initial} overlaps resolved in {iters} iterations")
                            else:
                                print(f"  Relaxation: {initial} initial overlaps, {final} remaining after {iters} iterations (increase iterations)")
                        else:
                            print(f"  Relaxation: no overlaps detected")

                    params = [0] * 56

                    params[0] = psys_settings.mol_selfcollision_active
                    params[1] = psys_settings.mol_othercollision_active
                    params[2] = psys_settings.mol_collision_group
                    params[3] = psys_settings.mol_friction
                    params[4] = psys_settings.mol_collision_damp
                    params[5] = psys_settings.mol_links_active
                    params[6] = psys_settings.mol_link_length
                    params[7] = psys_settings.mol_link_max
                    params[8] = psys_settings.mol_link_tension
                    params[9] = psys_settings.mol_link_tensionrand
                    params[10] = psys_settings.mol_link_stiff
                    params[11] = psys_settings.mol_link_stiffrand
                    params[12] = psys_settings.mol_link_stiffexp
                    params[13] = psys_settings.mol_link_damp
                    params[14] = psys_settings.mol_link_damprand
                    params[15] = psys_settings.mol_link_broken
                    params[16] = psys_settings.mol_link_brokenrand
                    params[17] = psys_settings.mol_link_estiff
                    params[18] = psys_settings.mol_link_estiffrand
                    params[19] = psys_settings.mol_link_estiffexp
                    params[20] = psys_settings.mol_link_edamp
                    params[21] = psys_settings.mol_link_edamprand
                    params[22] = psys_settings.mol_link_ebroken
                    params[23] = psys_settings.mol_link_ebrokenrand
                    params[24] = psys_settings.mol_relink_group
                    params[25] = psys_settings.mol_relink_chance
                    params[26] = psys_settings.mol_relink_chancerand
                    params[27] = psys_settings.mol_relink_max
                    params[28] = psys_settings.mol_relink_tension
                    params[29] = psys_settings.mol_relink_tensionrand
                    params[30] = psys_settings.mol_relink_stiff
                    params[31] = psys_settings.mol_relink_stiffexp
                    params[32] = psys_settings.mol_relink_stiffrand
                    params[33] = psys_settings.mol_relink_damp
                    params[34] = psys_settings.mol_relink_damprand
                    params[35] = psys_settings.mol_relink_broken
                    params[36] = psys_settings.mol_relink_brokenrand
                    params[37] = psys_settings.mol_relink_estiff
                    params[38] = psys_settings.mol_relink_estiffexp
                    params[39] = psys_settings.mol_relink_estiffrand
                    params[40] = psys_settings.mol_relink_edamp
                    params[41] = psys_settings.mol_relink_edamprand
                    params[42] = psys_settings.mol_relink_ebroken
                    params[43] = psys_settings.mol_relink_ebrokenrand
                    params[44] = psys_settings.mol_link_friction
                    params[45] = psys_settings.mol_link_group
                    params[46] = psys_settings.mol_other_link_active
                    params[47] = int(psys_settings.mol_link_rellength)
                    params[48] = psys_settings.mol_collision_adhesion_search_distance
                    params[49] = psys_settings.mol_collision_adhesion_factor
                    # Gravity (Barnes-Hut)
                    params[50] = psys_settings.mol_gravity_active
                    params[51] = psys_settings.mol_gravity_strength
                    params[52] = psys_settings.mol_gravity_theta
                    params[53] = psys_settings.mol_gravity_softening
                    params[54] = psys_settings.mol_gravity_initial_rotation
                    params[55] = psys_settings.mol_gravity_rotation_falloff

                mol_exportdata = bpy.context.scene.mol_exportdata

                if initiate:
                    mol_exportdata[0][2] = psyslen
                    mol_exportdata[0][3] = parnum
                    mol_exportdata.append(
                        (
                            parlen,
                            par_loc,
                            par_vel,
                            par_size,
                            par_mass,
                            par_alive,
                            params,
                            par_weak,
                            par_field,  # Field IDs for angular_velocity coloring (index 8)
                            par_scale,  # Raw scale multipliers for dynamic particle_size (index 9)
                        )
                    )
                else:
                    self_coll = psys_settings.mol_selfcollision_active
                    mol_exportdata.append((par_loc, par_vel, par_alive, self_coll))
