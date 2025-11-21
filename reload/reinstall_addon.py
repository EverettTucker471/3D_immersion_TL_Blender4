"""
Reinstalls the 3D immersion TL addon and configures the TL_coupling path
Author(s): Everett Tucker
Usage:
    blender --background --python reload_addon.py -- \
        --addon_zip_path /path/to/3D_immersion_TL-master.zip \
        --tl_coupling_path /path/to/TL_coupling
"""

import sys
import bpy
import argparse
import importlib
import subprocess


def restart_blender():
    """Relaunch Blender with the same command-line arguments."""
    blender_executable = bpy.app.binary_path
    original_args = [a for a in sys.argv if "reinstall_addon.py" not in a]
    subprocess.Popen([blender_executable] + original_args)
    bpy.ops.wm.quit_blender()


def main():

    # Removing the breaker argument from between the blender and python calls
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    # Getting command-line arguments from the reload_addon script
    parser = argparse.ArgumentParser(description='Reinstall 3D immersion TL with the given TL_coupling path')
    parser.add_argument('--addon_zip_path', help="The absolute path to your zipped addon (3D_immersion_TL-master.zip)", required=True)
    parser.add_argument('--tl_coupling_path', help='The absolute path to your TL_coupling directory', required=True)
    parser.add_argument('--addon_name', help="The name of the add-on, should be the same as the repo", required=True)
    args = parser.parse_args(argv)

    # Install the addon from the zip path
    bpy.ops.preferences.addon_install(filepath=args.addon_zip_path, overwrite=True, enable_on_install=True)
    bpy.ops.preferences.addon_disable(module=args.addon_name)
    bpy.ops.preferences.addon_enable(module=args.addon_name)

    # Configure the addon with the tl_coupling path

    print(bpy.context.preferences.addons[args.addon_name].preferences)
    prefs = bpy.context.preferences.addons[args.addon_name].preferences
    prefs.folder = args.tl_coupling_path
    bpy.ops.wm.save_userpref()

    print("3D Immersion TL Successfully Reloaded")


if __name__ == '__main__':
    main()