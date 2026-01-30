# ====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ======================= END GPL LICENSE BLOCK ========================

import bpy
from bpy.app.handlers import persistent


@persistent
def mol_restore_on_load(dummy):
    """
    Auto-restore particle sizes and field colors from CSV when file loads.
    Runs ONCE on file load - enables command line renders to work correctly.
    """
    # Delay execution slightly to ensure all data is loaded
    # Use a timer to run after Blender finishes loading
    def _do_restore():
        try:
            # Only restore if there are particle systems with mol_active and CSV set
            for obj in bpy.data.objects:
                for psys in obj.particle_systems:
                    if psys.settings.mol_active and psys.settings.mol_initial_csv:
                        print("Molecular+: Auto-restoring sizes and colors from CSV...")
                        bpy.ops.object.mol_restore_sizes()
                        bpy.ops.object.mol_restore_fields()
                        print("Molecular+: Restore complete.")
                        return None  # Done, don't repeat
            # No molecular particle systems with CSV found
            return None
        except Exception as e:
            print(f"Molecular+: Auto-restore skipped ({e})")
            return None

    # Run after 0.1 seconds to let Blender finish loading
    bpy.app.timers.register(_do_restore, first_interval=0.1)


bl_info = {
    "name": "Molecular+",
    "author": "Gregor Quade (u3dreal)",
    "version": (1, 21, 8),
    "blender": (4, 2, 0),
    "location": "Properties editor > Physics Tab",
    "description": "Addon for calculating collisions "
    "and for creating links between particles",
    "warning": "",  # used for warning icon and text in addons panel
    "wiki_url": "http://q3de.com/research/molecular/",
    "tracker_url": "https://discord.gg/tAwvNEAfA3",
    "category": "Physics",
}


def register():
    from . import properties, ui, operators, creators, addon_prefrences

    properties.define_props()

    for operator in operators.operator_classes:
        bpy.utils.register_class(operator)

    for panel in ui.panel_classes:
        bpy.utils.register_class(panel)

    for panel in creators.create_classes:
        bpy.utils.register_class(panel)

    bpy.utils.register_class(addon_prefrences.pref_classes)

    bpy.types.PHYSICS_PT_add.append(ui.append_to_PHYSICS_PT_add_panel)

    # Register load_post handler for auto-restoring CSV data
    if mol_restore_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(mol_restore_on_load)
    print("Molecular+: Registered load_post handler for auto-restore")


def unregister():
    from . import ui, operators, creators, addon_prefrences

    # Unregister load_post handler
    if mol_restore_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(mol_restore_on_load)
    print("Molecular+: Unregistered load_post handler")

    bpy.types.PHYSICS_PT_add.remove(ui.append_to_PHYSICS_PT_add_panel)

    for operator in reversed(operators.operator_classes):
        bpy.utils.unregister_class(operator)

    for panel in reversed(ui.panel_classes):
        bpy.utils.unregister_class(panel)

    for panel in reversed(creators.create_classes):
        bpy.utils.unregister_class(panel)

    bpy.utils.unregister_class(addon_prefrences.pref_classes)


if __name__ == "__main__":
    register()
